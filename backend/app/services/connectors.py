"""Connector agent: bring a shop's existing data (billing-software exports, a Google Sheet, an API, a read-only database)
into the catalog. The normalizer proposes the column mapping, the owner sees a preview and confirms, the importer writes,
and the sync job keeps saved sources in step. Guardrails and the flow: docs/lld/connector-agent.md."""

import csv
import io
import ipaddress
import json
import logging
import re
import socket
import uuid
from datetime import datetime, timedelta
from urllib.parse import parse_qs, urljoin, urlparse

import httpx
from google.genai import types
from pydantic import BaseModel

from app.config import settings
from app.connectors import csv_connector as csvc
from app.connectors import normalizer
from app.domain.models import now
from app.services import catalog, db, gemini, secrets

log = logging.getLogger(__name__)
KINDS = ("file", "sheet", "api", "db", "mcp")
KEEPABLE = ("sheet", "api", "db", "mcp")   # sources that can be pulled again on a schedule
MAX_BYTES = 10 * 1024 * 1024
MAX_ROWS = 20_000
EXTENSIONS = {"csv": "csv", "txt": "csv", "xlsx": "xlsx", "json": "json", "pdf": "pdf"}
DB_SCHEMES = ("postgresql", "postgresql+psycopg", "mysql", "mysql+pymysql")
PRIVATE = [ipaddress.ip_network(n) for n in (
    "0.0.0.0/8", "10.0.0.0/8", "100.64.0.0/10", "127.0.0.0/8", "169.254.0.0/16", "172.16.0.0/12", "192.168.0.0/16",
    "224.0.0.0/4", "240.0.0.0/4", "::/128", "::1/128", "fc00::/7", "fe80::/10")]


class SourceError(ValueError):
    pass


class Connector(BaseModel):
    connector_id: str
    kind: str
    label: str = ""
    url: str = ""
    table: str = ""
    mapping: dict[str, str] = {}
    every_min: int = 15
    enabled: bool = True
    created_by: str = ""
    created_at: datetime
    last_run_at: datetime | None = None
    last_result: dict = {}
    compare: bool = False                 # an MCP server also asked for prices when a shopper compares
    compare_tool: str = "search_products"


# --- guards -------------------------------------------------------------------------------------------------------

def public_host(host: str) -> None:
    """Every address the host resolves to must be public: no loopback, private, link-local or metadata ranges."""
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        raise SourceError(f"cannot resolve {host}")
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if any(ip in net for net in PRIVATE):
            raise SourceError("that address is not allowed")


def safe_url(url: str) -> str:
    u = urlparse(url)
    if u.scheme != "https" or not u.hostname:
        raise SourceError("an https link is required")
    public_host(u.hostname)
    return url


def fetch(url: str, headers: dict | None = None, hops: int = 5) -> httpx.Response:
    """GET with redirects followed by hand, so every hop is checked again."""
    for _ in range(hops):
        safe_url(url)
        res = httpx.get(url, headers=headers or {}, timeout=20, follow_redirects=False)
        if res.status_code in (301, 302, 303, 307, 308) and res.headers.get("location"):
            url = urljoin(url, res.headers["location"])
            continue
        res.raise_for_status()
        if len(res.content) > MAX_BYTES:
            raise SourceError("the response is larger than 10 MB")
        return res
    raise SourceError("too many redirects")


# --- readers: each returns (columns, records as dicts of strings) ---------------------------------------------------

def _cell(v) -> str:
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v)


def read_csv(data: bytes) -> tuple[list[str], list[dict]]:
    if len(data) > MAX_BYTES:
        raise SourceError("file larger than 10 MB")
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = data.decode("latin-1")
    reader = csv.DictReader(io.StringIO(text))
    columns = [c for c in (reader.fieldnames or []) if c]
    if not columns:
        raise SourceError("no header row found")
    records = []
    for rec in reader:
        if len(records) >= MAX_ROWS:
            raise SourceError(f"more than {MAX_ROWS} rows")
        records.append({k: _cell(v) for k, v in rec.items() if k})
    return columns, records


def read_xlsx(data: bytes) -> tuple[list[str], list[dict]]:
    import openpyxl
    try:
        wb = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    except Exception as exc:
        raise SourceError(f"not a readable Excel file: {exc}")
    rows = wb.worksheets[0].iter_rows(values_only=True)
    header = next(rows, None)
    if not header:
        raise SourceError("the sheet is empty")
    picks = [(str(h).strip(), i) for i, h in enumerate(header) if h is not None and str(h).strip()]
    columns = [c for c, _ in picks]
    records = []
    for r in rows:
        if r is None or all(v is None for v in r):
            continue
        if len(records) >= MAX_ROWS:
            raise SourceError(f"more than {MAX_ROWS} rows")
        records.append({c: _cell(r[i]) if i < len(r) else "" for c, i in picks})
    return columns, records


