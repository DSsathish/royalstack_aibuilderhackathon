"""MCP endpoints: the store catalog server and the demo provider (docs/lld/providers-mcp.md). Public, read-only."""

from fastapi import APIRouter, Path, Request, Response
from fastapi.responses import JSONResponse

from app.mcp import catalog_tools, demo_catalog, server
from app.services import db

router = APIRouter(prefix="/mcp", tags=["mcp"])
MAX_BODY = 64 * 1024


async def _serve(request: Request, tools: dict, name: str, instructions: str) -> Response:
    body = await request.body()
    if len(body) > MAX_BODY:
        return JSONResponse(server._error(None, -32600, "request too large"), status_code=413)
    try:
        message = __import__("json").loads(body or b"{}")
    except ValueError:
        return JSONResponse(server._error(None, -32700, "parse error"), status_code=400)
    reply = server.handle(message, tools, name, instructions)
    if reply is None:
        return Response(status_code=202)
    return JSONResponse(reply)


@router.get("")
def index():
    return {"servers": [{"path": "/mcp/stores/{store_id}", "about": "a shop's public catalog"},
                        {"path": "/mcp/demo/kirana-hub", "about": f"{demo_catalog.LABEL}: sample prices, not a real shop"}]}


@router.post("/stores/{store_id}")
async def store_server(request: Request, store_id: str = Path(pattern=r"^[a-z0-9-]{3,40}$")):
    if not db.store_ref(store_id).get().exists:
        return JSONResponse(server._error(None, -32004, "store not found"), status_code=404)
    return await _serve(request, catalog_tools.store_tools(store_id), f"royal-stack-{store_id}",
                        "This shop's catalog: search, look up and list products. Prices are in the shop's currency; stock is live.")


@router.post("/demo/kirana-hub")
async def demo_server(request: Request):
    return await _serve(request, catalog_tools.demo_tools(), demo_catalog.PROVIDER,
                        "Kirana Hub is a demo provider with sample prices and stock. Nothing here is a live offer.")


@router.api_route("/stores/{store_id}", methods=["GET", "DELETE"])
@router.api_route("/demo/kirana-hub", methods=["GET", "DELETE"])
def not_streaming():
    return Response(status_code=405, headers={"Allow": "POST"})
