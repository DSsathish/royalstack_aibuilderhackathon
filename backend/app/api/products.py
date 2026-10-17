"""Owner: barcode lookup and single-product create or update (add-by-scan)."""

import uuid

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Path
from pydantic import BaseModel, Field

from app.connectors import csv_connector as csvc
from app.domain.models import Location, now
from app.services import barcode, catalog, db
from app.services.auth import STORE_ID, current_uid, require_owner

router = APIRouter(tags=["products"])


@router.get("/owner/{store_id}/lookup/{code}")
def lookup(store_id: str = STORE_ID, code: str = Path(pattern=r"^[0-9]{8,14}$"), uid: str = Depends(current_uid)):
    require_owner(store_id, uid)
    return barcode.lookup(code)


class ProductIn(BaseModel):
    barcode: str = Field(pattern=r"^[0-9]{8,14}$")
    sku: str | None = Field(default=None, max_length=40)
    name: str = Field(min_length=1, max_length=120)
    brand: str = Field(default="", max_length=60)
    category: str = Field(default="", max_length=60)
    price: float = Field(ge=0, le=10_000_000)
    mrp: float | None = Field(default=None, ge=0, le=10_000_000)
    on_hand: int = Field(ge=0, le=1_000_000)
    aisle: str | None = Field(default=None, max_length=16)


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
    row = csvc.Row(line=0, sku=body.sku or body.barcode, name=body.name.strip(), price=body.price, on_hand=body.on_hand,
                   barcode=body.barcode, brand=body.brand.strip(), category=body.category.strip(), mrp=body.mrp or body.price,
                   aisle=(body.aisle or "").strip())
    csvc.upsert(store_id, [row], high_value_threshold=store.to_dict().get("high_value_threshold", 500))
    catalog.bump(store_id)
    db.audit(store_id).document(uuid.uuid4().hex).set({"actor": uid, "action": "product_saved", "created_at": now(),
                                                       "payload": {"barcode": body.barcode, "name": body.name}})
    view = catalog.get_product(store_id, f"{store_id}-{csvc.slug(row.sku)}")
    return view.model_dump(exclude={"embedding"}) if view else {"product_id": f"{store_id}-{csvc.slug(row.sku)}"}
