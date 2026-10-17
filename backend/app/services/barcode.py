"""Barcode lookup for the owner's add-by-scan: Open Food Facts, cached in Firestore for 30 days."""

import logging
from datetime import timedelta

import httpx

from app.domain.models import now
from app.services import db

log = logging.getLogger(__name__)
CACHE_DAYS = 30
FIELDS = ("found", "name", "brand", "category", "image_url")


def _fetch_open_food_facts(code: str) -> dict:
    try:
        res = httpx.get(f"https://world.openfoodfacts.org/api/v2/product/{code}.json",
                        params={"fields": "product_name,brands,categories_tags,image_front_small_url"},
                        headers={"User-Agent": "RoyalStack/1.0 (hackathon)"}, timeout=5)
        data = res.json() if res.status_code == 200 else {}
    except Exception as exc:
        log.warning("open food facts failed for %s: %s", code, exc)
        return {"found": False}
    p = data.get("product") or {}
    if data.get("status") != 1 or not p.get("product_name"):
        return {"found": False}
    tags = p.get("categories_tags") or []
    cats = [c.split(":", 1)[-1].replace("-", " ").title() for c in tags if c.startswith("en:")] or \
           [c.split(":", 1)[-1].replace("-", " ").title() for c in tags]
    return {"found": True, "name": p["product_name"].strip()[:120], "brand": (p.get("brands") or "").split(",")[0].strip()[:60],
            "category": cats[-1] if cats else "", "image_url": p.get("image_front_small_url") or ""}


def lookup(code: str) -> dict:
    ref = db.client().collection("barcode_lookups").document(code)
    doc = ref.get()
    if doc.exists and doc.to_dict().get("at") and now() - doc.to_dict()["at"] < timedelta(days=CACHE_DAYS):
        return {k: doc.to_dict().get(k) for k in FIELDS if k in doc.to_dict()}
    result = _fetch_open_food_facts(code)
    ref.set({**result, "at": now()})
    return result
