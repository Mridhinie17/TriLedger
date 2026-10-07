"""
Synthetic ERP Dataset Generator and Ground Truth Builder for TriLedger.
Generates SAP-style procurement records:
- Vendors (LIFNR)
- Purchase Orders & Items (EBELN, EBELP)
- Goods Receipts (MBLNR)
- Invoices & Items (BELNR, RBLGP)
- Ground Truth CSV tracking injected defects
- Real PDF invoices (including 10% simulated scans for OCR fallback)
"""

import csv
import random
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from faker import Faker
from sqlalchemy.orm import Session

from config.settings import settings
from data_gen.pdf_builder import build_invoice_pdf
from db.models import (
    AuditLog,
    GoodsReceipt,
    Invoice,
    InvoiceItem,
    PurchaseOrder,
    PurchaseOrderItem,
    Vendor,
)
from fx.loader import FXLoader, FXResolver

PRODUCT_CATALOG = [
    ("Industrial Ball Bearings (SKF-6205)", "EA", 450.0),
    ("CNC Milling Cutters - 12mm Carbide", "EA", 1200.0),
    ("Hydraulic Fluid ISO VG 46 (20L Drum)", "DRUM", 3800.0),
    ("Pneumatic Solenoid Valve 24V DC", "EA", 2400.0),
    ("Stainless Steel Hex Bolts M10x50", "BOX", 850.0),
    ("Precision Torque Wrench 20-100 Nm", "EA", 5600.0),
    ("Linear Motion Guide Rail 1000mm", "EA", 4200.0),
    ("Industrial Conveyor Belt Rubber 5m", "MTR", 1800.0),
    ("Digital Caliper 150mm Mitutoyo", "EA", 3100.0),
    ("Safety Goggles & Helmet Kit", "SET", 650.0),
    ("PLC Control Module Siemens S7-1200", "EA", 18500.0),
    ("High-Performance Thermal Paste 500g", "TUB", 950.0),
    ("Optoelectronic Sensor Diffuse 300mm", "EA", 2800.0),
    ("V-Belt Transmission B-Section 68-inch", "EA", 520.0),
    ("Industrial Air Filter Cartridge", "EA", 1450.0),
]

BANK_NAMES = [
    ("State Bank of India", "SBIN0001234"),
    ("HDFC Bank", "HDFC0004567"),
    ("ICICI Bank", "ICIC0007890"),
    ("Axis Bank", "UTIB0002345"),
    ("Citibank N.A.", "CITI0001122"),
    ("HSBC Bank", "HSBC0003344"),
    ("Deutsche Bank", "DEUT0005566"),
]


