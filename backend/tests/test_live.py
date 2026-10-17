import pytest
from fastapi.testclient import TestClient

from app.agent import live
from app.domain.models import Inventory, Product, Store
from app.main import app
from app.services import catalog, db


def test_declarations_match_mode_tools():
    decls = live.declarations("instore")
    names = {d.name for d in decls}
    assert "navigate_to" in names and "add_to_cart" not in names and "get_low_stock" not in names
    decls = live.declarations("online")
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


def test_live_config_has_voice_vad_resumption_compression_and_history(store_id):
    from google.genai import types
    from app.domain.models import Store
    from app.services import conversation, sessions
    db.store_ref(store_id).set(Store(store_id=store_id, name="S").model_dump())
    s = sessions.create(store_id, "instore")
    conversation.add_turn(s, "user", "Do you have basmati rice?")
    cfg = live._config(s)
    assert cfg.speech_config.voice_config.prebuilt_voice_config.voice_name == "Kore"
    vad = cfg.realtime_input_config.automatic_activity_detection
    assert vad.silence_duration_ms == 900 and vad.prefix_padding_ms == 300
    assert vad.end_of_speech_sensitivity == types.EndSensitivity.END_SENSITIVITY_LOW
    assert cfg.session_resumption is not None and cfg.context_window_compression is not None
    assert cfg.enable_affective_dialog is True
    assert "basmati rice" in cfg.system_instruction and "ask the shopper to repeat" in cfg.system_instruction
    assert "navigate_to" in {d.name for d in cfg.tools[0].function_declarations}


def test_config_reuses_a_stored_resumption_handle(store_id):
    from app.domain.models import Store
    from app.services import sessions
    db.store_ref(store_id).set(Store(store_id=store_id, name="S").model_dump())
    s = sessions.create(store_id, "instore")
    live._resume_handles[s.session_id] = "abc123"
    assert live._config(s).session_resumption.handle == "abc123"
    live._resume_handles.pop(s.session_id, None)
    assert live._config(s).session_resumption.handle is None


def test_turn_recorder_saves_on_turn_complete_and_interruption():
    saved = []
    rec = live.TurnRecorder(lambda role, text: saved.append((role, text)))
    rec.user("where is "); rec.user("atta?")
    rec.assistant("Aisle A1, "); rec.assistant("bay 2.")
    rec.turn_complete()
    assert saved == [("user", "where is atta?"), ("assistant", "Aisle A1, bay 2.")]
    rec.assistant("The price is"); rec.interrupted()
    assert saved[-1] == ("assistant", "The price is")
    rec.turn_complete()
    assert len(saved) == 3           # nothing new to save


def test_search_in_store_also_highlights_the_top_product_on_the_map():
    result = {"products": [{"product_id": "p1", "name": "Atta", "aisle": "A1", "bay": 2}, {"product_id": "p2", "name": "Rice", "aisle": "A1", "bay": 3}], "signal": "found"}
    extra = live.extra_actions("search_products", result, {"mode": "instore"})
    assert extra == [{"type": "action", "name": "highlight_map", "data": {"aisle": "A1", "bay": 2, "product_id": "p1", "name": "Atta", "shelf": 1, "side": "left", "x": 0, "y": 0}}]
    assert live.extra_actions("search_products", result, {"mode": "online"}) == []
    assert live.extra_actions("search_products", {"products": [], "signal": "not_carried"}, {"mode": "instore"}) == []
    assert live.extra_actions("get_product", result, {"mode": "instore"}) == []


def test_dispatch_coerces_string_numbers(monkeypatch):
    from app.agent import tools
    seen = {}
    def fake_add(product_id: str, qty: int, tool_context) -> dict:
        seen.update(product_id=product_id, qty=qty)
        return {"ok": True}
    monkeypatch.setitem(live.TOOLS_BY_MODE, "online", [fake_add])
    fake_add.__name__ = "fake_add"
    assert live.dispatch("fake_add", {"product_id": "x", "qty": "2"}, {"mode": "online"}) == {"ok": True}
    assert seen == {"product_id": "x", "qty": 2}
