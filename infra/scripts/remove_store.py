"""Remove a store completely: its document and every subcollection, the sessions, carts, orders and verifications that
point at it, its membership on user records, and its BigQuery sales rows and forecast model. Irreversible: take a backup
first (see docs/lld/sample-data.md). Dry run by default.

  backend/.venv/bin/python infra/scripts/remove_store.py --store demo-grocery          # shows what would go
  backend/.venv/bin/python infra/scripts/remove_store.py --store demo-grocery --yes    # removes it
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "backend"))

from google.cloud.firestore_v1 import FieldFilter  # noqa: E402

from app.config import settings  # noqa: E402
from app.services import db  # noqa: E402

TOP_LEVEL = ("sessions", "carts", "orders", "verifications")


def plan(store_id: str) -> dict:
    fs = db.client()
    out = {"store_exists": fs.collection("stores").document(store_id).get().exists}
    for top in TOP_LEVEL:
        out[top] = sum(1 for _ in fs.collection(top).where(filter=FieldFilter("store_id", "==", store_id)).select([]).stream())
    out["users"] = [u.to_dict().get("email", u.id) for u in fs.collection("users").stream()
                    if store_id in u.to_dict().get("stores", []) or store_id in u.to_dict().get("roles", {})]
    return out


def remove(store_id: str) -> None:
    fs = db.client()
    for u in fs.collection("users").stream():
        data = u.to_dict()
        if store_id in data.get("stores", []) or store_id in data.get("roles", {}):
            u.reference.update({"stores": [s for s in data.get("stores", []) if s != store_id],
                                "roles": {s: r for s, r in data.get("roles", {}).items() if s != store_id}})
    for top in TOP_LEVEL:
        for d in fs.collection(top).where(filter=FieldFilter("store_id", "==", store_id)).select([]).stream():
            d.reference.delete()
    fs.recursive_delete(fs.collection("stores").document(store_id))
    try:
        from google.cloud import bigquery
        bq = bigquery.Client(project=settings.google_cloud_project)
        ds = f"{settings.google_cloud_project}.retail"
        bq.query(f"DELETE FROM `{ds}.sales` WHERE store_id = @store", job_config=bigquery.QueryJobConfig(
            query_parameters=[bigquery.ScalarQueryParameter("store", "STRING", store_id)])).result()
        bq.query(f"CREATE OR REPLACE TABLE `{ds}.daily_product_sales` AS SELECT store_id, product_id, day, SUM(qty) AS qty FROM `{ds}.sales` GROUP BY 1, 2, 3").result()
        model = "demand_arima_" + "".join(c if c.isalnum() else "_" for c in store_id)
        bq.query(f"DROP MODEL IF EXISTS `{ds}.{model}`").result()
    except Exception as exc:  # no BigQuery rows for this store, or no dataset yet
        print("bigquery:", exc)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--store", required=True)
    ap.add_argument("--yes", action="store_true", help="actually remove; without it only the plan is printed")
    a = ap.parse_args()
    print("plan:", plan(a.store))
    if a.yes:
        remove(a.store)
        print("removed:", a.store, "| now:", plan(a.store))
