"""Customer segments from visits, spend and recency. One rule set, stored on the customer record."""

from collections import Counter
from datetime import timedelta

from app.domain.models import Customer, now
from app.services import db

VIP_VISITS, VIP_SPEND, AT_RISK_DAYS = 5, 5000.0, 45


def classify(c: Customer) -> str:
    if c.visits >= 2 and c.last_seen < now() - timedelta(days=AT_RISK_DAYS):
        return "at_risk"
    if c.visits >= VIP_VISITS and c.spend >= VIP_SPEND:
        return "vip"
    if c.visits >= 2:
        return "regular"
    return "new"


def refresh(store_id: str) -> dict[str, int]:
    """Nightly: recompute every customer's segment (at_risk depends on the calendar). Returns counts."""
    counts: Counter[str] = Counter()
    for d in db.customers(store_id).stream():
        c = Customer(**d.to_dict())
        seg = classify(c)
        counts[seg] += 1
        if seg != c.segment:
            d.reference.update({"segment": seg})
    return dict(counts)
