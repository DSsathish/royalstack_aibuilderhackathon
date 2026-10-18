# Demo video script (under 3 minutes)

Record on a laptop with the phone screen mirrored (QuickTime or scrcpy) so both views are visible. Speak the lines; the clicks are listed under each beat. Rehearse once with a timer. Total target: 2 minutes 50 seconds.

## Before recording
- Demo store `dailygoods` seeded and forecast job run (`infra/seed/seed.py --embed`, `python -m app.jobs.forecast --store dailygoods`).
- Owner signed in to https://royastacxk-aibuildercup.web.app/owner/ in the laptop browser.
- One offer created in the Offers tab ("Dairy week, 10% off Dairy, everyone") and one targeted at signed-in shoppers ("Members, ₹20 off above ₹300").
- Shopper phone: Chrome, no existing session (open the site once and clear site data). Test number `+91 99999 00001`, code `123456` (Firebase test number, no SMS). Give that shopper 120 points beforehand from the Customers tab ("Adjust", +120, "demo") after one sign-in.
- Entrance QR printed or shown from Connectors → "Show entrance and aisle links"; aisle A3 QR ready.
- A terminal with `python infra/scripts/sync_example.py --store dailygoods --secret <sync secret> --sku <a visible product's sku> --on-hand 2` typed and ready (secret from Connectors → Live sync → Generate secret).
- Exit kiosk open on a tablet or second browser window: https://royastacxk-aibuildercup.web.app/kiosk/ (PIN 1234).

## 0:00 Hook (15 s)
"Small retailers already run on billing software. Shoppers get no help in the aisle, owners guess their reorders, and nothing is connected. Royal Stack is one AI commerce agent and one inventory truth: the same Gemini agent serves the shopper in the store and online, runs the owner's inventory, and syncs with the software the shop already has."
- Show the title slide for two seconds, then the phone.

## 0:15 Shopper in the store (50 s)
- Scan the entrance QR. The welcome sheet appears: tap "Send code", enter 123456. "Sign-in is optional; it unlocks offers, history and points, with only the last four digits ever shown."
- Chat opens with "Hi, Priya" and the offers strip. Tap the orb and say: "Where is atta?" The assistant answers by voice, the map highlights the aisle, and it says "scan it to add".
- Scan the product barcode (Scan tab). The running receipt shows the item and the Dairy or Members discount line. "In store, items only enter the cart by scanning or a confirmed photo, so the exit check compares against what was physically scanned."
- Say: "What offers do I have?" The assistant lists them from the `get_offers` tool.

## 1:05 Checkout, points and exit (35 s)
- Tap Checkout. "Use points": send code, enter 123456, points field shows the maximum. "Spending points needs a fresh verification of the number; the server checks the token's sign-in time."
- Pay (sandbox). Receipt shows discounts, points used, points earned, and the exit QR.
- On the kiosk: scan the exit QR, take the bag photo, verdict "clear" with the seven layers. "Deterministic rules decide; Gemini vision only adjusts confidence and never blocks an exit. Photos are never stored."

## 1:40 Owner (55 s)
- Overview: today's sales, low stock, open flags.
- Inventory: forecast, days of cover (BigQuery ML ARIMA_PLUS, retrained nightly for every store).
- Reorders: open a draft, read one line of the Gemini rationale, approve it.
- Signals: "asked but not carried" from real conversations.
- Customers: segments (new, regular, VIP, at risk), points, the shopper who just paid.
- Offers: create "Weekend rice, ₹15 off each on Rice" and switch to the phone: the offers strip updates on the next load. "Offers apply themselves; the best one wins per item and one per bill."
- Connectors → Live sync: run the terminal command. Refresh the product in the shopper app: stock is 2. "Any billing system that can call a URL stays in sync: signed webhooks in, sale events out, or a published Sheet pulled every fifteen minutes. Every API instance reloads its catalog within two seconds."
- Ask tab, voice: "What is running low?" The owner assistant answers from the same data.

## 2:35 Architecture and close (15 s)
- Architecture slide: Firebase Hosting PWA, Cloud Run API with Google ADK and the Gemini Live bridge, Firestore, BigQuery ML, Vertex AI Gemini 3.5 Flash and Live, Cloud Scheduler, Secret Manager.
- "One canonical layer, many adapters. Two hundred and seventy-one unit tests, every control mapped in docs/security.md. Next: the Shopify adapter and an MCP server so any shopping assistant can talk to a Royal Stack store."

## If something fails live
- Voice: fall back to typing the same question; the tools and answers are identical.
- Phone sign-in: skip it; the demo still shows the store-wide offer and the cart.
- Kiosk camera: skip the photo; the receipt and order layers still clear the exit.
