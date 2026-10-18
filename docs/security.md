# Security controls: what exists, where it lives, how it is tested

Companion to `hld.md` section 3. Every row is implemented in the code path named and covered by the test named. Rows marked *console* are settings in the Google Cloud or Firebase console rather than code.

## Identity and sessions

| Control | Implementation | Test |
|---|---|---|
| Shopper credential is an unguessable 128-bit session id, 4 h expiry | `services/sessions.py` (`uuid4().hex`, `TTL`) | `test_sessions.py` |
| In-store sessions only from a signed entrance QR; HMAC-SHA256 over `{kind, store_id}`; token for another store refused | `services/qr.py`, `api/shop.py::enter_store` | `test_qr.py`, `test_api_shop.py::test_token_for_other_store_401` |
| The dev `/sessions` endpoint cannot mint in-store sessions; owner sessions only in dev/test | `api/agent.py::create_session` | `test_api_agent.py::test_dev_sessions_endpoint_cannot_mint_instore` |
| Owner identity: Firebase ID token verified server-side; uid from `sub`; email used only when `email_verified` | `services/auth.py::current_uid`, `verify_id_token` | `test_api_owner_import.py::test_bearer_token_uid_comes_from_sub`, `::test_unverified_email_does_not_bootstrap` |
| Owner membership: `users/{uid}.stores`, or bootstrap from `stores/{id}.owner_emails` on first verified sign-in | `services/auth.py::owned_stores`, `require_owner` | `test_api_owner.py::test_owner_by_email_is_bootstrapped` |
| Shopper identity is optional; a phone sign-in token is required for `/sessions/{id}/link` and every `/me/*` route, Google tokens get 403 | `services/auth.py::require_phone`, `api/me.py` | `test_api_me.py::test_link_requires_phone_token`, `::test_guest_session_has_no_customer` |
| Only the last four digits of the phone number are stored; owners see name, spend and preferences, never the number or conversations | `services/customers.py::link`, `api/owner.py::customers_list` | `test_api_me.py::test_link_session_creates_customer_and_marks_orders`, `::test_owner_customers_listing` |
| Self-service export and delete; delete anonymises orders and open sessions, removes turns and profiles, writes an audit entry | `services/customers.py::export`, `delete` | `test_api_me.py::test_export_and_delete` |
| Past receipts open only for the paying visit or a later visit linked to the same shopper | `api/shop.py::get_order` | `test_api_me.py::test_signed_in_shopper_reopens_old_receipts` |
| Profile fields bounded (name 60, lists 8/12/30 entries of 32 chars, enumerated language and substitution) | `api/me.py::ProfilePatch` | `test_api_me.py::test_profile_patch_and_assistant_block` |
| Points move only through the ledger inside transactions: earn at confirm, redeem after a phone verification not older than ten minutes by the linked shopper, owner adjustments with a reason and audit, expiry and stale-hold release by the nightly job; balances never go below zero | `services/points.py`, `api/shop.py::checkout_intent`, `services/auth.py::require_recent_phone`, `api/owner.py::adjust_points` | `test_points.py`, `test_api_offers.py::test_redeem_requires_fresh_matching_phone_token`, `::test_owner_points_adjust_and_me_points` |
| Offers are owner-only writes with bounded values (percent 1 to 90, one value type, names 60 chars) and audit entries; segment-targeted offers are never listed or applied for shoppers outside the segment | `domain/models.py::Offer`, `api/owner.py` offers routes, `services/offers.py::applicable` | `test_api_offers.py::test_owner_crud_and_audit`, `test_offers.py::test_segment_dates_and_active_gate_offers` |
| Scheduled jobs (`/jobs/forecast`, `/jobs/customers`) accept only the shared job key from Cloud Scheduler | `api/owner.py::_job_key` | `test_jobs_customers.py` |
| Inbound sync calls are HMAC-SHA256 signed over timestamp and body with a per-store secret from Secret Manager, refused when older than five minutes, replayed event ids are ignored, bodies capped at 1 MB and 5,000 rows; the pull endpoint needs the secret as a bearer | `api/sync.py`, `services/sync.py::verify`, `seen` | `test_sync.py::test_bad_signature_stale_timestamp_and_missing_secret_are_rejected`, `::test_inventory_webhook_sets_stock_keeps_reservations_and_dedupes` |
| Outbound sale events are signed the same way and only sent to https URLs the owner saved; failures queue in the outbox with backoff and give up after six attempts | `services/sync.py::deliver`, `retry_outbox`, `api/owner_sync.py::_https` | `test_sync.py::test_sale_webhook_is_signed_queued_on_failure_and_retried`, `::test_owner_sync_settings_secret_log_and_public_store` |
| Sync secrets are generated server-side (32 random bytes), shown once, rotated with an audit entry, never returned by any read endpoint; the public store document hides sync settings | `services/sync.py::new_secret`, `api/owner_sync.py::rotate_secret`, `api/catalog.py` | `test_sync.py::test_owner_sync_settings_secret_log_and_public_store` |
| Order confirmation flips pending to paid inside a transaction, so concurrent confirms commit stock, points and visits once; points releases are create-once ledger entries | `services/checkout.py::_claim`, `services/points.py::_move(once=True)` | `test_points.py::test_concurrent_confirms_apply_side_effects_once`, `::test_release_credits_an_order_once_even_when_racing` |
| Deleting a shopper account also deletes the points ledger and the per-store conversation turns, and sign-out unlinks the visit | `services/customers.py::delete`, `unlink`, `api/me.py::unlink` | `test_api_me.py::test_export_and_delete`, `::test_unlink_makes_the_visit_anonymous_again` |
| Product rows from the sync webhook pass the CSV connector's bounds (no negatives, parsed numbers); a failed apply is not recorded as processed; feed redirects must stay on https | `connectors/csv_connector.py::from_record`, `api/sync.py::_failed`, `services/sync.py::_fetch_https` | `test_sync.py::test_products_webhook_applies_csv_bounds`, `::test_failed_apply_is_not_remembered_as_processed`, `::test_feed_redirect_off_https_is_refused` |
| Owner and staff sign in with Google or with email and password (Firebase Auth; passwords never reach the API). A password account must verify its address before the API records the email, so an unverified account can neither register a store nor be bootstrapped into one; verification and reset emails are sent by Firebase | `services/auth.py::current_uid` (email only when `email_verified`), `verified_email`; `frontend/lib/firebase.ts`, `OwnerSignIn`, `VerifyEmail` in `frontend/app/owner/page.tsx` | `test_api_register.py::test_register_requires_verified_email`, `test_api_owner_import.py::test_unverified_email_does_not_bootstrap` |
| The owner agent cannot change anything in one call: every acting tool (stock, prices, reorder rules, points, offers, order approval) returns a plan unless `confirm=true`, which the model may set only after the owner agreed; each act writes an audit entry with the owner's uid as actor | `app/agent/owner_tools.py`, `prompts.OWNER_CORE` | `test_owner_agent.py::test_acting_tools_plan_first_then_act_with_audit`, `test_agent_live.py::test_owner_briefing_and_confirmed_offer` |
| Connector agent: links must be https and resolve to public addresses, re-checked at every redirect hop (no loopback, private, link-local or metadata ranges); database access read-only (SELECT on a table the database lists, row cap, read-only transaction), only postgresql/mysql schemes, same address check on the host; API auth headers and connection strings stored only in Secret Manager and never returned by the API; files capped at 10 MB and 20,000 rows by extension; mappings validated against the field list and the source's real columns; owner-only endpoints; every inspect, apply, save, run and removal audited with counts only | `services/connectors.py`, `api/owner_connectors.py` | `test_connectors.py`, `test_api_connectors.py` |
| Owner chat connector tools inspect only; `apply_source` writes only with `confirm=True`; files and database credentials never pass through chat | `agent/owner_tools.py` | `test_owner_agent.py` |
| Shoppers' and owners' spoken turns are kept as voice notes in the browser only (object URLs, gone on close); nothing is uploaded or stored server-side; a replayed note is muted from the live uplink | `lib/voiceClip.ts`, `lib/live.ts`, `components/VoiceNote.tsx` | `voiceClip.test.ts` |
| Agent teams: coordinators have no tools and can only delegate; each specialist's tools are a subset of the mode's gated list (`TOOLS_BY_MODE`), so routing cannot widen access; acting owner tools keep confirm-before-act; specialists cannot transfer back to the parent; `max_llm_calls` caps a turn | `agent/team.py`, `agent/agent.py` | `test_team.py` |
| Embedding fallback: query and document embeddings try the project's Vertex region, then the global endpoint, then the Gemini API with `GEMINI_API_KEY` from Secret Manager; the key serves no other call while Vertex is on; only the text being embedded leaves the system; vectors from all three are identical (same model) | `services/gemini.py::embed_endpoints` | `test_search_resilience.py` |
| Product facts tool: question cleaned and capped at 200 chars; grounded model restricted to product topics (literal OUT_OF_SCOPE otherwise) and told to ignore instructions in web pages; answers without citations rejected; only product name, brand, category and the question leave the system; store-internal barcodes never sent out; 15 lookups per visit; 1-day cache; output stripped of markup and capped; every lookup audited | `services/facts.py`, `agent/tools.py::product_facts` | `test_facts.py` |
| Live websocket, push-to-talk and profile `language` values validated against the language table (`languages.CODE_PATTERN`); transcriber markers stripped from transcripts; echo turns are not persisted; cut-off replies are marked, so memory never claims unsaid words | `api/agent.py::live_voice`, `agent/live.py::TurnRecorder` | `test_live.py` recorder and config tests |
| The live voice bridge can use a Gemini API (AI Studio) key for newer live models; the key lives in Secret Manager (`GEMINI_LIVE_API_KEY`), is used only for live sessions, and the client is pinned to AI Studio so the Vertex environment flag cannot redirect it | `services/gemini.py::live_client`, `config.py` | `test_live.py::test_live_client_prefers_ai_studio_when_a_live_key_is_set` |
| Owner chat sessions only through the authenticated owner endpoint | `api/owner.py::owner_session` | `test_api_owner.py::test_owner_session_endpoint` |
| `X-Test-Uid` shortcut active only when `ENV=test` | `services/auth.py::current_uid` | implicit in every owner test; Dockerfile sets no ENV, Cloud Run sets `ENV=demo` |

