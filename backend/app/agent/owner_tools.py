"""Owner agent tools: everything about one store. Plain functions; docstrings are what the model reads.

Reading tools return figures or {columns, rows}. Acting tools take confirm=False and only describe their plan until the
model calls them again with confirm=True after the owner agreed; every act writes an audit entry naming the owner."""

import uuid
from datetime import datetime, timedelta, timezone

from google.adk.tools import ToolContext
from google.cloud.firestore_v1 import FieldFilter

from app.domain.models import Location, Offer, now
from app.services import catalog, db, forecast as forecast_svc, insights, reorder, verification
from app.services import customers as customers_svc
from app.services import offers as offers_svc
from app.services import points as points_svc
from app.services import sync as sync_svc
from app.services.catalog import ProductView

IST = timezone(timedelta(hours=5, minutes=30))


def _sid(ctx: ToolContext) -> str:
    return ctx.state["store_id"]


def _actor(ctx: ToolContext) -> str:
    return ctx.state.get("user_id") or "agent"


def _audit(store_id: str, actor: str, action: str, payload: dict) -> None:
    db.audit(store_id).document(uuid.uuid4().hex).set({"actor": actor, "action": action, "created_at": now(), "payload": payload})


def _find(store_id: str, product: str) -> ProductView | None:
    """An id, a SKU, a barcode or a name; the owner may mean an out-of-stock item, so stock is not a filter."""
    key = product.strip()
    v = catalog.get_product(store_id, key) or catalog.get_by_sku(store_id, key)
    if v:
        return v
    hits = catalog.search(store_id, key.replace("-", " ").replace("_", " "), k=1)
    return hits[0] if hits else None


def _plan(text: str, **args) -> dict:
    return {"ok": False, "needs_confirmation": True, "plan": text, "args": args}


def _rows(columns: list[str], rows: list[dict]) -> dict:
    return {"columns": columns, "rows": rows, "count": len(rows)}


# --- reading -----------------------------------------------------------------------------------------------------

def store_snapshot(tool_context: ToolContext) -> dict:
    """The daily briefing: sales today, stock that needs attention, drafts and exit flags waiting, demand signals,
    signed-in customers and live offers. Call this when the owner greets you or asks how the store is doing."""
    sid = _sid(tool_context)
    o = insights.overview(sid)
    signed_in = len(list(db.customers(sid).select([]).stream()))
    live = len(offers_svc.applicable(sid, "all"))
    attention = []
    if o["out_of_stock"]:
        attention.append(f"{o['out_of_stock']} products are out of stock")
    if o["low_stock"]:
        attention.append(f"{o['low_stock']} products are at or below their reorder point")
    if o["open_drafts"]:
        attention.append(f"{o['open_drafts']} purchase-order drafts wait for approval")
    if o["open_flags"]:
        attention.append(f"{o['open_flags']} exit flags need review")
    if o["asked_not_found"]:
        attention.append(f"shoppers asked for {o['asked_not_found']} things we do not carry today")
    return {"today": o["today"], "low_stock": o["low_stock"], "out_of_stock": o["out_of_stock"], "dead_stock": o["dead_stock"],
            "open_drafts": o["open_drafts"], "open_flags": o["open_flags"], "asked_not_found": o["asked_not_found"],
            "signed_in_customers": signed_in, "live_offers": live, "attention": attention}


def stock_report(tool_context: ToolContext) -> dict:
    """The full stock picture: how many products, units on hand, stock value at selling price, counts per status
    (ok, low, out, dead, overstock) and the same per category. Use it for "all products" or "full stock" questions,
    then offer to list one status or category with find_products."""
    sid = _sid(tool_context)
    rows = insights.inventory(sid)
    by_status: dict[str, int] = {}
    by_cat: dict[str, dict] = {}
    units = value = 0.0
    for r in rows:
        by_status[r["status"]] = by_status.get(r["status"], 0) + 1
        c = by_cat.setdefault(r.get("category") or "Uncategorised", {"category": r.get("category") or "Uncategorised", "products": 0, "units": 0, "value": 0.0, "out": 0, "low": 0})
        c["products"] += 1
        c["units"] += r["on_hand"]
        c["value"] = round(c["value"] + r["on_hand"] * (r.get("price") or 0), 2)
        c["out"] += r["status"] == "out"
        c["low"] += r["status"] == "low"
        units += r["on_hand"]
        value += r["on_hand"] * (r.get("price") or 0)
    cats = sorted(by_cat.values(), key=lambda c: -c["value"])
    return {"products": len(rows), "units_on_hand": int(units), "stock_value": round(value, 2), "by_status": by_status,
            **_rows(["category", "products", "units", "value", "out", "low"], cats)}


