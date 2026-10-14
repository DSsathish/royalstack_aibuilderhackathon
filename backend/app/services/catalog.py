"""Read-side product lookup: by id, by barcode, by search. Writes demand signals."""

import math
import re
import time
import uuid

from pydantic import BaseModel

from app.domain.models import DemandSignal, Location, Product
from app.services import db, gemini, inventory

CACHE_TTL_S = 60
_cache: dict[str, tuple[float, list[Product], dict[str, Location]]] = {}


class ProductView(Product):
    available: int = 0
    location: Location | None = None


def invalidate(store_id: str) -> None:
    _cache.pop(store_id, None)


def _load(store_id: str) -> tuple[list[Product], dict[str, Location]]:
    hit = _cache.get(store_id)
    if hit and time.time() - hit[0] < CACHE_TTL_S:
        return hit[1], hit[2]
    products = [Product(**d.to_dict()) for d in db.products(store_id).stream()]
    locations = {d.id: Location(**d.to_dict()) for d in db.locations(store_id).stream()}
    _cache[store_id] = (time.time(), products, locations)
    return products, locations


def _view(store_id: str, p: Product, locations: dict[str, Location]) -> ProductView:
    return ProductView(**p.model_dump(), available=inventory.available(store_id, p.product_id),
                       location=locations.get(p.product_id))


def get_product(store_id: str, product_id: str) -> ProductView | None:
    products, locations = _load(store_id)
    p = next((p for p in products if p.product_id == product_id), None)
    return _view(store_id, p, locations) if p else None


def get_by_barcode(store_id: str, barcode: str) -> ProductView | None:
    products, locations = _load(store_id)
    p = next((p for p in products if p.barcode == barcode), None)
    return _view(store_id, p, locations) if p else None


# --- search -----------------------------------------------------------------

_TOKEN = re.compile(r"[\w஀-௿ऀ-ॿ]+")  # latin, tamil, devanagari


def _tokens(text: str) -> set[str]:
    return set(_TOKEN.findall(text.lower()))


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

    scored = []
    for p in products:
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