## Authorisation and tenancy

| Control | Implementation | Test |
|---|---|---|
| Carts and orders reachable only with the owning session id (`X-Session-Id`), 403 otherwise | `api/shop.py::_own_cart`, `get_order` | `test_api_shop.py::test_cart_requires_owning_session`, `::test_confirm_wrong_session_403` |
| Every owner endpoint calls `require_owner(store_id)`; all data paths are nested under `stores/{store_id}` | `api/owner.py`, `api/owner_import.py`, `api/exit.py::owner_verifications`, `services/db.py` | `test_api_owner.py::test_all_owner_endpoints_require_auth` |
| Agent tools are gated by session mode (owner tools never visible to shoppers and vice versa) | `agent/tools.py::TOOLS_BY_MODE`, `agent/live.py::declarations` | `test_agent_tools.py::test_mode_gating_table`, `test_live.py::test_dispatch_mode_gated` |
| Kiosk endpoints need the store's PIN; constant-time compare; 5 failures lock the store for 60 s | `api/exit.py::kiosk_auth` | `test_api_exit.py::test_verify_requires_pin`, `::test_pin_lockout_after_repeated_failures` |
| Kiosk PIN and audit rate never returned by the public store endpoint | `api/catalog.py` (`response_model_exclude`) | `test_api_catalog.py::test_public_store_hides_kiosk_pin_and_audit_rate` |
| Scheduled jobs need the `JOB_KEY` secret (`X-Job-Key`, constant-time) | `api/owner.py::forecast_job` | `test_api_owner.py::test_forecast_job_requires_key` |
| Firestore client SDK access denied entirely; all data access goes through the API | `firestore.rules` (deployed) | *console* |

