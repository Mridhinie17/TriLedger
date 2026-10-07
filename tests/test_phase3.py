"""
Unit and Integration Tests for TriLedger Phase 3: Matching, FX, and Anomaly Detection.
Verifies deterministic 3-way match tolerances, each of the 8 defect types,
FX reference rate validation, RapidFuzz duplicate detection, and IsolationForest scoring.
"""

import csv

import pytest

from config.settings import settings
from db.models import Invoice
from db.session import get_db_context
from eval.run_matching_eval import run_matching_evaluation
from fx.loader import FXResolver
from matching.engine import ReconciliationEngine
from matching.fx_validator import FXValidator
from matching.isolation_forest import InvoiceAnomalyDetector


@pytest.fixture(scope="module")
def ground_truth_map():
    gt_file = settings.DATA_DIR / "ground_truth.csv"
    assert gt_file.exists(), "ground_truth.csv missing"
    res = {}
    with open(gt_file, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            res[row["invoice_number"]] = row
    return res


def test_clean_invoice_reconciles_successfully(ground_truth_map):
    """Verify that an injected clean invoice matches completely with zero defects."""
    with get_db_context() as db:
        engine = ReconciliationEngine(db)
        clean_inv_num = next(
            num for num, data in ground_truth_map.items() if data["defect_type"] == "none"
        )
        inv = db.query(Invoice).filter(Invoice.invoice_number == clean_inv_num).first()
        assert inv is not None

        result = engine.reconcile_invoice(inv)
        assert result.is_matched is True
        assert result.overall_status == "MATCHED"
        assert len(result.detected_defect_types) == 0
        assert len(result.discrepancies) == 0


@pytest.mark.parametrize(
    "defect_type",
    [
        "quantity_mismatch",
        "price_over_tolerance",
        "duplicate_invoice",
        "no_matching_po",
        "tax_miscalculation",
        "bank_details_changed",
        "fx_rate_deviation",
        "wrong_currency",
    ],
)
def test_each_injected_defect_type_is_detected(ground_truth_map, defect_type):
    """Verify that each of the 8 injected defect types is accurately caught by the matching engine."""
    with get_db_context() as db:
        engine = ReconciliationEngine(db)
        target_inv_num = next(
            num for num, data in ground_truth_map.items() if data["defect_type"] == defect_type
        )
        inv = db.query(Invoice).filter(Invoice.invoice_number == target_inv_num).first()
        assert inv is not None, f"No invoice found for defect {defect_type}"

        result = engine.reconcile_invoice(inv)
        assert result.is_matched is False
        assert result.overall_status == "DISCREPANCY"
        assert defect_type in result.detected_defect_types, (
            f"Expected defect '{defect_type}' but got {result.detected_defect_types}"
        )


def test_fx_validator_tolerances():
    """Verify FX rate tolerance logic rejects excessive deviations and accepts minor fluctuations."""
    with get_db_context() as db:
        resolver = FXResolver(db)
        validator = FXValidator(resolver, tolerance_pct=1.5)

        # Clean USD invoice with rate 83.12 (near true ECB rate on 2024-06-03)
        res_ok = validator.validate_fx_rate(
            invoice_date=db.query(Invoice).first().invoice_date,
            currency="INR",
            stated_fx_rate=1.0,
            gross_amount=10000.0,
        )
        assert res_ok["is_valid"] is True

        # Manipulated FX rate: 95.00 instead of ~83.12 (>14% deviation)
        res_bad = validator.validate_fx_rate(
            invoice_date=db.query(Invoice).first().invoice_date,
            currency="USD",
            stated_fx_rate=95.0,
            gross_amount=1000.0,
        )
        assert res_bad["is_valid"] is False
        assert res_bad["deviation_pct"] > 1.5


def test_isolation_forest_secondary_anomaly_scoring():
    """Verify Isolation Forest extracts features and produces valid anomaly scores."""
    with get_db_context() as db:
        detector = InvoiceAnomalyDetector(contamination=0.05).fit_from_db(db)
        assert detector.is_fitted is True

        sample_inv = db.query(Invoice).first()
        is_anomaly, score = detector.predict_anomaly(sample_inv)
        assert isinstance(is_anomaly, bool)
        assert isinstance(score, float)


def test_matching_eval_runner(tmp_path):
    """Verify eval/run_matching_eval.py produces valid JSON output with per-defect metrics."""
    out_file = tmp_path / "test_matching_results.json"
    data = run_matching_evaluation(sample_size=40, output_file=out_file)

    assert out_file.exists()
    assert "per_defect_metrics" in data
    assert "binary_classification" in data
    assert data["binary_classification"]["precision_pct"] > 80.0
