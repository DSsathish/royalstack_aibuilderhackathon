# LLD: owner agent

A separate agent for the owner's side of the counter. Same runtime (ADK, Gemini, live voice bridge), its own prompt and its own tool set with full access to one store: inventory, sales, forecasts, reorders, customers, points, offers, exit checks, floor map and sync.

## Responsibility
- `app/agent/owner_tools.py`: plain functions over the existing services, one per question or action. Reading tools return rows the dashboard chat renders as a table; `store_snapshot` returns the daily briefing figures.
- `prompts.OWNER_CORE` replaces the shopper prompt for `mode == "owner"`: brief first, act on request, confirm before changing anything.

## Confirmation in code, not in prose
- Every acting tool (`set_reorder_rule`, `adjust_stock`, `update_price`, `move_product`, `create_offer`, `set_offer_active`, `adjust_points`, `approve_purchase_order`) takes `confirm: bool = False`. Without it the tool only returns `needs_confirmation` with a one-sentence plan; the model reads the plan back and asks. With `confirm=true` it acts, writes an audit entry with the owner's uid as actor, and returns what changed. A model cannot change anything in one call.
- `record_shelf_count` and `draft_purchase_order` act directly: counts and drafts change nothing until the owner acts on them.

## Tools
Reading: `store_snapshot`, `find_products(query, status)`, `get_low_stock`, `sales_report(days)`, `forecast_demand`, `reorder_drafts`, `demand_signals(days)`, `customers_overview(segment)`, `list_offers`, `exit_summary(days)`, `sync_status`, `floor_map_summary`, `get_product`, `search_products`.
Acting: the eight above plus `draft_purchase_order` and `record_shelf_count`.
Product arguments accept an id, a SKU, a barcode or a name (resolved through the catalog, any stock level).

## State
- The agent state carries `user_id` (the owner's uid) so audits name the person, not "agent". Live voice gets the same tools through the declaration builder (string, integer, number and boolean arguments only).

## UI
- Chat actions: `show_snapshot` renders the briefing figures; `show_rows` renders any `{columns, rows}` result as a compact table; owner suggestions reflect the new abilities.

## Not in scope
- Rejecting drafts, editing supplier details, staff management, payments and sync secrets stay in the dashboard forms.

## Tests
- `tests/test_owner_agent.py`: snapshot figures, product search by status, every acting tool refuses without `confirm` and acts with it (audit actor is the uid), name resolution, customers by segment, offers create and pause, points by last four digits, sync status, mode gating (no cart tools for owners, no owner tools for shoppers), owner prompt has no shopper rules, live declarations build for every owner tool.
- `tests/test_agent_live.py`: a greeting produces a briefing from `store_snapshot`; "create 10% off dairy" asks for confirmation and creates the offer after "yes".
