"""
Official ECB Foreign Exchange Reference Rates Loader & Cross-Rate Resolver.
Source: European Central Bank (https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist.zip)
Follows strict deterministic rules:
1. Base ECB currency is EUR.
2. Cross-rates (e.g. USD -> INR) derived via triangular parity:
   Rate(A -> B) = Rate(EUR -> B) / Rate(EUR -> A)
3. Weekends and bank holidays resolve to the last available prior business day.
4. Data quality violations (invalid date, non-numeric or <=0 rate) log to rejected_rows.
"""

import csv
import io
import urllib.request
import zipfile
from datetime import date, datetime, timedelta
from pathlib import Path

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from config.settings import settings
from db.models import AuditLog, FXRate, RejectedRow

ECB_HIST_URL = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist.zip"


class FXLoader:
    def __init__(self, data_dir: Path | None = None):
        self.data_dir = data_dir or (settings.DATA_DIR / "fx")
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.zip_path = self.data_dir / "eurofxref-hist.zip"
        self.csv_path = self.data_dir / "eurofxref-hist.csv"

    def download_ecb_dataset(self, force_refresh: bool = False) -> Path:
        """Download and extract the official ECB reference rates dataset."""
        if self.csv_path.exists() and not force_refresh:
            return self.csv_path

        req = urllib.request.Request(
            ECB_HIST_URL, headers={"User-Agent": "TriLedger-Reconciliation/1.0 (Portfolio Project)"}
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            content = resp.read()

        with open(self.zip_path, "wb") as f:
            f.write(content)

        with zipfile.ZipFile(io.BytesIO(content)) as z:
            # First file is always eurofxref-hist.csv
            csv_name = next(name for name in z.namelist() if name.endswith(".csv"))
            with z.open(csv_name) as zf, open(self.csv_path, "wb") as out_f:
                out_f.write(zf.read())

        return self.csv_path

    def load_rates_to_db(
        self, db: Session, start_year: int = 2023, currencies: list[str] | None = None
    ) -> dict[str, int]:
        """
        Parses the ECB CSV and loads EUR reference rates into fx_rates table.
        Rejects invalid rows to rejected_rows.
        """
        if currencies is None:
            currencies = ["USD", "JPY", "INR", "GBP"]

        csv_path = self.download_ecb_dataset()
        loaded_count = 0
        rejected_count = 0
        skipped_count = 0

        existing_pairs = set(
            db.execute(
                select(FXRate.rate_date, FXRate.target_currency).where(
                    FXRate.base_currency == "EUR"
                )
            ).all()
        )

        new_rates: list[FXRate] = []

        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            header = [h.strip() for h in next(reader)]
            col_indices = {}
            for curr in currencies:
                if curr in header:
                    col_indices[curr] = header.index(curr)

            date_idx = header.index("Date") if "Date" in header else 0

            for row_num, row in enumerate(reader, start=2):
                if not row or len(row) <= date_idx:
                    continue

                date_str = row[date_idx].strip()
                try:
                    r_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                except ValueError:
                    db.add(
                        RejectedRow(
                            source_table="fx_rates",
                            raw_payload=",".join(row),
                            rejection_reason=f"INVALID_DATE_FORMAT_ROW_{row_num}",
                        )
                    )
                    rejected_count += 1
                    continue

                if r_date.year < start_year:
                    continue

                for curr, idx in col_indices.items():
                    if idx >= len(row):
                        continue
                    val_str = row[idx].strip()
                    if not val_str or val_str.upper() == "N/A":
                        continue

                    try:
                        rate_val = float(val_str)
                        if rate_val <= 0:
                            raise ValueError("Rate must be strictly positive")
                    except ValueError as e:
                        db.add(
                            RejectedRow(
                                source_table="fx_rates",
                                raw_payload=f"Date: {date_str}, Curr: {curr}, Val: {val_str}",
                                rejection_reason=f"INVALID_RATE_VALUE: {e!s}",
                            )
                        )
                        rejected_count += 1
                        continue

                    if (r_date, curr) not in existing_pairs:
                        new_rates.append(
                            FXRate(
                                rate_date=r_date,
                                base_currency="EUR",
                                target_currency=curr,
                                rate=rate_val,
                                source="ECB_REFERENCE_HISTORICAL",
                            )
                        )
                        existing_pairs.add((r_date, curr))
                        loaded_count += 1
                    else:
                        skipped_count += 1

                # Batch insert every 1,000 rows
                if len(new_rates) >= 1000:
                    db.bulk_save_objects(new_rates)
                    db.commit()
                    new_rates.clear()

        if new_rates:
            db.bulk_save_objects(new_rates)
            db.commit()

        db.add(
            AuditLog(
                entity_type="FX_LOAD",
                entity_id="ECB_HISTORICAL",
                action="LOADED_RATES",
                actor="SYSTEM",
                details=f"loaded={loaded_count}, rejected={rejected_count}, skipped={skipped_count}",
            )
        )
        db.commit()

        return {"loaded": loaded_count, "rejected": rejected_count, "skipped": skipped_count}


class FXResolver:
    """
    Deterministic FX rate resolver using triangular cross-rate parity and prior-business-day rule.
    """

    def __init__(self, db: Session):
        self.db = db
        # In-memory lookup cache: (date, target_currency) -> rate
        self._cache: dict[tuple[date, str], float] = {}

    def get_rate_on_date(self, target_date: date, currency: str) -> float | None:
        """Fetch EUR -> currency rate on exact date."""
        if currency == "EUR":
            return 1.0

        key = (target_date, currency)
        if key in self._cache:
            return self._cache[key]

        rate_obj = self.db.execute(
            select(FXRate.rate).where(
                and_(
                    FXRate.rate_date == target_date,
                    FXRate.base_currency == "EUR",
                    FXRate.target_currency == currency,
                )
            )
        ).scalar_one_or_none()

        if rate_obj is not None:
            self._cache[key] = float(rate_obj)
            return float(rate_obj)

        return None

    def resolve_effective_rate(
        self,
        query_date: date,
        base_currency: str,
        target_currency: str,
        max_lookback_days: int = 10,
    ) -> tuple[float, date]:
        """
        Calculates the exchange rate: units of target_currency per 1 unit of base_currency.
        If query_date is a weekend or holiday, rolls back to the last available prior business day.
        Raises ValueError if rate cannot be resolved.
        Returns (rate, effective_date).
        """
        if base_currency == target_currency:
            return 1.0, query_date

        current_date = query_date
        days_checked = 0

        while days_checked <= max_lookback_days:
            # Check if rates for both currencies exist on current_date
            rate_base = (
                1.0
                if base_currency == "EUR"
                else self.get_rate_on_date(current_date, base_currency)
            )
            rate_target = (
                1.0
                if target_currency == "EUR"
                else self.get_rate_on_date(current_date, target_currency)
            )

            if rate_base is not None and rate_target is not None:
                # Triangular cross-rate formula:
                # 1 EUR = rate_base (Base)
                # 1 EUR = rate_target (Target)
                # 1 Base = rate_target / rate_base (Target)
                cross_rate = rate_target / rate_base
                return cross_rate, current_date

            # Step back one day (weekend/holiday rollback)
            current_date -= timedelta(days=1)
            days_checked += 1

        raise ValueError(
            f"No official ECB FX rate found for pair {base_currency}/{target_currency} "
            f"on or prior to {query_date} within {max_lookback_days} days lookback."
        )
