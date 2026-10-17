"""Agent tools. Plain functions; docstrings are what the model reads.

Every tool reads store_id / mode / cart_id from tool_context.state and returns a small dict.
"""

import uuid

from types import SimpleNamespace

from google.adk.tools import ToolContext

from app.domain.models import DemandSignal
from app.services import cart as cart_svc
from app.services import catalog, db, forecast as forecast_svc, insights, reorder, verification
from app.services.catalog import ProductView


def _row(v: ProductView) -> dict:
    loc = v.location
    return {"product_id": v.product_id, "name": v.name, "brand": v.brand, "price": v.price, "mrp": v.mrp,
            "unit": v.unit, "available": v.available,
            "aisle": loc.aisle if loc else "", "bay": loc.bay if loc else 0}


def _cart_summary(c) -> dict:
    subtotal, savings, total = cart_svc.totals(c)
    return {"items": [{"product_id": i.product_id, "name": i.name, "qty": i.qty, "unit_price": i.unit_price}
                      for i in c.items],
            "count": sum(i.qty for i in c.items), "subtotal": subtotal, "savings": savings, "total": total}


def search_products(query: str, tool_context: ToolContext, max_results: int = 6) -> dict:
    """Search the store catalog by product name, brand, category or a need (e.g. "headache", "breakfast").
    Works in English, Tamil and Hindi. Returns products with price, available stock and aisle.
    signal is "found", "out_of_stock" (all matches have no stock) or "not_carried" (no match)."""
    hits = catalog.search(tool_context.state["store_id"], query, k=max(1, min(max_results, 10)))
    if not hits:
        signal = "not_carried"
    elif all(h.available == 0 for h in hits):
        signal = "out_of_stock"
    else:
        signal = "found"
    return {"products": [_row(h) for h in hits], "signal": signal}


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
    found = [catalog.get_product(store_id, s) for s in v.substitutes]
    found = [s for s in found if s and s.available > 0]
    if len(found) < 3 and v.subcategory:
        for alt in catalog.search(store_id, v.subcategory, k=10):
            if alt.product_id != product_id and alt.available > 0 and alt.product_id not in {f.product_id for f in found}:
                found.append(alt)
    return {"products": [_row(f) for f in found[:4]]}


def navigate_to(product_id: str, tool_context: ToolContext) -> dict:
    """Where a product is on the shop floor: aisle, bay, shelf, side, map coordinates and spoken directions."""
    v = catalog.get_product(tool_context.state["store_id"], product_id)
    if not v or not v.location:
        return {"error": "no_location"}
    loc = v.location
    return {**loc.model_dump(), "product_id": product_id, "name": v.name,
            "directions": f"Aisle {loc.aisle}, bay {loc.bay}, shelf {loc.shelf}, {loc.side} side"}


def add_to_cart(product_id: str, qty: int, tool_context: ToolContext) -> dict:
    """Add qty units of a product to the shopper's cart. Use the product_id from search_products; a product name
    also works and is matched to the catalog. Fails with out_of_stock, item_limit or unknown_product."""
    s = tool_context.state
    resolved = None
    if not catalog.get_product(s["store_id"], product_id):
        hits = [h for h in catalog.search(s["store_id"], product_id.replace("-", " "), k=3) if h.available > 0]
        if not hits:
            return {"ok": False, "error": "unknown_product"}
        resolved, product_id = product_id, hits[0].product_id
    res = cart_svc.add(s["store_id"], s["cart_id"], product_id, qty, via="chat", mode=s.get("mode", "online"))
    if isinstance(res, str):
        return {"ok": False, "error": res}
    out = {"ok": True, "cart": _cart_summary(res)}
    if resolved:
        out["resolved_from"] = resolved
    return out


def remove_from_cart(product_id: str, tool_context: ToolContext) -> dict:
    """Remove a product line from the cart."""
    s = tool_context.state
    return {"ok": True, "cart": _cart_summary(cart_svc.remove(s["store_id"], s["cart_id"], product_id))}


def view_cart(tool_context: ToolContext) -> dict:
    """Current cart lines, item count, subtotal, savings and total."""
    s = tool_context.state
    return {"ok": True, "cart": _cart_summary(cart_svc.get(s["store_id"], s["cart_id"]))}


def start_checkout(tool_context: ToolContext) -> dict:
    """Begin checkout for the current cart. Returns the total the shopper will pay."""
    s = tool_context.state
    c = cart_svc.get(s["store_id"], s["cart_id"])
    if not c.items:
        return {"ok": False, "error": "empty_cart"}
    return {"ok": True, "cart_id": c.cart_id, "total": cart_svc.totals(c)[2]}


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
                add_to_cart, remove_from_cart, view_cart, start_checkout],
    "online": [search_products, get_product, suggest_substitutes, record_demand_signal,
               add_to_cart, remove_from_cart, view_cart, start_checkout],
    "owner": [search_products, get_product, get_low_stock, forecast_demand, draft_purchase_order, get_anomalies],
}