def find_products(query: str, tool_context: ToolContext, status: str = "", limit: int = 15) -> dict:
    """Inventory rows matching a name fragment and/or a status: ok, low, out, dead (not selling) or overstock.
    Each row has stock, sales per day, days of cover, reorder rule, aisle and price. Empty query with a status lists that status."""
    sid = _sid(tool_context)
    q = query.strip().lower()
    rows = [r for r in insights.inventory(sid) if (not q or q in r["name"].lower()) and (not status or r["status"] == status)]
    rows.sort(key=lambda r: (r["status"] != "out", r["status"] != "low", r["name"]))
    cols = ["name", "status", "available", "avg_daily", "days_of_cover", "reorder_point", "reorder_qty", "aisle", "price"]
    return _rows(cols, [{c: r.get(c) for c in cols} | {"product_id": r["product_id"]} for r in rows[:max(1, min(limit, 50))]])


def sales_report(tool_context: ToolContext, days: int = 7) -> dict:
    """Revenue per day and per channel for the last days, plus the best-selling products by units."""
    sid = _sid(tool_context)
    days = max(1, min(days, 90))
    start = (datetime.now(IST) - timedelta(days=days - 1)).replace(hour=0, minute=0, second=0, microsecond=0)
    by_channel: dict[str, float] = {}
    units: dict[str, int] = {}
    names: dict[str, str] = {}
    orders = 0
    for d in db.orders().where(filter=FieldFilter("store_id", "==", sid)).where(filter=FieldFilter("created_at", ">=", start)).stream():
        o = d.to_dict()
        if o.get("status") not in ("paid", "verified", "flagged"):
            continue
        orders += 1
        by_channel[o["channel"]] = round(by_channel.get(o["channel"], 0) + o["total"], 2)
        for i in o["items"]:
            units[i["product_id"]] = units.get(i["product_id"], 0) + i["qty"]
            names[i["product_id"]] = i["name"]
    series = insights.daily_revenue_history(sid, days - 1) + [{"day": datetime.now(IST).date().isoformat(), "revenue": insights.overview(sid)["today"]["revenue"]}]
    top = sorted(units.items(), key=lambda kv: -kv[1])[:10]
    return {"days": days, "orders": orders, "revenue": round(sum(by_channel.values()), 2), "by_channel": by_channel, "daily": series,
            **_rows(["name", "units"], [{"name": names[pid], "units": n, "product_id": pid} for pid, n in top])}


def reorder_drafts(tool_context: ToolContext) -> dict:
    """Purchase-order drafts and their status, newest first, with supplier, lines and the rationale."""
    drafts = reorder.list_drafts(_sid(tool_context))
    return _rows(["po_id", "supplier", "status", "lines", "summary"],
                 [{"po_id": d.po_id, "supplier": d.supplier_name, "status": d.status, "lines": len(d.lines), "summary": d.summary[:160],
                   "items": [f"{l['name']} x{l['qty']}" for l in d.lines]} for d in drafts[:20]])


def demand_signals(tool_context: ToolContext, days: int = 7) -> dict:
    """What shoppers asked for that the store does not carry, and what they asked for while it was out of stock, with counts."""
    s = insights.signals(_sid(tool_context), max(1, min(days, 90)))
    return {"days": days, **_rows(["query", "count", "kind"],
                                  [{"query": r["query"], "count": r["count"], "kind": "not carried"} for r in s["not_carried"][:15]]
                                  + [{"query": r["name"], "count": r["count"], "kind": "out of stock", "lost_sales": r.get("lost_sales")} for r in s["out_of_stock"][:15]])}


def customers_overview(tool_context: ToolContext, segment: str = "", limit: int = 10) -> dict:
    """Signed-in customers: counts per segment (new, regular, vip, at_risk) and the top spenders, optionally one segment.
    Customers are identified by name and the last four digits of their number; never by full number."""
    sid = _sid(tool_context)
    rows = [d.to_dict() for d in db.customers(sid).stream()]
    counts: dict[str, int] = {}
    for r in rows:
        counts[r.get("segment", "new")] = counts.get(r.get("segment", "new"), 0) + 1
    picked = [r for r in rows if not segment or r.get("segment") == segment]
    picked.sort(key=lambda r: -(r.get("spend") or 0))
    return {"segments": counts, "total": len(rows), **_rows(["name", "last4", "segment", "visits", "spend", "points"],
            [{"name": r.get("name") or "Shopper", "last4": r.get("phone_last4"), "segment": r.get("segment"), "visits": r.get("visits"),
              "spend": r.get("spend"), "points": r.get("points"), "uid": r.get("uid")} for r in picked[:max(1, min(limit, 50))]])}


