# Phase 2: Agent Core

Goal: one Google ADK agent with grounded tools, three context modes (in-store, online, owner), multilingual voice and text, multimodal image input. This is the 40% "Technical Merit & Gen AI Implementation" score.
Owner: backend. Estimated time: 6 to 8 hours. Runs in parallel with phase 1 using mocked tools until 1.7 lands.

## 2.1 Agent design

One `LlmAgent` from `google.adk.agents`, model = `GEMINI_FLASH_MODEL`. A single agent with a mode flag beats three agents because tool code and grounding stay shared, and judges can read one clear tool contract.

Session state injected per request:

```python
state = {
  "store_id": "...",
  "mode": "instore" | "online" | "owner",
  "session_id": "...",
  "cart_id": "...",
  "language": "en" | "ta" | "hi" | "auto",
  "aisle_hint": "A3" | None,
}
```

System prompt (`agent/prompts.py`) has a shared core plus a mode block:

- Core: you are the store's assistant, always answer from tool results, never invent stock or prices, reply in the user's language, keep answers short, offer the next action.
- In-store block: mention aisle and shelf, offer to add to cart, remind about self-checkout, never discuss delivery.
- Online block: mention delivery and sizes, never mention aisles, offer to add to cart and checkout.
- Owner block: you talk to the shop owner, use forecast and inventory tools, propose actions but never execute writes without approval.

## 2.2 Tools

Implement in `agent/tools.py` as plain Python functions with typed args and docstrings (ADK uses these as the tool schema). Every tool reads `store_id` and `mode` from `tool_context.state`.

| Tool | Modes | Signature | Backed by |
|---|---|---|---|
| `search_products` | all | `(query: str, max_results: int = 6)` | `services/catalog.search` |
| `get_product` | all | `(product_id: str)` | catalog + inventory + location |
| `get_stock_and_location` | instore, owner | `(product_id: str)` | inventory + location |
| `suggest_substitutes` | all | `(product_id: str)` | `substitutes[]` then same-subcategory in stock |
| `add_to_cart` | instore, online | `(product_id: str, qty: int = 1)` | `services/cart.add` (reserves stock) |
| `remove_from_cart` | instore, online | `(product_id: str)` | `services/cart.remove` |
| `view_cart` | instore, online | `()` | cart |
| `identify_product_from_image` | instore, online | `(image_ref: str)` | Gemini vision + catalog match (2.5) |
| `navigate_to` | instore | `(product_id: str)` | location + floor map, returns path text and map highlight |
| `start_checkout` | instore, online | `()` | `services/checkout.create_intent` |
| `record_demand_signal` | all | `(query: str, matched_product_id: str \| None, type: str)` | demand_signals |
| `forecast_demand` | owner | `(product_id: str \| None, horizon_days: int = 14)` | BigQuery ML (phase 6) |
| `get_low_stock` | owner | `(limit: int = 20)` | inventory where `on_hand <= reorder_point` |
| `draft_purchase_order` | owner | `(supplier_id: str, lines: list[dict], reason: str)` | po_drafts (status draft) |
| `get_anomalies` | owner | `(days: int = 7)` | verification flags + shrink calc (phase 6) |

Rules:
- Tools return small JSON. No tool returns more than ~2 KB.
- Write tools (`add_to_cart`, `draft_purchase_order`) log to `audit`.
- `record_demand_signal` is called by the agent whenever a search returns nothing or only out-of-stock items. Put this instruction in the prompt and also enforce it in code: `search_products` itself writes `not_carried` / `out_of_stock` signals when applicable, so the signal never depends on the model remembering.

## 2.3 Mode gating

Wrap tool registration: build the tool list per request from the mode.

```python
TOOLS_BY_MODE = {
  "instore": [search_products, get_product, get_stock_and_location, suggest_substitutes,
              add_to_cart, remove_from_cart, view_cart, identify_product_from_image,
              navigate_to, start_checkout],
  "online":  [search_products, get_product, suggest_substitutes, add_to_cart,
              remove_from_cart, view_cart, identify_product_from_image, start_checkout],
  "owner":   [search_products, get_product, get_stock_and_location, forecast_demand,
              get_low_stock, draft_purchase_order, get_anomalies],
}
```

