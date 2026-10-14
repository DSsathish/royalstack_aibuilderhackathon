# Phase 7: Hardening, Demo, and Submission

Goal: feature freeze at the start of 18 Oct, then make what exists reliable, record the video, write the deck, polish the repo, and submit with hours to spare.
Owner: whole team. Estimated time: full day.

## 7.1 Feature freeze rules

- No new features after 09:00 on 18 Oct. Only fixes, copy, and polish.
- 3D avatar: only if every acceptance checklist in phases 1 to 6 is green by 12:00. Otherwise skip. It is 10% of the score at most and can sink the day.
- Shopify connector and WhatsApp: ship only if already working. Do not debug them on the last day.

## 7.2 Security and reliability checklist

- [ ] All `/owner/*` endpoints verify Firebase ID tokens and store membership.
- [ ] `/jobs/*` endpoints accept only Cloud Scheduler OIDC tokens (`--oidc-service-account-email`).
- [ ] Twilio webhook signature validated. Razorpay signature validated.
- [ ] QR session tokens signed; receipt tokens single-use; sessions expire.
- [ ] No secrets in the repo. `git log -p | grep -i key` sanity check. Secrets in Secret Manager and GitHub secrets only.
- [ ] CORS limited to the Firebase Hosting origin and localhost.
- [ ] Rate limit on `/agent/chat` per session (simple in-memory token bucket) to protect the Gemini budget.
- [ ] Firestore security rules: clients read only their own session, cart, orders; everything else through the API. Owner reads via API only.
- [ ] Cloud Run: `--min-instances 1` for the demo week to avoid cold starts on camera; `--max-instances 3`; `--session-affinity` if sessions are in memory.
- [ ] Structured JSON logging with `session_id` and `store_id`; errors visible in Cloud Logging.
- [ ] Uptime check on `/healthz` in Cloud Monitoring with an email alert.

## 7.3 Testing pass

- Run unit tests, the agent eval harness, and a manual script on two real phones (one Android, one iPhone) plus one laptop.
- Manual script = the demo script below, run three times end to end. Fix anything that fails twice.
- Reset script `infra/scripts/reset_demo.py`: restores seed stock, clears carts, orders, verifications, signals, drafts, so the video can be recorded cleanly and judges get a fresh state. Document how judges can reset (a hidden owner button "Reset demo data" is acceptable).

## 7.4 Demo script (also `docs/demo-script.md`)

Target 2 min 45 s. Record on a phone screen plus a face camera for the in-store part if possible, otherwise screen recordings with voiceover.

| Time | Scene | What is shown |
|---|---|---|
| 0:00 | Problem | 15 s. Self-checkout shrink numbers, big retailers retreating from cashierless hardware, small retailers losing sales to unseen stockouts. One slide. |
| 0:15 | Enter the store | Scan entrance QR, app opens instantly, no install. |
| 0:25 | Ask in Tamil | Voice: "பால் எங்கே இருக்கு". Agent answers in Tamil, map highlights aisle 2. |
| 0:40 | Walk and scan | Scan milk barcode, running receipt updates. Ask for "oat milk", agent says not carried, suggests soya milk, adds it. |
| 1:00 | Vision scan | Photo of ghee tin with hidden barcode, agent identifies it, add. |
| 1:10 | Self-checkout | Pay in sandbox, exit QR shown. Item limit visible in settings. |
| 1:25 | Exit verification | Kiosk scans QR, bag photo, amber "please show the ghee tin", staff clears. Show the "not stored" notice. |
| 1:40 | Owner dashboard | The sale appears, milk stock dropped, "oat milk" in demand signals, reorder draft with Gemini rationale, approve it. |
| 2:05 | Online | Same agent on the retailer's website via the widget, product now shows out of stock because the last unit sold in store. WhatsApp message gets a product and a payment link (if built). |
| 2:25 | Architecture | 10 s. Gemini, ADK, Cloud Run, Firestore, BigQuery ML, Firebase. |
| 2:35 | Close | One sentence: one agent, one inventory truth, physical and digital, on the software retailers already use. |

Recording tips: record each scene separately, stitch in CapCut or iMovie, add captions for the Tamil parts, keep the Google Cloud services on screen in the architecture scene, upload to YouTube as unlisted, test the link in an incognito window.

## 7.5 Deck (PDF, 10 to 12 slides)

1. Title, team, theme.
2. Problem: shrink and stockout figures with sources (ECR Retail Loss 2026 report, Amazon and Walmart retreats, Redseer on kirana digitization).
3. Who we serve: small and mid retailers with a physical store and an online channel.
4. Solution overview: one agent, one inventory truth, three faces (in-store, online, owner).
5. In-store experience: QR, agent, navigation, scan, running receipt, self-checkout.
6. Layered exit verification: the seven layers, vision as confidence, privacy, honest limits.
7. Owner intelligence: forecasting, reorder approvals, demand signals from conversations, loss dashboard.
8. Digital: storefront, widget on any site, WhatsApp. Compatibility path with Google's commerce protocol.
9. Architecture on Google Cloud: diagram with Gemini Flash and Pro, ADK, Cloud Run, Firestore, BigQuery ML, Firebase Auth and Hosting, Scheduler, Pub/Sub, Secret Manager.
10. Gen AI implementation details: tool contract, mode gating, grounding guarantees, eval harness results, multimodal and multilingual.
11. What is different: comparison table vs Guitar Center QR assistant, Sam's Club exit AI, Shopify Sidekick, scan-and-go apps. Only ours combines all for small retailers.
12. Impact and next steps: pilot plan, metrics to track (flag rate, stockout rate, lost sales recovered), roadmap (Shopify write-back, UCP feed, 3D assistant).

Export to PDF. Keep text short; judges skim.

## 7.6 Repository polish

- `README.md`: one-paragraph pitch, architecture diagram image, live links (app, owner demo login, widget demo page, kiosk), how to run locally, how to deploy, env variables table, Google Cloud services used, team, license (MIT or Apache-2.0).
- `docs/architecture.md`: sequence diagrams for chat turn, checkout, exit verification, forecast job (Mermaid).
- Demo credentials for judges: owner demo account (Google sign-in whitelist or an email+password demo user), kiosk PIN, test card details, in the README under "For judges".
- Remove dead code, run formatters (`ruff`, `prettier`), make CI green.
- Tag `v1.0-submission`.

## 7.7 Submission checklist (Hack2skill portal)

- [ ] Live deployed link: the Firebase Hosting URL, verified in incognito on a phone
- [ ] Demo video under 3 minutes, public or unlisted YouTube link, verified in incognito
- [ ] Public GitHub repo link, verified logged out
- [ ] PDF deck uploaded
- [ ] Theme selected: Retail & Commerce
- [ ] Team members and details match registration
- [ ] Submitted before the portal deadline on 18 Oct, with at least 3 hours of buffer

## 7.8 After submission

- Keep Cloud Run and Firebase running through 6 Nov (evaluation window). Set a billing alert at a sane amount.
- Do not push breaking changes to `main` during evaluation. Use a branch.
- Prepare a 5-minute live demo version of the script for the Grand Finale if shortlisted (announced 7 Nov).
