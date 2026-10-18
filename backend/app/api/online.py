"""Online shop screens: the home (trending, categories, recommended, deals), category and search listings with purchase
counts, and label facts for a product sheet. Public reads keyed by store; the session header only personalises.
Design: docs/lld/online-shop.md."""

import re
import time
from collections import Counter
from datetime import timedelta

from fastapi import APIRouter, Header, HTTPException, Path, Query
from google.cloud.firestore_v1 import FieldFilter

from app.api.catalog import PUBLIC_EXCLUDE
from app.domain import languages
from app.domain.models import Product, now
from app.services import catalog, customers, db, facts, offers, providers, sessions
from app.services.auth import STORE_ID

router = APIRouter(tags=["online"])
HEX_ID = r"^[0-9a-f]{32}$"
PID = Path(pattern=r"^[a-z0-9-]{3,80}$")
POPULARITY_DAYS, POPULARITY_TTL_S = 30, 300
_popularity: dict[str, tuple[float, dict[str, int]]] = {}
FACTS_QUESTION = "ingredients, allergens, nutrition per 100 g and dietary notes"


def popularity(store_id: str) -> dict[str, int]:
    """Units sold per product in the last thirty days, from paid orders; cached five minutes per API instance."""
    hit = _popularity.get(store_id)
    if hit and time.monotonic() - hit[0] < POPULARITY_TTL_S:
        return hit[1]
    since = now() - timedelta(days=POPULARITY_DAYS)
    counts: Counter[str] = Counter()
    for d in db.orders().where(filter=FieldFilter("store_id", "==", store_id)).stream():
        o = d.to_dict()
        if o.get("status") in ("paid", "verified", "flagged") and o.get("created_at") and o["created_at"] >= since:
            for it in o.get("items", []):
                counts[it["product_id"]] += int(it.get("qty", 1))
    _popularity[store_id] = (time.monotonic(), dict(counts))
    return _popularity[store_id][1]


def _card(store_id: str, p: Product, bought: dict[str, int]) -> dict:
    view = catalog.get_product(store_id, p.product_id)
    d = (view or p).model_dump(exclude=PUBLIC_EXCLUDE)
    d["bought_30d"] = bought.get(p.product_id, 0)
    return d


def _shopper(store_id: str, x_session_id: str | None):
    """(segment, customer) for the session header, guest without one."""
    if x_session_id and re.fullmatch(HEX_ID, x_session_id):
        s = sessions.get(x_session_id)
        if s and s.store_id == store_id:
            return customers.segment_of(store_id, s.customer_id), (customers.get(store_id, s.customer_id) if s.customer_id else None)
    return "guest", None


@router.get("/stores")
def list_stores():
    """Shops a shopper can pick for online shopping: name, city and tagline only."""
    out = []
    for d in db.client().collection("stores").stream():
        x = d.to_dict()
        out.append({"store_id": d.id, "name": x.get("name", d.id), "city": x.get("city") or "", "tagline": (x.get("brand") or {}).get("tagline", "")})
    return sorted(out, key=lambda s: s["name"].lower())


@router.get("/stores/{store_id}/home")
def home(store_id: str = STORE_ID, x_session_id: str | None = Header(default=None)):
    if not db.store_ref(store_id).get().exists:
        raise HTTPException(404, "store not found")
    products, _ = catalog.product_map(store_id)
    bought = popularity(store_id)
    active = [p for p in products.values() if p.status == "active"]
    ranked = sorted(active, key=lambda p: (-bought.get(p.product_id, 0), p.name))
    trending = [p for p in ranked[:12] if bought.get(p.product_id, 0) > 0]
    categories = [{"name": c, "count": n} for c, n in Counter(p.category for p in active if p.category).most_common(12)]
    segment, customer = _shopper(store_id, x_session_id)
    rec: list[Product] = []
    if customer:
        rec += [products[pid] for pid in customer.usual_items if pid in products][:6]
        for cat in customer.favourite_categories:
            rec += [p for p in ranked if p.category == cat and p not in rec][:4]
    if len(rec) < 8:                                                     # guests and new shoppers: the next best sellers
        shown = {p.product_id for p in trending} | {p.product_id for p in rec}
        rec += [p for p in ranked if p.product_id not in shown][:12 - len(rec)]
    deals = []
    for o in offers.applicable(store_id, segment):
        if o.kind == "product":
            items = [products[o.product_id]] if o.product_id in products else []
        elif o.kind == "category":
            items = [p for p in ranked if p.category == o.category][:8]
        else:
            items = []
        deals.append({**offers.public(store_id, o), "products": [_card(store_id, p, bought) for p in items]})
    return {"categories": categories, "trending": [_card(store_id, p, bought) for p in trending],
            "recommended": [_card(store_id, p, bought) for p in rec[:12]], "deals": deals, "segment": segment}


@router.get("/stores/{store_id}/products")
def list_products(store_id: str = STORE_ID, category: str = Query(default="", max_length=60), q: str = Query(default="", max_length=200),
                  limit: int = Query(default=40, ge=1, le=100), offset: int = Query(default=0, ge=0)):
    """A category page (best sellers first) or a search page (the assistant's own search)."""
    bought = popularity(store_id)
    if q.strip():
        hits = catalog.search(store_id, q.strip(), k=limit)
        return {"products": [_card(store_id, p, bought) for p in hits], "total": len(hits), "more": False}
    products, _ = catalog.product_map(store_id)
    key = category.strip().lower()
    pool = [p for p in products.values() if p.status == "active" and (not key or key in (p.category.lower(), p.subcategory.lower()))]
    pool.sort(key=lambda p: (-bought.get(p.product_id, 0), p.name))
    page = pool[offset:offset + limit]
    return {"products": [_card(store_id, p, bought) for p in page], "total": len(pool), "more": offset + limit < len(pool)}


@router.get("/stores/{store_id}/products/{product_id}/facts")
def product_facts(store_id: str = STORE_ID, product_id: str = PID, x_session_id: str | None = Header(default=None),
                  language: str = Query(default="auto", pattern=languages.CODE_PATTERN)):
    """Label facts for the product sheet: the same guarded lookup the assistant uses, charged to the session's budget."""
    if not (x_session_id and re.fullmatch(HEX_ID, x_session_id)):
        raise HTTPException(401, "session required")
    s = sessions.get(x_session_id)
    if not s or s.store_id != store_id:
        raise HTTPException(401, "session not found or expired")
    p = catalog.get_product(store_id, product_id)
    if not p:
        raise HTTPException(404, "product not found")
    return facts.lookup(store_id, s.session_id, FACTS_QUESTION, p, language)


@router.get("/stores/{store_id}/products/{product_id}/compare")
def product_compare(store_id: str = STORE_ID, product_id: str = PID, x_session_id: str | None = Header(default=None)):
    """The same product at other providers: the demo provider plus the shop's MCP connectors marked for comparison."""
    if not (x_session_id and re.fullmatch(HEX_ID, x_session_id)):
        raise HTTPException(401, "session required")
    s = sessions.get(x_session_id)
    if not s or s.store_id != store_id:
        raise HTTPException(401, "session not found or expired")
    p = catalog.get_product(store_id, product_id)
    if not p:
        raise HTTPException(404, "product not found")
    return providers.compare(store_id, p)
