"""
Data Quality (DQ) Validator for TriLedger.
Validates SAP incoming procurement entities against mathematical and business constraints.
Any malformed or violating record is rejected and routed to the `rejected_rows` dead-letter table.
"""

from typing import Any

from sqlalchemy.orm import Session

from config.settings import settings
from db.models import RejectedRow


class DataQualityValidator:
    def __init__(self, db: Session):
        self.db = db

    def validate_invoice_payload(self, raw_invoice: dict[str, Any]) -> tuple[bool, list[str]]:
        """
        Validates an incoming invoice dictionary before persistence.
        Returns (is_valid, list_of_failure_reasons).
        """
        reasons = []

        # 1. Invoice Number Check
        inv_no = raw_invoice.get("invoice_number")
        if not inv_no or not str(inv_no).strip():
            reasons.append("MISSING_INVOICE_NUMBER")

        # 2. Currency Check
        curr = raw_invoice.get("currency")
        if not curr or curr not in settings.SUPPORTED_CURRENCIES:
            reasons.append(f"UNSUPPORTED_CURRENCY: {curr}")

        # 3. Numeric Headers Check
        net = raw_invoice.get("total_net_amount", 0.0)
        tax = raw_invoice.get("total_tax_amount", 0.0)
        gross = raw_invoice.get("total_gross_amount", 0.0)

        if net < 0 or tax < 0 or gross <= 0:
            reasons.append("NON_POSITIVE_AMOUNTS")

        # 4. Header Math Check (gross == net + tax within 0.10 rounding)
        if abs(gross - (net + tax)) > 0.10:
            reasons.append(f"HEADER_MATH_MISMATCH: gross={gross} vs net+tax={net+tax}")

        # 5. Line items check
        items = raw_invoice.get("items", [])
        if not items:
            reasons.append("EMPTY_LINE_ITEMS")
        else:
            calc_net = sum(it.get("net_amount", 0.0) for it in items)
            if abs(net - calc_net) > 0.10:
                reasons.append(f"LINE_TOTAL_HEADER_NET_MISMATCH: header_net={net} vs sum_lines={calc_net}")

            for idx, it in enumerate(items, start=1):
                qty = it.get("quantity", 0.0)
                price = it.get("unit_price", 0.0)
                if qty <= 0:
                    reasons.append(f"LINE_{idx}_INVALID_QUANTITY: {qty}")
                if price <= 0:
                    reasons.append(f"LINE_{idx}_INVALID_UNIT_PRICE: {price}")

        is_valid = len(reasons) == 0
        if not is_valid:
            # Route to dead-letter rejected_rows table
            self.db.add(RejectedRow(
                source_table="invoices",
                raw_payload=str(raw_invoice),
                rejection_reason="; ".join(reasons)
            ))
            self.db.commit()

        return is_valid, reasons
