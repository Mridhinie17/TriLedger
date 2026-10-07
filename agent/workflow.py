"""
LangGraph Multi-Step Reconciliation Investigation Agent for TriLedger.
Coordinates:
1. Input sanitization & prompt injection guardrail defense.
2. Read-only evidence retrieval (PO, Goods Receipts, Vendor Profile, FX Reference Rates).
3. LLM reasoning (Groq llama-3.3-70b-versatile with deterministic offline fallback).
4. Safety invariant validation (blocks unauthorized APPROVE, validates cited records).
5. Immutable audit trail logging (agent cannot mutate business tables).
"""

import json
import re
from typing import Dict, Any, List, Optional, TypedDict
from pydantic import BaseModel, Field

from sqlalchemy.orm import Session
from langgraph.graph import StateGraph, END

from config.settings import settings
from db.models import AuditLog, Invoice
from agent.tools import ReadOnlyTools
from agent.guardrails import GuardrailManager


class CaseInvestigationReport(BaseModel):
    invoice_number: str
    recommended_action: str = Field(..., description="APPROVE, HOLD, or ESCALATE")
    confidence: float = Field(..., ge=0.0, le=1.0)
    case_summary: str
    discrepancy_explanation: str
    cited_records: List[str] = Field(default_factory=list, description="IDs of cited DB records (e.g. PO-..., GR-..., VEND-...)")
    is_adversarial_injection_detected: bool = False
    guardrail_status: str = "PASSED"
    audit_logged: bool = False


class AgentState(TypedDict):
    invoice_number: str
    raw_invoice_text: Optional[str]
    is_adversarial: bool
    injection_matches: List[str]
    retrieved_evidence: Dict[str, Any]
    cited_records: List[str]
    case_summary: str
    discrepancy_explanation: str
    recommended_action: str
    confidence: float
    guardrail_status: str
    audit_logged: bool


