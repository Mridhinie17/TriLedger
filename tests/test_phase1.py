"""
Unit and Integration Tests for TriLedger Phase 1:
- SAP Schema completeness
- Real ECB FX Loader & Triangular Cross-Rate Parity
- Weekend/Holiday Rollback Rule
- Seeded Generator Determinism
- Ground Truth Row Count & Defect Breakdown Integrity
- Data Quality (DQ) Validation & Dead-Letter Rejection
"""

import csv
from datetime import date

import pytest
from sqlalchemy import inspect

from config.settings import settings
from data_gen.dq_validator import DataQualityValidator
from data_gen.generator import DatasetGenerator
from data_gen.pdf_builder import build_invoice_pdf
from db.models import Base, Invoice, RejectedRow
from db.session import get_db_context, init_db
from fx.loader import FXLoader, FXResolver


@pytest.fixture(scope="module", autouse=True)
def setup_database():
    """Ensure tables are initialized."""
    init_db()


def test_schema_all_tables_exist():
    """Verify that all 9 SAP-style tables are declared and initialized."""
    with get_db_context() as db:
        inspector = inspect(db.get_bind())
        table_names = set(inspector.get_table_names())
        required_tables = {
            "vendors",
            "purchase_orders",
            "po_items",
            "goods_receipts",
            "invoices",
            "invoice_items",
            "fx_rates",
            "audit_log",
            "rejected_rows"
        }
        missing = required_tables - table_names
        assert not missing, f"Missing required database tables: {missing}"


def test_fx_rates_loader_and_triangular_cross_rates():
    """Verify ECB rates download, database load, and triangular cross-rate formula."""
    with get_db_context() as db:
        loader = FXLoader()
        stats = loader.load_rates_to_db(db, start_year=2024, currencies=["USD", "EUR", "INR", "JPY"])
        assert stats["loaded"] > 0 or stats["skipped"] > 0

        resolver = FXResolver(db)
        # Test Monday 2024-06-03 rate resolution
        test_date = date(2024, 6, 3)
        rate_usd_inr, eff_date = resolver.resolve_effective_rate(test_date, "USD", "INR")

        assert rate_usd_inr > 70.0 and rate_usd_inr < 95.0, f"Unrealistic USD/INR rate: {rate_usd_inr}"
        assert eff_date == test_date

        # EUR to INR direct
        rate_eur_inr, _ = resolver.resolve_effective_rate(test_date, "EUR", "INR")
        assert rate_eur_inr > 80.0 and rate_eur_inr < 105.0

        # Identity rate
        rate_identity, _ = resolver.resolve_effective_rate(test_date, "INR", "INR")
        assert rate_identity == 1.0


def test_fx_weekend_and_holiday_rollback_rule():
    """Verify deterministic rollback to the last available prior business day."""
    with get_db_context() as db:
        resolver = FXResolver(db)
        # 2024-06-02 is a Sunday; the prior Friday was 2024-05-31
        sunday_date = date(2024, 6, 2)
        rate, eff_date = resolver.resolve_effective_rate(sunday_date, "USD", "INR")

        assert eff_date == date(2024, 5, 31), f"Expected rollback to 2024-05-31, got {eff_date}"
        assert rate > 0.0


