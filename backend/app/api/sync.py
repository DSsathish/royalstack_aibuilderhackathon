"""Inbound sync endpoints for the shop's own system: signed POSTs for stock and catalog, a bearer-protected pull."""

import hmac

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, Field, ValidationError

from app.services import sync
from app.services.auth import STORE_ID

router = APIRouter(prefix="/sync", tags=["sync"])
MAX_BODY = 1_000_000


class InvRow(BaseModel):
    sku: str = Field(min_length=1, max_length=64)
    on_hand: int = Field(ge=0, le=10_000_000)
    price: float | None = Field(default=None, ge=0, le=10_000_000)


class InventoryIn(BaseModel):
    event_id: str = Field(min_length=1, max_length=200)
    rows: list[InvRow] = Field(max_length=sync.MAX_ROWS)


class ProductsIn(BaseModel):
    event_id: str = Field(min_length=1, max_length=200)
    rows: list[dict] = Field(max_length=sync.MAX_ROWS)


async def _signed_body(request: Request, store_id: str) -> bytes:
    body = await request.body()
    if len(body) > MAX_BODY:
        raise HTTPException(413, "body larger than 1 MB")
    if not sync.verify(sync.secret_for(store_id), request.headers.get("x-sync-timestamp", ""), body, request.headers.get("x-sync-signature", "")):
        raise HTTPException(401, "bad or missing signature")
    return body


def _parse(model, body: bytes):
    try:
        return model.model_validate_json(body)
    except ValidationError as exc:
        raise HTTPException(422, str(exc)[:500])


@router.post("/{store_id}/inventory")
async def inventory_in(request: Request, store_id: str = STORE_ID):
    data = _parse(InventoryIn, await _signed_body(request, store_id))
    if sync.seen(store_id, data.event_id):
        return {"ok": True, "duplicate": True}
    out = sync.apply_inventory(store_id, [r.model_dump() for r in data.rows])
    sync.record(store_id, direction="in", kind="inventory", rows=len(data.rows), changed=out["updated"], unknown=out["unknown"],
                event_id=data.event_id, ok=True)
    return {"ok": True, "duplicate": False, **out}


@router.post("/{store_id}/products")
async def products_in(request: Request, store_id: str = STORE_ID):
    data = _parse(ProductsIn, await _signed_body(request, store_id))
    if sync.seen(store_id, data.event_id):
        return {"ok": True, "duplicate": True}
    result = sync.apply_products(store_id, data.rows)
    sync.record(store_id, direction="in", kind="products", rows=len(data.rows), changed=result.created + result.updated,
                errors=len(result.errors), event_id=data.event_id, ok=True)
    return {"ok": True, "duplicate": False, **result.model_dump()}


@router.get("/{store_id}/inventory")
def inventory_out(store_id: str = STORE_ID, authorization: str | None = Header(default=None)):
    secret = sync.secret_for(store_id)
    given = (authorization or "").removeprefix("Bearer ").strip()
    if not secret or not given or not hmac.compare_digest(secret, given):
        raise HTTPException(401, "bearer secret required")
    return sync.inventory_snapshot(store_id)
