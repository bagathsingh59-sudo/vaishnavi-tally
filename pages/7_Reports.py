import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import streamlit as st
import pandas as pd
from datetime import datetime, date
from services.report_service import (
    get_trial_balance, get_profit_loss, get_short_payments,
    get_excess_payments, get_outstanding_agewise, update_short_excess_status,
)
from utils.formatting import fmt_currency, fmt_date, fmt_month, TALLY_CSS

st.set_page_config(page_title="Reports — Vaishnavi", layout="wide")
st.markdown(TALLY_CSS, unsafe_allow_html=True)
st.markdown('<div class="tally-header">📊 Reports & Statements</div>', unsafe_allow_html=True)

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "⚖️ Trial Balance",
    "📈 Profit & Loss",
    "🔴 Short Payments",
    "🟢 Excess Payments",
    "📅 Age-wise Outstanding",
])

# ── Tab 1: Trial Balance ──────────────────────────────────────────────────────
with tab1:
    st.subheader("Trial Balance")
    as_of = st.date_input("As on Date", value=date.today())
    as_of_dt = datetime.combine(as_of, datetime.max.time())

    tb = get_trial_balance(as_of_dt)
    if tb:
        rows = []
        total_dr = total_cr = 0.0
        for r in tb:
            rows.append({
                "Ledger": r["ledger_name"],
                "Group": r["group"],
                "Opening Dr": f"{r['opening_dr']:,.2f}" if r["opening_dr"] else "—",
                "Opening Cr": f"{r['opening_cr']:,.2f}" if r["opening_cr"] else "—",
                "Transactions Dr": f"{r['total_dr']:,.2f}" if r["total_dr"] else "—",
                "Transactions Cr": f"{r['total_cr']:,.2f}" if r["total_cr"] else "—",
                "Closing Dr": f"{r['closing_dr']:,.2f}" if r["closing_dr"] else "—",
                "Closing Cr": f"{r['closing_cr']:,.2f}" if r["closing_cr"] else "—",
            })
            total_dr += r["closing_dr"]
            total_cr += r["closing_cr"]
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        col_tdr, col_tcr, col_diff = st.columns(3)
        col_tdr.metric("Total Dr", fmt_currency(total_dr))
        col_tcr.metric("Total Cr", fmt_currency(total_cr))
        diff = abs(total_dr - total_cr)
        if diff < 1:
            col_diff.success(f"✅ Balanced — Difference: {fmt_currency(diff)}")
        else:
            col_diff.error(f"⚠️ Out of balance by {fmt_currency(diff)}")
    else:
        st.info("No data for trial balance.")

# ── Tab 2: Profit & Loss ──────────────────────────────────────────────────────
with tab2:
    st.subheader("Profit & Loss Statement")
    col_fd, col_td = st.columns(2)
    fy_start = date(datetime.today().year if datetime.today().month >= 4 else datetime.today().year - 1, 4, 1)
    pl_from = col_fd.date_input("From", value=fy_start)
    pl_to = col_td.date_input("To", value=date.today())

    pl = get_profit_loss(
        datetime.combine(pl_from, datetime.min.time()),
        datetime.combine(pl_to, datetime.max.time()),
    )

    col_inc, col_exp = st.columns(2)
    with col_inc:
        st.markdown("### Income")
        if pl["income"]:
            for item in pl["income"]:
                st.markdown(f"&nbsp;&nbsp;{item['name']}: **{fmt_currency(item['amount'])}**")
        else:
            st.info("No income ledgers configured.")
        st.markdown(f"**Total Income: {fmt_currency(pl['total_income'])}**")

    with col_exp:
        st.markdown("### Expenses")
        if pl["expenses"]:
            for item in pl["expenses"]:
                st.markdown(f"&nbsp;&nbsp;{item['name']}: **{fmt_currency(item['amount'])}**")
        else:
            st.info("No expense ledgers configured.")
        st.markdown(f"**Total Expenses: {fmt_currency(pl['total_expense'])}**")

    st.divider()
    net = pl["net_profit"]
    if net >= 0:
        st.success(f"## Net Profit: {fmt_currency(net)}")
    else:
        st.error(f"## Net Loss: {fmt_currency(abs(net))}")

