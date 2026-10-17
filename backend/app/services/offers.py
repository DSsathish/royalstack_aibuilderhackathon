"""Owner-created offers that apply themselves: the best single offer per line, then the best single cart offer."""

import uuid

from google.cloud import firestore

from app.domain.models import Cart, DiscountLine, Offer, now
from app.services import catalog, db


def create(store_id: str, o: Offer) -> Offer:
    o = o.model_copy(update={"offer_id": uuid.uuid4().hex, "store_id": store_id})
    db.offers(store_id).document(o.offer_id).set(o.model_dump())
    return o


def get(store_id: str, offer_id: str) -> Offer | None:
    doc = db.offers(store_id).document(offer_id).get()
    return Offer(**doc.to_dict()) if doc.exists else None


def update(store_id: str, offer_id: str, fields: dict) -> Offer | None:
    """Apply a partial change; the whole offer is re-validated so bad combinations are refused."""
    cur = get(store_id, offer_id)
    if not cur:
        return None
    o = Offer(**{**cur.model_dump(), **fields})      # callers pass only the fields they set; None clears a date
    db.offers(store_id).document(offer_id).set(o.model_dump())
    return o


def delete(store_id: str, offer_id: str) -> bool:
    ref = db.offers(store_id).document(offer_id)
    if not ref.get().exists:
        return False
    ref.delete()
    return True


def list_all(store_id: str) -> list[Offer]:
    docs = db.offers(store_id).order_by("created_at", direction=firestore.Query.DESCENDING).stream()
    return [Offer(**d.to_dict()) for d in docs]


def applicable(store_id: str, segment: str) -> list[Offer]:
    """Active offers inside their date window that this shopper may use. Guests get store-wide offers only."""
    t = now()
    out = []
    for o in list_all(store_id):
        if not o.active or (o.starts_at and o.starts_at > t) or (o.ends_at and o.ends_at < t):
            continue
        if o.segment == "all" or (segment != "guest" and o.segment in ("signed_in", segment)):
            out.append(o)
    return out


def _off(o: Offer, amount: float, units: int = 1) -> float:
    """Discount one offer gives on `amount` (a line of `units` units, or the cart). Never more than the amount."""
    d = amount * o.percent_off / 100 if o.percent_off else o.amount_off * units
    return round(min(d, amount), 2)


def apply(store_id: str, cart: Cart, segment: str) -> tuple[list[DiscountLine], float]:
    active = applicable(store_id, segment)
    if not active or not cart.items:
        return [], 0.0
    products, _ = catalog.product_map(store_id)
    by_offer: dict[str, DiscountLine] = {}

    def take(o: Offer, amount: float) -> None:
        if amount <= 0:
            return
        line = by_offer.setdefault(o.offer_id, DiscountLine(offer_id=o.offer_id, name=o.name, amount=0.0))
        line.amount = round(line.amount + amount, 2)

    line_discounts = 0.0
    for i in cart.items:
        amount = i.unit_price * i.qty
        category = products[i.product_id].category if i.product_id in products else ""
        candidates = [(o, _off(o, amount, i.qty)) for o in active
                      if (o.kind == "product" and o.product_id == i.product_id)
                      or (o.kind == "category" and category and o.category.lower() == category.lower())]
        if candidates:
            best = max(candidates, key=lambda t: t[1])
            take(*best)
            line_discounts += best[1]
    after = round(sum(i.unit_price * i.qty for i in cart.items) - line_discounts, 2)
    cart_offers = [(o, _off(o, after)) for o in active if o.kind == "cart" and after >= o.min_total]
    if cart_offers:
        take(*max(cart_offers, key=lambda t: t[1]))
    lines = list(by_offer.values())
    return lines, round(sum(l.amount for l in lines), 2)


def describe(store_id: str, o: Offer) -> str:
    """One line a shopper understands: "10% off Milk", "₹8 off each on Dairy", "₹30 off above ₹350"."""
    value = f"{o.percent_off:g}% off" if o.percent_off else f"₹{o.amount_off:g} off"
    if o.kind == "product":
        products, _ = catalog.product_map(store_id)
        name = products[o.product_id].name if o.product_id in products else o.product_id
        return f"{value} {name}" if o.percent_off else f"{value} each on {name}"
    if o.kind == "category":
        return f"{value} {o.category}" if o.percent_off else f"{value} each on {o.category}"
    return f"{value} your bill" + (f" above ₹{o.min_total:g}" if o.min_total else "")


def public(store_id: str, o: Offer) -> dict:
    return {"offer_id": o.offer_id, "name": o.name, "kind": o.kind, "detail": describe(store_id, o),
            "segment": o.segment, "ends_at": o.ends_at}
