"""Agent wiring that does not need a live model: construction, gating, event translation."""

from google.adk.events import Event
from google.genai import types

from app.agent import agent, prompts


def test_build_uses_mode_tools_and_prompt():
    a = agent.build("instore")
    names = {t.__name__ for t in a.tools}
    assert "navigate_to" in names and "get_low_stock" not in names
    instore, online = agent.instruction_for("instore", {}), agent.instruction_for("online", {})
    assert "aisle" in instore.lower() and "self-checkout" in instore.lower()
    assert "self-checkout" not in online.lower() and "delivery and checkout" in online.lower()
    assert callable(a.instruction)   # provider: history is read from session state each turn


def test_prompt_core_rules_present():
    p = prompts.for_mode("owner")
    assert "tool" in p.lower() and "owner's language" in p.lower()
    assert "approval" in p.lower()


def ev(parts, partial=False, author="agent"):
    return Event(author=author, partial=partial, content=types.Content(role="model", parts=parts))


def test_translate_function_call_to_status():
    e = ev([types.Part(function_call=types.FunctionCall(name="search_products", args={"query": "milk"}))])
    assert list(agent.translate(e)) == [{"type": "status", "tool": "search_products"}]


def test_translate_function_response_to_action():
    e = ev([types.Part(function_response=types.FunctionResponse(name="navigate_to", response={"aisle": "A2"}))])
    assert list(agent.translate(e)) == [{"type": "action", "name": "highlight_map", "data": {"aisle": "A2"}}]


def test_translate_cart_tools_share_action():
    for name in ("add_to_cart", "remove_from_cart", "view_cart"):
        e = ev([types.Part(function_response=types.FunctionResponse(name=name, response={"ok": True}))])
        assert list(agent.translate(e))[0]["name"] == "cart_updated"


def test_translate_partial_text_to_token():
    e = ev([types.Part(text="Hel")], partial=True)
    assert list(agent.translate(e)) == [{"type": "token", "text": "Hel"}]


def test_translate_final_text_to_done():
    e = ev([types.Part(text="Hello there")])
    assert list(agent.translate(e)) == [{"type": "done", "text": "Hello there"}]


def test_translate_ignores_user_events():
    e = ev([types.Part(text="hi")], author="user")
    assert list(agent.translate(e)) == []


def test_instruction_includes_history_when_present():
    from app.agent.agent import instruction_for
    plain = instruction_for("instore", {"history": ""})
    with_hist = instruction_for("instore", {"history": "Earlier in this conversation (most recent last):\nShopper: milk?\nAssistant: Aisle A2."})
    assert plain == prompts.for_mode("instore")
    assert with_hist.startswith(prompts.for_mode("instore")) and with_hist.rstrip().endswith("Assistant: Aisle A2.")


def test_chat_records_turns_in_conversation_memory(store_id, monkeypatch):
    import asyncio
    from app.domain.models import Store
    from app.services import conversation, db, sessions
    db.store_ref(store_id).set(Store(store_id=store_id, name="S").model_dump())
    s = sessions.create(store_id, "online")

    class FakeRunner:
        async def run_async(self, **kw):
            yield ev([types.Part(text="Yes, we have it.")])
    monkeypatch.setattr(agent, "runner", lambda mode: FakeRunner())

    async def go():
        return [e async for e in agent.chat(s, "Do you have atta?")]
    events = asyncio.run(go())
    assert events[-1] == {"type": "done", "text": "Yes, we have it."}
    assert [(t["role"], t["text"]) for t in conversation.recent(s)] == [("user", "Do you have atta?"), ("assistant", "Yes, we have it.")]
