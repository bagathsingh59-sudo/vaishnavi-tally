from database import get_db
from datetime import datetime


def _get_fy() -> str:
    today = datetime.today()
    if today.month >= 4:
        return f"{str(today.year)[2:]}{str(today.year + 1)[2:]}"
    return f"{str(today.year - 1)[2:]}{str(today.year)[2:]}"


def get_next_number(prefix: str) -> str:
    db = get_db()
    key = f"{prefix}_{_get_fy()}"
    result = db.counters.find_one_and_update(
        {"_id": key},
        {"$inc": {"seq": 1}},
        upsert=True,
        return_document=True
    )
    return f"{prefix}-{_get_fy()}-{result['seq']:04d}"


def current_fy() -> str:
    return _get_fy()