class DatasetGenerator:
    def __init__(
        self,
        seed: int = 42,
        total_invoices: int = 800,
        defect_rate: float = 0.20,
        scanned_rate: float = 0.10,
        data_dir: Path = settings.DATA_DIR,
    ):
        self.seed = seed
        self.total_invoices = total_invoices
        self.defect_rate = defect_rate
        self.scanned_rate = scanned_rate
        self.data_dir = data_dir
        self.pdf_dir = data_dir / "invoices_pdf"
        self.ground_truth_path = data_dir / "ground_truth.csv"

        # Set deterministic seeds
        random.seed(seed)
        self.fake = Faker()
        Faker.seed(seed)

    def generate_all(self, db: Session, build_pdfs: bool = True) -> dict[str, Any]:
        """
        Executes end-to-end synthetic generation and loads into the database.
        Returns statistical summary of generated data.
        """
        self.pdf_dir.mkdir(parents=True, exist_ok=True)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # 1. Ensure FX rates exist
        fx_loader = FXLoader()
        fx_loader.load_rates_to_db(db, start_year=2024, currencies=["USD", "JPY", "EUR", "INR"])
        fx_resolver = FXResolver(db)

        # 2. Clear existing synthetic rows for clean deterministic reload
        db.query(InvoiceItem).delete()
        db.query(Invoice).delete()
        db.query(GoodsReceipt).delete()
        db.query(PurchaseOrderItem).delete()
        db.query(PurchaseOrder).delete()
        db.query(Vendor).delete()
        db.commit()

        # 3. Generate Vendors (~50)
        vendors = self._generate_vendors(count=50)
        db.bulk_save_objects(vendors)
        db.commit()

        # 4. Generate Purchase Orders & Items (~250 POs)
        pos, po_items = self._generate_purchase_orders(vendors, count=250)
        db.bulk_save_objects(pos)
        db.bulk_save_objects(po_items)
        db.commit()

        # 5. Generate Goods Receipts
        receipts = self._generate_goods_receipts(pos, po_items)
        db.bulk_save_objects(receipts)
        db.commit()

        # 6. Generate 800 Invoices with exactly 20% (160) defects and 10% (80) scanned
        invoices, invoice_items, ground_truth_rows = self._generate_invoices(
            pos=pos,
            po_items=po_items,
            receipts=receipts,
            vendors=vendors,
            fx_resolver=fx_resolver,
            build_pdfs=build_pdfs,
        )

        db.bulk_save_objects(invoices)
        db.bulk_save_objects(invoice_items)
        db.commit()

        # 7. Write Ground Truth CSV
        self._write_ground_truth(ground_truth_rows)

        # 8. Audit Log
        db.add(
            AuditLog(
                entity_type="SYSTEM",
                entity_id="DATASET_GENERATION",
                action="SEEDED_DATASET_GENERATED",
                actor="SYSTEM",
                details=(
                    f"total_invoices={len(invoices)}, "
                    f"defective={len([r for r in ground_truth_rows if r['is_defective']])}, "
                    f"scanned={len([r for r in ground_truth_rows if r['is_scanned']])}"
                ),
            )
        )
        db.commit()

        defect_counts = {}
        for r in ground_truth_rows:
            dt = r["defect_type"]
            defect_counts[dt] = defect_counts.get(dt, 0) + 1

        return {
            "vendors": len(vendors),
            "purchase_orders": len(pos),
            "goods_receipts": len(receipts),
            "total_invoices": len(invoices),
            "clean_invoices": defect_counts.get("none", 0),
            "defective_invoices": len(invoices) - defect_counts.get("none", 0),
            "scanned_invoices": len([r for r in ground_truth_rows if r["is_scanned"]]),
            "defect_breakdown": defect_counts,
            "ground_truth_file": str(self.ground_truth_path),
        }

    def _generate_vendors(self, count: int) -> list[Vendor]:
        vendors = []
        currencies = ["INR", "INR", "INR", "USD", "EUR", "JPY"]  # weighted to base INR
        for i in range(1, count + 1):
            vendor_id = f"VEND-{i:03d}"
            name = f"{self.fake.company()} Technologies Pvt Ltd"
            bank_name, bank_code = random.choice(BANK_NAMES)
            account_num = f"{random.randint(10000000000, 99999999999)}"
            tax_id = f"29{self.fake.bothify(text='?????####?')}1Z{random.randint(1, 9)}"
            curr = random.choice(currencies)

            vendors.append(
                Vendor(
                    vendor_id=vendor_id,
                    name=name,
                    tax_id=tax_id,
                    bank_account_number=account_num,
                    bank_name=bank_name,
                    bank_code=bank_code,
                    default_currency=curr,
                    payment_terms="Net 30",
                    address=f"{self.fake.street_address()}, {self.fake.city()}",
                    created_at=self.fake.date_time_between(start_date="-1y", end_date="-6m"),
                )
            )
        return vendors

    def _generate_purchase_orders(
        self, vendors: list[Vendor], count: int
    ) -> tuple[list[PurchaseOrder], list[PurchaseOrderItem]]:
        pos: list[PurchaseOrder] = []
        po_items: list[PurchaseOrderItem] = []

        start_date = date(2024, 1, 15)
        for i in range(1, count + 1):
            po_number = f"PO-2024-{i:05d}"
            vendor = random.choice(vendors)
            order_days = random.randint(0, 200)
            order_date = start_date + timedelta(days=order_days)
            currency = vendor.default_currency

            # Currency price adjustment factor
            curr_factor = 1.0
            if currency == "USD":
                curr_factor = 0.012  # ~ 1 USD = 83 INR
            elif currency == "EUR":
                curr_factor = 0.011  # ~ 1 EUR = 90 INR
            elif currency == "JPY":
                curr_factor = 1.8  # ~ 1 INR = 1.8 JPY

            num_lines = random.randint(1, 3)
            total_net = 0.0
            total_tax = 0.0

            selected_products = random.sample(PRODUCT_CATALOG, num_lines)
            for line_idx, (p_name, uom, base_price) in enumerate(selected_products, start=1):
                line_no = line_idx * 10
                qty = float(random.choice([5, 10, 20, 50, 100]))
                unit_price = round(base_price * curr_factor, 2)
                net = round(qty * unit_price, 2)
                tax_pct = 18.0
                tax = round(net * (tax_pct / 100.0), 2)
                total = round(net + tax, 2)

                total_net += net
                total_tax += tax

                po_items.append(
                    PurchaseOrderItem(
                        po_number=po_number,
                        line_number=line_no,
                        item_description=p_name,
                        quantity=qty,
                        unit_of_measure=uom,
                        unit_price=unit_price,
                        tax_rate_pct=tax_pct,
                        net_amount=net,
                        tax_amount=tax,
                        total_amount=total,
                    )
                )

            pos.append(
                PurchaseOrder(
                    po_number=po_number,
                    vendor_id=vendor.vendor_id,
                    order_date=order_date,
                    currency=currency,
                    total_net_amount=round(total_net, 2),
                    total_tax_amount=round(total_tax, 2),
                    total_gross_amount=round(total_net + total_tax, 2),
                    status="OPEN",
                )
            )

        return pos, po_items

    def _generate_goods_receipts(
        self, pos: list[PurchaseOrder], po_items: list[PurchaseOrderItem]
    ) -> list[GoodsReceipt]:
        receipts: list[GoodsReceipt] = []
        po_dict = {po.po_number: po for po in pos}

        for item in po_items:
            po = po_dict[item.po_number]
            receipt_date = po.order_date + timedelta(days=random.randint(2, 7))
            gr_number = f"GR-2024-{item.po_number.split('-')[-1]}"

            receipts.append(
                GoodsReceipt(
                    gr_number=gr_number,
                    po_number=po.po_number,
                    vendor_id=po.vendor_id,
                    line_number=item.line_number,
                    receipt_date=receipt_date,
                    item_description=item.item_description,
                    quantity_received=item.quantity,  # standard clean receipt
                    unit_of_measure=item.unit_of_measure,
                    received_by=f"Warehouse Specialist {random.randint(1, 5)}",
                )
            )
        return receipts

    def _generate_invoices(
        self,
        pos: list[PurchaseOrder],
        po_items: list[PurchaseOrderItem],
        receipts: list[GoodsReceipt],
        vendors: list[Vendor],
        fx_resolver: FXResolver,
        build_pdfs: bool = True,
    ) -> tuple[list[Invoice], list[InvoiceItem], list[dict[str, Any]]]:

        vendor_dict = {v.vendor_id: v for v in vendors}
        po_items_by_po: dict[str, list[PurchaseOrderItem]] = {}
        for it in po_items:
            po_items_by_po.setdefault(it.po_number, []).append(it)

        # Plan defect allocation: exactly 160 defective invoices across 8 types (20 each)
        defect_types = [
            "quantity_mismatch",
            "price_over_tolerance",
            "duplicate_invoice",
            "no_matching_po",
            "tax_miscalculation",
            "bank_details_changed",
            "fx_rate_deviation",
            "wrong_currency",
        ]
        target_defects_per_type = 20
        defect_queue = []
        for dt in defect_types:
            defect_queue.extend([dt] * target_defects_per_type)

        clean_count = self.total_invoices - len(defect_queue)
        all_planned_types = defect_queue + ["none"] * clean_count
        random.shuffle(all_planned_types)

        # Plan scanned invoices: exactly 80 scanned (10%)
        scanned_indices = set(
            random.sample(range(self.total_invoices), int(self.total_invoices * self.scanned_rate))
        )

        invoices: list[Invoice] = []
        invoice_items: list[InvoiceItem] = []
        ground_truth: list[dict[str, Any]] = []

        # Keep a list of created clean invoices for duplicate injection
        created_invoices_for_dupes: list[tuple[Invoice, list[dict[str, Any]], Vendor]] = []

        po_pool = list(pos)
        po_cycle_idx = 0

        for inv_idx in range(1, self.total_invoices + 1):
            inv_number = f"INV-2024-{inv_idx:05d}"
            plan_defect = all_planned_types[inv_idx - 1]
            is_scanned = (inv_idx - 1) in scanned_indices

            po = po_pool[po_cycle_idx % len(po_pool)]
            cycle_num = po_cycle_idx // len(po_pool)
            po_cycle_idx += 1
            vendor = vendor_dict[po.vendor_id]
            items_template = po_items_by_po[po.po_number]

            # Space recurring billing cycles by ~30 days (milestone/installment billing)
            inv_date = po.order_date + timedelta(days=5 + cycle_num * 30 + random.randint(0, 5))
            currency = po.currency

            # Resolve official reference rate on invoice date
            try:
                official_rate, _ = fx_resolver.resolve_effective_rate(inv_date, currency, "INR")
            except Exception:
                official_rate = (
                    83.20 if currency == "USD" else (90.50 if currency == "EUR" else 0.55)
                )

            stated_fx_rate = official_rate
            bank_account = vendor.bank_account_number
            bank_code = vendor.bank_code
            po_ref = po.po_number
            defect_details = "None (clean 3-way match)"

            # Construct line items
            lines: list[dict[str, Any]] = []
            for item in items_template:
                lines.append(
                    {
                        "line_number": item.line_number,
                        "item_description": item.item_description,
                        "quantity": item.quantity,
                        "unit_of_measure": item.unit_of_measure,
                        "unit_price": item.unit_price,
                        "tax_rate_pct": item.tax_rate_pct,
                        "net_amount": item.net_amount,
                        "tax_amount": item.tax_amount,
                        "total_amount": item.total_amount,
                    }
                )

            # Apply defect mutations
            if plan_defect == "quantity_mismatch":
                # Increase billed quantity by +20% (or +5 units) on first line item
                lines[0]["quantity"] = lines[0]["quantity"] + 5.0
                lines[0]["net_amount"] = round(lines[0]["quantity"] * lines[0]["unit_price"], 2)
                lines[0]["tax_amount"] = round(
                    lines[0]["net_amount"] * (lines[0]["tax_rate_pct"] / 100.0), 2
                )
                lines[0]["total_amount"] = round(lines[0]["net_amount"] + lines[0]["tax_amount"], 2)
                defect_details = f"Line {lines[0]['line_number']} quantity billed {lines[0]['quantity']} exceeds GR receipt quantity {items_template[0].quantity}"

            elif plan_defect == "price_over_tolerance":
                # Increase unit price by +8% (exceeds 1.0% tolerance and > 50 INR / 1 USD)
                original_price = lines[0]["unit_price"]
                lines[0]["unit_price"] = round(original_price * 1.08, 2)
                lines[0]["net_amount"] = round(lines[0]["quantity"] * lines[0]["unit_price"], 2)
                lines[0]["tax_amount"] = round(
                    lines[0]["net_amount"] * (lines[0]["tax_rate_pct"] / 100.0), 2
                )
                lines[0]["total_amount"] = round(lines[0]["net_amount"] + lines[0]["tax_amount"], 2)
                defect_details = f"Line {lines[0]['line_number']} price billed {lines[0]['unit_price']} exceeds PO price {original_price} by +8.0%"

            elif plan_defect == "duplicate_invoice":
                if created_invoices_for_dupes:
                    # Duplicate an existing invoice with same PO, vendor, date, and items
                    dupe_source_inv, dupe_lines, dupe_vendor = random.choice(
                        created_invoices_for_dupes
                    )
                    po_ref = dupe_source_inv.po_number
                    vendor = dupe_vendor
                    bank_account = dupe_vendor.bank_account_number
                    bank_code = dupe_vendor.bank_code
                    currency = dupe_source_inv.currency
                    inv_date = dupe_source_inv.invoice_date
                    stated_fx_rate = dupe_source_inv.stated_fx_rate
                    lines = [dict(ln) for ln in dupe_lines]
                    defect_details = f"Duplicate billing matching existing invoice {dupe_source_inv.invoice_number} for PO {po_ref}"
                else:
                    defect_details = "Duplicate invoice submission"

            elif plan_defect == "no_matching_po":
                po_ref = f"PO-PHANTOM-{random.randint(90000, 99999)}"
                defect_details = f"Cited PO {po_ref} does not exist in purchasing records"

            elif plan_defect == "tax_miscalculation":
                # Stated tax amount deviates significantly (+25% instead of 18%)
                lines[0]["tax_amount"] = round(lines[0]["net_amount"] * 0.28, 2)
                lines[0]["total_amount"] = round(lines[0]["net_amount"] + lines[0]["tax_amount"], 2)
                defect_details = f"Tax calculation mismatch: line {lines[0]['line_number']} tax states {lines[0]['tax_amount']} instead of 18% standard rate"

            elif plan_defect == "bank_details_changed":
                # Alter bank account number to simulate diversion fraud
                bank_account = f"9999{random.randint(1000000, 9999999)}"
                bank_code = "HACK0009999"
                defect_details = f"Remittance bank account {bank_account} differs from vendor master account {vendor.bank_account_number}"

            elif plan_defect == "fx_rate_deviation":
                # Use a foreign currency PO so that currency matches PO
                foreign_pos = [p for p in pos if p.currency in ("USD", "EUR", "JPY")]
                if foreign_pos:
                    po = random.choice(foreign_pos)
                    vendor = vendor_dict[po.vendor_id]
                    bank_account = vendor.bank_account_number
                    bank_code = vendor.bank_code
                    po_ref = po.po_number
                    currency = po.currency
                    inv_date = po.order_date + timedelta(days=random.randint(5, 14))
                    items_template = po_items_by_po[po.po_number]
                    lines = [
                        dict(it.__dict__)
                        for it in items_template
                        if not it.item_description.startswith("_")
                    ]
                    lines = [
                        {
                            "line_number": it.line_number,
                            "item_description": it.item_description,
                            "quantity": it.quantity,
                            "unit_of_measure": it.unit_of_measure,
                            "unit_price": it.unit_price,
                            "tax_rate_pct": it.tax_rate_pct,
                            "net_amount": it.net_amount,
                            "tax_amount": it.tax_amount,
                            "total_amount": it.total_amount,
                        }
                        for it in items_template
                    ]

                official_rate, _ = fx_resolver.resolve_effective_rate(inv_date, currency, "INR")
                stated_fx_rate = round(official_rate * 1.06, 4)
                defect_details = f"Stated FX rate {stated_fx_rate} deviates by +6.0% from official ECB reference rate {official_rate:.4f}"

            elif plan_defect == "wrong_currency":
                # Switch currency: e.g. PO was INR/USD, invoice claims EUR or JPY
                alternate_currs = [c for c in ["USD", "EUR", "JPY"] if c != currency]
                wrong_curr = random.choice(alternate_currs)
                currency = wrong_curr
                # Set stated FX rate to official rate of wrong_curr so ONLY wrong_currency is defective
                try:
                    official_rate, _ = fx_resolver.resolve_effective_rate(inv_date, currency, "INR")
                    stated_fx_rate = round(official_rate, 4)
                except Exception:
                    stated_fx_rate = 1.0
                defect_details = (
                    f"Invoice billed in {currency} but PO was contracted in {po.currency}"
                )

            # Calculate invoice header totals
            total_net = round(sum(ln["net_amount"] for ln in lines), 2)
            total_tax = round(sum(ln["tax_amount"] for ln in lines), 2)
            total_gross = round(total_net + total_tax, 2)

            pdf_filename = f"{inv_number}.pdf"
            pdf_path = self.pdf_dir / pdf_filename

            try:
                rel_pdf_path = str(pdf_path.relative_to(settings.BASE_DIR))
            except ValueError:
                rel_pdf_path = str(pdf_path)

            inv_obj = Invoice(
                invoice_number=inv_number,
                vendor_id=vendor.vendor_id,
                po_number=po_ref,
                invoice_date=inv_date,
                currency=currency,
                total_net_amount=total_net,
                total_tax_amount=total_tax,
                total_gross_amount=total_gross,
                stated_fx_rate=stated_fx_rate,
                bank_account_number=bank_account,
                bank_code=bank_code,
                pdf_path=rel_pdf_path,
                is_scanned=is_scanned,
                match_status="PENDING",
            )
            invoices.append(inv_obj)

            # Build line items
            for ln in lines:
                invoice_items.append(
                    InvoiceItem(
                        invoice_number=inv_number,
                        line_number=ln["line_number"],
                        item_description=ln["item_description"],
                        quantity=ln["quantity"],
                        unit_of_measure=ln["unit_of_measure"],
                        unit_price=ln["unit_price"],
                        tax_rate_pct=ln["tax_rate_pct"],
                        net_amount=ln["net_amount"],
                        tax_amount=ln["tax_amount"],
                        total_amount=ln["total_amount"],
                    )
                )

            # Record in ground truth
            is_defective = plan_defect != "none"
            ground_truth.append(
                {
                    "invoice_number": inv_number,
                    "vendor_id": vendor.vendor_id,
                    "po_number": po_ref,
                    "defect_type": plan_defect,
                    "is_defective": is_defective,
                    "defect_details": defect_details,
                    "currency": currency,
                    "total_amount": total_gross,
                    "is_scanned": is_scanned,
                }
            )

            # Store for duplicate reference if clean
            if not is_defective and len(created_invoices_for_dupes) < 30:
                created_invoices_for_dupes.append((inv_obj, lines, vendor))

            # Build PDF
            if build_pdfs:
                invoice_payload = {
                    "invoice_number": inv_number,
                    "vendor_id": vendor.vendor_id,
                    "vendor_name": vendor.name,
                    "vendor_address": vendor.address,
                    "tax_id": vendor.tax_id,
                    "invoice_date": inv_date.strftime("%Y-%m-%d"),
                    "po_number": po_ref,
                    "currency": currency,
                    "items": lines,
                    "total_net_amount": total_net,
                    "total_tax_amount": total_tax,
                    "total_gross_amount": total_gross,
                    "stated_fx_rate": stated_fx_rate,
                    "bank_name": vendor.bank_name,
                    "bank_account_number": bank_account,
                    "bank_code": bank_code,
                }
                build_invoice_pdf(invoice_payload, pdf_path, rasterize_as_scanned=is_scanned)

        return invoices, invoice_items, ground_truth

    def _write_ground_truth(self, rows: list[dict[str, Any]]) -> None:
        fieldnames = [
            "invoice_number",
            "vendor_id",
            "po_number",
            "defect_type",
            "is_defective",
            "defect_details",
            "currency",
            "total_amount",
            "is_scanned",
        ]
        with open(self.ground_truth_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
