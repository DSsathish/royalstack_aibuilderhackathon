"""Daily job: copy paid orders to BigQuery, train ARIMA_PLUS, write 14-day forecasts to Firestore.

    python -m app.jobs.forecast --store <store-id>
"""

import argparse
import json
import logging
import statistics
from datetime import date, timedelta, timezone

from google.cloud import bigquery
from google.cloud.firestore_v1 import FieldFilter

from app.config import settings
from app.services import db, forecast

log = logging.getLogger(__name__)
HORIZON = forecast.HORIZON
IST = timezone(timedelta(hours=5, minutes=30))


def _param(store_id: str) -> bigquery.QueryJobConfig:
    return bigquery.QueryJobConfig(query_parameters=[bigquery.ScalarQueryParameter("store", "STRING", store_id)])


def _model(store_id: str) -> str:
    return "demand_arima_" + "".join(c if c.isalnum() else "_" for c in store_id)


def sync_sales(bq: bigquery.Client, store_id: str) -> int:
    """Append paid orders that are not yet in retail.sales (idempotent on order_id)."""
    ds = f"{settings.google_cloud_project}.retail"
    bq.query(f"ALTER TABLE `{ds}.sales` ADD COLUMN IF NOT EXISTS order_id STRING").result()   # seed table predates order ids
    known = {r.order_id for r in bq.query(f"SELECT DISTINCT order_id FROM `{ds}.sales` WHERE store_id = @store AND order_id IS NOT NULL", job_config=_param(store_id)).result()}
    rows = []
    for o in db.orders().where(filter=FieldFilter("store_id", "==", store_id)).stream():
        d = o.to_dict()
        if d.get("status") not in ("paid", "verified", "flagged") or d["order_id"] in known:
            continue
        day = (d.get("paid_at") or d["created_at"]).astimezone(IST).date().isoformat()
        for item in d["items"]:
            rows.append({"store_id": store_id, "product_id": item["product_id"], "day": day, "channel": d["channel"],
                         "qty": item["qty"], "unit_price": item["unit_price"], "order_id": d["order_id"]})
    if rows:
        job = bq.load_table_from_json(rows, f"{ds}.sales", job_config=bigquery.LoadJobConfig(
            schema_update_options=["ALLOW_FIELD_ADDITION"], write_disposition="WRITE_APPEND",
            schema=[bigquery.SchemaField("store_id", "STRING"), bigquery.SchemaField("product_id", "STRING"), bigquery.SchemaField("day", "DATE"),
                    bigquery.SchemaField("channel", "STRING"), bigquery.SchemaField("qty", "INT64"), bigquery.SchemaField("unit_price", "NUMERIC"),
                    bigquery.SchemaField("order_id", "STRING")]))
        job.result()
    bq.query(f"CREATE OR REPLACE TABLE `{ds}.daily_product_sales` AS SELECT store_id, product_id, day, SUM(qty) AS qty FROM `{ds}.sales` GROUP BY 1, 2, 3").result()
    return len(rows)


def train_and_forecast(bq: bigquery.Client, store_id: str) -> dict[str, dict]:
    ds = f"{settings.google_cloud_project}.retail"
    bq.query(f"""
        CREATE OR REPLACE MODEL `{ds}.{_model(store_id)}`
        OPTIONS(model_type='ARIMA_PLUS', time_series_timestamp_col='day', time_series_data_col='qty',
                time_series_id_col='product_id', auto_arima=TRUE, data_frequency='DAILY', holiday_region='IN') AS
        SELECT product_id, day, qty FROM `{ds}.daily_product_sales` WHERE store_id = @store""", job_config=_param(store_id)).result()
    out: dict[str, dict] = {}
    for r in bq.query(f"""
        SELECT product_id, forecast_timestamp, forecast_value, standard_error
        FROM ML.FORECAST(MODEL `{ds}.{_model(store_id)}`, STRUCT({HORIZON} AS horizon, 0.8 AS confidence_level))
        ORDER BY product_id, forecast_timestamp""").result():
        f = out.setdefault(r.product_id, {"daily": [], "errs": []})
        f["daily"].append(max(0.0, float(r.forecast_value)))
        f["errs"].append(float(r.standard_error or 0))
    for pid, f in out.items():
        f["avg_daily"] = statistics.fmean(f["daily"]) if f["daily"] else 0.0
        f["std_daily"] = statistics.fmean(f["errs"]) if f["errs"] else 0.0
    return out


def history(bq: bigquery.Client, store_id: str, days: int = 30) -> dict[str, list[float]]:
    ds = f"{settings.google_cloud_project}.retail"
    out: dict[str, list[float]] = {}
    for r in bq.query(f"""SELECT product_id, day, qty FROM `{ds}.daily_product_sales`
                          WHERE store_id = @store AND day >= DATE_SUB(CURRENT_DATE('Asia/Kolkata'), INTERVAL {int(days)} DAY)""", job_config=_param(store_id)).result():
        out.setdefault(r.product_id, []).append(float(r.qty))
    return out


def run(store_id: str) -> dict:
    bq = bigquery.Client(project=settings.google_cloud_project)
    synced = sync_sales(bq, store_id)
    try:
        forecasts = train_and_forecast(bq, store_id)
        method = "arima_plus"
    except Exception as exc:
        log.warning("ARIMA training failed, using 30-day means: %s", exc)
        forecasts, method = {}, "mean_fallback"
    fallback = forecast.from_history(history(bq, store_id), days=30)
    for pid in db.products(store_id).select([]).stream():
        f = forecasts.get(pid.id) or fallback.get(pid.id) or {"daily": [0.0] * HORIZON, "avg_daily": 0.0, "std_daily": 0.0}
        forecast.put(store_id, pid.id, daily=f["daily"], avg_daily=f["avg_daily"], std_daily=f["std_daily"])
    return {"store_id": store_id, "synced_sales_rows": synced, "products": len(list(db.products(store_id).select([]).stream())), "method": method}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--store", required=True)
    print(json.dumps(run(ap.parse_args().store)))
