from database import get_db
from bson import ObjectId
from datetime import datetime


def _fmt(doc: dict) -> dict:
    if not doc:
        return doc
    doc["id"] = str(doc.pop("_id"))
    if "client_id" in doc and doc["client_id"]:
        doc["client_id"] = str(doc["client_id"])
    return doc


def create_ledger(data: dict) -> str:
    db = get_db()
    payload = {
        "name": data["name"].strip(),
        "group": data["group"],
        "opening_balance": float(data.get("opening_balance", 0)),
        "opening_balance_type": data.get("opening_balance_type", "dr"),
        "account_no": data.get("account_no", ""),
        "is_active": True,
        "created_at": datetime.utcnow(),
    }
    if data.get("client_id"):
        payload["client_id"] = ObjectId(data["client_id"])
    result = db.ledgers.insert_one(payload)
    return str(result.inserted_id)


def get_all_ledgers(group: str = None) -> list:
    db = get_db()
    query = {"is_active": True}
    if group:
        query["group"] = group
    return [_fmt(l) for l in db.ledgers.find(query).sort("name", 1)]


def get_ledger(ledger_id: str) -> dict | None:
    db = get_db()
    doc = db.ledgers.find_one({"_id": ObjectId(ledger_id)})
    return _fmt(doc) if doc else None


def get_client_ledger(client_id: str) -> dict | None:
    db = get_db()
    doc = db.ledgers.find_one({"client_id": ObjectId(client_id)})
    return _fmt(doc) if doc else None


def get_bank_ledgers() -> list:
    return get_all_ledgers("bank")


def get_cash_ledgers() -> list:
    return get_all_ledgers("cash")


def get_ledger_balance(ledger_id: str) -> float:
    _, balance = get_ledger_transactions(ledger_id)
    return balance


def get_ledger_transactions(
    ledger_id: str,
    from_date: datetime = None,
    to_date: datetime = None,
) -> tuple:
    """Returns (transactions_list, closing_balance).
    Positive closing_balance = Dr balance (they owe us / asset).
    """
    db = get_db()
    lid = ObjectId(ledger_id)
    ledger = db.ledgers.find_one({"_id": lid})
    if not ledger:
        return [], 0.0

    ob = float(ledger.get("opening_balance", 0))
    ob_type = ledger.get("opening_balance_type", "dr")
    balance = ob if ob_type == "dr" else -ob

    match_q = {"entries.ledger_id": lid}
    if from_date or to_date:
        date_filter = {}
        if from_date:
            date_filter["$gte"] = from_date
        if to_date:
            date_filter["$lte"] = to_date
        match_q["date"] = date_filter

    vouchers = list(db.vouchers.find(match_q).sort("date", 1))
    transactions = []
    for v in vouchers:
        for entry in v.get("entries", []):
            if entry.get("ledger_id") == lid:
                dr = float(entry.get("debit", 0))
                cr = float(entry.get("credit", 0))
                balance += dr - cr
                transactions.append({
                    "date": v["date"],
                    "voucher_no": v.get("voucher_no", ""),
                    "voucher_type": v.get("voucher_type", ""),
                    "narration": v.get("narration", ""),
                    "debit": dr,
                    "credit": cr,
                    "balance": abs(balance),
                    "balance_type": "Dr" if balance >= 0 else "Cr",
                })
    return transactions, balance


def ledger_name_map() -> dict:
    """Returns {id_str: name} for all active ledgers."""
    db = get_db()
    result = {}
    for l in db.ledgers.find({"is_active": True}):
        result[str(l["_id"])] = l["name"]
    return result
