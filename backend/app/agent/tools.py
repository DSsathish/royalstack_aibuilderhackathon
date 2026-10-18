"""Agent tools. Plain functions; docstrings are what the model reads.

Every tool reads store_id / mode / cart_id from tool_context.state and returns a small dict.
"""

import re
import uuid
from collections import Counter

from types import SimpleNamespace

from google.adk.tools import ToolContext

from app.domain.models import DemandSignal
from app.services import cart as cart_svc
from app.services import catalog, db, facts, forecast as forecast_svc, insights, reorder, verification
from app.services.catalog import ProductView


_UNITS = {"kg": "kg", "kgs": "kg", "g": "g", "gm": "g", "gms": "g", "gram": "g", "grams": "g", "l": "l", "ltr": "l", "litre": "l", "liter": "l",
          "litres": "l", "liters": "l", "ml": "ml", "pc": "pc", "pcs": "pc", "piece": "pc", "pieces": "pc", "nos": "pc", "tablets": "pc", "tablet": "pc",
          "capsules": "pc", "sachets": "pc", "bags": "pc", "pack": "pc"}
_PACK = re.compile(r"(?:(\d+)\s*[x×]\s*)?(\d+(?:\.\d+)?)\s*(" + "|".join(sorted(_UNITS, key=len, reverse=True)) + r")\b", re.I)


def pack_size(name: str) -> dict | None:
    """The pack size written in a product name: "Rice 5kg" -> 5 kg, "12 x 70 g" -> 840 g. None when there is none."""
    m = _PACK.search(name)
    if not m:
        return None
    count, size = int(m.group(1) or 1), float(m.group(2))
    total = count * size
    return {"size": int(total) if total.is_integer() else total, "unit": _UNITS[m.group(3).lower()]}


def _stock_note(available: int) -> str:
    return "out of stock" if available <= 0 else f"only {available} left" if available <= 3 else "in stock"


def _row(v: ProductView) -> dict:
    loc = v.location
    row = {"product_id": v.product_id, "name": v.name, "brand": v.brand, "price": v.price, "mrp": v.mrp,
           "unit": v.unit, "available": v.available, "in_stock": v.available > 0, "stock_note": _stock_note(v.available),
           "aisle": loc.aisle if loc else "", "bay": loc.bay if loc else 0}
    pack = pack_size(v.name)
    if pack:
        row["pack"] = pack
    return row


def _alternatives(store_id: str, v: ProductView, limit: int = 4) -> list[ProductView]:
    """In-stock stand-ins for a product: its listed substitutes, then the same subcategory, then the same category."""
    found = [s for s in (catalog.get_product(store_id, sid) for sid in v.substitutes) if s and s.available > 0 and s.use == v.use]
    products, _ = catalog.product_map(store_id)
    for attr in ("subcategory", "category"):          # exact matches, not keyword hits: soya milk never falls back to dairy
        key = getattr(v, attr)
        if len(found) >= 3 or not key:
            continue
        for p in sorted(products.values(), key=lambda p: p.name):
            if (p.product_id != v.product_id and getattr(p, attr) == key and p.use == v.use      # never pet food for a person
                    and p.product_id not in {f.product_id for f in found}):
                alt = catalog.get_product(store_id, p.product_id)
                if alt and alt.available > 0:
                    found.append(alt)
    return found[:limit]


FLOOR_NAMES = {1: "ground floor", 2: "first floor", 3: "second floor", 4: "third floor", 5: "fourth floor", 6: "fifth floor"}
KIND_LABEL = {"aisle": "Aisle", "chiller": "Chiller", "freezer": "Freezer", "counter": "Counter"}


def directions_for(store_id: str, loc) -> dict:
    """Spoken directions from a location and the floor map: "Chiller Dairy, bay 2, left side, first floor"."""
    block = catalog.blocks(store_id).get(loc.aisle, {})
    kind, floor = block.get("kind", "aisle"), int(block.get("floor", 1))
    label = KIND_LABEL.get(kind, "Aisle")
    where = f"{label} {loc.aisle}" if not loc.aisle.lower().startswith(label.lower()) else loc.aisle
    text = f"{where}, bay {loc.bay}, shelf {loc.shelf}, {loc.side} side" + (f", {FLOOR_NAMES.get(floor, f'floor {floor}')}" if floor > 1 else "")
    return {"kind": kind, "floor": floor, "directions": text}


