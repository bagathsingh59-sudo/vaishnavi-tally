import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import streamlit as st
import pandas as pd
from datetime import datetime, date
from services.ledger_service import get_all_ledgers, create_ledger, get_ledger_transactions
from utils.formatting import fmt_currency, fmt_date, TALLY_CSS

st.set_page_config(page_title="Ledgers — Vaishnavi", layout="wide")
st.markdown(TALLY_CSS, unsafe_allow_html=True)
st.markdown('<div class="tally-header">📒 Ledger Management</div>', unsafe_allow_html=True)

GROUPS = {
    "bank": "Bank Account",
    "cash": "Cash",
    "epf_payable": "EPF Payable",
    "esic_payable": "ESIC Payable",
    "income": "Income",
    "expense": "Expense / Overhead",
    "sundry_debtor": "Sundry Debtor",
    "sundry_creditor": "Sundry Creditor",
}

tab1, tab2, tab3 = st.tabs(["📒 View Ledger", "📋 All Ledgers", "➕ Add Ledger"])

# ── Tab 1: View Ledger with transactions ──────────────────────────────────────
with tab1:
    all_ledgers = get_all_ledgers()
    if not all_ledgers:
        st.info("No ledgers found. Add ledgers in the 'Add Ledger' tab.")
    else:
        ledger_names = [l["name"] for l in all_ledgers]
        ledger_map = {l["name"]: l["id"] for l in all_ledgers}
        ledger_group_map = {l["name"]: l.get("group", "") for l in all_ledgers}

        col_sel, col_grp = st.columns(2)
        with col_sel:
            sel_name = st.selectbox("Select Ledger", ledger_names)
        sel_id = ledger_map[sel_name]
        sel_group = ledger_group_map[sel_name]

        col_from, col_to = st.columns(2)
        from_d = col_from.date_input("From Date", value=None)
        to_d = col_to.date_input("To Date", value=None)

        fd = datetime.combine(from_d, datetime.min.time()) if from_d else None
        td = datetime.combine(to_d, datetime.max.time()) if to_d else None

        txns, closing = get_ledger_transactions(sel_id, fd, td)

        # Get opening balance
        sel_ledger_data = next((l for l in all_ledgers if l["id"] == sel_id), {})
        ob = sel_ledger_data.get("opening_balance", 0)
        ob_type = sel_ledger_data.get("opening_balance_type", "dr")

        st.markdown(
            f'<div class="balance-card">'
            f'<b>{sel_name}</b> &nbsp;|&nbsp; Group: <i>{GROUPS.get(sel_group, sel_group)}</i> &nbsp;|&nbsp; '
            f'Opening Balance: <b>{fmt_currency(ob)} {ob_type.upper()}</b>'
            f'</div>',
            unsafe_allow_html=True,
        )

        if txns:
            rows = []
            for t in txns:
                rows.append({
                    "Date": fmt_date(t["date"]),
                    "Voucher No": t["voucher_no"],
                    "Type": t["voucher_type"].title(),
                    "Narration": t["narration"],
                    "Debit (₹)": f"{t['debit']:,.2f}" if t["debit"] else "—",
                    "Credit (₹)": f"{t['credit']:,.2f}" if t["credit"] else "—",
                    "Balance": f"{t['balance']:,.2f} {t['balance_type']}",
                })
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
            col_cl1, col_cl2 = st.columns(2)
            col_cl1.metric(
                "Closing Balance",
                fmt_currency(abs(closing)),
                delta="Dr (Asset/Receivable)" if closing >= 0 else "Cr (Liability/Payable)",
            )
        else:
            st.info("No transactions in this period.")

# ── Tab 2: All Ledgers summary ────────────────────────────────────────────────
with tab2:
    filter_grp = st.selectbox("Filter by Group", ["All"] + list(GROUPS.keys()),
                               format_func=lambda x: "All" if x == "All" else GROUPS.get(x, x))
    ledgers = get_all_ledgers(group=None if filter_grp == "All" else filter_grp)
    if ledgers:
        rows = []
        for l in ledgers:
            from services.ledger_service import get_ledger_balance
            bal = get_ledger_balance(l["id"])
            rows.append({
                "Ledger Name": l["name"],
                "Group": GROUPS.get(l.get("group", ""), l.get("group", "")),
                "Opening Balance": fmt_currency(l.get("opening_balance", 0)),
                "O/B Type": l.get("opening_balance_type", "dr").upper(),
                "Current Balance": fmt_currency(abs(bal)),
                "Balance Type": "Dr" if bal >= 0 else "Cr",
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    else:
        st.info("No ledgers found.")

# ── Tab 3: Add Ledger ─────────────────────────────────────────────────────────
with tab3:
    st.subheader("Create New Ledger")
    with st.form("add_ledger_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            l_name = st.text_input("Ledger Name *")
            l_group = st.selectbox("Group *", list(GROUPS.keys()), format_func=lambda x: GROUPS[x])
            account_no = st.text_input("Account No (optional, for bank accounts)")
        with col2:
            l_ob = st.number_input("Opening Balance (₹)", min_value=0.0, value=0.0, step=100.0)
            l_ob_type = st.selectbox("Opening Balance Type", ["Dr", "Cr"])

        if st.form_submit_button("💾 Save Ledger", type="primary"):
            if not l_name.strip():
                st.error("Ledger name is required.")
            else:
                lid = create_ledger({
                    "name": l_name,
                    "group": l_group,
                    "opening_balance": l_ob,
                    "opening_balance_type": l_ob_type.lower(),
                    "account_no": account_no,
                })
                st.success(f"✅ Ledger '{l_name}' created!")
