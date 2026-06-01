import os
from pymongo import MongoClient

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

_client = None


def _mongo_uri() -> str:
    """
    URI resolution priority:
    1. Streamlit secrets (st.secrets) — for Streamlit Community Cloud
    2. Environment variables — for Docker / Railway / Render / local
    """
    try:
        import streamlit as st
        secrets = st.secrets
        if "MONGO_URI" in secrets:
            return secrets["MONGO_URI"]
        env = secrets.get("ENV", os.getenv("ENV", "development"))
        if env == "production" and "MONGO_URI_PROD" in secrets:
            return secrets["MONGO_URI_PROD"]
        if "MONGO_URI_DEV" in secrets:
            return secrets["MONGO_URI_DEV"]
    except Exception:
        pass

    env = os.getenv("ENV", "development")
    if env == "production":
        return os.getenv("MONGO_URI_PROD", "")
    return os.getenv("MONGO_URI_DEV", "mongodb://localhost:27017")


def _db_name() -> str:
    try:
        import streamlit as st
        if "DB_NAME" in st.secrets:
            return st.secrets["DB_NAME"]
    except Exception:
        pass
    return os.getenv("DB_NAME", "vaishnavi_tally")


def get_db():
    global _client
    if _client is None:
        _client = MongoClient(_mongo_uri(), serverSelectionTimeoutMS=5000)
    return _client[_db_name()]


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