def _brief(v: ProductView) -> dict:
    row = {"product_id": v.product_id, "name": v.name, "price": v.price, "available": v.available}
    pack = pack_size(v.name)
    if pack:
        row["pack"] = pack
    return row


def _cart_summary(c, segment: str = "guest") -> dict:
    p = cart_svc.pricing(c.store_id, c, segment)
    return {"items": [{"product_id": i.product_id, "name": i.name, "qty": i.qty, "unit_price": i.unit_price}
                      for i in c.items],
            "count": sum(i.qty for i in c.items), "subtotal": p.subtotal, "savings": p.savings,
            "discounts": [{"name": l.name, "amount": l.amount} for l in p.discounts], "discount_total": p.discount_total, "total": p.total}


def _segment(state) -> str:
    from app.services import customers
    return state.get("segment") or customers.segment_of(state["store_id"], state.get("customer_id"))


SECTION_STOPWORDS = frozenset({"and", "the", "of", "all", "list", "full"})


def _section_tokens(text: str) -> list[str]:
    """Catalog section names are English; the tokens are singularised so "dals" meets "Dals and Pulses"."""
    toks = re.sub(r"[^a-z0-9 ]+", " ", (text or "").lower()).split()
    return [t[:-1] if len(t) > 3 and t.endswith("s") else t for t in toks if t not in SECTION_STOPWORDS]


def store_overview(tool_context: ToolContext) -> dict:
    """The whole shop at a glance: every section with its subsections, how many products each holds, how many are in
    stock and out of stock, and the totals. For "what do you sell", "which sections do you have", "how many products",
    "what is out of stock". The screen shows the table; name the biggest sections and offer to list any of them."""
    s = catalog.sections(tool_context.state["store_id"])
    rows = [{"Section": c["category"], "Products": c["total"], "In stock": c["in_stock"], "Out of stock": c["out_of_stock"],
             "Subsections": ", ".join(f"{x['name']} ({x['in_stock']}/{x['total']})" for x in c["subcategories"][:12]) + (" …" if len(c["subcategories"]) > 12 else "")}
            for c in s.get("categories", [])]
    return {"total": s.get("total", 0), "in_stock": s.get("in_stock", 0), "out_of_stock": s.get("out_of_stock", 0),
            "sections": len(rows), "columns": ["Section", "Products", "In stock", "Out of stock", "Subsections"], "rows": rows, "count": len(rows)}


