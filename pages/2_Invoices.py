import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import streamlit as st
import pandas as pd
from datetime import datetime, date
from services.client_service import get_all_clients
from services.invoice_service import create_invoice, get_invoices, get_invoice
from utils.formatting import fmt_currency, fmt_date, fmt_month, TALLY_CSS

st.set_page_config(page_title="Invoices — Vaishnavi", layout="wide")
st.markdown(TALLY_CSS, unsafe_allow_html=True)
st.markdown('<div class="tally-header">🧾 Invoice Management</div>', unsafe_allow_html=True)

tab1, tab2 = st.tabs(["📋 Invoice List", "➕ New Invoice"])

# ── Tab 1: Invoice List ────────────────────────────────────────────────────────
with tab1:
    col_f1, col_f2, col_f3 = st.columns(3)
    clients = get_all_clients()
    client_names = ["All Clients"] + [c["name"] for c in clients]
    client_map = {c["name"]: c["id"] for c in clients}

    filter_client = col_f1.selectbox("Client", client_names)
    filter_status = col_f2.selectbox("Status", ["All", "unpaid", "partial", "paid", "excess"])
    filter_month = col_f3.text_input("Billing Month (YYYY-MM)", placeholder="2025-05")

    kwargs = {}
    if filter_client != "All Clients":
        kwargs["client_id"] = client_map[filter_client]
    if filter_status != "All":
        kwargs["status"] = filter_status
    if filter_month.strip():
        kwargs["billing_month"] = filter_month.strip()

    invoices = get_invoices(**kwargs)
    if not invoices:
        st.info("No invoices found.")
    else:
        rows = []
        for inv in invoices:
            status = inv.get("status", "")
            badge = f'<span class="{status}-badge">{status.upper()}</span>'
            rows.append({
                "Invoice No": inv.get("invoice_no", ""),
                "Client": inv.get("client_name", ""),
                "Month": fmt_month(inv.get("billing_month", "")),
                "EPF (₹)": f"{inv.get('epf_amount', 0):,.2f}",
                "ESIC (₹)": f"{inv.get('esic_amount', 0):,.2f}",
                "Prof Fee (₹)": f"{inv.get('professional_fee', 0):,.2f}",
                "Total": fmt_currency(inv.get("total_amount", 0)),
                "Paid": fmt_currency(inv.get("paid_amount", 0)),
                "Balance Due": fmt_currency(inv.get("balance_due", 0)),
                "Status": status.upper(),
            })
        df = pd.DataFrame(rows)
        st.dataframe(df, use_container_width=True, hide_index=True)

        total_invoiced = sum(inv.get("total_amount", 0) for inv in invoices)
        total_paid = sum(inv.get("paid_amount", 0) for inv in invoices)
        total_due = sum(inv.get("balance_due", 0) for inv in invoices)
        c1, c2, c3 = st.columns(3)
        c1.metric("Total Invoiced", fmt_currency(total_invoiced))
        c2.metric("Total Collected", fmt_currency(total_paid))
        c3.metric("Total Outstanding", fmt_currency(total_due))

# ── Tab 2: New Invoice ─────────────────────────────────────────────────────────
with tab2:
    st.subheader("Create New Invoice")
    clients = get_all_clients()
    if not clients:
        st.warning("Please add clients first.")
    else:
        with st.form("new_invoice_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                sel_client = st.selectbox("Client *", [c["name"] for c in clients])
                billing_month = st.text_input("Billing Month (YYYY-MM) *", value=datetime.today().strftime("%Y-%m"))
                due_date = st.date_input("Due Date", value=date.today())
            with col2:
                epf_amt = st.number_input("EPF Amount (₹)", min_value=0.0, value=0.0, step=100.0)
                esic_amt = st.number_input("ESIC Amount (₹)", min_value=0.0, value=0.0, step=100.0)
                prof_fee = st.number_input("Professional Fee (₹)", min_value=0.0, value=2000.0, step=100.0)

            total_preview = epf_amt + esic_amt + prof_fee
            st.info(f"**Total Invoice Amount: {fmt_currency(total_preview)}**  (EPF + ESIC + Professional Fee)")
            notes = st.text_area("Notes (optional)")

            if st.form_submit_button("💾 Save Invoice", type="primary"):
                client_id = next(c["id"] for c in clients if c["name"] == sel_client)
                if not billing_month.strip():
                    st.error("Billing month is required.")
                elif total_preview == 0:
                    st.error("Invoice total cannot be zero.")
                else:
                    inv_id = create_invoice({
                        "client_id": client_id,
                        "billing_month": billing_month.strip(),
                        "epf_amount": epf_amt,
                        "esic_amount": esic_amt,
                        "professional_fee": prof_fee,
                        "due_date": datetime.combine(due_date, datetime.min.time()),
                        "notes": notes,
                    })
                    st.success(f"✅ Invoice created! Total: {fmt_currency(total_preview)}")
