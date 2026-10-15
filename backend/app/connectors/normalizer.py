"""Universal normalizer: propose a column mapping for any product file from its header and a few sample rows.

The model maps columns; the connector transforms values. The model never sees the bulk rows.
"""

import json
import logging
import re

from google.genai import types
from pydantic import BaseModel

from app.config import settings
from app.connectors.csv_connector import OPTIONAL, REQUIRED
from app.services import gemini

log = logging.getLogger(__name__)
FIELDS = REQUIRED + OPTIONAL
MEANING = {
    "sku": "the store's own item code or product id (unique per product)", "name": "product name as printed",
    "price": "selling price per unit", "on_hand": "current stock quantity", "barcode": "EAN/UPC/GTIN barcode",
    "brand": "brand", "category": "department or category", "subcategory": "sub-category", "description": "longer description",
    "mrp": "printed maximum retail price if different from selling price", "unit": "unit of sale (pc, kg, l)",
    "image_url": "image link", "tags": "keywords or aliases, | separated", "substitutes": "alternative item codes, | separated",
    "aisle": "aisle or shelf location code", "bay": "bay number", "shelf": "shelf number", "side": "left/right",
    "reorder_point": "minimum stock before reordering", "reorder_qty": "quantity to reorder", "lead_time_days": "supplier lead time in days",
    "supplier_id": "supplier code",
}
SYNONYMS = {
    "sku": ["sku", "item code", "itemcode", "code", "product id", "productid", "article", "article no", "item no", "id"],
    "name": ["name", "item name", "itemname", "product", "product name", "description", "item", "title"],
    "price": ["price", "rate", "selling price", "sale price", "unit price", "sp", "rate (rs)", "price (inr)"],
    "on_hand": ["on_hand", "on hand", "qty", "quantity", "stock", "qty on hand", "stock qty", "units", "available", "closing stock"],
    "barcode": ["barcode", "bar code", "ean", "ean13", "upc", "gtin"],
    "brand": ["brand", "make", "manufacturer"],
    "category": ["category", "dept", "department", "group", "cat"],
    "subcategory": ["subcategory", "sub category", "sub-category", "subgroup"],
    "mrp": ["mrp", "list price", "retail price"],
    "unit": ["unit", "uom", "pack"],
    "aisle": ["aisle", "location", "loc", "shelf", "shelf location", "bin", "rack"],
    "supplier_id": ["supplier", "supplier id", "vendor", "vendor id"],
    "reorder_point": ["reorder point", "min stock", "minimum", "rop"],
    "reorder_qty": ["reorder qty", "order qty", "eoq"],
    "lead_time_days": ["lead time", "lead time days"],
    "image_url": ["image", "image url", "photo"],
    "tags": ["tags", "keywords", "aliases"],
}


class Proposal(BaseModel):
    mapping: dict[str, str] = {}
    notes: list[str] = []
    questions: list[str] = []
    confidence: float = 0.0
    source: str = "heuristic"


def _norm(h: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]+", " ", h.lower())).strip()


def heuristic(header: list[str]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    used: set[str] = set()
    for field, names in SYNONYMS.items():
        for h in header:
            n = _norm(h)
            if h not in used and (n in {_norm(x) for x in names} or n.replace(" ", "_") == field):
                mapping[field] = h
                used.add(h)
                break
    return mapping


def _ask_model(header: list[str], samples: list[dict]) -> dict:
    prompt = (
        "You map a retailer's product file to a canonical schema. Canonical fields and meanings:\n"
        + "\n".join(f"- {f}: {MEANING[f]}" for f in FIELDS)
        + "\n\nFile header: " + json.dumps(header)
        + "\nSample rows: " + json.dumps(samples[:5], ensure_ascii=False)
        + "\n\nReturn JSON with: 'mapping' (object: canonical field -> exact header text, only for columns you are confident about), "
          "'notes' (array of short strings about units, currency, suffixes or formats you noticed), "
          "'questions' (array of short questions for the owner about ambiguous columns), 'confidence' (0 to 1). "
          "Never map a canonical field to a header that does not exist. Do not invent columns."
    )
    res = gemini.client().models.generate_content(
        model=settings.gemini_flash_model, contents=prompt,
        config=types.GenerateContentConfig(response_mime_type="application/json",
                                           thinking_config=types.ThinkingConfig(thinking_level="low"),
                                           http_options=types.HttpOptions(timeout=15000, retry_options=types.HttpRetryOptions(
                                               attempts=2, initial_delay=1, http_status_codes=[429, 503, 504]))))
    return json.loads(res.text)


def propose(header: list[str], samples: list[dict]) -> Proposal:
    p = Proposal()
    if header:
        try:   # the model path; any failure (not configured, timeout, bad JSON) falls back to the heuristic
            raw = _ask_model(header, samples)
            valid = {k: v for k, v in (raw.get("mapping") or {}).items() if k in FIELDS and v in header}
            p = Proposal(mapping=valid, notes=[str(n) for n in raw.get("notes") or []][:10],
                         questions=[str(q) for q in raw.get("questions") or []][:10],
                         confidence=max(0.0, min(1.0, float(raw.get("confidence") or 0))), source="model")
        except Exception as exc:
            log.warning("normalizer model failed, using heuristic: %s", exc)
    if not p.mapping:
        p = Proposal(mapping=heuristic(header), source="heuristic", confidence=0.5 if header else 0.0)
    for field in REQUIRED:
        if field not in p.mapping:
            p.questions.append(f"Which column holds '{field}' ({MEANING[field]})? I could not find it.")
    return p
