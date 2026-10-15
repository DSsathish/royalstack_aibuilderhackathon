import pytest
from fastapi.testclient import TestClient

from app.agent import live
from app.domain.models import Inventory, Product, Store
from app.main import app
from app.services import catalog, db


def test_declarations_match_mode_tools():
    decls = live.declarations("instore")
    names = {d.name for d in decls}
    assert "navigate_to" in names and "add_to_cart" in names and "get_low_stock" not in names
    add = next(d for d in decls if d.name == "add_to_cart")
    props = add.parameters.properties
    assert "tool_context" not in props
    assert props["product_id"].type.name == "STRING" and props["qty"].type.name == "INTEGER"
    assert set(add.parameters.required) == {"product_id", "qty"}
    search = next(d for d in decls if d.name == "search_products")
    assert "max_results" not in search.parameters.required
    assert "Tamil" in search.description


@pytest.fixture
def shop(store_id):
    db.store_ref(store_id).set(Store(store_id=store_id, name="S").model_dump())
    p = Product.from_row(store_id=store_id, sku="milk", name="Toned Milk", price=28, mrp=28, threshold=500, tags=["milk"])
    db.products(store_id).document(p.product_id).set(p.model_dump())
    db.inventory(store_id).document(p.product_id).set(Inventory(product_id=p.product_id, store_id=store_id, on_hand=3).model_dump())
    catalog.invalidate(store_id)
    return store_id


def test_dispatch_runs_tool_with_state(shop):
    out = live.dispatch("search_products", {"query": "milk"}, {"store_id": shop, "mode": "instore", "cart_id": f"{shop}-c"})
    assert out["products"][0]["name"] == "Toned Milk" and out["signal"] == "found"


def test_dispatch_unknown_tool(shop):
    assert live.dispatch("rm_rf", {}, {"store_id": shop, "mode": "instore"}) == {"error": "unknown_tool"}


def test_dispatch_mode_gated(shop):
    assert live.dispatch("get_low_stock", {}, {"store_id": shop, "mode": "instore"}) == {"error": "unknown_tool"}


def test_websocket_rejects_bad_session():
    client = TestClient(app)
    with pytest.raises(Exception):
        with client.websocket_connect("/agent/live?session_id=nope") as ws:
            ws.receive_text()


def test_websocket_accepts_owner_session_from_owner_endpoint_outside_dev(store_id, monkeypatch):
    import json
    from app.api import agent as agent_api
    from app.config import settings
    from app.domain.models import Store
    from app.services import sessions
    db.store_ref(store_id).set(Store(store_id=store_id, name="S").model_dump())
    owner_s = sessions.create(store_id, "owner", user_id="owner-1")       # as /owner/{id}/session does
    dev_s = sessions.create(store_id, "owner")                            # as the dev /sessions path does
    monkeypatch.setattr(settings, "env", "demo")

    async def fake_run(ws, s):
        await ws.send_text(json.dumps({"type": "ready", "mode": s.mode}))
    monkeypatch.setattr(agent_api.live, "run", fake_run)
    client = TestClient(app)
    with client.websocket_connect(f"/agent/live?session_id={owner_s.session_id}") as ws:
        assert json.loads(ws.receive_text())["mode"] == "owner"
    with pytest.raises(Exception):
        with client.websocket_connect(f"/agent/live?session_id={dev_s.session_id}") as ws:
            ws.receive_text()
