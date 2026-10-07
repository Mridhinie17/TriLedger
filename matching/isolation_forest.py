"""
Unsupervised Anomaly Detection using Isolation Forest.
Provides a secondary anomaly signal on price and quantity variance features.
"""

from typing import List, Dict, Any, Tuple, Optional
import numpy as np
from sklearn.ensemble import IsolationForest
from sqlalchemy.orm import Session
from sqlalchemy import select

from db.models import Invoice, PurchaseOrder, GoodsReceipt, PurchaseOrderItem


class InvoiceAnomalyDetector:
    def __init__(self, contamination: float = 0.05, random_state: int = 42):
        self.contamination = contamination
        self.random_state = random_state
        self.model = IsolationForest(
            contamination=self.contamination,
            random_state=self.random_state,
            n_estimators=100
        )
        self.is_fitted = False

    def extract_features(
        self,
        invoice: Invoice,
        po: Optional[PurchaseOrder] = None,
        receipts: Optional[List[GoodsReceipt]] = None
    ) -> np.ndarray:
        """
        Extracts a 4-dimensional normalized feature vector:
        1. Price Ratio (Inv unit price / PO unit price)
        2. Quantity Ratio (Inv qty / GR qty)
        3. Tax Rate Ratio (Effective tax rate / 0.18)
        4. Gross to Net Ratio (Gross / Net)
        """
        # Baseline normal values
        price_ratio = 1.0
        qty_ratio = 1.0
        tax_ratio = 1.0
        gross_net_ratio = 1.18

        if invoice.total_net_amount > 0:
            eff_tax_pct = invoice.total_tax_amount / invoice.total_net_amount
            tax_ratio = eff_tax_pct / 0.18
            gross_net_ratio = invoice.total_gross_amount / invoice.total_net_amount

        if invoice.items and po and po.items:
            po_item_map = {item.line_number: item for item in po.items}
            gr_item_map = {r.line_number: r for r in receipts} if receipts else {}

            price_ratios = []
            qty_ratios = []
            for inv_item in invoice.items:
                po_item = po_item_map.get(inv_item.line_number)
                if po_item and po_item.unit_price > 0:
                    price_ratios.append(inv_item.unit_price / po_item.unit_price)

                gr_item = gr_item_map.get(inv_item.line_number)
                if gr_item and gr_item.quantity_received > 0:
                    qty_ratios.append(inv_item.quantity / gr_item.quantity_received)

            if price_ratios:
                price_ratio = float(np.mean(price_ratios))
            if qty_ratios:
                qty_ratio = float(np.mean(qty_ratios))

        return np.array([price_ratio, qty_ratio, tax_ratio, gross_net_ratio], dtype=float)

    def fit_from_db(self, db: Session) -> "InvoiceAnomalyDetector":
        """Fits the Isolation Forest on available database records."""
        invoices = db.execute(select(Invoice)).scalars().all()
        if not invoices:
            self.is_fitted = True
            return self

        X = []
        for inv in invoices:
            po = None
            if inv.po_number:
                po = db.execute(select(PurchaseOrder).where(PurchaseOrder.po_number == inv.po_number)).scalar_one_or_none()
            receipts = []
            if inv.po_number:
                receipts = db.execute(select(GoodsReceipt).where(GoodsReceipt.po_number == inv.po_number)).scalars().all()

            feat = self.extract_features(inv, po, receipts)
            X.append(feat)

        X_mat = np.array(X)
        self.model.fit(X_mat)
        self.is_fitted = True
        return self

    def predict_anomaly(
        self,
        invoice: Invoice,
        po: Optional[PurchaseOrder] = None,
        receipts: Optional[List[GoodsReceipt]] = None
    ) -> Tuple[bool, float]:
        """
        Returns (is_anomaly, anomaly_score).
        Negative score indicates higher anomaly confidence.
        """
        if not self.is_fitted:
            return False, 0.0

        feat = self.extract_features(invoice, po, receipts).reshape(1, -1)
        pred = self.model.predict(feat)[0]  # -1 for anomaly, 1 for inlier
        raw_score = float(self.model.decision_function(feat)[0])

        is_anomaly = bool(pred == -1)
        return is_anomaly, round(raw_score, 4)
