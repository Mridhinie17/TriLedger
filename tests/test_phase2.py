"""
Unit and Integration Tests for TriLedger Phase 2: Extraction.
Verifies digital pdfplumber extraction, Tesseract OCR fallback on scanned PDFs,
per-field confidence scoring, Pydantic schema validation, and evaluation pipeline output.
"""

import json

import pytest
from pydantic import ValidationError

from config.settings import settings
from db.models import Invoice
from db.session import get_db_context
from eval.run_extraction_eval import run_extraction_evaluation
from extraction.extractor import InvoiceExtractor
from extraction.schemas import ExtractedLineItem


@pytest.fixture
def extractor():
    return InvoiceExtractor(confidence_threshold=0.85)


def test_digital_invoice_extraction(extractor):
    """Verify digital PDF extraction using pdfplumber without triggering OCR."""
    with get_db_context() as db:
        digital_inv = db.query(Invoice).filter(Invoice.is_scanned.is_(False)).first()
        assert digital_inv is not None, "No digital invoices in database"

    pdf_path = settings.BASE_DIR / digital_inv.pdf_path
    result = extractor.extract_from_pdf(pdf_path)

    assert result.invoice.is_ocr_fallback_used is False
    assert result.invoice.invoice_number == digital_inv.invoice_number
    assert result.invoice.vendor_id == digital_inv.vendor_id
    assert result.invoice.currency == digital_inv.currency
    assert abs(result.invoice.total_gross_amount - digital_inv.total_gross_amount) <= 0.05
    assert result.overall_confidence >= 0.95
    assert not result.flagged_for_review


def test_scanned_invoice_ocr_fallback(extractor):
    """Verify scanned/rasterized PDF triggers OCR fallback and extracts accurate data."""
    with get_db_context() as db:
        scanned_inv = db.query(Invoice).filter(Invoice.is_scanned.is_(True)).first()
        assert scanned_inv is not None, "No scanned invoices in database"

    pdf_path = settings.BASE_DIR / scanned_inv.pdf_path
    result = extractor.extract_from_pdf(pdf_path)

    assert result.invoice.is_ocr_fallback_used is True
    assert result.invoice.invoice_number == scanned_inv.invoice_number
    assert result.invoice.vendor_id == scanned_inv.vendor_id
    assert result.invoice.currency == scanned_inv.currency
    assert abs(result.invoice.total_gross_amount - scanned_inv.total_gross_amount) <= 0.05
    assert result.overall_confidence >= 0.85


def test_pydantic_schema_validation():
    """Verify Pydantic models enforce types and constraints."""
    # Valid line item
    item = ExtractedLineItem(
        line_number=10,
        item_description="Industrial Ball Bearings",
        quantity=5.0,
        unit_of_measure="EA",
        unit_price=450.0,
        net_amount=2250.0,
        tax_amount=405.0,
        total_amount=2655.0
    )
    assert item.quantity == 5.0

    # Negative quantity should raise ValidationError
    with pytest.raises(ValidationError):
        ExtractedLineItem(
            line_number=10,
            item_description="Invalid Item",
            quantity=-5.0,
            unit_price=100.0,
            net_amount=-500.0,
            tax_amount=0.0,
            total_amount=-500.0
        )


def test_confidence_scoring_and_flagging(extractor, tmp_path):
    """Verify that an invalid or empty document receives low confidence and is flagged."""
    empty_pdf = tmp_path / "empty_doc.pdf"
    # Create empty 1-byte file
    empty_pdf.write_bytes(b"%PDF-1.4\n%%EOF")

    result = extractor.extract_from_pdf(empty_pdf)
    assert result.flagged_for_review is True
    assert result.overall_confidence < 0.85
    assert "invoice_number" in result.low_confidence_fields or "vendor_id" in result.low_confidence_fields


def test_extraction_eval_runner(tmp_path):
    """Verify eval/run_extraction_eval.py produces valid JSON results."""
    eval_output = tmp_path / "extraction_test_result.json"
    run_extraction_evaluation(sample_size=20, output_file=eval_output)

    assert eval_output.exists()
    with open(eval_output, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data["total_evaluated"] == 20
    assert "macro_average_accuracy_pct" in data
    assert "per_field_accuracy" in data
    assert data["macro_average_accuracy_pct"] >= 90.0
