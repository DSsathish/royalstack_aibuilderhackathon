"""Writes sales.csv: 90 days of daily sales per product with seasonality.

Usage: python infra/seed/make_sales.py --store demo-grocery
Deterministic (fixed random seed). Festival spike in the last 14 days for
Sweets, Oils & Ghee, Pooja items; 10 dead-stock products fade to zero.
"""

import argparse
import csv
import random
from datetime import date, timedelta
from pathlib import Path

HERE = Path(__file__).parent
DAYS = 90
BASE_DAILY = {  # mean units per day by category
    "Staples": 3, "Oils & Ghee": 2, "Dairy": 8, "Bakery": 4, "Beverages": 4, "Snacks": 6,
    "Sweets": 2, "Personal Care": 2, "Household": 2, "Baby": 1, "Pharmacy": 2,
    "Fruits & Vegetables": 7, "Frozen": 1.5, "Pet": 0.5,
}
FESTIVAL = {"Sweets", "Oils & Ghee"}
DEAD_STOCK = {"COLIN", "HIT", "FOIL", "SUNSCREEN", "TALC", "GREENTEA", "POPCORN", "RAJMA500", "CELEB", "WHISKAS"}


def slug(text: str) -> str:
    import re
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def main(store_id: str) -> None:
    rng = random.Random(42)
    products = list(csv.DictReader((HERE / "products.csv").open(encoding="utf-8")))
    end = date.today()
    out = HERE / "sales.csv"
    n = 0
    with out.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["store_id", "product_id", "day", "channel", "qty", "unit_price"])
        for p in products:
            base = BASE_DAILY[p["category"]]
            pooja = p["subcategory"] == "Pooja"
            for d in range(DAYS):
                day = end - timedelta(days=DAYS - d)
                mean = base * (1.4 if day.weekday() >= 5 else 1.0)
                if d >= DAYS - 14 and (p["category"] in FESTIVAL or pooja):
                    mean *= 2.5
                if p["sku"] in DEAD_STOCK:
                    mean *= max(0.0, 1 - d / 60)  # fades to zero after day 60
                qty = max(0, int(rng.gauss(mean, mean * 0.4 + 0.3)))
                if qty == 0:
                    continue
                online = rng.random() < 0.25
                w.writerow([store_id, f"{store_id}-{slug(p['sku'])}", day.isoformat(),
                            "online" if online else "store", qty, p["price"]])
                n += 1
    print(f"wrote {n} sales rows to {out}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--store", default="demo-grocery")
    main(ap.parse_args().store)
