"""Canonical commerce models stored in Firestore. See docs/lld/phase-1-data.md."""

import re
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def now() -> datetime:
    return datetime.now(timezone.utc)


class Aisle(BaseModel):
    aisle: str
    x: float
    y: float
    w: float
    h: float


class Store(BaseModel):
    store_id: str
    name: str
    currency: str = "INR"
    languages: list[str] = ["en", "ta", "hi"]
    self_checkout_item_limit: int = 15
    high_value_threshold: float = 500.0
    floor_map: list[Aisle] = []


class Product(BaseModel):
    product_id: str
    store_id: str
    sku: str
    barcode: str = ""
    name: str
    brand: str = ""
    category: str = ""
    subcategory: str = ""
    description: str = ""
    price: float
    mrp: float = 0
    unit: str = "pc"
    image_url: str = ""
    tags: list[str] = []
    substitutes: list[str] = []
    is_high_value: bool = False
    embedding: list[float] = []

    @classmethod
    def from_row(cls, *, store_id: str, sku: str, name: str, price: float, threshold: float, **extra) -> "Product":
        return cls(
            product_id=f"{store_id}-{slug(sku)}",
            store_id=store_id,
            sku=sku,
            name=name,
            price=price,
            is_high_value=price >= threshold,
            **extra,
        )


class Location(BaseModel):
    product_id: str
    store_id: str
    aisle: str
    bay: int = 1
    shelf: int = 1
    side: Literal["left", "right"] = "left"
    x: float = 0
    y: float = 0


class Inventory(BaseModel):
    product_id: str
    store_id: str
    on_hand: int = 0
    reserved: int = 0
    reorder_point: int = 5
    reorder_qty: int = 20
    lead_time_days: int = 3
    supplier_id: str = ""

    @property
    def available(self) -> int:
        return max(0, self.on_hand - self.reserved)


class Supplier(BaseModel):
    supplier_id: str
    store_id: str
    name: str
    email: str = ""
    lead_time_days: int = 3


class DemandSignal(BaseModel):
    signal_id: str
    store_id: str
    query_text: str
    matched_product_id: str | None = None
    type: Literal["not_carried", "out_of_stock", "found"]
    created_at: datetime = Field(default_factory=now)


Mode = Literal["instore", "online", "owner"]


class Session(BaseModel):
    session_id: str
    store_id: str
    mode: Mode
    cart_id: str
    user_id: str | None = None
    language: str = "auto"
    aisle_hint: str | None = None
    created_at: datetime = Field(default_factory=now)
    expires_at: datetime


class CartItem(BaseModel):
    product_id: str
    name: str
    qty: int
    unit_price: float
    mrp: float
    via: Literal["scan", "vision", "chat"] = "chat"


class Cart(BaseModel):
    cart_id: str
    store_id: str
    items: list[CartItem] = []
    status: Literal["open", "checked_out"] = "open"
