"""Agent teams on Google ADK: a coordinator that only routes, specialists that own a slice of the tools, and for the
owner a parallel briefing workflow. Tools, rules and the UI contract are unchanged; this is a routing layer over them.
Design: docs/lld/multi-agent.md."""

from google.adk.agents import LlmAgent, ParallelAgent, SequentialAgent
from google.adk.models.google_llm import Gemini

from app.agent import owner_tools as ot
from app.agent import prompts
from app.agent import tools as t
from app.config import settings
from app.domain.models import Mode
from app.services import gemini

SCOUTS = ("stock_scout", "sales_scout")     # their text is working notes, not an answer

SHOPPER_TOOLS = {
    "catalog_agent": [t.search_products, t.list_category, t.store_overview, t.get_product, t.suggest_substitutes, t.record_demand_signal, t.get_offers, t.product_facts, t.compare_prices],
    "navigation_agent": [t.search_products, t.navigate_to],
    "cart_agent": [t.search_products, t.add_to_cart, t.remove_from_cart, t.view_cart, t.start_checkout],
}
OWNER_TOOLS = {
    "inventory_planner": [ot.stock_report, ot.find_products, t.get_low_stock, t.forecast_demand, ot.reorder_drafts, t.draft_purchase_order,
                          ot.approve_purchase_order, ot.demand_signals, ot.floor_map_summary, t.search_products, t.get_product,
                          ot.set_reorder_rule, ot.adjust_stock, ot.record_shelf_count, ot.update_price, ot.move_product],
    "customers_offers": [ot.customers_overview, ot.list_offers, ot.create_offer, ot.set_offer_active, ot.adjust_points, t.search_products],
    "data_connector": [ot.connect_source, ot.apply_source, ot.connectors_status, ot.sync_status],
    "store_ops": [ot.store_snapshot, ot.sales_report, ot.exit_summary, t.get_anomalies, t.product_facts, t.search_products],
    "stock_scout": [t.get_low_stock, ot.reorder_drafts, ot.demand_signals],
    "sales_scout": [ot.store_snapshot, ot.sales_report, ot.exit_summary],
}


def _llm(name: str, mode: Mode, description: str, focus: str, tools: list, *, output_key: str | None = None,
         leaf: bool = True, sub_agents: list | None = None) -> LlmAgent:
    return LlmAgent(
        name=name, description=description,
        model=Gemini(model=settings.gemini_flash_model, retry_options=gemini.RETRY, client_kwargs=gemini.client_kwargs()),
        generate_content_config=gemini.FAST,
        instruction=lambda ctx, m=mode, f=focus: prompts.agent_instruction(m, dict(ctx.state), f),
        tools=list(tools), sub_agents=list(sub_agents or []), output_key=output_key,
        disallow_transfer_to_parent=leaf,          # a specialist hands over to a teammate, never back up: no ping-pong
    )


def tools_for(mode: Mode, name: str) -> list:
    """The specialist's tools, filtered to what the mode allows (online has no map, in store adds nothing by voice)."""
    allowed = set(t.TOOLS_BY_MODE[mode])
    table = OWNER_TOOLS if mode == "owner" else SHOPPER_TOOLS
    return [fn for fn in table[name] if fn in allowed]


def build_team(mode: Mode) -> LlmAgent:
    if mode == "owner":
        briefing = SequentialAgent(name="briefing", description=prompts.DESCRIPTIONS["briefing"], sub_agents=[
            ParallelAgent(name="briefing_scouts", description="Runs the stock and sales scouts at the same time", sub_agents=[
                _llm("stock_scout", mode, "Collects what is low, drafted and asked for", prompts.FOCUS["stock_scout"], tools_for(mode, "stock_scout"), output_key="stock_notes"),
                _llm("sales_scout", mode, "Collects today's sales, exits and flags", prompts.FOCUS["sales_scout"], tools_for(mode, "sales_scout"), output_key="sales_notes"),
            ]),
            _llm("briefing_writer", mode, "Writes the briefing from the scouts' notes", prompts.FOCUS["briefing_writer"], []),
        ])
        specialists = [briefing] + [_llm(n, mode, prompts.DESCRIPTIONS[n], prompts.FOCUS[n], tools_for(mode, n))
                                    for n in prompts.OWNER_TEAM if n != "briefing"]
    else:
        names = [n for n in prompts.SHOPPER_TEAM if n != "navigation_agent" or mode == "instore"]
        specialists = [_llm(n, mode, prompts.DESCRIPTIONS[n], prompts.FOCUS[n], tools_for(mode, n)) for n in names]
    return _llm(f"retail_{mode}", mode, "Routes every request to the right specialist", prompts.coordinator_focus(mode), [],
                leaf=False, sub_agents=specialists)


def agents_of(root: LlmAgent) -> dict[str, object]:
    """Every agent in the tree by name (for tests and diagnostics)."""
    out: dict[str, object] = {}
    def walk(a):
        out[a.name] = a
        for sub in getattr(a, "sub_agents", []) or []:
            walk(sub)
    walk(root)
    return out
