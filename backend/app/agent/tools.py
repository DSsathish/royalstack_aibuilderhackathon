"""Agent tools. Plain functions; docstrings are what the model reads.

Every tool reads store_id / mode / cart_id from tool_context.state and returns a small dict.
"""

import re
import uuid

from types import SimpleNamespace

from google.adk.tools import ToolContext

from app.domain.models import DemandSignal
from app.services import cart as cart_svc
from app.services import catalog, db, forecast as forecast_svc, insights, reorder, verification
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
    found = [s for s in (catalog.get_product(store_id, sid) for sid in v.substitutes) if s and s.available > 0]
    products, _ = catalog.product_map(store_id)
    for attr in ("subcategory", "category"):          # exact matches, not keyword hits: soya milk never falls back to dairy
        key = getattr(v, attr)
        if len(found) >= 3 or not key:
            continue
        for p in sorted(products.values(), key=lambda p: p.name):
            if p.product_id != v.product_id and getattr(p, attr) == key and p.product_id not in {f.product_id for f in found}:
                alt = catalog.get_product(store_id, p.product_id)
                if alt and alt.available > 0:
                    found.append(alt)
    return found[:limit]


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
    return {**loc.model_dump(), "product_id": product_id, "name": v.name,
            "directions": f"Aisle {loc.aisle}, bay {loc.bay}, shelf {loc.shelf}, {loc.side} side"}


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


TOOLS_BY_MODE = {
    "instore": [search_products, get_product, suggest_substitutes, navigate_to, record_demand_signal,
                remove_from_cart, view_cart, start_checkout, get_offers],      # items enter the cart only by scanning
    "online": [search_products, get_product, suggest_substitutes, record_demand_signal,
               add_to_cart, remove_from_cart, view_cart, start_checkout, get_offers],
    "owner": [],      # filled below from owner_tools: a separate agent with full access to the store
}

from app.agent import owner_tools as _ot  # noqa: E402

TOOLS_BY_MODE["owner"] = [
    _ot.store_snapshot, _ot.stock_report, _ot.find_products, get_low_stock, _ot.sales_report, forecast_demand, _ot.reorder_drafts, draft_purchase_order,
    _ot.demand_signals, _ot.customers_overview, _ot.list_offers, _ot.exit_summary, get_anomalies, _ot.sync_status, _ot.floor_map_summary,
    search_products, get_product,
    _ot.set_reorder_rule, _ot.adjust_stock, _ot.record_shelf_count, _ot.update_price, _ot.move_product, _ot.create_offer,
    _ot.set_offer_active, _ot.adjust_points, _ot.approve_purchase_order,
]
