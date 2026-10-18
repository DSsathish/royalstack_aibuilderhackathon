"""Owner: barcode lookup and single-product create or update (add-by-scan)."""

import uuid

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Path
from pydantic import BaseModel, Field

from app.connectors import csv_connector as csvc
from app.domain.models import Location, now
from app.domain import classify
from app.services import barcode, catalog, db
from app.services.auth import STORE_ID, current_uid, require_owner, require_staff

router = APIRouter(tags=["products"])


@router.get("/owner/{store_id}/lookup/{code}")
def lookup(store_id: str = STORE_ID, code: str = Path(pattern=r"^[0-9]{8,14}$"), uid: str = Depends(current_uid)):
    require_owner(store_id, uid)
    return barcode.lookup(code)


class ProductIn(BaseModel):
    """One product by hand or by scan: a barcode, a SKU, or both (one is required)."""
    barcode: str = Field(default="", pattern=r"^$|^[0-9]{8,14}$")
    sku: str | None = Field(default=None, max_length=40)
    name: str = Field(min_length=1, max_length=120)
    brand: str = Field(default="", max_length=60)
    category: str = Field(default="", max_length=60)
    subcategory: str = Field(default="", max_length=60)
    price: float = Field(ge=0, le=10_000_000)
    mrp: float | None = Field(default=None, ge=0, le=10_000_000)
    unit: str = Field(default="pc", max_length=16)
    pack_size: str = Field(default="", max_length=20)
    on_hand: int = Field(ge=0, le=1_000_000)
    reorder_point: int = Field(default=5, ge=0, le=1_000_000)
    reorder_qty: int = Field(default=20, ge=0, le=1_000_000)
    aisle: str | None = Field(default=None, max_length=16)


class ProductPatch(BaseModel):
    """Every editable field of a product, its stock record and its shelf spot; only the fields sent change. The SKU
    stays: it forms the product id that carts, orders and forecasts point at. Design: docs/lld/owner-product-edit.md."""
    name: str | None = Field(default=None, min_length=1, max_length=120)
    brand: str | None = Field(default=None, max_length=60)
    category: str | None = Field(default=None, max_length=60)
    subcategory: str | None = Field(default=None, max_length=60)
    description: str | None = Field(default=None, max_length=600)
    barcode: str | None = Field(default=None, pattern=r"^$|^[0-9]{8,14}$")
    price: float | None = Field(default=None, ge=0, le=10_000_000)
    mrp: float | None = Field(default=None, ge=0, le=10_000_000)
    cost_price: float | None = Field(default=None, ge=0, le=10_000_000)
    gst_rate: float | None = Field(default=None, ge=0, le=100)
    unit: str | None = Field(default=None, min_length=1, max_length=16)
    pack_size: str | None = Field(default=None, max_length=20)
    shelf_life_days: int | None = Field(default=None, ge=0, le=10_000)
    status: Literal["active", "inactive", "discontinued", "seasonal"] | None = None
    origin: str | None = Field(default=None, max_length=60)
    tags: list[str] | None = Field(default=None, max_length=20)
    image_url: str | None = Field(default=None, max_length=300)
    on_hand: int | None = Field(default=None, ge=0, le=1_000_000)
    reorder_point: int | None = Field(default=None, ge=0, le=1_000_000)
    reorder_qty: int | None = Field(default=None, ge=0, le=1_000_000)
    lead_time_days: int | None = Field(default=None, ge=0, le=365)
    supplier_id: str | None = Field(default=None, max_length=40)
    aisle: str | None = Field(default=None, max_length=16)
    bay: int | None = Field(default=None, ge=1, le=12)
    shelf: int | None = Field(default=None, ge=1, le=8)
    side: Literal["left", "right"] | None = None


STOCK_FIELDS = {"on_hand", "reorder_point", "reorder_qty", "lead_time_days", "supplier_id"}
SPOT_FIELDS = {"aisle", "bay", "shelf", "side"}


def _detail(store_id: str, product_id: str) -> dict:
    view = catalog.get_product(store_id, product_id)
    if not view:
        raise HTTPException(404, "product not found")
    stock = db.inventory(store_id).document(product_id).get()
    return {"product": view.model_dump(exclude={"embedding"}), "stock": stock.to_dict() if stock.exists else {}}


@router.get("/owner/{store_id}/products/{product_id}")
def product_detail(store_id: str = STORE_ID, product_id: str = Path(pattern=r"^[a-z0-9-]{3,80}$"), uid: str = Depends(current_uid)):
    require_staff(store_id, uid)
    return _detail(store_id, product_id)


