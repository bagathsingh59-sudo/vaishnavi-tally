from database import get_db
from bson import ObjectId
from datetime import datetime
from services.counter_service import get_next_number
from services.ledger_service import get_client_ledger


def _fmt(doc: dict) -> dict:
    if not doc:
        return doc
    doc["id"] = str(doc.pop("_id"))
    for key in ("client_id", "invoice_id"):
        if key in doc and doc[key]:
            doc[key] = str(doc[key])
    for entry in doc.get("entries", []):
        if "ledger_id" in entry and entry["ledger_id"]:
            entry["ledger_id"] = str(entry["ledger_id"])
    return doc


def _build_entries(raw_entries: list) -> list:
    entries = []
    for e in raw_entries:
        entries.append({
            "ledger_id": ObjectId(e["ledger_id"]),
            "ledger_name": e.get("ledger_name", ""),
            "debit": float(e.get("debit", 0)),
            "credit": float(e.get("credit", 0)),
        })
    return entries


def create_receipt(data: dict) -> dict:
    """
    data keys: client_id, bank_ledger_id, bank_ledger_name, amount, date,
               payment_mode, reference_no, narration, invoice_id (optional)
    Returns: {voucher_id, short_excess_info}
    """
    db = get_db()
    amount = float(data["amount"])
    client_ledger = get_client_ledger(data["client_id"])
    if not client_ledger:
        raise ValueError("Client ledger not found")

    client = db.clients.find_one({"_id": ObjectId(data["client_id"])}, {"name": 1})
    client_name = client["name"] if client else "Client"

    voucher = {
        "voucher_no": get_next_number("RCP"),
        "voucher_type": "receipt",
        "date": data["date"],
        "narration": data.get("narration", f"Receipt from {client_name}"),
        "client_id": ObjectId(data["client_id"]),
        "invoice_id": ObjectId(data["invoice_id"]) if data.get("invoice_id") else None,
        "payment_mode": data.get("payment_mode", "bank_transfer"),
        "reference_no": data.get("reference_no", ""),
        "entries": [
            {
                "ledger_id": ObjectId(data["bank_ledger_id"]),
                "ledger_name": data.get("bank_ledger_name", "Bank"),
                "debit": amount,
                "credit": 0.0,
            },
            {
                "ledger_id": ObjectId(client_ledger["id"]),
                "ledger_name": client_name,
                "debit": 0.0,
                "credit": amount,
            },
        ],
        "created_at": datetime.utcnow(),
    }
    result = db.vouchers.insert_one(voucher)
    voucher_id = str(result.inserted_id)

    short_excess_info = {}
    if data.get("invoice_id"):
        from services.invoice_service import update_invoice_payment
        short_excess_info = update_invoice_payment(data["invoice_id"], amount, voucher_id)

    return {"voucher_id": voucher_id, "short_excess_info": short_excess_info}


def create_payment(data: dict) -> str:
    """
    data keys: bank_ledger_id, bank_ledger_name, expense_ledger_id, expense_ledger_name,
               amount, date, payment_mode, reference_no, narration, client_id (optional)
    """
    db = get_db()
    amount = float(data["amount"])

    voucher = {
        "voucher_no": get_next_number("PAY"),
        "voucher_type": "payment",
        "date": data["date"],
        "narration": data.get("narration", "Payment"),
        "client_id": ObjectId(data["client_id"]) if data.get("client_id") else None,
        "payment_mode": data.get("payment_mode", "bank_transfer"),
        "reference_no": data.get("reference_no", ""),
        "entries": [
            {
                "ledger_id": ObjectId(data["expense_ledger_id"]),
                "ledger_name": data.get("expense_ledger_name", "Expense"),
                "debit": amount,
                "credit": 0.0,
            },
            {
                "ledger_id": ObjectId(data["bank_ledger_id"]),
                "ledger_name": data.get("bank_ledger_name", "Bank"),
                "debit": 0.0,
                "credit": amount,
            },
        ],
        "created_at": datetime.utcnow(),
    }
    result = db.vouchers.insert_one(voucher)
    return str(result.inserted_id)


def create_journal(data: dict) -> str:
    """
    data keys: date, narration, entries: [{ledger_id, ledger_name, debit, credit}]
    Validates DR == CR before saving.
    """
    db = get_db()
    entries = _build_entries(data["entries"])
    total_dr = sum(e["debit"] for e in entries)
    total_cr = sum(e["credit"] for e in entries)
    if abs(total_dr - total_cr) > 0.01:
        raise ValueError(f"Journal entries do not balance: DR={total_dr:.2f}, CR={total_cr:.2f}")

    voucher = {
        "voucher_no": get_next_number("JRN"),
        "voucher_type": "journal",
        "date": data["date"],
        "narration": data.get("narration", ""),
        "client_id": None,
        "entries": entries,
        "created_at": datetime.utcnow(),
    }
    result = db.vouchers.insert_one(voucher)
    return str(result.inserted_id)


