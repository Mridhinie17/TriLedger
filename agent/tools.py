"""
Read-Only Tools for TriLedger LangGraph Agent.
Provides strictly read-only access to ERP entities:
- get_po(po_number)
- get_receipt(po_number)
- get_invoice(invoice_number)
- vendor_history(vendor_id)
- find_duplicates(invoice_number)
- get_fx_rate(currency, date)
- explain_discrepancy(invoice_number)
"""

from datetime import date
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select, func, desc

from db.models import (
    Invoice,
    PurchaseOrder,
    PurchaseOrderItem,
    GoodsReceipt,
    Vendor,
    FXRate
)
from fx.loader import FXResolver
from matching.engine import ReconciliationEngine
from matching.duplicate_detector import DuplicateDetector
from agent.guardrails import GuardrailManager


class ReadOnlyTools:
    def __init__(self, db: Session):
        self.db = db
        self.fx_resolver = FXResolver(db)
        self.engine = ReconciliationEngine(db)
        self.duplicate_detector = DuplicateDetector(db)

    def get_po(self, po_number: str) -> Dict[str, Any]:
        """Fetch Purchase Order details including line items, contracted pricing, and currency."""
        po = self.db.execute(
            select(PurchaseOrder).where(PurchaseOrder.po_number == po_number)
        ).scalar_one_or_none()

        if not po:
            return {"error": f"Purchase Order {po_number} not found in records"}

        items = []
        for it in po.items:
            items.append({
                "line_number": it.line_number,
                "item_description": it.item_description,
                "quantity": it.quantity,
                "unit_of_measure": it.unit_of_measure,
                "unit_price": it.unit_price,
                "tax_rate_pct": it.tax_rate_pct,
                "net_amount": it.net_amount,
                "tax_amount": it.tax_amount,
                "total_amount": it.total_amount
            })

        return {
            "po_number": po.po_number,
            "vendor_id": po.vendor_id,
            "order_date": po.order_date.isoformat(),
            "currency": po.currency,
            "total_net_amount": po.total_net_amount,
            "total_tax_amount": po.total_tax_amount,
            "total_gross_amount": po.total_gross_amount,
            "status": po.status,
            "items": items
        }

    def get_receipt(self, po_number: str) -> Dict[str, Any]:
        """Fetch physical Goods Receipt (GR) material records for a PO."""
        receipts = self.db.execute(
            select(GoodsReceipt).where(GoodsReceipt.po_number == po_number)
        ).scalars().all()

        if not receipts:
            return {"po_number": po_number, "receipts_found": 0, "items": []}

        items = []
        for r in receipts:
            items.append({
                "gr_number": r.gr_number,
                "line_number": r.line_number,
                "receipt_date": r.receipt_date.isoformat(),
                "item_description": r.item_description,
                "quantity_received": r.quantity_received,
                "unit_of_measure": r.unit_of_measure,
                "received_by": r.received_by
            })

        return {
            "po_number": po_number,
            "receipts_found": len(receipts),
            "items": items
        }

    def get_invoice(self, invoice_number: str) -> Dict[str, Any]:
        """Fetch incoming invoice details with masked bank account details."""
        inv = self.db.execute(
            select(Invoice).where(Invoice.invoice_number == invoice_number)
        ).scalar_one_or_none()

        if not inv:
            return {"error": f"Invoice {invoice_number} not found"}

        items = []
        for it in inv.items:
            items.append({
                "line_number": it.line_number,
                "item_description": it.item_description,
                "quantity": it.quantity,
                "unit_price": it.unit_price,
                "net_amount": it.net_amount,
                "tax_amount": it.tax_amount,
                "total_amount": it.total_amount
            })

        masked_bank = GuardrailManager.mask_bank_details(inv.bank_account_number or "")

        return {
            "invoice_number": inv.invoice_number,
            "vendor_id": inv.vendor_id,
            "po_number": inv.po_number,
            "invoice_date": inv.invoice_date.isoformat(),
            "currency": inv.currency,
            "total_net_amount": inv.total_net_amount,
            "total_tax_amount": inv.total_tax_amount,
            "total_gross_amount": inv.total_gross_amount,
            "stated_fx_rate": inv.stated_fx_rate,
            "bank_account_number": masked_bank,
            "bank_code": inv.bank_code,
            "is_scanned": inv.is_scanned,
            "items": items
        }

    def vendor_history(self, vendor_id: str) -> Dict[str, Any]:
        """Fetch vendor profile and historical billing track record."""
        vendor = self.db.execute(
            select(Vendor).where(Vendor.vendor_id == vendor_id)
        ).scalar_one_or_none()

        if not vendor:
            return {"error": f"Vendor {vendor_id} not found"}

        # Query past invoices for this vendor
        invoices = self.db.execute(
            select(Invoice).where(Invoice.vendor_id == vendor_id)
        ).scalars().all()

        total_spent = sum(inv.total_gross_amount for inv in invoices)
        avg_inv_amt = total_spent / max(len(invoices), 1)

        return {
            "vendor_id": vendor.vendor_id,
            "name": vendor.name,
            "tax_id": vendor.tax_id,
            "default_currency": vendor.default_currency,
            "payment_terms": vendor.payment_terms,
            "master_bank_account": GuardrailManager.mask_bank_details(vendor.bank_account_number),
            "historical_invoices_count": len(invoices),
            "historical_total_spent": round(total_spent, 2),
            "average_invoice_amount": round(avg_inv_amt, 2)
        }

    def find_duplicates(self, invoice_number: str) -> Dict[str, Any]:
        """Runs RapidFuzz duplicate check for an invoice against prior records."""
        inv = self.db.execute(
            select(Invoice).where(Invoice.invoice_number == invoice_number)
        ).scalar_one_or_none()

        if not inv:
            return {"error": f"Invoice {invoice_number} not found"}

        return self.duplicate_detector.check_duplicate(inv)

    def get_fx_rate(self, currency: str, query_date: str) -> Dict[str, Any]:
        """Retrieves official ECB foreign exchange reference rate on date (with rollback)."""
        try:
            d = date.fromisoformat(query_date)
            rate, eff_date = self.fx_resolver.resolve_effective_rate(
                query_date=d,
                base_currency=currency,
                target_currency="INR"
            )
            return {
                "currency": currency,
                "target_currency": "INR",
                "requested_date": query_date,
                "effective_rate_date": eff_date.isoformat(),
                "rate": round(rate, 4),
                "is_rolled_back": (eff_date != d),
                "source": "ECB_EURO_REFERENCE_RATES"
            }
        except Exception as e:
            return {"error": str(e)}

    def explain_discrepancy(self, invoice_number: str) -> Dict[str, Any]:
        """Runs full 3-way matching engine and returns exact mathematical discrepancy details."""
        inv = self.db.execute(
            select(Invoice).where(Invoice.invoice_number == invoice_number)
        ).scalar_one_or_none()

        if not inv:
            return {"error": f"Invoice {invoice_number} not found"}

        res = self.engine.reconcile_invoice(inv)
        return {
            "invoice_number": invoice_number,
            "is_matched": res.is_matched,
            "overall_status": res.overall_status,
            "detected_defects": res.detected_defect_types,
            "discrepancies": [
                {"type": d.check_type, "severity": d.severity, "message": d.message}
                for d in res.discrepancies
            ],
            "isolation_forest_anomaly": res.isolation_forest_anomaly,
            "line_variances": res.line_item_variances
        }
