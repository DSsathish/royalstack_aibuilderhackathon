"""What the screen says while a tool or a teammate works. One map for text chat, live voice and press-to-talk, so the
wording lives here and nowhere in the clients."""

TOOLS = {
    "search_products": "Checking the shelves", "list_category": "Listing the section", "store_overview": "Reading the sections",
    "get_product": "Checking the product", "suggest_substitutes": "Looking for alternatives", "navigate_to": "Finding the aisle",
    "product_facts": "Looking up facts", "record_demand_signal": "Noting your request", "get_offers": "Checking offers",
    "add_to_cart": "Adding to your cart", "remove_from_cart": "Updating your cart", "view_cart": "Opening your cart",
    "start_checkout": "Preparing checkout",
    "store_snapshot": "Pulling today's figures", "stock_report": "Reading the stock report", "find_products": "Searching the inventory",
    "get_low_stock": "Checking stock levels", "sales_report": "Totting up sales", "forecast_demand": "Reading the forecast",
    "reorder_drafts": "Opening the drafts", "draft_purchase_order": "Drafting orders", "approve_purchase_order": "Approving the order",
    "demand_signals": "Reading demand signals", "customers_overview": "Looking at customers", "list_offers": "Listing offers",
    "create_offer": "Creating the offer", "set_offer_active": "Updating the offer", "adjust_points": "Adjusting points",
    "exit_summary": "Checking exits", "get_anomalies": "Checking exits and counts", "sync_status": "Checking the sync",
    "floor_map_summary": "Reading the floor map", "set_reorder_rule": "Updating the reorder rule", "adjust_stock": "Adjusting stock",
    "record_shelf_count": "Recording the count", "update_price": "Updating the price", "move_product": "Moving the product",
    "connect_source": "Reading your data source", "apply_source": "Applying your data", "connectors_status": "Checking your connectors",
}
AGENTS = {
    "catalog_agent": "Finding products", "navigation_agent": "Checking the map", "cart_agent": "Updating your cart",
    "briefing": "Preparing your briefing", "inventory_planner": "Checking stock and forecasts",
    "customers_offers": "Looking at customers and offers", "data_connector": "Checking your data sources",
    "store_ops": "Checking sales and exits",
}
DEFAULT = "Working"


def for_tool(name: str) -> str:
    return TOOLS.get(name, DEFAULT)


def for_agent(name: str) -> str:
    return AGENTS.get(name, DEFAULT)