## Money and stock integrity

| Control | Implementation | Test |
|---|---|---|
| Totals computed from the server-side cart, never from the client | `services/cart.py::totals`, `services/checkout.py::intent` | `test_checkout.py::test_intent_creates_pending_order_with_server_totals` |
| Stock reserved in Firestore transactions; concurrent reserve of the last unit yields one winner | `services/inventory.py` | `test_inventory.py::test_concurrent_reserve_of_last_unit_only_one_wins` |
| Payment confirmation verifies an HMAC signature (Razorpay) or the mock signature; mock refused in prod | `services/checkout.py::confirm`, `razorpay_signature_ok` | `test_checkout.py::test_confirm_bad_signature_rejected`, `::test_razorpay_signature_check` |
| A cart cannot be paid twice; confirm is idempotent for the same order | `services/checkout.py::confirm` (cart status check) | `test_checkout.py::test_second_intent_cannot_double_commit`, `::test_confirm_is_idempotent` |
| Receipt token signed, 30 min expiry, bound to order id and item count | `services/qr.py::receipt_token` | `test_qr.py::test_receipt_token_carries_order_and_expires` |
| Receipt is single-use: the order is claimed in a transaction before the slow vision call | `services/verification.py::_claim` | `test_verification.py::test_concurrent_exits_on_one_receipt_only_one_clears`, `::test_receipt_is_single_use` |
| Deterministic exit layers decide; vision only adjusts confidence and can never block an exit | `services/verification.py::verify_exit`, `services/vision.py` | `test_verification.py::test_vision_failure_does_not_block` |
| Purchase orders need an explicit owner approval; approve/reject are one-shot; every decision audited | `services/reorder.py::approve`, `reject` | `test_reorder.py::test_approve_and_reject`, `::test_approve_twice_is_rejected` |
| Manual reorder point is a floor; `reorder_qty = 0` disables reordering; no duplicate drafts per supplier | `services/reorder.py::candidates`, `draft` | `test_reorder.py::test_manual_reorder_point_is_a_floor_and_zero_qty_disables`, `::test_draft_skips_suppliers_with_an_open_draft` |

