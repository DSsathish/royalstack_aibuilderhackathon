# Roadmap after submission: self-service shops, sync, identity, offers and rewards

Decisions recorded 17 Oct 2026 with the owner. Everything here is post-submission work; the submitted prototype stays as it is. Order follows dependency, not preference: identity before rewards, discount lines before offers, registration before anything per-shop.

| Release | Scope | Estimate |
|---|---|---|
| R1 | Self-service shops: registration, setup wizard, branding, QR tab, staff role, per-store payments | 2 days |
| R2 | Data sync: webhook-first connector contract, Shopify, generic inventory webhook, Sheets and POS CSV schedules, cross-instance cache invalidation | 2 days |
| R3 | Scan-first cart and owner product add by barcode | 1 day |
| R4 | Shopper identity: optional phone OTP, profile, history, consent and deletion | 1.5 days |
| R5 | Customers, segments, offers and reward points | 3 days |
| R6 | Platform hygiene: multi-store jobs, GST, returns, retention | 1.5 days |

---

## R1. Self-service shops

**Registration and login.** Google sign-in only (decided). A signed-in user with no store sees "Register your shop": shop name, city, languages, currency. We create `stores/{slug}` with a unique slug from the name, add the uid to `users/{uid}.stores`, and open the setup wizard. One owner may own several stores; a store switcher already exists in the dashboard header.

**Setup wizard (four steps, each skippable).**
1. Import products: CSV with the normalizer, or "add by scanning" (R3), or start empty.
2. Floor map: number of aisles and their names; we generate the map geometry; drag-to-reorder later.
3. Branding: logo upload (Cloud Storage), accent colour, tagline, greeting line the assistant uses, languages. The shopper app reads these from the store document and themes itself per store.
4. Print: QR tab with a printable sheet of entrance and aisle codes, branded with the logo, plus the kiosk PIN.

**Staff role.** `users/{uid}.roles[store_id] = owner | staff`. Staff can run the kiosk, record counts, and mark orders packed; staff cannot approve purchase orders, change settings, or see customer data. Kiosk PIN remains for tablets without sign-in.

**Per-store payments.** Razorpay key id and secret stored per store in Secret Manager (`razorpay-{store_id}`), looked up by the checkout service; a store without keys stays in mock mode and the dashboard says so. Platform-level Razorpay Route is the later option for taking a platform fee.

**Security additions.** Slug validation and uniqueness in a transaction; logo uploads limited to 1 MB images; every new store starts with a random kiosk PIN shown once.

## R2. Data sync, webhook-first

**Decision.** The agent must reflect the shop's own system of record, reached through an API, with webhook notification when stock changes so updates are instant. We do not assume which system; we offer three adapters behind one contract and let the shop pick.

**Connector contract.**

```
pull_products(store_id) -> list[Product]
pull_inventory(store_id) -> list[Inventory]
push_inventory(store_id, updates) -> None
handle_webhook(store_id, headers, body) -> list[Inventory] | list[Order]
```

**Adapters.**
1. **Generic inventory webhook API** (first, because it works with any billing software that can call a URL): the shop's system calls `POST /sync/{store_id}/inventory` with `{sku, on_hand}` rows and an HMAC signature using a per-store secret; `POST /sync/{store_id}/products` for catalog changes. We also expose `GET /sync/{store_id}/inventory` so the shop's system can pull our stock, and we call the shop's registered URL on every sale (outbound webhook, retried with backoff). This is the path for Tally, Marg, GoFrugal, and custom billing software through their integration partners.
2. **Shopify**: Admin GraphQL for products and inventory levels; webhooks `orders/create`, `inventory_levels/update`, `products/update`; push with `inventoryAdjustQuantities`. HMAC verification on `X-Shopify-Hmac-Sha256`.
3. **Google Sheets**: scheduled pull every 15 minutes with the saved column mapping; write-back of stock to a "stock" column; a change log sheet for the owner.
4. **POS CSV drops**: scheduled import of files the POS exports to a shared folder or Cloud Storage bucket; owner reviews a diff before apply.

**Instant agent consistency.** A `stores/{id}.catalog_version` counter is bumped on every product write; the API compares it on each request and reloads the per-instance catalog cache when it changed. Inventory is already read live. Result: an owner edit or a webhook update is visible to the assistant on the next turn, on every instance.

