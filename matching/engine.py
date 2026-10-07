"""
Central Three-Way Matching Engine for TriLedger.
Performs deterministic 3-way reconciliation across Purchase Orders (PO), Goods Receipts (GR), and Invoices.
Integrates FX validation, RapidFuzz duplicate detection, and IsolationForest anomaly scoring.
Tolerances are externalized via config/tolerances.yaml.
"""

from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select

from config.settings import settings
from db.models import (
    Invoice,
    PurchaseOrder,
    PurchaseOrderItem,
    GoodsReceipt,
    Vendor
)
from fx.loader import FXResolver
from matching.schemas import MatchResult, DiscrepancyDetail
from matching.fx_validator import FXValidator
from matching.duplicate_detector import DuplicateDetector
from matching.isolation_forest import InvoiceAnomalyDetector


class ReconciliationEngine:
    def __init__(self, db: Session, anomaly_detector: Optional[InvoiceAnomalyDetector] = None):
        self.db = db
        tolerances_cfg = settings.load_tolerances().get("matching", {})

        # Load configurable tolerances
        self.qty_tolerance_pct = tolerances_cfg.get("quantity_tolerance_pct", 0.0)
        self.price_tolerance_pct = tolerances_cfg.get("price_tolerance_pct", 1.0)
        self.price_tolerance_abs_base = tolerances_cfg.get("price_tolerance_absolute_base", 50.0)
        self.price_tolerance_abs_usd = tolerances_cfg.get("price_tolerance_absolute_usd", 1.0)
        self.fx_tolerance_pct = tolerances_cfg.get("fx_rate_tolerance_pct", 1.5)
        self.tax_tolerance_base = tolerances_cfg.get("tax_tolerance_absolute_base", 1.0)
        self.duplicate_threshold = tolerances_cfg.get("duplicate_similarity_threshold", 90.0)

        # Specialized validators
        fx_resolver = FXResolver(db)
        self.fx_validator = FXValidator(fx_resolver, tolerance_pct=self.fx_tolerance_pct)
        self.duplicate_detector = DuplicateDetector(db, similarity_threshold=self.duplicate_threshold)

        # Unsupervised secondary model
        if anomaly_detector and anomaly_detector.is_fitted:
            self.anomaly_detector = anomaly_detector
        else:
            self.anomaly_detector = InvoiceAnomalyDetector().fit_from_db(db)

    def reconcile_invoice(self, invoice: Invoice) -> MatchResult:
        """
        Runs comprehensive deterministic 3-way matching and secondary anomaly scoring on an invoice.
        """
        defects: List[str] = []
        discrepancies: List[DiscrepancyDetail] = []
        line_variances: List[Dict[str, Any]] = []

        # 1. PO Existence Check
        po: Optional[PurchaseOrder] = None
        if not invoice.po_number:
            defects.append("no_matching_po")
            discrepancies.append(DiscrepancyDetail(
                check_type="PO_MISSING",
                severity="HIGH",
                message="Invoice does not reference any Purchase Order"
            ))
        else:
            po = self.db.execute(
                select(PurchaseOrder).where(PurchaseOrder.po_number == invoice.po_number)
            ).scalar_one_or_none()

            if not po:
                defects.append("no_matching_po")
                discrepancies.append(DiscrepancyDetail(
                    check_type="PO_NOT_FOUND",
                    severity="HIGH",
                    message=f"Referenced PO '{invoice.po_number}' does not exist in purchasing records"
                ))

        # 2. Currency Consistency Check
        if po and invoice.currency != po.currency:
            defects.append("wrong_currency")
            discrepancies.append(DiscrepancyDetail(
                check_type="CURRENCY_MISMATCH",
                severity="HIGH",
                message=f"Invoice billed in {invoice.currency} but PO contracted in {po.currency}",
                variance={"invoice_currency": invoice.currency, "po_currency": po.currency}
            ))

        # 3. Bank Remittance Account Check
        vendor = self.db.execute(
            select(Vendor).where(Vendor.vendor_id == invoice.vendor_id)
        ).scalar_one_or_none()

        if vendor and invoice.bank_account_number:
            if invoice.bank_account_number != vendor.bank_account_number:
                defects.append("bank_details_changed")
                discrepancies.append(DiscrepancyDetail(
                    check_type="BANK_DETAILS_MISMATCH",
                    severity="HIGH",
                    message=(
                        f"Invoiced remittance bank account '{invoice.bank_account_number}' "
                        f"differs from vendor master record '{vendor.bank_account_number}'"
                    ),
                    variance={
                        "invoiced_bank_account": invoice.bank_account_number,
                        "master_bank_account": vendor.bank_account_number
                    }
                ))

        # 4. Duplicate Invoice Detection
        dupe_res = self.duplicate_detector.check_duplicate(invoice)
        if dupe_res["is_duplicate"]:
            defects.append("duplicate_invoice")
            discrepancies.append(DiscrepancyDetail(
                check_type="DUPLICATE_INVOICE",
                severity="HIGH",
                message=f"Suspected duplicate submission matching {dupe_res['duplicate_of']} (similarity score: {dupe_res['similarity_score']}%)",
                variance=dupe_res
            ))

        # 5. Foreign Exchange (FX) Rate Validation
        fx_res = self.fx_validator.validate_fx_rate(
            invoice_date=invoice.invoice_date,
            currency=invoice.currency,
            stated_fx_rate=invoice.stated_fx_rate,
            gross_amount=invoice.total_gross_amount
        )
        if not fx_res["is_valid"]:
            defects.append("fx_rate_deviation")
            discrepancies.append(DiscrepancyDetail(
                check_type="FX_RATE_DEVIATION",
                severity="HIGH",
                message=fx_res["message"],
                variance=fx_res
            ))

        # 6. Tax Calculation Math Check
        # Standard tax rate is 18%; check if stated tax deviates from expected line math
        if invoice.items:
            expected_tax = round(sum(it.net_amount * (it.tax_rate_pct / 100.0) for it in invoice.items), 2)
            tax_diff = abs(invoice.total_tax_amount - expected_tax)
            # Allow tax tolerance
            max_tax_tol = self.tax_tolerance_base if invoice.currency == "INR" else 0.05
            if tax_diff > max_tax_tol:
                defects.append("tax_miscalculation")
                discrepancies.append(DiscrepancyDetail(
                    check_type="TAX_CALCULATION_ERROR",
                    severity="MEDIUM",
                    message=(
                        f"Tax calculation mismatch: Invoiced tax {invoice.total_tax_amount:.2f} "
                        f"differs from calculated tax {expected_tax:.2f} (diff: {tax_diff:.2f})"
                    ),
                    variance={"invoiced_tax": invoice.total_tax_amount, "expected_tax": expected_tax, "difference": tax_diff}
                ))

        # 7. Line-Item Three-Way Matching (PO vs GR vs Invoice)
        receipts: List[GoodsReceipt] = []
        if po:
            receipts = self.db.execute(
                select(GoodsReceipt).where(GoodsReceipt.po_number == po.po_number)
            ).scalars().all()

            po_item_map = {item.line_number: item for item in po.items}
            gr_item_map = {gr.line_number: gr for gr in receipts}

            has_qty_mismatch = False
            has_price_mismatch = False

            for inv_item in invoice.items:
                po_item = po_item_map.get(inv_item.line_number)
                gr_item = gr_item_map.get(inv_item.line_number)

                line_var = {
                    "line_number": inv_item.line_number,
                    "description": inv_item.item_description,
                    "inv_qty": inv_item.quantity,
                    "gr_qty": gr_item.quantity_received if gr_item else None,
                    "inv_price": inv_item.unit_price,
                    "po_price": po_item.unit_price if po_item else None,
                }

                # Quantity check: Invoice vs Goods Receipt
                if gr_item:
                    qty_diff = inv_item.quantity - gr_item.quantity_received
                    line_var["qty_diff"] = qty_diff
                    if qty_diff > 0:  # Invoiced more than received
                        has_qty_mismatch = True
                        discrepancies.append(DiscrepancyDetail(
                            check_type="QUANTITY_MISMATCH",
                            severity="HIGH",
                            message=(
                                f"Line {inv_item.line_number} quantity billed ({inv_item.quantity}) "
                                f"exceeds goods receipt quantity ({gr_item.quantity_received})"
                            ),
                            variance={"billed_qty": inv_item.quantity, "received_qty": gr_item.quantity_received, "diff": qty_diff}
                        ))

                # Unit price check: Invoice vs PO
                if po_item:
                    price_diff = inv_item.unit_price - po_item.unit_price
                    pct_price_diff = (price_diff / po_item.unit_price) * 100.0 if po_item.unit_price > 0 else 0.0
                    line_var["price_diff"] = round(price_diff, 2)
                    line_var["price_diff_pct"] = round(pct_price_diff, 2)

                    abs_tol = self.price_tolerance_abs_base if invoice.currency == "INR" else self.price_tolerance_abs_usd

                    if pct_price_diff > self.price_tolerance_pct and price_diff > abs_tol:
                        has_price_mismatch = True
                        discrepancies.append(DiscrepancyDetail(
                            check_type="PRICE_OVER_TOLERANCE",
                            severity="HIGH",
                            message=(
                                f"Line {inv_item.line_number} unit price billed ({inv_item.unit_price:.2f}) "
                                f"exceeds PO unit price ({po_item.unit_price:.2f}) by +{pct_price_diff:.1f}%"
                            ),
                            variance={"billed_price": inv_item.unit_price, "po_price": po_item.unit_price, "diff_pct": round(pct_price_diff, 2)}
                        ))

                line_variances.append(line_var)

            if has_qty_mismatch:
                defects.append("quantity_mismatch")
            if has_price_mismatch:
                defects.append("price_over_tolerance")

        # 8. Unsupervised Secondary Anomaly Signal
        is_iforest_anomaly, iforest_score = self.anomaly_detector.predict_anomaly(invoice, po, receipts)

        # Remove duplicate defect tags
        unique_defects = sorted(list(set(defects)))
        is_matched = len(unique_defects) == 0

        return MatchResult(
            invoice_number=invoice.invoice_number,
            is_matched=is_matched,
            overall_status="MATCHED" if is_matched else "DISCREPANCY",
            detected_defect_types=unique_defects,
            discrepancies=discrepancies,
            fx_validation=fx_res,
            duplicate_info=dupe_res,
            isolation_forest_anomaly=is_iforest_anomaly,
            isolation_forest_score=iforest_score,
            line_item_variances=line_variances
        )
