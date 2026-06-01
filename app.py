import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime

from database import ensure_indexes
from services.report_service import get_dashboard_stats
from utils.formatting import fmt_currency, fmt_date, TALLY_CSS

st.set_page_config(
    page_title="Vaishnavi Consultants",
    page_icon="💼",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(TALLY_CSS, unsafe_allow_html=True)

# Indexes are best-effort — do NOT let a missing DB crash the process before
# Streamlit's HTTP server even binds to its port.
try:
    ensure_indexes()
except Exception:
    pass

# ── Header ────────────────────────────────────────────────────────────────────
try:
    firm = st.secrets.get("FIRM_NAME", os.getenv("FIRM_NAME", "Vaishnavi Consultants"))
except Exception:
    firm = os.getenv("FIRM_NAME", "Vaishnavi Consultants")
st.markdown(
    f'<div class="tally-header">💼 {firm} — Workstation &nbsp;|&nbsp; '
    f'{datetime.today().strftime("%d %b %Y")}</div>',
    unsafe_allow_html=True,
)

# ── Sidebar navigation hint ───────────────────────────────────────────────────
st.sidebar.markdown("## Navigation")
st.sidebar.info("Use the pages in the sidebar to navigate between modules.")

# ── Dashboard stats ───────────────────────────────────────────────────────────
st.subheader("Dashboard")
try:
    stats = get_dashboard_stats()
except Exception as e:
    st.error("⚠️ Cannot connect to MongoDB. The database is not configured yet.")
    st.markdown("""
**To fix this, add your MongoDB Atlas URI in Streamlit Cloud secrets:**

1. Go to your app → **⋮ menu → Settings → Secrets**
2. Paste the following (replace the URI with your Atlas connection string):

```toml
ENV = "production"
DB_NAME = "vaishnavi_tally"
FIRM_NAME = "Vaishnavi Consultants"
MONGO_URI_PROD = "mongodb+srv://<user>:<password>@cluster.mongodb.net/"
```

3. Click **Save** — the app will reboot automatically.

> Get a free Atlas cluster at [cloud.mongodb.com](https://cloud.mongodb.com)
""")
    with st.expander("Technical error details"):
        st.code(str(e))
    st.stop()

col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Outstanding", fmt_currency(stats["total_outstanding"]))
col2.metric("This Month Collections", fmt_currency(stats["month_receipts"]))
col3.metric("Bank Balance", fmt_currency(stats["bank_balance"]))
col4.metric("Cash in Hand", fmt_currency(stats["cash_balance"]))

col5, col6 = st.columns(2)
col5.metric(
    "Short Payments Pending",
    fmt_currency(stats["short_pending_amount"]),
    delta=f"{stats['short_pending_count']} clients",
    delta_color="inverse",
)
col6.metric("Excess Held", fmt_currency(stats["excess_held"]), delta_color="normal")

st.divider()

# ── Monthly collections chart ─────────────────────────────────────────────────
col_chart, col_recent = st.columns([1.4, 1])

with col_chart:
    st.markdown("**Monthly Collections (₹)**")
    chart_data = stats.get("monthly_chart", [])
    if chart_data:
        months = [d["_id"] for d in chart_data]
        amounts = [d["total"] for d in chart_data]
        fig = go.Figure(
            go.Bar(
                x=months,
                y=amounts,
                marker_color="#003366",
                text=[fmt_currency(a) for a in amounts],
                textposition="outside",
            )
        )
        fig.update_layout(
            height=300,
            margin=dict(l=0, r=0, t=10, b=0),
            yaxis=dict(showgrid=True, gridcolor="#eee"),
            plot_bgcolor="white",
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No collection data yet. Add receipts to see the chart.")

with col_recent:
    st.markdown("**Recent Transactions**")
    recent = stats.get("recent_vouchers", [])
    if recent:
        df = pd.DataFrame(recent)
        df["date"] = df["date"].apply(fmt_date)
        df["amount"] = df["amount"].apply(fmt_currency)
        df = df[["date", "voucher_no", "type", "client", "amount"]]
        df.columns = ["Date", "Voucher", "Type", "Client", "Amount"]
        st.dataframe(df, use_container_width=True, hide_index=True, height=300)
    else:
        st.info("No transactions yet.")
