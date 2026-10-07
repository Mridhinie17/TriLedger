"""
Power BI Data Mart Exporter for TriLedger.
Generates analytical datasets in both CSV and Apache Parquet formats:
1. Spend Analysis: Aggregated and line-level vendor spend normalized to EUR.
2. Exception Log: 3-way match reconciliation discrepancies, defect classifications, and severity.
3. Invoice Aging: Payables aging breakdown by time horizons (<30, 31-60, 61-90, >90 days).
4. Open Payables: Pending and approved obligations with bank safety masking.
5. FX Sensitivity: Currency exposures and FX rate drift impact.
"""

import sys
from datetime import datetime, date
from pathlib import Path
from typing import Dict, Any, List

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import numpy as np

from config.settings import settings
from db.models import Invoice, PurchaseOrder, GoodsReceipt, Vendor, FXRate, AuditLog
from db.session import get_db_context
from matching.engine import ReconciliationEngine


class DataMartExporter:
    """Exports data marts to CSV and Parquet for Power BI and analytical dashboards."""

    def __init__(self, output_dir: Path = settings.DATA_DIR / "marts"):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def export_all(self) -> Dict[str, Dict[str, Path]]:
        """Generates all 5 marts in CSV and Parquet."""
        results = {
            "spend_analysis": self.export_spend_analysis(),
            "exception_log": self.export_exception_log(),
            "invoice_aging": self.export_invoice_aging(),
            "open_payables": self.export_open_payables(),
            "fx_sensitivity": self.export_fx_sensitivity(),
        }
        return results

    def _save_df(self, df: pd.DataFrame, name: str) -> Dict[str, Path]:
        csv_path = self.output_dir / f"{name}.csv"
        parquet_path = self.output_dir / f"{name}.parquet"

        df.to_csv(csv_path, index=False)
        df.to_parquet(parquet_path, index=False, engine="pyarrow")
        return {"csv": csv_path, "parquet": parquet_path}

    def export_spend_analysis(self) -> Dict[str, Path]:
        with get_db_context() as db:
            invoices = db.query(Invoice).all()
            vendors = {v.vendor_id: v for v in db.query(Vendor).all()}
            
            rows = []
            for inv in invoices:
                v = vendors.get(inv.vendor_id)
                rate = inv.stated_fx_rate if inv.stated_fx_rate and inv.stated_fx_rate > 0 else 1.0
                
                # Base EUR equivalent calculation
                if inv.currency == "EUR":
                    amount_eur = inv.total_gross_amount
                elif inv.currency == "USD":
                    amount_eur = inv.total_gross_amount / rate if rate > 0 else inv.total_gross_amount
                elif inv.currency == "INR":
                    amount_eur = inv.total_gross_amount / rate if rate > 0 else inv.total_gross_amount
                else:
                    amount_eur = inv.total_gross_amount

                rows.append({
                    "invoice_number": inv.invoice_number,
                    "vendor_id": inv.vendor_id,
                    "vendor_name": v.name if v else "Unknown",
                    "vendor_country": "DE" if inv.currency == "EUR" else ("US" if inv.currency == "USD" else "IN"),
                    "invoice_date": inv.invoice_date.isoformat() if inv.invoice_date else None,
                    "currency": inv.currency,
                    "total_net_amount": round(inv.total_net_amount, 2),
                    "total_tax_amount": round(inv.total_tax_amount, 2),
                    "total_gross_amount": round(inv.total_gross_amount, 2),
                    "total_amount_eur": round(amount_eur, 2),
                    "payment_terms": v.payment_terms if v else "Net 30",
                    "match_status": inv.match_status,
                    "is_scanned": inv.is_scanned,
                    "created_at": inv.created_at.isoformat() if inv.created_at else None
                })

            df = pd.DataFrame(rows)
            return self._save_df(df, "spend_analysis")

    def export_exception_log(self) -> Dict[str, Path]:
        with get_db_context() as db:
            engine = ReconciliationEngine(db)
            invoices = db.query(Invoice).all()
            
            rows = []
            for inv in invoices:
                result = engine.reconcile_invoice(inv)
                if not result.is_matched:
                    discrepancy_msgs = [d.message for d in result.discrepancies]
                    severities = [d.severity for d in result.discrepancies]
                    max_severity = "HIGH" if "HIGH" in severities else ("MEDIUM" if "MEDIUM" in severities else "LOW")

                    rows.append({
                        "invoice_number": inv.invoice_number,
                        "vendor_id": inv.vendor_id,
                        "po_number": inv.po_number or "MISSING_PO",
                        "invoice_date": inv.invoice_date.isoformat() if inv.invoice_date else None,
                        "discrepancy_count": len(result.discrepancies),
                        "defect_types": "; ".join(result.detected_defect_types),
                        "discrepancies": " | ".join(discrepancy_msgs),
                        "max_severity": max_severity,
                        "is_anomaly": result.isolation_forest_anomaly,
                        "anomaly_score": round(result.isolation_forest_score, 4),
                        "match_status": inv.match_status
                    })

            df = pd.DataFrame(rows)
            if df.empty:
                df = pd.DataFrame(columns=[
                    "invoice_number", "vendor_id", "po_number", "invoice_date",
                    "discrepancy_count", "defect_types", "discrepancies",
                    "max_severity", "is_anomaly", "anomaly_score", "match_status"
                ])
            return self._save_df(df, "exception_log")

    def export_invoice_aging(self) -> Dict[str, Path]:
        ref_date = date.today()
        with get_db_context() as db:
            invoices = db.query(Invoice).all()
            rows = []
            for inv in invoices:
                inv_date = inv.invoice_date or date.today()
                age_days = (ref_date - inv_date).days
                if age_days < 0:
                    age_days = 0

                if age_days <= 30:
                    bucket = "0-30 Days (Current)"
                elif age_days <= 60:
                    bucket = "31-60 Days"
                elif age_days <= 90:
                    bucket = "61-90 Days"
                else:
                    bucket = "90+ Days (Overdue)"

                rows.append({
                    "invoice_number": inv.invoice_number,
                    "vendor_id": inv.vendor_id,
                    "invoice_date": inv_date.isoformat(),
                    "age_days": age_days,
                    "aging_bucket": bucket,
                    "currency": inv.currency,
                    "total_amount": round(inv.total_gross_amount, 2),
                    "match_status": inv.match_status
                })

            df = pd.DataFrame(rows)
            return self._save_df(df, "invoice_aging")

    def export_open_payables(self) -> Dict[str, Path]:
        with get_db_context() as db:
            vendors = {v.vendor_id: v for v in db.query(Vendor).all()}
            invoices = db.query(Invoice).filter(Invoice.match_status != "REJECTED").all()
            
            rows = []
            for inv in invoices:
                v = vendors.get(inv.vendor_id)
                account_str = str(inv.bank_account_number or "")
                masked_account = ("*" * max(0, len(account_str) - 4) + account_str[-4:]) if len(account_str) > 4 else "****"

                rows.append({
                    "invoice_number": inv.invoice_number,
                    "vendor_id": inv.vendor_id,
                    "vendor_name": v.name if v else "Unknown",
                    "currency": inv.currency,
                    "total_gross_amount": round(inv.total_gross_amount, 2),
                    "masked_bank_account": masked_account,
                    "match_status": inv.match_status,
                    "bank_code": inv.bank_code or (v.bank_code if v else ""),
                    "requires_review": inv.match_status in ("ON_HOLD", "ESCALATED", "PENDING")
                })

            df = pd.DataFrame(rows)
            return self._save_df(df, "open_payables")

    def export_fx_sensitivity(self) -> Dict[str, Path]:
        with get_db_context() as db:
            invoices = db.query(Invoice).filter(Invoice.currency != "EUR").all()
            
            rows = []
            for inv in invoices:
                fx_rec = db.query(FXRate).filter(
                    FXRate.target_currency == inv.currency,
                    FXRate.rate_date <= inv.invoice_date
                ).order_by(FXRate.rate_date.desc()).first()

                official_rate = fx_rec.rate if fx_rec else 1.0
                claimed_rate = inv.stated_fx_rate if inv.stated_fx_rate else official_rate
                
                pct_variance = 0.0
                if official_rate > 0:
                    pct_variance = round(((claimed_rate - official_rate) / official_rate) * 100.0, 3)

                claimed_eur = inv.total_gross_amount / claimed_rate if claimed_rate > 0 else 0
                official_eur = inv.total_gross_amount / official_rate if official_rate > 0 else 0
                fx_drift_eur = round(abs(claimed_eur - official_eur), 2)

                rows.append({
                    "invoice_number": inv.invoice_number,
                    "currency": inv.currency,
                    "invoice_date": inv.invoice_date.isoformat() if inv.invoice_date else None,
                    "claimed_fx_rate": round(claimed_rate, 4),
                    "official_ecb_rate": round(official_rate, 4),
                    "variance_pct": pct_variance,
                    "invoice_amount_local": round(inv.total_gross_amount, 2),
                    "fx_drift_impact_eur": fx_drift_eur,
                    "is_over_tolerance": abs(pct_variance) > settings.load_tolerances().get("matching", {}).get("fx_rate_tolerance_pct", 1.5)
                })

            df = pd.DataFrame(rows)
            if df.empty:
                df = pd.DataFrame(columns=[
                    "invoice_number", "currency", "invoice_date", "claimed_fx_rate",
                    "official_ecb_rate", "variance_pct", "invoice_amount_local",
                    "fx_drift_impact_eur", "is_over_tolerance"
                ])
            return self._save_df(df, "fx_sensitivity")


if __name__ == "__main__":
    exporter = DataMartExporter()
    paths = exporter.export_all()
    print("Exported Power BI Data Marts:")
    for mart, files in paths.items():
        print(f"  {mart}:")
        print(f"    CSV: {files['csv']}")
        print(f"    Parquet: {files['parquet']}")
