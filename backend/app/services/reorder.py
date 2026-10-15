"""Reorder points, purchase order drafts with a Gemini rationale, owner approval."""

import json
import logging
import math
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import date

from google.cloud.firestore_v1 import FieldFilter
from google.genai import types
from pydantic import BaseModel

from app.config import settings
from app.domain.models import PurchaseOrderDraft, now
from app.services import catalog, db, forecast, gemini

log = logging.getLogger(__name__)
FESTIVALS = [("Diwali", date(2026, 11, 8)), ("Christmas", date(2026, 12, 25)), ("Pongal", date(2027, 1, 14))]


def reorder_point(*, avg_daily: float, lead_time_days: int, std_daily: float) -> int:
    return math.ceil(avg_daily * lead_time_days + 1.5 * std_daily)


def candidates(store_id: str) -> dict[str, list[dict]]:
    fc = forecast.all(store_id)
    groups: dict[str, list[dict]] = {}
    for d in db.inventory(store_id).stream():
        inv = d.to_dict()
        p = catalog.get_product(store_id, d.id)
        if not p:
            continue
        f = fc.get(d.id)
        available = max(0, inv["on_hand"] - inv.get("reserved", 0))
        manual_point, manual_qty = inv.get("reorder_point", 0), inv.get("reorder_qty", 0)
        if manual_qty <= 0:
            continue   # reorder_qty 0 means "do not reorder" (discontinued)
        if f:
            point = max(manual_point, reorder_point(avg_daily=f["avg_daily"], lead_time_days=inv.get("lead_time_days", 3), std_daily=f["std_daily"]))
            qty = max(manual_qty, math.ceil(f["avg_daily"] * 14))
        else:
            point, qty = manual_point, manual_qty
        if available <= point:
            groups.setdefault(inv.get("supplier_id") or "unknown", []).append({
                "product_id": d.id, "name": p.name, "qty": qty, "available": available, "reorder_point": point,
                "avg_daily": f["avg_daily"] if f else None, "lead_time_days": inv.get("lead_time_days", 3), "reason": ""})
    return groups


class _Reason(BaseModel):
    product_id: str
    reason: str


class _Rationale(BaseModel):
    summary: str
    reasons: list[_Reason]


EXPLAIN_LINES = 8   # the most urgent lines get a model-written reason; the rest use the template


def explain(store_id: str, supplier_name: str, lines: list[dict]) -> tuple[str, dict[str, str]]:
    """One Gemini call per supplier: a reason for the most urgent lines plus a summary. Template fallback on failure."""
    reasons = {l["product_id"]: f"{l['available']} left, below reorder point {l['reorder_point']}." for l in lines}
    if not gemini.configured():
        return "Items at or below reorder point.", reasons
    upcoming = [f"{n} on {d.isoformat()}" for n, d in FESTIVALS if 0 <= (d - date.today()).days <= 45]
    urgent = sorted(lines, key=lambda l: l["available"] / (l["reorder_point"] or 1))[:EXPLAIN_LINES]
    chunk = [{k: l[k] for k in ("product_id", "name", "qty", "available", "reorder_point", "avg_daily", "lead_time_days")} for l in urgent]
    prompt = (f"You advise a grocery store owner on a purchase order to supplier {supplier_name} with {len(lines)} lines. "
              f"Today is {date.today().isoformat()}. Upcoming festivals: {', '.join(upcoming) or 'none within 45 days'}. "
              f"For each line below give ONE short reason (max 18 words) using available stock, reorder point, average daily sales "
              f"and lead time, then a one-sentence summary for the whole order. Return JSON with keys 'summary' (string) "
              f"and 'reasons' (array of objects with 'product_id' and 'reason').\nLines: {json.dumps(chunk)}")
    by_name = {l["name"]: l["product_id"] for l in lines}
    try:
        res = gemini.client().models.generate_content(
            model=settings.gemini_flash_model, contents=prompt,
            # JSON mode without a strict schema: measured 5-8 s consistently; schema-constrained output hit 30 s+ 504s
            config=types.GenerateContentConfig(response_mime_type="application/json",
                                               thinking_config=types.ThinkingConfig(thinking_level="low"),
                                               http_options=types.HttpOptions(timeout=15000, retry_options=types.HttpRetryOptions(
                                                   attempts=2, initial_delay=1, http_status_codes=[429, 503, 504]))))
        r = _Rationale.model_validate_json(res.text)
        for item in r.reasons:
            reasons[by_name.get(item.product_id, item.product_id)] = item.reason
        return r.summary, reasons
    except Exception as exc:
        log.warning("explain failed: %s", exc)
        return "Items at or below reorder point.", reasons


