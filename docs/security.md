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
| Agent: max 8 model calls per turn; tools are the only source of truth for stock, price, location (prompt + UI renders only from tool results) | `agent/agent.py::MAX_LLM_CALLS`, `agent/prompts.py::CORE`, `frontend/components/Chat.tsx` | `test_agent_live.py` (grounding scenarios) |
| Live voice: one socket per session, 15 min maximum, audio frames > 32 KB dropped, malformed JSON ignored, errors surfaced then closed | `agent/live.py` (`MAX_SESSION_S`, `MAX_AUDIO_FRAME`, `_active`) | `test_live.py` |
| Default QR signing key refused outside dev/test (deploy without the secret fails fast) | `config.py::_no_default_key_outside_dev` | `test_config.py` |
| CORS limited to the hosting origins and localhost | Cloud Run env `CORS_ORIGINS`, `main.py` | verified by curl preflight on 15 Oct |

## Secrets and data handling

| Control | Implementation | Test |
|---|---|---|
| Secrets in Secret Manager mounted as env (`QR_SESSION_SIGNING_KEY`, `JOB_KEY`); `.env` git-ignored and excluded from Cloud Build uploads | `backend/.gcloudignore`, root `.gitignore` | *console* |
| Bag photos processed in memory only; stored fields are verdict, confidence, item names and a SHA-256 of the bytes | `services/verification.py::verify_exit` (`image_hash`) | `test_verification.py::test_vision_low_confidence_flags`, `test_api_exit.py::test_verify_with_bag_image` |
| Audit trail for imports, settings changes, purchase-order decisions | `stores/{id}/audit` writes in `api/owner_import.py`, `api/owner.py`, `services/reorder.py` | `test_api_owner_import.py::test_import_writes_audit`, `test_reorder.py::test_approve_and_reject` |
| Runtime service account has only the roles it needs (Firestore user, BigQuery data editor/job user, Vertex user, secret accessor, Pub/Sub publisher, log writer) | `docs/plan/01-phase-0-setup.md`, created 15 Oct | *console* |
| BigQuery queries parameterised; the ARIMA model is per store | `services/insights.py::daily_revenue_history`, `jobs/forecast.py::_param`, `_model` | reviewed; job run 16 Oct |
| Dependencies pinned (`requirements.txt`, `package-lock.json`); CI runs the full backend suite under the Firestore emulator plus frontend tests, lint and build | `.github/workflows/ci.yml` | CI |

## Known gaps (deliberate for the hackathon)

- No rate limit on `/agent/chat` beyond the per-turn call cap. Add a per-session token bucket before any public pilot.
- Cart `add` is read-modify-write outside a transaction; a simultaneous add from chat and scan could drop a line.
- Owner membership is not revoked when an email is removed from `owner_emails`.
- Firebase web API key should be restricted by HTTP referrer in the Google Cloud console, and only the Google provider should be enabled in Firebase Auth (*console*).
- Verification records are kept indefinitely; the 90-day retention job from the plan is not implemented.
