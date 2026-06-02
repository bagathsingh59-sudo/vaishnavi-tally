import os
from datetime import datetime, date

from flask import (Flask, render_template, request, redirect, url_for, flash, jsonify, Response)

from database import ensure_indexes
from utils.formatting import fmt_currency, fmt_date, fmt_date_input, fmt_month, voucher_type_label

from services import client_service as clients_svc
from services import ledger_service as ledger_svc
from services import voucher_service as voucher_svc
from services import report_service as report_svc
from services import admin_service as admin_svc
from services import reco_service as reco_svc

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "vaishnavi-tally-dev-key-change-me")

# Jinja filters
app.jinja_env.filters["inr"] = fmt_currency
app.jinja_env.filters["date"] = fmt_date
app.jinja_env.filters["dateinput"] = fmt_date_input
app.jinja_env.filters["month"] = fmt_month
app.jinja_env.filters["vtype"] = voucher_type_label

try:
    ensure_indexes()
except Exception:
    pass


@app.context_processor
def inject_globals():
    return {
        "FIRM_NAME": os.getenv("FIRM_NAME", "Vaishnavi Consultants"),
        "TODAY": datetime.today(),
        "FY_LABEL": _fy_label(),
    }


def _fy_label():
    t = datetime.today()
    start = t.year if t.month >= 4 else t.year - 1
    return f"Apr {start}–{str(start + 1)[2:]}"


def _parse_date(s, default=None):
    if not s:
        return default or datetime.combine(date.today(), datetime.min.time())
    try:
        return datetime.combine(datetime.strptime(s, "%Y-%m-%d").date(), datetime.min.time())
    except ValueError:
        return default or datetime.combine(date.today(), datetime.min.time())


# ═══════════════════════════════════════════════════════════════════════════════
# DASHBOARD
# ═══════════════════════════════════════════════════════════════════════════════
@app.route("/")
def dashboard():
    try:
        stats = report_svc.get_dashboard_stats()
    except Exception as e:
        return render_template("db_error.html", error=str(e))

    liquid = stats["bank_balance"] + stats["cash_balance"]

    # Build chart series (months union of receipts & payments)
    rcpt = {d["_id"]: d["total"] for d in stats.get("monthly_chart", [])}
    paym = {d["_id"]: d["total"] for d in stats.get("monthly_payments", [])}
    months = sorted(set(list(rcpt.keys()) + list(paym.keys())))
    chart = {
        "labels": [fmt_month(m) for m in months],
        "receipts": [rcpt.get(m, 0) for m in months],
        "payments": [paym.get(m, 0) for m in months],
    }
    return render_template("dashboard.html", s=stats, liquid=liquid, chart=chart)


# ═══════════════════════════════════════════════════════════════════════════════
# CLIENTS
# ═══════════════════════════════════════════════════════════════════════════════
@app.route("/clients")
def clients():
    q = request.args.get("q", "").strip()
    show_inactive = request.args.get("inactive") == "1"
    if q:
        rows = clients_svc.search_clients(q)
    else:
        rows = clients_svc.get_all_clients(active_only=not show_inactive)
    for c in rows:
        c["outstanding"] = clients_svc.get_client_outstanding(c["id"])
    return render_template("clients.html", clients=rows, q=q, show_inactive=show_inactive)


@app.route("/clients/add", methods=["POST"])
def clients_add():
    f = request.form
    if not f.get("name", "").strip():
        flash("Client name is required.", "error")
        return redirect(url_for("clients"))
    clients_svc.create_client({
        "name": f["name"], "contact_person": f.get("contact_person", ""),
        "phone": f.get("phone", ""), "email": f.get("email", ""),
        "address": f.get("address", ""), "epf_account_no": f.get("epf_account_no", ""),
        "esic_account_no": f.get("esic_account_no", ""),
        "opening_balance": f.get("opening_balance", 0) or 0,
        "opening_balance_type": f.get("opening_balance_type", "dr"),
    })
    flash(f"Client '{f['name']}' added.", "success")
    return redirect(url_for("clients"))


