import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import streamlit as st
import pandas as pd
from services.client_service import (
    get_all_clients, get_client, create_client, update_client,
    deactivate_client, reactivate_client, search_clients, get_client_outstanding,
)
from services.ledger_service import get_ledger_transactions, get_client_ledger
from services.report_service import get_short_payments, get_excess_payments
from utils.formatting import fmt_currency, fmt_date, fmt_month, TALLY_CSS, fkey_bar, keyboard_shortcuts

st.markdown(TALLY_CSS, unsafe_allow_html=True)
st.markdown('<div class="tally-titlebar">👥 &nbsp;CLIENTS — SUNDRY DEBTORS<span>F2 · Master Data</span></div>', unsafe_allow_html=True)

tab1, tab2, tab3 = st.tabs(["📋 Client List", "➕ Add New Client", "📄 Client Ledger"])

# ── Tab 1: Client List ─────────────────────────────────────────────────────────
with tab1:
    col_search, col_toggle = st.columns([3, 1])
    with col_search:
        search_q = st.text_input("Search clients", placeholder="Name / Contact / Phone")
    with col_toggle:
        show_inactive = st.checkbox("Show inactive")

    clients = search_clients(search_q) if search_q else get_all_clients(active_only=not show_inactive)

    if not clients:
        st.info("No clients found. Add your first client in the 'Add New Client' tab.")
    else:
        rows = []
        for c in clients:
            outstanding = get_client_outstanding(c["id"])
            rows.append({
                "Name": c["name"],
                "Contact": c.get("contact_person", ""),
                "Phone": c.get("phone", ""),
                "EPF No": c.get("epf_account_no", ""),
                "ESIC No": c.get("esic_account_no", ""),
                "Outstanding": fmt_currency(outstanding),
                "Status": "Active" if c.get("is_active") else "Inactive",
                "_id": c["id"],
            })
        df = pd.DataFrame(rows)
        display_df = df.drop(columns=["_id"])
        st.dataframe(display_df, use_container_width=True, hide_index=True)

        st.divider()
        st.markdown("**Quick Actions**")
        col_sel, col_act = st.columns([2, 1])
        with col_sel:
            selected_name = st.selectbox("Select client", [r["Name"] for r in rows])
        selected_row = next((r for r in rows if r["Name"] == selected_name), None)

        if selected_row:
            col_edit, col_deact = st.columns(2)
            with col_edit:
                if st.button("✏️ Edit in Tab 3"):
                    st.session_state["view_client_id"] = selected_row["_id"]
                    st.info("Switch to 'Client Ledger' tab to view/edit.")
            with col_deact:
                status_label = "Reactivate" if not next(
                    (c for c in clients if c["id"] == selected_row["_id"]), {}
                ).get("is_active", True) else "Deactivate"
                if st.button(f"🔴 {status_label}"):
                    if status_label == "Deactivate":
                        deactivate_client(selected_row["_id"])
                    else:
                        reactivate_client(selected_row["_id"])
                    st.success(f"Client {status_label.lower()}d.")
                    st.rerun()

# ── Tab 2: Add New Client ──────────────────────────────────────────────────────
with tab2:
    with st.form("add_client_form", clear_on_submit=True):
        st.subheader("New Client Details")
        col1, col2 = st.columns(2)
        with col1:
            name = st.text_input("Client / Company Name *")
            contact = st.text_input("Contact Person")
            phone = st.text_input("Phone")
            email = st.text_input("Email")
        with col2:
            address = st.text_area("Address", height=80)
            epf_no = st.text_input("EPF Account No")
            esic_no = st.text_input("ESIC Account No")

        st.subheader("Opening Balance")
        col3, col4 = st.columns(2)
        with col3:
            ob = st.number_input("Opening Balance (₹)", min_value=0.0, value=0.0, step=100.0)
        with col4:
            ob_type = st.selectbox("Type", ["Dr (They owe us)", "Cr (We owe them)"])

        submitted = st.form_submit_button("💾 Save Client", type="primary")
        if submitted:
            if not name.strip():
                st.error("Client name is required.")
            else:
                create_client({
                    "name": name,
                    "contact_person": contact,
                    "phone": phone,
                    "email": email,
                    "address": address,
                    "epf_account_no": epf_no,
                    "esic_account_no": esic_no,
                    "opening_balance": ob,
                    "opening_balance_type": "dr" if "Dr" in ob_type else "cr",
                })
                st.success(f"✅ Client '{name}' added successfully!")

