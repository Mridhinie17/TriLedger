"""
CLI Seed Runner for TriLedger Phase 1.
Initializes SAP tables, loads official ECB foreign exchange rates,
and deterministically generates 800 synthetic invoices + ground_truth.csv.
"""

import argparse

from config.settings import settings
from data_gen.generator import DatasetGenerator
from db.session import get_db_context, init_db


def run_seed(build_pdfs: bool = True, total_invoices: int = 800) -> None:
    print("=" * 60)
    print("TriLedger: Initializing Database & Seed Pipeline")
    print("=" * 60)

    # 1. Initialize Tables
    print("Step 1: Creating database tables...")
    init_db()
    print("  -> SAP tables initialized successfully.")

    # 2. Run Dataset Generation
    print(f"\nStep 2: Generating synthetic procurement dataset (Total: {total_invoices})...")
    generator = DatasetGenerator(
        seed=42,
        total_invoices=total_invoices,
        defect_rate=0.20,
        scanned_rate=0.10,
        data_dir=settings.DATA_DIR
    )

    with get_db_context() as db:
        stats = generator.generate_all(db, build_pdfs=build_pdfs)

    print("\n" + "=" * 60)
    print("Dataset Generation Complete!")
    print("=" * 60)
    print(f"Vendors Created:         {stats['vendors']}")
    print(f"Purchase Orders Created: {stats['purchase_orders']}")
    print(f"Goods Receipts Created:  {stats['goods_receipts']}")
    print(f"Total Invoices:          {stats['total_invoices']}")
    print(f"  - Clean Invoices:      {stats['clean_invoices']}")
    print(f"  - Defective Invoices:  {stats['defective_invoices']} (Rate: {stats['defective_invoices']/stats['total_invoices']:.1%})")
    print(f"  - Scanned Invoices:    {stats['scanned_invoices']} (Rate: {stats['scanned_invoices']/stats['total_invoices']:.1%})")
    print("\nDefect Breakdown:")
    for defect, count in sorted(stats['defect_breakdown'].items()):
        print(f"  - {defect:25s}: {count:3d}")
    print(f"\nGround Truth CSV:        {stats['ground_truth_file']}")
    print("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed TriLedger database")
    parser.add_argument("--skip-pdfs", action="store_true", help="Skip rendering physical PDFs for fast unit testing")
    parser.add_argument("--count", type=int, default=800, help="Number of invoices to generate")
    args = parser.parse_args()

    run_seed(build_pdfs=not args.skip_pdfs, total_invoices=args.count)
