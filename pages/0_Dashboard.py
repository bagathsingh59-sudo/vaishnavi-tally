import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime

from datetime import date
from services.report_service import (
    get_dashboard_stats, get_short_payments, get_excess_payments, get_outstanding_agewise,
)
from services.voucher_service import get_vouchers
from services.ledger_service import get_all_ledgers, get_ledger_balance
from utils.formatting import fmt_currency, fmt_date, fmt_month, TALLY_CSS, fkey_bar

st.markdown(TALLY_CSS, unsafe_allow_html=True)

try:
    firm = st.secrets.get("FIRM_NAME", os.getenv("FIRM_NAME", "Vaishnavi Consultants"))
except Exception:
    firm = os.getenv("FIRM_NAME", "Vaishnavi Consultants")

fy = (datetime.today().year if datetime.today().month >= 4 else datetime.today().year - 1)

st.markdown(
    f'<div class="tally-titlebar">📊 &nbsp;{firm.upper()} — DASHBOARD'
    f'<span>📅 {datetime.today().strftime("%d-%b-%Y")} &nbsp;|&nbsp; '
    f'Financial Year: Apr {fy}–{str(fy + 1)[2:]}</span></div>',
    unsafe_allow_html=True,
)

# ── Load stats ────────────────────────────────────────────────────────────────
try:
    stats = get_dashboard_stats()
except Exception as e:
    st.error("⚠️ Cannot connect to MongoDB. Add your Atlas URI in Settings → Secrets.")
    with st.expander("Technical error details"):
        st.code(str(e))
    fkey_bar()
    st.stop()

PRIMARY  = "#002B5C"
GOLD     = "#FFD700"
GREEN    = "#1E8449"
RED      = "#C0392B"
PURPLE   = "#5B4FCF"

# ═══════════════════════════════════════════════════════════════════════════════
# ROW 1 — KEY FINANCIAL POSITION
# ═══════════════════════════════════════════════════════════════════════════════
st.markdown('<div class="tally-section">💵 FINANCIAL POSITION</div>', unsafe_allow_html=True)

liquid = stats["bank_balance"] + stats["cash_balance"]
c1, c2, c3, c4 = st.columns(4)
c1.metric("💰 Total Liquid Funds", fmt_currency(liquid),
          help="Bank + Cash on hand")
c2.metric("🏦 Bank Balance", fmt_currency(stats["bank_balance"]))
c3.metric("💵 Cash in Hand", fmt_currency(stats["cash_balance"]))
c4.metric("📊 Outstanding (Receivable)", fmt_currency(stats["total_outstanding"]),
          delta=f"{stats['short_pending_count']} parties short",
          delta_color="inverse")

# ═══════════════════════════════════════════════════════════════════════════════
# ROW 2 — THIS MONTH ACTIVITY
# ═══════════════════════════════════════════════════════════════════════════════
st.markdown('<div class="tally-section">📅 THIS MONTH</div>', unsafe_allow_html=True)

net_flow = stats["month_receipts"] - stats["month_payments"]
m1, m2, m3, m4 = st.columns(4)
m1.metric("⬆️ Receipts (In)", fmt_currency(stats["month_receipts"]))
m2.metric("⬇️ Payments (Out)", fmt_currency(stats["month_payments"]))
m3.metric("💹 Net Cash Flow", fmt_currency(net_flow),
          delta="Surplus" if net_flow >= 0 else "Deficit",
          delta_color="normal" if net_flow >= 0 else "inverse")
m4.metric("🔴 Short / 🟢 Excess",
          f"{fmt_currency(stats['short_pending_amount'])} / {fmt_currency(stats['excess_held'])}")

# ── Drill-down: click to expand the entries behind each number ─────────────────
st.markdown('<div class="tally-section">🔍 CLICK TO VIEW DETAILS</div>', unsafe_allow_html=True)
d1, d2, d3 = st.columns(3)

with d1:
    with st.expander(f"🏦 Funds Breakdown — {fmt_currency(liquid)}"):
        rows = []
        for l in get_all_ledgers("bank") + get_all_ledgers("cash"):
            bal = get_ledger_balance(l["id"])
            rows.append({"Ledger": l["name"],
                         "Balance": fmt_currency(abs(bal)),
                         "Type": "Dr" if bal >= 0 else "Cr"})
        if rows:
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
            if st.button("Open Ledgers →", key="dd_led"):
                st.switch_page("pages/5_Ledgers.py")
        else:
            st.caption("No bank/cash ledgers yet.")

with d2:
    with st.expander(f"📊 Outstanding (Receivable) — {fmt_currency(stats['total_outstanding'])}"):
        agewise = get_outstanding_agewise()
        if agewise:
            rows = [{"Client": a["client_name"], "Total Due": fmt_currency(a["total"])}
                    for a in agewise if a["total"] > 0]
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        else:
            st.caption("No outstanding balances.")
        shorts = get_short_payments(status="pending")
        if shorts:
            st.markdown("**Short Payments (pending)**")
            st.dataframe(pd.DataFrame([
                {"Client": s["client_name"], "Month": fmt_month(s.get("billing_month", "")),
                 "Short By": fmt_currency(s.get("difference", 0))} for s in shorts
            ]), use_container_width=True, hide_index=True)

