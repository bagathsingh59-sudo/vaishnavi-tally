import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import streamlit as st
import pandas as pd
from datetime import datetime, date
from services.client_service import get_all_clients
from services.ledger_service import get_bank_ledgers, get_cash_ledgers, get_ledger_balance
from services.voucher_service import create_receipt, get_vouchers, update_receipt, delete_voucher
from services.counter_service import get_next_number
from utils.formatting import fmt_currency, fmt_date, TALLY_CSS, fkey_bar, keyboard_shortcuts

st.markdown(TALLY_CSS, unsafe_allow_html=True)

# ── Extra voucher CSS ──────────────────────────────────────────────────────────
st.markdown("""
<style>
.vch-bar {
    background:#002B5C; color:#fff; padding:6px 14px;
    display:flex; justify-content:space-between; align-items:center;
    border-bottom:2px solid #FFD700; margin-bottom:10px;
}
.vch-badge {
    background:#FFD700; color:#002B5C; font-weight:800;
    padding:3px 14px; font-size:13px; margin-right:10px;
}
.vch-no { color:#FFD700; font-size:12px; }
.vch-date-box {
    background:#FFFDE7; border:1px solid #FFD700;
    color:#002B5C; font-weight:700; padding:3px 12px; font-size:13px;
}
.tally-table-hdr {
    background:#003580; color:#FFD700; font-weight:700;
    padding:5px 10px; font-size:12px; margin:8px 0 2px 0;
    display:grid; grid-template-columns:3fr 1fr;
}
.acc-row {
    background:#FFFFFF; border:1px solid #CCCCCC;
    padding:8px 10px; margin:4px 0;
}
.bal-pill {
    background:#E8F4FD; border:1px solid #003580;
    padding:2px 10px; font-size:12px; font-weight:600; color:#002B5C;
}
</style>
""", unsafe_allow_html=True)