@app.route("/clients/template")
def clients_template():
    csv_data = ("Name,Contact Person,Phone,EPF No,ESIC No,Opening Balance,Dr/Cr\n"
                "ABC Industries,Ramesh Kumar,9876543210,MH/BAN/0012345,31000123456,0,Dr\n"
                "XYZ Traders,Suresh Rao,9123456780,MH/PUN/0067890,31000678901,5000,Cr\n")
    return Response(csv_data, mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=clients_template.csv"})


@app.route("/clients/bulk", methods=["POST"])
def clients_bulk():
    f = request.files.get("csvfile")
    if not f or not f.filename:
        flash("Please choose a CSV file.", "error")
        return redirect(url_for("clients"))
    try:
        res = clients_svc.bulk_create_clients(f.read())
        msg = f"Created {res['created']} client(s)."
        if res["skipped"]:
            msg += f" Skipped {len(res['skipped'])} already-existing: {', '.join(res['skipped'][:10])}"
        flash(msg, "success")
    except Exception as e:
        flash(f"Upload error: {e}", "error")
    return redirect(url_for("clients"))


@app.route("/clients/<cid>/edit", methods=["POST"])
def clients_edit(cid):
    f = request.form
    clients_svc.update_client(cid, {
        "name": f["name"], "contact_person": f.get("contact_person", ""),
        "phone": f.get("phone", ""), "email": f.get("email", ""),
        "address": f.get("address", ""), "epf_account_no": f.get("epf_account_no", ""),
        "esic_account_no": f.get("esic_account_no", ""),
    })
    flash("Client updated.", "success")
    return redirect(url_for("client_detail", cid=cid))


@app.route("/clients/<cid>/toggle", methods=["POST"])
def clients_toggle(cid):
    c = clients_svc.get_client(cid)
    if c and c.get("is_active"):
        clients_svc.deactivate_client(cid)
        flash("Client deactivated.", "success")
    else:
        clients_svc.reactivate_client(cid)
        flash("Client reactivated.", "success")
    return redirect(url_for("clients"))


@app.route("/clients/<cid>")
def client_detail(cid):
    c = clients_svc.get_client(cid)
    if not c:
        flash("Client not found.", "error")
        return redirect(url_for("clients"))
    ledger = ledger_svc.get_client_ledger(cid)
    txns, closing = ([], 0.0)
    if ledger:
        txns, closing = ledger_svc.get_ledger_transactions(ledger["id"])
    outstanding = clients_svc.get_client_outstanding(cid)
    shorts = [s for s in report_svc.get_short_payments() if s.get("client_id") == cid]
    excess = [e for e in report_svc.get_excess_payments() if e.get("client_id") == cid]
    return render_template("client_detail.html", c=c, txns=txns, closing=closing,
                           outstanding=outstanding, shorts=shorts, excess=excess)


# ═══════════════════════════════════════════════════════════════════════════════
# RECEIPTS
# ═══════════════════════════════════════════════════════════════════════════════
@app.route("/receipts")
def receipts():
    cl = clients_svc.get_all_clients()
    banks = ledger_svc.get_bank_ledgers() + ledger_svc.get_cash_ledgers()
    vlist = voucher_svc.get_vouchers(voucher_type="receipt")
    for v in vlist:
        v["amount"] = sum(e.get("debit", 0) for e in v.get("entries", []))
    return render_template("receipts.html", clients=cl, banks=banks, vouchers=vlist)


@app.route("/receipts/add", methods=["POST"])
def receipts_add():
    f = request.form
    bank = ledger_svc.get_ledger(f["bank_ledger_id"])
    try:
        res = voucher_svc.create_receipt({
            "client_id": f["client_id"],
            "date": _parse_date(f.get("date")),
            "amount": float(f.get("amount", 0) or 0),
            "payment_mode": f.get("payment_mode", "bank_transfer"),
            "reference_no": f.get("reference_no", ""),
            "narration": f.get("narration", ""),
            "bank_ledger_id": bank["id"],
            "bank_ledger_name": bank["name"],
        })
        msg = "Receipt saved."
        if res.get("short_excess_info"):
            info = res["short_excess_info"]
            msg += f" {info['type'].title()} of {fmt_currency(info['amount'])} recorded."
        flash(msg, "success")
    except Exception as e:
        flash(f"Error: {e}", "error")
    return redirect(url_for("receipts"))


@app.route("/receipts/<vid>/edit", methods=["POST"])
def receipts_edit(vid):
    f = request.form
    bank = ledger_svc.get_ledger(f["bank_ledger_id"])
    try:
        voucher_svc.update_receipt(vid, {
            "client_id": f["client_id"],
            "date": _parse_date(f.get("date")),
            "amount": float(f.get("amount", 0) or 0),
            "payment_mode": f.get("payment_mode", "bank_transfer"),
            "reference_no": f.get("reference_no", ""),
            "narration": f.get("narration", ""),
            "bank_ledger_id": bank["id"],
            "bank_ledger_name": bank["name"],
        })
        flash("Receipt updated.", "success")
    except Exception as e:
        flash(f"Error: {e}", "error")
    return redirect(url_for("receipts"))


@app.route("/receipts/<vid>/delete", methods=["POST"])
def receipts_delete(vid):
    voucher_svc.delete_voucher(vid)
    flash("Receipt deleted.", "success")
    return redirect(url_for("receipts"))


# ═══════════════════════════════════════════════════════════════════════════════
# PAYMENTS
# ═══════════════════════════════════════════════════════════════════════════════
# Groups that can appear on the "Pay To" side of a Payment voucher.
# sundry_debtor is included so you can REFUND an excess back to a client
# (DR Client / CR Bank).
PAYABLE_GROUPS = ["expense", "indirect_expense", "direct_expense",
                  "epf_payable", "esic_payable", "current_liability",
                  "sundry_creditor", "sundry_debtor"]


def _expense_ledgers():
    out = []
    for g in PAYABLE_GROUPS:
        out += ledger_svc.get_all_ledgers(g)
    return out


@app.route("/payments")
def payments():
    banks = ledger_svc.get_bank_ledgers() + ledger_svc.get_cash_ledgers()
    exps = _expense_ledgers()
    vlist = voucher_svc.get_vouchers(voucher_type="payment")
    for v in vlist:
        v["amount"] = sum(e.get("credit", 0) for e in v.get("entries", []))
    return render_template("payments.html", banks=banks, expenses=exps, vouchers=vlist)


@app.route("/payments/add", methods=["POST"])
def payments_add():
    f = request.form
    bank = ledger_svc.get_ledger(f["bank_ledger_id"])
    exp = ledger_svc.get_ledger(f["expense_ledger_id"])
    try:
        voucher_svc.create_payment({
            "bank_ledger_id": bank["id"], "bank_ledger_name": bank["name"],
            "expense_ledger_id": exp["id"], "expense_ledger_name": exp["name"],
            "amount": float(f.get("amount", 0) or 0),
            "date": _parse_date(f.get("date")),
            "payment_mode": f.get("payment_mode", "bank_transfer"),
            "reference_no": f.get("reference_no", ""),
            "narration": f.get("narration", ""),
        })
        flash("Payment saved.", "success")
    except Exception as e:
        flash(f"Error: {e}", "error")
    return redirect(url_for("payments"))


@app.route("/payments/<vid>/edit", methods=["POST"])
def payments_edit(vid):
    f = request.form
    bank = ledger_svc.get_ledger(f["bank_ledger_id"])
    exp = ledger_svc.get_ledger(f["expense_ledger_id"])
    try:
        voucher_svc.update_payment(vid, {
            "bank_ledger_id": bank["id"], "bank_ledger_name": bank["name"],
            "expense_ledger_id": exp["id"], "expense_ledger_name": exp["name"],
            "amount": float(f.get("amount", 0) or 0),
            "date": _parse_date(f.get("date")),
            "reference_no": f.get("reference_no", ""),
            "narration": f.get("narration", ""),
        })
        flash("Payment updated.", "success")
    except Exception as e:
        flash(f"Error: {e}", "error")
    return redirect(url_for("payments"))


@app.route("/payments/<vid>/delete", methods=["POST"])
def payments_delete(vid):
    voucher_svc.delete_voucher(vid)
    flash("Payment deleted.", "success")
    return redirect(url_for("payments"))


# ═══════════════════════════════════════════════════════════════════════════════
# JOURNAL
# ═══════════════════════════════════════════════════════════════════════════════
@app.route("/journal")
def journal():
    ledgers = ledger_svc.get_all_ledgers()
    vlist = voucher_svc.get_vouchers(voucher_type="journal")
    for v in vlist:
        v["total_dr"] = sum(e.get("debit", 0) for e in v.get("entries", []))
    return render_template("journal.html", ledgers=ledgers, vouchers=vlist)


def _collect_journal_entries(f):
    """Form sends parallel arrays: ledger_id[], debit[], credit[]."""
    ids = f.getlist("ledger_id[]")
    debits = f.getlist("debit[]")
    credits = f.getlist("credit[]")
    entries = []
    for i, lid in enumerate(ids):
        if not lid:
            continue
        led = ledger_svc.get_ledger(lid)
        dr = float(debits[i] or 0) if i < len(debits) else 0
        cr = float(credits[i] or 0) if i < len(credits) else 0
        if dr == 0 and cr == 0:
            continue
        entries.append({"ledger_id": lid, "ledger_name": led["name"] if led else "",
                        "debit": dr, "credit": cr})
    return entries


@app.route("/journal/add", methods=["POST"])
def journal_add():
    f = request.form
    entries = _collect_journal_entries(f)
    try:
        voucher_svc.create_journal({
            "date": _parse_date(f.get("date")),
            "narration": f.get("narration", ""),
            "entries": entries,
        })
        flash("Journal entry saved.", "success")
    except Exception as e:
        flash(f"Error: {e}", "error")
    return redirect(url_for("journal"))


@app.route("/journal/<vid>/edit", methods=["POST"])
def journal_edit(vid):
    f = request.form
    entries = _collect_journal_entries(f)
    try:
        voucher_svc.update_journal(vid, {
            "date": _parse_date(f.get("date")),
            "narration": f.get("narration", ""),
            "entries": entries,
        })
        flash("Journal entry updated.", "success")
    except Exception as e:
        flash(f"Error: {e}", "error")
    return redirect(url_for("journal"))


@app.route("/journal/<vid>/delete", methods=["POST"])
def journal_delete(vid):
    voucher_svc.delete_voucher(vid)
    flash("Journal entry deleted.", "success")
    return redirect(url_for("journal"))


# ═══════════════════════════════════════════════════════════════════════════════
# LEDGERS
# ═══════════════════════════════════════════════════════════════════════════════
GROUPS = {
    "bank": "Bank Account",
    "cash": "Cash-in-Hand",
    "sundry_debtor": "Sundry Debtors",
    "sundry_creditor": "Sundry Creditors",
    "current_liability": "Current Liabilities",
    "epf_payable": "EPF Payable (Current Liability)",
    "esic_payable": "ESIC Payable (Current Liability)",
    "current_asset": "Current Assets",
    "indirect_income": "Indirect Income",
    "direct_income": "Direct Income",
    "indirect_expense": "Indirect Expenses",
    "direct_expense": "Direct Expenses",
    "income": "Income (General)",
    "expense": "Expenses (General)",
}


@app.route("/ledgers")
def ledgers():
    all_l = ledger_svc.get_all_ledgers()
    for l in all_l:
        l["balance"] = ledger_svc.get_ledger_balance(l["id"])
    sel_id = request.args.get("view")
    txns, closing, sel = [], 0.0, None
    if sel_id:
        sel = ledger_svc.get_ledger(sel_id)
        txns, closing = ledger_svc.get_ledger_transactions(sel_id)
    return render_template("ledgers.html", ledgers=all_l, groups=GROUPS,
                           sel=sel, txns=txns, closing=closing)


@app.route("/api/ledger/<lid>/balance")
def api_ledger_balance(lid):
    """Live current balance for a ledger (used by Journal/Payment/Receipt forms)."""
    try:
        bal = ledger_svc.get_ledger_balance(lid)
        return jsonify({
            "balance": abs(bal),
            "type": "Dr" if bal >= 0 else "Cr",
            "formatted": fmt_currency(abs(bal)) + (" Dr" if bal >= 0 else " Cr"),
        })
    except Exception:
        return jsonify({"balance": 0, "type": "Dr", "formatted": "—"})


@app.route("/ledgers/add", methods=["POST"])
def ledgers_add():
    f = request.form
    if not f.get("name", "").strip():
        flash("Ledger name is required.", "error")
        return redirect(url_for("ledgers"))
    ledger_svc.create_ledger({
        "name": f["name"], "group": f["group"],
        "opening_balance": f.get("opening_balance", 0) or 0,
        "opening_balance_type": f.get("opening_balance_type", "dr"),
        "account_no": f.get("account_no", ""),
    })
    flash(f"Ledger '{f['name']}' created.", "success")
    return redirect(url_for("ledgers"))


# ═══════════════════════════════════════════════════════════════════════════════
# DAY BOOK
# ═══════════════════════════════════════════════════════════════════════════════
@app.route("/daybook")
def daybook():
    from_s = request.args.get("from") or date.today().strftime("%Y-%m-%d")
    to_s = request.args.get("to") or date.today().strftime("%Y-%m-%d")
    vtype = request.args.get("type", "All")
    kw = {"from_date": _parse_date(from_s),
          "to_date": datetime.combine(_parse_date(to_s).date(), datetime.max.time()),
          "limit": 500}
    if vtype != "All":
        kw["voucher_type"] = vtype.lower()
    vouchers = voucher_svc.get_vouchers(**kw)
    rcpt_total = sum(sum(e.get("debit", 0) for e in v.get("entries", []))
                     for v in vouchers if v.get("voucher_type") == "receipt")
    pay_total = sum(sum(e.get("credit", 0) for e in v.get("entries", []))
                    for v in vouchers if v.get("voucher_type") == "payment")
    for v in vouchers:
        v["amount"] = max(sum(e.get("debit", 0) for e in v.get("entries", [])),
                          sum(e.get("credit", 0) for e in v.get("entries", [])))
    return render_template("daybook.html", vouchers=vouchers, from_s=from_s, to_s=to_s,
                           vtype=vtype, rcpt_total=rcpt_total, pay_total=pay_total)


@app.route("/daybook/<vid>/delete", methods=["POST"])
def daybook_delete(vid):
    voucher_svc.delete_voucher(vid)
    flash("Entry deleted.", "success")
    return redirect(request.referrer or url_for("daybook"))


# ═══════════════════════════════════════════════════════════════════════════════
# REPORTS
# ═══════════════════════════════════════════════════════════════════════════════
@app.route("/reports")
def reports():
    tab = request.args.get("tab", "trial")
    today = date.today()
    fy_start = date(today.year if today.month >= 4 else today.year - 1, 4, 1)

    ctx = {"tab": tab, "fy_start": fy_start.strftime("%Y-%m-%d"),
           "today": today.strftime("%Y-%m-%d")}

    if tab == "trial":
        as_of = request.args.get("as_of") or today.strftime("%Y-%m-%d")
        tb = report_svc.get_trial_balance(
            datetime.combine(_parse_date(as_of).date(), datetime.max.time()))
        ctx["tb"] = tb
        ctx["as_of"] = as_of
        ctx["total_dr"] = sum(r["closing_dr"] for r in tb)
        ctx["total_cr"] = sum(r["closing_cr"] for r in tb)
    elif tab == "pl":
        pf = request.args.get("from") or fy_start.strftime("%Y-%m-%d")
        pt = request.args.get("to") or today.strftime("%Y-%m-%d")
        ctx["pl"] = report_svc.get_profit_loss(
            _parse_date(pf), datetime.combine(_parse_date(pt).date(), datetime.max.time()))
        ctx["pf"], ctx["pt"] = pf, pt
    elif tab in ("clients", "short", "excess"):
        balances = report_svc.get_client_balances()
        if tab == "short":
            ctx["rows"] = [b for b in balances if b["typ"] == "short"]
        elif tab == "excess":
            ctx["rows"] = [b for b in balances if b["typ"] == "excess"]
        else:
            ctx["rows"] = balances
        ctx["total_short"] = sum(b["balance"] for b in balances if b["typ"] == "short")
        ctx["total_excess"] = sum(b["balance"] for b in balances if b["typ"] == "excess")
    elif tab == "agewise":
        ctx["agewise"] = report_svc.get_outstanding_agewise()
        ctx["grand"] = sum(a["total"] for a in ctx["agewise"])

    return render_template("reports.html", **ctx)


# ═══════════════════════════════════════════════════════════════════════════════
# BANK RECONCILIATION  (separate from the books — compare only, never posts)
# ═══════════════════════════════════════════════════════════════════════════════
@app.route("/reconcile")
def reconcile_view():
    banks = ledger_svc.get_bank_ledgers() + ledger_svc.get_cash_ledgers()
    sel_id = request.args.get("bank") or (banks[0]["id"] if banks else None)
    today = date.today()
    from_s = request.args.get("from") or today.replace(day=1).strftime("%Y-%m-%d")
    to_s = request.args.get("to") or today.strftime("%Y-%m-%d")
    data = None
    if sel_id:
        data = reco_svc.reconcile(
            sel_id, _parse_date(from_s),
            datetime.combine(_parse_date(to_s).date(), datetime.max.time()))
    return render_template("reconcile.html", banks=banks, sel_id=sel_id,
                           data=data, from_s=from_s, to_s=to_s)


@app.route("/reconcile/upload", methods=["POST"])
def reconcile_upload():
    bank = request.form["bank_ledger_id"]
    f = request.files.get("statement")
    if not f or not f.filename:
        flash("Please choose a bank-statement CSV file.", "error")
        return redirect(url_for("reconcile_view", bank=bank))
    try:
        lines = reco_svc.parse_statement(f.read())
        n = reco_svc.save_statement(bank, lines)
        if n:
            flash(f"Uploaded {n} statement lines. (This is only for cross-checking — "
                  f"your books are untouched.)", "success")
        else:
            flash("No transaction rows detected. Check the CSV has Date + Deposit/Withdrawal columns.", "error")
    except Exception as e:
        flash(f"Could not read the file: {e}", "error")
    return redirect(url_for("reconcile_view", bank=bank))


@app.route("/reconcile/clear", methods=["POST"])
def reconcile_clear():
    bank = request.form["bank_ledger_id"]
    reco_svc.clear_statement(bank)
    flash("Uploaded statement cleared.", "success")
    return redirect(url_for("reconcile_view", bank=bank))


@app.route("/reconcile/template")
def reconcile_template():
    csv_data = ("Date,Description,Withdrawal,Deposit,Balance\n"
                "01-06-2026,NEFT CR XYZ COMPANY,,150000,150000\n"
                "01-06-2026,NEFT DR EPF,135000,,15000\n")
    return Response(csv_data, mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=bank_statement_template.csv"})


@app.route("/mis")
def mis():
    from datetime import timedelta
    today = date.today()
    period = request.args.get("period", "week")
    if period == "month":
        frm = today.replace(day=1)
    elif period == "fy":
        frm = date(today.year if today.month >= 4 else today.year - 1, 4, 1)
    elif period == "custom":
        frm = _parse_date(request.args.get("from")).date()
        today = _parse_date(request.args.get("to")).date()
    else:  # week
        period = "week"
        frm = today - timedelta(days=6)
    data = report_svc.get_mis_report(
        datetime.combine(frm, datetime.min.time()),
        datetime.combine(today, datetime.max.time()))
    return render_template("mis.html", m=data, period=period,
                           from_s=frm.strftime("%Y-%m-%d"), to_s=today.strftime("%Y-%m-%d"))


@app.route("/reports/se/<rid>/status", methods=["POST"])
def update_se_status(rid):
    f = request.form
    report_svc.update_short_excess_status(rid, f["status"], f.get("remarks", ""))
    flash("Status updated.", "success")
    return redirect(url_for("reports", tab=f.get("tab", "short")))


# ═══════════════════════════════════════════════════════════════════════════════
# SETTINGS
# ═══════════════════════════════════════════════════════════════════════════════
@app.route("/settings")
def settings():
    return render_template("settings.html", counts=admin_svc.count_all())


@app.route("/settings/backup")
def backup():
    payload = admin_svc.export_backup_json()
    fname = f"vaishnavi_backup_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
    return Response(payload, mimetype="application/json",
                    headers={"Content-Disposition": f"attachment; filename={fname}"})


@app.route("/settings/export-ca")
def export_ca():
    data = admin_svc.export_ca_zip()
    fname = f"vaishnavi_audit_{datetime.now().strftime('%Y%m%d')}.zip"
    return Response(data, mimetype="application/zip",
                    headers={"Content-Disposition": f"attachment; filename={fname}"})


@app.route("/settings/starter-setup", methods=["POST"])
def starter_setup():
    res = admin_svc.create_starter_setup()
    parts = []
    if res["ledgers"]:
        parts.append(f"{len(res['ledgers'])} ledgers created ({', '.join(res['ledgers'])})")
    if res["clients"]:
        parts.append(f"sample client '{res['clients'][0]}' created")
    if res["skipped"]:
        parts.append(f"skipped existing: {', '.join(res['skipped'])}")
    flash("Starter setup: " + ("; ".join(parts) if parts else "nothing to create."), "success")
    return redirect(url_for("settings"))


@app.route("/settings/reset-transactions", methods=["POST"])
def reset_transactions():
    if request.form.get("confirm", "").strip().upper() == "RESET TRANSACTIONS":
        res = admin_svc.reset_transactions()
        flash(f"Cleared — Vouchers: {res['vouchers']}, Short/Excess: {res['short_excess']}. "
              f"Clients & Ledgers kept.", "success")
    else:
        flash("Confirmation text did not match. Type exactly: RESET TRANSACTIONS", "error")
    return redirect(url_for("settings"))


@app.route("/settings/reset-all", methods=["POST"])
def reset_all():
    if request.form.get("confirm", "").strip().upper() == "DELETE EVERYTHING":
        res = admin_svc.reset_everything()
        flash(f"Full reset done — {sum(res.values())} records deleted.", "success")
    else:
        flash("Confirmation text did not match. Type exactly: DELETE EVERYTHING", "error")
    return redirect(url_for("settings"))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 8000)), debug=True)
