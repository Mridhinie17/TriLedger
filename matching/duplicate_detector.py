"""
Fuzzy and Exact Duplicate Invoice Detection using RapidFuzz.
Detects duplicate invoice submissions across vendor, invoice number, PO, amount, and date.
"""

from typing import Any, Dict, List, Optional

from rapidfuzz import fuzz
from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from db.models import Invoice


class DuplicateDetector:
    def __init__(self, db: Session, similarity_threshold: float = 90.0):
        self.db = db
        self.similarity_threshold = similarity_threshold

    def check_duplicate(self, candidate_invoice: Invoice) -> Dict[str, Any]:
        """
        Scans other invoices in the system to determine if candidate_invoice is a duplicate.
        Returns duplicate detection details and similarity metrics.
        """
        # Query potential matches: only previously submitted invoices (temporal causality)
        stmt = select(Invoice).where(
            and_(
                Invoice.invoice_number < candidate_invoice.invoice_number,
                (
                    (Invoice.vendor_id == candidate_invoice.vendor_id)
                    | (Invoice.po_number == candidate_invoice.po_number)
                ),
            )
        )
        potential_matches = self.db.execute(stmt).scalars().all()

        best_match_inv: Optional[str] = None
        highest_score = 0.0
        reasons: List[str] = []

        for other in potential_matches:
            # 1. Vendor Match (binary)
            vendor_match = 100.0 if other.vendor_id == candidate_invoice.vendor_id else 0.0

            # 2. Amount Match (binary with 1.00 currency tolerance)
            amount_diff = abs(other.total_gross_amount - candidate_invoice.total_gross_amount)
            amount_score = (
                100.0
                if amount_diff <= 1.0
                else max(
                    0.0,
                    100.0 - (amount_diff / max(candidate_invoice.total_gross_amount, 1.0)) * 100.0,
                )
            )

            # 3. PO Reference Match
            po_score = 0.0
            if candidate_invoice.po_number and other.po_number:
                if candidate_invoice.po_number == other.po_number:
                    po_score = 100.0
                else:
                    po_score = float(
                        fuzz.token_sort_ratio(candidate_invoice.po_number, other.po_number)
                    )

            # 4. Date Match (Days difference)
            days_diff = abs((candidate_invoice.invoice_date - other.invoice_date).days)
            date_match = 100.0 if days_diff <= 1 else 0.0

            # 5. Invoice Number String Similarity
            num_similarity = float(
                fuzz.token_sort_ratio(candidate_invoice.invoice_number, other.invoice_number)
            )

            # Composite Score: True business duplicate must match PO, vendor, amount, AND date!
            if (
                vendor_match == 100.0
                and po_score == 100.0
                and amount_score >= 99.0
                and date_match == 100.0
            ):
                composite_score = 98.0
            else:
                composite_score = (
                    0.25 * num_similarity
                    + 0.25 * amount_score
                    + 0.25 * po_score
                    + 0.15 * vendor_match
                    + 0.10 * date_match
                )
                # If invoices are in different billing cycles, cannot be a duplicate
                if days_diff > 3:
                    composite_score = min(composite_score, 75.0)

            if composite_score > highest_score:
                highest_score = composite_score
                best_match_inv = other.invoice_number
                reasons = [
                    f"Matched existing invoice {other.invoice_number}",
                    f"Same PO: {other.po_number}",
                    f"Amount diff: {amount_diff:.2f}",
                    f"String similarity: {num_similarity:.1f}%",
                ]

        is_duplicate = highest_score >= self.similarity_threshold

        return {
            "is_duplicate": is_duplicate,
            "similarity_score": round(highest_score, 2),
            "threshold": self.similarity_threshold,
            "duplicate_of": best_match_inv if is_duplicate else None,
            "details": reasons if is_duplicate else [],
        }
