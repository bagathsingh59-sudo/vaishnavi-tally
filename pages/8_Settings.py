import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import streamlit as st
from services.admin_service import count_all, reset_transactions, reset_everything
from utils.formatting import TALLY_CSS, fkey_bar

st.markdown(TALLY_CSS, unsafe_allow_html=True)
st.markdown('<div class="tally-titlebar">⚙️ &nbsp;SETTINGS — DATA MANAGEMENT<span>Admin · Reset</span></div>',
            unsafe_allow_html=True)

# ── Current data counts ───────────────────────────────────────────────────────
counts = count_all()
st.markdown('<div class="tally-section">📊 CURRENT DATA</div>', unsafe_allow_html=True)
c1, c2, c3, c4 = st.columns(4)
c1.metric("Clients",        counts["clients"])
c2.metric("Ledgers",        counts["ledgers"])
c3.metric("Vouchers",       counts["vouchers"])
c4.metric("Short / Excess", counts["short_excess"])

st.markdown("---")

# ═══════════════════════════════════════════════════════════════════════════════
# OPTION 1 — Reset Transactions Only
# ═══════════════════════════════════════════════════════════════════════════════
st.markdown('<div class="tally-section">🧹 OPTION 1 — CLEAR TRANSACTIONS ONLY</div>',
            unsafe_allow_html=True)
st.info("Deletes **all vouchers** (Receipts, Payments, Journals), short/excess "
        "records and resets voucher numbering. **Keeps your Clients and Ledgers** "
        "(your setup stays intact). Recommended for starting fresh data entry.")

confirm1 = st.text_input(
    "Type **RESET TRANSACTIONS** to confirm",
    key="confirm_txn", placeholder="RESET TRANSACTIONS",
)
if st.button("🧹 Clear All Transactions", key="btn_txn"):
    if confirm1.strip().upper() == "RESET TRANSACTIONS":
        res = reset_transactions()
        st.success(f"✅ Cleared — Vouchers: {res['vouchers']}, "
                   f"Short/Excess: {res['short_excess']}, Invoices: {res['invoices']}. "
                   f"Voucher numbering reset. Clients & Ledgers kept.")
        st.balloons()
    else:
        st.error("Confirmation text does not match. Type exactly: RESET TRANSACTIONS")

st.markdown("---")

# ═══════════════════════════════════════════════════════════════════════════════
# OPTION 2 — Full Wipe
# ═══════════════════════════════════════════════════════════════════════════════
st.markdown('<div class="tally-section">🔴 OPTION 2 — FULL RESET (EVERYTHING)</div>',
            unsafe_allow_html=True)
st.warning("⚠️ Deletes **everything** — Clients, Ledgers, Vouchers, Short/Excess, "
           "Invoices and counters. The database will be completely empty. "
           "Use only if you want to rebuild from scratch.")

confirm2 = st.text_input(
    "Type **DELETE EVERYTHING** to confirm",
    key="confirm_all", placeholder="DELETE EVERYTHING",
)
agree = st.checkbox("I understand this cannot be undone", key="agree_all")
if st.button("🔴 Wipe Entire Database", key="btn_all", disabled=not agree):
    if confirm2.strip().upper() == "DELETE EVERYTHING":
        res = reset_everything()
        st.success(f"✅ Full reset done — {sum(res.values())} records deleted across "
                   f"all collections. Database is now empty.")
        st.balloons()
    else:
        st.error("Confirmation text does not match. Type exactly: DELETE EVERYTHING")

st.markdown("---")
st.caption("💡 Tip: After clearing, set up your Bank/Cash ledger (F9) and Client "
           "(F2) first, then start entering vouchers.")

fkey_bar()
