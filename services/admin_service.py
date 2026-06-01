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


def reset_everything() -> dict:
    """Full wipe — clients, ledgers, vouchers, short/excess, invoices, counters.
    Start completely fresh."""
    db = get_db()
    result = {}
    for col in ["clients", "ledgers", "vouchers", "short_excess_tracker",
                "invoices", "counters"]:
        result[col] = db[col].delete_many({}).deleted_count
    return result