def list_offers(tool_context: ToolContext) -> dict:
    """Every offer with its rule, audience and whether it is live."""
    sid = _sid(tool_context)
    return _rows(["name", "detail", "segment", "active", "ends_at"],
                 [{"name": o.name, "detail": offers_svc.describe(sid, o), "segment": o.segment, "active": o.active,
                   "ends_at": o.ends_at.date().isoformat() if o.ends_at else None, "offer_id": o.offer_id} for o in offers_svc.list_all(sid)])


def exit_summary(tool_context: ToolContext, days: int = 7) -> dict:
    """Exit checks for the last days (clear, spot checks, flags, confirmed issues) and shrink candidates from shelf counts."""
    sid = _sid(tool_context)
    return {"exits": verification.summary(sid, max(1, min(days, 90))), **_rows(["name", "system", "counted", "difference", "value"], insights.shrink(sid)[:10])}


def sync_status(tool_context: ToolContext) -> dict:
    """Live sync with the billing system: webhook and feed settings, last pull, pending and failed deliveries, recent log."""
    sid = _sid(tool_context)
    cfg = sync_svc._settings(sid)
    log = [d.to_dict() for d in db.sync_log(sid).order_by("at", direction="DESCENDING").limit(10).stream()]
    outbox = [d.to_dict() for d in db.sync_outbox(sid).stream()]
    return {"webhook_url": bool(cfg.webhook_url), "feed_url": bool(cfg.feed_url), "feed_every_min": cfg.feed_every_min,
            "last_pull_at": cfg.last_pull_at.isoformat() if cfg.last_pull_at else None, "has_secret": cfg.has_secret,
            "outbox_pending": sum(1 for e in outbox if not e.get("dead")), "outbox_dead": sum(1 for e in outbox if e.get("dead")),
            **_rows(["at", "direction", "kind", "rows", "changed", "ok", "error"],
                    [{c: (e.get(c).isoformat() if c == "at" and e.get("at") else e.get(c)) for c in ("at", "direction", "kind", "rows", "changed", "ok", "error")} for e in log])}


def floor_map_summary(tool_context: ToolContext) -> dict:
    """The aisles on the floor map and how many products sit in each; products without a place are counted too."""
    sid = _sid(tool_context)
    aisles = [a["aisle"] for a in (db.store_ref(sid).get().to_dict() or {}).get("floor_map", [])]
    counts = {a: 0 for a in aisles}
    unplaced = 0
    for d in db.locations(sid).stream():
        a = d.to_dict().get("aisle")
        if a in counts:
            counts[a] += 1
    placed = sum(counts.values())
    unplaced = len(list(db.products(sid).select([]).stream())) - placed
    return {"aisles": aisles, **_rows(["aisle", "products"], [{"aisle": a, "products": n} for a, n in counts.items()]), "unplaced": max(0, unplaced)}


# --- acting --------------------------------------------------------------------------------------------------------

def set_reorder_rule(product: str, tool_context: ToolContext, reorder_point: int = -1, reorder_qty: int = -1, confirm: bool = False) -> dict:
    """Change when a product is reordered (reorder_point) and how much (reorder_qty). Pass -1 to leave one unchanged.
    Without confirm it only describes the change; call again with confirm=true after the owner agrees."""
    sid = _sid(tool_context)
    v = _find(sid, product)
    if not v:
        return {"ok": False, "error": "unknown_product"}
    changes = {k: n for k, n in (("reorder_point", reorder_point), ("reorder_qty", reorder_qty)) if n >= 0}
    if not changes:
        return {"ok": False, "error": "nothing_to_change"}
    if not confirm:
        return _plan(f"Set {v.name}: " + ", ".join(f"{k.replace('_', ' ')} {n}" for k, n in changes.items()), product=v.product_id, **changes)
    db.inventory(sid).document(v.product_id).update(changes)
    _audit(sid, _actor(tool_context), "reorder_rule", {"product_id": v.product_id, **changes})
    return {"ok": True, "name": v.name, **changes}


