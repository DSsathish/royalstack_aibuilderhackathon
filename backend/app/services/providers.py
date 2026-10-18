"""Price comparison across providers: the demo provider in process, plus saved MCP connectors marked for comparison.
Rows carry provider, label, demo flag and status; nothing sample is ever presented as live (docs/lld/providers-mcp.md)."""

import time
from concurrent.futures import ThreadPoolExecutor

from app.connectors.mcp_client import MCPClient
from app.domain.models import now
from app.mcp import demo_catalog
from app.services import connectors, secrets

TIMEOUT_S = 8
CACHE_TTL_S = 600
_cache: dict[tuple[str, str], tuple[float, list[dict]]] = {}


def _tokens(text: str) -> set[str]:
    return {t for t in "".join(c.lower() if c.isalnum() else " " for c in text).split() if len(t) > 1}


def best_match(records: list[dict], product) -> dict | None:
    """The record for the same product: by barcode when both have one, else enough name words in common."""
    code = (getattr(product, "barcode", "") or "").strip()
    for r in records:
        if code and str(r.get("barcode", "")).strip() == code:
            return r
    want = _tokens(product.name)
    scored = []
    for r in records:
        have = _tokens(str(r.get("name", "")))
        if want and have:
            scored.append((len(want & have) / len(want | have), r))
    scored.sort(key=lambda x: -x[0])
    return scored[0][1] if scored and scored[0][0] >= 0.5 else None


def _row(meta: dict, records: list[dict], product) -> dict:
    m = best_match(records, product)
    if not m:
        return {**meta, "status": "no_match"}
    stock = m.get("stock", m.get("available"))
    return {**meta, "status": "ok", "name": m.get("name"), "price": m.get("price"), "mrp": m.get("mrp"),
            "available": int(stock) if isinstance(stock, (int, float)) else None, "fetched_at": now().isoformat()}


def _ask(store_id: str, c: connectors.Connector, product) -> dict:
    meta = {"provider": c.connector_id, "label": c.label, "demo": False}
    auth_name, _ = connectors._secret_names(store_id, c.connector_id)
    try:
        client = MCPClient(c.url, secrets.get(auth_name))
        client.initialize()
        return _row(meta, client.call(c.compare_tool or "search_products", {"query": product.name, "limit": 5}), product)
    except Exception as exc:
        return {**meta, "status": "unavailable", "note": str(exc)[:120]}


def compare(store_id: str, product) -> list[dict]:
    key = (store_id, product.product_id)
    hit = _cache.get(key)
    if hit and time.monotonic() - hit[0] < CACHE_TTL_S:
        return hit[1]
    rows = [_row({"provider": demo_catalog.PROVIDER, "label": demo_catalog.LABEL, "demo": True}, demo_catalog.search(product.name, 5), product)]
    live = [c for c in connectors.list_(store_id) if c.kind == "mcp" and c.compare and c.enabled]
    if live:
        with ThreadPoolExecutor(max_workers=min(4, len(live))) as pool:
            futures = [pool.submit(_ask, store_id, c, product) for c in live]
            for c, f in zip(live, futures):
                try:
                    rows.append(f.result(timeout=TIMEOUT_S))
                except Exception:
                    rows.append({"provider": c.connector_id, "label": c.label, "demo": False, "status": "unavailable", "note": "no answer in time"})
    _cache[key] = (time.monotonic(), rows)
    return rows