## Input validation and abuse limits

| Control | Implementation | Test |
|---|---|---|
| Path and body ids validated by regex (`store_id`, `product_id`, hex session/cart/order/po ids); barcode `^[0-9]{8,14}$`; query ≤ 200 chars | `services/auth.py::STORE_ID`, `api/shop.py::HEX_ID`, `api/catalog.py`, `api/owner.py` | `test_api_catalog.py::test_barcode_validation`, `test_api_shop.py::test_malformed_ids_are_4xx_not_500` |
| Uploads: content type must be `image/*` or `audio/*`, ≤ 4 MB | `api/agent.py::_read_upload` | `test_api_agent.py::test_chat_image_too_large_is_413`, `::test_chat_rejects_non_image_upload` |
| CSV import ≤ 5 MB and ≤ 10 000 rows, printable headers only, numeric fields parsed as `Decimal` after stripping currency and unit text (no negatives, no infinities), bad encoding → 400 | `connectors/csv_connector.py::parse`, `_num` | `test_csv_connector.py`, `test_normalizer.py::test_num_cleaning` |
| Normalizer sees only the header and up to 5 sample rows, never the bulk file; its mapping is validated against the real header and unknown fields are dropped; owner-only endpoint, audited | `connectors/normalizer.py::propose`, `api/owner_import.py::propose_mapping` | `test_normalizer.py::test_model_proposal_is_validated`, `test_api_owner_import.py::test_propose_endpoint` |
| Rate limits: 20 agent turns per session per minute (`/agent/chat`, `/agent/audio`), 30 session creations per client address per minute (`/sessions`, `/sessions/instore`); 429 beyond | `services/ratelimit.py`, `api/agent.py::limit_chat`, `limit_sessions` | `test_ratelimit.py`, `test_api_agent.py::test_chat_is_rate_limited_per_session`, `::test_session_creation_is_rate_limited_per_client` |
| Agent: max 8 model calls per turn; tools are the only source of truth for stock, price, location (prompt + UI renders only from tool results) | `agent/agent.py::MAX_LLM_CALLS`, `agent/prompts.py::CORE`, `frontend/components/Chat.tsx` | `test_agent_live.py` (grounding scenarios) |
| Live voice: one socket per session, 15 min maximum, audio frames > 32 KB dropped, malformed JSON ignored, errors surfaced then closed | `agent/live.py` (`MAX_SESSION_S`, `MAX_AUDIO_FRAME`, `_active`) | `test_live.py` |
| Default QR signing key refused outside dev/test (deploy without the secret fails fast) | `config.py::_no_default_key_outside_dev` | `test_config.py` |
| CORS limited to the hosting origins and localhost | Cloud Run env `CORS_ORIGINS`, `main.py` | verified by curl preflight on 15 Oct |

