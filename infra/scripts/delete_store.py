"""Remove a store and everything under it: Firestore subcollections, sessions, carts, orders and verifications for the
store, its BigQuery sales rows and forecast model, and the store's roles on dashboard accounts. Irreversible.

    cd backend && .venv/bin/python ../infra/scripts/delete_store.py --store coffe-shop --yes
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "backend"))

from google.cloud.firestore_v1 import FieldFilter  # noqa: E402

from app.config import settings  # noqa: E402
from app.services import db  # noqa: E402


def delete_tree(ref) -> int:
    """Delete a document and everything under it, in small batches (documents with embeddings are large)."""
    n = 0
    for sub in ref.collections():
        refs = []
        for d in sub.stream():
            if list(d.reference.collections()):
                n += delete_tree(d.reference)
            else:
                refs.append(d.reference)
        db.batched(refs, lambda b, r: b.delete(r), size=10)
        n += len(refs)
    ref.delete()
    return n + 1


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
    docs = delete_tree(ref)
    for coll in (db.sessions(), db.carts(), db.orders(), db.verifications()):
        refs = [d.reference for d in coll.where(filter=FieldFilter("store_id", "==", a.store)).stream()]
        db.batched(refs, lambda b, r: b.delete(r))
        docs += len(refs)
    users = 0
    for d in db.users().stream():
        u = d.to_dict()
        if a.store in (u.get("stores") or []) or a.store in (u.get("roles") or {}):
            d.reference.update({"stores": [s for s in u.get("stores", []) if s != a.store], "roles": {k: v for k, v in (u.get("roles") or {}).items() if k != a.store}})
            users += 1
    try:
        from google.cloud import bigquery
        bq = bigquery.Client(project=settings.google_cloud_project)
        ds = f"{settings.google_cloud_project}.retail"
        bq.query(f"DELETE FROM `{ds}.sales` WHERE store_id = @store", job_config=bigquery.QueryJobConfig(
            query_parameters=[bigquery.ScalarQueryParameter("store", "STRING", a.store)])).result()
        bq.query(f"CREATE OR REPLACE TABLE `{ds}.daily_product_sales` AS SELECT store_id, product_id, day, SUM(qty) AS qty FROM `{ds}.sales` GROUP BY 1, 2, 3").result()
        model = "demand_arima_" + "".join(c if c.isalnum() else "_" for c in a.store)
        bq.query(f"DROP MODEL IF EXISTS `{ds}.{model}`").result()
    except Exception as exc:
        print("bigquery cleanup skipped:", str(exc)[:120])
    print(f"deleted store {a.store}: {docs} documents, roles removed from {users} account(s)")


if __name__ == "__main__":
    main()
