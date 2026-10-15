"""Seed the demo store into Firestore and BigQuery. Idempotent.

Usage (from repo root, with ADC or emulator configured):
  backend/.venv/bin/python infra/seed/seed.py --store demo-grocery [--embed] [--skip-bq]

Steps: store doc with floor map -> suppliers -> products/inventory/locations via the
CSV connector -> optional Gemini embeddings -> sales.csv into BigQuery by load job.
"""

import argparse
import csv
import sys
import time
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent.parent / "backend"))

from app.connectors import csv_connector as csvc  # noqa: E402
from app.config import settings  # noqa: E402
from app.domain.models import Aisle, Store, Supplier  # noqa: E402
from app.services import db, gemini  # noqa: E402

MAPPING = {h: h for h in csvc.REQUIRED + csvc.OPTIONAL}
FLOOR_MAP = [Aisle(aisle=f"A{i}", x=80 + (i - 1) * 150, y=80, w=90, h=420) for i in range(1, 7)]
SUPPLIERS = [
    ("sup-metro-cash", "Metro Cash & Carry", "orders@metro.example", 3),
    ("sup-aavin", "Aavin Dairy Depot", "depot@aavin.example", 1),
    ("sup-hul", "HUL Distributor", "orders@hul.example", 4),
    ("sup-apollo", "Apollo Pharma Wholesale", "b2b@apollo.example", 2),
    ("sup-koyambedu", "Koyambedu Market Agent", "agent@koyambedu.example", 1),
]


def seed_store(store_id: str, owner_emails: list[str]) -> Store:
    store = Store(store_id=store_id, name="Royal Stack Supermarket", floor_map=FLOOR_MAP, owner_emails=[e.lower() for e in owner_emails])
    data = store.model_dump()
    if not owner_emails:
        data.pop("owner_emails")   # keep whatever is already registered
    db.store_ref(store_id).set(data, merge=True)
    for sid, name, email, lead in SUPPLIERS:
        db.suppliers(store_id).document(sid).set(
            Supplier(supplier_id=sid, store_id=store_id, name=name, email=email, lead_time_days=lead).model_dump())
    return store


def seed_products(store: Store) -> None:
    data = (HERE / "products.csv").read_bytes()
    mapping = {k: v for k, v in MAPPING.items() if v in data.decode("utf-8").splitlines()[0].split(",")}
    rows, errors = csvc.parse(data, mapping)
    if errors:
        raise SystemExit(f"products.csv has errors: {errors[:3]}")
    res = csvc.upsert(store.store_id, rows, high_value_threshold=store.high_value_threshold)
    print(f"products: created={res.created} updated={res.updated}")


def seed_embeddings(store_id: str) -> None:
    docs = list(db.products(store_id).stream())
    texts = [" | ".join(filter(None, [d.get("name"), d.get("brand"), d.get("category"),
                                       d.get("subcategory"), " ".join(d.get("tags") or [])])) for d in docs]
    done, size = 0, 20  # free tier counts each text against the per-minute embed quota
    for i in range(0, len(docs), size):
        vecs = []
        for attempt in range(4):
            vecs = gemini.embed_texts(texts[i:i + size])
            if vecs:
                break
            time.sleep(20 * (attempt + 1))  # quota window
        if not vecs:
            print(f"embeddings stopped at {done} (Gemini not configured or quota exhausted); re-run --embed later")
            return
        batch = db.client().batch()
        for d, v in zip(docs[i:i + size], vecs):
            batch.update(d.reference, {"embedding": v})
        batch.commit()
        done += len(vecs)
        time.sleep(3)
    print(f"embeddings: {done}")


def seed_bigquery_rows(store_id: str, rows: list[dict]) -> None:
    """Load sales rows ({store_id, product_id, day, channel, qty, unit_price}) for one store and rebuild the daily table."""
    from google.cloud import bigquery

    bq = bigquery.Client(project=settings.google_cloud_project)
    ds = f"{settings.google_cloud_project}.retail"
    bq.create_dataset(bigquery.Dataset(ds), exists_ok=True)
    table = f"{ds}.sales"
    schema = [
        bigquery.SchemaField("store_id", "STRING"), bigquery.SchemaField("product_id", "STRING"),
        bigquery.SchemaField("day", "DATE"), bigquery.SchemaField("channel", "STRING"),
        bigquery.SchemaField("qty", "INT64"), bigquery.SchemaField("unit_price", "NUMERIC"),
        bigquery.SchemaField("order_id", "STRING"),
    ]
    try:
        bq.query(f"DELETE FROM `{table}` WHERE store_id = @store", job_config=bigquery.QueryJobConfig(
            query_parameters=[bigquery.ScalarQueryParameter("store", "STRING", store_id)])).result()
    except Exception:
        pass  # table may not exist yet
    bq.load_table_from_json(rows, table, job_config=bigquery.LoadJobConfig(schema=schema, write_disposition="WRITE_APPEND")).result()
    bq.query(f"CREATE OR REPLACE TABLE `{ds}.daily_product_sales` AS SELECT store_id, product_id, day, SUM(qty) AS qty FROM `{table}` GROUP BY 1, 2, 3").result()
    print(f"bigquery: {len(rows)} sales rows loaded for {store_id}")


def seed_bigquery(store_id: str) -> None:
    from google.cloud import bigquery

    bq = bigquery.Client(project=settings.google_cloud_project)
    ds = f"{settings.google_cloud_project}.retail"
    bq.create_dataset(bigquery.Dataset(ds), exists_ok=True)
    table = f"{ds}.sales"
    schema = [
        bigquery.SchemaField("store_id", "STRING"), bigquery.SchemaField("product_id", "STRING"),
        bigquery.SchemaField("day", "DATE"), bigquery.SchemaField("channel", "STRING"),
        bigquery.SchemaField("qty", "INT64"), bigquery.SchemaField("unit_price", "NUMERIC"),
    ]
    if not (HERE / "sales.csv").exists():
        import make_sales
        make_sales.main(store_id)
    job = bq.load_table_from_file(
        (HERE / "sales.csv").open("rb"), table,
        job_config=bigquery.LoadJobConfig(schema=schema, skip_leading_rows=1,
                                          write_disposition="WRITE_TRUNCATE"))
    job.result()
    bq.query(f"""
        CREATE OR REPLACE TABLE `{ds}.daily_product_sales` AS
        SELECT store_id, product_id, day, SUM(qty) AS qty
        FROM `{table}` GROUP BY store_id, product_id, day
    """).result()
    n = list(bq.query(f"SELECT COUNT(*) c FROM `{table}`").result())[0].c
    print(f"bigquery: {n} sales rows loaded, daily_product_sales rebuilt")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--store", default="demo-grocery")
    ap.add_argument("--embed", action="store_true", help="compute Gemini embeddings")
    ap.add_argument("--skip-bq", action="store_true")
    ap.add_argument("--owner-email", action="append", default=[], help="Google account allowed into the owner dashboard (repeatable)")
    a = ap.parse_args()

    store = seed_store(a.store, a.owner_email)
    seed_products(store)
    if a.embed:
        seed_embeddings(a.store)
    if not a.skip_bq:
        seed_bigquery(a.store)
    print("done")
