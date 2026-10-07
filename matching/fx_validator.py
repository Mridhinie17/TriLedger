"""
Foreign Exchange (FX) Rate Validation Module for TriLedger.
Validates foreign currency invoices against official ECB reference rates.
Calculates exchange rate deviations, converts to base currency (INR),
and flags deviations exceeding configurable tolerance.
"""

from datetime import date
from typing import Dict, Any, Optional
from fx.loader import FXResolver


class FXValidator:
    def __init__(self, fx_resolver: FXResolver, tolerance_pct: float = 1.5):
        self.fx_resolver = fx_resolver
        self.tolerance_pct = tolerance_pct

    def validate_fx_rate(
        self,
        invoice_date: date,
        currency: str,
        stated_fx_rate: Optional[float],
        gross_amount: float
    ) -> Dict[str, Any]:
        """
        Validates invoice exchange rate against official ECB reference rate.
        Never silently defaults. Handles weekend/holiday rollback through FXResolver.
        """
        # Base currency needs no FX conversion
        if currency.upper() == "INR":
            return {
                "is_valid": True,
                "currency": "INR",
                "stated_rate": 1.0,
                "official_rate": 1.0,
                "effective_date": invoice_date.isoformat(),
                "deviation_pct": 0.0,
                "tolerance_pct": self.tolerance_pct,
                "booked_amount_base": gross_amount,
                "official_amount_base": gross_amount,
                "variance_base": 0.0,
                "is_foreign": False,
                "message": "Base currency INR (no conversion required)"
            }

        # Stated rate check for foreign currency
        if stated_fx_rate is None or stated_fx_rate <= 0:
            return {
                "is_valid": False,
                "currency": currency,
                "stated_rate": stated_fx_rate,
                "official_rate": None,
                "effective_date": None,
                "deviation_pct": 100.0,
                "tolerance_pct": self.tolerance_pct,
                "booked_amount_base": 0.0,
                "official_amount_base": 0.0,
                "variance_base": 0.0,
                "is_foreign": True,
                "message": f"Foreign currency invoice in {currency} is missing valid stated exchange rate"
            }

        # Resolve official ECB rate on invoice date (or prior business day)
        official_rate, effective_date = self.fx_resolver.resolve_effective_rate(
            query_date=invoice_date,
            base_currency=currency,
            target_currency="INR"
        )

        deviation_pct = round(abs(stated_fx_rate - official_rate) / official_rate * 100.0, 4)
        booked_inr = round(gross_amount * stated_fx_rate, 2)
        official_inr = round(gross_amount * official_rate, 2)
        variance_inr = round(booked_inr - official_inr, 2)

        is_valid = deviation_pct <= self.tolerance_pct

        if is_valid:
            msg = (
                f"FX rate verified: Stated {stated_fx_rate:.4f} within {self.tolerance_pct}% "
                f"of ECB rate {official_rate:.4f} (effective date {effective_date})"
            )
        else:
            msg = (
                f"FX rate deviation: Stated rate {stated_fx_rate:.4f} deviates by {deviation_pct:.2f}% "
                f"from official ECB rate {official_rate:.4f} (effective date {effective_date}), "
                f"exceeding tolerance {self.tolerance_pct}%. Valuation variance: ₹{variance_inr:+,.2f} INR"
            )

        return {
            "is_valid": is_valid,
            "currency": currency,
            "stated_rate": stated_fx_rate,
            "official_rate": round(official_rate, 4),
            "effective_date": effective_date.isoformat(),
            "deviation_pct": deviation_pct,
            "tolerance_pct": self.tolerance_pct,
            "booked_amount_base": booked_inr,
            "official_amount_base": official_inr,
            "variance_base": variance_inr,
            "is_foreign": True,
            "message": msg
        }
