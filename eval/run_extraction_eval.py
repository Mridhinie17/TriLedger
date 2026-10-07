"""
Extraction Evaluation Runner for TriLedger Phase 2.
Evaluates pdfplumber digital extraction and Tesseract OCR fallback against ground-truth database records.
Measures per-field accuracy, OCR trigger rates, and extraction latencies.
Outputs formatted metrics table and saves results to eval/results/extraction.json.
"""

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.settings import settings
from db.models import Invoice
from db.session import get_db_context
from extraction.extractor import InvoiceExtractor


def run_extraction_evaluation(sample_size: int = 800, output_file: Optional[Path] = None) -> Dict[str, Any]:
    output_path = output_file or (settings.EVAL_DIR / "results" / "extraction.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    extractor = InvoiceExtractor(confidence_threshold=0.85)

    with get_db_context() as db:
        query = db.query(Invoice).order_by(Invoice.invoice_number)
        if sample_size < 800:
            query = query.limit(sample_size)
        db_invoices = query.all()

    total_count = len(db_invoices)
    if total_count == 0:
        raise ValueError("No invoices found in database to evaluate! Please run `python run_seed.py` first.")

    print("=" * 75)
    print(f"TriLedger: Running Extraction Evaluation on {total_count} Invoices")
    print("=" * 75)

    field_keys = [
        "invoice_number",
        "vendor_id",
        "po_number",
        "invoice_date",
        "currency",
        "total_net_amount",
        "total_tax_amount",
        "total_gross_amount",
        "bank_account_number"
    ]

    # Metrics accumulators
    matches = {k: 0 for k in field_keys}
    matches_digital = {k: 0 for k in field_keys}
    matches_scanned = {k: 0 for k in field_keys}

    digital_count = 0
    scanned_count = 0
    ocr_triggered_on_scanned = 0
    flagged_for_review_count = 0
    total_latency_sec = 0.0

    start_eval_time = time.time()

    for idx, expected in enumerate(db_invoices, start=1):
        pdf_path = settings.BASE_DIR / expected.pdf_path
        if not pdf_path.exists():
            continue

        t0 = time.time()
        result = extractor.extract_from_pdf(pdf_path)
        latency = time.time() - t0
        total_latency_sec += latency

        actual = result.invoice
        is_scanned = expected.is_scanned

        if is_scanned:
            scanned_count += 1
            if result.invoice.is_ocr_fallback_used:
                ocr_triggered_on_scanned += 1
        else:
            digital_count += 1

        if result.flagged_for_review:
            flagged_for_review_count += 1

        # Evaluate field equality
        # 1. Invoice Number
        if actual.invoice_number == expected.invoice_number:
            matches["invoice_number"] += 1
            (matches_scanned if is_scanned else matches_digital)["invoice_number"] += 1

        # 2. Vendor ID
        if actual.vendor_id == expected.vendor_id:
            matches["vendor_id"] += 1
            (matches_scanned if is_scanned else matches_digital)["vendor_id"] += 1

        # 3. PO Number
        exp_po = expected.po_number or "NONE"
        act_po = actual.po_number or "NONE"
        if act_po == exp_po:
            matches["po_number"] += 1
            (matches_scanned if is_scanned else matches_digital)["po_number"] += 1

        # 4. Invoice Date
        if actual.invoice_date == expected.invoice_date:
            matches["invoice_date"] += 1
            (matches_scanned if is_scanned else matches_digital)["invoice_date"] += 1

        # 5. Currency
        if actual.currency == expected.currency:
            matches["currency"] += 1
            (matches_scanned if is_scanned else matches_digital)["currency"] += 1

        # 6. Amounts (within 0.05 rounding)
        if abs(actual.total_net_amount - expected.total_net_amount) <= 0.05:
            matches["total_net_amount"] += 1
            (matches_scanned if is_scanned else matches_digital)["total_net_amount"] += 1

        if abs(actual.total_tax_amount - expected.total_tax_amount) <= 0.05:
            matches["total_tax_amount"] += 1
            (matches_scanned if is_scanned else matches_digital)["total_tax_amount"] += 1

        if abs(actual.total_gross_amount - expected.total_gross_amount) <= 0.05:
            matches["total_gross_amount"] += 1
            (matches_scanned if is_scanned else matches_digital)["total_gross_amount"] += 1

        # 7. Bank Account
        exp_bank = expected.bank_account_number or ""
        act_bank = actual.bank_account_number or ""
        if act_bank == exp_bank:
            matches["bank_account_number"] += 1
            (matches_scanned if is_scanned else matches_digital)["bank_account_number"] += 1

        if idx % 100 == 0 or idx == total_count:
            print(f"  Processed {idx}/{total_count} invoices...")

    total_eval_duration = time.time() - start_eval_time
    avg_latency_ms = round((total_latency_sec / max(total_count, 1)) * 1000, 2)

    # Compute Accuracies
    overall_field_accuracies = {
        k: round((matches[k] / max(total_count, 1)) * 100, 2) for k in field_keys
    }
    digital_field_accuracies = {
        k: round((matches_digital[k] / max(digital_count, 1)) * 100, 2) for k in field_keys
    }
    scanned_field_accuracies = {
        k: round((matches_scanned[k] / max(scanned_count, 1)) * 100, 2) for k in field_keys
    }

    avg_overall_accuracy = round(
        sum(overall_field_accuracies.values()) / len(overall_field_accuracies), 2
    )
    ocr_recall = round(
        (ocr_triggered_on_scanned / max(scanned_count, 1)) * 100, 2
    )

    # Print Table
    print("\n" + "=" * 75)
    print("EXTRACTION ACCURACY REPORT")
    print("=" * 75)
    print(f"{'Field':<24} | {'Digital Acc (%)':<15} | {'Scanned Acc (%)':<15} | {'Overall Acc (%)':<15}")
    print("-" * 75)
    for k in field_keys:
        print(f"{k:<24} | {digital_field_accuracies[k]:>14.2f}% | {scanned_field_accuracies[k]:>14.2f}% | {overall_field_accuracies[k]:>14.2f}%")
    print("-" * 75)
    print(f"{'MACRO-AVERAGE ACCURACY':<24} | "
          f"{sum(digital_field_accuracies.values())/len(digital_field_accuracies):>14.2f}% | "
          f"{sum(scanned_field_accuracies.values())/len(scanned_field_accuracies):>14.2f}% | "
          f"{avg_overall_accuracy:>14.2f}%")
    print("=" * 75)
    print(f"Total Evaluated:         {total_count} (Digital: {digital_count}, Scanned: {scanned_count})")
    print(f"OCR Fallback Trigger Rate on Scans: {ocr_recall}% ({ocr_triggered_on_scanned}/{scanned_count})")
    print(f"Flagged for Review:      {flagged_for_review_count} ({flagged_for_review_count/total_count:.1%})")
    print(f"Average Latency / Doc:   {avg_latency_ms} ms")
    print(f"Total Execution Time:    {total_eval_duration:.2f} s")
    print("=" * 75)

    results_data = {
        "timestamp": datetime.utcnow().isoformat(),
        "total_evaluated": total_count,
        "digital_count": digital_count,
        "scanned_count": scanned_count,
        "ocr_triggered_on_scanned": ocr_triggered_on_scanned,
        "ocr_trigger_rate_pct": ocr_recall,
        "macro_average_accuracy_pct": avg_overall_accuracy,
        "per_field_accuracy": overall_field_accuracies,
        "digital_per_field_accuracy": digital_field_accuracies,
        "scanned_per_field_accuracy": scanned_field_accuracies,
        "flagged_for_human_review_count": flagged_for_review_count,
        "flagged_for_human_review_rate_pct": round((flagged_for_review_count / total_count) * 100, 2),
        "average_latency_ms": avg_latency_ms,
        "total_duration_seconds": round(total_eval_duration, 2)
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results_data, f, indent=2)

    print(f"Saved evaluation metrics to: {output_path}")
    return results_data


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Extraction Evaluation")
    parser.add_argument("--sample", type=int, default=800, help="Number of invoices to evaluate")
    parser.add_argument("--output", type=str, default=None, help="Custom output JSON path")
    args = parser.parse_args()

    custom_out = Path(args.output) if args.output else None
    run_extraction_evaluation(sample_size=args.sample, output_file=custom_out)
