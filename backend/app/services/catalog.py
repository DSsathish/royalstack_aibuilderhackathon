"""Read-side product lookup: by id, by barcode, by search. Writes demand signals."""

import math
import re
import time
import uuid

from pydantic import BaseModel

from app.domain.models import DemandSignal, Location, Product
from app.domain import classify, lexicon
from app.services import db, gemini, inventory

CACHE_TTL_S = 60
VERSION_CHECK_S = 2       # how often an instance asks Firestore whether the catalog changed elsewhere
_cache: dict[str, dict] = {}


class ProductView(Product):
    available: int = 0
    location: Location | None = None


def invalidate(store_id: str) -> None:
    _cache.pop(store_id, None)
    _sections_cache.pop(store_id, None)


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
    _cache[store_id] = {"at": t, "checked": t, "version": version, "products": products, "locations": locations,
                        "weights": _token_weights(products)}
    return products, locations


def _fields(p: Product) -> tuple[set[str], set[str], set[str], set[str]]:
    return _tokens(p.name), _tokens(p.brand), _tokens(" ".join(p.tags)), _tokens(f"{p.category} {p.subcategory}")


def _token_weights(products: list[Product]) -> dict[str, float]:
    """How telling a word is: one that appears in few products weighs more than one in many ("pack", "1l"). Smoothed
    inverse document frequency scaled so a typical word weighs 1.0, which keeps keyword and semantic scores on the
    same footing as before; rare and common words then differ by ratio, not by scale."""
    df: dict[str, int] = {}
    for p in products:
        for tok in set().union(*_fields(p)):
            df[tok] = df.get(tok, 0) + 1
    n = max(1, len(products))
    raw = {tok: 1.0 + math.log((n + 1) / (c + 1)) for tok, c in df.items()}
    mean = sum(raw.values()) / len(raw) if raw else 1.0
    return {tok: (v / mean) * (FORM_WEIGHT if tok in lexicon.FORM_WORDS or _PACK.match(tok) else 1.0) for tok, v in raw.items()}


def token_weights(store_id: str) -> dict[str, float]:
    _load(store_id)
    return _cache[store_id].get("weights") or {}


def _view(store_id: str, p: Product, locations: dict[str, Location]) -> ProductView:
    return ProductView(**p.model_dump(), available=inventory.available(store_id, p.product_id),
                       location=locations.get(p.product_id))


def blocks(store_id: str) -> dict[str, dict]:
    """Floor-map blocks by name (kind and floor), read fresh: the owner edits them rarely, the assistant reads them often."""
    doc = db.store_ref(store_id).get().to_dict() or {}
    return {b["aisle"]: b for b in doc.get("floor_map", [])}


SECTIONS_TTL_S = 600
FORM_WEIGHT = 0.3            # packaging and unit words (lexicon.FORM_WORDS) and pack sizes count this much of a telling word
_PACK = re.compile(r"^\d+(\.\d+)?(kg|g|gm|ml|l|ltr|litre|liter|pcs?|pc|x|w)?$")   # 500ml, 5kg, 12, 9w: a size, not a product
_sections_cache: dict[str, tuple[float, dict]] = {}


def sections(store_id: str) -> dict:
    """The whole shop at a glance: every category and subcategory with how many products it holds and how many are in
    stock. Feeds the assistant's prompt and the store_overview tool, so it is cached for a minute."""
    hit = _sections_cache.get(store_id)
    if hit and time.time() - hit[0] < SECTIONS_TTL_S:
        return hit[1]
    products, _ = product_map(store_id)
    stock = {d.id: max(0, (d.to_dict() or {}).get("on_hand", 0) - (d.to_dict() or {}).get("reserved", 0)) for d in db.inventory(store_id).stream()}
    cats: dict[str, dict] = {}
    for p in products.values():
        cat = cats.setdefault(p.category or "General", {"category": p.category or "General", "total": 0, "in_stock": 0, "subs": {}})
        sub = cat["subs"].setdefault(p.subcategory or "Other", {"name": p.subcategory or "Other", "total": 0, "in_stock": 0})
        available = stock.get(p.product_id, 0) > 0
        for bucket in (cat, sub):
            bucket["total"] += 1
            bucket["in_stock"] += 1 if available else 0
    out = {"total": len(products), "in_stock": sum(c["in_stock"] for c in cats.values()), "categories": []}
    out["out_of_stock"] = out["total"] - out["in_stock"]
    for c in sorted(cats.values(), key=lambda c: -c["total"]):
        subs = sorted(c["subs"].values(), key=lambda s: -s["total"])
        out["categories"].append({"category": c["category"], "total": c["total"], "in_stock": c["in_stock"], "out_of_stock": c["total"] - c["in_stock"],
                                  "subcategories": [{**s, "out_of_stock": s["total"] - s["in_stock"]} for s in subs]})
    _sections_cache[store_id] = (time.time(), out)
    return out


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
    """Lower-cased words, plurals folded ("chocolates" meets "chocolate"); models often write snake_case ids."""
    return {t[:-1] if len(t) > 3 and t.endswith("s") and not t.endswith("ss") else t
            for t in _TOKEN.findall(text.lower().replace("_", " "))}


def _keyword_score(q: set[str], p: Product, weights: dict[str, float] | None = None) -> float:
    """Each query word scores once: 3 in the name, else 2 as a brand or tag alias, else 1 from the category or
    subcategory, scaled by how telling the word is (packaging words barely count). A product that carries every query
    word gets half as much again, so "chocolate bar" prefers a chocolate bar to a soap bar; the semantic score decides
    between partial matches."""
    name, brand, tags, cat = _fields(p)
    weights = weights or {}
    score, matched = 0.0, 0
    for tok in q:
        field = 3 if tok in name else 2 if tok in brand or tok in tags else 1 if tok in cat else 0
        if field:
            matched += 1
            score += field * weights.get(tok, 1.0)
    if q and matched == len(q):
        score *= 1.5
    return score


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
    weights = token_weights(store_id)
    scored = []
    for p in products:
        if wanted and p.use != wanted:
            continue                      # "dog biscuits" means pet products only
        if not wanted and p.use == "pet":
            continue                      # nobody asked for pets: pet products never answer a people's query
        kw = _keyword_score(q, p, weights)
        sem = _cosine(qvec, p.embedding)
        if kw > 0 or sem > 0.6:
            scored.append((kw + 5 * sem, p))
    scored.sort(key=lambda t: t[0], reverse=True)
    seen, picked = set(), []
    for _, p in scored:                     # the same name twice (two listings of one product) shows once
        name = " ".join(p.name.lower().split())
        if name in seen:
            continue
        seen.add(name); picked.append(p)
        if len(picked) == k:
            break
    hits = [_view(store_id, p, locations) for p in picked]

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
