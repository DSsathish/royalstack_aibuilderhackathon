"""Public read-only catalog endpoints."""

from fastapi import APIRouter, HTTPException, Path, Query

from app.domain.models import Store
from app.services import catalog, db
from app.services.auth import STORE_ID

router = APIRouter(tags=["catalog"])
PUBLIC_EXCLUDE = {"embedding"}


@router.get("/stores/{store_id}", response_model=Store, response_model_exclude={"kiosk_pin", "audit_rate"})
def get_store(store_id: str = STORE_ID):
    doc = db.store_ref(store_id).get()
    if not doc.exists:
        raise HTTPException(404, "store not found")
    return doc.to_dict()


@router.get("/stores/{store_id}/products/by-barcode/{barcode}",
            response_model=catalog.ProductView, response_model_exclude=PUBLIC_EXCLUDE)
def get_by_barcode(store_id: str = STORE_ID, barcode: str = Path(pattern=r"^[0-9]{8,14}$")):
    view = catalog.get_by_barcode(store_id, barcode)
    if not view:
        raise HTTPException(404, "product not found")
    return view


@router.get("/stores/{store_id}/products/{product_id}",
            response_model=catalog.ProductView, response_model_exclude=PUBLIC_EXCLUDE)
def get_product(store_id: str = STORE_ID, product_id: str = Path(pattern=r"^[a-z0-9-]{3,80}$")):
    view = catalog.get_product(store_id, product_id)
    if not view:
        raise HTTPException(404, "product not found")
    return view


@router.get("/stores/{store_id}/search",
            response_model=list[catalog.ProductView], response_model_exclude=PUBLIC_EXCLUDE)
def search(store_id: str = STORE_ID, q: str = Query(min_length=1, max_length=200),
           k: int = Query(default=6, ge=1, le=20)):
    if not db.store_ref(store_id).get().exists:
        raise HTTPException(404, "store not found")
    return catalog.search(store_id, q, k=k)
