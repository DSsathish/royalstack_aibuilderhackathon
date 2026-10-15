"""Per-product demand forecasts stored in Firestore. The BigQuery ML job writes them; chat and reorder read them."""

import statistics

from app.domain.models import now
from app.services import db

HORIZON = 14


def put(store_id: str, product_id: str, *, daily: list[float], avg_daily: float, std_daily: float) -> None:
    db.forecasts(store_id).document(product_id).set({
        "product_id": product_id, "daily": [round(float(x), 2) for x in daily], "avg_daily": round(float(avg_daily), 2),
        "std_daily": round(float(std_daily), 2), "generated_at": now()})


def get(store_id: str, product_id: str) -> dict | None:
    doc = db.forecasts(store_id).document(product_id).get()
    return doc.to_dict() if doc.exists else None


def all(store_id: str) -> dict[str, dict]:
    return {d.id: d.to_dict() for d in db.forecasts(store_id).stream()}


def from_history(history: dict[str, list[float]], days: int | None = None) -> dict[str, dict]:
    """Fallback for products with too little history for ARIMA: flat forecast at the mean over `days` (zero-filled)."""
    out = {}
    for pid, series in history.items():
        n = days or len(series)
        filled = list(series) + [0.0] * max(0, n - len(series))
        avg = statistics.fmean(filled) if filled else 0.0
        std = statistics.pstdev(filled) if len(filled) > 1 else 0.0
        out[pid] = {"daily": [avg] * HORIZON, "avg_daily": avg, "std_daily": std}
    return out
