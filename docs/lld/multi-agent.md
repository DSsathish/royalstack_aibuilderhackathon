# Multi-agent design (18 Oct)

## Goal and non-goals
Turn the two single agents (shopper, owner) into coordinated teams of specialists on Google ADK, without changing any
tool, rule, guardrail or UI contract. Non-goals: new capabilities, changes to the live-voice bridge, changes to memory.
Every tool function, the `TOOLS_BY_MODE` lists, `ACTION_FOR_TOOL`, the prompt rules and the confirm-before-acting
pattern stay exactly as they are; the teams are a routing layer over them.

## Topology
```
Shopper coordinator (no tools; routes, greets, redirects off-topic)
  ├─ catalog_agent       find products, stock, prices, sizes, alternatives, offers, product facts
  ├─ navigation_agent    in store only: where a product is, lights the map
  └─ cart_agent          add (online), remove, view cart, start checkout
Owner coordinator (no tools)
  ├─ briefing            SequentialAgent[ ParallelAgent[stock_scout, sales_scout] → briefing_writer ]
  ├─ inventory_planner   stock, forecasts, reorder drafts and approvals, rules, prices, placement, floor map
  ├─ customers_offers    segments, offers, points
  ├─ data_connector      sheets and API feeds in step, sync status
  └─ store_ops           sales reports, exit checks, anomalies, product facts
Agent-tools (a Gemini run inside a tool, used by specialists): product_facts (grounded research),
connect_source / apply_source (the normalizer agent proposes the mapping).
```
- Routing is ADK agent transfer: the coordinator has sub-agents and no tools, so its only move is to delegate (or to
  answer a greeting). Specialists may transfer to a peer (a multi-intent turn: "where is atta, add two") but not back
  to the parent, which prevents ping-pong. Each text turn starts at the coordinator because a fresh ADK session is
  created per turn (memory of record stays the Firestore conversation).
- The briefing is a workflow: two scouts run in parallel (stock: low stock, drafts, signals; sales: snapshot, sales,
  exits), each writes its findings to session state (`output_key`), and a writer with no tools composes the briefing.
  Their tool results stream to the UI as today (snapshot card, low-stock list).
- Instructions: every agent composes its own instruction from the same parts: the shared block (identity, the rules,
  the "how to talk" block, store and customer blocks, the conversation so far), its own focus (what it handles, which
  teammate handles the rest), and the language rule last, so it stays the last thing the model reads. (ADK's
  `global_instruction` is deprecated in this version, so nothing relies on it.)
- Scouts' interim text is not streamed to the UI (only their tool results are); the writer's text is the briefing.

## Contracts that do not change
- Tool functions and their gating (`TOOLS_BY_MODE`), the live-voice bridge (declarations and dispatch read the flat
  lists; voice latency unchanged), `ACTION_FOR_TOOL` and the UI's action handling, conversation memory, rate limits.
- The event translation adds one mapping: a `transfer_to_agent` call becomes a `status` with the target's label
  ("Finding products", "Checking the map", "Updating your cart", "Preparing your briefing"); its response is not an action.
- `MAX_LLM_CALLS` rises from 8 to 12: a turn now spends one call on routing before the specialist's tool loop.

## Impact analysis
- Text turns: one extra model call, about 0.7 to 1.5 s, before the specialist answers. Voice: none.
- Behaviour risk: a coordinator that answers instead of delegating (mitigated: no tools, explicit routing rules, live
  tests assert tool use), a specialist lacking a tool for a follow-up (mitigated: every turn re-routes from the root;
  specialists share the resolver `search_products`), transfer loops (mitigated: no transfer to parent, call cap).
- Rollback: `build(mode)` returns the team root; the old single agent is one line away (`single(mode)`), kept for
  comparison and tests.

## Tests
- Unit: the union of specialist tools equals `TOOLS_BY_MODE[mode]`; coordinators have no tools and non-empty
  descriptions; specialists cannot transfer to the parent; instruction composition keeps the language rule last;
  translate maps transfers to status labels and emits no action for them.
- Live (`LIVE_GEMINI=1`): the existing scenarios (where is atta → navigate; Tamil; out of stock; not carried; add to
  cart; online never navigates; owner low stock; off topic; packs; owner briefing with confirmed offer; language switch)
  now run through the teams, plus a multi-intent turn that crosses two specialists.
