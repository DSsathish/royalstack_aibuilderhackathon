"""A small Model Context Protocol server over Streamable HTTP: JSON-RPC 2.0 messages in, JSON answers out. Stateless;
notifications are acknowledged with nothing; batches are handled one by one. Tool sets are plain functions."""

import json
from dataclasses import dataclass
from typing import Any, Callable

PROTOCOL = "2025-06-18"


@dataclass
class Tool:
    name: str
    description: str
    input_schema: dict
    fn: Callable[[dict], Any]


def _ok(mid, result: dict) -> dict:
    return {"jsonrpc": "2.0", "id": mid, "result": result}


def _error(mid, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": mid, "error": {"code": code, "message": message}}


def handle(message: Any, tools: dict[str, Tool], server_name: str, instructions: str = "") -> dict | list | None:
    """One message (or a batch). None means nothing to send back (a notification)."""
    if isinstance(message, list):
        replies = [r for r in (handle(m, tools, server_name, instructions) for m in message) if r is not None]
        return replies or None
    if not isinstance(message, dict) or message.get("jsonrpc") != "2.0" or not isinstance(message.get("method"), str):
        return _error(message.get("id") if isinstance(message, dict) else None, -32600, "invalid request")
    method, mid, params = message["method"], message.get("id"), message.get("params") or {}
    if mid is None:
        return None
    if method == "initialize":
        return _ok(mid, {"protocolVersion": PROTOCOL, "capabilities": {"tools": {"listChanged": False}},
                         "serverInfo": {"name": server_name, "version": "1.0"}, "instructions": instructions})
    if method == "ping":
        return _ok(mid, {})
    if method == "tools/list":
        return _ok(mid, {"tools": [{"name": t.name, "description": t.description, "inputSchema": t.input_schema} for t in tools.values()]})
    if method == "tools/call":
        tool = tools.get(str(params.get("name", "")))
        if not tool:
            return _ok(mid, {"content": [{"type": "text", "text": "unknown tool"}], "isError": True})
        try:
            result = tool.fn(params.get("arguments") or {})
        except (ValueError, KeyError, TypeError) as exc:
            return _ok(mid, {"content": [{"type": "text", "text": str(exc)[:200]}], "isError": True})
        structured = result if isinstance(result, dict) else {"items": result}
        return _ok(mid, {"content": [{"type": "text", "text": json.dumps(structured, default=str)}], "structuredContent": structured, "isError": False})
    return _error(mid, -32601, "method not found")


def schema(**props: str) -> dict:
    """A flat object schema from name=type pairs ("string", "integer"); a trailing "!" marks a required property."""
    out = {"type": "object", "properties": {}, "required": []}
    for name, kind in props.items():
        required = kind.endswith("!")
        out["properties"][name] = {"type": kind.rstrip("!")}
        if required:
            out["required"].append(name)
    return out
