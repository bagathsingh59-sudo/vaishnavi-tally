import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta
from services.voucher_service import get_vouchers
from utils.formatting import fmt_currency, fmt_date, TALLY_CSS, fkey_bar, keyboard_shortcuts
from database import get_db

st.set_page_config(page_title="Day Book — Vaishnavi", layout="wide")
st.markdown(TALLY_CSS, unsafe_allow_html=True)
keyboard_shortcuts()
st.markdown('<div class="tally-titlebar">📅 &nbsp;DAY BOOK<span>Display · All Vouchers</span></div>',
            unsafe_allow_html=True)

# ── Date range ────────────────────────────────────────────────────────────────
col_f1, col_f2, col_f3 = st.columns([1.5, 1.5, 3])
from_d = col_f1.date_input("From Date", value=date.today())
to_d   = col_f2.date_input("To Date",   value=date.today())
vtype  = col_f3.selectbox("Filter by Voucher Type",
                           ["All", "Receipt", "Payment", "Journal"])

kw = {
    "from_date": datetime.combine(from_d, datetime.min.time()),
    "to_date":   datetime.combine(to_d,   datetime.max.time()),
    "limit":     500,
}
if vtype != "All":
    kw["voucher_type"] = vtype.lower()

vouchers = get_vouchers(**kw)

if not vouchers:
    st.info(f"No transactions found for {fmt_date(datetime.combine(from_d, datetime.min.time()))} "
            f"to {fmt_date(datetime.combine(to_d, datetime.max.time()))}")
    fkey_bar(); st.stop()

# ── Build flat rows ───────────────────────────────────────────────────────────
TYPE_COLOR = {"receipt": "#1E8449", "payment": "#C0392B", "journal": "#5B4FCF", "contra": "#E67E22"}
rows, total_dr, total_cr = [], 0.0, 0.0

for v in vouchers:
    vt   = v.get("voucher_type", "")
    vno  = v.get("voucher_no", "")
    vdt  = fmt_date(v.get("date"))
    narr = v.get("narration", "")
    party= v.get("client_name", "")

    for e in v.get("entries", []):
        dr = e.get("debit", 0)
        cr = e.get("credit", 0)
        total_dr += dr
        total_cr += cr
        rows.append({
            "Date":        vdt,
            "Voucher No":  vno,
            "Type":        vt.title(),
            "Party":       party,
            "Ledger":      e.get("ledger_name", ""),
            "Narration":   narr[:50],
            "Debit (₹)":  f"{dr:,.2f}" if dr else "—",
            "Credit (₹)": f"{cr:,.2f}" if cr else "—",
        })

# ── Summary metrics ───────────────────────────────────────────────────────────
m1, m2, m3, m4 = st.columns(4)
rcpt_total = sum(
    sum(e.get("debit", 0) for e in v.get("entries", []))
    for v in vouchers if v.get("voucher_type") == "receipt"
)
pay_total = sum(
    sum(e.get("credit", 0) for e in v.get("entries", []))
    for v in vouchers if v.get("voucher_type") == "payment"
)
m1.metric("Total Receipts",  fmt_currency(rcpt_total))
m2.metric("Total Payments",  fmt_currency(pay_total))
m3.metric("Net Cash Flow",   fmt_currency(rcpt_total - pay_total))
m4.metric("Vouchers",        str(len(vouchers)))

st.markdown("---")

# ── Day Book table ────────────────────────────────────────────────────────────
df = pd.DataFrame(rows)
st.dataframe(df, use_container_width=True, hide_index=True, height=500)

# ── Totals row ────────────────────────────────────────────────────────────────
col_l, col_dr, col_cr = st.columns([6, 1, 1])
col_l.markdown("**GRAND TOTAL**")
col_dr.markdown(f"**{fmt_currency(total_dr)}**")
col_cr.markdown(f"**{fmt_currency(total_cr)}**")

# ── Voucher-wise summary ──────────────────────────────────────────────────────
st.markdown("---")
st.markdown("**Summary by Voucher Type**")
summary_rows = {}
for v in vouchers:
    vt = v.get("voucher_type", "other").title()
    amt = max(
        sum(e.get("debit", 0) for e in v.get("entries", [])),
        sum(e.get("credit", 0) for e in v.get("entries", []))
    )
    summary_rows[vt] = summary_rows.get(vt, {"count": 0, "amount": 0.0})
    summary_rows[vt]["count"]  += 1
    summary_rows[vt]["amount"] += amt

s_rows = [{"Type": k, "Count": v["count"], "Amount": fmt_currency(v["amount"])}
          for k, v in summary_rows.items()]
st.dataframe(pd.DataFrame(s_rows), use_container_width=False, hide_index=True)

fkey_bar()
