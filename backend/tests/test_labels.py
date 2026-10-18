"""Every tool and every teammate has a label the screen can show, from the one map."""
from app.agent import agent, labels, team
from app.agent.tools import TOOLS_BY_MODE


def test_every_tool_and_agent_has_a_label():
    for mode, tools in TOOLS_BY_MODE.items():
        missing = [t.__name__ for t in tools if t.__name__ not in labels.TOOLS]
        assert not missing, (mode, missing)
    for mode in ("instore", "online", "owner"):
        root = agent.build(mode)
        for name in team.agents_of(root):
            if name == root.name or name in team.SCOUTS or name.startswith("briefing_"):
                continue
            assert name in labels.AGENTS, name
    assert labels.for_tool("nope") == labels.for_agent("nope") == "Working"