## Secrets and data handling

| Control | Implementation | Test |
|---|---|---|
| Secrets in Secret Manager mounted as env (`QR_SESSION_SIGNING_KEY`, `JOB_KEY`); `.env` git-ignored and excluded from Cloud Build uploads | `backend/.gcloudignore`, root `.gitignore` | *console* |
| Conversation memory stores text turns only (no audio), 600 chars per turn, keyed by the anonymous session for shoppers and by the owner's uid for owners; shoppers' memory is unreachable after the 4 h session expires because the key is never reissued | `services/conversation.py` | `test_conversation.py` |
| Bag photos processed in memory only; stored fields are verdict, confidence, item names and a SHA-256 of the bytes | `services/verification.py::verify_exit` (`image_hash`) | `test_verification.py::test_vision_low_confidence_flags`, `test_api_exit.py::test_verify_with_bag_image` |
| Audit trail for imports, settings changes, purchase-order decisions | `stores/{id}/audit` writes in `api/owner_import.py`, `api/owner.py`, `services/reorder.py` | `test_api_owner_import.py::test_import_writes_audit`, `test_reorder.py::test_approve_and_reject` |
| Runtime service account has only the roles it needs (Firestore user, BigQuery data editor/job user, Vertex user, secret accessor, Pub/Sub publisher, log writer) | `docs/plan/01-phase-0-setup.md`, created 15 Oct | *console* |
| BigQuery queries parameterised; the ARIMA model is per store | `services/insights.py::daily_revenue_history`, `jobs/forecast.py::_param`, `_model` | reviewed; job run 16 Oct |
| Dependencies pinned (`requirements.txt`, `package-lock.json`); CI runs the full backend suite under the Firestore emulator plus frontend tests, lint and build | `.github/workflows/ci.yml` | CI |

## Known gaps (deliberate for the hackathon)

- Cart `add` is read-modify-write outside a transaction; a simultaneous add from chat and scan could drop a line.
- Owner membership is not revoked when an email is removed from `owner_emails`.
- Firebase web API key should be restricted by HTTP referrer in the Google Cloud console, and only the Google, Email/Password and Phone providers should be enabled in Firebase Auth (*console*; phone enabled 17 Oct with three test numbers that never send SMS, email/password enabled 17 Oct).
- Verification records and conversation turns are kept indefinitely; the 90-day retention job from the plan is not implemented.
- Sync signatures bind the timestamp and body but not the path: a captured inventory body could be replayed to the products endpoint within five minutes (it fails row validation there, so nothing changes). Binding the path is a contract change for integrators, deferred.
- A payment captured for an order that a later checkout attempt on the same cart cancelled (two tabs) is not refunded automatically; the order shows as cancelled and the owner refunds in the gateway.
- Per-process maps of verified emails, phone numbers and sign-in times hold one entry per user for the life of the instance.
