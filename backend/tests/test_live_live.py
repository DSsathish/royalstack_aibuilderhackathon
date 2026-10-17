"""Live speech-to-speech round trip against Gemini Live. LIVE_GEMINI=1 only."""

import json
import os

import pytest
from fastapi.testclient import TestClient

from app.domain.models import Inventory, Location, Product, Store
from app.main import app
from app.services import catalog, db, sessions

pytestmark = pytest.mark.skipif(os.environ.get("LIVE_GEMINI") != "1", reason="set LIVE_GEMINI=1 to run")


@pytest.fixture(autouse=True)
def real_gemini(monkeypatch):
    from dotenv import dotenv_values
    env = dotenv_values(os.path.join(os.path.dirname(__file__), "..", ".env"))
    from app.config import settings
    from app.services import gemini as gemini_svc
    for key, attr in (("GOOGLE_CLOUD_PROJECT", "google_cloud_project"), ("GEMINI_LOCATION", "gemini_location")):
        monkeypatch.setattr(settings, attr, env.get(key, getattr(settings, attr)))
    monkeypatch.setattr(settings, "google_genai_use_vertexai", env.get("GOOGLE_GENAI_USE_VERTEXAI", "true") == "true")
    gemini_svc.client.cache_clear()


def test_text_turn_returns_audio_actions_and_transcript(store_id):
    db.store_ref(store_id).set(Store(store_id=store_id, name="Royal Stack").model_dump())
    p = Product.from_row(store_id=store_id, sku="atta5", name="Aashirvaad Whole Wheat Atta 5kg", price=265, mrp=280, threshold=500, tags=["atta"])
    db.products(store_id).document(p.product_id).set(p.model_dump())
    db.inventory(store_id).document(p.product_id).set(Inventory(product_id=p.product_id, store_id=store_id, on_hand=40).model_dump())
    db.locations(store_id).document(p.product_id).set(Location(product_id=p.product_id, store_id=store_id, aisle="A1", bay=2).model_dump())
    catalog.invalidate(store_id)
    s = sessions.create(store_id, "instore")

    client = TestClient(app)
    audio, actions, transcript = 0, [], ""
    with client.websocket_connect(f"/agent/live?session_id={s.session_id}") as ws:
        ws.send_text(json.dumps({"type": "text", "text": "Where is Aashirvaad atta?"}))
        for _ in range(400):
            msg = ws.receive()
            if msg.get("bytes"):
                audio += len(msg["bytes"])
            elif msg.get("text"):
                e = json.loads(msg["text"])
                if e["type"] == "action": actions.append(e["name"])
                if e["type"] == "transcript" and e["role"] == "assistant": transcript += e["text"]
                if e["type"] == "turn_complete" and audio > 0: break   # tool-call turns complete before the spoken turn
        ws.send_text(json.dumps({"type": "end"}))
    print(f"\naudio_bytes={audio} actions={actions} transcript={transcript[:120]}")
    assert audio > 10000
    assert "show_products" in actions and "highlight_map" in actions


def test_owner_voice_turn_uses_owner_tools(store_id):
    db.store_ref(store_id).set(Store(store_id=store_id, name="Royal Stack").model_dump())
    p = Product.from_row(store_id=store_id, sku="ghee", name="Amul Ghee 1L", price=650, mrp=690, threshold=500)
    db.products(store_id).document(p.product_id).set(p.model_dump())
    db.inventory(store_id).document(p.product_id).set(Inventory(product_id=p.product_id, store_id=store_id, on_hand=1, reorder_point=5, supplier_id="sup-x").model_dump())
    catalog.invalidate(store_id)
    s = sessions.create(store_id, "owner", user_id="owner-live")

    client = TestClient(app)
    audio, actions, transcript = 0, [], ""
    with client.websocket_connect(f"/agent/live?session_id={s.session_id}") as ws:
        ws.send_text(json.dumps({"type": "text", "text": "What is running low in the store?"}))
        for _ in range(400):
            msg = ws.receive()
            if msg.get("bytes"):
                audio += len(msg["bytes"])
            elif msg.get("text"):
                e = json.loads(msg["text"])
                if e["type"] == "action": actions.append(e["name"])
                if e["type"] == "transcript" and e["role"] == "assistant": transcript += e["text"]
                if e["type"] == "turn_complete" and audio > 0: break
        ws.send_text(json.dumps({"type": "end"}))
    print(f"\nowner audio_bytes={audio} actions={actions} transcript={transcript[:120]}")
    assert audio > 10000 and "show_low_stock" in actions
    assert "ghee" in transcript.lower()


def test_live_voice_remembers_earlier_text_conversation(store_id):
    """Memory across channels: the product was named in a typed turn; the spoken turn only says 'add it'."""
    from app.services import conversation
    db.store_ref(store_id).set(Store(store_id=store_id, name="Royal Stack").model_dump())
    p = Product.from_row(store_id=store_id, sku="rice5", name="India Gate Basmati Rice 5kg", price=650, mrp=720, threshold=500, tags=["basmati", "rice"])
    db.products(store_id).document(p.product_id).set(p.model_dump())
    db.inventory(store_id).document(p.product_id).set(Inventory(product_id=p.product_id, store_id=store_id, on_hand=18).model_dump())
    catalog.invalidate(store_id)
    s = sessions.create(store_id, "online")
    conversation.add_turn(s, "user", "Do you have basmati rice?")
    conversation.add_turn(s, "assistant", "Yes, we have India Gate Basmati Rice 5kg for 650 rupees, 18 in stock.")

    client = TestClient(app)
    audio, actions, carts = 0, [], []
    with client.websocket_connect(f"/agent/live?session_id={s.session_id}") as ws:
        ws.send_text(json.dumps({"type": "text", "text": "Great, add it to my cart."}))
        for _ in range(400):
            msg = ws.receive()
            if msg.get("bytes"):
                audio += len(msg["bytes"])
            elif msg.get("text"):
                e = json.loads(msg["text"])
                if e["type"] == "action":
                    actions.append(e["name"])
                    if e["name"] == "cart_updated": carts.append(e["data"])
                if e["type"] == "turn_complete" and audio > 0: break
        ws.send_text(json.dumps({"type": "end"}))
    print(f"\nmemory actions={actions} cart={carts[-1] if carts else None}")
    assert "cart_updated" in actions and carts[-1].get("ok"), carts
    assert carts[-1]["cart"]["items"][0]["product_id"] == p.product_id
    turns = conversation.recent(s)
    assert turns[-2]["role"] == "user" and "add it" in turns[-2]["text"].lower()
    assert turns[-1]["role"] == "assistant" and turns[-1]["text"]