def draft(store_id: str, *, created_by: str) -> list[PurchaseOrderDraft]:
    suppliers = {d.id: d.to_dict() for d in db.suppliers(store_id).stream()}
    open_for = {d.supplier_id for d in list_drafts(store_id) if d.status == "draft"}
    groups = {sid: lines for sid, lines in candidates(store_id).items() if sid not in open_for}
    names = {sid: suppliers.get(sid, {}).get("name", sid) for sid in groups}
    if gemini.configured():
        gemini.client()   # build the cached client once, before the threads race to create it
    with ThreadPoolExecutor(max_workers=2) as pool:   # one rationale call per supplier; Vertex 504s under heavier fan-out
        rationales = dict(zip(groups, pool.map(lambda sid: explain(store_id, names[sid], groups[sid]), groups)))
    out = []
    for sid, lines in groups.items():
        name = names[sid]
        summary, reasons = rationales[sid]
        for l in lines:
            l["reason"] = reasons.get(l["product_id"], "")
        po = PurchaseOrderDraft(po_id=uuid.uuid4().hex, store_id=store_id, supplier_id=sid, supplier_name=name,
                                lines=lines, summary=summary, created_by=created_by)
        db.po_drafts(store_id).document(po.po_id).set(po.model_dump())
        out.append(po)
    return out


def list_drafts(store_id: str) -> list[PurchaseOrderDraft]:
    docs = [PurchaseOrderDraft(**d.to_dict()) for d in db.po_drafts(store_id).stream()]
    return sorted(docs, key=lambda d: d.created_at, reverse=True)


def get(store_id: str, po_id: str) -> PurchaseOrderDraft | None:
    doc = db.po_drafts(store_id).document(po_id).get()
    return PurchaseOrderDraft(**doc.to_dict()) if doc.exists else None


def _email(store_name: str, po: PurchaseOrderDraft) -> str:
    rows = "\n".join(f"- {l['name']}: {l['qty']}" for l in po.lines)
    return f"Dear {po.supplier_name},\n\nPlease supply the following for {store_name}:\n{rows}\n\nThank you,\n{store_name}"


def approve(store_id: str, po_id: str, *, by: str, qty_override: dict[str, int] | None = None) -> PurchaseOrderDraft:
    po = get(store_id, po_id)
    if not po or po.status != "draft":
        raise ValueError("draft not found or already decided")
    for l in po.lines:
        if qty_override and l["product_id"] in qty_override:
            l["qty"] = max(0, int(qty_override[l["product_id"]]))
    po.status, po.decided_by, po.decided_at = "approved", by, now()
    po.email_text = _email(db.store_ref(store_id).get().to_dict().get("name", store_id), po)
    db.po_drafts(store_id).document(po_id).set(po.model_dump())
    db.audit(store_id).document(uuid.uuid4().hex).set({"actor": by, "action": "po_approved", "created_at": now(),
                                                       "payload": {"po_id": po_id, "supplier": po.supplier_id, "lines": len(po.lines)}})
    return po


def reject(store_id: str, po_id: str, *, by: str, reason: str) -> PurchaseOrderDraft:
    po = get(store_id, po_id)
    if not po or po.status != "draft":
        raise ValueError("draft not found or already decided")
    po.status, po.decided_by, po.decided_at, po.reason = "rejected", by, now(), reason[:300]
    db.po_drafts(store_id).document(po_id).set(po.model_dump())
    db.audit(store_id).document(uuid.uuid4().hex).set({"actor": by, "action": "po_rejected", "created_at": now(),
                                                       "payload": {"po_id": po_id, "reason": po.reason}})
    return po
