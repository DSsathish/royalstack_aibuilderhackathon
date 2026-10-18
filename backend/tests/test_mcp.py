import json

import httpx
import pytest
from fastapi.testclient import TestClient

from app.connectors import csv_connector as csvc
from app.connectors import mcp_client
from app.domain.models import Store
from app.main import app
from app.mcp import demo_catalog
from app.services import catalog, connectors, db, providers

client = TestClient(app)
OWNER = {"X-Test-Uid": "owner-1"}


@pytest.fixture
def shop(store_id):
    db.store_ref(store_id).set(Store(store_id=store_id, name="MCP Mart").model_dump())
    db.users().document("owner-1").set({"stores": [store_id], "roles": {store_id: "owner"}})
    csvc.upsert(store_id, [csvc.Row(line=1, sku="ATTA5", name="Aashirvaad Whole Wheat Atta 5kg", price=265, on_hand=12, barcode="8900000000012", category="Grocery", aisle="A1"),
                          csvc.Row(line=2, sku="SOAP", name="Lifebuoy Soap 100 g", price=30, on_hand=50, category="Personal Care")], high_value_threshold=500)
    catalog.invalidate(store_id)
    providers._cache.clear()
    return store_id


def rpc(path, method, params=None, mid=1):
    return client.post(path, json={"jsonrpc": "2.0", "id": mid, "method": method, "params": params or {}})


def test_store_server_answers_initialize_tools_and_a_search(shop):
    init = rpc(f"/mcp/stores/{shop}", "initialize", {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "t", "version": "1"}}).json()
    assert init["result"]["protocolVersion"] == "2025-06-18" and init["result"]["serverInfo"]["name"] == f"royal-stack-{shop}"
    assert client.post(f"/mcp/stores/{shop}", json={"jsonrpc": "2.0", "method": "notifications/initialized"}).status_code == 202
    names = [t["name"] for t in rpc(f"/mcp/stores/{shop}", "tools/list").json()["result"]["tools"]]
    assert names == ["store_info", "search_products", "get_product", "list_category"]
    found = rpc(f"/mcp/stores/{shop}", "tools/call", {"name": "search_products", "arguments": {"query": "atta"}}).json()["result"]
    assert found["isError"] is False and found["structuredContent"]["items"][0]["name"] == "Aashirvaad Whole Wheat Atta 5kg"
    assert "cost_price" not in found["structuredContent"]["items"][0] and "embedding" not in found["structuredContent"]["items"][0]
    assert rpc(f"/mcp/stores/{shop}", "tools/call", {"name": "get_product", "arguments": {"barcode": "8900000000012"}}).json()["result"]["structuredContent"]["sku"] == "ATTA5"
    assert rpc(f"/mcp/stores/{shop}", "nope").json()["error"]["code"] == -32601
    assert client.get(f"/mcp/stores/{shop}").status_code == 405
    assert rpc("/mcp/stores/no-such-store", "ping").status_code == 404


def test_demo_provider_marks_everything_as_demo_data():
    items = rpc("/mcp/demo/kirana-hub", "tools/call", {"name": "list_products", "arguments": {"limit": 3}}).json()["result"]["structuredContent"]["items"]
    assert len(items) == 3 and all(i["demo"] is True and i["provider"] == demo_catalog.LABEL for i in items)
    hit = rpc("/mcp/demo/kirana-hub", "tools/call", {"name": "search_products", "arguments": {"query": "atta aashirvaad"}}).json()["result"]["structuredContent"]["items"]
    assert hit and "Atta" in hit[0]["name"]


def _via_testclient(monkeypatch):
    """Route the MCP client's HTTP through the test app, and make one host fail."""
    def fake_post(url, body, headers):
        if "down.example" in url:
            raise httpx.ConnectError("connection refused")
        path = url.split("testserver", 1)[1]
        r = client.post(path, json=body, headers=headers)
        return httpx.Response(r.status_code, content=r.content, headers={"content-type": r.headers.get("content-type", "")}, request=httpx.Request("POST", url))
    monkeypatch.setattr(mcp_client, "post_json", fake_post)


def test_mcp_connector_imports_from_a_server_and_can_be_kept_for_comparison(shop, monkeypatch):
    _via_testclient(monkeypatch)
    url = "http://testserver/mcp/demo/kirana-hub"
    tools = client.post(f"/owner/{shop}/connectors/mcp/tools", json={"url": url}, headers=OWNER).json()
    assert tools["server"]["name"] == demo_catalog.PROVIDER and {t["name"] for t in tools["tools"]} == {"search_products", "list_products", "get_product"}
    insp = client.post(f"/owner/{shop}/connectors/inspect", data={"kind": "mcp", "url": url, "table": "list_products"}, headers=OWNER).json()
    assert insp["row_count"] == len(demo_catalog.ITEMS) and {"sku", "name", "price", "stock"} <= set(insp["columns"])
    mapping = {"sku": "sku", "name": "name", "price": "price", "on_hand": "stock", "barcode": "barcode", "brand": "brand", "category": "category", "mrp": "mrp"}
    done = client.post(f"/owner/{shop}/connectors/apply", data={"kind": "mcp", "url": url, "table": "list_products", "mapping": json.dumps(mapping),
                                                              "label": "Kirana Hub", "save": "true", "compare": "true"}, headers=OWNER).json()
    assert done["result"]["created"] == len(demo_catalog.ITEMS) and done["connector"]["kind"] == "mcp" and done["connector"]["compare"] is True
    saved = connectors.get(shop, done["connector"]["connector_id"])
    assert saved and saved.compare_tool == "search_products" and catalog.get_by_sku(shop, "KH-OATMILK") is not None


def test_compare_gives_a_demo_row_and_marks_an_unreachable_provider(shop, monkeypatch):
    _via_testclient(monkeypatch)
    connectors.save(shop, "mcp", label="Down Provider", mapping={}, actor="owner-1", url="https://down.example/mcp", compare=True)
    s = client.post("/sessions", json={"store_id": shop, "mode": "online"}).json()
    pid = f"{shop}-atta5"
    assert client.get(f"/stores/{shop}/products/{pid}/compare").status_code == 401
    rows = client.get(f"/stores/{shop}/products/{pid}/compare", headers={"X-Session-Id": s["session_id"]}).json()
    demo = next(r for r in rows if r["demo"])
    assert demo["status"] == "ok" and demo["label"] == demo_catalog.LABEL and demo["price"] > 0 and demo["name"].startswith("Aashirvaad")
    down = next(r for r in rows if r["label"] == "Down Provider")
    assert down["status"] == "unavailable" and not down["demo"]
    soap = client.get(f"/stores/{shop}/products/{shop}-soap/compare", headers={"X-Session-Id": s["session_id"]}).json()
    assert next(r for r in soap if r["demo"])["status"] == "no_match"