# ── Tab 3: Short Payments ─────────────────────────────────────────────────────
with tab3:
    st.subheader("Short Payment Ledger")
    st.caption("Clients who paid less than the invoice amount.")
    filter_s = st.selectbox("Status", ["All", "pending", "recovered", "written_off"], key="short_filter")
    shorts = get_short_payments(status=None if filter_s == "All" else filter_s)

    if shorts:
        rows = []
        for s in shorts:
            rows.append({
                "Date": fmt_date(s.get("date")),
                "Client": s.get("client_name", ""),
                "Month": fmt_month(s.get("billing_month", "")),
                "Invoiced": fmt_currency(s.get("invoiced_amount", 0)),
                "Received": fmt_currency(s.get("received_amount", 0)),
                "Short By": fmt_currency(s.get("difference", 0)),
                "Status": s.get("status", "").upper(),
                "Remarks": s.get("remarks", ""),
                "_id": s["id"],
            })
        df_s = pd.DataFrame(rows)
        st.dataframe(df_s.drop(columns=["_id"]), use_container_width=True, hide_index=True)

        total_short = sum(s.get("difference", 0) for s in shorts if s.get("status") == "pending")
        st.metric("Total Short Pending", fmt_currency(total_short))

        st.divider()
        st.markdown("**Update Status**")
        sel_short = st.selectbox("Select Record", [r["_id"] for r in rows], format_func=lambda x: next((r["Client"] + " | " + r["Month"] for r in rows if r["_id"] == x), x))
        new_status = st.selectbox("New Status", ["pending", "recovered", "written_off"])
        remarks = st.text_input("Remarks")
        if st.button("Update Short Payment Status"):
            update_short_excess_status(sel_short, new_status, remarks)
            st.success("Updated!")
            st.rerun()
    else:
        st.success("No short payments found.")

# ── Tab 4: Excess Payments ────────────────────────────────────────────────────
with tab4:
    st.subheader("Excess Payment Ledger")
    st.caption("Clients who paid more than the invoice amount. The excess is held as credit.")
    filter_e = st.selectbox("Status", ["All", "pending", "adjusted", "refunded"], key="excess_filter")
    excesses = get_excess_payments(status=None if filter_e == "All" else filter_e)

    if excesses:
        rows_e = []
        for e in excesses:
            rows_e.append({
                "Date": fmt_date(e.get("date")),
                "Client": e.get("client_name", ""),
                "Month": fmt_month(e.get("billing_month", "")),
                "Invoiced": fmt_currency(e.get("invoiced_amount", 0)),
                "Received": fmt_currency(e.get("received_amount", 0)),
                "Excess": fmt_currency(e.get("difference", 0)),
                "Status": e.get("status", "").upper(),
                "Remarks": e.get("remarks", ""),
                "_id": e["id"],
            })
        df_e = pd.DataFrame(rows_e)
        st.dataframe(df_e.drop(columns=["_id"]), use_container_width=True, hide_index=True)

        total_excess = sum(e.get("difference", 0) for e in excesses if e.get("status") == "pending")
        st.metric("Total Excess Held", fmt_currency(total_excess))

        st.divider()
        st.markdown("**Update Status**")
        sel_excess = st.selectbox("Select Record", [r["_id"] for r in rows_e], format_func=lambda x: next((r["Client"] + " | " + r["Month"] for r in rows_e if r["_id"] == x), x))
        new_status_e = st.selectbox("New Status", ["pending", "adjusted", "refunded"])
        remarks_e = st.text_input("Remarks", key="exc_rem")
        if st.button("Update Excess Payment Status"):
            update_short_excess_status(sel_excess, new_status_e, remarks_e)
            st.success("Updated!")
            st.rerun()
    else:
        st.info("No excess payments found.")

# ── Tab 5: Age-wise Outstanding ───────────────────────────────────────────────
with tab5:
    st.subheader("Age-wise Outstanding Statement")
    st.caption("Based on invoice due dates.")
    agewise = get_outstanding_agewise()
    if agewise:
        rows_a = []
        for a in agewise:
            rows_a.append({
                "Client": a["client_name"],
                "0–30 Days": fmt_currency(a["0_30"]),
                "31–60 Days": fmt_currency(a["31_60"]),
                "61–90 Days": fmt_currency(a["61_90"]),
                "90+ Days": fmt_currency(a["above_90"]),
                "Total": fmt_currency(a["total"]),
            })
        st.dataframe(pd.DataFrame(rows_a), use_container_width=True, hide_index=True)
        grand_total = sum(a["total"] for a in agewise)
        st.metric("Grand Total Outstanding", fmt_currency(grand_total))
    else:
        st.success("No outstanding invoices.")