def list_category(category: str, tool_context: ToolContext, status: str = "in_stock", page: int = 1, limit: int = 40) -> dict:
    """Every product in one section of the store, for requests like "list all the vegetables you have", "what dals are
    there", "what is out of stock in dairy". category is the section's name from the sections paragraph when you can
    name it; the shopper's own words in any language also work. status is in_stock (default), out_of_stock or all;
    page is 1, 2, ... for "next" or "more" (limit rows per page). Returns total, in_stock, out_of_stock, the rows shown
    (Product, Price, Stock), page, pages and more. Say the count, read the first ten names, and offer to continue; the
    screen shows the list. If total is 0 the section was not found: say so and ask for a product name; never say it is
    out of stock."""
    store_id = tool_context.state["store_id"]
    products, _ = catalog.product_map(store_id)
    want = _section_tokens(category)
    scored = []
    for p in products.values():
        hay = " ".join(_section_tokens(f"{p.category} {p.subcategory}"))
        score = sum(1 for t in want if t and t in hay)
        if score:
            scored.append((score, p))
    matched_by = "section"
    if scored:
        best = max(s for s, _ in scored)
        picked = [p for s, p in scored if s == best]
    else:                                       # another language or another word for it: let the search say which section
        hits = catalog.search(store_id, category, k=8)
        counts = Counter((h.subcategory or h.category) for h in hits)
        if counts and counts.most_common(1)[0][1] >= 3:
            top = counts.most_common(1)[0][0]
            picked = [p for p in products.values() if (p.subcategory or p.category) == top]
            matched_by = "section"
        else:
            matched_by = "search"
            picked = list(hits)
    stock = {d.id: max(0, (d.to_dict() or {}).get("on_hand", 0) - (d.to_dict() or {}).get("reserved", 0)) for d in db.inventory(store_id).stream()}
    items = sorted(((p, stock.get(p.product_id, 0)) for p in picked), key=lambda x: x[0].name.lower())
    in_stock = [(p, n) for p, n in items if n > 0]
    out_of_stock = [(p, n) for p, n in items if n == 0]
    status = status if status in ("in_stock", "out_of_stock", "all") else "in_stock"
    wanted = {"in_stock": in_stock, "out_of_stock": out_of_stock, "all": items}[status]
    per = max(1, min(limit, 100)); page = max(1, page); pages = max(1, -(-len(wanted) // per))
    shown = wanted[(page - 1) * per: page * per]
    sections = sorted({p.subcategory or p.category for p in picked})[:4]
    return {"category": ", ".join(sections) if matched_by == "section" else category, "matched_by": matched_by, "status": status,
            "total": len(items), "in_stock": len(in_stock), "out_of_stock": len(out_of_stock), "shown": len(shown),
            "page": page, "pages": pages, "more": max(0, len(wanted) - page * per),
            "columns": ["Product", "Price", "Stock"],
            "rows": [{"Product": p.name, "Price": f"₹{float(p.price):g}", "Stock": n if n > 0 else "out of stock"} for p, n in shown],
            "signal": "found" if items else "not_carried",
            **({} if items else {"note": "No section or product matched. Say you could not find that section and ask for a product name; do not say it is out of stock."})}


def search_products(query: str, tool_context: ToolContext, max_results: int = 6) -> dict:
    """Search the store catalog by product name, brand, category or a need (e.g. "headache", "breakfast").
    Works in English, Tamil and Hindi. Each product carries price, in_stock, stock_note ("out of stock", "only 2 left",
    "in stock"), aisle, pack (size and unit read from the name, e.g. 5 kg) and, when it is out of stock, alternatives
    that are in stock. out_of_stock lists the names with no stock. signal is "found", "out_of_stock" (every match has
    no stock) or "not_carried" (no match)."""
    store_id = tool_context.state["store_id"]
    hits = catalog.search(store_id, query, k=max(1, min(max_results, 10)))
    if not hits:
        signal = "not_carried"
    elif all(h.available == 0 for h in hits):
        signal = "out_of_stock"
    else:
        signal = "found"
    rows = []
    for h in hits:
        row = _row(h)
        if h.available <= 0:
            row["alternatives"] = [_brief(a) for a in _alternatives(store_id, h, limit=3)]
        rows.append(row)
    return {"products": rows, "signal": signal, "out_of_stock": [h.name for h in hits if h.available <= 0]}


def get_product(product_id: str, tool_context: ToolContext) -> dict:
    """Full details for one product: description, tags, substitutes, stock, and shelf location."""
    v = catalog.get_product(tool_context.state["store_id"], product_id)
    if not v:
        return {"error": "unknown_product"}
    return {**_row(v), "category": v.category, "subcategory": v.subcategory, "description": v.description,
            "tags": v.tags, "substitutes": v.substitutes, "is_high_value": v.is_high_value,
            "location": v.location.model_dump() if v.location else None}


def suggest_substitutes(product_id: str, tool_context: ToolContext) -> dict:
    """Alternatives for a product that is out of stock or not wanted: its listed substitutes first,
    then in-stock products from the same subcategory."""
    store_id = tool_context.state["store_id"]
    v = catalog.get_product(store_id, product_id)
    if not v:
        return {"error": "unknown_product"}
    return {"products": [_row(f) for f in _alternatives(store_id, v)]}


def navigate_to(product_id: str, tool_context: ToolContext) -> dict:
    """Where a product is on the shop floor: aisle, bay, shelf, side, map coordinates and spoken directions."""
    v = catalog.get_product(tool_context.state["store_id"], product_id)
    if not v or not v.location:
        return {"error": "no_location"}
    loc = v.location
    return {**loc.model_dump(), "product_id": product_id, "name": v.name, **directions_for(tool_context.state["store_id"], loc)}


def add_to_cart(product_id: str, qty: int, tool_context: ToolContext) -> dict:
    """Add qty units of a product to the shopper's cart. Pass the product_id from a search_products result, or,
    when you only know the product from the conversation, its exact name (for example "India Gate Basmati Rice 5kg").
    Never invent an id. Fails with out_of_stock (alternatives included), insufficient_stock (available tells how many
    are left), item_limit or unknown_product."""
    s = tool_context.state
    resolved = None
    view = catalog.get_product(s["store_id"], product_id)
    if not view:
        exact = catalog.get_by_sku(s["store_id"], product_id)
        hits = [exact] if exact else [h for h in catalog.search(s["store_id"], product_id.replace("-", " ").replace("_", " "), k=3) if h.available > 0]
        if not hits:
            return {"ok": False, "error": "unknown_product"}
        resolved, product_id, view = product_id, hits[0].product_id, hits[0]
    if view.available <= 0:
        return {"ok": False, "error": "out_of_stock", "name": view.name, "alternatives": [_brief(a) for a in _alternatives(s["store_id"], view, limit=3)]}
    if qty > view.available:
        return {"ok": False, "error": "insufficient_stock", "name": view.name, "available": view.available, "requested": qty}
    res = cart_svc.add(s["store_id"], s["cart_id"], product_id, qty, via="chat", mode=s.get("mode", "online"))
    if isinstance(res, str):
        return {"ok": False, "error": res}
    out = {"ok": True, "cart": _cart_summary(res, _segment(s))}
    if resolved:
        out["resolved_from"] = resolved
    return out


def remove_from_cart(product_id: str, tool_context: ToolContext) -> dict:
    """Remove a product line from the cart."""
    s = tool_context.state
    return {"ok": True, "cart": _cart_summary(cart_svc.remove(s["store_id"], s["cart_id"], product_id), _segment(s))}


def view_cart(tool_context: ToolContext) -> dict:
    """Current cart lines, item count, subtotal, savings and total."""
    s = tool_context.state
    return {"ok": True, "cart": _cart_summary(cart_svc.get(s["store_id"], s["cart_id"]), _segment(s))}


def start_checkout(tool_context: ToolContext) -> dict:
    """Begin checkout for the current cart. Returns the total the shopper will pay after offers."""
    s = tool_context.state
    c = cart_svc.get(s["store_id"], s["cart_id"])
    if not c.items:
        return {"ok": False, "error": "empty_cart"}
    return {"ok": True, "cart_id": c.cart_id, "total": cart_svc.pricing(c.store_id, c, _segment(s)).total}


def get_offers(tool_context: ToolContext) -> dict:
    """Offers and discounts this shopper can use right now: store-wide ones plus any for their segment."""
    from app.services import offers
    s = tool_context.state
    items = [offers.public(s["store_id"], o) for o in offers.applicable(s["store_id"], _segment(s))]
    return {"ok": True, "offers": [{"name": o["name"], "detail": o["detail"]} for o in items]}


def record_demand_signal(requested_item: str, tool_context: ToolContext) -> dict:
    """Record that a shopper asked for a specific product this store does not carry
    (e.g. "oat milk"). Call it once per such request, with the item name as the shopper said it."""
    store_id = tool_context.state["store_id"]
    sig = DemandSignal(signal_id=uuid.uuid4().hex, store_id=store_id, query_text=requested_item.strip()[:200],
                       type="not_carried", source="agent")
    db.demand_signals(store_id).document(sig.signal_id).set(sig.model_dump())
    return {"ok": True}


def get_low_stock(tool_context: ToolContext, limit: int = 20) -> dict:
    """Owner tool: products at or below their reorder point, with supplier."""
    store_id = tool_context.state["store_id"]
    products, _ = catalog.product_map(store_id)
    items = []
    for d in db.inventory(store_id).stream():
        inv = d.to_dict()
        available = inv["on_hand"] - inv.get("reserved", 0)
        if available <= inv.get("reorder_point", 0):
            v = products.get(d.id)
            items.append({"product_id": d.id, "name": v.name if v else d.id, "available": available,
                          "reorder_point": inv.get("reorder_point", 0), "supplier_id": inv.get("supplier_id", "")})
    items.sort(key=lambda i: i["available"])
    return {"items": items[:limit]}


def forecast_demand(tool_context: ToolContext, product_id: str = "", horizon_days: int = 14) -> dict:
    """Owner tool: expected daily demand for the next days from the store's forecast model.
    With a product_id returns that product's daily forecast; without it, the products with the highest expected demand."""
    store_id = tool_context.state["store_id"]
    if product_id:
        f = forecast_svc.get(store_id, product_id)
        if not f:
            return {"error": "no_forecast"}
        p = catalog.get_product(store_id, product_id)
        return {"product_id": product_id, "name": p.name if p else product_id, "avg_daily": f["avg_daily"],
                "daily": f["daily"][:max(1, min(horizon_days, 14))], "available": p.available if p else None}
    top = sorted(forecast_svc.all(store_id).items(), key=lambda kv: -kv[1]["avg_daily"])[:10]
    return {"top": [{"product_id": pid, "name": (catalog.get_product(store_id, pid) or SimpleNamespace(name=pid)).name,
                     "avg_daily": f["avg_daily"]} for pid, f in top]}


def draft_purchase_order(tool_context: ToolContext) -> dict:
    """Owner tool: create purchase-order drafts for everything at or below its reorder point, one per supplier.
    Drafts wait for the owner's approval in the dashboard; nothing is sent."""
    drafts = reorder.draft(tool_context.state["store_id"], created_by="agent")
    return {"drafts": [{"po_id": d.po_id, "supplier": d.supplier_name, "lines": len(d.lines), "summary": d.summary,
                        "items": [f"{l['name']} x{l['qty']}" for l in d.lines]} for d in drafts]}


def get_anomalies(tool_context: ToolContext, days: int = 7) -> dict:
    """Owner tool: exit-verification flags and stock-count discrepancies (possible shrink) for the last days."""
    store_id = tool_context.state["store_id"]
    return {"exits": verification.summary(store_id, days), "shrink": insights.shrink(store_id)[:10],
            "asked_but_not_carried": insights.signals(store_id, days)["not_carried"][:10]}


def _find(store_id: str, ref: str) -> ProductView | None:
    """A catalog product by id, SKU, barcode or name, or None."""
    view = catalog.get_product(store_id, ref) or catalog.get_by_sku(store_id, ref)
    if view:
        return view
    hits = catalog.search(store_id, ref.replace("-", " ").replace("_", " "), k=1)
    return hits[0] if hits else None


def product_facts(question: str, product_id: str = "", tool_context: ToolContext = None) -> dict:
    """What the catalog does not say about a product or ingredient: ingredients, nutrition, allergens, material, how to
    use or store it, where it comes from, or what a term such as "A2 milk" means. Looked up in public sources and cited.
    Pass product_id (or the exact product name) when the question is about a catalog product; leave it empty for a
    general question. The result's note must be repeated when health or allergies are involved."""
    s = tool_context.state
    product = _find(s["store_id"], product_id) if product_id else None
    return facts.lookup(s["store_id"], s["session_id"], question, product, s.get("language") or "auto")


TOOLS_BY_MODE = {
    "instore": [search_products, list_category, store_overview, get_product, suggest_substitutes, navigate_to, record_demand_signal,
                remove_from_cart, view_cart, start_checkout, get_offers, product_facts],      # items enter the cart only by scanning
    "online": [search_products, list_category, store_overview, get_product, suggest_substitutes, record_demand_signal,
               add_to_cart, remove_from_cart, view_cart, start_checkout, get_offers, product_facts],
    "owner": [],      # filled below from owner_tools: a separate agent with full access to the store
}

from app.agent import owner_tools as _ot  # noqa: E402

TOOLS_BY_MODE["owner"] = [
    _ot.store_snapshot, _ot.stock_report, _ot.find_products, get_low_stock, _ot.sales_report, forecast_demand, _ot.reorder_drafts, draft_purchase_order,
    _ot.demand_signals, _ot.customers_overview, _ot.list_offers, _ot.exit_summary, get_anomalies, _ot.sync_status, _ot.floor_map_summary,
    search_products, get_product, product_facts,
    _ot.set_reorder_rule, _ot.adjust_stock, _ot.record_shelf_count, _ot.update_price, _ot.move_product, _ot.create_offer,
    _ot.set_offer_active, _ot.adjust_points, _ot.approve_purchase_order,
    _ot.connect_source, _ot.apply_source, _ot.connectors_status,
]
