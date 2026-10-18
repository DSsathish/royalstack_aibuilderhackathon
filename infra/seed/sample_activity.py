"""Sample activity for a seeded store, so every owner tab has something to show: sixty days of paid orders (store and
online, busier at weekends and in the evening), forty customers with segments, demand signals from the last week, a few
products run down to zero or low stock, shelf counts with discrepancies, exit checks and three offers.

Deterministic (seeded random) and idempotent: documents carry stable ids, so a re-run overwrites the same ones.

  backend/.venv/bin/python infra/seed/sample_activity.py --store dailygoods
  backend/.venv/bin/python -m app.jobs.forecast --store dailygoods      # then: days of cover and reorder drafts
"""

import argparse
import hashlib
import random
import sys
import uuid
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "backend"))

from app.domain.models import CartItem, Customer, DemandSignal, Layers, Offer, Order, Verification, VisionResult, now  # noqa: E402
from app.services import db, segments  # noqa: E402

IST = timezone(timedelta(hours=5, minutes=30))
DAYS = 60
NAMES = ["Hema", "Karthik", "Priya", "Arun", "Divya", "Suresh", "Lakshmi", "Vignesh", "Meena", "Rahul", "Anitha", "Manoj", "Kavya", "Deepak",
         "Sangeetha", "Praveen", "Nithya", "Ramesh", "Shalini", "Ajay", "Revathi", "Gokul", "Pooja", "Senthil", "Janani", "Harish", "Sowmya",
         "Bala", "Keerthana", "Naveen", "Yamini", "Dinesh", "Aishwarya", "Mohan", "Swathi", "Vijay", "Gayathri", "Sathish", "Ramya", "Kumar"]
NOT_CARRIED = ["oat milk", "quinoa", "kombucha", "sourdough bread", "avocado", "cat litter", "ஓட்ஸ் பால்", "சர்க்கரை இல்லாத பிஸ்கட்", "डायपर",
               "protein bar", "almond flour", "tofu", "greek yogurt", "blueberries", "air fryer oil", "dishwasher tablets", "bamboo toothbrush",
               "trail mix", "makhana", "கினோவா", "cold brew coffee", "dark chocolate 70", "peanut butter", "fresh basil", "millet mix",
               "कोल्ड कॉफी", "vegan cheese", "gluten free pasta", "ghee 500 ml", "skyr"]
FLAG_REASONS = ["1 item in the bag is not on the receipt", "Count differs from the receipt by 2", "High-value item needs a spot check"]


def _ts(day_offset: int, hour: float) -> datetime:
    """A moment on an IST day, as UTC: day_offset days ago at the given hour."""
    d = (datetime.now(IST) - timedelta(days=day_offset)).replace(hour=0, minute=0, second=0, microsecond=0)
    return (d + timedelta(hours=hour)).astimezone(timezone.utc)


def _popular(products: list[dict], rnd: random.Random) -> list[tuple[dict, float]]:
    """Three hundred products with a long-tail weight; everyday categories sell more."""
    boost = {"Grocery and Food Products": 3.0, "Dairy, Bread and Eggs": 3.0, "Fruits and Vegetables": 2.5, "Snacks and Branded Foods": 2.0, "Beverages": 1.8}
    pool = sorted(products, key=lambda p: rnd.random() / boost.get(p.get("category", ""), 1.0))[:300]
    return [(p, 1.0 / (i + 3)) for i, p in enumerate(pool)]


