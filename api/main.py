"""
TriLedger Enterprise FastAPI Reconciliation Service.
Provides REST APIs for:
- Reconciliation KPIs and summary statistics
- Paginated and filtered invoice queues
- Full 3-way match detail (PO, GR, Invoice line comparisons, tolerances, anomalies)
- High-fidelity PDF streaming
- LangGraph Autonomous Investigation Agent trigger
- Audit-compliant Human-in-the-Loop decision actions
- Instant PDF upload extraction & matching
- Power BI Data Mart generation
- Google Stitch Single Page Application static hosting
"""

import json
import os
import sys
import shutil
from datetime import datetime, date
from pathlib import Path
from typing import Optional, List, Dict, Any

# Ensure project root in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import FastAPI, HTTPException, Query, UploadFile, File, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from sqlalchemy import func, or_

from config.settings import settings
from db.session import get_db, get_db_context
from db.models import Invoice, InvoiceItem, PurchaseOrder, PurchaseOrderItem, GoodsReceipt, Vendor, AuditLog, FXRate
from matching.engine import ReconciliationEngine
from agent.workflow import TriLedgerAgent
from agent.guardrails import GuardrailManager
from marts.exporter import DataMartExporter
from extraction.extractor import InvoiceExtractor
from api.schemas import (
    KPIStats,
    InvoiceSummaryItem,
    InvoiceListResponse,
    InvoiceDetailResponse,
    LineItemDetail,
    ThreeWayMatchComparison,
    DecisionRequest,
    DecisionResponse,
    InvestigationResponse
)

