"""Pure-Python formatting helpers used as Jinja filters (no UI framework)."""
from datetime import datetime


def fmt_currency(amount) -> str:
    try:
        amount = float(amount or 0)
    except (TypeError, ValueError):
        amount = 0.0
    if amount < 0:
        return f"-₹{abs(amount):,.2f}"
    return f"₹{amount:,.2f}"


def fmt_date(dt) -> str:
    if not dt:
        return ""
    if isinstance(dt, str):
        return dt
    return dt.strftime("%d-%b-%Y")


def fmt_date_input(dt) -> str:
    """yyyy-mm-dd for <input type=date>."""
    if not dt:
        return datetime.today().strftime("%Y-%m-%d")
    if isinstance(dt, str):
        return dt
    return dt.strftime("%Y-%m-%d")


def fmt_month(month_str: str) -> str:
    try:
        return datetime.strptime(month_str, "%Y-%m").strftime("%b %Y")
    except Exception:
        return month_str or ""


def voucher_type_label(vtype: str) -> str:
    return {"receipt": "Receipt", "payment": "Payment",
            "journal": "Journal", "contra": "Contra"}.get(vtype, (vtype or "").title())