## 2.4 Runner and API

`agent/runner.py` wraps `google.adk.runners.Runner` with an in-memory session service keyed by `session_id` (swap for a Firestore-backed session service if time allows; in-memory is fine on a single Cloud Run instance with `--min-instances 1 --max-instances 1` for the demo, or set `--session-affinity`).

Endpoints:

| Method | Path | Purpose |
|---|---|---|
| POST | `/agent/chat` | `{session_id, message, image_ref?, audio_ref?}` → streamed text + structured `actions[]` (product cards, map highlight, cart update) |
| POST | `/agent/audio` | multipart audio (webm/ogg) → Gemini transcribes in the same call, then same as chat |
| GET | `/agent/history/{session_id}` | messages for UI reload |

Streaming: use Server-Sent Events. The UI needs structured side-channel events, so emit two event types: `token` and `action`. Actions come from tool results, not from the model's prose: after each tool call, map the result to a UI action (e.g. `search_products` → `show_products`, `navigate_to` → `highlight_map`, `add_to_cart` → `cart_updated`).

## 2.5 Multimodal

- **Image in chat:** frontend uploads to a `POST /uploads` endpoint which stores in Cloud Storage (or Firestore bytes for tiny images) and returns `image_ref`. `identify_product_from_image` loads the bytes and asks Gemini Flash with the prompt: "Identify the retail product. Return JSON {brand, name, size, category, barcode_if_visible}". Then match against the catalog via `search_products` with the extracted name. Return top 3 candidates with confidence; the UI asks the shopper to confirm one.
- **Audio in:** send the audio blob to Gemini Flash as an audio part with the instruction "Transcribe exactly, keep the original language, output text only". Then run the normal chat turn. Detect language from the transcript and set `state.language`.
- **Audio out:** browser `speechSynthesis` with the language voice if available, falls back to text. (Gemini TTS is a stretch.)

## 2.6 Multilingual

- Prompt core: "Reply in the language the user wrote or spoke in. Product names stay in their catalog form."
- Seed tags include Tamil and Hindi aliases so keyword search works; embeddings handle the rest.
- Quick test set: 10 queries each in English, Tamil, Hindi, in `tests/lang_queries.json`.

## 2.7 Guardrails

- Tool results are the only source of truth for price, stock, location. Prompt says so and tests check that an answer about stock matches the tool output.
- Max 6 tool calls per turn. ADK `max_llm_calls` or a counter in the runner.
- Owner mode never executes writes other than `draft_purchase_order` with status draft.
- Reject off-topic requests briefly and return to shopping.

## 2.8 Evaluation harness

`backend/tests/test_agent_eval.py` with ~20 scripted conversations and assertions on which tools were called and on key facts in the reply:

- "Where is Aashirvaad atta?" → `navigate_to` called, reply contains aisle.
- "Do you have oat milk?" (not carried) → `record_demand_signal(type=not_carried)`, reply suggests substitute.
- "Add 2 packets" after a product card → `add_to_cart(qty=2)`.
- Tamil: "பால் எங்கே இருக்கு" → `navigate_to` for milk, reply in Tamil.
- Owner: "What should I reorder this week?" → `get_low_stock` then `forecast_demand`, reply proposes a draft.

Run in CI with real Gemini calls (cost is small) or mark as `@slow` and run manually before submission.

## Acceptance criteria

- [ ] `/agent/chat` streams a grounded answer with product cards for a search
- [ ] Out-of-stock query returns substitutes and writes a demand signal
- [ ] Image of a product returns the correct catalog item in top 3
- [ ] Tamil voice query answered in Tamil
- [ ] Owner mode cannot call cart tools; in-store mode cannot call forecast
- [ ] Eval harness passes 18 of 20 scenarios

## Risks

- ADK API changes between versions: pin `google-adk` to the version tested on day 1.
- Latency: Flash with 2 to 3 tool calls is 2 to 4 s. Stream tokens so the UI feels alive; show "checking shelf…" status events from tool starts.
- Model hallucinating a cart add without calling the tool: make the UI render cart state only from `cart_updated` actions, never from text.