def adjust_stock(product: str, on_hand: int, reason: str, tool_context: ToolContext, confirm: bool = False) -> dict:
    """Set a product's stock on hand after a delivery, a correction or damage. Reservations are kept. Needs confirm."""
    sid = _sid(tool_context)
    v = _find(sid, product)
    if not v:
        return {"ok": False, "error": "unknown_product"}
    if on_hand < 0 or not reason.strip():
        return {"ok": False, "error": "need_non_negative_stock_and_a_reason"}
    doc = db.inventory(sid).document(v.product_id).get().to_dict() or {}
    if not confirm:
        return _plan(f"Set {v.name} stock from {doc.get('on_hand', 0)} to {on_hand} ({reason.strip()})", product=v.product_id, on_hand=on_hand, reason=reason)
    db.inventory(sid).document(v.product_id).update({"on_hand": int(on_hand)})
    _audit(sid, _actor(tool_context), "stock_adjusted", {"product_id": v.product_id, "from": doc.get("on_hand", 0), "to": int(on_hand), "reason": reason.strip()[:120]})
    return {"ok": True, "name": v.name, "on_hand": int(on_hand), "was": doc.get("on_hand", 0)}


def record_shelf_count(product: str, counted: int, tool_context: ToolContext) -> dict:
    """Record a physical shelf count. Differences against system stock show up as shrink candidates; stock itself is not changed."""
    sid = _sid(tool_context)
    v = _find(sid, product)
    if not v or counted < 0:
        return {"ok": False, "error": "unknown_product_or_bad_count"}
    insights.record_count(sid, v.product_id, counted=int(counted), by=_actor(tool_context))
    return {"ok": True, "name": v.name, "counted": int(counted), "system": v.available}


def update_price(product: str, price: float, tool_context: ToolContext, mrp: float = 0.0, confirm: bool = False) -> dict:
    """Change a product's selling price (and MRP when given). Needs confirm; the shopper app updates within two seconds."""
    sid = _sid(tool_context)
    v = _find(sid, product)
    if not v:
        return {"ok": False, "error": "unknown_product"}
    if price <= 0 or price > 10_000_000:
        return {"ok": False, "error": "bad_price"}
    new_mrp = mrp if mrp > 0 else max(v.mrp, price)
    if not confirm:
        return _plan(f"Change {v.name} from ₹{v.price:g} to ₹{price:g}" + (f" (MRP ₹{new_mrp:g})" if mrp > 0 else ""), product=v.product_id, price=price, mrp=new_mrp)
    db.products(sid).document(v.product_id).update({"price": float(price), "mrp": float(new_mrp)})
    catalog.bump(sid)
    _audit(sid, _actor(tool_context), "price_changed", {"product_id": v.product_id, "from": v.price, "to": float(price), "mrp": float(new_mrp)})
    return {"ok": True, "name": v.name, "price": float(price), "mrp": float(new_mrp), "was": v.price}


def move_product(product: str, aisle: str, tool_context: ToolContext, bay: int = 1, side: str = "left", confirm: bool = False) -> dict:
    """Place a product on an aisle of the floor map (bay 1 upwards, side left or right). Needs confirm."""
    sid = _sid(tool_context)
    v = _find(sid, product)
    if not v:
        return {"ok": False, "error": "unknown_product"}
    aisles = [a["aisle"] for a in (db.store_ref(sid).get().to_dict() or {}).get("floor_map", [])]
    match = next((a for a in aisles if a.lower() == aisle.strip().lower()), None)
    if not match:
        return {"ok": False, "error": "aisle_not_on_map", "aisles": aisles}
    side = "right" if side.lower().startswith("r") else "left"
    bay = max(1, min(int(bay), 12))
    if not confirm:
        return _plan(f"Move {v.name} to aisle {match}, bay {bay}, {side} side", product=v.product_id, aisle=match, bay=bay, side=side)
    db.locations(sid).document(v.product_id).set(Location(product_id=v.product_id, store_id=sid, aisle=match, bay=bay, side=side).model_dump())
    catalog.bump(sid)
    _audit(sid, _actor(tool_context), "product_moved", {"product_id": v.product_id, "aisle": match, "bay": bay})
    return {"ok": True, "name": v.name, "aisle": match, "bay": bay, "side": side}


