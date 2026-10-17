"""Generic sync adapter: signed inbound stock and catalog updates, outbound sale events with retries,
and a scheduled CSV feed. Any billing system that can call a URL or publish a CSV fits this contract."""

import hashlib
import hmac
import json
import logging
import secrets as pysecrets
import threading
import time
from datetime import timedelta

import httpx
from google.api_core.exceptions import AlreadyExists
from google.cloud import firestore
from google.cloud.firestore_v1 import FieldFilter

from app.connectors import csv_connector as csvc
from app.domain.models import Order, Sync, now, slug
from app.services import catalog, db, secrets

log = logging.getLogger(__name__)
MAX_SKEW_S = 300
MAX_ROWS = 5000
BACKOFF_MIN = (1, 5, 30, 120, 480)
MAX_ATTEMPTS = 6
TIMEOUT_S = 5


# --- secrets and signatures ----------------------------------------------------

def secret_for(store_id: str) -> str:
    return secrets.get(f"sync-{store_id}")


def new_secret(store_id: str) -> str:
    """A fresh 64-hex-character secret, stored in Secret Manager and shown to the owner once."""
    value = pysecrets.token_hex(32)
    secrets.put(f"sync-{store_id}", value)
    db.store_ref(store_id).update({"sync.has_secret": True})
    return value


def sign(secret: str, timestamp: str, body: bytes) -> str:
    return "sha256=" + hmac.new(secret.encode(), f"{timestamp}.".encode() + body, hashlib.sha256).hexdigest()


def verify(secret: str, timestamp: str, body: bytes, signature: str) -> bool:
    if not secret or not timestamp or not signature:
        return False
    try:
        if abs(time.time() - int(timestamp)) > MAX_SKEW_S:
            return False
    except ValueError:
        return False
    return hmac.compare_digest(sign(secret, timestamp, body), signature)


def _settings(store_id: str) -> Sync:
    doc = db.store_ref(store_id).get().to_dict() or {}
    return Sync(**(doc.get("sync") or {}))


# --- log and idempotency -------------------------------------------------------

def record(store_id: str, **entry) -> None:
    db.sync_log(store_id).add({"at": now(), **entry})


def seen(store_id: str, event_id: str) -> bool:
    """True when this event id was processed before. The first caller wins through a create-only write."""
    ref = db.sync_events(store_id).document(hashlib.sha256(event_id.encode()).hexdigest()[:32])
    try:
        ref.create({"event_id": event_id[:200], "at": now()})
        return False
    except AlreadyExists:
        return True


# --- inbound -------------------------------------------------------------------

def apply_inventory(store_id: str, rows: list[dict]) -> dict:
    """Absolute on_hand per SKU, reservations kept; optional price. Unknown SKUs are reported, never created."""
    updated, unknown, price_changed = 0, [], False
    batch, pending = db.client().batch(), 0
    for r in rows:
        pid = f"{store_id}-{slug(r['sku'])}"
        inv = db.inventory(store_id).document(pid)
        if not inv.get().exists:
            unknown.append(r["sku"])
            continue
        batch.update(inv, {"on_hand": int(r["on_hand"])})
        pending += 1
        if r.get("price") is not None:
            batch.update(db.products(store_id).document(pid), {"price": float(r["price"])})
            pending += 1
            price_changed = True
        updated += 1
        if pending >= csvc.BATCH:
            batch.commit()
            batch, pending = db.client().batch(), 0
    if pending:
        batch.commit()
    if price_changed:
        catalog.bump(store_id)
    return {"updated": updated, "unknown": unknown}


def apply_products(store_id: str, rows: list[dict]) -> csvc.ImportResult:
    threshold = (db.store_ref(store_id).get().to_dict() or {}).get("high_value_threshold", 500)
    parsed, errors = [], []
    for i, r in enumerate(rows, start=1):
        try:
            parsed.append(csvc.Row(line=i, **{k: v for k, v in r.items() if k in csvc.Row.model_fields}))
        except ValueError as exc:
            errors.append(csvc.RowError(line=i, message=str(exc)[:200]))
    result = csvc.upsert(store_id, parsed, high_value_threshold=threshold)
    result.errors = errors
    catalog.bump(store_id)
    return result


def inventory_snapshot(store_id: str) -> list[dict]:
    products, _ = catalog.product_map(store_id)
    out = []
    for d in db.inventory(store_id).stream():
        i = d.to_dict()
        p = products.get(d.id)
        out.append({"sku": p.sku if p else d.id, "product_id": d.id, "on_hand": i.get("on_hand", 0), "reserved": i.get("reserved", 0),
                    "available": max(0, i.get("on_hand", 0) - i.get("reserved", 0)), "price": p.price if p else None})
    return out


# --- outbound ------------------------------------------------------------------

def deliver(store_id: str, url: str, payload: dict) -> None:
    raw = json.dumps(payload, default=str).encode()
    ts = str(int(time.time()))
    headers = {"Content-Type": "application/json", "X-Sync-Timestamp": ts, "X-Sync-Signature": sign(secret_for(store_id), ts, raw),
               "User-Agent": "RoyalStack-Sync/1"}
    httpx.post(url, content=raw, headers=headers, timeout=TIMEOUT_S).raise_for_status()


