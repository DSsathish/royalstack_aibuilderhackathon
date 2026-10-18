"""A minimal MCP client over Streamable HTTP for the connector agent: initialize, list tools, call one, and turn the
result into records. The same network guards as the API source (public host, size cap, timeouts)."""

import json

import httpx

from app.mcp.server import PROTOCOL

TIMEOUT_S = 20
MAX_BYTES = 10 * 1024 * 1024
LIST_KEYS = ("items", "products", "results", "data", "rows")


def post_json(url: str, body: dict, headers: dict) -> httpx.Response:
    from app.services import connectors                       # late: connectors imports this module
    target = connectors.safe_url(url)
    connectors.public_host(httpx.URL(target).host)
    res = httpx.post(target, json=body, headers={"Accept": "application/json, text/event-stream", "Content-Type": "application/json", **headers}, timeout=TIMEOUT_S, follow_redirects=False)
    if len(res.content) > MAX_BYTES:
        raise ValueError("response larger than 10 MB")
    return res


def _messages(res: httpx.Response) -> list[dict]:
    """JSON, a JSON batch, or the data lines of an SSE stream."""
    ctype = res.headers.get("content-type", "")
    if "text/event-stream" in ctype:
        out = []
        for line in res.text.splitlines():
            if line.startswith("data:"):
                try:
                    out.append(json.loads(line[5:].strip()))
                except ValueError:
                    continue
        return out
    if not res.content.strip():
        return []
    data = res.json()
    return data if isinstance(data, list) else [data]


def records_from(result: dict) -> list[dict]:
    """The records in a tool result: structuredContent first, else the first JSON text block."""
    candidates = [result.get("structuredContent")]
    for c in result.get("content") or []:
        if c.get("type") == "text":
            try:
                candidates.append(json.loads(c.get("text", "")))
            except ValueError:
                continue
    for data in candidates:
        if isinstance(data, list):
            return [d for d in data if isinstance(d, dict)]
        if isinstance(data, dict):
            for key in LIST_KEYS:
                if isinstance(data.get(key), list):
                    return [d for d in data[key] if isinstance(d, dict)]
            if data and all(not isinstance(v, (dict, list)) for v in data.values()):
                return [data]
    return []


class MCPClient:
    def __init__(self, url: str, auth: str = ""):
        self.url, self.auth, self.session_id, self.server = url, auth, "", {}
        self._next = 1

    def _headers(self) -> dict:
        h = {}
        if self.auth:
            h["Authorization"] = self.auth
        if self.session_id:
            h["Mcp-Session-Id"] = self.session_id
        return h

    def _rpc(self, method: str, params: dict | None = None) -> dict:
        mid = self._next
        self._next += 1
        res = post_json(self.url, {"jsonrpc": "2.0", "id": mid, "method": method, "params": params or {}}, self._headers())
        if res.status_code >= 400:
            raise ValueError(f"the MCP server answered {res.status_code}")
        if res.headers.get("mcp-session-id"):
            self.session_id = res.headers["mcp-session-id"]
        for m in _messages(res):
            if m.get("id") == mid:
                if "error" in m:
                    raise ValueError(f"MCP error: {m['error'].get('message', 'unknown')}")
                return m.get("result") or {}
        raise ValueError("no answer from the MCP server")

    def initialize(self) -> dict:
        r = self._rpc("initialize", {"protocolVersion": PROTOCOL, "capabilities": {}, "clientInfo": {"name": "royal-stack-connector", "version": "1.0"}})
        self.server = r.get("serverInfo") or {}
        try:
            post_json(self.url, {"jsonrpc": "2.0", "method": "notifications/initialized"}, self._headers())
        except (httpx.HTTPError, ValueError):
            pass                                                  # a server may not accept the notification; the session still works
        return r

    def tools(self) -> list[dict]:
        return [{"name": t.get("name", ""), "description": t.get("description", "")} for t in self._rpc("tools/list").get("tools", [])]

    def call(self, name: str, arguments: dict) -> list[dict]:
        r = self._rpc("tools/call", {"name": name, "arguments": arguments})
        if r.get("isError"):
            text = next((c.get("text", "") for c in r.get("content") or [] if c.get("type") == "text"), "tool error")
            raise ValueError(f"{name}: {text[:200]}")
        return records_from(r)