@router.patch("/owner/{store_id}/products/{product_id}")
def edit_product(body: ProductPatch, store_id: str = STORE_ID, product_id: str = Path(pattern=r"^[a-z0-9-]{3,80}$"), uid: str = Depends(current_uid)):
    require_owner(store_id, uid)
    fields = {k: (v.strip() if isinstance(v, str) else v) for k, v in body.model_dump().items() if v is not None}
    if not fields:
        raise HTTPException(422, "nothing to change")
    store = db.store_ref(store_id).get()
    pref = db.products(store_id).document(product_id)
    current = pref.get()
    if not store.exists or not current.exists:
        raise HTTPException(404, "store or product not found")
    product = {k: v for k, v in fields.items() if k not in STOCK_FIELDS and k not in SPOT_FIELDS}
    if "tags" in product:
        product["tags"] = [t.strip() for t in product["tags"] if t.strip()][:20]
    price = product.get("price", current.to_dict().get("price", 0))
    mrp = product.get("mrp", current.to_dict().get("mrp", 0))
    if mrp and mrp < price:
        raise HTTPException(422, "MRP is below the selling price")
    if "price" in product:
        product["is_high_value"] = price >= store.to_dict().get("high_value_threshold", 500)
    if product:
        pref.update(product)
    stock = {k: v for k, v in fields.items() if k in STOCK_FIELDS}
    if stock:
        db.inventory(store_id).document(product_id).set({"product_id": product_id, "store_id": store_id, **stock}, merge=True)
    spot = {k: v for k, v in fields.items() if k in SPOT_FIELDS}
    if spot:
        here = db.locations(store_id).document(product_id).get()
        cur = here.to_dict() if here.exists else {}
        aisle = spot.get("aisle") or cur.get("aisle", "")
        if not aisle:
            raise HTTPException(422, "pick an aisle first")
        if aisle not in {a["aisle"] for a in store.to_dict().get("floor_map", [])}:
            raise HTTPException(422, "that aisle is not on the floor map")
        loc = Location(product_id=product_id, store_id=store_id, aisle=aisle, bay=spot.get("bay", cur.get("bay", 1)),
                       shelf=spot.get("shelf", cur.get("shelf", 1)), side=spot.get("side", cur.get("side", "left")))
        db.locations(store_id).document(product_id).set(loc.model_dump())
    catalog.bump(store_id)
    db.audit(store_id).document(uuid.uuid4().hex).set({"actor": uid, "action": "product_edited", "created_at": now(),
                                                       "payload": {"product_id": product_id, "fields": sorted(fields)}})
    return _detail(store_id, product_id)


class LocationIn(BaseModel):
    aisle: str = Field(min_length=1, max_length=16)
    bay: int = Field(default=1, ge=1, le=12)
    shelf: int = Field(default=1, ge=1, le=8)
    side: Literal["left", "right"] = "left"


@router.patch("/owner/{store_id}/products/{product_id}/location")
def set_location(body: LocationIn, store_id: str = STORE_ID, product_id: str = Path(pattern=r"^[a-z0-9-]{3,80}$"), uid: str = Depends(current_uid)):
    """Move a product to an aisle on the owner's floor map; the shopper map and the assistant follow immediately."""
    require_owner(store_id, uid)
    store = db.store_ref(store_id).get()
    if not store.exists or not db.products(store_id).document(product_id).get().exists:
        raise HTTPException(404, "store or product not found")
    if body.aisle.strip() not in {a["aisle"] for a in store.to_dict().get("floor_map", [])}:
        raise HTTPException(422, "that aisle is not on the floor map")
    loc = Location(product_id=product_id, store_id=store_id, aisle=body.aisle.strip(), bay=body.bay, shelf=body.shelf, side=body.side)
    db.locations(store_id).document(product_id).set(loc.model_dump())
    catalog.bump(store_id)
    db.audit(store_id).document(uuid.uuid4().hex).set({"actor": uid, "action": "product_moved", "created_at": now(),
                                                       "payload": {"product_id": product_id, "aisle": loc.aisle, "bay": loc.bay}})
    return loc.model_dump()


@router.post("/owner/{store_id}/products")
def create_product(body: ProductIn, store_id: str = STORE_ID, uid: str = Depends(current_uid)):
    require_owner(store_id, uid)
    store = db.store_ref(store_id).get()
    if not store.exists:
        raise HTTPException(404, "store not found")
    sku = (body.sku or body.barcode or "").strip()
    if not sku:
        raise HTTPException(422, "a SKU or a barcode is required")
    aisle = (body.aisle or "").strip()
    if not aisle:                       # cold products default to the chiller or freezer block when the map has one
        aisle = classify.block_for(store.to_dict().get("floor_map", []), classify.storage_of(body.name, body.category)) or ""
    row = csvc.Row(line=0, sku=sku, name=body.name.strip(), price=body.price, on_hand=body.on_hand,
                   barcode=body.barcode, brand=body.brand.strip(), category=body.category.strip(), subcategory=body.subcategory.strip(),
                   mrp=body.mrp or body.price, unit=body.unit.strip() or "pc", pack_size=body.pack_size.strip(),
                   reorder_point=body.reorder_point, reorder_qty=body.reorder_qty, aisle=aisle)
    csvc.upsert(store_id, [row], high_value_threshold=store.to_dict().get("high_value_threshold", 500))
    catalog.bump(store_id)
    db.audit(store_id).document(uuid.uuid4().hex).set({"actor": uid, "action": "product_saved", "created_at": now(),
                                                       "payload": {"barcode": body.barcode, "sku": sku, "name": body.name}})
    view = catalog.get_product(store_id, f"{store_id}-{csvc.slug(row.sku)}")
    return view.model_dump(exclude={"embedding"}) if view else {"product_id": f"{store_id}-{csvc.slug(row.sku)}"}
