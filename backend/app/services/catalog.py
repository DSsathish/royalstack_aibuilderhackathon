"""Read-side product lookup: by id, by barcode, by search. Writes demand signals."""

import math
import re
import time
import uuid

from pydantic import BaseModel

from app.domain.models import DemandSignal, Location, Product
from app.domain import classify
from app.services import db, gemini, inventory

CACHE_TTL_S = 60
VERSION_CHECK_S = 2       # how often an instance asks Firestore whether the catalog changed elsewhere
_cache: dict[str, dict] = {}


class ProductView(Product):
    available: int = 0
    location: Location | None = None


def invalidate(store_id: str) -> None:
    _cache.pop(store_id, None)


def bump(store_id: str) -> None:
    """Every product write ends here: the version counter tells every API instance to reload its cache."""
    from google.cloud import firestore
    db.store_ref(store_id).update({"catalog_version": firestore.Increment(1)})
    invalidate(store_id)


def _version(store_id: str) -> int:
    doc = db.store_ref(store_id).get(field_paths=["catalog_version"])
    return int((doc.to_dict() or {}).get("catalog_version", 0)) if doc.exists else 0


def _load(store_id: str) -> tuple[list[Product], dict[str, Location]]:
    t = time.time()
    hit = _cache.get(store_id)
    if hit and t - hit["at"] < CACHE_TTL_S:
        if t - hit["checked"] < VERSION_CHECK_S:
            return hit["products"], hit["locations"]
        if _version(store_id) == hit["version"]:
            hit["checked"] = t
            return hit["products"], hit["locations"]
    version = _version(store_id)
    products = [Product(**d.to_dict()) for d in db.products(store_id).stream()]
    locations = {d.id: Location(**d.to_dict()) for d in db.locations(store_id).stream()}
    _cache[store_id] = {"at": t, "checked": t, "version": version, "products": products, "locations": locations}
    return products, locations


def _view(store_id: str, p: Product, locations: dict[str, Location]) -> ProductView:
    return ProductView(**p.model_dump(), available=inventory.available(store_id, p.product_id),
                       location=locations.get(p.product_id))


def blocks(store_id: str) -> dict[str, dict]:
    """Floor-map blocks by name (kind and floor), read fresh: the owner edits them rarely, the assistant reads them often."""
    doc = db.store_ref(store_id).get().to_dict() or {}
    return {b["aisle"]: b for b in doc.get("floor_map", [])}


def product_map(store_id: str) -> tuple[dict[str, Product], dict[str, Location]]:
    """Cached products and locations by id, with no inventory reads. For bulk views that stream inventory themselves."""
    products, locations = _load(store_id)
    return {p.product_id: p for p in products}, locations


def get_product(store_id: str, product_id: str) -> ProductView | None:
    products, locations = _load(store_id)
    p = next((p for p in products if p.product_id == product_id), None)
    return _view(store_id, p, locations) if p else None


def get_by_sku(store_id: str, sku: str) -> ProductView | None:
    """Exact SKU or barcode match, case-insensitive: what a model echoes back from an earlier result."""
    products, locations = _load(store_id)
    key = sku.strip().lower()
    p = next((p for p in products if p.sku.lower() == key or (p.barcode and p.barcode == key)), None)
    return _view(store_id, p, locations) if p else None


def get_by_barcode(store_id: str, barcode: str) -> ProductView | None:
    products, locations = _load(store_id)
    p = next((p for p in products if p.barcode == barcode), None)
    return _view(store_id, p, locations) if p else None


# --- search -----------------------------------------------------------------

_TOKEN = re.compile(r"[\w஀-௿ऀ-ॿ]+")  # latin, tamil, devanagari


def _tokens(text: str) -> set[str]:
    return set(_TOKEN.findall(text.lower().replace("_", " ")))    # models often write snake_case ids


def _keyword_score(q: set[str], p: Product) -> float:
    name, brand, tags, cat = _tokens(p.name), _tokens(p.brand), _tokens(" ".join(p.tags)), _tokens(p.category)
    return 3 * len(q & name) + 2 * len(q & brand) + 2 * len(q & tags) + len(q & cat)


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    return dot / (math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b)) + 1e-9)


def search(store_id: str, query: str, k: int = 6) -> list[ProductView]:
    products, locations = _load(store_id)
    q = _tokens(query)
    qvec = (gemini.embed_texts([query], for_query=True) or [[]])[0]

    wanted = classify.query_use(query)
    scored = []
    for p in products:
        if wanted and p.use != wanted:
            continue                      # "dog biscuits" means pet products only
        if not wanted and p.use == "pet":
            continue                      # nobody asked for pets: pet products never answer a people's query
        kw = _keyword_score(q, p)
        sem = _cosine(qvec, p.embedding)
        if kw > 0 or sem > 0.6:
            scored.append((kw + 5 * sem, p))
    scored.sort(key=lambda t: t[0], reverse=True)
    hits = [_view(store_id, p, locations) for _, p in scored[:k]]

    _record_signal(store_id, query, hits)
    return hits


def _record_signal(store_id: str, query: str, hits: list[ProductView]) -> None:
    """Automatic signals only for clear cases; the agent records judgment calls itself."""
    if not hits:
        kind, matched = "not_carried", None
    elif all(h.available == 0 for h in hits):
        kind, matched = "out_of_stock", hits[0].product_id
    else:
        return
    sig = DemandSignal(signal_id=uuid.uuid4().hex, store_id=store_id, query_text=query,
                       matched_product_id=matched, type=kind)
    db.demand_signals(store_id).document(sig.signal_id).set(sig.model_dump())
