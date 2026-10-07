"""
SAP-style Enterprise Database Models for TriLedger Reconciliation System.
Maps standard SAP ERP entities (LIFNR, EBELN, EBELP, MBLNR, BELNR) to SQLAlchemy models.
"""

from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class Vendor(Base):
    """SAP Vendor Master Record (LIFNR)."""
    __tablename__ = "vendors"

    vendor_id = Column(String(32), primary_key=True, index=True, doc="SAP LIFNR: Vendor Account Number")
    name = Column(String(255), nullable=False, doc="SAP NAME1: Name 1")
    tax_id = Column(String(64), nullable=False, doc="SAP STCEG: Tax Number / GSTIN / VAT")
    bank_account_number = Column(String(64), nullable=False, doc="SAP BANKN: Bank Account Number")
    bank_name = Column(String(128), nullable=False, doc="SAP BANKA: Name of Bank")
    bank_code = Column(String(32), nullable=False, doc="SAP SWIFT/IFSC: Bank Key")
    default_currency = Column(String(8), nullable=False, default="INR", doc="SAP WAERS: Currency Key")
    payment_terms = Column(String(32), nullable=False, default="Net 30", doc="SAP ZTERM: Terms of Payment")
    address = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    purchase_orders = relationship("PurchaseOrder", back_populates="vendor")
    goods_receipts = relationship("GoodsReceipt", back_populates="vendor")


class PurchaseOrder(Base):
    """SAP Purchasing Document Header (EKKO / EBELN)."""
    __tablename__ = "purchase_orders"

    po_number = Column(String(32), primary_key=True, index=True, doc="SAP EBELN: Purchasing Document Number")
    vendor_id = Column(String(32), ForeignKey("vendors.vendor_id"), nullable=False, index=True, doc="SAP LIFNR")
    order_date = Column(Date, nullable=False, doc="SAP BEDAT: Purchasing Document Date")
    currency = Column(String(8), nullable=False, default="INR", doc="SAP WAERS: Currency Key")
    total_net_amount = Column(Float, nullable=False, default=0.0, doc="Total Net Value without Tax")
    total_tax_amount = Column(Float, nullable=False, default=0.0, doc="Total Tax Amount")
    total_gross_amount = Column(Float, nullable=False, default=0.0, doc="Total Gross Amount")
    status = Column(String(32), nullable=False, default="OPEN", doc="Document Status: OPEN, RECEIVED, BILLED, CLOSED")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    vendor = relationship("Vendor", back_populates="purchase_orders")
    items = relationship("PurchaseOrderItem", back_populates="purchase_order", cascade="all, delete-orphan")
    goods_receipts = relationship("GoodsReceipt", back_populates="purchase_order")


class PurchaseOrderItem(Base):
    """SAP Purchasing Document Item (EKPO / EBELP)."""
    __tablename__ = "po_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    po_number = Column(String(32), ForeignKey("purchase_orders.po_number"), nullable=False, index=True, doc="SAP EBELN")
    line_number = Column(Integer, nullable=False, doc="SAP EBELP: Item Number (10, 20, 30...)")
    item_description = Column(String(255), nullable=False, doc="SAP TXZ01: Short Text")
    quantity = Column(Float, nullable=False, doc="SAP MENGE: Target Quantity")
    unit_of_measure = Column(String(16), nullable=False, default="EA", doc="SAP MEINS: Order Unit")
    unit_price = Column(Float, nullable=False, doc="SAP NETPR: Net Price")
    tax_rate_pct = Column(Float, nullable=False, default=18.0, doc="Tax percentage (e.g. 18.0 for 18% GST)")
    net_amount = Column(Float, nullable=False, doc="Net amount for item")
    tax_amount = Column(Float, nullable=False, doc="Tax amount for item")
    total_amount = Column(Float, nullable=False, doc="Gross amount for item")

    purchase_order = relationship("PurchaseOrder", back_populates="items")

    __table_args__ = (
        UniqueConstraint("po_number", "line_number", name="uq_po_item_line"),
    )


class GoodsReceipt(Base):
    """SAP Material Document / Goods Receipt Item (MSEG / MBLNR)."""
    __tablename__ = "goods_receipts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    gr_number = Column(String(32), nullable=False, index=True, doc="SAP MBLNR: Number of Material Document")
    po_number = Column(String(32), ForeignKey("purchase_orders.po_number"), nullable=False, index=True, doc="SAP EBELN")
    vendor_id = Column(String(32), ForeignKey("vendors.vendor_id"), nullable=False, index=True, doc="SAP LIFNR")
    line_number = Column(Integer, nullable=False, doc="SAP ZEILE: Item in Material Document (corresponds to EBELP)")
    receipt_date = Column(Date, nullable=False, doc="SAP BUDAT: Posting Date in Document")
    item_description = Column(String(255), nullable=False)
    quantity_received = Column(Float, nullable=False, doc="SAP MENGE: Quantity received")
    unit_of_measure = Column(String(16), nullable=False, default="EA")
    received_by = Column(String(64), nullable=False, default="Warehouse Mgr")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    vendor = relationship("Vendor", back_populates="goods_receipts")
    purchase_order = relationship("PurchaseOrder", back_populates="goods_receipts")

    __table_args__ = (
        UniqueConstraint("gr_number", "line_number", name="uq_gr_number_line"),
    )


