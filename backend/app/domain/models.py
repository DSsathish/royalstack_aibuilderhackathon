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


class Brand(BaseModel):
    accent: str = "#27a36e"
    tagline: str = ""
    greeting: str = ""


class Payments(BaseModel):
    provider: Literal["mock", "razorpay"] = "mock"
    key_id: str = ""              # public key id; the secret lives in Secret Manager as razorpay-{store_id}


class Store(BaseModel):
    store_id: str
    name: str
    city: str = ""
    brand: Brand = Brand()
    payments: Payments = Payments()
    staff_emails: list[str] = []
    created_at: datetime = Field(default_factory=now)
    currency: str = "INR"
    languages: list[str] = ["en", "ta", "hi"]
    self_checkout_item_limit: int = 15
    high_value_threshold: float = 500.0
    audit_rate: float = 0.10      # share of clear exits sent to a random spot check
    kiosk_pin: str = "1234"       # exit kiosk access; owner rotates it
    owner_emails: list[str] = []  # Google accounts allowed into the owner dashboard
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
    type: Literal["not_carried", "out_of_stock"]
    source: Literal["search", "agent"] = "search"  # search = automatic heuristic, agent = model judgment
    created_at: datetime = Field(default_factory=now)


Mode = Literal["instore", "online", "owner"]


class Session(BaseModel):
    session_id: str
    store_id: str
    mode: Mode
    cart_id: str
    user_id: str | None = None
    customer_id: str | None = None     # signed-in shopper (phone uid); None for guests
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


class Order(BaseModel):
    order_id: str
    store_id: str
    session_id: str
    cart_id: str
    channel: Literal["store", "online", "whatsapp"]
    items: list[CartItem]
    subtotal: float
    savings: float
    total: float
    status: Literal["pending", "paid", "verified", "flagged"] = "pending"
    payment_provider: Literal["mock", "razorpay"] = "mock"
    payment_ref: str = ""   # provider order id
    payment_id: str = ""    # provider payment id
    receipt_token: str = ""
    customer_id: str | None = None
    created_at: datetime = Field(default_factory=now)
    paid_at: datetime | None = None
    exited_at: datetime | None = None


class Layers(BaseModel):
    receipt_ok: bool = False
    order_ok: bool = False
    count_ok: bool | None = None     # None when no count was supplied
    limit_ok: bool = True
    high_value: list[str] = []       # product ids that need a spot check
    random_audit: bool = False


class VisionResult(BaseModel):
    confidence: float = 1.0
    visible_items: list[str] = []
    unexpected_items: list[str] = []
    notes: str = ""
    skipped: bool = False


class Verification(BaseModel):
    verification_id: str
    store_id: str
    order_id: str = ""
    kiosk_id: str = ""
    layers: Layers = Layers()
    verdict: Literal["clear", "spot_check", "flag"]
    reasons: list[str] = []
    vision: VisionResult | None = None
    image_hash: str = ""
    reviewed_by: str = ""
    review_note: str = ""
    review_outcome: Literal["cleared", "issue_confirmed"] | None = None
    created_at: datetime = Field(default_factory=now)


class PurchaseOrderDraft(BaseModel):
    po_id: str
    store_id: str
    supplier_id: str
    supplier_name: str
    lines: list[dict]            # {product_id, name, qty, available, reorder_point, avg_daily, reason}
    summary: str = ""
    status: Literal["draft", "approved", "rejected"] = "draft"
    email_text: str = ""
    reason: str = ""             # rejection reason
    created_by: str = "agent"
    decided_by: str = ""
    decided_at: datetime | None = None
    created_at: datetime = Field(default_factory=now)


class Customer(BaseModel):
    uid: str
    store_id: str
    phone_last4: str = ""
    name: str = ""
    language: str = "auto"
    dietary: list[str] = []
    favourite_categories: list[str] = []
    usual_items: list[str] = []
    substitution: Literal["ask", "same_brand", "any"] = "ask"
    consent_at: datetime = Field(default_factory=now)
    created_at: datetime = Field(default_factory=now)
    last_seen: datetime = Field(default_factory=now)
    visits: int = 0
    spend: float = 0.0
    points: int = 0