# ── Tab 3: Client Ledger ───────────────────────────────────────────────────────
with tab3:
    clients_list = get_all_clients()
    if not clients_list:
        st.info("No clients yet.")
    else:
        names_map = {c["name"]: c["id"] for c in clients_list}
        default_name = next(
            (c["name"] for c in clients_list if c["id"] == st.session_state.get("view_client_id")),
            clients_list[0]["name"],
        )
        sel_name = st.selectbox("Select Client", list(names_map.keys()), index=list(names_map.keys()).index(default_name))
        sel_id = names_map[sel_name]
        client_data = get_client(sel_id)

        if client_data:
            col_info, col_bal = st.columns([2, 1])
            with col_info:
                st.markdown(f"""
                **{client_data['name']}**
                Contact: {client_data.get('contact_person', '—')} | Phone: {client_data.get('phone', '—')}
                EPF: `{client_data.get('epf_account_no', '—')}` | ESIC: `{client_data.get('esic_account_no', '—')}`
                """)
            with col_bal:
                outstanding = get_client_outstanding(sel_id)
                bal_type = "Dr (Receivable)" if outstanding >= 0 else "Cr (Excess Held)"
                st.metric("Outstanding Balance", fmt_currency(abs(outstanding)), delta=bal_type)

            # Edit form
            with st.expander("✏️ Edit Client Details"):
                with st.form("edit_client_form"):
                    ec1, ec2 = st.columns(2)
                    with ec1:
                        new_name = st.text_input("Name", value=client_data["name"])
                        new_contact = st.text_input("Contact", value=client_data.get("contact_person", ""))
                        new_phone = st.text_input("Phone", value=client_data.get("phone", ""))
                    with ec2:
                        new_epf = st.text_input("EPF No", value=client_data.get("epf_account_no", ""))
                        new_esic = st.text_input("ESIC No", value=client_data.get("esic_account_no", ""))
                        new_address = st.text_area("Address", value=client_data.get("address", ""), height=68)
                    if st.form_submit_button("Update"):
                        update_client(sel_id, {
                            "name": new_name, "contact_person": new_contact,
                            "phone": new_phone, "epf_account_no": new_epf,
                            "esic_account_no": new_esic, "address": new_address,
                        })
                        st.success("Updated!")
                        st.rerun()

            st.divider()
            st.markdown("**Ledger Statement**")
            ledger = get_client_ledger(sel_id)
            if ledger:
                col_fd, col_td = st.columns(2)
                from_d = col_fd.date_input("From", value=None)
                to_d = col_td.date_input("To", value=None)
                from datetime import datetime as dt
                fd = dt.combine(from_d, dt.min.time()) if from_d else None
                td = dt.combine(to_d, dt.max.time()) if to_d else None
                txns, closing = get_ledger_transactions(ledger["id"], fd, td)
                if txns:
                    rows_df = []
                    for t in txns:
                        rows_df.append({
                            "Date": fmt_date(t["date"]),
                            "Voucher No": t["voucher_no"],
                            "Type": t["voucher_type"].title(),
                            "Narration": t["narration"],
                            "Dr (₹)": f"{t['debit']:,.2f}" if t["debit"] else "",
                            "Cr (₹)": f"{t['credit']:,.2f}" if t["credit"] else "",
                            "Balance": f"{t['balance']:,.2f} {t['balance_type']}",
                        })
                    st.dataframe(pd.DataFrame(rows_df), use_container_width=True, hide_index=True)
                    st.markdown(
                        f"**Closing Balance: {fmt_currency(abs(closing))} {'Dr' if closing >= 0 else 'Cr'}**"
                    )
                else:
                    st.info("No transactions found for this period.")

            # Short / Excess summary for this client
            st.divider()
            shorts  = [s for s in get_short_payments()  if s.get("client_id") == sel_id]
            excesses= [e for e in get_excess_payments() if e.get("client_id") == sel_id]
            if shorts or excesses:
                st.markdown("**Short / Excess Payment History**")
                se_rows = []
                for s in shorts:
                    se_rows.append({"Type":"SHORT","Month":s.get("billing_month",""),
                        "Amount":fmt_currency(s.get("difference",0)),"Status":s.get("status","").upper()})
                for e in excesses:
                    se_rows.append({"Type":"EXCESS","Month":e.get("billing_month",""),
                        "Amount":fmt_currency(e.get("difference",0)),"Status":e.get("status","").upper()})
                if se_rows:
                    st.dataframe(pd.DataFrame(se_rows), use_container_width=True, hide_index=True)
