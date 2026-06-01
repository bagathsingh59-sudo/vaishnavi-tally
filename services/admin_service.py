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
