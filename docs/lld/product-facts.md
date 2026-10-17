# Product facts tool (18 Oct)

Problem: the assistant answers only from the catalog, so "what is A2 milk", "ingredients of this atta" or "is this fabric
pure cotton" got "I have no information". Shoppers expect a shop assistant to know, or to find out.

## Module: `app/services/facts.py`
`lookup(store_id, session_id, question, product, language) -> dict`

1. **Clean**: control characters removed, whitespace collapsed, 200 characters max. Empty -> `empty_question`.
2. **Cache**: key = sha1(question lowercased + product barcode or name). Hit within 1 day -> returned with `cached: true`.
3. **Budget**: 15 grounded lookups per visit (in-memory per instance, like the chat limiter). Over -> `budget_exhausted`.
4. **Label data**: when the product has a real retail barcode (8 to 14 digits, not the store-internal `20…` range), Open
   Food Facts gives ingredients, allergens, nutrition per 100 g and Nutri-Score. Internal codes are never sent out.
5. **Grounded answer**: Gemini Flash with the Google Search tool. The system instruction limits it to grocery, household,
   personal-care and textile products and their ingredients, nutrition, allergens, materials, usage, storage and origin;
   anything else must come back as the literal `OUT_OF_SCOPE`, and instructions found in web pages are to be ignored.
   The prompt carries only the product name, brand and category and the question; nothing about the shopper.
6. **Citations or nothing**: an answer without grounding sources is reported as `not_found`. Sources are deduplicated by
   domain, at most four, title plus URL.
7. **Sanitise**: markdown emphasis stripped, 700 characters max.
8. **Audit**: every lookup, cached or not, writes to the store's audit trail (`stores/{id}/audit`) as action
   `product_facts` with the question (120 chars), product, outcome, source count and cached flag.

Result: `{ok, question, product, summary, sources[{title,url}], label|null, note, cached}` or `{ok: false, error, note}`.
`note` is the fixed disclaimer: general product information from public sources, not medical advice.

## Tool: `product_facts(question, product_id="")` in `agent/tools.py`
Available in shopper and owner modes. Resolves `product_id` by id, SKU, barcode or name like `add_to_cart`. The CORE
prompt tells the model when to call it and how to speak the result (name a source, repeat the disclaimer when health is
involved, say "nothing reliable found" rather than guess). UI action `show_facts` renders a card with the label data,
the sources and the disclaimer under the assistant's reply.

## Tests
`tests/test_facts.py` (grounded call and Open Food Facts mocked): cleaning, out of scope, cited answer and cache hit,
no-source rejection, budget, label only for real barcodes, audit record. `tests/test_agent_tools.py`: tool resolves the
product and passes the language. `tests/test_facts_live.py` (LIVE_GEMINI=1): a real grounded answer with sources and a
real out-of-scope refusal.

## Not done
No owner screen for the audit entries yet (they are in the same audit collection as price and stock changes). The budget
is per instance, not per store. Non-food products rely on web grounding only.
