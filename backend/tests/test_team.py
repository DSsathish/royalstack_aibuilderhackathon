"""Agent teams: structure, tool partition, instructions and event translation. No model calls."""
from google.adk.events import Event
from google.genai import types

from app.agent import agent, prompts, team
from app.agent.tools import TOOLS_BY_MODE


def _tools(a):
    return {fn.__name__ for fn in (getattr(a, "tools", []) or [])}


def test_every_mode_tool_belongs_to_exactly_one_team_and_coordinators_route_only():
    for mode in ("instore", "online", "owner"):
        root = agent.build(mode)
        agents = team.agents_of(root)
        assert not root.tools and root.sub_agents and not root.disallow_transfer_to_parent
        union = set().union(*(_tools(a) for a in agents.values()))
        assert union == {fn.__name__ for fn in TOOLS_BY_MODE[mode]}, mode
        for name, a in agents.items():
            if name != root.name and hasattr(a, "disallow_transfer_to_parent"):
                assert a.disallow_transfer_to_parent, name          # specialists hand over sideways, never back up
            assert a.description, name


def test_mode_specific_specialists():
    assert "navigation_agent" in team.agents_of(agent.build("instore"))
    assert "navigation_agent" not in team.agents_of(agent.build("online"))
    assert "add_to_cart" in _tools(team.agents_of(agent.build("online"))["cart_agent"])
    assert "add_to_cart" not in _tools(team.agents_of(agent.build("instore"))["cart_agent"])      # in store, items enter by scanning
    owner = team.agents_of(agent.build("owner"))
    assert _tools(owner["data_connector"]) == {"connect_source", "apply_source", "connectors_status", "sync_status"}
    assert owner["stock_scout"].output_key == "stock_notes" and owner["sales_scout"].output_key == "sales_notes"
    assert not owner["briefing_writer"].tools


def test_specialist_instruction_has_shared_rules_focus_and_language_last():
    state = {"history": "Earlier in this conversation:\nShopper: hi\nAssistant: hello", "language": "ta"}
    text = prompts.agent_instruction("instore", state, prompts.FOCUS["navigation_agent"])
    assert "Answer only from tool results" in text and "navigate_to" in text and "transfer_to_agent" in text
    assert text.index("Earlier in this conversation") < text.index("Your job") < text.index("Language:")
    assert "chose Tamil" in text.split("Language:")[-1]
    writer = prompts.agent_instruction("owner", {"stock_notes": "Milk low (2 left)", "sales_notes": "₹12,400 today"}, prompts.FOCUS["briefing_writer"])
    assert "Milk low" in writer and "₹12,400" in writer and writer.index("Sales notes") < writer.index("Language:")
    assert "transfer every" in prompts.coordinator_focus("owner") and "briefing" in prompts.coordinator_focus("owner")


def _ev(parts, author="catalog_agent", partial=False):
    return Event(author=author, partial=partial, content=types.Content(role="model", parts=parts))


def test_translate_shows_handovers_as_labels_and_hides_scout_notes():
    call = types.Part(function_call=types.FunctionCall(name="transfer_to_agent", args={"agent_name": "navigation_agent"}))
    assert list(agent.translate(_ev([call], author="retail_instore"))) == [{"type": "status", "tool": "transfer_to_agent", "agent": "navigation_agent", "label": "Checking the map"}]
    resp = types.Part(function_response=types.FunctionResponse(name="transfer_to_agent", response={}))
    assert list(agent.translate(_ev([resp], author="retail_instore"))) == []
    assert list(agent.translate(_ev([types.Part(text="Milk low")], author="stock_scout"))) == []
    assert list(agent.translate(_ev([types.Part(text="Sales are up.")], author="briefing_writer"))) == [{"type": "done", "text": "Sales are up."}]
    unknown = types.Part(function_call=types.FunctionCall(name="transfer_to_agent", args={"agent_name": "nobody"}))
    assert list(agent.translate(_ev([unknown])))[0]["label"] == "Working"
