from database import get_db
from bson import ObjectId
from datetime import datetime


def get_dashboard_stats() -> dict:
    db = get_db()
    today = datetime.utcnow()
    month_start = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    # This month receipts (sum of DR side in receipt vouchers)
    month_rcpt_agg = list(db.vouchers.aggregate([
        {"$match": {"voucher_type": "receipt", "date": {"$gte": month_start}}},
        {"$unwind": "$entries"},
        {"$match": {"entries.debit": {"$gt": 0}}},
        {"$group": {"_id": None, "total": {"$sum": "$entries.debit"}}},
    ]))
    month_receipts = month_rcpt_agg[0]["total"] if month_rcpt_agg else 0.0

    # Short payments pending
    short_pending = db.short_excess_tracker.count_documents({"type": "short", "status": "pending"})
    short_amount_agg = list(db.short_excess_tracker.aggregate([
        {"$match": {"type": "short", "status": "pending"}},
        {"$group": {"_id": None, "total": {"$sum": "$difference"}}},
    ]))
    short_amount = short_amount_agg[0]["total"] if short_amount_agg else 0.0

    # Excess held
    excess_agg = list(db.short_excess_tracker.aggregate([
        {"$match": {"type": "excess", "status": "pending"}},
        {"$group": {"_id": None, "total": {"$sum": "$difference"}}},
    ]))
    excess_amount = excess_agg[0]["total"] if excess_agg else 0.0

    # Total outstanding invoices
    outstanding_agg = list(db.invoices.aggregate([
        {"$match": {"status": {"$in": ["unpaid", "partial"]}}},
        {"$group": {"_id": None, "total": {"$sum": "$balance_due"}}},
    ]))
    total_outstanding = outstanding_agg[0]["total"] if outstanding_agg else 0.0

    # Bank balance (first bank ledger)
    bank_balance = 0.0
    bank_ledgers = list(db.ledgers.find({"group": "bank", "is_active": True}))
    for bl in bank_ledgers:
        from services.ledger_service import get_ledger_balance
        bank_balance += get_ledger_balance(str(bl["_id"]))

    # Cash balance
    cash_balance = 0.0
    cash_ledgers = list(db.ledgers.find({"group": "cash", "is_active": True}))
    for cl in cash_ledgers:
        from services.ledger_service import get_ledger_balance
        cash_balance += get_ledger_balance(str(cl["_id"]))

    # Recent vouchers
    recent = list(db.vouchers.find().sort("created_at", -1).limit(8))
    names = {str(c["_id"]): c["name"] for c in db.clients.find({}, {"name": 1})}
    recent_list = []
    for v in recent:
        recent_list.append({
            "date": v.get("date"),
            "voucher_no": v.get("voucher_no", ""),
            "type": v.get("voucher_type", ""),
            "narration": v.get("narration", ""),
            "client": names.get(str(v.get("client_id", "")), ""),
            "amount": sum(e.get("debit", 0) for e in v.get("entries", []) if e.get("debit", 0) > 0),
        })

    # This month payments (sum of CR side in payment vouchers — bank/cash credited)
    month_pay_agg = list(db.vouchers.aggregate([
        {"$match": {"voucher_type": "payment", "date": {"$gte": month_start}}},
        {"$unwind": "$entries"},
        {"$match": {"entries.credit": {"$gt": 0}}},
        {"$group": {"_id": None, "total": {"$sum": "$entries.credit"}}},
    ]))
    month_payments = month_pay_agg[0]["total"] if month_pay_agg else 0.0

    # Monthly collection chart data (receipts, last 12 months)
    monthly_data = list(db.vouchers.aggregate([
        {"$match": {"voucher_type": "receipt"}},
        {"$unwind": "$entries"},
        {"$match": {"entries.debit": {"$gt": 0}}},
        {"$group": {
            "_id": {"$dateToString": {"format": "%Y-%m", "date": "$date"}},
            "total": {"$sum": "$entries.debit"},
        }},
        {"$sort": {"_id": 1}},
        {"$limit": 12},
    ]))

    # Monthly payments chart data (last 12 months)
    monthly_pay = list(db.vouchers.aggregate([
        {"$match": {"voucher_type": "payment"}},
        {"$unwind": "$entries"},
        {"$match": {"entries.credit": {"$gt": 0}}},
        {"$group": {
            "_id": {"$dateToString": {"format": "%Y-%m", "date": "$date"}},
            "total": {"$sum": "$entries.credit"},
        }},
        {"$sort": {"_id": 1}},
        {"$limit": 12},
    ]))

    # Voucher counts by type
    type_counts = {}
    for row in db.vouchers.aggregate([
        {"$group": {"_id": "$voucher_type", "count": {"$sum": 1}}}
    ]):
        type_counts[row["_id"]] = row["count"]

    return {
        "month_receipts": month_receipts,
        "month_payments": month_payments,
        "total_outstanding": total_outstanding,
        "short_pending_count": short_pending,
        "short_pending_amount": short_amount,
        "excess_held": excess_amount,
        "bank_balance": bank_balance,
        "cash_balance": cash_balance,
        "total_clients": db.clients.count_documents({"is_active": True}),
        "total_vouchers": db.vouchers.count_documents({}),
        "recent_vouchers": recent_list,
        "monthly_chart": monthly_data,
        "monthly_payments": monthly_pay,
        "type_counts": type_counts,
    }