**Conflict policy.** Firestore is the stock of record for in-store sales; the external system is the record for its own sales. Updates carry a timestamp; the newer wins; differences above a threshold create a shrink candidate for the owner. Every sync writes a `sync_log` entry; the Connectors tab shows last sync, rows changed, and errors.

## R3. Scan-first cart and owner product add by barcode

**Shopper, in store (decided).** Items enter the cart only through a barcode scan or, for items without a readable barcode, a photo match the shopper confirms. The assistant no longer adds to the cart in store; it finds, guides to the aisle, and says "scan it to add". `add_to_cart` is removed from the in-store tool set; online keeps it. The exit check then compares a receipt built only from physically scanned items.

**Owner, add product by scanning (decided).** In the Inventory tab, "Add by scan" opens the camera; the barcode is looked up in Open Food Facts for name, brand, category, and image; the owner enters price, stock, aisle; unknown barcodes fall back to manual entry with the barcode pre-filled. The same path works from the kiosk camera for bulk intake. Lookups are cached per barcode.

## R4. Shopper identity, optional

**Decision.** Phone OTP sign-in is optional. Guests keep today's anonymous flow. The entrance screen offers "Sign in to get your offers and history" with a one-line consent. Firebase phone auth on web (reCAPTCHA), test numbers for demos.

**Profile.** Name, preferred language, dietary preferences (veg, vegan, no sugar, allergens), favourite categories. From the research on grocery personalisation, two more fields earn their place: "usual items" for one-tap reorder of staples, and substitution preference (ask first, or auto-substitute same brand) for out-of-stock moments. Local or sustainable preference can follow.

**History.** Orders by date with receipts, re-order from a past order, points balance and expiry, offers used.

**Data rights.** Consent text at sign-in, "Download my data" and "Delete my account" in the profile, deletion removes the customer record, history and points; receipts are anonymised, not deleted, because they are the shop's sales records.

**Owner view.** Customers tab lists signed-in customers with visits, spend, last visit, segment, and points; guests appear only as counts.

## R5. Customers, segments, offers, reward points

**Segmentation.** Recency, frequency, monetary scores computed nightly per store: new (first visit under 30 days), regular (3+ visits in 90 days), high-value (top 20% spend), lapsed (no visit in 60 days). Segments drive targeted offers and the owner's dashboard.

**Discount lines.** Cart, order, receipt, payment amount and the owner's revenue reports gain a `discounts[]` array (`{kind, label, amount}`); the exit check counts items, not money, so it is unaffected.

**Offers (owner-created, decided).** Types: per-product discount, cart discount above an amount, category discount, segment-targeted offer. Fields: scope, value (percent or rupees), validity window, segment, per-customer limit, stackable flag. Applied automatically at checkout, best offer wins when not stackable, shown as a discount line. The shopper app shows "Offers for you" cards; the assistant gets a `get_offers` tool so "any deals on dairy?" is answered from real offers.

**Reward points (decided).** Earn 1 point per ₹100 paid, after discounts, for signed-in shoppers only; points expire 12 months after they are earned; the owner can change the rate and expiry per store. Redeem at checkout: 1 point = ₹1, minimum 50 points, an OTP to the registered phone confirms the redemption, the amount becomes a discount line, the ledger records earn and burn with the order id. Points are never transferable; only the owner can adjust a balance, with an audit entry.

**Fraud controls.** Points earn only on paid, verified exits; a refund reverses the earn; redemption OTP rate-limited; segment offers limited per customer.

## R6. Platform hygiene

- Forecast job iterates over all stores with a connector or sales history.
- GST: tax rate per product, tax line on receipts.
- Returns and refunds: owner-initiated against an order; stock returns to shelf; points and discounts reversed.
- Retention: verification records and conversation turns pruned after 90 days by a scheduled job; consent and deletion wired in R4.
- Multi-location: stores grouped under an owner with a combined overview.

## Open items to decide when R1 starts

- Logo and image storage bucket and CDN caching.
- Whether staff sign in with Google or with a store-issued code.
- Pricing: per-store subscription or per-transaction fee through Razorpay Route.
