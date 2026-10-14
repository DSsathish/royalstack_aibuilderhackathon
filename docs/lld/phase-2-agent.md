# LLD: Phase 2 agent core

One Google ADK `LlmAgent` per mode (in-store, online, owner) sharing one tool module and one session service. Tools are plain functions. The UI renders only from tool results, never from model prose.

---

## `app/services/sessions.py`

**Responsibility.** Create and read shopper/owner sessions. Phase 3 adds QR token validation and expiry; phase 2 only needs a session to carry `store_id`, `mode`, `cart_id`.

**Functions.**
- `create(store_id, mode, user_id=None) -> Session` — writes `sessions/{session_id}` with a fresh `cart_id`, `expires_at = now + 4h`.
- `get(session_id) -> Session | None` — returns None when missing or expired.

**Model.** `Session(session_id, store_id, mode, cart_id, user_id, language="auto", aisle_hint=None, created_at, expires_at)`.

**Not in scope.** QR signing (phase 3), WhatsApp phone mapping (phase 5).

---

## `app/services/cart.py`

**Responsibility.** Cart lines and totals. Reserves stock on add, releases on remove. Server computes money.

**Functions.**
- `get(cart_id) -> Cart` — creates an empty cart doc on first read.
- `add(store_id, cart_id, product_id, qty, via) -> Cart | str` — reserves `qty`; returns the cart or an error string (`"out_of_stock"`, `"unknown_product"`, `"item_limit"`).
- `remove(store_id, cart_id, product_id) -> Cart` — releases the line's qty.
- `totals(cart) -> (subtotal, savings, total)` — pure.

**Model.** `Cart(cart_id, store_id, items: list[CartItem], status="open")`, `CartItem(product_id, name, qty, unit_price, mrp, via)`.

**Rule.** `len(items) >= store.self_checkout_item_limit` blocks add in `instore` mode (limit read from the store doc).

**Not in scope.** Checkout, payment, order creation (phase 3).

---

## `app/agent/tools.py`

Plain functions. Each reads `store_id`, `mode`, `cart_id` from `tool_context.state`. Each returns a small dict (≤ 2 KB). Docstrings are the tool descriptions the model sees, so they are written for the model.

| Tool | Modes | Args | Returns |
|---|---|---|---|
| `search_products` | all | `query: str`, `max_results: int = 6` | `{products: [{product_id, name, brand, price, mrp, unit, available, aisle, bay}], signal: found/out_of_stock/not_carried}` |
| `get_product` | all | `product_id` | full view incl. description, tags, substitutes, location |
| `suggest_substitutes` | all | `product_id` | `{products: [...]}` from `substitutes[]` then same subcategory in stock |
| `navigate_to` | instore | `product_id` | `{aisle, bay, shelf, side, x, y, directions: "Aisle 2, bay 3, left side"}` |
| `add_to_cart` | instore, online | `product_id`, `qty: int = 1` | `{ok, error?, cart: {items, subtotal, total, count}}` |
| `remove_from_cart` | instore, online | `product_id` | cart summary |
| `view_cart` | instore, online | – | cart summary |
| `start_checkout` | instore, online | – | `{ok, cart_id, total}` (phase 3 wires payment; phase 2 returns the summary) |
| `get_low_stock` | owner | `limit: int = 20` | `{items: [{product_id, name, available, reorder_point, supplier_id}]}` |

Dropped from the plan: `record_demand_signal` (search already records signals in code) and `identify_product_from_image` (the image is passed inline to the multimodal model, which then calls `search_products`; one less moving part). Owner tools `forecast_demand`, `draft_purchase_order`, `get_anomalies` arrive in phase 6.

`TOOLS_BY_MODE` is the single gating table.

---

## `app/agent/prompts.py`

`CORE` + one block per mode. Core rules: answer only from tool results; never invent stock, price, or location; reply in the user's language (Tamil, Hindi, English); keep replies under 80 words; when an image is attached, identify brand, product, size and call `search_products`; offer the next action.

---

## `app/agent/agent.py`

**Responsibility.** Build the three agents, run a turn, translate events into UI messages.

