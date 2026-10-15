"""Owner-facing reads: overview tiles, inventory rows, demand signals, shrink candidates."""

import re
import time
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

from google.cloud.firestore_v1 import FieldFilter

from app.domain.models import now
from app.services import catalog, db, forecast

IST = timezone(timedelta(hours=5, minutes=30))


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower().strip())


def signals(store_id: str, days: int = 7) -> dict:
    since = now() - timedelta(days=days)
    docs = [d.to_dict() for d in db.demand_signals(store_id).where(filter=FieldFilter("created_at", ">=", since)).stream()]
    nc: dict[str, dict] = {}
    for s in docs:
        if s["type"] != "not_carried":
            continue
        key = _norm(s["query_text"])
        row = nc.setdefault(key, {"query": key, "count": 0, "source": "search"})
        row["count"] += 1
        if s.get("source") == "agent":
            row["source"] = "agent"
    oos = Counter(s["matched_product_id"] for s in docs if s["type"] == "out_of_stock" and s.get("matched_product_id"))
    out_of_stock = []
    for pid, count in oos.most_common():
        p = catalog.get_product(store_id, pid)
        out_of_stock.append({"product_id": pid, "name": p.name if p else pid, "count": count,
                             "lost_sales": round(count * (p.price if p else 0), 2)})
    not_carried = sorted(nc.values(), key=lambda r: (r["source"] != "agent", -r["count"]))
    return {"days": days, "not_carried": not_carried, "out_of_stock": out_of_stock}


def record_count(store_id: str, product_id: str, *, counted: int, by: str) -> None:
    inv = db.inventory(store_id).document(product_id).get()
    system = inv.to_dict()["on_hand"] if inv.exists else 0
    db.counts(store_id).document(product_id).set({"product_id": product_id, "counted": counted, "system": system, "by": by, "at": now()})


def shrink(store_id: str) -> list[dict]:
    out = []
    for d in db.counts(store_id).stream():
        c = d.to_dict()
        diff = c["counted"] - c["system"]
        if diff == 0:
            continue
        p = catalog.get_product(store_id, c["product_id"])
        out.append({"product_id": c["product_id"], "name": p.name if p else c["product_id"], "system": c["system"],
                    "counted": c["counted"], "difference": diff, "value": round(abs(diff) * (p.price if p else 0), 2)})
    return sorted(out, key=lambda r: -r["value"])


def inventory(store_id: str) -> list[dict]:
    fc = forecast.all(store_id)
    products, locations = catalog.product_map(store_id)   # one cached read; inventory streamed once below
    rows = []
    for d in db.inventory(store_id).stream():
        inv = d.to_dict()
        p = products.get(d.id)
        if not p:
            continue
        available = max(0, inv["on_hand"] - inv.get("reserved", 0))
        avg = fc.get(d.id, {}).get("avg_daily")
        cover = round(available / avg, 1) if avg else None
        if available == 0:
            status = "out"
        elif available <= inv.get("reorder_point", 0) or (cover is not None and cover < inv.get("lead_time_days", 3)):
            status = "low"
        elif avg == 0 and available > 0:
            status = "dead"
        elif cover is not None and cover > 60:
            status = "overstock"
        else:
            status = "ok"
        rows.append({"product_id": d.id, "name": p.name, "category": p.category, "price": p.price, "available": available,
                     "on_hand": inv["on_hand"], "reserved": inv.get("reserved", 0), "reorder_point": inv.get("reorder_point", 0),
                     "reorder_qty": inv.get("reorder_qty", 0), "supplier_id": inv.get("supplier_id", ""),
                     "lead_time_days": inv.get("lead_time_days", 3), "avg_daily": avg, "days_of_cover": cover, "status": status,
                     "aisle": locations[d.id].aisle if d.id in locations else ""})
    return sorted(rows, key=lambda r: ({"out": 0, "low": 1, "dead": 2, "overstock": 3, "ok": 4}[r["status"]], r["name"]))


_history_cache: dict[tuple[str, int], tuple[float, list[dict]]] = {}
HISTORY_TTL_S = 300


def daily_revenue_history(store_id: str, days: int) -> list[dict]:
    """Past days from BigQuery daily sales, cached 5 minutes (history only changes nightly). Empty when BigQuery is unavailable."""
    hit = _history_cache.get((store_id, days))
    if hit and time.time() - hit[0] < HISTORY_TTL_S:
        return hit[1]
    rows = _query_history(store_id, days)
    if rows:
        _history_cache[(store_id, days)] = (time.time(), rows)
    return rows


def _query_history(store_id: str, days: int) -> list[dict]:
    try:
        from google.cloud import bigquery

        from app.config import settings
        bq = bigquery.Client(project=settings.google_cloud_project)
        rows = bq.query(f"""
            SELECT day, SUM(qty * unit_price) AS revenue FROM `{settings.google_cloud_project}.retail.sales`
            WHERE store_id = @store AND day >= DATE_SUB(CURRENT_DATE('Asia/Kolkata'), INTERVAL @days DAY) AND day < CURRENT_DATE('Asia/Kolkata')
            GROUP BY day ORDER BY day""", job_config=bigquery.QueryJobConfig(query_parameters=[
                bigquery.ScalarQueryParameter("store", "STRING", store_id), bigquery.ScalarQueryParameter("days", "INT64", days)])).result()
        return [{"day": r.day.isoformat(), "revenue": float(r.revenue)} for r in rows]
    except Exception:
        return []


def overview(store_id: str) -> dict:
    start = datetime.now(IST).replace(hour=0, minute=0, second=0, microsecond=0)
    orders = [o.to_dict() for o in db.orders().where(filter=FieldFilter("store_id", "==", store_id))
              .where(filter=FieldFilter("created_at", ">=", start)).stream() if o.to_dict().get("status") in ("paid", "verified", "flagged")]
    by_channel: dict[str, float] = defaultdict(float)
    for o in orders:
        by_channel[o["channel"]] += o["total"]
    revenue = round(sum(by_channel.values()), 2)
    inv = inventory(store_id)
    drafts = sum(1 for d in db.po_drafts(store_id).where(filter=FieldFilter("status", "==", "draft")).stream())
    flags = sum(1 for v in db.verifications().where(filter=FieldFilter("store_id", "==", store_id))
                .where(filter=FieldFilter("verdict", "==", "flag")).stream() if not v.to_dict().get("review_outcome"))
    series = daily_revenue_history(store_id, 13) + [{"day": start.date().isoformat(), "revenue": revenue}]
    return {
        "today": {"orders": len(orders), "revenue": revenue, "by_channel": dict(by_channel),
                  "avg_basket": round(revenue / len(orders), 2) if orders else 0},
        "low_stock": sum(1 for r in inv if r["status"] == "low"), "out_of_stock": sum(1 for r in inv if r["status"] == "out"),
        "dead_stock": sum(1 for r in inv if r["status"] == "dead"), "open_drafts": drafts, "open_flags": flags,
        "asked_not_found": len(signals(store_id, 1)["not_carried"]), "series": series,
    }
