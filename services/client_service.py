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


def create_client(data: dict) -> str:
    db = get_db()
    payload = {
        "name": data["name"].strip(),
        "type": data.get("type", "sundry_debtor"),
        "contact_person": data.get("contact_person", ""),
        "phone": data.get("phone", ""),
        "email": data.get("email", ""),
        "address": data.get("address", ""),
        "opening_balance": float(data.get("opening_balance", 0)),
        "opening_balance_type": data.get("opening_balance_type", "dr"),
        "epf_account_no": data.get("epf_account_no", ""),
        "esic_account_no": data.get("esic_account_no", ""),
        "is_active": True,
        "created_at": datetime.utcnow(),
    }
    result = db.clients.insert_one(payload)
    cid = result.inserted_id

    # Auto-create linked ledger
    db.ledgers.insert_one({
        "name": payload["name"],
        "group": payload["type"],
        "client_id": cid,
        "opening_balance": payload["opening_balance"],
        "opening_balance_type": payload["opening_balance_type"],
        "is_active": True,
        "created_at": datetime.utcnow(),
    })
    return str(cid)


def bulk_create_clients(file_bytes: bytes) -> dict:
    """Create many clients from an uploaded CSV. Skips names that already exist."""
    import csv, io
    db = get_db()
    text = file_bytes.decode("utf-8", errors="ignore")
    reader = csv.DictReader(io.StringIO(text))
    existing = {c["name"].strip().lower() for c in db.clients.find({}, {"name": 1})}
    created, skipped = 0, []

    def g(row, *keys):
        for k in keys:
            for actual in row:
                if actual and actual.strip().lower() == k.lower():
                    return (row[actual] or "").strip()
        return ""

    for row in reader:
        name = g(row, "Name", "Client Name", "client")
        if not name:
            continue
        if name.lower() in existing:
            skipped.append(name)
            continue
        ob_raw = g(row, "Opening Balance", "Opening", "OB").replace(",", "")
        try:
            ob = float(ob_raw) if ob_raw else 0.0
        except ValueError:
            ob = 0.0
        obt = (g(row, "Dr/Cr", "Type", "OB Type") or "dr").lower()
        create_client({
            "name": name,
            "contact_person": g(row, "Contact Person", "Contact"),
            "phone": g(row, "Phone", "Mobile"),
            "email": g(row, "Email"),
            "address": g(row, "Address"),
            "epf_account_no": g(row, "EPF No", "EPF", "EPF Account No"),
            "esic_account_no": g(row, "ESIC No", "ESIC", "ESIC Account No"),
            "opening_balance": ob,
            "opening_balance_type": "cr" if obt.startswith("cr") else "dr",
        })
        existing.add(name.lower())
        created += 1
    return {"created": created, "skipped": skipped}


def get_all_clients(active_only: bool = True) -> list:
    db = get_db()
    query = {"is_active": True} if active_only else {}
    return [_fmt(c) for c in db.clients.find(query).sort("name", 1)]


def get_client(client_id: str) -> dict | None:
    db = get_db()
    doc = db.clients.find_one({"_id": ObjectId(client_id)})
    return _fmt(doc) if doc else None


def update_client(client_id: str, data: dict) -> bool:
    db = get_db()
    result = db.clients.update_one({"_id": ObjectId(client_id)}, {"$set": data})
    if "name" in data:
        db.ledgers.update_one({"client_id": ObjectId(client_id)}, {"$set": {"name": data["name"].strip()}})
    return result.modified_count > 0


def deactivate_client(client_id: str) -> bool:
    return update_client(client_id, {"is_active": False})


def reactivate_client(client_id: str) -> bool:
    return update_client(client_id, {"is_active": True})


def search_clients(query: str) -> list:
    db = get_db()
    rx = {"$regex": query, "$options": "i"}
    docs = db.clients.find({
        "is_active": True,
        "$or": [{"name": rx}, {"contact_person": rx}, {"phone": rx}]
    }).sort("name", 1)
    return [_fmt(c) for c in docs]


def get_client_outstanding(client_id: str) -> float:
    """Positive = client owes us (Dr balance). Negative = we owe client (excess held)."""
    from services.ledger_service import get_client_ledger, get_ledger_balance
    ledger = get_client_ledger(client_id)
    if not ledger:
        return 0.0
    return get_ledger_balance(ledger["id"])
