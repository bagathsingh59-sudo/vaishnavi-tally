from datetime import datetime
import streamlit as st
import streamlit.components.v1 as components


# ── Currency & date helpers ────────────────────────────────────────────────────

def fmt_currency(amount: float) -> str:
    if amount < 0:
        return f"-₹{abs(amount):,.2f}"
    return f"₹{amount:,.2f}"


def fmt_date(dt) -> str:
    if not dt:
        return ""
    if isinstance(dt, str):
        return dt
    return dt.strftime("%d-%b-%Y")


def fmt_month(month_str: str) -> str:
    try:
        return datetime.strptime(month_str, "%Y-%m").strftime("%b %Y")
    except Exception:
        return month_str


def voucher_type_label(vtype: str) -> str:
    return {"receipt": "Receipt", "payment": "Payment",
            "journal": "Journal", "contra": "Contra"}.get(vtype, vtype.title())


# ── Tally ERP 9 CSS ────────────────────────────────────────────────────────────

TALLY_CSS = """
<style>
/* ── Base ── */
html, body, [class*="css"] {
    font-family: 'Segoe UI', Arial, sans-serif;
    font-size: 13px;
}

/* Hide Streamlit default chrome */
#MainMenu { visibility: hidden; }
footer    { visibility: hidden; }
header    { visibility: hidden; }

/* Main background */
.stApp { background-color: #F0F0EC; }

/* ── Title bar ── */
.tally-titlebar {
    background: #002B5C;
    color: #FFD700;
    padding: 6px 18px;
    font-size: 14px;
    font-weight: 700;
    letter-spacing: 0.8px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    border-bottom: 2px solid #FFD700;
    margin-bottom: 12px;
    border-radius: 2px;
}
.tally-titlebar span { color: #CCDDFF; font-size: 11px; font-weight: 400; }

/* ── Section header ── */
.tally-section {
    background: #003580;
    color: #FFD700;
    padding: 4px 14px;
    font-size: 12px;
    font-weight: 700;
    letter-spacing: 0.5px;
    border-left: 4px solid #FFD700;
    margin: 10px 0 6px 0;
    text-transform: uppercase;
}

/* ── Info boxes ── */
.tally-box {
    background: #FFFFFF;
    border: 1px solid #B0B0B0;
    border-top: 3px solid #002B5C;
    padding: 10px 14px;
    margin: 4px 0;
}

/* ── Dr / Cr colors ── */
.tally-dr { color: #CC0000; font-weight: 700; }
.tally-cr { color: #006600; font-weight: 700; }

/* ── Status badges ── */
.badge-paid    { background:#d4edda; color:#155724; padding:2px 8px; border-radius:2px; font-size:11px; font-weight:600; }
.badge-unpaid  { background:#f8d7da; color:#721c24; padding:2px 8px; border-radius:2px; font-size:11px; font-weight:600; }
.badge-partial { background:#fff3cd; color:#856404; padding:2px 8px; border-radius:2px; font-size:11px; font-weight:600; }
.badge-excess  { background:#cce5ff; color:#004085; padding:2px 8px; border-radius:2px; font-size:11px; font-weight:600; }
.badge-short   { background:#fff3cd; color:#856404; padding:2px 8px; border-radius:2px; font-size:11px; font-weight:600; }

/* ── Sidebar ── */
section[data-testid="stSidebar"] {
    background: #002B5C !important;
    border-right: 2px solid #FFD700;
}
section[data-testid="stSidebar"] * { color: #FFFFFF !important; }
section[data-testid="stSidebar"] .stMarkdown p { color: #FFD700 !important; font-weight: 600; }
section[data-testid="stSidebar"] a:hover { color: #FFD700 !important; }

/* ── Dataframe / Table ── */
div[data-testid="stDataFrame"] thead th {
    background-color: #002B5C !important;
    color: #FFD700 !important;
    font-weight: 700 !important;
    font-size: 12px !important;
}
div[data-testid="stDataFrame"] tbody tr:nth-child(even) { background: #F5F8FF; }
div[data-testid="stDataFrame"] tbody tr:hover { background: #FFFDE7 !important; }

/* ── Metrics ── */
div[data-testid="stMetric"] {
    background: #FFFFFF;
    border: 1px solid #CCCCCC;
    border-top: 3px solid #002B5C;
    padding: 8px 12px !important;
    border-radius: 2px;
}
div[data-testid="metric-container"] label { color: #002B5C !important; font-weight: 600; font-size: 11px; }

/* ── Input fields ── */
.stTextInput > div > div > input,
.stNumberInput > div > div > input,
.stTextArea > div > div > textarea {
    border: 1px solid #AAAAAA !important;
    border-radius: 0 !important;
    background: #FFFDE7 !important;
    font-family: 'Courier New', monospace !important;
    font-size: 13px !important;
}
.stTextInput > div > div > input:focus,
.stNumberInput > div > div > input:focus {
    border: 1px solid #002B5C !important;
    box-shadow: 0 0 0 2px #FFD70033 !important;
}

/* ── Selectbox ── */
.stSelectbox > div > div {
    border: 1px solid #AAAAAA !important;
    border-radius: 0 !important;
    background: #FFFDE7 !important;
}

/* ── Buttons — all variants ── */
.stButton button,
.stButton > button,
div.stButton button {
    border-radius: 2px !important;
    background: #002B5C !important;
    color: #FFD700 !important;
    border: 1px solid #FFD700 !important;
    font-weight: 700 !important;
    font-size: 12px !important;
    letter-spacing: 0.5px;
    padding: 5px 20px !important;
    transition: background 0.1s, color 0.1s;
}
.stButton button:hover,
.stButton > button:hover {
    background: #FFD700 !important;
    color: #002B5C !important;
    border-color: #002B5C !important;
}
/* Primary button — gold background */
button[kind="primary"],
.stButton button[kind="primary"] {
    background: #FFD700 !important;
    color: #002B5C !important;
    border: 2px solid #002B5C !important;
    font-size: 13px !important;
}
button[kind="primary"]:hover,
.stButton button[kind="primary"]:hover {
    background: #FFC200 !important;
}

/* ── Tabs — Streamlit 1.45 data-testid selectors ── */
button[data-testid="stTab"] {
    background: #DCE3F0 !important;
    color: #002B5C !important;
    border-radius: 0 !important;
    font-weight: 600 !important;
    font-size: 12px !important;
    border: 1px solid #AAAACC !important;
    border-bottom: 2px solid transparent !important;
    padding: 6px 18px !important;
    margin-right: 2px !important;
}
button[data-testid="stTab"]:hover {
    background: #003580 !important;
    color: #FFD700 !important;
}
button[data-testid="stTab"][aria-selected="true"] {
    background: #002B5C !important;
    color: #FFD700 !important;
    border-color: #002B5C !important;
    border-bottom: 2px solid #FFD700 !important;
    font-weight: 700 !important;
}

/* ── Alerts ── */
div[data-testid="stAlert"] { border-radius: 2px !important; border-left: 4px solid #002B5C; }

/* ── Divider ── */
hr { border-color: #002B5C !important; border-width: 1px !important; }

/* ── F-key bar spacer ── */
.fkey-spacer { height: 36px; }

/* ── F-key fixed bar ── */
.fkey-bar {
    position: fixed;
    bottom: 0; left: 0; right: 0;
    background: #001A3D;
    border-top: 2px solid #FFD700;
    padding: 4px 8px;
    display: flex;
    flex-wrap: nowrap;
    gap: 4px;
    z-index: 99999;
    font-size: 11px;
}
.fkey-item {
    display: inline-flex;
    align-items: center;
    gap: 2px;
    cursor: pointer;
    padding: 2px 6px;
    border: 1px solid #FFD70066;
    color: #FFFFFF;
    white-space: nowrap;
    text-decoration: none;
}
.fkey-item:hover { background: #FFD700; color: #002B5C !important; border-color: #FFD700; }
.fkey-item b { color: #FFD700; margin-right: 2px; }
.fkey-item:hover b { color: #002B5C; }

/* ── Keyboard shortcut toast ── */
#shortcut-toast {
    display: none;
    position: fixed;
    bottom: 44px; left: 50%;
    transform: translateX(-50%);
    background: #002B5C;
    color: #FFD700;
    border: 1px solid #FFD700;
    padding: 4px 16px;
    font-size: 12px;
    font-weight: 700;
    z-index: 99998;
    border-radius: 2px;
}
</style>
"""