class TriLedgerAgent:
    def __init__(self, db: Session):
        self.db = db
        self.tools = ReadOnlyTools(db)
        self.guardrails = GuardrailManager()
        self.graph = self._build_graph()

    def _build_graph(self):
        builder = StateGraph(AgentState)

        builder.add_node("sanitize_and_scan", self._sanitize_node)
        builder.add_node("gather_evidence", self._gather_evidence_node)
        builder.add_node("reason_and_analyze", self._reason_node)
        builder.add_node("enforce_guardrails", self._guardrail_node)
        builder.add_node("log_audit_trail", self._audit_node)

        builder.set_entry_point("sanitize_and_scan")
        builder.add_edge("sanitize_and_scan", "gather_evidence")
        builder.add_edge("gather_evidence", "reason_and_analyze")
        builder.add_edge("reason_and_analyze", "enforce_guardrails")
        builder.add_edge("enforce_guardrails", "log_audit_trail")
        builder.add_edge("log_audit_trail", END)

        return builder.compile()

    def _sanitize_node(self, state: AgentState) -> Dict[str, Any]:
        """Scans for adversarial prompt injections and sanitizes input boundaries."""
        raw_text = state.get("raw_invoice_text") or ""
        is_inj, matches = self.guardrails.scan_prompt_injection(raw_text)

        return {
            "is_adversarial": is_inj,
            "injection_matches": matches
        }

    def _gather_evidence_node(self, state: AgentState) -> Dict[str, Any]:
        """Calls read-only tools to collect PO, Goods Receipts, Vendor history, and FX rates."""
        inv_no = state["invoice_number"]

        invoice_data = self.tools.get_invoice(inv_no)
        discrepancy_data = self.tools.explain_discrepancy(inv_no)

        po_no = invoice_data.get("po_number")
        po_data = self.tools.get_po(po_no) if po_no else {"error": "NO_PO"}
        receipt_data = self.tools.get_receipt(po_no) if po_no else {"items": []}

        vend_id = invoice_data.get("vendor_id")
        vendor_data = self.tools.vendor_history(vend_id) if vend_id else {}

        dupe_data = self.tools.find_duplicates(inv_no)

        fx_data = {}
        if invoice_data.get("currency") != "INR" and invoice_data.get("invoice_date"):
            fx_data = self.tools.get_fx_rate(invoice_data["currency"], invoice_data["invoice_date"])

        evidence = {
            "invoice": invoice_data,
            "purchase_order": po_data,
            "receipts": receipt_data,
            "vendor": vendor_data,
            "discrepancy": discrepancy_data,
            "duplicate_check": dupe_data,
            "fx_rate": fx_data
        }

        # Build list of real cited records
        cited = []
        if po_no and "error" not in po_data:
            cited.append(po_no)
        if vend_id and "error" not in vendor_data:
            cited.append(vend_id)
        if receipt_data.get("items"):
            for r in receipt_data["items"][:2]:
                if "gr_number" in r:
                    cited.append(r["gr_number"])
        if dupe_data.get("duplicate_of"):
            cited.append(dupe_data["duplicate_of"])

        return {
            "retrieved_evidence": evidence,
            "cited_records": list(dict.fromkeys(cited))
        }

    def _reason_node(self, state: AgentState) -> Dict[str, Any]:
        """Synthesizes evidence and generates structured investigation recommendation."""
        evidence = state["retrieved_evidence"]
        is_inj = state.get("is_adversarial", False)

        # Check if live Groq API key is configured
        if settings.GROQ_API_KEY and not is_inj:
            try:
                from langchain_groq import ChatGroq
                llm = ChatGroq(
                    model=settings.GROQ_MODEL,
                    api_key=settings.GROQ_API_KEY,
                    temperature=0.1
                )
                system_prompt = (
                    "You are TriLedger's Senior Audit Agent. Analyze the procurement reconciliation evidence.\n"
                    "Your recommendation MUST be one of: APPROVE, HOLD, or ESCALATE.\n"
                    "Rules:\n"
                    "- If all checks match within tolerance, recommend APPROVE.\n"
                    "- If unit price, quantity, or tax discrepancies exist, recommend HOLD.\n"
                    "- If bank details changed, phantom PO, or duplicate billing occurs, recommend ESCALATE.\n"
                    "Return ONLY valid JSON with keys: case_summary, discrepancy_explanation, recommended_action, confidence."
                )
                safe_evidence = GuardrailManager.mask_dict_pii(evidence)
                prompt_text = (
                    f"{system_prompt}\n\nEvidence:\n{json.dumps(safe_evidence, default=str)}\n\n"
                    f"Untrusted Invoice Text:\n{GuardrailManager.wrap_untrusted_content(state.get('raw_invoice_text') or '')}"
                )
                response = llm.invoke(prompt_text)
                parsed = json.loads(re.search(r"\{.*\}", response.content, re.DOTALL).group(0))

                return {
                    "case_summary": parsed.get("case_summary", "Reconciliation investigation complete."),
                    "discrepancy_explanation": parsed.get("discrepancy_explanation", "No discrepancies identified."),
                    "recommended_action": parsed.get("recommended_action", "HOLD").upper(),
                    "confidence": float(parsed.get("confidence", 0.90))
                }
            except Exception:
                pass  # Fall through to deterministic expert engine

        # Deterministic Expert Reasoner (Zero-dependency & fallback)
        discrepancy_info = evidence.get("discrepancy", {})
        is_matched = discrepancy_info.get("is_matched", False)
        defects = discrepancy_info.get("detected_defects", [])
        discrepancies = discrepancy_info.get("discrepancies", [])

        if is_inj:
            return {
                "case_summary": "SECURITY ALERT: Adversarial prompt injection payload detected inside invoice document content.",
                "discrepancy_explanation": f"Document text attempted prompt jailbreak/override: {state.get('injection_matches')}. Immediate security freeze required.",
                "recommended_action": "ESCALATE",
                "confidence": 0.99
            }

        if is_matched:
            return {
                "case_summary": (
                    f"Invoice {state['invoice_number']} successfully verified across 3-way match. "
                    f"PO pricing, Goods Receipt quantities, vendor master records, and FX rates confirmed within policy tolerances."
                ),
                "discrepancy_explanation": "All 3-way reconciliation checks passed successfully with zero variances.",
                "recommended_action": "APPROVE",
                "confidence": 0.98
            }

        # Handle specific defect escalations
        reasons_list = [d.get("message", "") for d in discrepancies]
        explanation = "; ".join(reasons_list)

        if "bank_details_changed" in defects:
            action = "ESCALATE"
            summary = "CRITICAL FRAUD RISK: Invoiced bank remittance account does not match vendor master record on file."
            conf = 0.99
        elif "no_matching_po" in defects:
            action = "ESCALATE"
            summary = "PROCUREMENT VIOLATION: Invoiced purchase order does not exist in purchasing records."
            conf = 0.95
        elif "duplicate_invoice" in defects:
            action = "ESCALATE"
            summary = "DUPLICATE PAYMENT RISK: Invoice matches an existing processed invoice in vendor, PO, amount, and date."
            conf = 0.96
        elif "wrong_currency" in defects:
            action = "HOLD"
            summary = "CURRENCY MISMATCH: Invoiced currency differs from contracted Purchase Order currency."
            conf = 0.94
        elif "price_over_tolerance" in defects:
            action = "HOLD"
            summary = "PRICE EXCEPTION: Invoiced unit price exceeds contracted PO price beyond the 1.0% tolerance."
            conf = 0.95
        elif "quantity_mismatch" in defects:
            action = "HOLD"
            summary = "QUANTITY EXCEPTION: Invoiced quantity exceeds confirmed Goods Receipt warehouse count."
            conf = 0.95
        elif "fx_rate_deviation" in defects:
            action = "HOLD"
            summary = "FX DEVIATION: Invoiced foreign exchange rate deviates beyond ±1.5% from the official ECB reference rate."
            conf = 0.94
        elif "tax_miscalculation" in defects:
            action = "HOLD"
            summary = "TAX ERROR: Invoiced tax calculation math deviates from standard rate."
            conf = 0.92
        else:
            action = "HOLD"
            summary = "RECONCILIATION EXCEPTION: Invoice failed one or more business matching rules."
            conf = 0.90

        return {
            "case_summary": summary,
            "discrepancy_explanation": explanation,
            "recommended_action": action,
            "confidence": conf
        }

    def _guardrail_node(self, state: AgentState) -> Dict[str, Any]:
        """Enforces hard invariants: prevents unauthorized approvals and validates cited records."""
        rec_action = state["recommended_action"]
        is_inj = state.get("is_adversarial", False)
        defects = state["retrieved_evidence"].get("discrepancy", {}).get("detected_defects", [])

        final_action, reason = self.guardrails.validate_action_against_discrepancies(
            recommended_action=rec_action,
            detected_defects=defects,
            is_injection=is_inj
        )

        return {
            "recommended_action": final_action,
            "guardrail_status": "PASSED" if final_action == rec_action else "MODIFIED_BY_GUARDRAIL"
        }

    def _audit_node(self, state: AgentState) -> Dict[str, Any]:
        """Appends immutable audit record to audit_log table. Agent cannot touch ledger tables."""
        audit_entry = AuditLog(
            entity_type="INVOICE",
            entity_id=state["invoice_number"],
            action="AGENT_INVESTIGATED",
            actor="LANGGRAPH_AGENT",
            details=json.dumps({
                "recommended_action": state["recommended_action"],
                "confidence": state["confidence"],
                "cited_records": state["cited_records"],
                "guardrail_status": state["guardrail_status"],
                "summary": state["case_summary"],
                "is_adversarial": state.get("is_adversarial", False)
            })
        )
        self.db.add(audit_entry)
        self.db.commit()

        return {"audit_logged": True}

    def investigate(self, invoice_number: str, raw_text: Optional[str] = None) -> CaseInvestigationReport:
        """Runs the LangGraph investigation workflow end-to-end for a given invoice."""
        initial_state: AgentState = {
            "invoice_number": invoice_number,
            "raw_invoice_text": raw_text,
            "is_adversarial": False,
            "injection_matches": [],
            "retrieved_evidence": {},
            "cited_records": [],
            "case_summary": "",
            "discrepancy_explanation": "",
            "recommended_action": "HOLD",
            "confidence": 0.0,
            "guardrail_status": "PENDING",
            "audit_logged": False
        }

        final_state = self.graph.invoke(initial_state)

        return CaseInvestigationReport(
            invoice_number=final_state["invoice_number"],
            recommended_action=final_state["recommended_action"],
            confidence=final_state["confidence"],
            case_summary=final_state["case_summary"],
            discrepancy_explanation=final_state["discrepancy_explanation"],
            cited_records=final_state["cited_records"],
            is_adversarial_injection_detected=final_state["is_adversarial"],
            guardrail_status=final_state["guardrail_status"],
            audit_logged=final_state["audit_logged"]
        )
