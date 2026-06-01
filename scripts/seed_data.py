"""
Run this once to populate MongoDB with system ledgers + 10 dummy clients
and realistic transactions for FY 2025-26.

Usage:
    python scripts/seed_data.py
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from datetime import datetime, timedelta
from database import get_db, ensure_indexes
from services.client_service import create_client
from services.ledger_service import create_ledger, get_client_ledger
from services.invoice_service import create_invoice, get_invoices
from services.voucher_service import create_receipt, create_payment
from bson import ObjectId

db = get_db()
ensure_indexes()


def clear_existing():
    print("⚠️  Clearing existing data...")
    for col in ["clients", "ledgers", "invoices", "vouchers", "short_excess_tracker", "counters"]:
        db[col].drop()
    print("   Done.\n")


def setup_system_ledgers():
    print("📒 Creating system ledgers...")
    system_ledgers = [
        {"name": "SBI Current Account", "group": "bank", "opening_balance": 125000, "opening_balance_type": "dr", "account_no": "XXXX1234"},
        {"name": "Cash in Hand", "group": "cash", "opening_balance": 8500, "opening_balance_type": "dr"},
        {"name": "EPF Payable", "group": "epf_payable", "opening_balance": 0, "opening_balance_type": "cr"},
        {"name": "ESIC Payable", "group": "esic_payable", "opening_balance": 0, "opening_balance_type": "cr"},
        {"name": "Professional Fee Income", "group": "income", "opening_balance": 0, "opening_balance_type": "cr"},
        {"name": "Office Rent", "group": "expense", "opening_balance": 0, "opening_balance_type": "dr"},
        {"name": "Staff Salary", "group": "expense", "opening_balance": 0, "opening_balance_type": "dr"},
        {"name": "Bank Charges", "group": "expense", "opening_balance": 0, "opening_balance_type": "dr"},
        {"name": "Telephone & Internet", "group": "expense", "opening_balance": 0, "opening_balance_type": "dr"},
        {"name": "Miscellaneous Expenses", "group": "expense", "opening_balance": 0, "opening_balance_type": "dr"},
    ]
    ledger_ids = {}
    for l in system_ledgers:
        lid = create_ledger(l)
        ledger_ids[l["name"]] = lid
        print(f"   ✅ {l['name']}")
    return ledger_ids


def create_clients():
    print("\n👥 Creating clients...")
    clients_data = [
        {
            "name": "Sunrise Garments Pvt Ltd",
            "contact_person": "Rajesh Sharma",
            "phone": "9823456781",
            "epf_account_no": "MH/BAN/0045231",
            "esic_account_no": "31000456780000",
            "opening_balance": 0,
        },
        {
            "name": "Krishna Engineering Works",
            "contact_person": "Suresh Patil",
            "phone": "9712345678",
            "epf_account_no": "MH/PUN/0023441",
            "esic_account_no": "31000234560000",
            "opening_balance": 2200,
            "opening_balance_type": "dr",  # they owe us from previous
        },
        {
            "name": "Mehta Brothers Trading Co",
            "contact_person": "Amit Mehta",
            "phone": "9634512378",
            "epf_account_no": "MH/MUM/0078923",
            "esic_account_no": "31000789230000",
            "opening_balance": 0,
        },
        {
            "name": "Patel Textiles",
            "contact_person": "Haresh Patel",
            "phone": "9512367890",
            "epf_account_no": "GJ/AHM/0034521",
            "esic_account_no": "61000345210000",
            "opening_balance": 1500,
            "opening_balance_type": "cr",  # excess held from previous
        },
        {
            "name": "Gupta Pharma Distributors",
            "contact_person": "Vikram Gupta",
            "phone": "9823412345",
            "epf_account_no": "MH/BAN/0056732",
            "esic_account_no": "31000567320000",
            "opening_balance": 0,
        },
        {
            "name": "Shree Balaji Constructions",
            "contact_person": "Dinesh Yadav",
            "phone": "9765432109",
            "epf_account_no": "MH/NAS/0012398",
            "esic_account_no": "31000123980000",
            "opening_balance": 0,
        },
        {
            "name": "Laxmi Food Products",
            "contact_person": "Priya Deshmukh",
            "phone": "9898765432",
            "epf_account_no": "MH/PUN/0067821",
            "esic_account_no": "31000678210000",
            "opening_balance": 3500,
            "opening_balance_type": "dr",  # short outstanding
        },
        {
            "name": "Jain Electronics",
            "contact_person": "Sanjay Jain",
            "phone": "9876123450",
            "epf_account_no": "MH/MUM/0089234",
            "esic_account_no": "31000892340000",
            "opening_balance": 0,
        },
        {
            "name": "Ramdas Agro Pvt Ltd",
            "contact_person": "Ramdas Kulkarni",
            "phone": "9712398765",
            "epf_account_no": "MH/AUR/0023451",
            "esic_account_no": "31000234510000",
            "opening_balance": 0,
        },
        {
            "name": "Modern Packaging Solutions",
            "contact_person": "Kavita Nair",
            "phone": "9654321098",
            "epf_account_no": "MH/BAN/0091234",
            "esic_account_no": "31000912340000",
            "opening_balance": 2000,
            "opening_balance_type": "cr",  # excess credit held
        },
    ]
    client_ids = {}
    for c in clients_data:
        cid = create_client(c)
        client_ids[c["name"]] = cid
        print(f"   ✅ {c['name']}")
    return client_ids


# Monthly billing amounts per client
BILLING = {
    "Sunrise Garments Pvt Ltd":      {"epf": 18500, "esic": 6800, "fee": 2500},
    "Krishna Engineering Works":     {"epf": 12000, "esic": 4200, "fee": 2000},
    "Mehta Brothers Trading Co":     {"epf": 32000, "esic": 11200, "fee": 3500},
    "Patel Textiles":                {"epf": 22000, "esic": 7700, "fee": 2500},
    "Gupta Pharma Distributors":     {"epf": 8500,  "esic": 3000, "fee": 1500},
    "Shree Balaji Constructions":    {"epf": 45000, "esic": 15750, "fee": 5000},
    "Laxmi Food Products":           {"epf": 14000, "esic": 4900, "fee": 2000},
    "Jain Electronics":              {"epf": 28000, "esic": 9800, "fee": 3000},
    "Ramdas Agro Pvt Ltd":           {"epf": 9500,  "esic": 3325, "fee": 1500},
    "Modern Packaging Solutions":    {"epf": 19500, "esic": 6825, "fee": 2500},
}


def create_invoices(client_ids):
    print("\n🧾 Creating invoices (April & May 2025)...")
    invoice_ids = {}
    for month in ["2025-04", "2025-05"]:
        invoice_ids[month] = {}
        due_map = {"2025-04": datetime(2025, 4, 20), "2025-05": datetime(2025, 5, 20)}
        for name, cid in client_ids.items():
            b = BILLING[name]
            inv_id = create_invoice({
                "client_id": cid,
                "billing_month": month,
                "epf_amount": b["epf"],
                "esic_amount": b["esic"],
                "professional_fee": b["fee"],
                "due_date": due_map[month],
            })
            invoice_ids[month][name] = inv_id
    print("   ✅ Invoices created for all clients for April & May 2025")
    return invoice_ids


def create_receipts(client_ids, invoice_ids, ledger_ids):
    """Create receipts with realistic short/excess scenarios."""
    print("\n💰 Creating receipts...")
    bank_id = ledger_ids["SBI Current Account"]

    def total(name):
        b = BILLING[name]
        return b["epf"] + b["esic"] + b["fee"]

    scenarios = [
        # April receipts (all paid)
        {"name": "Sunrise Garments Pvt Ltd",   "month": "2025-04", "received": None, "date": datetime(2025, 4, 15), "ref": "NEFT01234"},
        {"name": "Krishna Engineering Works",  "month": "2025-04", "received": None, "date": datetime(2025, 4, 16), "ref": "NEFT01235"},
        {"name": "Mehta Brothers Trading Co",  "month": "2025-04", "received": None, "date": datetime(2025, 4, 17), "ref": "NEFT01236"},
        {"name": "Patel Textiles",             "month": "2025-04", "received": None, "date": datetime(2025, 4, 18), "ref": "NEFT01237"},
        {"name": "Gupta Pharma Distributors",  "month": "2025-04", "received": None, "date": datetime(2025, 4, 18), "ref": "NEFT01238"},
        {"name": "Shree Balaji Constructions", "month": "2025-04", "received": None, "date": datetime(2025, 4, 19), "ref": "NEFT01239"},
        {"name": "Laxmi Food Products",        "month": "2025-04", "received": None, "date": datetime(2025, 4, 19), "ref": "NEFT01240"},
        {"name": "Jain Electronics",           "month": "2025-04", "received": None, "date": datetime(2025, 4, 20), "ref": "NEFT01241"},
        {"name": "Ramdas Agro Pvt Ltd",        "month": "2025-04", "received": None, "date": datetime(2025, 4, 20), "ref": "NEFT01242"},
        {"name": "Modern Packaging Solutions", "month": "2025-04", "received": None, "date": datetime(2025, 4, 21), "ref": "NEFT01243"},
        # May receipts (mixed scenarios)
        {"name": "Sunrise Garments Pvt Ltd",   "month": "2025-05", "received": None,           "date": datetime(2025, 5, 15), "ref": "UTR05201"},  # exact
        {"name": "Krishna Engineering Works",  "month": "2025-05", "received": lambda t: t - 2000, "date": datetime(2025, 5, 16), "ref": "UTR05202"},  # short
        {"name": "Mehta Brothers Trading Co",  "month": "2025-05", "received": None,           "date": datetime(2025, 5, 16), "ref": "UTR05203"},  # exact
        {"name": "Patel Textiles",             "month": "2025-05", "received": lambda t: t + 500, "date": datetime(2025, 5, 17), "ref": "UTR05204"},  # excess
        {"name": "Gupta Pharma Distributors",  "month": "2025-05", "received": None,           "date": datetime(2025, 5, 18), "ref": "UTR05205"},  # exact
        {"name": "Shree Balaji Constructions", "month": "2025-05", "received": lambda t: t - 5000, "date": datetime(2025, 5, 19), "ref": "UTR05206"},  # short
        {"name": "Laxmi Food Products",        "month": "2025-05", "received": None,           "date": datetime(2025, 5, 20), "ref": "UTR05207"},  # exact
        {"name": "Jain Electronics",           "month": "2025-05", "received": lambda t: t + 800, "date": datetime(2025, 5, 21), "ref": "UTR05208"},  # excess
        # Ramdas and Modern Packaging: not yet paid for May (outstanding)
    ]

    for s in scenarios:
        name = s["name"]
        cid = client_ids[name]
        inv_id = invoice_ids[s["month"]][name]
        t = total(name)
        received = s["received"](t) if callable(s.get("received")) else (s["received"] if s["received"] else t)

        result = create_receipt({
            "client_id": cid,
            "invoice_id": inv_id,
            "date": s["date"],
            "amount": received,
            "payment_mode": "bank_transfer",
            "reference_no": s["ref"],
            "narration": f"Receipt from {name} for {s['month']}",
            "bank_ledger_id": bank_id,
            "bank_ledger_name": "SBI Current Account",
        })
        tag = ""
        if result.get("short_excess_info"):
            info = result["short_excess_info"]
            tag = f"  ⚠️ {info['type'].upper()} ₹{info['amount']:,.0f}"
        print(f"   ✅ {name[:30]:<30} {s['month']}  ₹{received:>10,.0f}{tag}")


def create_expense_payments(ledger_ids):
    print("\n💸 Creating expense payments...")
    bank_id = ledger_ids["SBI Current Account"]
    expenses = [
        {"exp": "Office Rent",         "amount": 15000, "date": datetime(2025, 4, 1),  "ref": "CHQ001", "narration": "Office rent for April 2025"},
        {"exp": "Staff Salary",        "amount": 25000, "date": datetime(2025, 4, 30), "ref": "NEFT999", "narration": "Salary - April 2025"},
        {"exp": "Office Rent",         "amount": 15000, "date": datetime(2025, 5, 1),  "ref": "CHQ002", "narration": "Office rent for May 2025"},
        {"exp": "Bank Charges",        "amount": 450,   "date": datetime(2025, 5, 31), "ref": "AUTO",   "narration": "Bank service charges May 2025"},
        {"exp": "Telephone & Internet","amount": 1800,  "date": datetime(2025, 5, 10), "ref": "AUTO2",  "narration": "Internet bill May 2025"},
        {"exp": "Staff Salary",        "amount": 25000, "date": datetime(2025, 5, 31), "ref": "NEFT998", "narration": "Salary - May 2025"},
    ]
    exp_ledger_ids = {}
    for l in db.ledgers.find({"group": {"$in": ["expense", "epf_payable", "esic_payable"]}}):
        exp_ledger_ids[l["name"]] = str(l["_id"])

    for e in expenses:
        exp_lid = exp_ledger_ids.get(e["exp"])
        if exp_lid:
            create_payment({
                "bank_ledger_id": bank_id,
                "bank_ledger_name": "SBI Current Account",
                "expense_ledger_id": exp_lid,
                "expense_ledger_name": e["exp"],
                "amount": e["amount"],
                "date": e["date"],
                "payment_mode": "bank_transfer",
                "reference_no": e["ref"],
                "narration": e["narration"],
            })
            print(f"   ✅ {e['narration'][:45]:<45}  ₹{e['amount']:>8,.0f}")


def main():
    print("=" * 65)
    print("  Vaishnavi Tally — Seed Data Script")
    print("=" * 65)

    confirm = input("\nThis will CLEAR all existing data and reseed. Continue? (y/N): ")
    if confirm.lower() != "y":
        print("Aborted.")
        return

    clear_existing()
    ledger_ids = setup_system_ledgers()
    client_ids = create_clients()
    invoice_ids = create_invoices(client_ids)
    create_receipts(client_ids, invoice_ids, ledger_ids)
    create_expense_payments(ledger_ids)

    print("\n" + "=" * 65)
    print("✅ Seed data complete!")
    print(f"   Clients  : {db.clients.count_documents({})}")
    print(f"   Ledgers  : {db.ledgers.count_documents({})}")
    print(f"   Invoices : {db.invoices.count_documents({})}")
    print(f"   Vouchers : {db.vouchers.count_documents({})}")
    print(f"   Short/Exc: {db.short_excess_tracker.count_documents({})}")
    print("=" * 65)
    print("\nRun the app with: streamlit run app.py\n")


if __name__ == "__main__":
    main()