def get_trial_balance(as_of_date: datetime = None) -> list:
    db = get_db()
    ledgers = list(db.ledgers.find({"is_active": True}).sort("group", 1))
    result = []
    for ledger in ledgers:
        lid = ledger["_id"]
        ob = float(ledger.get("opening_balance", 0))
        ob_type = ledger.get("opening_balance_type", "dr")
        ob_dr = ob if ob_type == "dr" else 0.0
        ob_cr = ob if ob_type == "cr" else 0.0

        match_q = {"entries.ledger_id": lid}
        if as_of_date:
            match_q["date"] = {"$lte": as_of_date}

        agg = list(db.vouchers.aggregate([
            {"$match": match_q},
            {"$unwind": "$entries"},
            {"$match": {"entries.ledger_id": lid}},
            {"$group": {
                "_id": None,
                "total_dr": {"$sum": "$entries.debit"},
                "total_cr": {"$sum": "$entries.credit"},
            }},
        ]))
        total_dr = agg[0]["total_dr"] if agg else 0.0
        total_cr = agg[0]["total_cr"] if agg else 0.0

        closing_dr = ob_dr + total_dr
        closing_cr = ob_cr + total_cr
        net = closing_dr - closing_cr

        result.append({
            "ledger_name": ledger["name"],
            "group": ledger.get("group", ""),
            "opening_dr": ob_dr,
            "opening_cr": ob_cr,
            "total_dr": total_dr,
            "total_cr": total_cr,
            "closing_dr": closing_dr if net >= 0 else 0.0,
            "closing_cr": abs(net) if net < 0 else 0.0,
        })
    return result


INCOME_GROUPS = ["income", "indirect_income", "direct_income"]
EXPENSE_GROUPS = ["expense", "indirect_expense", "direct_expense"]


def get_profit_loss(from_date: datetime, to_date: datetime) -> dict:
    db = get_db()
    income_ledgers = list(db.ledgers.find({"group": {"$in": INCOME_GROUPS}, "is_active": True}))
    expense_ledgers = list(db.ledgers.find({"group": {"$in": EXPENSE_GROUPS}, "is_active": True}))

    def sum_ledger(ledger_id, side: str) -> float:
        agg = list(db.vouchers.aggregate([
            {"$match": {"entries.ledger_id": ledger_id, "date": {"$gte": from_date, "$lte": to_date}}},
            {"$unwind": "$entries"},
            {"$match": {"entries.ledger_id": ledger_id}},
            {"$group": {"_id": None, "total": {"$sum": f"$entries.{side}"}}},
        ]))
        return agg[0]["total"] if agg else 0.0

    income_items = []
    total_income = 0.0
    for l in income_ledgers:
        cr = sum_ledger(l["_id"], "credit")
        dr = sum_ledger(l["_id"], "debit")
        net = cr - dr
        income_items.append({"name": l["name"], "amount": net})
        total_income += net

    expense_items = []
    total_expense = 0.0
    for l in expense_ledgers:
        dr = sum_ledger(l["_id"], "debit")
        cr = sum_ledger(l["_id"], "credit")
        net = dr - cr
        expense_items.append({"name": l["name"], "amount": net})
        total_expense += net

    return {
        "income": income_items,
        "expenses": expense_items,
        "total_income": total_income,
        "total_expense": total_expense,
        "net_profit": total_income - total_expense,
    }


def get_short_payments(status: str = None) -> list:
    db = get_db()
    query = {"type": "short"}
    if status:
        query["status"] = status
    docs = list(db.short_excess_tracker.find(query).sort("date", -1))
    names = {str(c["_id"]): c["name"] for c in db.clients.find({}, {"name": 1})}
    result = []
    for d in docs:
        d["id"] = str(d.pop("_id"))
        d["client_id"] = str(d["client_id"])
        d["client_name"] = names.get(d["client_id"], "Unknown")
        result.append(d)
    return result


def get_excess_payments(status: str = None) -> list:
    db = get_db()
    query = {"type": "excess"}
    if status:
        query["status"] = status
    docs = list(db.short_excess_tracker.find(query).sort("date", -1))
    names = {str(c["_id"]): c["name"] for c in db.clients.find({}, {"name": 1})}
    result = []
    for d in docs:
        d["id"] = str(d.pop("_id"))
        d["client_id"] = str(d["client_id"])
        d["client_name"] = names.get(d["client_id"], "Unknown")
        result.append(d)
    return result


def update_short_excess_status(record_id: str, status: str, remarks: str = "") -> bool:
    db = get_db()
    result = db.short_excess_tracker.update_one(
        {"_id": ObjectId(record_id)},
        {"$set": {"status": status, "remarks": remarks}},
    )
    return result.modified_count > 0


def get_outstanding_agewise() -> list:
    db = get_db()
    today = datetime.utcnow()
    invoices = list(db.invoices.find({"status": {"$in": ["unpaid", "partial"]}}))
    names = {str(c["_id"]): c["name"] for c in db.clients.find({}, {"name": 1})}
    client_buckets: dict = {}

    for inv in invoices:
        cid = str(inv["client_id"])
        if cid not in client_buckets:
            client_buckets[cid] = {
                "client_name": names.get(cid, "Unknown"),
                "0_30": 0.0, "31_60": 0.0, "61_90": 0.0, "above_90": 0.0,
            }
        due = inv.get("due_date") or inv["created_at"]
        days_overdue = (today - due).days
        amt = float(inv.get("balance_due", 0))
        if days_overdue <= 30:
            client_buckets[cid]["0_30"] += amt
        elif days_overdue <= 60:
            client_buckets[cid]["31_60"] += amt
        elif days_overdue <= 90:
            client_buckets[cid]["61_90"] += amt
        else:
            client_buckets[cid]["above_90"] += amt

    result = list(client_buckets.values())
    for r in result:
        r["total"] = r["0_30"] + r["31_60"] + r["61_90"] + r["above_90"]
    return sorted(result, key=lambda x: -x["total"])
