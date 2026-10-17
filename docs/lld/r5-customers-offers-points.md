# LLD: R5 customer insight, offers and reward points

Owners learn who their signed-in customers are, create offers that apply themselves, and run a points programme. Everything is per store; guests see store-wide offers only.

## Segments (`services/segments.py`)
- One rule set, stored on the customer record as `segment` so cart pricing never computes it:
  `new` (one visit or none), `regular` (two or more), `vip` (five or more visits and spend of 5,000 or more), `at_risk` (two or more visits, last seen more than 45 days ago). Guests are `guest`.
- `classify(customer) -> str`; `refresh(store_id)` rewrites the segment of every customer (nightly, because `at_risk` depends on time); `record_order` sets it after each purchase.
- Owner Customers tab shows segment counts and a segment filter.

## Offers (`stores/{sid}/offers/{offer_id}`, `services/offers.py`)
- `Offer(offer_id, store_id, name, kind: product|category|cart, product_id, category, min_total, percent_off, amount_off, segment: all|signed_in|new|regular|vip|at_risk, active, starts_at, ends_at, created_by, created_at)`. Exactly one of `percent_off` (1 to 90) or `amount_off` (> 0).
- `applicable(store_id, segment)`: active, inside the date window, `segment` is `all`, or `signed_in` for any signed-in shopper, or equal to the shopper's segment.
- `apply(store_id, cart, segment) -> (lines, discount_total)`: per line the best single product or category offer (category read from the cached catalog); then the best single cart offer whose `min_total` the subtotal after line discounts meets. Discounts never exceed the line or cart amount. Lines are `DiscountLine(offer_id, name, amount)` merged per offer.
- Owner API: `GET/POST /owner/{sid}/offers`, `PATCH /owner/{sid}/offers/{id}` (any field, including `active`), `DELETE /owner/{sid}/offers/{id}`; audit entries on create, change and delete.
- Shopper API: `GET /stores/{sid}/offers` with the optional `X-Session-Id` header returns the offers that apply to that shopper (store-wide ones for guests). Agent tool `get_offers` returns the same list; action `show_offers`.

## Pricing (`services/cart.py::pricing`)
- `pricing(store_id, cart, segment="guest", points=0) -> Pricing(subtotal, savings, discounts, discount_total, points_redeemed, points_value, total)`. Replaces `totals`. Points value is one rupee per point, capped at the total after discounts.
- `GET /carts/{id}` uses the session's customer segment; the view carries `discounts`, `discount_total`, `points_balance` (signed-in only) and `segment`.

## Points (`customer.points` balance plus `stores/{sid}/customers/{uid}/ledger/{entry_id}`, `services/points.py`)
- Earn one point per 100 rupees of money paid (total after discounts and redemption), rounded down, at `checkout.confirm`; ledger `earn` entries carry `remaining` and `expires_at` twelve months out.
- Redeem at `checkout.intent` with `points` in the body: signed-in shopper, at least 50 points, not more than the balance or the amount due, and a phone token issued within the last ten minutes (`auth.require_recent_phone`, from the token's `auth_time`). This is the OTP step: the app re-verifies the number right before paying. The redemption is written inside a Firestore transaction (`points._move`: read the unexpired credits, consume oldest first, write the `redeem` entry, set the balance to what is actually left) and tied to the order. If the shopper starts a new checkout for the same cart while an earlier order still holds points, that order is cancelled and its points come back as a `release` credit (fresh twelve-month expiry); orders without points are left alone. The nightly job does the same for point-holding orders pending for more than a day. A cancelled order cannot be confirmed. An order fully covered by points has a zero total and settles through the mock provider.
- Owner adjustments: `POST /owner/{sid}/customers/{uid}/points {delta, reason}` (owner only, non-zero delta with a reason, balance never below zero, audit entry `points_adjusted`). Shopper view: `GET /me/points?store_id=` returns balance, minimum redemption and the last 50 entries.
- Expiry: nightly, credits past `expires_at` with `remaining > 0` are zeroed (chunked writes) with an `expire` entry, and the balance is set to the credits that remain. Both `_move` and `expire` write the balance absolutely from unexpired credits, so a move between a credit's expiry and the nightly run never double-counts. Release entries use a fixed id (`release-{order_id}`) written create-once, so a retry and the nightly job cannot both credit an order. `checkout.confirm` claims the order pending to paid in a transaction before any side effect, so concurrent confirms earn points once.
- Orders record `discounts`, `discount_total`, `points_redeemed`, `points_value`, `points_earned`; receipts show them.

## Nightly job (`jobs/customers.py`, `POST /jobs/customers`, scheduler `customers-nightly`)
- For every store: refresh segments, expire points, release stale redemptions. `POST /jobs/forecast` without `store_id` now runs the forecast for every store (R6 part); the scheduler job is updated accordingly. Sequential per store is fine at this size; per-store fan-out through Cloud Tasks is the next step when a run approaches the request timeout.

## Client
- Shopper: "Offers for you" strip on the chat tab (from `GET /stores/{sid}/offers`), discount lines and points balance in the cart and total bar, "Use points" on the checkout page with the re-verification code step, receipt lines for discounts, points used and points earned; points history on `/me`.
- Owner: Offers tab (list, create form with kind, target, value, segment, dates, active toggle), Customers tab gains segments, filter and a points adjustment dialog.

## Security
- Offer values bounded (percent 1 to 90, amount greater than zero, names 60 characters); only owners write offers; segment-targeted offers are never shown to shoppers outside the segment.
- Points move only through the ledger: earn at confirm, redeem in a transaction after a fresh phone verification, owner adjustments with a reason and audit, expiry by the job. No endpoint sets a balance directly.
- The redemption check uses the token's `auth_time`, so a stolen long-lived token cannot spend points.

## Tests
- `test_offers.py`: applicability by segment and dates; product versus category best-wins; cart threshold; discounts capped; pricing totals.
- `test_points.py`: earn on confirm; redeem below minimum, above balance and without a fresh token refused; FIFO consumption; release on re-intent; expiry; owner adjustment floor at zero.
- `test_api_offers.py`: owner CRUD and audit; shopper listing by segment; `get_offers` tool.
- `test_segments.py`: classification rules and refresh.
