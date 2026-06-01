import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime

from database import ensure_indexes
from services.report_service import get_dashboard_stats
from utils.formatting import fmt_currency, fmt_date, TALLY_CSS, fkey_bar, keyboard_shortcuts

st.set_page_config(
    page_title="Vaishnavi Consultants — Tally",
    page_icon="💼",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(TALLY_CSS, unsafe_allow_html=True)
keyboard_shortcuts()

try:
    ensure_indexes()
except Exception:
    pass

try:
    firm = st.secrets.get("FIRM_NAME", os.getenv("FIRM_NAME", "Vaishnavi Consultants"))
except Exception:
    firm = os.getenv("FIRM_NAME", "Vaishnavi Consultants")

# ── Title bar ─────────────────────────────────────────────────────────────────
st.markdown(
    f'<div class="tally-titlebar">'
    f'💼 &nbsp;{firm.upper()} &nbsp;—&nbsp; GATEWAY OF TALLY'
    f'<span>📅 {datetime.today().strftime("%d-%b-%Y")} &nbsp;|&nbsp; '
    f'Financial Year: Apr {datetime.today().year if datetime.today().month >= 4 else datetime.today().year-1}'
    f'–{str(datetime.today().year + 1 if datetime.today().month >= 4 else datetime.today().year)[2:]}'
    f'</span>'
    f'</div>',
    unsafe_allow_html=True,
)

# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🏠 GATEWAY OF TALLY")
    st.markdown("---")
    st.markdown("**ACCOUNTING VOUCHERS**")
    st.page_link("pages/2_Receipts.py",  label="F6  Receipt",  icon="💰")
    st.page_link("pages/3_Payments.py",  label="F5  Payment",  icon="💸")
    st.page_link("pages/4_Journal.py",   label="F7  Journal",  icon="📓")
    st.markdown("---")
    st.markdown("**MASTER DATA**")
    st.page_link("pages/1_Clients.py",   label="F2  Clients",  icon="👥")
    st.page_link("pages/5_Ledgers.py",   label="F9  Ledgers",  icon="📒")
    st.markdown("---")
    st.markdown("**DISPLAY / REPORTS**")
    st.page_link("pages/7_DayBook.py",   label="F8  Day Book", icon="📅")
    st.page_link("pages/6_Reports.py",   label="F12 Reports",  icon="📊")

# ── Dashboard ─────────────────────────────────────────────────────────────────
st.markdown('<div class="tally-section">📊 CURRENT STATUS</div>', unsafe_allow_html=True)

try:
    stats = get_dashboard_stats()
except Exception as e:
    st.error("⚠️ Cannot connect to MongoDB. The database is not configured yet.")
    st.markdown("""
**To fix this, add your MongoDB Atlas URI in Streamlit Cloud secrets:**

1. Go to your app → **⋮ menu → Settings → Secrets**
2. Paste the following:

```toml
ENV = "production"
DB_NAME = "vaishnavi_tally"
FIRM_NAME = "Vaishnavi Consultants"
MONGO_URI_PROD = "mongodb+srv://<user>:<password>@cluster.mongodb.net/"
```

3. Click **Save** — the app will reboot automatically.
""")
    with st.expander("Technical error details"):
        st.code(str(e))
    fkey_bar()
    st.stop()

# ── Metrics ───────────────────────────────────────────────────────────────────
c1, c2, c3, c4, c5, c6 = st.columns(6)
c1.metric("Outstanding",         fmt_currency(stats["total_outstanding"]))
c2.metric("This Month Receipts", fmt_currency(stats["month_receipts"]))
c3.metric("Bank Balance",        fmt_currency(stats["bank_balance"]))
c4.metric("Cash in Hand",        fmt_currency(stats["cash_balance"]))
c5.metric("Short Pending",       fmt_currency(stats["short_pending_amount"]),
          delta=f"{stats['short_pending_count']} parties", delta_color="inverse")
c6.metric("Excess Held",         fmt_currency(stats["excess_held"]))

st.markdown("---")

# ── Quick Actions ─────────────────────────────────────────────────────────────
st.markdown('<div class="tally-section">⚡ QUICK ACTIONS</div>', unsafe_allow_html=True)

qa1, qa2, qa3, qa4 = st.columns(4)
with qa1:
    st.markdown('<div class="tally-box"><b>F7 — Journal Voucher</b><br>'
                '<small>Record client billing entry</small></div>', unsafe_allow_html=True)
    if st.button("New Journal →", key="qa_jrn"):
        st.switch_page("pages/4_Journal.py")

with qa2:
    st.markdown('<div class="tally-box"><b>F6 — Receipt Voucher</b><br>'
                '<small>Record payment from client</small></div>', unsafe_allow_html=True)
    if st.button("New Receipt →", key="qa_rcpt"):
        st.switch_page("pages/2_Receipts.py")

with qa3:
    st.markdown('<div class="tally-box"><b>F5 — Payment Voucher</b><br>'
                '<small>EPF / ESIC / Expense</small></div>', unsafe_allow_html=True)
    if st.button("New Payment →", key="qa_pay"):
        st.switch_page("pages/3_Payments.py")

with qa4:
    st.markdown('<div class="tally-box"><b>F8 — Day Book</b><br>'
                '<small>View all today\'s entries</small></div>', unsafe_allow_html=True)
    if st.button("Day Book →", key="qa_db"):
        st.switch_page("pages/7_DayBook.py")

st.markdown("---")

# ── Charts + Recent ───────────────────────────────────────────────────────────
col_chart, col_recent = st.columns([1.6, 1])

with col_chart:
    st.markdown('<div class="tally-section">📈 MONTHLY COLLECTIONS (₹)</div>', unsafe_allow_html=True)
    chart_data = stats.get("monthly_chart", [])
    if chart_data:
        months  = [d["_id"] for d in chart_data]
        amounts = [d["total"] for d in chart_data]
        fig = go.Figure(go.Bar(
            x=months, y=amounts,
            marker_color="#002B5C",
            text=[fmt_currency(a) for a in amounts],
            textposition="outside",
            textfont=dict(color="#002B5C", size=11),
        ))
        fig.update_layout(
            height=280, margin=dict(l=0, r=0, t=10, b=0),
            paper_bgcolor="#F0F0EC", plot_bgcolor="#FFFFFF",
            yaxis=dict(showgrid=True, gridcolor="#DDDDDD"),
            xaxis=dict(showgrid=False),
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No entries yet. Start with F7 Journal to record your first entry.")

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
        st.dataframe(df, use_container_width=True, hide_index=True, height=280)
    else:
        st.info("No transactions yet.")

fkey_bar()
