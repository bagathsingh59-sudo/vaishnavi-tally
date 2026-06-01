import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import streamlit as st
import pandas as pd
from datetime import datetime, date
from services.ledger_service import get_bank_ledgers, get_cash_ledgers, get_all_ledgers
from services.voucher_service import create_payment, get_vouchers
from utils.formatting import fmt_currency, fmt_date, TALLY_CSS

st.set_page_config(page_title="Payments — Vaishnavi", layout="wide")
st.markdown(TALLY_CSS, unsafe_allow_html=True)
st.markdown('<div class="tally-header">💸 Payment Vouchers</div>', unsafe_allow_html=True)

tab1, tab2 = st.tabs(["➕ New Payment", "📋 Payment List"])

with tab1:
    st.subheader("Record Payment Made")
    bank_ledgers = get_bank_ledgers() + get_cash_ledgers()
    expense_ledgers = get_all_ledgers("expense") + get_all_ledgers("epf_payable") + get_all_ledgers("esic_payable")

    if not bank_ledgers:
        st.warning("No Bank/Cash ledgers. Please set up ledgers first.")
        st.stop()

    col1, col2 = st.columns(2)
    with col1:
        pay_date = st.date_input("Payment Date *", value=date.today())
        pay_mode = st.selectbox("Payment Mode", ["Bank Transfer (NEFT/IMPS)", "UPI", "Cheque", "Cash"])
        bank_names = [l["name"] for l in bank_ledgers]
        sel_bank_name = st.selectbox("Pay From *", bank_names)
        sel_bank = next(l for l in bank_ledgers if l["name"] == sel_bank_name)

    with col2:
        exp_options = [l["name"] for l in expense_ledgers] if expense_ledgers else []
        if exp_options:
            sel_exp_name = st.selectbox("Pay To (Expense / Ledger) *", exp_options)
            sel_exp = next(l for l in expense_ledgers if l["name"] == sel_exp_name)
        else:
            st.warning("No expense/payable ledgers found. Please add them in Ledger Setup.")

    with st.form("payment_form", clear_on_submit=True):
        fc1, fc2 = st.columns(2)
        amount = fc1.number_input("Amount (₹) *", min_value=1.0, value=0.0, step=100.0)
        reference = fc2.text_input("Reference No (UTR / Cheque No)")
        narration = st.text_area("Narration / Purpose", height=60)

        submitted = st.form_submit_button("💾 Save Payment", type="primary")
        if submitted:
            if amount <= 0:
                st.error("Amount must be greater than zero.")
            elif not exp_options:
                st.error("Set up expense ledgers first.")
            else:
                mode_clean = pay_mode.split("(")[0].strip().lower().replace(" ", "_")
                vid = create_payment({
                    "bank_ledger_id": sel_bank["id"],
                    "bank_ledger_name": sel_bank["name"],
                    "expense_ledger_id": sel_exp["id"],
                    "expense_ledger_name": sel_exp["name"],
                    "amount": amount,
                    "date": datetime.combine(pay_date, datetime.min.time()),
                    "payment_mode": mode_clean,
                    "reference_no": reference,
                    "narration": narration,
                })
                st.success(f"✅ Payment saved! Voucher: **{vid}**")

with tab2:
    col_f1, col_f2 = st.columns(2)
    from_date_p = col_f1.date_input("From", value=None, key="p_from")
    to_date_p = col_f2.date_input("To", value=None, key="p_to")

    kwargs_p = {"voucher_type": "payment"}
    if from_date_p:
        kwargs_p["from_date"] = datetime.combine(from_date_p, datetime.min.time())
    if to_date_p:
        kwargs_p["to_date"] = datetime.combine(to_date_p, datetime.max.time())

    vouchers = get_vouchers(**kwargs_p)
    if not vouchers:
        st.info("No payments found.")
    else:
        rows = []
        for v in vouchers:
            cr_total = sum(e.get("credit", 0) for e in v.get("entries", []))
            rows.append({
                "Date": fmt_date(v.get("date")),
                "Voucher No": v.get("voucher_no", ""),
                "Amount": fmt_currency(cr_total),
                "Mode": v.get("payment_mode", ""),
                "Reference": v.get("reference_no", ""),
                "Narration": v.get("narration", ""),
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        total_pay = sum(
            sum(e.get("credit", 0) for e in v.get("entries", [])) for v in vouchers
        )
        st.markdown(f"**Total Payments: {fmt_currency(total_pay)}**")