with d3:
    with st.expander(f"⬆️ This Month's Receipts — {fmt_currency(stats['month_receipts'])}"):
        today = datetime.today()
        mstart = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        recs = get_vouchers(voucher_type="receipt",
                            from_date=mstart, to_date=datetime.now())
        if recs:
            st.dataframe(pd.DataFrame([
                {"Date": fmt_date(v.get("date")), "Voucher": v.get("voucher_no", ""),
                 "Party": v.get("client_name", ""),
                 "Amount": fmt_currency(sum(e.get("debit", 0) for e in v.get("entries", [])))}
                for v in recs
            ]), use_container_width=True, hide_index=True)
            if st.button("Open Day Book →", key="dd_db"):
                st.switch_page("pages/7_DayBook.py")
        else:
            st.caption("No receipts recorded this month.")

st.markdown("---")

# ═══════════════════════════════════════════════════════════════════════════════
# ROW 3 — CHARTS
# ═══════════════════════════════════════════════════════════════════════════════
col_left, col_right = st.columns([1.7, 1])

# ── Left: Receipts vs Payments grouped bar (trend) ─────────────────────────────
with col_left:
    st.markdown('<div class="tally-section">📈 RECEIPTS vs PAYMENTS — MONTHLY TREND</div>',
                unsafe_allow_html=True)

    rcpt = {d["_id"]: d["total"] for d in stats.get("monthly_chart", [])}
    paym = {d["_id"]: d["total"] for d in stats.get("monthly_payments", [])}
    all_months = sorted(set(list(rcpt.keys()) + list(paym.keys())))

    if all_months:
        labels = [fmt_month(m) for m in all_months]
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=labels, y=[rcpt.get(m, 0) for m in all_months],
            name="Receipts", marker_color=GREEN,
        ))
        fig.add_trace(go.Bar(
            x=labels, y=[paym.get(m, 0) for m in all_months],
            name="Payments", marker_color=RED,
        ))
        fig.update_layout(
            barmode="group", height=320,
            margin=dict(l=0, r=0, t=10, b=0),
            paper_bgcolor="#F0F0EC", plot_bgcolor="#FFFFFF",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
            yaxis=dict(showgrid=True, gridcolor="#DDDDDD", title="₹"),
            xaxis=dict(showgrid=False),
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No transaction data yet. Record entries to see trends.")

# ── Right: Liquid funds donut (Bank vs Cash) ───────────────────────────────────
with col_right:
    st.markdown('<div class="tally-section">🏦 FUNDS SPLIT</div>', unsafe_allow_html=True)
    if liquid > 0:
        fig2 = go.Figure(go.Pie(
            labels=["Bank", "Cash"],
            values=[max(stats["bank_balance"], 0), max(stats["cash_balance"], 0)],
            hole=0.55,
            marker=dict(colors=[PRIMARY, GOLD]),
            textinfo="label+percent",
        ))
        fig2.update_layout(
            height=320, margin=dict(l=0, r=0, t=10, b=0),
            paper_bgcolor="#F0F0EC",
            showlegend=False,
            annotations=[dict(text=fmt_currency(liquid), x=0.5, y=0.5,
                              font_size=14, showarrow=False, font_color=PRIMARY)],
        )
        st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("No funds recorded yet.")

st.markdown("---")

# ═══════════════════════════════════════════════════════════════════════════════
# ROW 4 — RECENT TRANSACTIONS + QUICK ACTIONS
# ═══════════════════════════════════════════════════════════════════════════════
col_recent, col_actions = st.columns([2, 1])

with col_recent:
    st.markdown('<div class="tally-section">🕐 RECENT TRANSACTIONS</div>', unsafe_allow_html=True)
    recent = stats.get("recent_vouchers", [])
    if recent:
        df = pd.DataFrame(recent)
        df["date"]   = df["date"].apply(fmt_date)
        df["amount"] = df["amount"].apply(fmt_currency)
        df["type"]   = df["type"].str.upper()
        df = df[["date", "voucher_no", "type", "client", "amount"]]
        df.columns = ["Date", "Voucher", "Type", "Party", "Amount"]
        st.dataframe(df, use_container_width=True, hide_index=True, height=300)
    else:
        st.info("No transactions yet. Start with F7 Journal.")

with col_actions:
    st.markdown('<div class="tally-section">⚡ QUICK ENTRY</div>', unsafe_allow_html=True)
    st.metric("👥 Active Clients", stats.get("total_clients", 0))
    st.metric("📑 Total Vouchers", stats.get("total_vouchers", 0))
    if st.button("📓  New Journal  (F7)", use_container_width=True):
        st.switch_page("pages/4_Journal.py")
    if st.button("💰  New Receipt  (F6)", use_container_width=True):
        st.switch_page("pages/2_Receipts.py")
    if st.button("💸  New Payment  (F5)", use_container_width=True):
        st.switch_page("pages/3_Payments.py")
    if st.button("📅  Day Book  (F8)", use_container_width=True):
        st.switch_page("pages/7_DayBook.py")

fkey_bar()
