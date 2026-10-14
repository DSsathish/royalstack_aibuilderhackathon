"""Agent wiring that does not need a live model: construction, gating, event translation."""

from google.adk.events import Event
from google.genai import types

from app.agent import agent, prompts


def test_build_uses_mode_tools_and_prompt():
    a = agent.build("instore")
    names = {t.__name__ for t in a.tools}
    assert "navigate_to" in names and "get_low_stock" not in names
    assert "aisle" in a.instruction.lower()
    assert "self-checkout" in a.instruction.lower()
    assert "self-checkout" not in agent.build("online").instruction.lower()
    assert "delivery and checkout" in agent.build("online").instruction.lower()


def test_prompt_core_rules_present():
    p = prompts.for_mode("owner")
    assert "tool" in p.lower() and "tamil" in p.lower()
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
