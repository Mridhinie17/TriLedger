"""
Three-Way Reconciliation & Anomaly Detection Evaluation Runner for TriLedger Phase 3.
Evaluates the matching engine, FX validation, RapidFuzz duplicate detection,
and IsolationForest anomaly detection against data/ground_truth.csv.
Computes per-defect-type Precision, Recall, and F1-scores and saves to eval/results/matching.json.
"""

import argparse
import csv
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

# Ensure project root is in Python path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.settings import settings
from db.models import Invoice
from db.session import get_db_context
from matching.engine import ReconciliationEngine


def run_matching_evaluation(
    sample_size: int = 800, output_file: Optional[Path] = None
) -> Dict[str, Any]:
    output_path = output_file or (settings.EVAL_DIR / "results" / "matching.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # 1. Load ground truth
    gt_file = settings.DATA_DIR / "ground_truth.csv"
    if not gt_file.exists():
        raise FileNotFoundError(f"Ground truth file missing at {gt_file}! Run run_seed.py first.")

    ground_truth: Dict[str, Dict[str, Any]] = {}
    with open(gt_file, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            ground_truth[row["invoice_number"]] = {
                "defect_type": row["defect_type"],
                "is_defective": row["is_defective"].lower() == "true",
                "defect_details": row["defect_details"],
            }

    # 2. Load invoices
    with get_db_context() as db:
        query = db.query(Invoice).order_by(Invoice.invoice_number)
        if sample_size < 800:
            query = query.limit(sample_size)
        invoices = query.all()

        total_evaluated = len(invoices)
        if total_evaluated == 0:
            raise ValueError("No invoices found in database! Run run_seed.py first.")

        print("=" * 80)
        print(
            f"TriLedger: Running 3-Way Match & Anomaly Detection Evaluation ({total_evaluated} Invoices)"
        )
        print("=" * 80)

        engine = ReconciliationEngine(db)

        all_defect_types = [
            "quantity_mismatch",
            "price_over_tolerance",
            "duplicate_invoice",
            "no_matching_po",
            "tax_miscalculation",
            "bank_details_changed",
            "fx_rate_deviation",
            "wrong_currency",
        ]

        # Accumulators per defect type: TP, FP, FN, TN, support
        stats = {dt: {"tp": 0, "fp": 0, "fn": 0, "tn": 0, "support": 0} for dt in all_defect_types}

        # Binary Clean vs Defective
        binary_stats = {"tp": 0, "fp": 0, "fn": 0, "tn": 0}
        iforest_overlap_defects = 0
        total_defects_in_dataset = 0
        total_latency_sec = 0.0

        start_time = time.time()

        for idx, inv in enumerate(invoices, start=1):
            t0 = time.time()
            match_res = engine.reconcile_invoice(inv)
            total_latency_sec += time.time() - t0

            gt_info = ground_truth.get(
                inv.invoice_number, {"defect_type": "none", "is_defective": False}
            )
            true_defect = gt_info["defect_type"]
            true_is_defective = gt_info["is_defective"]

            if true_is_defective:
                total_defects_in_dataset += 1
                if match_res.isolation_forest_anomaly:
                    iforest_overlap_defects += 1

            pred_is_defective = not match_res.is_matched
            pred_defects = set(match_res.detected_defect_types)

            # Binary metrics (Positive = Defective)
            if pred_is_defective and true_is_defective:
                binary_stats["tp"] += 1
            elif pred_is_defective and not true_is_defective:
                binary_stats["fp"] += 1
            elif not pred_is_defective and true_is_defective:
                binary_stats["fn"] += 1
            else:
                binary_stats["tn"] += 1

            # Per-defect type metrics
            for dt in all_defect_types:
                is_true_dt = true_defect == dt
                is_pred_dt = dt in pred_defects

                if is_true_dt:
                    stats[dt]["support"] += 1

                if is_pred_dt and is_true_dt:
                    stats[dt]["tp"] += 1
                elif is_pred_dt and not is_true_dt:
                    stats[dt]["fp"] += 1
                elif not is_pred_dt and is_true_dt:
                    stats[dt]["fn"] += 1
                else:
                    stats[dt]["tn"] += 1

            if idx % 100 == 0 or idx == total_evaluated:
                print(f"  Evaluated {idx}/{total_evaluated} invoices...")

    total_duration = time.time() - start_time
    avg_latency_ms = round((total_latency_sec / total_evaluated) * 1000, 2)

    # Compute per-defect Precision, Recall, F1
    per_defect_metrics = {}
    sum_prec = 0.0
    sum_rec = 0.0
    sum_f1 = 0.0
    valid_count = 0

    for dt in all_defect_types:
        s = stats[dt]
        tp, fp, fn, support = s["tp"], s["fp"], s["fn"], s["support"]

        prec = (tp / (tp + fp)) * 100.0 if (tp + fp) > 0 else 0.0
        rec = (tp / (tp + fn)) * 100.0 if (tp + fn) > 0 else 0.0
        f1 = (2 * prec * rec / (prec + rec)) if (prec + rec) > 0 else 0.0

        per_defect_metrics[dt] = {
            "precision_pct": round(prec, 2),
            "recall_pct": round(rec, 2),
            "f1_score": round(f1 / 100.0, 4),
            "tp": tp,
            "fp": fp,
            "fn": fn,
            "support": support,
        }

        if support > 0:
            sum_prec += prec
            sum_rec += rec
            sum_f1 += f1 / 100.0
            valid_count += 1

    macro_precision = round(sum_prec / max(valid_count, 1), 2)
    macro_recall = round(sum_rec / max(valid_count, 1), 2)
    macro_f1 = round(sum_f1 / max(valid_count, 1), 4)

    # Binary Classification Performance
    bin_tp, bin_fp, bin_fn, bin_tn = (
        binary_stats["tp"],
        binary_stats["fp"],
        binary_stats["fn"],
        binary_stats["tn"],
    )
    bin_prec = round((bin_tp / (bin_tp + bin_fp)) * 100.0, 2) if (bin_tp + bin_fp) > 0 else 0.0
    bin_rec = round((bin_tp / (bin_tp + bin_fn)) * 100.0, 2) if (bin_tp + bin_fn) > 0 else 0.0
    bin_f1 = (
        round((2 * bin_prec * bin_rec / (bin_prec + bin_rec)) / 100.0, 4)
        if (bin_prec + bin_rec) > 0
        else 0.0
    )
    bin_acc = round(((bin_tp + bin_tn) / total_evaluated) * 100.0, 2)

    # Print Table
    print("\n" + "=" * 80)
    print("THREE-WAY MATCH & DEFECT DETECTION BENCHMARK (Against Ground Truth)")
    print("=" * 80)
    print(
        f"{'Defect Type':<26} | {'Precision':<10} | {'Recall':<10} | {'F1-Score':<10} | {'Support':<8}"
    )
    print("-" * 80)
    for dt in all_defect_types:
        m = per_defect_metrics[dt]
        print(
            f"{dt:<26} | {m['precision_pct']:>9.2f}% | {m['recall_pct']:>9.2f}% | {m['f1_score']:>10.4f} | {m['support']:>8d}"
        )
    print("-" * 80)
    print(
        f"{'MACRO AVERAGE':<26} | {macro_precision:>9.2f}% | {macro_recall:>9.2f}% | {macro_f1:>10.4f} | {total_defects_in_dataset:>8d}"
    )
    print("=" * 80)
    print(f"Overall Discrepancy Detection Accuracy: {bin_acc}%")
    print(f"Discrepancy Precision:                  {bin_prec}%")
    print(f"Discrepancy Recall:                     {bin_rec}%")
    print(f"Discrepancy F1-Score:                   {bin_f1:.4f}")
    print(
        f"IsolationForest Defect Capture:         {iforest_overlap_defects}/{total_defects_in_dataset} ({iforest_overlap_defects / max(total_defects_in_dataset, 1):.1%})"
    )
    print(f"Average Matching Latency:               {avg_latency_ms} ms / invoice")
    print(f"Total Execution Time:                   {total_duration:.2f} s")
    print("=" * 80)

    results_data = {
        "timestamp": datetime.utcnow().isoformat(),
        "total_evaluated": total_evaluated,
        "clean_count": total_evaluated - total_defects_in_dataset,
        "defective_count": total_defects_in_dataset,
        "binary_classification": {
            "accuracy_pct": bin_acc,
            "precision_pct": bin_prec,
            "recall_pct": bin_rec,
            "f1_score": bin_f1,
            "confusion_matrix": binary_stats,
        },
        "per_defect_metrics": per_defect_metrics,
        "macro_metrics": {
            "macro_precision_pct": macro_precision,
            "macro_recall_pct": macro_recall,
            "macro_f1_score": macro_f1,
        },
        "isolation_forest_secondary_signal": {
            "defects_flagged": iforest_overlap_defects,
            "defect_capture_rate_pct": round(
                (iforest_overlap_defects / max(total_defects_in_dataset, 1)) * 100.0, 2
            ),
        },
        "average_latency_ms": avg_latency_ms,
        "total_duration_seconds": round(total_duration, 2),
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results_data, f, indent=2)

    print(f"Saved matching evaluation results to: {output_path}")
    return results_data


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Matching Evaluation")
    parser.add_argument("--sample", type=int, default=800, help="Number of invoices to evaluate")
    parser.add_argument("--output", type=str, default=None, help="Custom output JSON path")
    args = parser.parse_args()

    custom_out = Path(args.output) if args.output else None
    run_matching_evaluation(sample_size=args.sample, output_file=custom_out)