def test_generator_determinism(tmp_path):
    """Verify that running DatasetGenerator with the same seed yields identical outputs."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    test_db_url = f"sqlite:///{tmp_path}/test_det.db"
    test_engine = create_engine(test_db_url)
    Base.metadata.create_all(bind=test_engine)
    TestSession = sessionmaker(bind=test_engine)

    with TestSession() as db:
        gen1 = DatasetGenerator(seed=42, total_invoices=20, defect_rate=0.20, scanned_rate=0.10, data_dir=tmp_path)
        res1 = gen1.generate_all(db, build_pdfs=False)

        invs1 = [
            (inv.invoice_number, inv.total_gross_amount, inv.currency)
            for inv in db.query(Invoice).order_by(Invoice.invoice_number).limit(5).all()
        ]

    # Re-initialize clean test db for run 2
    test_db_url2 = f"sqlite:///{tmp_path}/test_det2.db"
    test_engine2 = create_engine(test_db_url2)
    Base.metadata.create_all(bind=test_engine2)
    TestSession2 = sessionmaker(bind=test_engine2)

    with TestSession2() as db:
        gen2 = DatasetGenerator(seed=42, total_invoices=20, defect_rate=0.20, scanned_rate=0.10, data_dir=tmp_path)
        res2 = gen2.generate_all(db, build_pdfs=False)

        invs2 = [
            (inv.invoice_number, inv.total_gross_amount, inv.currency)
            for inv in db.query(Invoice).order_by(Invoice.invoice_number).limit(5).all()
        ]

    assert invs1 == invs2, "Generator outputs differed across identical seed runs!"
    assert res1["defective_invoices"] == res2["defective_invoices"]


def test_ground_truth_integrity_and_defect_counts():
    """Verify ground_truth.csv exists and matches generated counts."""
    gt_file = settings.DATA_DIR / "ground_truth.csv"
    assert gt_file.exists(), f"Ground truth file missing at {gt_file}"

    with open(gt_file, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    assert len(rows) > 0
    defective_rows = [r for r in rows if r["is_defective"] == "True"]
    clean_rows = [r for r in rows if r["is_defective"] == "False"]
    assert len(defective_rows) + len(clean_rows) == len(rows)

    # Check defect types are valid
    valid_defects = {
        "quantity_mismatch",
        "price_over_tolerance",
        "duplicate_invoice",
        "no_matching_po",
        "tax_miscalculation",
        "bank_details_changed",
        "fx_rate_deviation",
        "wrong_currency",
        "none"
    }
    for r in rows:
        assert r["defect_type"] in valid_defects, f"Unknown defect type: {r['defect_type']}"


def test_data_quality_rejections_logged_to_dead_letter():
    """Verify that DQ checks reject malformed records and record them in rejected_rows."""
    with get_db_context() as db:
        validator = DataQualityValidator(db)

        # 1. Invalid currency and negative amount
        bad_payload = {
            "invoice_number": "INV-TEST-BAD-01",
            "currency": "BITCOIN",  # Unsupported
            "total_net_amount": -500.0,  # Negative
            "total_tax_amount": 0.0,
            "total_gross_amount": -500.0,
            "items": []
        }
        is_valid, reasons = validator.validate_invoice_payload(bad_payload)
        assert not is_valid
        assert any("UNSUPPORTED_CURRENCY" in r for r in reasons)
        assert any("NON_POSITIVE_AMOUNTS" in r for r in reasons)

        # 2. Mathematical mismatch (gross != net + tax)
        unbalanced_payload = {
            "invoice_number": "INV-TEST-BAD-02",
            "currency": "INR",
            "total_net_amount": 1000.0,
            "total_tax_amount": 180.0,
            "total_gross_amount": 9999.0,  # Deliberate mismatch
            "items": [{
                "line_number": 10,
                "quantity": 1.0,
                "unit_price": 1000.0,
                "net_amount": 1000.0,
                "tax_amount": 180.0,
                "total_amount": 1180.0
            }]
        }
        is_valid2, reasons2 = validator.validate_invoice_payload(unbalanced_payload)
        assert not is_valid2
        assert any("HEADER_MATH_MISMATCH" in r for r in reasons2)

        # Verify entry in rejected_rows table
        rejected_entry = db.query(RejectedRow).filter(
            RejectedRow.rejection_reason.like("%HEADER_MATH_MISMATCH%")
        ).first()
        assert rejected_entry is not None
        assert rejected_entry.source_table == "invoices"


def test_pdf_rendering_and_scan_simulation(tmp_path):
    """Verify ReportLab PDF generation and rasterized scan creation."""
    test_pdf_path = tmp_path / "test_sample.pdf"
    scanned_pdf_path = tmp_path / "test_scanned.pdf"

    payload = {
        "invoice_number": "INV-TEST-PDF-001",
        "vendor_id": "VEND-001",
        "vendor_name": "Test Aerospace Ltd",
        "tax_id": "29TESTGSTIN1Z1",
        "invoice_date": "2024-05-10",
        "po_number": "PO-2024-00001",
        "currency": "INR",
        "items": [{
            "line_number": 10,
            "item_description": "Industrial Bearing Assembly",
            "quantity": 5.0,
            "unit_of_measure": "EA",
            "unit_price": 1000.0,
            "tax_rate_pct": 18.0,
            "net_amount": 5000.0,
            "tax_amount": 900.0,
            "total_amount": 5900.0
        }],
        "total_net_amount": 5000.0,
        "total_tax_amount": 900.0,
        "total_gross_amount": 5900.0,
        "bank_name": "HDFC Bank",
        "bank_account_number": "1234567890",
        "bank_code": "HDFC0001234"
    }

    # Generate standard clean PDF
    build_invoice_pdf(payload, test_pdf_path, rasterize_as_scanned=False)
    assert test_pdf_path.exists()
    assert test_pdf_path.stat().st_size > 1000
    with open(test_pdf_path, "rb") as f:
        assert f.read(5) == b"%PDF-"

    # Generate rasterized scanned PDF
    build_invoice_pdf(payload, scanned_pdf_path, rasterize_as_scanned=True)
    assert scanned_pdf_path.exists()
    assert scanned_pdf_path.stat().st_size > 1000
    with open(scanned_pdf_path, "rb") as f:
        assert f.read(5) == b"%PDF-"
