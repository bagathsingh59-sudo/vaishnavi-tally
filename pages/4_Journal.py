import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import streamlit as st
import pandas as pd
from datetime import datetime, date
from services.ledger_service import get_all_ledgers, get_ledger_balance
from services.voucher_service import create_journal, get_vouchers
from utils.formatting import fmt_currency, fmt_date, TALLY_CSS, fkey_bar, keyboard_shortcuts

st.markdown(TALLY_CSS, unsafe_allow_html=True)
st.markdown('<div class="tally-titlebar">📓 &nbsp;JOURNAL VOUCHER<span>F7 · Accounting Vouchers</span></div>',
            unsafe_allow_html=True)

st.markdown("""
<style>
.jrn-hdr { background:#003580; color:#FFD700; font-weight:700; font-size:11px;
    padding:4px 8px; display:grid; grid-template-columns:0.4fr 3fr 1.4fr 1.4fr 0.3fr; gap:4px; }
.by-pill { background:#FFD700; color:#002B5C; font-weight:800; padding:1px 8px;
    font-size:11px; border-radius:2px; }
.to-pill { background:#E8F4FD; color:#002B5C; font-weight:800; padding:1px 8px;
    font-size:11px; border-radius:2px; border:1px solid #003580; }
</style>
""", unsafe_allow_html=True)