# ── F-key navigation bar ──────────────────────────────────────────────────────

FKEYS = [
    ("F1",  "Dashboard", "/"),
    ("F2",  "Clients",  "/Clients"),
    ("F5",  "Payment",  "/Payments"),
    ("F6",  "Receipt",  "/Receipts"),
    ("F7",  "Journal",  "/Journal"),
    ("F8",  "Day Book", "/DayBook"),
    ("F9",  "Ledgers",  "/Ledgers"),
    ("F12", "Reports",  "/Reports"),
]


def fkey_bar():
    """Render Tally-like F-key navigation bar fixed at the bottom."""
    links = "".join(
        f'<a class="fkey-item" href="{path}"><b>{key}</b>{label}</a>'
        for key, label, path in FKEYS
    )
    st.markdown(
        f'<div class="fkey-bar">{links}'
        f'<span style="margin-left:auto;color:#AAAAAA;font-size:10px;padding-right:8px">'
        f'Ctrl+S: Save &nbsp;|&nbsp; Esc: Cancel &nbsp;|&nbsp; Tab: Next Field</span>'
        f'</div>'
        f'<div class="fkey-spacer"></div>',
        unsafe_allow_html=True,
    )


def keyboard_shortcuts():
    """Inject keyboard shortcut handler for Tally-like navigation."""
    components.html("""
    <div id="shortcut-toast"></div>
    <script>
    (function() {
        const routes = {
            'F1':  '/',
            'F2':  '/Clients',
            'F3':  '/Invoices',
            'F5':  '/Payments',
            'F6':  '/Receipts',
            'F7':  '/Journal',
            'F9':  '/Ledgers',
            'F12': '/Reports',
        };
        const labels = {
            'F1':'Home','F2':'Clients','F3':'Invoices',
            'F5':'Payment','F6':'Receipt','F7':'Journal',
            'F9':'Ledgers','F12':'Reports'
        };

        function showToast(msg) {
            const t = window.parent.document.getElementById('shortcut-toast');
            if (!t) return;
            t.textContent = msg;
            t.style.display = 'block';
            setTimeout(() => { t.style.display = 'none'; }, 800);
        }

        window.parent.document.addEventListener('keydown', function(e) {
            // Skip if user is typing in an input
            const tag = window.parent.document.activeElement.tagName;
            if (['INPUT','TEXTAREA','SELECT'].includes(tag)) {
                // Ctrl+S → click first primary button (Save)
                if ((e.ctrlKey || e.metaKey) && e.key === 's') {
                    e.preventDefault();
                    const btn = window.parent.document.querySelector('button[kind="primary"]');
                    if (btn) btn.click();
                    showToast('Ctrl+S — Saving...');
                }
                return;
            }
            const path = routes[e.key];
            if (path) {
                e.preventDefault();
                showToast(e.key + ' → ' + (labels[e.key] || ''));
                // Streamlit Cloud paths are lowercase page names
                setTimeout(() => { window.parent.location.pathname = path; }, 200);
            }
        }, true);
    })();
    </script>
    """, height=0)