tab_new, tab_list = st.tabs(["➕ New Receipt  (F6)", "📋 Receipt List"])

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 1 — NEW RECEIPT
# ═══════════════════════════════════════════════════════════════════════════════
with tab_new:
    clients    = get_all_clients()
    bank_list  = get_bank_ledgers() + get_cash_ledgers()

    if not clients:
        st.warning("No clients found. Go to Clients (F2) → Add New Client first.")
        fkey_bar(); st.stop()
    if not bank_list:
        st.warning("No Bank/Cash ledger. Go to Ledgers (F9) → Add Ledger first.")
        fkey_bar(); st.stop()

    # ── Voucher top bar ────────────────────────────────────────────────────────
    col_badge, col_no, col_spacer, col_date = st.columns([1, 1, 4, 1.5])
    with col_badge:
        st.markdown('<div style="background:#FFD700;color:#002B5C;font-weight:800;'
                    'padding:5px 16px;font-size:14px;display:inline-block;'
                    'margin-top:4px">RECEIPT</div>', unsafe_allow_html=True)
    with col_no:
        st.markdown('<div style="color:#555;font-size:12px;margin-top:10px">'
                    'Accounting Voucher Creation</div>', unsafe_allow_html=True)
    with col_date:
        rcpt_date = st.date_input("Date", value=date.today(), label_visibility="collapsed")

    st.markdown("---")

    # ── Main Account (Bank/Cash) ───────────────────────────────────────────────
    st.markdown('<div style="color:#888;font-size:11px;font-weight:600;'
                'letter-spacing:0.5px">ACCOUNT</div>', unsafe_allow_html=True)
    col_acc, col_bal = st.columns([3, 1])
    with col_acc:
        bank_names = [l["name"] for l in bank_list]
        sel_bank_name = st.selectbox("Account", bank_names, label_visibility="collapsed")
        sel_bank = next(l for l in bank_list if l["name"] == sel_bank_name)
    with col_bal:
        bal = get_ledger_balance(sel_bank["id"])
        st.markdown(
            f'<div style="background:#E8F4FD;border:1px solid #003580;padding:8px 12px;'
            f'font-size:12px;font-weight:600;color:#002B5C;margin-top:2px">'
            f'Cur Bal: {fmt_currency(abs(bal))} {"Dr" if bal>=0 else "Cr"}</div>',
            unsafe_allow_html=True)

    st.markdown("---")

    # ── Particulars table header ───────────────────────────────────────────────
    h1, h2, h3 = st.columns([3.5, 1.5, 0.8])
    h1.markdown("**Particulars** *(Party / Client)*")
    h2.markdown("**Amount (₹)**")
    h3.markdown("**Mode**")

    # ── Particulars rows (multi-row support) ───────────────────────────────────
    client_names = [c["name"] for c in clients]
    client_map   = {c["name"]: c["id"] for c in clients}

    if "rcpt_rows" not in st.session_state:
        st.session_state.rcpt_rows = [{"party": client_names[0], "amount": 0.0}]

    updated_rows = []
    for i, row in enumerate(st.session_state.rcpt_rows):
        c1, c2, c3, c4 = st.columns([3.5, 1.5, 0.8, 0.3])
        party = c1.selectbox("Party", client_names,
                             index=client_names.index(row["party"]) if row["party"] in client_names else 0,
                             key=f"rcpt_party_{i}", label_visibility="collapsed")
        amt   = c2.number_input("Amt", min_value=0.0, value=float(row["amount"]),
                                step=100.0, key=f"rcpt_amt_{i}", label_visibility="collapsed")
        mode  = c3.selectbox("Mode", ["NEFT/IMPS", "UPI", "Cheque", "Cash"],
                             key=f"rcpt_mode_{i}", label_visibility="collapsed")
        if c4.button("✕", key=f"rcpt_del_{i}") and len(st.session_state.rcpt_rows) > 1:
            st.session_state.rcpt_rows.pop(i); st.rerun()
        updated_rows.append({"party": party, "amount": amt, "mode": mode})
    st.session_state.rcpt_rows = updated_rows

    if st.button("＋ Add Row", key="rcpt_add"):
        st.session_state.rcpt_rows.append({"party": client_names[0], "amount": 0.0}); st.rerun()

    st.markdown("---")

    # ── Reference + Narration ─────────────────────────────────────────────────
    r1, r2 = st.columns(2)
    reference = r1.text_input("Reference No. (UTR / Cheque)", placeholder="UTR / Cheque No")
    narration = r2.text_input("Narration", placeholder="Brief description")

    # ── Total + Accept ────────────────────────────────────────────────────────
    total = sum(r["amount"] for r in st.session_state.rcpt_rows)
    tc1, tc2 = st.columns([3, 1])
    with tc1:
        if total > 0:
            st.success(f"✅ Total Receipt Amount: **{fmt_currency(total)}**")
        else:
            st.info("Enter amount in the Particulars row above.")
    with tc2:
        accept = st.button("✔ Accept  (Ctrl+A)", type="primary", use_container_width=True)

    if accept:
        if total <= 0:
            st.error("Amount must be greater than zero.")
        else:
            saved, errors = 0, []
            for row in st.session_state.rcpt_rows:
                if row["amount"] <= 0:
                    continue
                try:
                    result = create_receipt({
                        "client_id":       client_map[row["party"]],
                        "date":            datetime.combine(rcpt_date, datetime.min.time()),
                        "amount":          row["amount"],
                        "payment_mode":    row["mode"].lower().replace("/","_"),
                        "reference_no":    reference,
                        "narration":       narration or f"Receipt from {row['party']}",
                        "bank_ledger_id":  sel_bank["id"],
                        "bank_ledger_name":sel_bank["name"],
                    })
                    saved += 1
                    info = result.get("short_excess_info", {})
                    if info:
                        st.warning(f"⚠️ {row['party']}: {info['type'].title()} of "
                                   f"{fmt_currency(info['amount'])} recorded.")
                except Exception as e:
                    errors.append(str(e))

            if saved:
                st.success(f"✅ Receipt saved!  {fmt_currency(total)}  →  {sel_bank_name}")
                st.session_state.rcpt_rows = [{"party": client_names[0], "amount": 0.0}]
                st.rerun()
            for e in errors:
                st.error(e)

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 2 — RECEIPT LIST
# ═══════════════════════════════════════════════════════════════════════════════
with tab_list:
    col_f1, col_f2, col_f3 = st.columns(3)
    client_filter = col_f1.selectbox("Client", ["All"] + [c["name"] for c in clients], key="rl_c")
    from_r = col_f2.date_input("From", value=None, key="rl_from")
    to_r   = col_f3.date_input("To",   value=None, key="rl_to")

    kw = {"voucher_type": "receipt"}
    if client_filter != "All":
        kw["client_id"] = next(c["id"] for c in clients if c["name"] == client_filter)
    if from_r: kw["from_date"] = datetime.combine(from_r, datetime.min.time())
    if to_r:   kw["to_date"]   = datetime.combine(to_r,   datetime.max.time())

    vlist = get_vouchers(**kw)
    if not vlist:
        st.info("No receipts found for the selected filters.")
    else:
        rows, grand = [], 0.0
        for v in vlist:
            amt = sum(e.get("debit", 0) for e in v.get("entries", []))
            grand += amt
            rows.append({
                "Date":       fmt_date(v.get("date")),
                "Voucher No": v.get("voucher_no", ""),
                "Party":      v.get("client_name", ""),
                "Mode":       v.get("payment_mode", ""),
                "Reference":  v.get("reference_no", ""),
                "Narration":  v.get("narration", ""),
                "Amount":     fmt_currency(amt),
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        st.markdown(f"**Total Receipts: {fmt_currency(grand)}** &nbsp;|&nbsp; {len(rows)} entries")

        # ── Manage (Edit / Delete) ────────────────────────────────────────────
        st.markdown("---")
        st.markdown('<div class="tally-section">✏️ MODIFY / DELETE ENTRY</div>',
                    unsafe_allow_html=True)

        vmap = {f"{v.get('voucher_no','')}  |  {fmt_date(v.get('date'))}  |  "
                f"{v.get('client_name','')}  |  "
                f"{fmt_currency(sum(e.get('debit',0) for e in v.get('entries',[])))}": v
                for v in vlist}
        sel_label = st.selectbox("Select a receipt to edit or delete", list(vmap.keys()), key="rl_sel")
        sel_v = vmap[sel_label]

        ec1, ec2 = st.columns(2)

        # ── Edit form ─────────────────────────────────────────────────────────
        with ec1:
            with st.expander("✏️ Edit this Receipt", expanded=False):
                cur_amt = sum(e.get("debit", 0) for e in sel_v.get("entries", []))
                cur_party = sel_v.get("client_name", clients[0]["name"])
                cur_bank = next((e["ledger_name"] for e in sel_v["entries"] if e.get("debit", 0) > 0),
                                bank_list[0]["name"])

                e_date = st.date_input("Date", value=sel_v.get("date").date()
                                       if hasattr(sel_v.get("date"), "date") else date.today(),
                                       key="re_date")
                e_party = st.selectbox("Party", [c["name"] for c in clients],
                                       index=[c["name"] for c in clients].index(cur_party)
                                       if cur_party in [c["name"] for c in clients] else 0,
                                       key="re_party")
                e_bank = st.selectbox("Received In", [l["name"] for l in bank_list],
                                      index=[l["name"] for l in bank_list].index(cur_bank)
                                      if cur_bank in [l["name"] for l in bank_list] else 0,
                                      key="re_bank")
                e_amt = st.number_input("Amount (₹)", min_value=0.0, value=float(cur_amt),
                                        step=100.0, key="re_amt")
                e_ref = st.text_input("Reference No.", value=sel_v.get("reference_no", ""), key="re_ref")
                e_narr = st.text_input("Narration", value=sel_v.get("narration", ""), key="re_narr")

                if st.button("💾 Update Receipt", type="primary", key="re_save"):
                    if e_amt <= 0:
                        st.error("Amount must be greater than zero.")
                    else:
                        bank_obj = next(l for l in bank_list if l["name"] == e_bank)
                        update_receipt(sel_v["id"], {
                            "client_id":        client_map[e_party],
                            "date":             datetime.combine(e_date, datetime.min.time()),
                            "amount":           e_amt,
                            "reference_no":     e_ref,
                            "narration":        e_narr,
                            "bank_ledger_id":   bank_obj["id"],
                            "bank_ledger_name": bank_obj["name"],
                        })
                        st.success("✅ Receipt updated!")
                        st.rerun()

        # ── Delete ────────────────────────────────────────────────────────────
        with ec2:
            with st.expander("🗑️ Delete this Receipt", expanded=False):
                st.warning(f"This will permanently delete **{sel_v.get('voucher_no','')}** "
                           f"({fmt_currency(sum(e.get('debit',0) for e in sel_v.get('entries',[])))}).")
                confirm = st.checkbox("Yes, I want to delete this entry", key="re_confirm")
                if st.button("🗑️ Delete Permanently", key="re_del", disabled=not confirm):
                    delete_voucher(sel_v["id"])
                    st.success("🗑️ Receipt deleted.")
                    st.rerun()

fkey_bar()