**Functions.**
- `build(mode) -> LlmAgent` — `model=settings.gemini_flash_model`, `instruction=prompts.for_mode(mode)`, `tools=TOOLS_BY_MODE[mode]`.
- `runner(mode) -> Runner` — cached, `InMemorySessionService` shared across modes.
- `async chat(session: Session, text: str, image: tuple[bytes, str] | None) -> AsyncIterator[dict]` — ensures an ADK session exists with `state={store_id, mode, cart_id, session_id, language}`, runs with `RunConfig(streaming_mode=SSE, max_llm_calls=8)`, yields:
  - `{"type": "status", "tool": name}` when a tool call starts,
  - `{"type": "action", "name": <ui action>, "data": <tool result>}` after a tool result,
  - `{"type": "token", "text": chunk}` for partial text,
  - `{"type": "done", "text": full_reply}`.
- `ACTION_FOR_TOOL = {search_products: "show_products", suggest_substitutes: "show_products", navigate_to: "highlight_map", add_to_cart/remove_from_cart/view_cart: "cart_updated", start_checkout: "checkout_ready", get_low_stock: "show_low_stock"}`.

**Guardrails.** `max_llm_calls=8`. Tools validate `product_id` belongs to `state.store_id` by construction (ids are prefixed with the store id and looked up under that store's collection). Mode gating by construction.

**Audio.** `transcribe(audio_bytes, mime) -> str` in `services/gemini.py`: one Flash call, "transcribe exactly, keep the language". The API then runs a normal text turn with the transcript.

---

## `app/api/agent.py`

| Method | Path | Body | Returns |
|---|---|---|---|
| POST | `/sessions` | `{store_id, mode}` | Session (dev convenience; phase 3 replaces the in-store path with the QR flow) |
| POST | `/agent/chat` | multipart: `session_id`, `message`, optional `image` (≤ 4 MB, image/*) | `text/event-stream` of the events above |
| POST | `/agent/audio` | multipart: `session_id`, `audio` (≤ 4 MB, audio/*) | same stream, first event `{"type":"transcript","text":...}` |

Owner mode sessions require a verified owner (phase 6 wires the token); phase 2 allows owner sessions only when `ENV=test` or `dev`.

---

## Tests

| File | Covers | Needs Gemini |
|---|---|---|
| `test_cart.py` | add reserves, remove releases, totals, item limit, out of stock | no |
| `test_sessions.py` | create, get, expiry | no |
| `test_agent_tools.py` | each tool with a fake `ToolContext` against the emulator; mode gating table | no |
| `test_api_agent.py` | `/sessions`, `/agent/chat` validation (bad session 404, image too big 413) | no |
| `test_agent_live.py` | 8 scripted conversations, asserts tool calls and reply facts; marked `live`, skipped without a key | yes |

---

## Rulings

- Image handled inline by the multimodal model, no upload endpoint, no identify tool. Cost if wrong: add the tool later, one file.
- Session and cart services land in phase 2 (the agent needs them); phase 3 extends them.
- Flash default changed to `gemini-3.5-flash` after listing available models; Pro stays `gemini-2.5-pro` (stable).
- ADK `InMemorySessionService`: one Cloud Run instance for the demo (`max-instances 1`). Firestore-backed sessions only if time allows.

## Live evaluation findings (15 Oct, free-tier AI Studio key)

First live run: 4 of 8 scenarios passed outright. Tamil reply in Tamil with aisle and stock; out-of-stock
almond milk led to `suggest_substitutes`; oat milk declined honestly with alternatives; owner low-stock and
off-topic redirection correct. Fixes from the failures:
- `navigate_to` is now mandatory in the in-store prompt when the shopper asks where something is; the model
  had answered the aisle from search results, which would leave the map unhighlighted.
- `record_demand_signal` reinstated as a tool (reverses the earlier ruling). Keyword search marked "oat milk"
  as found because "milk" matched other products; only the model can judge "asked for X, we do not carry X".
  Automatic signals are now only `not_carried` (zero hits) and `out_of_stock`; agent signals carry `source=agent`.
- Tool status events were emitted twice under streaming (partial + final event); now reported once.
- Retries on 429/503 and `thinking_level=low` on every model call; free-tier capacity is bursty.

Model availability on this key (free tier): 2.5 models return 404, Pro models have no free quota,
`gemini-3.5-flash` is usually 503, `gemini-3-flash-preview` works at ~4 s but is capped at 20 requests before a
long reset, `gemini-3.1-flash-lite` works at ~12 s. Conclusion: the free tier cannot run a tool-calling agent
for a demo. Needs AI Studio prepaid credits or Vertex AI on a billed project. Defaults are env-overridable.