tab_new, tab_list = st.tabs(["➕ New Journal Entry  (F7)", "📋 Journal List"])

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 1 — NEW JOURNAL
# ═══════════════════════════════════════════════════════════════════════════════
with tab_new:
    all_ledgers = get_all_ledgers()
    if not all_ledgers:
        st.warning("No ledgers found. Go to Ledgers (F9) and add them first.")
        fkey_bar(); st.stop()

    ledger_names = [l["name"] for l in all_ledgers]
    ledger_map   = {l["name"]: l["id"] for l in all_ledgers}

    # ── Voucher top bar ────────────────────────────────────────────────────────
    col_b, _, col_d = st.columns([1, 4, 1.5])
    col_b.markdown('<div style="background:#5B4FCF;color:#fff;font-weight:800;'
                   'padding:5px 16px;font-size:14px;display:inline-block;margin-top:4px">'
                   'JOURNAL</div>', unsafe_allow_html=True)
    jrn_date = col_d.date_input("Date", value=date.today(), label_visibility="collapsed")

    st.markdown("---")

    # ── Table header ──────────────────────────────────────────────────────────
    hc1, hc2, hc3, hc4, hc5 = st.columns([0.5, 3.5, 1.5, 1.5, 0.3])
    hc1.markdown("**Dr/Cr**")
    hc2.markdown("**Particulars**")
    hc3.markdown("**Debit (₹)**")
    hc4.markdown("**Credit (₹)**")

    # ── Journal rows ──────────────────────────────────────────────────────────
    if "jrn_rows" not in st.session_state:
        st.session_state.jrn_rows = [
            {"type": "By", "ledger": "", "debit": 0.0,   "credit": 0.0},
            {"type": "To", "ledger": "", "debit": 0.0,   "credit": 0.0},
        ]

    updated = []
    for i, row in enumerate(st.session_state.jrn_rows):
        c1, c2, c3, c4, c5 = st.columns([0.5, 3.5, 1.5, 1.5, 0.3])

        dr_cr = c1.selectbox("T", ["By", "To"],
                             index=0 if row["type"] == "By" else 1,
                             key=f"jt_{i}", label_visibility="collapsed")

        sel_l = c2.selectbox("Ledger", ["— Select —"] + ledger_names,
                             index=(["— Select —"] + ledger_names).index(row["ledger"])
                                   if row["ledger"] in ledger_names else 0,
                             key=f"jl_{i}", label_visibility="collapsed")

        # Show current balance under ledger
        if sel_l and sel_l != "— Select —":
            bal = get_ledger_balance(ledger_map[sel_l])
            c2.caption(f"Cur Bal: {fmt_currency(abs(bal))} {'Dr' if bal>=0 else 'Cr'}")

        # By = Debit side, To = Credit side (auto-lock the other)
        if dr_cr == "By":
            dr = c3.number_input("Dr", min_value=0.0, value=float(row["debit"]),
                                 step=100.0, key=f"jd_{i}", label_visibility="collapsed")
            c4.markdown('<div style="text-align:center;color:#AAA;padding:8px">—</div>',
                        unsafe_allow_html=True)
            cr = 0.0
        else:
            c3.markdown('<div style="text-align:center;color:#AAA;padding:8px">—</div>',
                        unsafe_allow_html=True)
            dr = 0.0
            cr = c4.number_input("Cr", min_value=0.0, value=float(row["credit"]),
                                 step=100.0, key=f"jc_{i}", label_visibility="collapsed")

        if c5.button("✕", key=f"jdel_{i}") and len(st.session_state.jrn_rows) > 2:
            st.session_state.jrn_rows.pop(i); st.rerun()

        updated.append({"type": dr_cr, "ledger": sel_l if sel_l != "— Select —" else "",
                         "debit": dr, "credit": cr})
    st.session_state.jrn_rows = updated

    if st.button("＋ Add Row", key="jrn_add_row"):
        st.session_state.jrn_rows.append({"type": "To", "ledger": "", "debit": 0.0, "credit": 0.0})
        st.rerun()

    st.markdown("---")

    # ── Totals ────────────────────────────────────────────────────────────────
    total_dr = sum(r["debit"]  for r in st.session_state.jrn_rows)
    total_cr = sum(r["credit"] for r in st.session_state.jrn_rows)
    diff     = total_dr - total_cr

    tc1, tc2, tc3 = st.columns([2, 2, 2])
    tc1.metric("Total Debit",  fmt_currency(total_dr))
    tc2.metric("Total Credit", fmt_currency(total_cr))
    if abs(diff) < 0.01 and total_dr > 0:
        tc3.success("✅ Balanced")
    else:
        tc3.error(f"Difference: {fmt_currency(abs(diff))}")

    narration = st.text_input("Narration", placeholder="e.g. EPF & ESIC for May 2025 — SM Brother Contractor")

    _, accept_col = st.columns([4, 1])
    accept = accept_col.button("✔ Accept  (Ctrl+A)", type="primary", use_container_width=True)

    if accept:
        if abs(diff) >= 0.01:
            st.error("Journal does not balance. Total Debit must equal Total Credit.")
        elif total_dr == 0:
            st.error("Amounts cannot be zero.")
        elif not narration.strip():
            st.error("Narration is required.")
        else:
            entries = [
                {"ledger_id": ledger_map[r["ledger"]], "ledger_name": r["ledger"],
                 "debit": r["debit"], "credit": r["credit"]}
                for r in st.session_state.jrn_rows if r["ledger"]
            ]
            try:
                vid = create_journal({
                    "date":      datetime.combine(jrn_date, datetime.min.time()),
                    "narration": narration,
                    "entries":   entries,
                })
                st.success(f"✅ Journal saved!")
                st.session_state.jrn_rows = [
                    {"type": "By", "ledger": "", "debit": 0.0, "credit": 0.0},
                    {"type": "To", "ledger": "", "debit": 0.0, "credit": 0.0},
                ]
                st.rerun()
            except ValueError as e:
                st.error(str(e))

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 2 — LIST
# ═══════════════════════════════════════════════════════════════════════════════
with tab_list:
    col_f1, col_f2 = st.columns(2)
    from_j = col_f1.date_input("From", value=None, key="jl_from")
    to_j   = col_f2.date_input("To",   value=None, key="jl_to")
    kw = {"voucher_type": "journal"}
    if from_j: kw["from_date"] = datetime.combine(from_j, datetime.min.time())
    if to_j:   kw["to_date"]   = datetime.combine(to_j,   datetime.max.time())

    vlist = get_vouchers(**kw)
    if not vlist:
        st.info("No journal entries found.")
    else:
        for v in vlist:
            total_dr = sum(e.get("debit", 0)  for e in v.get("entries", []))
            total_cr = sum(e.get("credit", 0) for e in v.get("entries", []))
            with st.expander(
                f"**{v.get('voucher_no','')}** &nbsp;|&nbsp; "
                f"{fmt_date(v.get('date'))} &nbsp;|&nbsp; "
                f"{v.get('narration','')[:60]}  "
                f"&nbsp;&nbsp; Dr: {fmt_currency(total_dr)}"
            ):
                rows = []
                for e in v.get("entries", []):
                    rows.append({
                        "Dr/Cr":     "By" if e.get("debit", 0) > 0 else "To",
                        "Ledger":    e.get("ledger_name", ""),
                        "Debit":     fmt_currency(e["debit"])  if e.get("debit")  else "—",
                        "Credit":    fmt_currency(e["credit"]) if e.get("credit") else "—",
                    })
                st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
                st.caption(f"DR: {fmt_currency(total_dr)}  |  CR: {fmt_currency(total_cr)}")

fkey_bar()