def run(store_id: str) -> dict:
    rnd = random.Random(f"sample-{store_id}")
    products = [d.to_dict() for d in db.products(store_id).stream() if d.to_dict().get("status", "active") == "active"]
    if not products:
        raise SystemExit("seed the catalog first")
    pop = _popular(products, rnd)
    weights = [w for _, w in pop]
    pid_of = {p["product_id"]: p for p, _ in pop}

    # customers: who they are and when they shop
    customers = []
    for i, name in enumerate(NAMES):
        uid = f"sample-cust-{i:03d}"
        kind = "vip" if i < 7 else "regular" if i < 22 else "at_risk" if i < 31 else "new"
        window = (0, DAYS) if kind in ("vip", "regular") else (47, DAYS) if kind == "at_risk" else (0, 20)
        n_orders = {"vip": rnd.randint(7, 14), "regular": rnd.randint(2, 5), "at_risk": rnd.randint(2, 4), "new": 1}[kind]
        customers.append({"uid": uid, "name": name, "kind": kind, "window": window, "n_orders": n_orders,
                          "language": rnd.choice(["auto", "ta", "en", "hi", "auto"]), "phone_last4": f"{rnd.randint(0, 9999):04d}",
                          "dietary": rnd.choice([[], [], ["vegetarian"], ["vegan"], ["no nuts"]])})
    visits_left = {c["uid"]: list(sorted(rnd.randint(c["window"][0], c["window"][1]) for _ in range(c["n_orders"]))) for c in customers}

    # orders: sixty days, weekends and evenings busier, today's up to now
    orders, by_customer = [], defaultdict(list)
    now_ist = datetime.now(IST)
    for day in range(DAYS, -1, -1):
        date = now_ist - timedelta(days=day)
        n = rnd.randint(16, 22) + (8 if date.weekday() >= 5 else 0)
        hours = sorted(rnd.choice([rnd.uniform(8, 12), rnd.uniform(12, 17), rnd.uniform(17, 21.5), rnd.uniform(17, 21.5)]) for _ in range(n))
        if day == 0:
            hours = [h for h in hours if h < now_ist.hour + now_ist.minute / 60 - 0.1]
        todays = [c for c in customers if day in visits_left[c["uid"]]]
        for k, hour in enumerate(hours):
            cust = todays.pop() if todays and rnd.random() < 0.9 else None
            if cust:
                visits_left[cust["uid"]].remove(day)
            lines = rnd.choices(pop, weights=weights, k=rnd.choice([1, 2, 2, 3, 3, 4, 5, 6, 8]))
            items, seen = [], set()
            for p, _ in lines:
                if p["product_id"] in seen:
                    continue
                seen.add(p["product_id"])
                qty = rnd.choice([1, 1, 1, 2, 2, 3])
                items.append(CartItem(product_id=p["product_id"], name=p["name"], qty=qty, unit_price=float(p["price"]), mrp=float(p.get("mrp") or p["price"]), via=rnd.choice(["scan", "scan", "chat"])))
            subtotal = round(sum(i.unit_price * i.qty for i in items), 2)
            savings = round(sum(max(0.0, i.mrp - i.unit_price) * i.qty for i in items), 2)
            channel = "online" if rnd.random() < 0.25 else "store"
            created = _ts(day, hour)
            oid = "sample-" + hashlib.sha1(f"{store_id}-{day}-{k}".encode()).hexdigest()[:20]
            o = Order(order_id=oid, store_id=store_id, session_id=f"sample-session-{oid[-8:]}", cart_id=f"sample-cart-{oid[-8:]}", channel=channel,
                      items=items, subtotal=subtotal, savings=savings, total=subtotal, status="paid", receipt_token=uuid.uuid5(uuid.NAMESPACE_URL, oid).hex,
                      customer_id=cust["uid"] if cust else None, created_at=created, paid_at=created + timedelta(minutes=2),
                      exited_at=created + timedelta(minutes=9) if channel == "store" else None, points_earned=int(subtotal // 100) if cust else 0)
            orders.append(o)
            if cust:
                by_customer[cust["uid"]].append(o)

    batch, n = db.client().batch(), 0
    def put(ref, data):
        nonlocal batch, n
        batch.set(ref, data); n += 1
        if n >= 400:
            batch.commit(); batch, n = db.client().batch(), 0
    for o in orders:
        put(db.orders().document(o.order_id), o.model_dump())

    # customers: visits, spend, usual items and the segment the rules give them
    seg_counts = Counter()
    for c in customers:
        mine = sorted(by_customer[c["uid"]], key=lambda o: o.created_at)
        counts = Counter()
        for o in mine:
            counts.update({i.product_id for i in o.items})
        usual = [pid for pid, k in counts.most_common(10) if k >= 2]
        spend = round(sum(o.total for o in mine), 2)
        fav = Counter(pid_of[i.product_id].get("category", "") for o in mine for i in o.items if i.product_id in pid_of).most_common(2)
        cust = Customer(uid=c["uid"], store_id=store_id, name=c["name"], language=c["language"], dietary=c["dietary"], phone_last4=c["phone_last4"],
                        favourite_categories=[f for f, _ in fav], usual_items=usual, substitution=rnd.choice(["ask", "same_brand", "any"]),
                        consent_at=mine[0].created_at if mine else now(), created_at=mine[0].created_at if mine else now(),
                        last_seen=mine[-1].created_at if mine else now(), visits=len(mine), spend=spend, points=int(spend // 100))
        cust.segment = segments.classify(cust)
        seg_counts[cust.segment] += 1
        put(db.customers(store_id).document(cust.uid), cust.model_dump())

    # stock: some lines sold out, some low, so the inventory and reorder tabs have work to show
    out = [p for p, _ in pop[:40:2]]
    low = [p for p, _ in pop[1:70:2]]
    for p in out:
        put(db.inventory(store_id).document(p["product_id"]), {"on_hand": 0})
    for p in low:
        put(db.inventory(store_id).document(p["product_id"]), {"on_hand": rnd.randint(1, 4)})
    batch.commit(); batch, n = db.client().batch(), 0
    # (the on_hand writes above must merge: redo them as updates)
    for p in out:
        db.inventory(store_id).document(p["product_id"]).update({"on_hand": 0})
    for p in low:
        db.inventory(store_id).document(p["product_id"]).update({"on_hand": rnd.randint(1, 4)})

    # demand signals from the last week: what shoppers asked for and could not get
    for i, q in enumerate(NOT_CARRIED):
        sig = DemandSignal(signal_id=hashlib.sha1(f"{store_id}-nc-{i}".encode()).hexdigest()[:32], store_id=store_id, query_text=q,
                           type="not_carried", source="agent" if i % 3 else "search", created_at=_ts(rnd.randint(0, 6), rnd.uniform(9, 21)))
        put(db.demand_signals(store_id).document(sig.signal_id), sig.model_dump())
    for i, p in enumerate(out[:14]):
        sig = DemandSignal(signal_id=hashlib.sha1(f"{store_id}-oos-{i}".encode()).hexdigest()[:32], store_id=store_id, query_text=p["name"].split(" ")[0].lower() + " " + (p["name"].split(" ")[1].lower() if len(p["name"].split(" ")) > 1 else ""),
                           matched_product_id=p["product_id"], type="out_of_stock", source="agent", created_at=_ts(rnd.randint(0, 6), rnd.uniform(9, 21)))
        put(db.demand_signals(store_id).document(sig.signal_id), sig.model_dump())

    # shelf counts: a few discrepancies for the loss tab
    for i, (p, _) in enumerate(pop[80:92]):
        system = db.inventory(store_id).document(p["product_id"]).get().to_dict().get("on_hand", 0)
        counted = system if i % 3 == 0 else max(0, system - rnd.randint(1, 4))
        put(db.counts(store_id).document(p["product_id"]), {"product_id": p["product_id"], "counted": counted, "system": system, "by": "sample-staff", "at": _ts(rnd.randint(0, 5), rnd.uniform(9, 20))})

    # exit checks over the last two weeks, mostly clear
    store_orders = [o for o in orders if o.channel == "store" and (now() - o.created_at).days <= 14]
    flags = 0
    for i, o in enumerate(rnd.sample(store_orders, min(60, len(store_orders)))):
        roll = rnd.random()
        verdict = "clear" if roll < 0.8 else "spot_check" if roll < 0.92 else "flag"
        high = [it.product_id for it in o.items if it.unit_price >= 500][:2]
        v = Verification(verification_id=hashlib.sha1(f"{store_id}-v-{i}".encode()).hexdigest()[:32], store_id=store_id, order_id=o.order_id, kiosk_id="exit-1",
                         layers=Layers(receipt_ok=True, order_ok=True, count_ok=verdict != "flag", limit_ok=True, high_value=high, random_audit=verdict == "spot_check" and not high),
                         verdict=verdict, reasons=[rnd.choice(FLAG_REASONS)] if verdict == "flag" else (["Random spot check"] if verdict == "spot_check" else []),
                         vision=VisionResult(confidence=round(rnd.uniform(0.6, 0.98), 2), visible_items=[it.name for it in o.items[:3]]) if verdict != "clear" else None,
                         reviewed_by="owner" if verdict == "flag" and i % 2 else "", review_outcome=rnd.choice(["cleared", "issue_confirmed"]) if verdict == "flag" and i % 2 else None,
                         created_at=o.created_at + timedelta(minutes=8))
        flags += verdict == "flag"
        put(db.verifications().document(v.verification_id), v.model_dump())

    # three offers
    atta = next((p for p in products if p["sku"].upper() == "ATTA5"), None)
    offers = [Offer(offer_id="sample-offer-dairy-vip", store_id=store_id, name="10% off dairy for VIP members", kind="category", category="Dairy, Bread and Eggs", percent_off=10, segment="vip", created_by="owner"),
              Offer(offer_id="sample-offer-cart-1500", store_id=store_id, name="Rs 100 off bills over Rs 1,500", kind="cart", min_total=1500, amount_off=100, segment="all", created_by="owner")]
    if atta:
        offers.append(Offer(offer_id="sample-offer-atta", store_id=store_id, name="Rs 15 off Aashirvaad Atta 5 kg", kind="product", product_id=atta["product_id"], amount_off=15, segment="all", created_by="owner"))
    for o in offers:
        put(db.offers(store_id).document(o.offer_id), o.model_dump())
    if n:
        batch.commit()
    return {"orders": len(orders), "today": sum(1 for o in orders if (now() - o.created_at).total_seconds() < 86400 * 1), "customers": dict(seg_counts),
            "out_of_stock": len(out), "low": len(low), "signals": len(NOT_CARRIED) + min(14, len(out)), "counts": 12, "exit_checks": min(60, len(store_orders)), "flags": flags, "offers": len(offers)}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--store", required=True)
    print(run(ap.parse_args().store))
