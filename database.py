import os
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

_client = None


def get_db():
    global _client
    if _client is None:
        env = os.getenv("ENV", "development")
        uri = os.getenv("MONGO_URI_PROD") if env == "production" else os.getenv("MONGO_URI_DEV", "mongodb://localhost:27017")
        _client = MongoClient(uri)
    return _client[os.getenv("DB_NAME", "vaishnavi_tally")]


def ensure_indexes():
    db = get_db()
    db.clients.create_index("name")
    db.clients.create_index("is_active")
    db.ledgers.create_index("group")
    db.ledgers.create_index("client_id")
    db.invoices.create_index([("client_id", 1), ("billing_month", 1)])
    db.invoices.create_index("status")
    db.vouchers.create_index([("date", -1)])
    db.vouchers.create_index("voucher_type")
    db.vouchers.create_index("client_id")
    db.vouchers.create_index("entries.ledger_id")
    db.short_excess_tracker.create_index([("client_id", 1), ("status", 1)])
