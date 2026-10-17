"""Empty a store's catalogue (products, stock, locations, suppliers, forecasts, drafts, signals, counts, sales history)
while keeping the store itself: its name, owners, branding, PIN, customers and settings. Irreversible.

    cd backend && .venv/bin/python ../infra/scripts/clear_catalog.py --store kingsman-textiles --yes
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "backend"))

from app.config import settings  # noqa: E402
from app.services import catalog, db  # noqa: E402

COLLECTIONS = ("products", "inventory", "locations", "suppliers", "forecasts", "po_drafts", "demand_signals", "counts")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--store", required=True)
    ap.add_argument("--yes", action="store_true")
    a = ap.parse_args()
    if not a.yes:
        sys.exit("add --yes to confirm; this cannot be undone")
    ref = db.store_ref(a.store)
    if not ref.get().exists:
        sys.exit(f"store {a.store} not found")
    n = 0
    for name in COLLECTIONS:
        refs = [d.reference for d in ref.collection(name).stream()]
        db.batched(refs, lambda b, r: b.delete(r), size=10)      # product documents carry embeddings; big batches exceed the 10 MB transaction limit
        n += len(refs)
    catalog.bump(a.store)
    try:
        from google.cloud import bigquery
        bq = bigquery.Client(project=settings.google_cloud_project)
        ds = f"{settings.google_cloud_project}.retail"
        bq.query(f"DELETE FROM `{ds}.sales` WHERE store_id = @store", job_config=bigquery.QueryJobConfig(
            query_parameters=[bigquery.ScalarQueryParameter("store", "STRING", a.store)])).result()
        bq.query(f"CREATE OR REPLACE TABLE `{ds}.daily_product_sales` AS SELECT store_id, product_id, day, SUM(qty) AS qty FROM `{ds}.sales` GROUP BY 1, 2, 3").result()
        bq.query(f"DROP MODEL IF EXISTS `{ds}.demand_arima_" + "".join(c if c.isalnum() else "_" for c in a.store) + "`").result()
    except Exception as exc:
        print("bigquery cleanup skipped:", str(exc)[:120])
    print(f"cleared catalogue of {a.store}: {n} documents removed")


if __name__ == "__main__":
    main()
