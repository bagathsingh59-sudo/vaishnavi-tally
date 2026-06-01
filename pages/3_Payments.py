import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import streamlit as st
import pandas as pd
from datetime import datetime, date
from services.ledger_service import get_bank_ledgers, get_cash_ledgers, get_all_ledgers, get_ledger_balance
from services.voucher_service import create_payment, get_vouchers, update_payment, delete_voucher
from utils.formatting import fmt_currency, fmt_date, TALLY_CSS, fkey_bar, keyboard_shortcuts

st.markdown(TALLY_CSS, unsafe_allow_html=True)

st.markdown("""
<style>
.vch-badge-pay { background:#4472C4; color:#fff; font-weight:800;
    padding:5px 16px; font-size:14px; display:inline-block; margin-top:4px; }
</style>
""", unsafe_allow_html=True)

tab_new, tab_list = st.tabs(["➕ New Payment  (F5)", "📋 Payment List"])

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 1 — NEW PAYMENT
# ═══════════════════════════════════════════════════════════════════════════════
with tab_new:
    bank_list = get_bank_ledgers() + get_cash_ledgers()
    exp_list  = (get_all_ledgers("expense") + get_all_ledgers("epf_payable")
                 + get_all_ledgers("esic_payable") + get_all_ledgers("sundry_creditor"))

    if not bank_list:
        st.warning("No Bank/Cash ledger. Go to Ledgers (F9) → Add Ledger first.")
        fkey_bar(); st.stop()

    # ── Voucher top bar ────────────────────────────────────────────────────────
    col_b, _, col_d = st.columns([1, 4, 1.5])
    col_b.markdown('<div class="vch-badge-pay">PAYMENT</div>', unsafe_allow_html=True)
    pay_date = col_d.date_input("Date", value=date.today(), label_visibility="collapsed")

    st.markdown("---")

    # ── Main Account (Bank/Cash — paying from) ─────────────────────────────────
    st.markdown('<div style="color:#888;font-size:11px;font-weight:600">ACCOUNT  *(Paying From)*</div>',
                unsafe_allow_html=True)
    col_acc, col_bal = st.columns([3, 1])
    with col_acc:
        bank_names    = [l["name"] for l in bank_list]
        sel_bank_name = st.selectbox("Account", bank_names, label_visibility="collapsed")
        sel_bank      = next(l for l in bank_list if l["name"] == sel_bank_name)
    with col_bal:
        bal = get_ledger_balance(sel_bank["id"])
        st.markdown(f'<div style="background:#E8F4FD;border:1px solid #003580;padding:8px 12px;'
                    f'font-size:12px;font-weight:600;color:#002B5C;margin-top:2px">'
                    f'Cur Bal: {fmt_currency(abs(bal))} {"Dr" if bal>=0 else "Cr"}</div>',
                    unsafe_allow_html=True)

    st.markdown("---")

    # ── Particulars ────────────────────────────────────────────────────────────
    h1, h2 = st.columns([4, 1.5])
    h1.markdown("**Particulars** *(Expense / Payable Ledger)*")
    h2.markdown("**Amount (₹)**")

    if not exp_list:
        st.warning("No expense/payable ledgers found. Go to Ledgers (F9) and add them.")
    else:
        exp_names = [l["name"] for l in exp_list]
        exp_map   = {l["name"]: l["id"] for l in exp_list}

        if "pay_rows" not in st.session_state:
            st.session_state.pay_rows = [{"ledger": exp_names[0], "amount": 0.0}]

        updated = []
        for i, row in enumerate(st.session_state.pay_rows):
            c1, c2, c3 = st.columns([4, 1.5, 0.3])
            lname = c1.selectbox("Ledger", exp_names,
                                 index=exp_names.index(row["ledger"]) if row["ledger"] in exp_names else 0,
                                 key=f"pay_l_{i}", label_visibility="collapsed")
            amt   = c2.number_input("Amt", min_value=0.0, value=float(row["amount"]),
                                    step=100.0, key=f"pay_a_{i}", label_visibility="collapsed")
            if c3.button("✕", key=f"pay_d_{i}") and len(st.session_state.pay_rows) > 1:
                st.session_state.pay_rows.pop(i); st.rerun()
            updated.append({"ledger": lname, "amount": amt})
        st.session_state.pay_rows = updated

        if st.button("＋ Add Row", key="pay_add"):
            st.session_state.pay_rows.append({"ledger": exp_names[0], "amount": 0.0}); st.rerun()

    st.markdown("---")

    r1, r2 = st.columns(2)
    reference = r1.text_input("Reference No. (UTR / Cheque)", placeholder="UTR / Cheque No")
    narration = r2.text_input("Narration", placeholder="Brief description")

    total = sum(r["amount"] for r in st.session_state.get("pay_rows", []))
    tc1, tc2 = st.columns([3, 1])
    with tc1:
        if total > 0:
            st.success(f"✅ Total Payment: **{fmt_currency(total)}**")
        else:
            st.info("Enter amount in the Particulars row above.")
    with tc2:
        accept = st.button("✔ Accept  (Ctrl+A)", type="primary", use_container_width=True)

    if accept and exp_list:
        if total <= 0:
            st.error("Amount must be greater than zero.")
        else:
            saved = 0
            for row in st.session_state.pay_rows:
                if row["amount"] <= 0:
                    continue
                try:
                    create_payment({
                        "bank_ledger_id":      sel_bank["id"],
                        "bank_ledger_name":    sel_bank["name"],
                        "expense_ledger_id":   exp_map[row["ledger"]],
                        "expense_ledger_name": row["ledger"],
                        "amount":              row["amount"],
                        "date":                datetime.combine(pay_date, datetime.min.time()),
                        "payment_mode":        "bank_transfer",
                        "reference_no":        reference,
                        "narration":           narration or f"Payment: {row['ledger']}",
                    })
                    saved += 1
                except Exception as e:
                    st.error(str(e))

            if saved:
                st.success(f"✅ Payment saved!  {fmt_currency(total)}  from  {sel_bank_name}")
                st.session_state.pay_rows = [{"ledger": exp_names[0] if exp_list else "", "amount": 0.0}]
                st.rerun()

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 2 — LIST
# ═══════════════════════════════════════════════════════════════════════════════
with tab_list:
    col_f1, col_f2 = st.columns(2)
    from_p = col_f1.date_input("From", value=None, key="pl_from")
    to_p   = col_f2.date_input("To",   value=None, key="pl_to")
    kw = {"voucher_type": "payment"}
    if from_p: kw["from_date"] = datetime.combine(from_p, datetime.min.time())
    if to_p:   kw["to_date"]   = datetime.combine(to_p,   datetime.max.time())

    vlist = get_vouchers(**kw)
    if not vlist:
        st.info("No payments found.")
    else:
        rows, grand = [], 0.0
        for v in vlist:
            amt = sum(e.get("credit", 0) for e in v.get("entries", []))
            grand += amt
            rows.append({
                "Date": fmt_date(v.get("date")), "Voucher No": v.get("voucher_no", ""),
                "Narration": v.get("narration", ""), "Reference": v.get("reference_no", ""),
                "Amount": fmt_currency(amt),
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        st.markdown(f"**Total Payments: {fmt_currency(grand)}**")

        # ── Manage (Edit / Delete) ────────────────────────────────────────────
        st.markdown("---")
        st.markdown('<div class="tally-section">✏️ MODIFY / DELETE ENTRY</div>',
                    unsafe_allow_html=True)

        all_banks = get_bank_ledgers() + get_cash_ledgers()
        all_exp   = (get_all_ledgers("expense") + get_all_ledgers("epf_payable")
                     + get_all_ledgers("esic_payable") + get_all_ledgers("sundry_creditor"))
        bank_names = [l["name"] for l in all_banks]
        exp_names  = [l["name"] for l in all_exp]
        exp_map    = {l["name"]: l["id"] for l in all_exp}
        bank_map   = {l["name"]: l["id"] for l in all_banks}

        vmap = {f"{v.get('voucher_no','')}  |  {fmt_date(v.get('date'))}  |  "
                f"{v.get('narration','')[:30]}  |  "
                f"{fmt_currency(sum(e.get('credit',0) for e in v.get('entries',[])))}": v
                for v in vlist}
        sel_label = st.selectbox("Select a payment to edit or delete", list(vmap.keys()), key="pl_sel")
        sel_v = vmap[sel_label]

        ec1, ec2 = st.columns(2)
        with ec1:
            with st.expander("✏️ Edit this Payment", expanded=False):
                cur_amt  = sum(e.get("credit", 0) for e in sel_v.get("entries", []))
                cur_exp  = next((e["ledger_name"] for e in sel_v["entries"] if e.get("debit", 0) > 0),
                                exp_names[0] if exp_names else "")
                cur_bank = next((e["ledger_name"] for e in sel_v["entries"] if e.get("credit", 0) > 0),
                                bank_names[0] if bank_names else "")

                e_date = st.date_input("Date", value=sel_v.get("date").date()
                                       if hasattr(sel_v.get("date"), "date") else date.today(),
                                       key="pe_date")
                e_exp  = st.selectbox("Pay To (Expense / Payable)", exp_names,
                                      index=exp_names.index(cur_exp) if cur_exp in exp_names else 0,
                                      key="pe_exp") if exp_names else None
                e_bank = st.selectbox("Pay From (Bank / Cash)", bank_names,
                                      index=bank_names.index(cur_bank) if cur_bank in bank_names else 0,
                                      key="pe_bank")
                e_amt  = st.number_input("Amount (₹)", min_value=0.0, value=float(cur_amt),
                                         step=100.0, key="pe_amt")
                e_ref  = st.text_input("Reference No.", value=sel_v.get("reference_no", ""), key="pe_ref")
                e_narr = st.text_input("Narration", value=sel_v.get("narration", ""), key="pe_narr")

                if st.button("💾 Update Payment", type="primary", key="pe_save"):
                    if not e_exp:
                        st.error("No expense ledger available.")
                    elif e_amt <= 0:
                        st.error("Amount must be greater than zero.")
                    else:
                        update_payment(sel_v["id"], {
                            "expense_ledger_id":   exp_map[e_exp],
                            "expense_ledger_name": e_exp,
                            "bank_ledger_id":      bank_map[e_bank],
                            "bank_ledger_name":    e_bank,
                            "amount":              e_amt,
                            "date":                datetime.combine(e_date, datetime.min.time()),
                            "reference_no":        e_ref,
                            "narration":           e_narr,
                        })
                        st.success("✅ Payment updated!")
                        st.rerun()

        with ec2:
            with st.expander("🗑️ Delete this Payment", expanded=False):
                st.warning(f"This will permanently delete **{sel_v.get('voucher_no','')}** "
                           f"({fmt_currency(sum(e.get('credit',0) for e in sel_v.get('entries',[])))}).")
                confirm = st.checkbox("Yes, I want to delete this entry", key="pe_confirm")
                if st.button("🗑️ Delete Permanently", key="pe_del", disabled=not confirm):
                    delete_voucher(sel_v["id"])
                    st.success("🗑️ Payment deleted.")
                    st.rerun()

fkey_bar()
