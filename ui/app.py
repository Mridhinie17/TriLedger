"""
Streamlit Analyst Workbench for TriLedger Reconciliation System.
Provides interactive ERP reconciliation workbench:
- KPI Dashboard & Real-Time Metrics
- Searchable & Filterable Invoice Queue
- 3-Way Reconciliation Comparison (PO vs GR vs Invoice)
- LangGraph Autonomous Investigation Agent Trigger
- Human-in-the-Loop Override Decision Station
- Power BI Data Marts Interactive Explorer
"""

import sys
from datetime import datetime, date
from pathlib import Path
import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.settings import settings
from db.models import Invoice, PurchaseOrder, GoodsReceipt, Vendor, AuditLog
from db.session import get_db_context
from matching.engine import ReconciliationEngine
from agent.workflow import TriLedgerAgent
from agent.guardrails import GuardrailManager
from marts.exporter import DataMartExporter

st.set_page_config(
    page_title="TriLedger | 3-Way Reconciliation Workbench",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom Styling
st.markdown("""
<style>
    .metric-card {
        background-color: #f8fafc;
        border-radius: 8px;
        padding: 16px;
        border: 1px solid #e2e8f0;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }
    .badge-approved { background-color: #dcfce7; color: #166534; padding: 4px 8px; border-radius: 4px; font-weight: bold; }
    .badge-hold { background-color: #fef9c3; color: #854d0e; padding: 4px 8px; border-radius: 4px; font-weight: bold; }
    .badge-escalated { background-color: #fee2e2; color: #991b1b; padding: 4px 8px; border-radius: 4px; font-weight: bold; }
    .stTabs [data-baseweb="tab-list"] { gap: 24px; }
    .stTabs [data-baseweb="tab"] { height: 50px; white-space: pre-wrap; font-size: 16px; font-weight: 600; }
</style>
""", unsafe_allow_html=True)


def load_invoices_df():
    with get_db_context() as db:
        invoices = db.query(Invoice).all()
        vendors = {v.vendor_id: v.name for v in db.query(Vendor).all()}
        rows = []
        for inv in invoices:
            rows.append({
                "invoice_number": inv.invoice_number,
                "vendor_id": inv.vendor_id,
                "vendor_name": vendors.get(inv.vendor_id, "Unknown"),
                "po_number": inv.po_number or "NONE",
                "invoice_date": inv.invoice_date,
                "currency": inv.currency,
                "gross_amount": inv.total_gross_amount,
                "match_status": inv.match_status,
                "is_scanned": inv.is_scanned,
            })
        return pd.DataFrame(rows)


def main():
    st.title("⚖️ TriLedger: Enterprise 3-Way Reconciliation Workbench")
    st.caption("Agentic Accounts Payable Audit, European Central Bank FX Validation & LangGraph Reasoning")

    # Sidebar
    st.sidebar.header("Controls & Filters")
    status_filter = st.sidebar.selectbox("Match Status", ["ALL", "PENDING", "APPROVED", "ON_HOLD", "ESCALATED"])
    curr_filter = st.sidebar.selectbox("Currency", ["ALL", "EUR", "USD", "INR"])

    st.sidebar.divider()
    if st.sidebar.button("🔄 Export Power BI Data Marts"):
        with st.spinner("Exporting analytical CSV and Parquet marts..."):
            exporter = DataMartExporter()
            paths = exporter.export_all()
            st.sidebar.success(f"Exported {len(paths)} data marts to data/marts/")

    tab_queue, tab_investigate, tab_marts = st.tabs([
        "📋 Reconciliation Queue",
        "🔍 Single-Invoice Deep Dive & Agent",
        "📊 Power BI Data Marts"
    ])

    df = load_invoices_df()

    # KPI Top Bar
    total_inv = len(df)
    appr_cnt = len(df[df["match_status"] == "APPROVED"])
    hold_cnt = len(df[df["match_status"] == "ON_HOLD"])
    esc_cnt = len(df[df["match_status"] == "ESCALATED"])
    pend_cnt = total_inv - (appr_cnt + hold_cnt + esc_cnt)

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Total Invoices", total_inv)
    col2.metric("Approved", appr_cnt)
    col3.metric("On Hold", hold_cnt)
    col4.metric("Escalated", esc_cnt)
    col5.metric("Pending Review", pend_cnt)

    # Tab 1: Queue
    with tab_queue:
        filtered_df = df.copy()
        if status_filter != "ALL":
            filtered_df = filtered_df[filtered_df["match_status"] == status_filter]
        if curr_filter != "ALL":
            filtered_df = filtered_df[filtered_df["currency"] == curr_filter]

        st.subheader(f"Queue ({len(filtered_df)} invoices)")
        st.dataframe(
            filtered_df,
            use_container_width=True,
            column_config={
                "gross_amount": st.column_config.NumberColumn(format="%.2f"),
                "is_scanned": st.column_config.CheckboxColumn("Scanned/OCR"),
            }
        )

    # Tab 2: Investigation & Agent
    with tab_investigate:
        inv_list = df["invoice_number"].tolist()
        selected_inv = st.selectbox("Select Invoice to Reconcile", inv_list)

        if selected_inv:
            with get_db_context() as db:
                inv = db.query(Invoice).filter(Invoice.invoice_number == selected_inv).first()
                vendor = db.query(Vendor).filter(Vendor.vendor_id == inv.vendor_id).first()
                po = db.query(PurchaseOrder).filter(PurchaseOrder.po_number == inv.po_number).first() if inv.po_number else None
                engine = ReconciliationEngine(db)
                match_res = engine.reconcile_invoice(inv)

                left_col, right_col = st.columns([1, 1])

                with left_col:
                    st.markdown("### 📄 Invoice & PO Comparison")
                    st.markdown(f"**Invoice Number:** `{inv.invoice_number}`")
                    st.markdown(f"**Vendor:** {vendor.name if vendor else 'Unknown'} (`{inv.vendor_id}`)")
                    st.markdown(f"**Bank Account (Masked):** `{GuardrailManager.mask_bank_details(inv.bank_account_number or '')}`")
                    st.markdown(f"**Date:** {inv.invoice_date} | **Currency:** `{inv.currency}`")
                    st.markdown(f"**Gross Amount:** `{inv.currency} {inv.total_gross_amount:,.2f}`")

                    st.divider()
                    st.markdown("#### 3-Way Match Status")
                    if match_res.is_matched:
                        st.success("✅ 3-Way Match Succeeded (Within Tolerances)")
                    else:
                        st.error(f"❌ Discrepancies Detected ({len(match_res.discrepancies)})")
                        for d in match_res.discrepancies:
                            st.warning(f"• **[{d.check_type}]** {d.message}")

                    if match_res.isolation_forest_anomaly:
                        st.error(f"⚠️ Unsupervised Anomaly Flagged (Score: {match_res.isolation_forest_score:.4f})")

                    if po:
                        st.markdown(f"#### Referenced PO: `{po.po_number}`")
                        st.markdown(f"**PO Gross Total:** `{po.currency} {po.total_gross_amount:,.2f}`")
                    else:
                        st.error("No Referenced Purchase Order Found in ERP!")

                with right_col:
                    st.markdown("### 🤖 LangGraph Autonomous Agent")
                    if st.button("🚀 Run Agent Investigation", key="run_agent_btn"):
                        with st.spinner("Gathering ERP records & executing security guardrails..."):
                            agent = TriLedgerAgent(db)
                            report = agent.investigate(inv.invoice_number)

                            st.session_state[f"report_{inv.invoice_number}"] = report

                    report = st.session_state.get(f"report_{inv.invoice_number}")
                    if report:
                        st.markdown(f"**Recommendation:** `{report.recommended_action}` (Confidence: {report.confidence * 100:.1f}%)")
                        st.info(f"**Case Summary:**\n{report.case_summary}")
                        st.markdown(f"**Discrepancy Explanation:**\n{report.discrepancy_explanation}")
                        st.markdown(f"**Cited ERP Records:** {', '.join(f'`{r}`' for r in report.cited_records)}")

                        if report.is_adversarial_injection_detected:
                            st.error("🚨 Prompt Injection Attack Blocked by Security Guardrail!")

                        st.divider()
                        st.markdown("#### ✍️ Analyst Override & Audit Action")
                        override_action = st.radio("Choose Action", ["APPROVE", "ON_HOLD", "ESCALATE", "REJECT"], horizontal=True)
                        reason_input = st.text_input("Audit Reason", value=report.case_summary[:100])

                        if st.button("Confirm Decision", key="confirm_decision_btn"):
                            inv.match_status = override_action
                            audit = AuditLog(
                                entity_type="INVOICE",
                                entity_id=inv.invoice_number,
                                action=f"UI_ACTION_{override_action}",
                                actor="streamlit_analyst",
                                details={"reason": reason_input, "timestamp": datetime.utcnow().isoformat()}
                            )
                            db.add(audit)
                            db.commit()
                            st.success(f"Updated status to {override_action} with immutable audit log.")
                            st.rerun()

    # Tab 3: Data Marts
    with tab_marts:
        st.subheader("📊 Power BI Mart Data Previews")
        mart_choice = st.selectbox("Select Mart", ["spend_analysis", "exception_log", "invoice_aging", "open_payables", "fx_sensitivity"])
        mart_csv = settings.DATA_DIR / "marts" / f"{mart_choice}.csv"

        if mart_csv.exists():
            mart_df = pd.read_csv(mart_csv)
            st.markdown(f"**Total Records:** {len(mart_df)} | **Location:** `{mart_csv}`")
            st.dataframe(mart_df.head(100), use_container_width=True)
        else:
            st.info(f"Mart {mart_choice}.csv not yet exported. Click 'Export Power BI Data Marts' in the sidebar.")


if __name__ == "__main__":
    main()
