"""
Enterprise Invoice Field Extractor with OCR Fallback.
Uses pdfplumber for digital PDFs and falls back to pytesseract + pdf2image for scanned/rasterized documents.
Calculates per-field confidence scores and validates against Pydantic schemas.
"""

import re
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

import pdf2image
import pdfplumber
import pytesseract

from extraction.schemas import ExtractedInvoice, ExtractedLineItem, ExtractionResult


class InvoiceExtractor:
    def __init__(self, confidence_threshold: float = 0.85):
        self.confidence_threshold = confidence_threshold

    def extract_from_pdf(self, pdf_path: Path) -> ExtractionResult:
        """
        Ingests a PDF, runs digital extraction or OCR fallback, parses fields,
        computes confidence scores, and returns an ExtractionResult.
        """
        raw_text, tables, is_ocr = self._get_text_and_tables(pdf_path)

        fields, confidences = self._parse_fields(raw_text, tables, is_ocr)

        # Flag fields below confidence threshold
        low_confidence_fields = [
            f_name for f_name, score in confidences.items()
            if score < self.confidence_threshold
        ]

        overall_conf = round(sum(confidences.values()) / max(len(confidences), 1), 4)
        flagged = len(low_confidence_fields) > 0 or overall_conf < self.confidence_threshold

        extracted_inv = ExtractedInvoice(
            invoice_number=fields.get("invoice_number", "UNKNOWN"),
            vendor_id=fields.get("vendor_id", "UNKNOWN"),
            vendor_name=fields.get("vendor_name"),
            tax_id=fields.get("tax_id"),
            invoice_date=fields.get("invoice_date", date(2024, 1, 1)),
            po_number=fields.get("po_number"),
            currency=fields.get("currency", "INR"),
            items=fields.get("items", []),
            total_net_amount=fields.get("total_net_amount", 0.0),
            total_tax_amount=fields.get("total_tax_amount", 0.0),
            total_gross_amount=fields.get("total_gross_amount", 0.0),
            stated_fx_rate=fields.get("stated_fx_rate"),
            bank_name=fields.get("bank_name"),
            bank_account_number=fields.get("bank_account_number"),
            bank_code=fields.get("bank_code"),
            is_ocr_fallback_used=is_ocr,
            raw_text=raw_text
        )

        return ExtractionResult(
            invoice=extracted_inv,
            field_confidences=confidences,
            overall_confidence=overall_conf,
            flagged_for_review=flagged,
            low_confidence_fields=low_confidence_fields
        )

    def _get_text_and_tables(self, pdf_path: Path) -> Tuple[str, List[List[List[str]]], bool]:
        """Extracts text and tables, falling back to Tesseract OCR if text is missing or sparse."""
        raw_text = ""
        tables: List[List[List[str]]] = []

        try:
            with pdfplumber.open(pdf_path) as pdf:
                for page in pdf.pages:
                    p_text = page.extract_text()
                    if p_text:
                        raw_text += p_text + "\n"
                    p_tables = page.extract_tables()
                    if p_tables:
                        tables.extend(p_tables)
        except Exception:
            raw_text = ""

        # If extracted digital text is less than 50 characters, PDF is scanned/rasterized
        if len(raw_text.strip()) < 50:
            try:
                images = pdf2image.convert_from_path(pdf_path, dpi=200)
                ocr_parts = []
                for img in images:
                    ocr_parts.append(pytesseract.image_to_string(img))
                raw_text = "\n".join(ocr_parts)
                return raw_text, tables, True
            except Exception:
                # Corrupt or unparseable document
                return "", [], True

        return raw_text, tables, False

    def _parse_fields(
        self,
        text: str,
        tables: List[List[List[str]]],
        is_ocr: bool
    ) -> Tuple[Dict[str, Any], Dict[str, float]]:
        base_conf = 0.95 if is_ocr else 1.0
        fields: Dict[str, Any] = {}
        confidences: Dict[str, float] = {}

        # 1. Invoice Number
        inv_match = re.search(r"TAX INVOICE:\s*([A-Za-z0-9\-]+)", text, re.IGNORECASE) or \
                    re.search(r"INVOICE\s*(?:NUMBER|NO|#)?:\s*([A-Za-z0-9\-]+)", text, re.IGNORECASE)
        if inv_match:
            fields["invoice_number"] = inv_match.group(1).strip()
            confidences["invoice_number"] = base_conf
        else:
            fields["invoice_number"] = "UNKNOWN"
            confidences["invoice_number"] = 0.0

        # 2. Vendor ID
        vend_match = re.search(r"Vendor ID:\s*([A-Za-z0-9\-]+)", text, re.IGNORECASE)
        if vend_match:
            fields["vendor_id"] = vend_match.group(1).strip()
            confidences["vendor_id"] = base_conf
        else:
            fields["vendor_id"] = "UNKNOWN"
            confidences["vendor_id"] = 0.0

        # 3. Vendor Name
        vname_match = re.search(r"Vendor:\s*([^\n\r]+?)(?:\s+Invoice Date:|\s+Tax ID|\s+Vendor ID|\n)", text, re.IGNORECASE)
        if vname_match:
            fields["vendor_name"] = vname_match.group(1).strip()
            confidences["vendor_name"] = base_conf
        else:
            fields["vendor_name"] = None
            confidences["vendor_name"] = 0.50

        # 4. Tax ID / GSTIN
        tax_id_match = re.search(r"Tax ID\s*(?:/\s*GSTIN)?:\s*([A-Za-z0-9]+)", text, re.IGNORECASE)
        if tax_id_match:
            fields["tax_id"] = tax_id_match.group(1).strip()
            confidences["tax_id"] = base_conf
        else:
            fields["tax_id"] = None
            confidences["tax_id"] = 0.50

        # 5. Invoice Date
        date_match = re.search(r"Invoice Date:\s*(\d{4}-\d{2}-\d{2})", text, re.IGNORECASE)
        if date_match:
            try:
                fields["invoice_date"] = datetime.strptime(date_match.group(1).strip(), "%Y-%m-%d").date()
                confidences["invoice_date"] = base_conf
            except ValueError:
                fields["invoice_date"] = date(2024, 1, 1)
                confidences["invoice_date"] = 0.40
        else:
            fields["invoice_date"] = date(2024, 1, 1)
            confidences["invoice_date"] = 0.0

        # 6. PO Number Reference
        po_match = re.search(r"PO Reference:\s*([A-Za-z0-9\-]+)", text, re.IGNORECASE)
        if po_match:
            po_val = po_match.group(1).strip()
            fields["po_number"] = None if po_val.upper() in ("N/A", "NONE") else po_val
            confidences["po_number"] = base_conf
        else:
            fields["po_number"] = None
            confidences["po_number"] = 0.50

        # 7. Currency
        curr_match = re.search(r"Currency:\s*([A-Za-z]{3})", text, re.IGNORECASE)
        if curr_match:
            fields["currency"] = curr_match.group(1).strip().upper()
            confidences["currency"] = base_conf
        else:
            fields["currency"] = "INR"
            confidences["currency"] = 0.30

        # 8. Totals (Subtotal, Tax, Gross)
        net_match = re.search(r"Subtotal:\s*(?:[A-Za-z]{3}\s*)?([0-9,]+\.[0-9]{2})", text, re.IGNORECASE)
        tax_match = re.search(r"Tax Amount:\s*(?:[A-Za-z]{3}\s*)?([0-9,]+\.[0-9]{2})", text, re.IGNORECASE)
        gross_match = re.search(r"Total Payable:\s*(?:[A-Za-z]{3}\s*)?([0-9,]+\.[0-9]{2})", text, re.IGNORECASE)

        net_val = float(net_match.group(1).replace(",", "")) if net_match else 0.0
        tax_val = float(tax_match.group(1).replace(",", "")) if tax_match else 0.0
        gross_val = float(gross_match.group(1).replace(",", "")) if gross_match else 0.0

        fields["total_net_amount"] = net_val
        fields["total_tax_amount"] = tax_val
        fields["total_gross_amount"] = gross_val

        confidences["total_net_amount"] = base_conf if net_match else 0.0
        confidences["total_tax_amount"] = base_conf if tax_match else 0.0
        confidences["total_gross_amount"] = base_conf if gross_match else 0.0

        # Cross-validation math check
        if gross_val > 0 and abs(gross_val - (net_val + tax_val)) <= 0.10:
            confidences["math_reconciliation"] = base_conf
        else:
            confidences["math_reconciliation"] = 0.65

        # 9. Stated FX Rate
        fx_match = re.search(r"Stated FX Rate:\s*1\s*[A-Za-z]{3}\s*=\s*([0-9.]+)\s*INR", text, re.IGNORECASE)
        if fx_match:
            fields["stated_fx_rate"] = float(fx_match.group(1).strip())
            confidences["stated_fx_rate"] = base_conf
        else:
            fields["stated_fx_rate"] = None
            confidences["stated_fx_rate"] = 1.0  # None is expected for INR invoices

        # 10. Bank Details
        bname_match = re.search(r"Bank Name:\s*([^\n\r]+)", text, re.IGNORECASE)
        acc_match = re.search(r"Account No:\s*([0-9]+)", text, re.IGNORECASE)
        code_match = re.search(r"IFSC\s*/\s*SWIFT:\s*([A-Za-z0-9]+)", text, re.IGNORECASE)

        fields["bank_name"] = bname_match.group(1).strip() if bname_match else None
        fields["bank_account_number"] = acc_match.group(1).strip() if acc_match else None
        fields["bank_code"] = code_match.group(1).strip() if code_match else None

        confidences["bank_account_number"] = base_conf if acc_match else 0.40
        confidences["bank_code"] = base_conf if code_match else 0.40

        # 11. Line Items
        items: List[ExtractedLineItem] = []
        if tables:
            # Parse digital table
            for tbl in tables:
                if len(tbl) < 2:
                    continue
                header = [str(col).strip() if col else "" for col in tbl[0]]
                if "Item" in header and "Qty" in header:
                    for row in tbl[1:]:
                        if len(row) < 8 or not row[0]:
                            continue
                        try:
                            line_no = int(str(row[0]).strip())
                            desc = str(row[1]).strip()
                            qty = float(str(row[2]).replace(",", "").strip())
                            uom = str(row[3]).strip()
                            price = float(str(row[4]).replace(",", "").strip())
                            net_amt = float(str(row[5]).replace(",", "").strip())
                            tax_amt = float(str(row[6]).replace(",", "").strip())
                            tot_amt = float(str(row[7]).replace(",", "").strip())
                            items.append(ExtractedLineItem(
                                line_number=line_no,
                                item_description=desc,
                                quantity=qty,
                                unit_of_measure=uom,
                                unit_price=price,
                                net_amount=net_amt,
                                tax_amount=tax_amt,
                                total_amount=tot_amt
                            ))
                        except (ValueError, TypeError):
                            continue

        # If table parsing didn't find lines (e.g. OCR text), use line-by-line regex
        if not items:
            line_pattern = re.compile(
                r"^\s*(\d{2,3})\s+(.+?)\s+([\d.]+)\s+([A-Za-z]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)",
                re.MULTILINE
            )
            for m in line_pattern.finditer(text):
                try:
                    items.append(ExtractedLineItem(
                        line_number=int(m.group(1)),
                        item_description=m.group(2).strip(),
                        quantity=float(m.group(3)),
                        unit_of_measure=m.group(4).strip(),
                        unit_price=float(m.group(5)),
                        net_amount=float(m.group(6)),
                        tax_amount=float(m.group(7)),
                        total_amount=float(m.group(8))
                    ))
                except (ValueError, TypeError):
                    continue

        fields["items"] = items
        confidences["line_items"] = base_conf if items else 0.50

        return fields, confidences
