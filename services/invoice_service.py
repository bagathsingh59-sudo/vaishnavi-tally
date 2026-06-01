from database import get_db
from bson import ObjectId
from datetime import datetime
from services.counter_service import get_next_number


def _fmt(doc: dict) -> dict:
    if not doc:
        return doc
    doc["id"] = str(doc.pop("_id"))
    if "client_id" in doc and doc["client_id"]:
        doc["client_id"] = str(doc["client_id"])
    return doc


def create_invoice(data: dict) -> str:
    db = get_db()
    epf = float(data.get("epf_amount", 0))
    esic = float(data.get("esic_amount", 0))
    fee = float(data.get("professional_fee", 0))
    total = epf + esic + fee

    invoice = {
        "invoice_no": get_next_number("INV"),
        "client_id": ObjectId(data["client_id"]),
        "billing_month": data["billing_month"],
        "epf_amount": epf,
        "esic_amount": esic,
        "professional_fee": fee,
        "total_amount": total,
        "paid_amount": 0.0,
        "balance_due": total,
        "status": "unpaid",
        "due_date": data.get("due_date"),
        "notes": data.get("notes", ""),
        "created_at": datetime.utcnow(),
    }
    result = db.invoices.insert_one(invoice)
    return str(result.inserted_id)


def get_invoices(
    client_id: str = None,
    status: str = None,
    billing_month: str = None,
) -> list:
    db = get_db()
    query = {}
    if client_id:
        query["client_id"] = ObjectId(client_id)
    if status:
        query["status"] = status
    if billing_month:
        query["billing_month"] = billing_month

    invoices = list(db.invoices.find(query).sort("created_at", -1))
    names = {str(c["_id"]): c["name"] for c in db.clients.find({}, {"name": 1})}
    result = []
    for inv in invoices:
        inv = _fmt(inv)
        inv["client_name"] = names.get(inv["client_id"], "Unknown")
        result.append(inv)
    return result


def get_invoice(invoice_id: str) -> dict | None:
    db = get_db()
    doc = db.invoices.find_one({"_id": ObjectId(invoice_id)})
    if not doc:
        return None
    doc = _fmt(doc)
    client = db.clients.find_one({"_id": ObjectId(doc["client_id"])}, {"name": 1})
    doc["client_name"] = client["name"] if client else "Unknown"
    return doc


def get_pending_invoices_for_client(client_id: str) -> list:
    return get_invoices(client_id=client_id, status=None)


def get_unpaid_invoices_for_client(client_id: str) -> list:
    db = get_db()
    docs = list(db.invoices.find({
        "client_id": ObjectId(client_id),
        "status": {"$in": ["unpaid", "partial"]}
    }).sort("billing_month", 1))
    return [_fmt(d) for d in docs]


def update_invoice_payment(invoice_id: str, received_amount: float, voucher_id: str) -> dict:
    """Update invoice after a receipt. Returns short/excess info dict or {}."""
    db = get_db()
    invoice = db.invoices.find_one({"_id": ObjectId(invoice_id)})
    if not invoice:
        return {}

    prev_paid = float(invoice.get("paid_amount", 0))
    balance_due = float(invoice.get("balance_due", invoice["total_amount"]))
    new_paid = prev_paid + received_amount
    new_balance = float(invoice["total_amount"]) - new_paid

    if new_balance > 0.01:
        status = "partial"
    elif new_balance < -0.01:
        status = "excess"
    else:
        status = "paid"
        new_balance = 0.0

    db.invoices.update_one(
        {"_id": ObjectId(invoice_id)},
        {"$set": {"paid_amount": new_paid, "balance_due": max(0, new_balance), "status": status}},
    )

    difference = received_amount - balance_due  # positive = excess, negative = short
    tracker_info = {}
    if abs(difference) > 0.01:
        tracker_type = "excess" if difference > 0 else "short"
        db.short_excess_tracker.insert_one({
            "client_id": invoice["client_id"],
            "invoice_id": ObjectId(invoice_id),
            "voucher_id": ObjectId(voucher_id),
            "billing_month": invoice["billing_month"],
            "invoiced_amount": invoice["total_amount"],
            "received_amount": received_amount,
            "difference": abs(difference),
            "type": tracker_type,
            "status": "pending",
            "remarks": "",
            "date": datetime.utcnow(),
        })
        tracker_info = {"type": tracker_type, "amount": abs(difference)}

    return tracker_info


def bulk_create_invoices(client_ids: list, billing_month: str, epf_map: dict, esic_map: dict, fee_map: dict) -> int:
    count = 0
    for cid in client_ids:
        create_invoice({
            "client_id": cid,
            "billing_month": billing_month,
            "epf_amount": epf_map.get(cid, 0),
            "esic_amount": esic_map.get(cid, 0),
            "professional_fee": fee_map.get(cid, 0),
        })
        count += 1
    return count