def get_vouchers(
    voucher_type: str = None,
    client_id: str = None,
    from_date: datetime = None,
    to_date: datetime = None,
    limit: int = 200,
) -> list:
    db = get_db()
    query = {}
    if voucher_type:
        query["voucher_type"] = voucher_type
    if client_id:
        query["client_id"] = ObjectId(client_id)
    if from_date or to_date:
        date_f = {}
        if from_date:
            date_f["$gte"] = from_date
        if to_date:
            date_f["$lte"] = to_date
        query["date"] = date_f

    docs = list(db.vouchers.find(query).sort("date", -1).limit(limit))
    names = {str(c["_id"]): c["name"] for c in db.clients.find({}, {"name": 1})}
    result = []
    for v in docs:
        v = _fmt(v)
        if v.get("client_id"):
            v["client_name"] = names.get(v["client_id"], "")
        result.append(v)
    return result


def get_voucher(voucher_id: str) -> dict | None:
    db = get_db()
    doc = db.vouchers.find_one({"_id": ObjectId(voucher_id)})
    return _fmt(doc) if doc else None


def delete_voucher(voucher_id: str) -> bool:
    """Delete a voucher and any short/excess tracker records linked to it."""
    db = get_db()
    db.short_excess_tracker.delete_many({"voucher_id": ObjectId(voucher_id)})
    result = db.vouchers.delete_one({"_id": ObjectId(voucher_id)})
    return result.deleted_count > 0


def update_receipt(voucher_id: str, data: dict) -> bool:
    """Update an existing receipt voucher in place (keeps voucher_no)."""
    db = get_db()
    amount = float(data["amount"])
    client_ledger = get_client_ledger(data["client_id"])
    if not client_ledger:
        raise ValueError("Client ledger not found")
    client = db.clients.find_one({"_id": ObjectId(data["client_id"])}, {"name": 1})
    client_name = client["name"] if client else "Client"

    result = db.vouchers.update_one(
        {"_id": ObjectId(voucher_id)},
        {"$set": {
            "date": data["date"],
            "narration": data.get("narration", f"Receipt from {client_name}"),
            "client_id": ObjectId(data["client_id"]),
            "payment_mode": data.get("payment_mode", "bank_transfer"),
            "reference_no": data.get("reference_no", ""),
            "entries": [
                {"ledger_id": ObjectId(data["bank_ledger_id"]),
                 "ledger_name": data.get("bank_ledger_name", "Bank"),
                 "debit": amount, "credit": 0.0},
                {"ledger_id": ObjectId(client_ledger["id"]),
                 "ledger_name": client_name, "debit": 0.0, "credit": amount},
            ],
            "updated_at": datetime.utcnow(),
        }},
    )
    return result.modified_count > 0


def update_payment(voucher_id: str, data: dict) -> bool:
    db = get_db()
    amount = float(data["amount"])
    result = db.vouchers.update_one(
        {"_id": ObjectId(voucher_id)},
        {"$set": {
            "date": data["date"],
            "narration": data.get("narration", "Payment"),
            "reference_no": data.get("reference_no", ""),
            "entries": [
                {"ledger_id": ObjectId(data["expense_ledger_id"]),
                 "ledger_name": data.get("expense_ledger_name", "Expense"),
                 "debit": amount, "credit": 0.0},
                {"ledger_id": ObjectId(data["bank_ledger_id"]),
                 "ledger_name": data.get("bank_ledger_name", "Bank"),
                 "debit": 0.0, "credit": amount},
            ],
            "updated_at": datetime.utcnow(),
        }},
    )
    return result.modified_count > 0


def update_journal(voucher_id: str, data: dict) -> bool:
    db = get_db()
    entries = _build_entries(data["entries"])
    total_dr = sum(e["debit"] for e in entries)
    total_cr = sum(e["credit"] for e in entries)
    if abs(total_dr - total_cr) > 0.01:
        raise ValueError(f"Journal entries do not balance: DR={total_dr:.2f}, CR={total_cr:.2f}")
    result = db.vouchers.update_one(
        {"_id": ObjectId(voucher_id)},
        {"$set": {
            "date": data["date"],
            "narration": data.get("narration", ""),
            "entries": entries,
            "updated_at": datetime.utcnow(),
        }},
    )
    return result.modified_count > 0
