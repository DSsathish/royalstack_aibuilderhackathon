"""Live evaluation against Gemini. Runs only when LIVE_GEMINI=1 and a key is configured.

    LIVE_GEMINI=1 backend/scripts/test.sh tests/test_agent_live.py -s

Each scenario asserts which tools were called and a fact that must appear in the reply.
"""

import asyncio
import os

import pytest

from app.agent import agent
from app.domain.models import Inventory, Location, Product, Store
from app.services import catalog, db, sessions

pytestmark = pytest.mark.skipif(os.environ.get("LIVE_GEMINI") != "1", reason="set LIVE_GEMINI=1 to run")


@pytest.fixture(autouse=True)
def pace():
    """Free tier allows ~5 requests/min per model; each turn uses 2 to 4. Space the scenarios out."""
    import time
    time.sleep(30)


@pytest.fixture(autouse=True)
def real_gemini(monkeypatch):
    # conftest blanks the key for unit tests; restore it from the real .env for live runs
    from dotenv import dotenv_values
    env = dotenv_values(os.path.join(os.path.dirname(__file__), "..", ".env"))
    from app.config import settings
    monkeypatch.setattr(settings, "gemini_api_key", env.get("GEMINI_API_KEY", ""))
    monkeypatch.setattr(settings, "google_genai_use_vertexai", env.get("GOOGLE_GENAI_USE_VERTEXAI", "false") == "true")
    monkeypatch.setattr(settings, "gemini_flash_model", env.get("GEMINI_FLASH_MODEL", settings.gemini_flash_model))
    monkeypatch.setenv("GOOGLE_API_KEY", settings.gemini_api_key)
    agent.runner.cache_clear()


def put(store_id, sku, name, price, on_hand, *, tags=(), subcategory="", substitutes=(), aisle="A1", bay=1):
    p = Product.from_row(store_id=store_id, sku=sku, name=name, price=price, mrp=price + 5, threshold=500,
                         tags=list(tags), subcategory=subcategory, substitutes=[f"{store_id}-{s}" for s in substitutes])
    db.products(store_id).document(p.product_id).set(p.model_dump())
    db.inventory(store_id).document(p.product_id).set(
        Inventory(product_id=p.product_id, store_id=store_id, on_hand=on_hand).model_dump())
    db.locations(store_id).document(p.product_id).set(
        Location(product_id=p.product_id, store_id=store_id, aisle=aisle, bay=bay).model_dump())


@pytest.fixture
def shop(store_id):
    db.store_ref(store_id).set(Store(store_id=store_id, name="Royal Stack").model_dump())
    put(store_id, "atta5", "Aashirvaad Whole Wheat Atta 5kg", 265, 40, tags=["atta", "wheat flour", "आटा"], aisle="A1", bay=2)
    put(store_id, "milk500", "Aavin Toned Milk 500ml", 28, 60, tags=["milk", "பால்", "दूध"], subcategory="Milk", aisle="A2", bay=3)
    put(store_id, "soya", "Sofit Soya Milk 1L", 110, 12, tags=["soya milk", "plant milk"], subcategory="Plant milk")
    put(store_id, "almond", "So Good Almond Milk 1L", 230, 0, tags=["almond milk", "plant milk"], subcategory="Plant milk", substitutes=("soya",))
    put(store_id, "dolo", "Dolo 650 15 tablets", 30, 50, tags=["paracetamol", "fever", "headache"], aisle="A5")
    catalog.invalidate(store_id)
    return store_id


def run(session, text):
    async def go():
        out = []
        async for e in agent.chat(session, text):
            out.append(e)
        return out
    events = asyncio.run(go())
    tools = [e["tool"] for e in events if e["type"] == "status"]
    reply = "".join(e["text"] for e in events if e["type"] == "done") or "".join(e["text"] for e in events if e["type"] == "token")
    print(f"\n[{text}] tools={tools}\n  -> {reply[:200]}")
    return tools, reply, events


def test_where_is_atta_navigates(shop):
    tools, reply, _ = run(sessions.create(shop, "instore"), "Where is Aashirvaad atta?")
    assert "search_products" in tools and "navigate_to" in tools
    assert "A1" in reply


def test_tamil_milk_answered_in_tamil(shop):
    tools, reply, _ = run(sessions.create(shop, "instore"), "பால் எங்கே இருக்கு?")
    assert "search_products" in tools
    assert any("஀" <= ch <= "௿" for ch in reply), "reply should contain Tamil"


def test_out_of_stock_offers_substitute(shop):
    tools, reply, _ = run(sessions.create(shop, "instore"), "Do you have almond milk?")
    assert "search_products" in tools
    assert "soya" in reply.lower()


def test_not_carried_is_honest(shop):
    tools, reply, _ = run(sessions.create(shop, "online"), "Do you sell oat milk?")
    assert "search_products" in tools
    assert "oat" in reply.lower()
    assert "record_demand_signal" in tools
    sigs = [d.to_dict() for d in db.demand_signals(shop).stream()]
    assert any(s["type"] == "not_carried" and s["source"] == "agent" and "oat" in s["query_text"].lower() for s in sigs)


def test_add_to_cart_emits_cart_action(shop):
    s = sessions.create(shop, "instore")
    tools, reply, events = run(s, "Add 2 packets of Dolo 650 to my cart")
    assert "add_to_cart" in tools
    carts = [e for e in events if e["type"] == "action" and e["name"] == "cart_updated"]
    assert carts and carts[-1]["data"]["cart"]["count"] == 2


def test_online_mode_never_navigates(shop):
    tools, reply, _ = run(sessions.create(shop, "online"), "Where is the milk kept?")
    assert "navigate_to" not in tools
    assert "aisle" not in reply.lower()


def test_owner_low_stock(shop):
    tools, reply, _ = run(sessions.create(shop, "owner"), "What is running low?")
    assert "get_low_stock" in tools
    assert "almond" in reply.lower()


def test_off_topic_redirects(shop):
    tools, reply, _ = run(sessions.create(shop, "instore"), "Write me a poem about the moon")
    assert len(reply) < 400