def _flat(v) -> str:
    return json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else _cell(v)


def read_json(data: bytes) -> tuple[list[str], list[dict]]:
    try:
        obj = json.loads(data.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SourceError(f"not valid JSON: {exc}")
    items = obj if isinstance(obj, list) else None
    if isinstance(obj, dict):
        items = next((obj[k] for k in ("items", "products", "rows", "data", "records") if isinstance(obj.get(k), list)), None)
        if items is None:
            items = next((v for v in obj.values() if isinstance(v, list)), None)
    if not isinstance(items, list) or not items or not all(isinstance(x, dict) for x in items):
        raise SourceError("expected a list of objects")
    if len(items) > MAX_ROWS:
        raise SourceError(f"more than {MAX_ROWS} rows")
    columns: list[str] = []
    for it in items:
        for k in it:
            if str(k) not in columns:
                columns.append(str(k))
    return columns, [{k: _flat(it.get(k)) for k in columns} for it in items]


def read_pdf(data: bytes) -> tuple[list[str], list[dict]]:
    """Gemini reads the document's tables into rows; it sees the document and never touches the catalog."""
    res = gemini.client().models.generate_content(
        model=settings.gemini_flash_model,
        contents=[types.Part.from_bytes(data=data, mime_type="application/pdf"),
                  "Extract every product row from the tables in this document as a JSON array of objects. Use the document's "
                  "own column headings as keys and the printed values as strings. Output only the JSON array."],
        config=types.GenerateContentConfig(response_mime_type="application/json",
                                           thinking_config=types.ThinkingConfig(thinking_level="low")))
    return read_json((res.text or "[]").encode())


def read_file(data: bytes, filename: str) -> tuple[list[str], list[dict]]:
    if len(data) > MAX_BYTES:
        raise SourceError("file larger than 10 MB")
    ext = filename.rsplit(".", 1)[-1].lower() if "." in (filename or "") else ""
    kind = EXTENSIONS.get(ext)
    if not kind:
        raise SourceError("use a .csv, .xlsx, .json or .pdf file")
    return {"csv": read_csv, "xlsx": read_xlsx, "json": read_json, "pdf": read_pdf}[kind](data)


def sheet_csv_url(url: str) -> str:
    m = re.search(r"/spreadsheets/d/([A-Za-z0-9_-]+)", url)
    if not m:
        raise SourceError("that is not a Google Sheets link")
    u = urlparse(url)
    gid = (parse_qs(u.query).get("gid") or [None])[0] or (re.search(r"gid=(\d+)", u.fragment or "") or [None, None])[1]
    return f"https://docs.google.com/spreadsheets/d/{m.group(1)}/export?format=csv" + (f"&gid={gid}" if gid else "")


def read_sheet(url: str) -> tuple[list[str], list[dict]]:
    res = fetch(sheet_csv_url(url))
    if b"<html" in res.content[:400].lower():
        raise SourceError("the sheet is not shared: in Google Sheets choose Share, then 'Anyone with the link' as viewer")
    return read_csv(res.content)


def read_api(url: str, auth: str = "") -> tuple[list[str], list[dict]]:
    res = fetch(url, headers={"Authorization": auth} if auth else None)
    body = res.content
    if "json" in res.headers.get("content-type", "") or body[:1] in (b"[", b"{"):
        return read_json(body)
    return read_csv(body)


def _engine(dsn: str):
    from sqlalchemy import create_engine
    from sqlalchemy.engine import make_url
    try:
        url = make_url(dsn)
    except Exception:
        raise SourceError("that connection string is not valid")
    if url.drivername == "sqlite" and settings.env in ("dev", "test"):
        return create_engine(url)
    if url.drivername not in DB_SCHEMES:
        raise SourceError("only postgresql:// and mysql:// connections are supported")
    if not url.host:
        raise SourceError("the connection string needs a host")
    public_host(url.host)
    url = url.set(drivername={"postgresql": "postgresql+psycopg", "mysql": "mysql+pymysql"}.get(url.drivername, url.drivername))
    return create_engine(url, pool_pre_ping=True, connect_args={"connect_timeout": 10})


def discover(dsn: str) -> list[str]:
    from sqlalchemy import inspect as sa_inspect
    engine = _engine(dsn)
    try:
        return sorted(sa_inspect(engine).get_table_names())[:200]
    finally:
        engine.dispose()


def read_db(dsn: str, table: str) -> tuple[list[str], list[dict]]:
    """One table, read-only, capped. The table must be one the database itself lists."""
    from sqlalchemy import inspect as sa_inspect, text
    engine = _engine(dsn)
    try:
        if table not in sa_inspect(engine).get_table_names():
            raise SourceError("that table is not in the database")
        quoted = engine.dialect.identifier_preparer.quote(table)
        with engine.connect() as conn:
            if engine.dialect.name == "postgresql":
                conn = conn.execution_options(postgresql_readonly=True)
            elif engine.dialect.name == "mysql":
                conn.execute(text("SET SESSION TRANSACTION READ ONLY"))
            result = conn.execute(text(f"SELECT * FROM {quoted} LIMIT {MAX_ROWS + 1}"))
            columns = [str(c) for c in result.keys()]
            rows = result.fetchall()
    finally:
        engine.dispose()
    if len(rows) > MAX_ROWS:
        raise SourceError(f"more than {MAX_ROWS} rows")
    return columns, [{c: _cell(v) for c, v in zip(columns, r)} for r in rows]


def read_mcp(url: str, auth: str = "", tool: str = "") -> tuple[list[str], list[dict]]:
    """Call the server's catalog tool and read its records like a JSON document."""
    from app.connectors.mcp_client import MCPClient
    client = MCPClient(url, auth)
    client.initialize()
    records = client.call(tool or "list_products", {"limit": MAX_ROWS})
    if not records:
        raise SourceError("the tool returned no records")
    return read_json(json.dumps(records).encode("utf-8"))


def mcp_tools(url: str, auth: str = "") -> dict:
    """What an MCP server offers, for the owner to pick a tool before importing."""
    from app.connectors.mcp_client import MCPClient
    client = MCPClient(url, auth)
    info = client.initialize()
    return {"server": info.get("serverInfo") or {}, "instructions": (info.get("instructions") or "")[:300], "tools": client.tools()}


def read(kind: str, *, data: bytes = b"", filename: str = "", url: str = "", auth: str = "", dsn: str = "", table: str = ""):
    if kind == "mcp":
        return read_mcp(url, auth, table)
    if kind == "file":
        return read_file(data, filename)
    if kind == "sheet":
        return read_sheet(url)
    if kind == "api":
        return read_api(url, auth)
    if kind == "db":
        return read_db(dsn, table)
    raise SourceError("unknown source kind")


# --- inspect, preview, apply ----------------------------------------------------------------------------------------

def check_mapping(mapping: dict, columns: list[str]) -> dict[str, str]:
    clean = {k: v for k, v in (mapping or {}).items() if v}
    bad = [k for k in clean if k not in normalizer.FIELDS]
    if bad:
        raise SourceError(f"unknown fields in the mapping: {bad}")
    absent = [v for v in clean.values() if v not in columns]
    if absent:
        raise SourceError(f"columns not in the source: {absent}")
    missing = [f for f in csvc.REQUIRED if f not in clean]
    if missing:
        raise SourceError(f"the mapping still needs: {', '.join(missing)}")
    return clean


def inspect(store_id: str, kind: str, *, mapping: dict | None = None, **source) -> dict:
    """Read the source, propose (or check) a mapping, and say what applying it would change. Writes nothing."""
    columns, records = read(kind, **source)
    samples = records[:5]
    proposal = None
    if not mapping:
        proposal = normalizer.propose(columns, samples)
        mapping = proposal.mapping
    out = {"kind": kind, "columns": columns, "samples": samples, "row_count": len(records), "mapping": mapping,
           "proposal": proposal.model_dump() if proposal else None, "preview": None, "problem": ""}
    try:
        clean = check_mapping(mapping, columns)
    except SourceError as exc:
        out["problem"] = str(exc)               # the owner completes the mapping; no preview until it is whole
        return out
    rows, errors = csvc.rows_from_records(records, clean)
    out["mapping"] = clean
    out["preview"] = preview(store_id, rows, errors)
    return out


def preview(store_id: str, rows: list[csvc.Row], errors: list[csvc.RowError]) -> dict:
    products, _ = catalog.product_map(store_id)
    by_sku = {p.sku.lower(): p for p in products.values()}
    stock = {d.id: (d.to_dict() or {}).get("on_hand", 0) for d in db.inventory(store_id).stream()}
    counts = {"adds": 0, "updates": 0, "restocks": 0, "unchanged": 0}
    changes = []
    for r in rows:
        p = by_sku.get(r.sku.lower())
        if not p:
            counts["adds"] += 1
            change = ("add", f"{r.name}: new at ₹{r.price:g}, {r.on_hand} on hand")
        elif p.name != r.name or abs(float(p.price) - float(r.price)) > 0.004:
            counts["updates"] += 1
            change = ("update", f"{p.name}: ₹{float(p.price):g} -> ₹{r.price:g}" if p.name == r.name else f"{p.name} -> {r.name}")
        elif stock.get(p.product_id, 0) != r.on_hand:
            counts["restocks"] += 1
            change = ("restock", f"{r.name}: {stock.get(p.product_id, 0)} -> {r.on_hand} on hand")
        else:
            counts["unchanged"] += 1
            continue
        if len(changes) < 8:
            changes.append({"kind": change[0], "sku": r.sku, "note": change[1]})
    return {**counts, "errors": len(errors), "error_samples": [e.model_dump() for e in errors[:5]], "changes": changes}


def apply(store_id: str, kind: str, *, mapping: dict, actor: str, label: str = "", **source) -> dict:
    columns, records = read(kind, **source)
    clean = check_mapping(mapping, columns)
    rows, errors = csvc.rows_from_records(records, clean)
    store = db.store_ref(store_id).get().to_dict() or {}
    result = csvc.upsert(store_id, rows, high_value_threshold=store.get("high_value_threshold", 500))
    catalog.bump(store_id)
    summary = {"created": result.created, "updated": result.updated, "errors": len(errors), "rows": len(rows), "source": label or kind}
    _audit(store_id, actor, "connector_apply", summary)
    return {**summary, "error_samples": [e.model_dump() for e in errors[:5]]}


# --- saved connectors ---------------------------------------------------------------------------------------------

def _col(store_id: str):
    return db.store_ref(store_id).collection("connectors")


def _secret_names(store_id: str, cid: str) -> tuple[str, str]:
    return f"conn-{store_id}-{cid}", f"conn-{store_id}-{cid}-dsn"


def save(store_id: str, kind: str, *, label: str, mapping: dict, actor: str, url: str = "", table: str = "",
         every_min: int = 15, auth: str = "", dsn: str = "", compare: bool = False, compare_tool: str = "search_products") -> Connector:
    if kind not in KEEPABLE:
        raise SourceError("only a sheet, an API or a database can be kept in step")
    cid = uuid.uuid4().hex[:12]
    auth_name, dsn_name = _secret_names(store_id, cid)
    if auth:
        secrets.put(auth_name, auth)
    if dsn:
        secrets.put(dsn_name, dsn)
    c = Connector(connector_id=cid, kind=kind, label=(label or kind)[:80], url=url, table=table, mapping=mapping,
                  every_min=max(5, min(1440, int(every_min))), created_by=actor, created_at=now(),
                  compare=bool(compare and kind == "mcp"), compare_tool=(compare_tool or "search_products")[:60])
    _col(store_id).document(cid).set(c.model_dump())
    _audit(store_id, actor, "connector_saved", {"connector_id": cid, "kind": kind, "label": c.label, "every_min": c.every_min})
    return c


def list_(store_id: str) -> list[Connector]:
    return sorted((Connector(**d.to_dict()) for d in _col(store_id).stream()), key=lambda c: c.created_at)


def get(store_id: str, cid: str) -> Connector | None:
    doc = _col(store_id).document(cid).get()
    return Connector(**doc.to_dict()) if doc.exists else None


def remove(store_id: str, cid: str, actor: str) -> bool:
    c = get(store_id, cid)
    if not c:
        return False
    _col(store_id).document(cid).delete()
    auth_name, dsn_name = _secret_names(store_id, cid)
    for name, needed in ((auth_name, c.kind == "api"), (dsn_name, c.kind == "db")):
        if needed:
            try:
                secrets.put(name, "")           # blank the secret; the connector is gone
            except Exception as exc:
                log.warning("could not blank %s: %s", name, exc)
    _audit(store_id, actor, "connector_removed", {"connector_id": cid, "label": c.label})
    return True


def run(store_id: str, c: Connector, actor: str = "scheduler") -> dict:
    auth_name, dsn_name = _secret_names(store_id, c.connector_id)
    source = {"url": c.url, "table": c.table}
    if c.kind in ("api", "mcp"):
        source["auth"] = secrets.get(auth_name)
    if c.kind == "db":
        source["dsn"] = secrets.get(dsn_name)
    try:
        outcome = {"ok": True, **apply(store_id, c.kind, mapping=c.mapping, actor=actor, label=c.label, **source)}
    except Exception as exc:
        log.warning("connector %s/%s failed: %s", store_id, c.connector_id, exc)
        outcome = {"ok": False, "error": str(exc)[:200]}
    outcome.pop("error_samples", None)
    _col(store_id).document(c.connector_id).update({"last_run_at": now(), "last_result": outcome})
    return outcome


def run_due() -> dict:
    """Every store's enabled connectors whose interval has passed. Called with the sync job."""
    ran = failed = 0
    for store in db.client().collection("stores").stream():
        for c in list_(store.id):
            if c.enabled and (not c.last_run_at or now() - c.last_run_at >= timedelta(minutes=c.every_min)):
                ran += 1
                if not run(store.id, c).get("ok"):
                    failed += 1
    return {"connectors_run": ran, "connectors_failed": failed}


def _audit(store_id: str, actor: str, action: str, payload: dict) -> None:
    db.audit(store_id).document(uuid.uuid4().hex).set({"actor": actor, "action": action, "created_at": now(), "payload": payload})