class Invoice(Base):
    """SAP Incoming Invoice Header (RBKP / BELNR)."""
    __tablename__ = "invoices"

    invoice_number = Column(String(64), primary_key=True, index=True, doc="SAP BELNR: Document Number of an Invoice Document")
    vendor_id = Column(String(32), nullable=False, index=True, doc="Claimed Vendor LIFNR on invoice")
    po_number = Column(String(32), nullable=True, index=True, doc="Claimed PO EBELN on invoice (can be null or phantom)")
    invoice_date = Column(Date, nullable=False, index=True, doc="SAP BLDAT: Document Date in Document")
    currency = Column(String(8), nullable=False, doc="SAP WAERS: Currency Key on invoice")
    total_net_amount = Column(Float, nullable=False, doc="Invoice subtotal before tax")
    total_tax_amount = Column(Float, nullable=False, doc="Invoice tax amount")
    total_gross_amount = Column(Float, nullable=False, doc="Invoice total gross payable")
    stated_fx_rate = Column(Float, nullable=True, default=1.0, doc="Claimed exchange rate to base currency (INR)")
    bank_account_number = Column(String(64), nullable=True, doc="Claimed bank account number on invoice")
    bank_code = Column(String(32), nullable=True, doc="Claimed IFSC/SWIFT key on invoice")
    pdf_path = Column(String(500), nullable=True, doc="Relative or absolute path to generated PDF")
    is_scanned = Column(Boolean, nullable=False, default=False, doc="Whether PDF was rasterized to simulate physical scan")
    match_status = Column(String(32), nullable=False, default="PENDING", doc="PENDING, APPROVED, ON_HOLD, ESCALATED, REJECTED")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    items = relationship("InvoiceItem", back_populates="invoice", cascade="all, delete-orphan")


class InvoiceItem(Base):
    """SAP Incoming Invoice Item (RSEG / RBLGP)."""
    __tablename__ = "invoice_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    invoice_number = Column(String(64), ForeignKey("invoices.invoice_number"), nullable=False, index=True)
    line_number = Column(Integer, nullable=False, doc="Item line number (10, 20...)")
    item_description = Column(String(255), nullable=False)
    quantity = Column(Float, nullable=False, doc="Billed quantity on invoice")
    unit_of_measure = Column(String(16), nullable=False, default="EA")
    unit_price = Column(Float, nullable=False, doc="Billed unit price on invoice")
    tax_rate_pct = Column(Float, nullable=False, default=18.0)
    net_amount = Column(Float, nullable=False)
    tax_amount = Column(Float, nullable=False)
    total_amount = Column(Float, nullable=False)

    invoice = relationship("Invoice", back_populates="items")


class FXRate(Base):
    """Official Foreign Exchange Reference Rates (e.g. European Central Bank)."""
    __tablename__ = "fx_rates"

    id = Column(Integer, primary_key=True, autoincrement=True)
    rate_date = Column(Date, nullable=False, index=True)
    base_currency = Column(String(8), nullable=False, doc="Base currency for quotation (e.g. EUR)")
    target_currency = Column(String(8), nullable=False, doc="Target currency (e.g. INR, USD, JPY)")
    rate = Column(Float, nullable=False, doc="Units of target currency per 1 unit of base currency")
    source = Column(String(64), nullable=False, default="ECB_REFERENCE_HISTORICAL")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("rate_date", "base_currency", "target_currency", name="uq_fx_rate_date_pair"),
        Index("ix_fx_lookup", "rate_date", "target_currency"),
    )


class AuditLog(Base):
    """Immutable Audit Trail for all system events, AI investigations, and human decisions."""
    __tablename__ = "audit_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    entity_type = Column(String(32), nullable=False, doc="INVOICE, PO, DECISION, FX_LOAD, SYSTEM")
    entity_id = Column(String(64), nullable=False, index=True)
    action = Column(String(64), nullable=False, doc="INGESTED, 3WAY_MATCHED, AGENT_INVESTIGATED, HUMAN_APPROVED, HUMAN_HELD, HUMAN_ESCALATED")
    actor = Column(String(64), nullable=False, doc="SYSTEM, AGENT, HUMAN_USER")
    details = Column(Text, nullable=True, doc="JSON-encoded contextual details, cited IDs, or reason notes")


class RejectedRow(Base):
    """Dead-letter store for data-quality failures and unparseable ingestion payloads."""
    __tablename__ = "rejected_rows"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    source_table = Column(String(64), nullable=False, doc="Source entity name (e.g. invoices, fx_rates, po_items)")
    raw_payload = Column(Text, nullable=False, doc="Original raw payload string or JSON")
    rejection_reason = Column(String(255), nullable=False, doc="Descriptive failure reason code")