def _send_or_queue(store_id: str, url: str, payload: dict, key: str) -> bool:
    try:
        deliver(store_id, url, payload)
        record(store_id, direction="out", kind=payload.get("event", "event"), rows=1, changed=1, event_id=key, ok=True)
        return True
    except Exception as exc:
        db.sync_outbox(store_id).document(key).set({"key": key, "url": url, "payload": json.dumps(payload, default=str), "attempts": 1,
                                                   "next_at": now() + timedelta(minutes=BACKOFF_MIN[0]), "created_at": now(),
                                                   "last_error": str(exc)[:200], "dead": False})
        record(store_id, direction="out", kind=payload.get("event", "event"), rows=1, changed=0, event_id=key, ok=False, error=str(exc)[:200])
        return False


def notify_sale(o: Order) -> None:
    cfg = _settings(o.store_id)
    if not cfg.webhook_url:
        return
    products, _ = catalog.product_map(o.store_id)
    payload = {"event": "sale", "order_id": o.order_id, "store_id": o.store_id, "channel": o.channel,
               "paid_at": o.paid_at.isoformat() if o.paid_at else None, "total": o.total,
               "items": [{"sku": products[i.product_id].sku if i.product_id in products else "", "product_id": i.product_id,
                          "qty": i.qty, "unit_price": i.unit_price} for i in o.items]}
    _send_or_queue(o.store_id, cfg.webhook_url, payload, key=o.order_id)


def notify_sale_async(o: Order) -> None:
    """Off the payment path: the shopper's receipt never waits for the shop's system."""
    def go():
        try:
            notify_sale(o)
        except Exception:
            log.exception("sale notification failed for %s", o.order_id)
    threading.Thread(target=go, daemon=True).start()


def send_test(store_id: str) -> dict:
    cfg = _settings(store_id)
    if not cfg.webhook_url:
        return {"ok": False, "error": "no webhook_url"}
    try:
        deliver(store_id, cfg.webhook_url, {"event": "test", "store_id": store_id, "at": now().isoformat()})
        record(store_id, direction="out", kind="test", rows=1, changed=1, ok=True)
        return {"ok": True}
    except Exception as exc:
        record(store_id, direction="out", kind="test", rows=1, changed=0, ok=False, error=str(exc)[:200])
        return {"ok": False, "error": str(exc)[:200]}


def retry_outbox(store_id: str) -> int:
    """Resend due entries with backoff; give up after MAX_ATTEMPTS and leave the entry marked dead for the owner."""
    delivered = 0
    for d in db.sync_outbox(store_id).where(filter=FieldFilter("next_at", "<=", now())).stream():
        e = d.to_dict()
        if e.get("dead"):
            continue
        try:
            deliver(store_id, e["url"], json.loads(e["payload"]))
            d.reference.delete()
            record(store_id, direction="out", kind="retry", rows=1, changed=1, event_id=e["key"], ok=True)
            delivered += 1
        except Exception as exc:
            attempts = e.get("attempts", 1) + 1
            d.reference.update({"attempts": attempts, "last_error": str(exc)[:200], "dead": attempts >= MAX_ATTEMPTS,
                                "next_at": now() + timedelta(minutes=BACKOFF_MIN[min(attempts - 1, len(BACKOFF_MIN) - 1)])})
            record(store_id, direction="out", kind="retry", rows=1, changed=0, event_id=e["key"], ok=False, error=str(exc)[:200])
    return delivered


# --- scheduled feed ------------------------------------------------------------

def pull_feed(store_id: str) -> dict:
    cfg = _settings(store_id)
    if not cfg.feed_url:
        return {"skipped": "no feed_url"}
    try:
        res = httpx.get(cfg.feed_url, timeout=20, follow_redirects=True)
        res.raise_for_status()
        if len(res.content) > csvc.MAX_BYTES:
            raise ValueError("feed larger than 5 MB")
        rows, errors = csvc.parse(res.content, cfg.feed_mapping)
        threshold = (db.store_ref(store_id).get().to_dict() or {}).get("high_value_threshold", 500)
        result = csvc.upsert(store_id, rows, high_value_threshold=threshold)
        catalog.bump(store_id)
        db.store_ref(store_id).update({"sync.last_pull_at": now()})
        record(store_id, direction="in", kind="feed", rows=len(rows) + len(errors), changed=result.created + result.updated,
               errors=len(errors), ok=True)
        return {"created": result.created, "updated": result.updated, "errors": len(errors)}
    except Exception as exc:
        record(store_id, direction="in", kind="feed", rows=0, changed=0, ok=False, error=str(exc)[:200])
        return {"error": str(exc)[:200]}


def run_scheduled() -> dict:
    """Every store: pull a due feed, retry its outbox. Called by Cloud Scheduler through /jobs/sync."""
    pulled = delivered = 0
    for d in db.client().collection("stores").stream():
        sid = d.id
        cfg = Sync(**((d.to_dict() or {}).get("sync") or {}))
        due = not cfg.last_pull_at or now() - cfg.last_pull_at >= timedelta(minutes=cfg.feed_every_min)
        if cfg.feed_url and due:
            pull_feed(sid)
            pulled += 1
        delivered += retry_outbox(sid)
    return {"pulled": pulled, "delivered": delivered}