app = FastAPI(
    title="TriLedger Reconciliation Engine API",
    description="Enterprise 3-way match, official ECB FX verification, LangGraph investigation agent, and audit trail.",
    version="1.0.0"
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["System"])
def health_check(db: Session = Depends(get_db)):
    """Health check validating database connectivity."""
    try:
        inv_count = db.query(Invoice).count()
        return {
            "status": "healthy",
            "database": "connected",
            "total_invoices_indexed": inv_count,
            "version": "1.0.0"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database unreachable: {str(e)}")


@app.get("/api/stats", response_model=KPIStats, tags=["Analytics"])
def get_kpi_stats(db: Session = Depends(get_db)):
    """Computes global operational and risk KPIs."""
    total_invoices = db.query(Invoice).count()
    if total_invoices == 0:
        return KPIStats(
            total_invoices=0,
            matched_clean_count=0,
            exception_count=0,
            straight_through_processing_pct=100.0,
            total_spend_inr=0.0,
            high_risk_anomalies=0,
            pending_review=0,
            approved_count=0,
            on_hold_count=0,
            escalated_count=0
        )

    # Status counts
    approved_count = db.query(Invoice).filter(Invoice.match_status == "APPROVED").count()
    on_hold_count = db.query(Invoice).filter(Invoice.match_status == "ON_HOLD").count()
    escalated_count = db.query(Invoice).filter(Invoice.match_status == "ESCALATED").count()
    pending_count = db.query(Invoice).filter(Invoice.match_status.in_(["PENDING", "UNMATCHED"])).count()

    # Calculate total spend normalized to INR (base currency)
    invoices = db.query(Invoice).all()
    total_spend_inr = 0.0
    for inv in invoices:
        rate = inv.stated_fx_rate if inv.stated_fx_rate and inv.stated_fx_rate > 0 else 1.0
        if inv.currency == "INR":
            total_spend_inr += inv.total_gross_amount
        else:
            # stated_fx_rate is X→INR (e.g. 1 EUR = 90 INR), so multiply
            total_spend_inr += (inv.total_gross_amount * rate)

    # Engine match counts
    engine = ReconciliationEngine(db)
    matched_count = 0
    exception_count = 0
    high_risk_anomalies = 0

    for inv in invoices:
        res = engine.reconcile_invoice(inv)
        if res.is_matched:
            matched_count += 1
        else:
            exception_count += 1
        if res.isolation_forest_anomaly:
            high_risk_anomalies += 1

    stp_rate = round((matched_count / total_invoices) * 100.0, 2)

    return KPIStats(
        total_invoices=total_invoices,
        matched_clean_count=matched_count,
        exception_count=exception_count,
        straight_through_processing_pct=stp_rate,
        total_spend_inr=round(total_spend_inr, 2),
        high_risk_anomalies=high_risk_anomalies,
        pending_review=pending_count,
        approved_count=approved_count,
        on_hold_count=on_hold_count,
        escalated_count=escalated_count
    )


@app.get("/api/invoices", response_model=InvoiceListResponse, tags=["Invoices"])
def list_invoices(
    status: Optional[str] = Query(None, description="Filter by match status: APPROVED, ON_HOLD, ESCALATED, PENDING"),
    has_discrepancy: Optional[bool] = Query(None, description="Filter invoices with detected discrepancies"),
    currency: Optional[str] = Query(None, description="Filter by currency: EUR, USD, INR"),
    search: Optional[str] = Query(None, description="Search invoice number or vendor ID"),
    page: int = Query(1, ge=1),
    limit: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """Returns paginated, searchable list of invoices with live reconciliation status."""
    query = db.query(Invoice)

    if status and status.upper() != "ALL":
        query = query.filter(Invoice.match_status == status.upper())

    if currency and currency.upper() != "ALL":
        query = query.filter(Invoice.currency == currency.upper())

    if search:
        search_term = f"%{search.strip()}%"
        query = query.filter(
            or_(
                Invoice.invoice_number.ilike(search_term),
                Invoice.vendor_id.ilike(search_term),
                Invoice.po_number.ilike(search_term)
            )
        )

    all_invoices = query.order_by(Invoice.invoice_number.asc()).all()
    vendors = {v.vendor_id: v.name for v in db.query(Vendor).all()}
    engine = ReconciliationEngine(db)

    items: List[InvoiceSummaryItem] = []
    for inv in all_invoices:
        match_res = engine.reconcile_invoice(inv)
        is_disc = not match_res.is_matched

        if has_discrepancy is not None and is_disc != has_discrepancy:
            continue

        v_name = vendors.get(inv.vendor_id, "Unknown Vendor")
        items.append(
            InvoiceSummaryItem(
                invoice_number=inv.invoice_number,
                vendor_id=inv.vendor_id,
                vendor_name=v_name,
                po_number=inv.po_number,
                invoice_date=inv.invoice_date,
                currency=inv.currency,
                total_gross_amount=round(inv.total_gross_amount, 2),
                match_status=inv.match_status,
                is_scanned=inv.is_scanned,
                defect_types=match_res.detected_defect_types,
                has_discrepancy=is_disc,
                discrepancy_count=len(match_res.discrepancies),
                anomaly_score=round(match_res.isolation_forest_score, 4)
            )
        )

    total_filtered = len(items)
    start_idx = (page - 1) * limit
    end_idx = start_idx + limit
    paginated_items = items[start_idx:end_idx]

    return InvoiceListResponse(
        total=total_filtered,
        page=page,
        limit=limit,
        items=paginated_items
    )


@app.get("/api/invoices/{invoice_number}", response_model=InvoiceDetailResponse, tags=["Invoices"])
def get_invoice_detail(invoice_number: str, db: Session = Depends(get_db)):
    """Retrieves full invoice details, line items, referenced PO and GR, and 3-way match result."""
    inv = db.query(Invoice).filter(Invoice.invoice_number == invoice_number).first()
    if not inv:
        raise HTTPException(status_code=404, detail=f"Invoice '{invoice_number}' not found.")

    vendor = db.query(Vendor).filter(Vendor.vendor_id == inv.vendor_id).first()
    v_name = vendor.name if vendor else "Unknown Vendor"
    v_tax_id = vendor.tax_id if vendor else None
    masked_bank = GuardrailManager.mask_bank_details(inv.bank_account_number or (vendor.bank_account_number if vendor else ""))

    # Line items
    line_items: List[LineItemDetail] = []
    for it in inv.items:
        line_items.append(
            LineItemDetail(
                line_number=it.line_number,
                item_description=it.item_description,
                quantity=it.quantity,
                unit_of_measure=it.unit_of_measure or "EA",
                unit_price=it.unit_price,
                tax_rate_pct=it.tax_rate_pct,
                net_amount=it.net_amount,
                tax_amount=it.tax_amount,
                total_amount=it.total_amount
            )
        )

    # Referenced PO details
    po_data = None
    if inv.po_number:
        po = db.query(PurchaseOrder).filter(PurchaseOrder.po_number == inv.po_number).first()
        if po:
            po_data = {
                "po_number": po.po_number,
                "vendor_id": po.vendor_id,
                "currency": po.currency,
                "total_net_amount": po.total_net_amount,
                "total_tax_amount": po.total_tax_amount,
                "total_gross_amount": po.total_gross_amount,
                "created_at": po.created_at.isoformat() if po.created_at else None,
                "items": [
                    {
                        "line_number": p_it.line_number,
                        "item_description": p_it.item_description,
                        "quantity": p_it.quantity,
                        "unit_of_measure": p_it.unit_of_measure or "EA",
                        "unit_price": p_it.unit_price,
                        "tax_rate_pct": p_it.tax_rate_pct,
                        "net_amount": p_it.net_amount,
                        "tax_amount": p_it.tax_amount,
                        "total_amount": p_it.total_amount
                    }
                    for p_it in po.items
                ]
            }

    # Referenced Goods Receipts
    gr_data = None
    if inv.po_number:
        grs = db.query(GoodsReceipt).filter(GoodsReceipt.po_number == inv.po_number).all()
        if grs:
            gr_data = {
                "count": len(grs),
                "receipts": [
                    {
                        "gr_number": gr.gr_number,
                        "line_number": gr.line_number,
                        "receipt_date": gr.receipt_date.isoformat() if gr.receipt_date else None,
                        "item_description": gr.item_description,
                        "quantity_received": gr.quantity_received,
                        "unit_of_measure": gr.unit_of_measure,
                        "received_by": gr.received_by
                    }
                    for gr in grs
                ]
            }

    # Reconcile invoice
    engine = ReconciliationEngine(db)
    match_res = engine.reconcile_invoice(inv)

    comparison = ThreeWayMatchComparison(
        is_matched=match_res.is_matched,
        overall_status=match_res.overall_status,
        defect_types=match_res.detected_defect_types,
        discrepancies=[d.model_dump() for d in match_res.discrepancies],
        line_item_variances=match_res.line_item_variances,
        isolation_forest_anomaly=match_res.isolation_forest_anomaly,
        isolation_forest_score=match_res.isolation_forest_score,
        fx_validation=match_res.fx_validation,
        duplicate_info=match_res.duplicate_info
    )

    pdf_path = settings.DATA_DIR / "invoices_pdf" / f"{invoice_number}.pdf"

    return InvoiceDetailResponse(
        invoice_number=inv.invoice_number,
        vendor_id=inv.vendor_id,
        vendor_name=v_name,
        vendor_tax_id=v_tax_id,
        vendor_bank_masked=masked_bank,
        po_number=inv.po_number,
        invoice_date=inv.invoice_date,
        currency=inv.currency,
        total_net_amount=inv.total_net_amount,
        total_tax_amount=inv.total_tax_amount,
        total_gross_amount=inv.total_gross_amount,
        stated_fx_rate=inv.stated_fx_rate or 1.0,
        is_scanned=inv.is_scanned,
        match_status=inv.match_status,
        pdf_available=pdf_path.exists(),
        items=line_items,
        po_details=po_data,
        gr_details=gr_data,
        match_result=comparison
    )


@app.get("/api/invoices/{invoice_number}/pdf", tags=["Invoices"])
def stream_invoice_pdf(invoice_number: str):
    """Streams original high-resolution invoice PDF document."""
    pdf_path = settings.DATA_DIR / "invoices_pdf" / f"{invoice_number}.pdf"
    if not pdf_path.exists():
        raise HTTPException(status_code=404, detail=f"PDF for invoice '{invoice_number}' not found.")
    return FileResponse(
        path=pdf_path,
        media_type="application/pdf",
        filename=f"{invoice_number}.pdf"
    )


@app.post("/api/invoices/{invoice_number}/investigate", response_model=InvestigationResponse, tags=["Agent"])
def investigate_invoice(invoice_number: str, raw_text: Optional[str] = None, db: Session = Depends(get_db)):
    """Triggers LangGraph autonomous investigation agent with cited evidence and audit logging."""
    inv = db.query(Invoice).filter(Invoice.invoice_number == invoice_number).first()
    if not inv:
        raise HTTPException(status_code=404, detail=f"Invoice '{invoice_number}' not found.")

    agent = TriLedgerAgent(db)
    report = agent.investigate(invoice_number=invoice_number, raw_text=raw_text)

    return InvestigationResponse(
        invoice_number=report.invoice_number,
        recommended_action=report.recommended_action,
        confidence=report.confidence,
        case_summary=report.case_summary,
        discrepancy_explanation=report.discrepancy_explanation,
        cited_records=report.cited_records,
        is_adversarial_injection_detected=report.is_adversarial_injection_detected,
        guardrail_status=report.guardrail_status,
        step_history=["sanitize_and_scan", "gather_evidence", "reason_and_analyze", "enforce_guardrails", "log_audit_trail"],
        audit_logged=report.audit_logged
    )


@app.post("/api/invoices/{invoice_number}/decision", response_model=DecisionResponse, tags=["Decisions"])
def record_decision(invoice_number: str, req: DecisionRequest, db: Session = Depends(get_db)):
    """Records human-in-the-loop analyst action into immutable audit log and updates invoice status."""
    inv = db.query(Invoice).filter(Invoice.invoice_number == invoice_number).first()
    if not inv:
        raise HTTPException(status_code=404, detail=f"Invoice '{invoice_number}' not found.")

    prev_status = inv.match_status
    target_status = req.decision.upper()

    # Map request decision to standard match_status
    valid_statuses = {"APPROVE": "APPROVED", "APPROVED": "APPROVED",
                      "HOLD": "ON_HOLD", "ON_HOLD": "ON_HOLD",
                      "ESCALATE": "ESCALATED", "ESCALATED": "ESCALATED",
                      "REJECT": "REJECTED", "REJECTED": "REJECTED"}
    
    if target_status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Invalid decision '{req.decision}'. Choose APPROVE, ON_HOLD, ESCALATE, or REJECT.")

    new_status = valid_statuses[target_status]
    inv.match_status = new_status

    # Write immutable audit log
    audit_entry = AuditLog(
        entity_type="INVOICE",
        entity_id=invoice_number,
        action=f"DECISION_{new_status}",
        actor=req.analyst_name,
        details=json.dumps({
            "previous_status": prev_status,
            "new_status": new_status,
            "reason": req.reason,
            "notes": req.notes,
            "timestamp": datetime.utcnow().isoformat()
        })
    )
    db.add(audit_entry)
    db.commit()
    db.refresh(audit_entry)

    return DecisionResponse(
        invoice_number=invoice_number,
        previous_status=prev_status,
        new_status=new_status,
        audit_log_id=audit_entry.id,
        timestamp=audit_entry.timestamp,
        message=f"Invoice status updated to {new_status} by {req.analyst_name}. Audit log recorded."
    )


@app.post("/api/invoices/upload", tags=["Extraction"])
async def upload_and_process_invoice(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Uploads a PDF invoice, executes OCR/digital extraction, runs 3-way matching, and returns result."""
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF invoice files are supported.")

    dest_path = settings.DATA_DIR / "invoices_pdf" / file.filename
    with open(dest_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    extractor = InvoiceExtractor()
    extracted = extractor.extract(dest_path)

    # Check if invoice exists in DB or create temporary check
    existing_inv = db.query(Invoice).filter(Invoice.invoice_number == extracted.invoice_number).first()
    
    match_details = None
    if existing_inv:
        engine = ReconciliationEngine(db)
        match_res = engine.reconcile_invoice(existing_inv)
        match_details = {
            "is_matched": match_res.is_matched,
            "status": match_res.overall_status,
            "discrepancies": [d.model_dump() for d in match_res.discrepancies]
        }

    return {
        "status": "extracted",
        "file_name": file.filename,
        "extraction_method": extracted.extraction_method,
        "confidence_score": extracted.confidence_score,
        "is_scanned_ocr": extracted.is_scanned_ocr,
        "invoice_data": {
            "invoice_number": extracted.invoice_number,
            "vendor_id": extracted.vendor_id,
            "po_number": extracted.po_number,
            "invoice_date": extracted.invoice_date.isoformat() if extracted.invoice_date else None,
            "currency": extracted.currency,
            "total_gross_amount": extracted.total_gross_amount,
            "items_count": len(extracted.line_items)
        },
        "match_result": match_details
    }


@app.get("/api/marts/export", tags=["Analytics"])
def trigger_mart_export():
    """Generates and updates Power BI analytical CSV and Parquet data marts."""
    exporter = DataMartExporter()
    paths = exporter.export_all()
    formatted = {}
    for mart_name, files in paths.items():
        formatted[mart_name] = {
            "csv": str(files["csv"].relative_to(settings.BASE_DIR)),
            "parquet": str(files["parquet"].relative_to(settings.BASE_DIR)),
            "csv_size_bytes": files["csv"].stat().st_size,
            "parquet_size_bytes": files["parquet"].stat().st_size
        }
    return {
        "message": "Power BI Data Marts successfully generated",
        "timestamp": datetime.utcnow().isoformat(),
        "marts": formatted
    }


# Static React SPA hosting if frontend/dist exists
frontend_dist = settings.BASE_DIR / "frontend" / "dist"
if frontend_dist.exists():
    app.mount("/assets", StaticFiles(directory=str(frontend_dist / "assets")), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_react_spa(full_path: str):
        file_path = frontend_dist / full_path
        if file_path.exists() and file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(frontend_dist / "index.html")
