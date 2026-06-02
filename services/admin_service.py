from database import get_db


def count_all() -> dict:
    db = get_db()
    return {
        "clients":  db.clients.count_documents({}),
        "ledgers":  db.ledgers.count_documents({}),
        "vouchers": db.vouchers.count_documents({}),
        "short_excess": db.short_excess_tracker.count_documents({}),
        "invoices": db.invoices.count_documents({}),
    }


def reset_transactions() -> dict:
    """Delete all transactions (vouchers, short/excess, invoices, counters).
    KEEPS clients and ledgers (your masters / opening setup)."""
    db = get_db()
    result = {
        "vouchers":     db.vouchers.delete_many({}).deleted_count,
        "short_excess": db.short_excess_tracker.delete_many({}).deleted_count,
        "invoices":     db.invoices.delete_many({}).deleted_count,
    }
    db.counters.delete_many({})   # reset voucher numbering
    return result


def export_backup_json() -> str:
    """Full database dump as JSON (BSON-extended) — for safe-keeping / restore."""
    from bson.json_util import dumps
    db = get_db()
    out = {}
    for col in ["clients", "ledgers", "vouchers", "short_excess_tracker",
                "invoices", "counters"]:
        out[col] = list(db[col].find())
    return dumps(out, indent=2)


def export_ca_zip() -> bytes:
    """A ZIP of CSV files an accountant / CA needs to audit the books:
    Trial Balance, Day Book (all vouchers), Profit & Loss, Ledger list,
    and Client Balances."""
    import io, csv, zipfile
    from datetime import datetime
    from services import report_service, ledger_service
    db = get_db()

    def csv_str(header, rows):
        s = io.StringIO()
        w = csv.writer(s)
        w.writerow(header)
        w.writerows(rows)
        return s.getvalue()

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        # 1. Trial Balance
        tb = report_service.get_trial_balance(datetime.now())
        z.writestr("1_trial_balance.csv", csv_str(
            ["Ledger", "Group", "Closing Dr", "Closing Cr"],
            [[r["ledger_name"], r["group"], r["closing_dr"], r["closing_cr"]] for r in tb]))

        # 2. Day Book (all voucher entries)
        rows = []
        names = {str(c["_id"]): c["name"] for c in db.clients.find({}, {"name": 1})}
        for v in db.vouchers.find().sort("date", 1):
            d = v.get("date")
            ds = d.strftime("%d-%m-%Y") if hasattr(d, "strftime") else str(d)
            for e in v.get("entries", []):
                rows.append([ds, v.get("voucher_no", ""), v.get("voucher_type", ""),
                             e.get("ledger_name", ""), e.get("debit", 0), e.get("credit", 0),
                             v.get("narration", "")])
        z.writestr("2_day_book.csv", csv_str(
            ["Date", "Voucher No", "Type", "Ledger", "Debit", "Credit", "Narration"], rows))

        # 3. Profit & Loss (this FY)
        today = datetime.now()
        fy_start = datetime(today.year if today.month >= 4 else today.year - 1, 4, 1)
        pl = report_service.get_profit_loss(fy_start, today)
        pl_rows = [["INCOME", i["name"], i["amount"]] for i in pl["income"]]
        pl_rows.append(["", "TOTAL INCOME", pl["total_income"]])
        pl_rows += [["EXPENSE", e["name"], e["amount"]] for e in pl["expenses"]]
        pl_rows.append(["", "TOTAL EXPENSE", pl["total_expense"]])
        pl_rows.append(["", "NET PROFIT", pl["net_profit"]])
        z.writestr("3_profit_and_loss.csv", csv_str(["Section", "Head", "Amount"], pl_rows))

        # 4. Ledger list with balances
        led_rows = []
        for l in db.ledgers.find().sort("group", 1):
            bal = ledger_service.get_ledger_balance(str(l["_id"]))
            led_rows.append([l["name"], l.get("group", ""), l.get("opening_balance", 0),
                             l.get("opening_balance_type", "").upper(),
                             abs(bal), "Dr" if bal >= 0 else "Cr"])
        z.writestr("4_ledgers.csv", csv_str(
            ["Ledger", "Group", "Opening", "OB Type", "Current Balance", "Dr/Cr"], led_rows))

        # 5. Client Balances
        cb = report_service.get_client_balances()
        z.writestr("5_client_balances.csv", csv_str(
            ["Client", "Phone", "Balance", "Dr/Cr", "Status"],
            [[c["name"], c["phone"], c["balance"], c["bal_type"], c["typ"]] for c in cb]))

    buf.seek(0)
    return buf.getvalue()


def create_starter_setup() -> dict:
    """Create the standard ledgers + a sample client. Idempotent — skips names
    that already exist, so it is safe to click more than once."""
    from services import ledger_service, client_service

    db = get_db()
    created = {"ledgers": [], "clients": [], "skipped": []}

    existing = {l["name"].strip().lower() for l in db.ledgers.find({}, {"name": 1})}

    starter_ledgers = [
        ("SBI Current Account",  "bank",              "dr"),
        ("Cash-in-Hand",         "cash",              "dr"),
        ("EPF Payable",          "epf_payable",       "cr"),
        ("ESIC Payable",         "esic_payable",      "cr"),
        ("Excess Payment",       "current_liability", "cr"),
        ("Professional Fees",    "indirect_income",   "cr"),
        ("Other Works Charges",  "indirect_income",   "cr"),
        ("Salary Payable",       "expense",           "dr"),
    ]
    for name, group, obt in starter_ledgers:
        if name.lower() in existing:
            created["skipped"].append(name)
            continue
        ledger_service.create_ledger({
            "name": name, "group": group,
            "opening_balance": 0, "opening_balance_type": obt,
        })
        created["ledgers"].append(name)

    # Sample client (auto-creates its Sundry Debtor ledger)
    existing_clients = {c["name"].strip().lower() for c in db.clients.find({}, {"name": 1})}
    sample = "XYZ Company (Sample)"
    if sample.lower() not in existing_clients:
        client_service.create_client({
            "name": sample, "contact_person": "Sample Contact",
            "phone": "9000000000", "epf_account_no": "MH/SAMPLE/0001",
            "esic_account_no": "31000SAMPLE001",
        })
        created["clients"].append(sample)
    else:
        created["skipped"].append(sample)

    return created


def reset_everything() -> dict:
    """Full wipe — clients, ledgers, vouchers, short/excess, invoices, counters.
    Start completely fresh."""
    db = get_db()
    result = {}
    for col in ["clients", "ledgers", "vouchers", "short_excess_tracker",
                "invoices", "counters"]:
        result[col] = db[col].delete_many({}).deleted_count
    return result
