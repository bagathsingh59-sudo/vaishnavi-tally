"""Bank Reconciliation (BRS) — completely SEPARATE from the books.
Uploaded bank-statement lines live in their own collection (bank_statements)
and are only COMPARED against the bank ledger. Nothing here ever creates,
edits, or deletes a voucher."""
import csv
import io
from datetime import datetime

from bson import ObjectId
from dateutil import parser as dateparser

from database import get_db

DATE_KEYS = ["txn date", "transaction date", "tran date", "value date", "date", "posting date"]
DESC_KEYS = ["description", "narration", "particulars", "remarks", "transaction remarks", "details"]
DR_KEYS = ["withdrawal", "withdrawal amt", "withdrawal amt (inr)", "withdrawal amount",
           "debit", "debit amount", "dr"]
CR_KEYS = ["deposit", "deposit amt", "deposit amt (inr)", "deposit amount",
           "credit", "credit amount", "cr"]
BAL_KEYS = ["balance", "closing balance", "running balance"]


def _find_col(headers, keys):
    low = [h.strip().lower() for h in headers]
    for k in keys:                       # exact match first
        if k in low:
            return low.index(k)
    for k in keys:                       # then partial
        for i, h in enumerate(low):
            if k in h:
                return i
    return None


def _amt(cell):
    v = (cell or "").replace(",", "").replace("₹", "").replace("Cr", "").replace("Dr", "").strip()
    try:
        return abs(float(v)) if v else 0.0
    except ValueError:
        return 0.0


def parse_statement(file_bytes) -> list:
    """Parse a bank-statement CSV into normalised lines. Auto-detects the
    header row and common column names across SBI/HDFC/ICICI/Axis etc."""
    text = file_bytes.decode("utf-8", errors="ignore")
    rows = [r for r in csv.reader(io.StringIO(text)) if any((c or "").strip() for c in r)]
    if not rows:
        return []

    header_idx = 0
    for i, r in enumerate(rows[:20]):
        low = [(c or "").strip().lower() for c in r]
        has_date = any(any(k in c for k in DATE_KEYS) for c in low)
        has_amt = any(any(k in c for k in DR_KEYS + CR_KEYS) for c in low)
        if has_date and has_amt:
            header_idx = i
            break

    headers = rows[header_idx]
    di = _find_col(headers, DATE_KEYS)
    ci = _find_col(headers, DESC_KEYS)
    wi = _find_col(headers, DR_KEYS)
    cri = _find_col(headers, CR_KEYS)
    bi = _find_col(headers, BAL_KEYS)

    lines = []
    for r in rows[header_idx + 1:]:
        if di is None or di >= len(r):
            continue
        dval = (r[di] or "").strip()
        if not dval:
            continue
        try:
            d = dateparser.parse(dval, dayfirst=True)
        except (ValueError, OverflowError):
            continue
        lines.append({
            "date": d,
            "description": (r[ci].strip() if ci is not None and ci < len(r) else ""),
            "withdrawal": _amt(r[wi]) if wi is not None and wi < len(r) else 0.0,
            "deposit": _amt(r[cri]) if cri is not None and cri < len(r) else 0.0,
            "balance": _amt(r[bi]) if bi is not None and bi < len(r) else 0.0,
        })
    return lines


def save_statement(bank_ledger_id: str, lines: list) -> int:
    """Replace any previously uploaded statement for this bank ledger."""
    db = get_db()
    bid = ObjectId(bank_ledger_id)
    db.bank_statements.delete_many({"bank_ledger_id": bid})
    for ln in lines:
        doc = dict(ln)
        doc["bank_ledger_id"] = bid
        doc["uploaded_at"] = datetime.utcnow()
        db.bank_statements.insert_one(doc)
    return len(lines)


def clear_statement(bank_ledger_id: str) -> int:
    db = get_db()
    return db.bank_statements.delete_many(
        {"bank_ledger_id": ObjectId(bank_ledger_id)}).deleted_count


def reconcile(bank_ledger_id: str, from_date: datetime, to_date: datetime) -> dict:
    """Compare uploaded statement lines against the bank ledger's own
    transactions. Read-only — books are never modified."""
    from services.ledger_service import get_ledger_transactions
    db = get_db()
    bid = ObjectId(bank_ledger_id)

    stmt = list(db.bank_statements.find({"bank_ledger_id": bid}).sort("date", 1))
    stmt = [s for s in stmt
            if (not from_date or s["date"] >= from_date)
            and (not to_date or s["date"] <= to_date)]

    tx, closing = get_ledger_transactions(bank_ledger_id, from_date, to_date)
    for s in stmt:
        s["matched"] = False
    for t in tx:
        t["matched"] = False

    def near(d1, d2):
        return abs((d1 - d2).days) <= 5

    # statement deposit  ↔  tally debit (money INTO bank)
    for s in stmt:
        if s["deposit"] <= 0:
            continue
        for t in tx:
            if not t["matched"] and t["debit"] > 0 \
               and abs(t["debit"] - s["deposit"]) < 0.01 and near(t["date"], s["date"]):
                s["matched"] = t["matched"] = True
                break
    # statement withdrawal  ↔  tally credit (money OUT of bank)
    for s in stmt:
        if s["withdrawal"] <= 0:
            continue
        for t in tx:
            if not t["matched"] and t["credit"] > 0 \
               and abs(t["credit"] - s["withdrawal"]) < 0.01 and near(t["date"], s["date"]):
                s["matched"] = t["matched"] = True
                break

    summary = {
        "stmt_deposits": sum(s["deposit"] for s in stmt),
        "stmt_withdrawals": sum(s["withdrawal"] for s in stmt),
        "tally_in": sum(t["debit"] for t in tx),
        "tally_out": sum(t["credit"] for t in tx),
        "stmt_count": len(stmt),
        "tally_count": len(tx),
        "stmt_unmatched": sum(1 for s in stmt if not s["matched"]),
        "tally_unmatched": sum(1 for t in tx if not t["matched"]),
        "tally_closing": closing,
    }
    for s in stmt:
        s["id"] = str(s.pop("_id"))
        s.pop("bank_ledger_id", None)
    return {"statement": stmt, "tally": tx, "summary": summary}
