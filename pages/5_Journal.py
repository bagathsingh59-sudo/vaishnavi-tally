import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import streamlit as st
import pandas as pd
from datetime import datetime, date
from services.ledger_service import get_all_ledgers
from services.voucher_service import create_journal, get_vouchers
from utils.formatting import fmt_currency, fmt_date, TALLY_CSS

st.set_page_config(page_title="Journal — Vaishnavi", layout="wide")
st.markdown(TALLY_CSS, unsafe_allow_html=True)
st.markdown('<div class="tally-header">📓 Journal Voucher</div>', unsafe_allow_html=True)

tab1, tab2 = st.tabs(["➕ New Journal Entry", "📋 Journal List"])

with tab1:
    st.subheader("Manual Journal Entry (Double-Entry)")
    st.caption("Total Debit must equal Total Credit before saving.")

    all_ledgers = get_all_ledgers()
    if not all_ledgers:
        st.warning("No ledgers found. Please set up ledgers first.")
        st.stop()

    ledger_names = [l["name"] for l in all_ledgers]
    ledger_map = {l["name"]: l["id"] for l in all_ledgers}

    jrn_date = st.date_input("Journal Date *", value=date.today())
    narration = st.text_area("Narration *", height=60)

    st.markdown("**Journal Entries**")
    st.caption("Add rows below. Each row is one ledger line.")

    if "jrn_rows" not in st.session_state:
        st.session_state.jrn_rows = [
            {"ledger": "", "debit": 0.0, "credit": 0.0},
            {"ledger": "", "debit": 0.0, "credit": 0.0},
        ]

    cols_hdr = st.columns([3, 2, 2, 1])
    cols_hdr[0].markdown("**Ledger**")
    cols_hdr[1].markdown("**Debit (₹)**")
    cols_hdr[2].markdown("**Credit (₹)**")

    updated_rows = []
    for i, row in enumerate(st.session_state.jrn_rows):
        c1, c2, c3, c4 = st.columns([3, 2, 2, 1])
        with c1:
            sel_ledger = st.selectbox(
                f"Ledger {i+1}",
                ["— Select —"] + ledger_names,
                index=(["— Select —"] + ledger_names).index(row["ledger"]) if row["ledger"] in ledger_names else 0,
                key=f"jrn_l_{i}",
                label_visibility="collapsed",
            )
        with c2:
            dr = st.number_input("Dr", min_value=0.0, value=float(row["debit"]), step=100.0, key=f"jrn_d_{i}", label_visibility="collapsed")
        with c3:
            cr = st.number_input("Cr", min_value=0.0, value=float(row["credit"]), step=100.0, key=f"jrn_c_{i}", label_visibility="collapsed")
        with c4:
            if st.button("🗑", key=f"del_{i}") and len(st.session_state.jrn_rows) > 2:
                st.session_state.jrn_rows.pop(i)
                st.rerun()
        updated_rows.append({"ledger": sel_ledger, "debit": dr, "credit": cr})
    st.session_state.jrn_rows = updated_rows

    col_add, col_totals = st.columns([1, 2])
    with col_add:
        if st.button("➕ Add Row"):
            st.session_state.jrn_rows.append({"ledger": "", "debit": 0.0, "credit": 0.0})
            st.rerun()

    total_dr = sum(r["debit"] for r in st.session_state.jrn_rows)
    total_cr = sum(r["credit"] for r in st.session_state.jrn_rows)
    with col_totals:
        if abs(total_dr - total_cr) < 0.01 and total_dr > 0:
            st.success(f"✅ Balanced — Dr: {fmt_currency(total_dr)} = Cr: {fmt_currency(total_cr)}")
        else:
            diff = total_dr - total_cr
            st.warning(f"⚠️ Difference: {fmt_currency(abs(diff))} — {'Add more Credit' if diff > 0 else 'Add more Debit'}")

    if st.button("💾 Save Journal Entry", type="primary"):
        if not narration.strip():
            st.error("Narration is required.")
        elif abs(total_dr - total_cr) >= 0.01:
            st.error("Journal does not balance. Please fix before saving.")
        elif total_dr == 0:
            st.error("Amounts cannot be zero.")
        else:
            entries = []
            for r in st.session_state.jrn_rows:
                if r["ledger"] and r["ledger"] != "— Select —":
                    entries.append({
                        "ledger_id": ledger_map[r["ledger"]],
                        "ledger_name": r["ledger"],
                        "debit": r["debit"],
                        "credit": r["credit"],
                    })
            try:
                vid = create_journal({
                    "date": datetime.combine(jrn_date, datetime.min.time()),
                    "narration": narration,
                    "entries": entries,
                })
                st.success(f"✅ Journal saved! Voucher: **{vid}**")
                st.session_state.jrn_rows = [
                    {"ledger": "", "debit": 0.0, "credit": 0.0},
                    {"ledger": "", "debit": 0.0, "credit": 0.0},
                ]
                st.rerun()
            except ValueError as e:
                st.error(str(e))

with tab2:
    col_f1, col_f2 = st.columns(2)
    from_j = col_f1.date_input("From", value=None, key="j_from")
    to_j = col_f2.date_input("To", value=None, key="j_to")

    kwargs_j = {"voucher_type": "journal"}
    if from_j:
        kwargs_j["from_date"] = datetime.combine(from_j, datetime.min.time())
    if to_j:
        kwargs_j["to_date"] = datetime.combine(to_j, datetime.max.time())

    vouchers = get_vouchers(**kwargs_j)
    if not vouchers:
        st.info("No journal entries found.")
    else:
        for v in vouchers:
            with st.expander(f"{v.get('voucher_no', '')} | {fmt_date(v.get('date'))} | {v.get('narration', '')}"):
                rows = []
                for e in v.get("entries", []):
                    rows.append({
                        "Ledger": e.get("ledger_name", ""),
                        "Debit (₹)": f"{e.get('debit', 0):,.2f}" if e.get("debit") else "",
                        "Credit (₹)": f"{e.get('credit', 0):,.2f}" if e.get("credit") else "",
                    })
                st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
