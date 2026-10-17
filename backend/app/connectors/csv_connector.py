"""CSV import: bytes + column mapping -> Product, Location, Inventory upserts."""

import csv
import io
import re
from decimal import Decimal, InvalidOperation

from pydantic import BaseModel

from app.domain.models import Inventory, Location, Product, slug
from app.services import db

MAX_BYTES = 5 * 1024 * 1024
MAX_ROWS = 10_000
BATCH = 400
REQUIRED = ("sku", "name", "price", "on_hand")
OPTIONAL = ("barcode", "brand", "category", "subcategory", "description", "mrp", "unit",
            "image_url", "tags", "substitutes", "aisle", "bay", "shelf", "side",
            "reorder_point", "reorder_qty", "lead_time_days", "supplier_id",
            "pack_size", "cost_price", "gst_rate", "shelf_life_days", "status", "origin")
HEADER_RE = re.compile(r"^[^\x00-\x1f]{1,64}$")   # any printable header text, e.g. "Rate (Rs)" or "M.R.P."


class ImportError_(ValueError):
    """Whole-file problem: bad mapping, too big, missing header."""


class Row(BaseModel):
    line: int
    sku: str
    name: str
    price: float
    on_hand: int
    barcode: str = ""
    brand: str = ""
    category: str = ""
    subcategory: str = ""
    description: str = ""
    mrp: float = 0
    unit: str = "pc"
    image_url: str = ""
    tags: list[str] = []
    substitutes: list[str] = []
    aisle: str = ""
    bay: int = 1
    shelf: int = 1
    side: str = "left"
    reorder_point: int = 5
    reorder_qty: int = 20
    lead_time_days: int = 3
    supplier_id: str = ""
    pack_size: str = ""
    cost_price: float | None = None
    gst_rate: float | None = None
    shelf_life_days: int | None = None
    status: str = "active"
    origin: str = ""


class RowError(BaseModel):
    line: int
    message: str


class ImportResult(BaseModel):
    created: int = 0
    updated: int = 0
    errors: list[RowError] = []


_NUM = re.compile(r"-?\d+(?:\.\d+)?")


def _num(value: str, *, integer: bool) -> float | int:
    """Tolerant of currency symbols, thousands separators and unit suffixes: '₹ 1,250.00' -> 1250, '12 pcs' -> 12."""
    text = value.strip().replace(",", "")
    if not text:
        return 0
    m = _NUM.search(text)
    if not m or not re.fullmatch(r"[^\d-]*" + re.escape(m.group()) + r"[^\d]*", text):
        raise ValueError(f"not a number: {value!r}")
    d = Decimal(m.group())
    if not d.is_finite() or d < 0:
        raise ValueError("negative")
    return int(d) if integer else float(d)


def parse(data: bytes, mapping: dict[str, str]) -> tuple[list[Row], list[RowError]]:
    if len(data) > MAX_BYTES:
        raise ImportError_(f"file larger than {MAX_BYTES} bytes")
    for field, header in mapping.items():
        if field not in REQUIRED + OPTIONAL or not HEADER_RE.match(header):
            raise ImportError_(f"bad mapping entry {field!r} -> {header!r}")
    missing = [f for f in REQUIRED if f not in mapping]
    if missing:
        raise ImportError_(f"mapping missing required fields: {missing}")

    try:
        reader = csv.DictReader(io.StringIO(data.decode("utf-8-sig")))
        headers = reader.fieldnames or []
    except (UnicodeDecodeError, csv.Error) as exc:
        raise ImportError_(f"file is not valid UTF-8 CSV: {exc}")
    absent = [h for h in mapping.values() if h not in headers]
    if absent:
        raise ImportError_(f"headers not found in file: {absent}")

    rows, errors = [], []
    for i, rec in enumerate(reader, start=2):  # line 1 is the header
        if i - 1 > MAX_ROWS:
            raise ImportError_(f"more than {MAX_ROWS} rows")
        try:
            rows.append(_row(i, rec, mapping))
        except (ValueError, InvalidOperation, OverflowError) as exc:
            errors.append(RowError(line=i, message=str(exc)))
    return rows, errors


