"""
Pydantic Schemas for TriLedger FastAPI Endpoints.
"""

from datetime import date, datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class KPIStats(BaseModel):
    total_invoices: int
    matched_clean_count: int
    exception_count: int
    straight_through_processing_pct: float
    total_spend_inr: float
    high_risk_anomalies: int
    pending_review: int
    approved_count: int
    on_hold_count: int
    escalated_count: int


class InvoiceSummaryItem(BaseModel):
    invoice_number: str
    vendor_id: str
    vendor_name: str
    po_number: Optional[str]
    invoice_date: Optional[date]
    currency: str
    total_gross_amount: float
    match_status: str
    is_scanned: bool
    defect_types: List[str] = Field(default_factory=list)
    has_discrepancy: bool = False
    discrepancy_count: int = 0
    anomaly_score: float = 0.0


class InvoiceListResponse(BaseModel):
    total: int
    page: int
    limit: int
    items: List[InvoiceSummaryItem]


class LineItemDetail(BaseModel):
    line_number: int
    item_description: str
    quantity: float
    unit_of_measure: str = "EA"
    unit_price: float
    tax_rate_pct: float
    net_amount: float
    tax_amount: float
    total_amount: float


class ThreeWayMatchComparison(BaseModel):
    is_matched: bool
    overall_status: str
    defect_types: List[str]
    discrepancies: List[Dict[str, Any]]
    line_item_variances: List[Dict[str, Any]]
    isolation_forest_anomaly: bool
    isolation_forest_score: float
    fx_validation: Optional[Dict[str, Any]] = None
    duplicate_info: Optional[Dict[str, Any]] = None


class InvoiceDetailResponse(BaseModel):
    invoice_number: str
    vendor_id: str
    vendor_name: str
    vendor_tax_id: Optional[str]
    vendor_bank_masked: str
    po_number: Optional[str]
    invoice_date: Optional[date]
    currency: str
    total_net_amount: float
    total_tax_amount: float
    total_gross_amount: float
    stated_fx_rate: float
    is_scanned: bool
    match_status: str
    pdf_available: bool
    items: List[LineItemDetail]
    po_details: Optional[Dict[str, Any]] = None
    gr_details: Optional[Dict[str, Any]] = None
    match_result: Optional[ThreeWayMatchComparison] = None


class DecisionRequest(BaseModel):
    decision: str = Field(..., description="APPROVE, ON_HOLD, ESCALATE, or REJECT")
    analyst_name: str = Field("analyst@enterprise.com", description="Analyst identifier")
    reason: str = Field(..., description="Justification for override/action")
    notes: Optional[str] = None


class DecisionResponse(BaseModel):
    invoice_number: str
    previous_status: str
    new_status: str
    audit_log_id: int
    timestamp: datetime
    message: str


class InvestigationResponse(BaseModel):
    invoice_number: str
    recommended_action: str
    confidence: float
    case_summary: str
    discrepancy_explanation: str
    cited_records: List[str]
    is_adversarial_injection_detected: bool
    guardrail_status: str
    step_history: List[str]
    audit_logged: bool
