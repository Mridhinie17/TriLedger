"""
Professional Invoice PDF Generator and Scanned/Rasterized PDF Simulator.
Uses ReportLab to generate clean enterprise invoice layouts and pdf2image/Pillow to simulate physical scans.
"""

import io
from pathlib import Path
from typing import Any

import pdf2image
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def build_invoice_pdf(
    invoice_data: dict[str, Any],
    output_path: Path,
    rasterize_as_scanned: bool = False
) -> Path:
    """
    Renders an invoice to PDF. If rasterize_as_scanned is True,
    the rendered PDF is converted to a simulated low-res/greyscale scan image and re-saved.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temp_buffer = io.BytesIO()

    doc = SimpleDocTemplate(
        temp_buffer,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )

    styles = getSampleStyleSheet()
    header_style = ParagraphStyle(
        'HeaderStyle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=18,
        leading=22,
        textColor=colors.HexColor('#1E293B')
    )
    subhead_style = ParagraphStyle(
        'SubHeadStyle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=12,
        textColor=colors.HexColor('#64748B')
    )
    body_style = ParagraphStyle(
        'BodyStyle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=12,
        textColor=colors.HexColor('#334155')
    )

    story = []

    # Title & Invoice Header
    story.append(Paragraph(f"TAX INVOICE: {invoice_data['invoice_number']}", header_style))
    story.append(Paragraph("TriLedger Enterprise Procurement Network - Inbound Billing", subhead_style))
    story.append(Spacer(1, 15))

    # Meta Info Grid: Vendor info on left, Invoice details on right
    meta_table_data = [
        [
            Paragraph(f"<b>Vendor:</b> {invoice_data['vendor_name']}<br/>"
                      f"<b>Vendor ID:</b> {invoice_data['vendor_id']}<br/>"
                      f"<b>Tax ID / GSTIN:</b> {invoice_data['tax_id']}<br/>"
                      f"<b>Address:</b> {invoice_data.get('vendor_address', 'Industrial Zone, Bangalore')}", body_style),
            Paragraph(f"<b>Invoice Date:</b> {invoice_data['invoice_date']}<br/>"
                      f"<b>PO Reference:</b> {invoice_data.get('po_number', 'N/A')}<br/>"
                      f"<b>Currency:</b> {invoice_data['currency']}<br/>"
                      f"<b>Payment Terms:</b> Net 30 Days", body_style)
        ]
    ]
    meta_table = Table(meta_table_data, colWidths=[270, 270])
    meta_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F8FAFC')),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#E2E8F0')),
        ('PADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 15))

    # Line Items Table
    curr_symbol = invoice_data['currency']
    table_header = ["Item", "Description", "Qty", "UOM", f"Unit Price ({curr_symbol})", f"Net ({curr_symbol})", f"Tax ({curr_symbol})", f"Total ({curr_symbol})"]
    line_data = [table_header]

    for item in invoice_data['items']:
        line_data.append([
            str(item['line_number']),
            Paragraph(item['item_description'], body_style),
            f"{item['quantity']:.2f}",
            item.get('unit_of_measure', 'EA'),
            f"{item['unit_price']:.2f}",
            f"{item['net_amount']:.2f}",
            f"{item['tax_amount']:.2f}",
            f"{item['total_amount']:.2f}"
        ])

    items_table = Table(line_data, colWidths=[35, 155, 45, 35, 75, 65, 65, 65])
    items_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#F1F5F9')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#0F172A')),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('ALIGN', (2, 0), (-1, -1), 'RIGHT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    story.append(items_table)
    story.append(Spacer(1, 15))

    # Totals & Banking Details Grid
    fx_rate_note = ""
    if invoice_data.get('stated_fx_rate') and invoice_data['currency'] != "INR":
        fx_rate_note = f"<br/><b>Stated FX Rate:</b> 1 {invoice_data['currency']} = {invoice_data['stated_fx_rate']:.4f} INR"

    bank_details_html = (
        f"<b>Remittance Banking Information:</b><br/>"
        f"Bank Name: {invoice_data.get('bank_name', 'HDFC Bank')}<br/>"
        f"Account No: {invoice_data.get('bank_account_number', 'N/A')}<br/>"
        f"IFSC / SWIFT: {invoice_data.get('bank_code', 'N/A')}"
        f"{fx_rate_note}"
    )

    totals_table_data = [
        [
            Paragraph(bank_details_html, body_style),
            Table([
                ["Subtotal:", f"{curr_symbol} {invoice_data['total_net_amount']:.2f}"],
                ["Tax Amount:", f"{curr_symbol} {invoice_data['total_tax_amount']:.2f}"],
                ["Total Payable:", f"{curr_symbol} {invoice_data['total_gross_amount']:.2f}"]
            ], colWidths=[90, 110], style=[
                ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
                ('FONTNAME', (0, 2), (-1, 2), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 2), (-1, 2), 11),
                ('TEXTCOLOR', (0, 2), (-1, 2), colors.HexColor('#0F172A')),
                ('LINEABOVE', (0, 2), (-1, 2), 1, colors.HexColor('#0F172A')),
                ('PADDING', (0, 0), (-1, -1), 4),
            ])
        ]
    ]

    totals_table = Table(totals_table_data, colWidths=[340, 200])
    totals_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('PADDING', (0, 0), (-1, -1), 0),
    ]))
    story.append(totals_table)

    # Build the base clean PDF
    doc.build(story)
    pdf_bytes = temp_buffer.getvalue()

    if not rasterize_as_scanned:
        with open(output_path, "wb") as f:
            f.write(pdf_bytes)
        return output_path

    # Rasterize to simulate a scanned physical invoice
    # Converts PDF pages to 150 DPI images, converts to greyscale, and re-encapsulates as image PDF
    images = pdf2image.convert_from_bytes(pdf_bytes, dpi=150)
    scanned_images = []
    for img in images:
        # Convert to greyscale and apply mild scan noise / contrast
        grey_img = img.convert('L')
        scanned_images.append(grey_img)

    if scanned_images:
        scanned_images[0].save(
            output_path,
            "PDF",
            resolution=150.0,
            save_all=True,
            append_images=scanned_images[1:]
        )
    return output_path