def from_record(line: int, rec: dict) -> Row:
    """A JSON object with canonical column names (sync webhooks) through the same checks as a CSV row."""
    text = {k: ("" if v is None else str(v)) for k, v in rec.items() if isinstance(k, str)}
    return _row(line, text, {k: k for k in text if k in REQUIRED + OPTIONAL})


def _row(line: int, rec: dict, mapping: dict[str, str]) -> Row:
    get = lambda f: (rec.get(mapping[f]) or "").strip() if f in mapping else ""
    if not get("sku"):
        raise ValueError("sku is required")
    if not get("name"):
        raise ValueError("name is required")
    kwargs = {
        "line": line, "sku": get("sku"), "name": get("name"),
        "price": _num(get("price"), integer=False), "on_hand": _num(get("on_hand"), integer=True),
    }
    for f in OPTIONAL:
        v = get(f)
        if not v:
            continue
        if f in ("tags", "substitutes"):
            kwargs[f] = [t.strip() for t in v.split("|") if t.strip()]
        elif f in ("mrp", "cost_price", "gst_rate"):
            kwargs[f] = _num(v, integer=False)
        elif f in ("bay", "shelf", "reorder_point", "reorder_qty", "lead_time_days", "shelf_life_days"):
            kwargs[f] = _num(v, integer=True)
        elif f == "status":
            if v.lower() not in ("active", "inactive", "discontinued", "seasonal"):
                raise ValueError("status must be active, inactive, discontinued or seasonal")
            kwargs[f] = v.lower()
        elif f == "side":
            if v.lower() not in ("left", "right"):
                raise ValueError("side must be left or right")
            kwargs[f] = v.lower()
        else:
            kwargs[f] = v
    return Row(**kwargs)


def upsert(store_id: str, rows: list[Row], *, high_value_threshold: float) -> ImportResult:
    result = ImportResult()
    existing = {d.id for d in db.products(store_id).select([]).stream()}
    batch = db.client().batch()
    pending = 0

    for r in rows:
        p = Product.from_row(
            store_id=store_id, sku=r.sku, name=r.name, price=r.price, threshold=high_value_threshold,
            barcode=r.barcode, brand=r.brand, category=r.category, subcategory=r.subcategory,
            description=r.description, mrp=r.mrp or r.price, unit=r.unit, image_url=r.image_url,
            tags=r.tags, substitutes=[f"{store_id}-{slug(s)}" for s in r.substitutes],
            pack_size=r.pack_size, cost_price=r.cost_price, gst_rate=r.gst_rate, shelf_life_days=r.shelf_life_days,
            status=r.status, origin=r.origin,
        )
        batch.set(db.products(store_id).document(p.product_id), p.model_dump(exclude={"embedding"}), merge=True)
        batch.set(db.inventory(store_id).document(p.product_id), Inventory(
            product_id=p.product_id, store_id=store_id, on_hand=r.on_hand,
            reorder_point=r.reorder_point, reorder_qty=r.reorder_qty,
            lead_time_days=r.lead_time_days, supplier_id=r.supplier_id,
        ).model_dump(exclude={"reserved"}), merge=True)
        if r.aisle:
            batch.set(db.locations(store_id).document(p.product_id), Location(
                product_id=p.product_id, store_id=store_id, aisle=r.aisle,
                bay=r.bay, shelf=r.shelf, side=r.side,
            ).model_dump())
        pending += 3
        if p.product_id in existing:
            result.updated += 1
        else:
            result.created += 1
            existing.add(p.product_id)
        if pending >= BATCH:
            batch.commit()
            batch, pending = db.client().batch(), 0
    if pending:
        batch.commit()
    return result
