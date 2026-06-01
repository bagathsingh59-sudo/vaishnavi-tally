import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import streamlit as st

from database import ensure_indexes
from utils.formatting import TALLY_CSS, keyboard_shortcuts

st.set_page_config(
    page_title="Vaishnavi Consultants — Tally",
    page_icon="💼",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Inject styling + keyboard shortcuts ONCE for the whole app
st.markdown(TALLY_CSS, unsafe_allow_html=True)
keyboard_shortcuts()

try:
    ensure_indexes()
except Exception:
    pass

# ── Define pages (st.navigation overrides the default pages/ auto-discovery) ────
dashboard = st.Page("pages/0_Dashboard.py", title="Dashboard", icon="🏠", default=True)
clients   = st.Page("pages/1_Clients.py",   title="Clients",   icon="👥", url_path="Clients")
receipts  = st.Page("pages/2_Receipts.py",  title="Receipt",   icon="💰", url_path="Receipts")
payments  = st.Page("pages/3_Payments.py",  title="Payment",   icon="💸", url_path="Payments")
journal   = st.Page("pages/4_Journal.py",   title="Journal",   icon="📓", url_path="Journal")
ledgers   = st.Page("pages/5_Ledgers.py",   title="Ledgers",   icon="📒", url_path="Ledgers")
reports   = st.Page("pages/6_Reports.py",   title="Reports",   icon="📊", url_path="Reports")
daybook   = st.Page("pages/7_DayBook.py",   title="Day Book",  icon="📅", url_path="DayBook")
settings  = st.Page("pages/8_Settings.py",  title="Settings",  icon="⚙️", url_path="Settings")

pg = st.navigation({
    "Gateway":             [dashboard],
    "Accounting Vouchers": [receipts, payments, journal],
    "Masters":             [clients, ledgers],
    "Display / Reports":   [daybook, reports],
    "Admin":               [settings],
})

pg.run()
