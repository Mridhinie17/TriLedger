"""
Integration and Unit Tests for TriLedger Phase 5: Interfaces, API, and Data Marts.
Verifies FastAPI REST endpoints, PDF streaming, decision logging, and Power BI mart generation.
"""

from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from config.settings import settings
from db.session import get_db_context
from db.models import Invoice, AuditLog
from api.main import app
from marts.exporter import DataMartExporter

client = TestClient(app)


def test_health_endpoint():
    """Verify health endpoint returns 200 OK and database connectivity."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["total_invoices_indexed"] > 0


def test_kpi_stats_endpoint():
    """Verify stats endpoint computes global KPIs correctly."""
    response = client.get("/api/stats")
    assert response.status_code == 200
    stats = response.json()
    assert stats["total_invoices"] == 800
    assert stats["total_spend_inr"] > 0
    assert 0 <= stats["straight_through_processing_pct"] <= 100
    assert stats["matched_clean_count"] > 0
    assert stats["exception_count"] > 0


def test_list_invoices_pagination_and_filters():
    """Verify invoice list supports pagination, search, and status filters."""
    # Default paginated
    resp = client.get("/api/invoices?page=1&limit=10")
    assert resp.status_code == 200
    data = resp.json()
    assert data["page"] == 1
    assert data["limit"] == 10
    assert len(data["items"]) == 10
    assert data["total"] >= 10

    # Filter with discrepancies
    resp_disc = client.get("/api/invoices?has_discrepancy=true&limit=5")
    assert resp_disc.status_code == 200
    disc_data = resp_disc.json()
    assert all(item["has_discrepancy"] is True for item in disc_data["items"])


def test_invoice_detail_and_pdf_streaming():
    """Verify invoice detail includes PO/GR comparisons and PDF streams correctly."""
    with get_db_context() as db:
        inv = db.query(Invoice).first()
        assert inv is not None
        inv_num = inv.invoice_number

    resp = client.get(f"/api/invoices/{inv_num}")
    assert resp.status_code == 200
    detail = resp.json()
    assert detail["invoice_number"] == inv_num
    assert "vendor_name" in detail
    assert "match_result" in detail
    assert len(detail["items"]) > 0

    # Stream PDF
    pdf_resp = client.get(f"/api/invoices/{inv_num}/pdf")
    assert pdf_resp.status_code == 200
    assert pdf_resp.headers["content-type"] == "application/pdf"
    assert len(pdf_resp.content) > 0


def test_agent_investigate_endpoint():
    """Verify FastAPI triggers LangGraph agent investigation and returns cited records."""
    with get_db_context() as db:
        inv = db.query(Invoice).first()
        inv_num = inv.invoice_number

    resp = client.post(f"/api/invoices/{inv_num}/investigate")
    assert resp.status_code == 200
    result = resp.json()
    assert result["invoice_number"] == inv_num
    assert result["recommended_action"] in ("APPROVE", "HOLD", "ESCALATE")
    assert result["confidence"] > 0.5
    assert len(result["cited_records"]) > 0


def test_record_analyst_decision():
    """Verify analyst decision updates status and appends to immutable audit trail."""
    with get_db_context() as db:
        inv = db.query(Invoice).first()
        inv_num = inv.invoice_number

    payload = {
        "decision": "ON_HOLD",
        "analyst_name": "lead_auditor@enterprise.com",
        "reason": "Temporary hold pending supplier quantity confirmation",
        "notes": "Verified by procurement desk"
    }

    resp = client.post(f"/api/invoices/{inv_num}/decision", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["invoice_number"] == inv_num
    assert data["new_status"] == "ON_HOLD"
    assert data["audit_log_id"] > 0

    # Verify directly in DB
    with get_db_context() as db:
        updated_inv = db.query(Invoice).filter(Invoice.invoice_number == inv_num).first()
        assert updated_inv.match_status == "ON_HOLD"
        audit = db.query(AuditLog).filter(AuditLog.id == data["audit_log_id"]).first()
        assert audit.actor == "lead_auditor@enterprise.com"
        assert audit.action == "DECISION_ON_HOLD"


def test_power_bi_mart_exports(tmp_path):
    """Verify DataMartExporter generates all 5 datasets in CSV and Parquet formats."""
    exporter = DataMartExporter(output_dir=tmp_path)
    paths = exporter.export_all()

    expected_marts = ["spend_analysis", "exception_log", "invoice_aging", "open_payables", "fx_sensitivity"]
    for mart in expected_marts:
        assert mart in paths
        csv_file = paths[mart]["csv"]
        parquet_file = paths[mart]["parquet"]
        assert csv_file.exists(), f"Missing {mart}.csv"
        assert parquet_file.exists(), f"Missing {mart}.parquet"
        assert csv_file.stat().st_size > 0
        assert parquet_file.stat().st_size > 0
