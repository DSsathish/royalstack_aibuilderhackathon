# Providers over MCP (18 Oct)

What exists outside: Swiggy Instamart has an official MCP server (production access whitelist-only; staging after an
application); Zepto has no official API, only unofficial third-party servers; Meesho's API is partner-gated. So Royal
Stack speaks MCP generically, hosts a clearly labelled demo provider so the flows can be shown today, and never presents
sample numbers as live prices.

## MCP servers hosted by Royal Stack (`app/mcp/`, routes in `api/mcp.py`)
A small Streamable-HTTP JSON-RPC server (`initialize`, `ping`, `tools/list`, `tools/call`; notifications get 202;
batches allowed; stateless; GET and DELETE answer 405). Two tool sets:
- `/mcp/stores/{store_id}`: the store's own public catalog for any MCP client (Claude, ChatGPT, another shop's agent):
  `store_info`, `search_products`, `get_product`, `list_category`. Read-only, public fields only (no cost, GST, flags).
- `/mcp/demo/kirana-hub`: "Kirana Hub (demo data)", about sixty everyday items with sample prices and stock, every item
  marked `demo: true`. Tools `search_products`, `list_products`, `get_product`.

## MCP source in the connector agent (`connectors/mcp_client.py`, `services/connectors.py`)
- `MCPClient`: initialize (keeps `Mcp-Session-Id` when the server issues one), list tools, call a tool, and turn the
  result (`structuredContent` or a JSON text block) into records. Same network guards as the API source: https or a
  public host only, size cap, timeouts. The token is sent as the Authorization header and stored in Secret Manager.
- Source kind `mcp`: URL, token, the tool that lists the catalog (`table` holds the tool name). Records go through the
  same propose-mapping, preview and confirm flow as a sheet or an API, and the saved connector pulls on the 15-minute
  job like the others. "List tools" shows what the server offers before any import.
- A saved MCP connector can be marked for price comparison, with the search tool to use (`search_products` by default).

## Comparison (`services/providers.py`)
`compare(store, product)`: the demo provider (in process) plus every saved MCP connector marked for comparison, each
asked for the product by name with an 8-second limit. Matching: barcode first, then name-token overlap. Each row says
`provider`, `label`, `demo`, and `status` (ok, no_match, unavailable), with name, price, MRP, stock and the fetch time
when ok. Ten-minute cache per product per API instance. Surfaces: the product sheet's "Compare" section (session
required) and the assistant's `compare_prices` tool, which renders as a table with the demo rows labelled.

## Owner: Integrations tab
The Connectors tab is now "Integrations": the MCP source joins file, sheet, API and database; status, last run and
errors show as before; remove disconnects; the token never comes back to the browser.

## Tests
`tests/test_mcp.py`: the store server answers initialize, tools and a search; the demo provider labels its data; an MCP
connector is inspected, imported and saved through the owner endpoints against the demo server; comparison returns a
demo row and marks an unreachable provider unavailable.
