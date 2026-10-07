"""
Pydantic Schemas for Extracted Invoice Fields and Confidence Scores.
Used to validate the structured output of pdfplumber and OCR fallback parsers.
"""

from datetime import date
from typing import Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


class ExtractedLineItem(BaseModel):
    line_number: int = Field(..., description="Line item position (e.g. 10, 20)")
    item_description: str = Field(..., description="Description of product or service")
    quantity: float = Field(..., gt=0, description="Billed quantity")
    unit_of_measure: str = Field("EA", description="Unit of measure (e.g. EA, BOX, DRUM)")
    unit_price: float = Field(..., gt=0, description="Unit price")
    net_amount: float = Field(..., ge=0, description="Total net price")
    tax_amount: float = Field(..., ge=0, description="Calculated tax amount")
    total_amount: float = Field(..., ge=0, description="Gross amount")


class ExtractedInvoice(BaseModel):
    invoice_number: str = Field(..., min_length=3, description="Invoice document number")
    vendor_id: str = Field(..., description="SAP LIFNR or vendor identifier")
    vendor_name: Optional[str] = None
    tax_id: Optional[str] = None
    invoice_date: date = Field(..., description="Date stated on invoice")
    po_number: Optional[str] = Field(None, description="Referenced PO number or phantom PO")
    currency: str = Field(
        ..., min_length=3, max_length=3, description="Currency code (e.g. INR, USD)"
    )
    items: List[ExtractedLineItem] = Field(default_factory=list, description="Extracted line items")
    total_net_amount: float = Field(..., ge=0, description="Invoice subtotal before tax")
    total_tax_amount: float = Field(..., ge=0, description="Invoice tax total")
    total_gross_amount: float = Field(..., ge=0, description="Total payable")
    stated_fx_rate: Optional[float] = Field(
        None, gt=0, description="Claimed FX conversion rate to base currency"
    )
    bank_name: Optional[str] = None
    bank_account_number: Optional[str] = None
    bank_code: Optional[str] = None
    is_ocr_fallback_used: bool = False
    raw_text: Optional[str] = None

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, v: str) -> str:
        return v.strip().upper()


class ExtractionResult(BaseModel):
    invoice: ExtractedInvoice
    field_confidences: Dict[str, float] = Field(
        ..., description="Confidence scores (0.0 to 1.0) per field"
    )
    overall_confidence: float = Field(..., ge=0.0, le=1.0)
    flagged_for_review: bool = False
    low_confidence_fields: List[str] = Field(default_factory=list)
