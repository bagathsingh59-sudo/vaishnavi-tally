from datetime import datetime


def fmt_currency(amount: float) -> str:
    """Format as Indian Rupees: ₹1,23,456.00"""
    if amount < 0:
        return f"-₹{abs(amount):,.2f}"
    return f"₹{amount:,.2f}"


def fmt_date(dt) -> str:
    if not dt:
        return ""
    if isinstance(dt, str):
        return dt
    return dt.strftime("%d-%b-%Y")


def fmt_month(month_str: str) -> str:
    """'2025-05' → 'May 2025'"""
    try:
        return datetime.strptime(month_str, "%Y-%m").strftime("%b %Y")
    except Exception:
        return month_str


def balance_color(amount: float, balance_type: str = "dr") -> str:
    """Return HTML color string for balance display."""
    if balance_type == "dr":
        return "#dc3545"  # red for debit (they owe us)
    return "#28a745"  # green for credit


def voucher_type_label(vtype: str) -> str:
    labels = {
        "receipt": "Receipt",
        "payment": "Payment",
        "journal": "Journal",
        "contra": "Contra",
    }
    return labels.get(vtype, vtype.title())


TALLY_CSS = """
<style>
    .tally-header {
        background: linear-gradient(135deg, #003366 0%, #004080 100%);
        color: white;
        padding: 12px 20px;
        border-radius: 6px;
        margin-bottom: 16px;
        font-size: 1.1em;
        font-weight: 600;
        letter-spacing: 0.5px;
    }
    .balance-card {
        background: #f8f9fa;
        border: 1px solid #dee2e6;
        border-left: 4px solid #003366;
        border-radius: 6px;
        padding: 14px 18px;
        margin: 6px 0;
    }
    .dr-amt { color: #dc3545; font-weight: 700; }
    .cr-amt { color: #28a745; font-weight: 700; }
    .short-badge { background: #fff3cd; color: #856404; padding: 2px 8px; border-radius: 4px; font-size: 0.85em; }
    .excess-badge { background: #d1e7dd; color: #0f5132; padding: 2px 8px; border-radius: 4px; font-size: 0.85em; }
    .paid-badge { background: #d1e7dd; color: #0f5132; padding: 2px 8px; border-radius: 4px; font-size: 0.85em; }
    .unpaid-badge { background: #f8d7da; color: #842029; padding: 2px 8px; border-radius: 4px; font-size: 0.85em; }
    .partial-badge { background: #fff3cd; color: #856404; padding: 2px 8px; border-radius: 4px; font-size: 0.85em; }
    div[data-testid="stDataFrame"] thead th { background-color: #003366 !important; color: white !important; }
</style>
"""
