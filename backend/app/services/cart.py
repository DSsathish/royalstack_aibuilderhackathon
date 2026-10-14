"""Cart lines and totals. Reserves stock on add, releases on remove."""

from app.domain.models import Cart, CartItem, Mode
from app.services import catalog, db, inventory


def get(store_id: str, cart_id: str) -> Cart:
    doc = db.carts().document(cart_id).get()
    if doc.exists:
        return Cart(**doc.to_dict())
    c = Cart(cart_id=cart_id, store_id=store_id)
    db.carts().document(cart_id).set(c.model_dump())
    return c


def _save(c: Cart) -> Cart:
    db.carts().document(c.cart_id).set(c.model_dump())
    return c


def add(store_id: str, cart_id: str, product_id: str, qty: int, *, via: str, mode: Mode = "online") -> Cart | str:
    if qty <= 0:
        return "bad_qty"
    view = catalog.get_product(store_id, product_id)
    if not view:
        return "unknown_product"
    c = get(store_id, cart_id)
    line = next((i for i in c.items if i.product_id == product_id), None)
    if mode == "instore" and line is None:
        limit = db.store_ref(store_id).get().to_dict().get("self_checkout_item_limit", 15)
        if len(c.items) >= limit:
            return "item_limit"
    if not inventory.reserve(store_id, product_id, qty):
        return "out_of_stock"
    if line:
        line.qty += qty
    else:
        c.items.append(CartItem(product_id=product_id, name=view.name, qty=qty,
                                unit_price=view.price, mrp=view.mrp or view.price, via=via))
    return _save(c)


def remove(store_id: str, cart_id: str, product_id: str) -> Cart:
    c = get(store_id, cart_id)
    line = next((i for i in c.items if i.product_id == product_id), None)
    if line:
        inventory.release(store_id, product_id, line.qty)
        c.items.remove(line)
    return _save(c)


def totals(c: Cart) -> tuple[float, float, float]:
    """(subtotal, savings vs MRP, total). Total equals subtotal until discounts exist."""
    subtotal = round(sum(i.unit_price * i.qty for i in c.items), 2)
    savings = round(sum((i.mrp - i.unit_price) * i.qty for i in c.items), 2)
    return subtotal, savings, subtotal