def create_offer(name: str, kind: str, tool_context: ToolContext, percent_off: float = 0.0, amount_off: float = 0.0, product: str = "",
                 category: str = "", min_total: float = 0.0, segment: str = "all", ends_in_days: int = 0, confirm: bool = False) -> dict:
    """Create an offer that applies itself in the cart. kind: product (needs product), category (needs category) or cart
    (bill above min_total). One of percent_off (1 to 90) or amount_off (rupees; per unit for product and category offers).
    segment: all, signed_in, new, regular, vip or at_risk. Needs confirm."""
    sid = _sid(tool_context)
    product_id = ""
    if kind == "product":
        v = _find(sid, product)
        if not v:
            return {"ok": False, "error": "unknown_product"}
        product_id, product = v.product_id, v.name
    try:
        o = Offer(offer_id="", store_id=sid, name=name.strip()[:60] or "Offer", kind=kind, product_id=product_id, category=category.strip(),
                  min_total=min_total, percent_off=percent_off, amount_off=amount_off, segment=segment, created_by=_actor(tool_context),
                  ends_at=now() + timedelta(days=int(ends_in_days)) if ends_in_days > 0 else None)
    except ValueError as exc:
        return {"ok": False, "error": str(exc)[:160]}
    detail = offers_svc.describe(sid, o.model_copy(update={"product_id": product_id}))
    if not confirm:
        return _plan(f"Create offer “{o.name}”: {detail}, for {segment.replace('_', ' ')}" + (f", ending in {ends_in_days} days" if ends_in_days > 0 else ""),
                     name=o.name, kind=kind, percent_off=percent_off, amount_off=amount_off, product=product, category=category, min_total=min_total, segment=segment, ends_in_days=ends_in_days)
    saved = offers_svc.create(sid, o)
    _audit(sid, _actor(tool_context), "offer_created", {"offer_id": saved.offer_id, "name": saved.name, "kind": kind, "by": "agent"})
    return {"ok": True, "name": saved.name, "detail": detail, "segment": segment}


def set_offer_active(name: str, active: bool, tool_context: ToolContext, confirm: bool = False) -> dict:
    """Pause (active=false) or resume (active=true) an offer by name. Needs confirm."""
    sid = _sid(tool_context)
    o = next((x for x in offers_svc.list_all(sid) if x.name.lower() == name.strip().lower()), None)
    if not o:
        return {"ok": False, "error": "unknown_offer"}
    if not confirm:
        return _plan(f"{'Resume' if active else 'Pause'} the offer “{o.name}”", name=o.name, active=active)
    offers_svc.update(sid, o.offer_id, {"active": active})
    _audit(sid, _actor(tool_context), "offer_changed", {"offer_id": o.offer_id, "fields": ["active"], "by": "agent"})
    return {"ok": True, "name": o.name, "active": active}


def adjust_points(customer: str, delta: int, reason: str, tool_context: ToolContext, confirm: bool = False) -> dict:
    """Give or take reward points for a signed-in customer, found by name or by the last four digits of their number. Needs confirm."""
    sid = _sid(tool_context)
    key = customer.strip().lower()
    rows = [d.to_dict() for d in db.customers(sid).stream()]
    found = [r for r in rows if key and (key == (r.get("phone_last4") or "") or key in (r.get("name") or "").lower())]
    if len(found) != 1:
        return {"ok": False, "error": "no_single_match", "matches": [{"name": r.get("name") or "Shopper", "last4": r.get("phone_last4")} for r in found[:5]]}
    r = found[0]
    label = f"{r.get('name') or 'Shopper'} (····{r.get('phone_last4')})"
    if not confirm:
        return _plan(f"{'Add' if delta > 0 else 'Remove'} {abs(delta)} points for {label} ({reason.strip()})", customer=customer, delta=delta, reason=reason)
    try:
        balance = points_svc.adjust(sid, r["uid"], int(delta), reason, by=_actor(tool_context))
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}
    _audit(sid, _actor(tool_context), "points_adjusted", {"customer": r["uid"], "delta": int(delta), "reason": reason.strip()[:120], "by": "agent"})
    return {"ok": True, "customer": label, "points": balance}


def approve_purchase_order(po_id: str, tool_context: ToolContext, confirm: bool = False) -> dict:
    """Approve a purchase-order draft so it can be sent to the supplier. Needs confirm; the owner should hear the lines first."""
    sid = _sid(tool_context)
    d = reorder.get(sid, po_id)
    if not d:
        return {"ok": False, "error": "unknown_draft"}
    if d.status != "draft":
        return {"ok": False, "error": f"already_{d.status}"}
    if not confirm:
        return _plan(f"Approve the order to {d.supplier_name}: " + ", ".join(f"{l['name']} x{l['qty']}" for l in d.lines[:6]) + (" and more" if len(d.lines) > 6 else ""), po_id=po_id)
    approved = reorder.approve(sid, po_id, by=_actor(tool_context))
    return {"ok": True, "po_id": approved.po_id, "supplier": approved.supplier_name, "status": approved.status, "lines": len(approved.lines)}
