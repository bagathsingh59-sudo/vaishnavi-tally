import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import streamlit as st
import pandas as pd
from datetime import datetime, date
from services.client_service import get_all_clients
from services.ledger_service import get_bank_ledgers, get_cash_ledgers
from services.invoice_service import get_unpaid_invoices_for_client
from services.voucher_service import create_receipt, get_vouchers
from utils.formatting import fmt_currency, fmt_date, fmt_month, TALLY_CSS, fkey_bar, keyboard_shortcuts

st.set_page_config(page_title="Receipts — Vaishnavi", layout="wide")
st.markdown(TALLY_CSS, unsafe_allow_html=True)
keyboard_shortcuts()
st.markdown('<div class="tally-titlebar">💰 &nbsp;RECEIPT VOUCHER<span>F6 · Accounting Vouchers</span></div>', unsafe_allow_html=True)

tab1, tab2 = st.tabs(["➕ New Receipt", "📋 Receipt List"])

# ── Tab 1: New Receipt ─────────────────────────────────────────────────────────
with tab1:
    clients = get_all_clients()
    bank_ledgers = get_bank_ledgers()
    cash_ledgers = get_cash_ledgers()
    all_cash_bank = bank_ledgers + cash_ledgers

    if not clients:
        st.warning("No clients found. Please add clients first.")
        st.stop()
    if not all_cash_bank:
        st.warning("No Bank or Cash ledgers found. Please set up ledgers first.")
        st.stop()

    st.subheader("Record Payment Received from Client")

    col1, col2 = st.columns(2)
    with col1:
        sel_client = st.selectbox("Client *", [c["name"] for c in clients])
        client_id = next(c["id"] for c in clients if c["name"] == sel_client)

    # Load unpaid invoices for selected client
    unpaid_inv = get_unpaid_invoices_for_client(client_id)
    inv_options = ["— No specific invoice —"] + [
        f"{inv.get('invoice_no', '')} | {fmt_month(inv.get('billing_month', ''))} | Due: {fmt_currency(inv.get('balance_due', 0))}"
        for inv in unpaid_inv
    ]
    inv_id_map = {
        f"{inv.get('invoice_no', '')} | {fmt_month(inv.get('billing_month', ''))} | Due: {fmt_currency(inv.get('balance_due', 0))}": inv["id"]
        for inv in unpaid_inv
    }

    with col1:
        sel_inv_label = st.selectbox("Link to Invoice (optional)", inv_options)
        sel_inv_id = inv_id_map.get(sel_inv_label)

        if sel_inv_id and sel_inv_label != inv_options[0]:
            inv_data = next((i for i in unpaid_inv if i["id"] == sel_inv_id), None)
            if inv_data:
                st.info(
                    f"Invoice: {inv_data.get('invoice_no')} | "
                    f"Month: {fmt_month(inv_data.get('billing_month', ''))} | "
                    f"Balance Due: **{fmt_currency(inv_data.get('balance_due', 0))}**"
                )
    with col2:
        rcpt_date = st.date_input("Receipt Date *", value=date.today())
        payment_mode = st.selectbox("Payment Mode", ["Bank Transfer (NEFT/IMPS)", "UPI", "Cheque", "Cash"])
        cash_bank_names = [l["name"] for l in all_cash_bank]
        sel_ledger_name = st.selectbox("Received in *", cash_bank_names)
        sel_ledger = next(l for l in all_cash_bank if l["name"] == sel_ledger_name)

    with st.form("receipt_form", clear_on_submit=True):
        fc1, fc2 = st.columns(2)
        amount = fc1.number_input("Amount Received (₹) *", min_value=1.0, value=0.0, step=100.0)
        reference = fc2.text_input("Reference No (UTR / Cheque No)")
        narration = st.text_area(
            "Narration",
            value=f"Receipt from {sel_client}" + (f" for {fmt_month(next((i for i in unpaid_inv if i.get('id') == sel_inv_id), {}).get('billing_month', ''))}" if sel_inv_id else ""),
            height=60,
        )

        if sel_inv_id:
            inv_bal = next((i.get("balance_due", 0) for i in unpaid_inv if i["id"] == sel_inv_id), 0)
            if amount > 0:
                diff = amount - inv_bal
                if abs(diff) < 0.01:
                    st.success(f"✅ Exact payment — Invoice will be marked PAID")
                elif diff < 0:
                    st.warning(f"⚠️ Short by {fmt_currency(abs(diff))} — will be recorded in Short Payment Ledger")
                else:
                    st.info(f"ℹ️ Excess by {fmt_currency(diff)} — will be recorded in Excess Payment Ledger")

        submitted = st.form_submit_button("💾 Save Receipt", type="primary")
        if submitted:
            if amount <= 0:
                st.error("Amount must be greater than zero.")
            else:
                mode_clean = payment_mode.split("(")[0].strip().lower().replace(" ", "_")
                result = create_receipt({
                    "client_id": client_id,
                    "invoice_id": sel_inv_id,
                    "date": datetime.combine(rcpt_date, datetime.min.time()),
                    "amount": amount,
                    "payment_mode": mode_clean,
                    "reference_no": reference,
                    "narration": narration,
                    "bank_ledger_id": sel_ledger["id"],
                    "bank_ledger_name": sel_ledger["name"],
                })
                msg = f"✅ Receipt saved! Voucher: **{result.get('voucher_id', '')}**"
                info = result.get("short_excess_info", {})
                if info:
                    msg += f"  |  ⚠️ {info['type'].title()} of {fmt_currency(info['amount'])} recorded."
                st.success(msg)

# ── Tab 2: Receipt List ────────────────────────────────────────────────────────
with tab2:
    col_f1, col_f2, col_f3 = st.columns(3)
    filter_client_r = col_f1.selectbox("Filter Client", ["All"] + [c["name"] for c in clients], key="r_client")
    from_date_r = col_f2.date_input("From", value=None, key="r_from")
    to_date_r = col_f3.date_input("To", value=None, key="r_to")

    kwargs_r = {"voucher_type": "receipt"}
    if filter_client_r != "All":
        kwargs_r["client_id"] = next(c["id"] for c in clients if c["name"] == filter_client_r)
    if from_date_r:
        kwargs_r["from_date"] = datetime.combine(from_date_r, datetime.min.time())
    if to_date_r:
        kwargs_r["to_date"] = datetime.combine(to_date_r, datetime.max.time())

    vouchers = get_vouchers(**kwargs_r)
    if not vouchers:
        st.info("No receipts found.")
    else:
        rows = []
        for v in vouchers:
            dr_total = sum(e.get("debit", 0) for e in v.get("entries", []))
            rows.append({
                "Date": fmt_date(v.get("date")),
                "Voucher No": v.get("voucher_no", ""),
                "Client": v.get("client_name", ""),
                "Amount": fmt_currency(dr_total),
                "Mode": v.get("payment_mode", ""),
                "Reference": v.get("reference_no", ""),
                "Narration": v.get("narration", ""),
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        total_rcpt = sum(
            sum(e.get("debit", 0) for e in v.get("entries", [])) for v in vouchers
        )
        st.markdown(f"**Total Receipts: {fmt_currency(total_rcpt)}**")

fkey_bar()
