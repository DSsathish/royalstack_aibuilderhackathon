"""Create or fill a store from a public Kaggle product catalogue. No Kaggle account needed (kagglehub, public datasets).

    cd backend && .venv/bin/python ../infra/seed/kaggle_catalog.py --dataset bigbasket --store my-mart --name "My Mart" \
        --owner-email you@example.com --seed 1 --limit 300 [--categories "Beverages|Bakery, Cakes & Dairy"] [--append-sales] [--no-embed]
    cd backend && .venv/bin/python ../infra/seed/kaggle_catalog.py --dataset myntra --store my-textiles --name "My Textiles" ...

Datasets: bigbasket = 27,555 Indian grocery products (surajjha101); myntra = 12,491 clothing and accessories with INR prices
(shivamb). Steps: download -> sample across categories -> canonical CSV with synthetic stock -> 90 days of synthetic sales ->
import_dataset.py (store, products, aisles, suppliers, BigQuery) -> Gemini embeddings -> attach to an existing dashboard account.
"""

import argparse
import csv
import glob
import json
import os
import random
import re
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent.parent / "backend"))
sys.path.insert(0, str(HERE))

OUT = Path(os.environ.get("KAGGLE_OUT", Path.home() / ".cache" / "royalstack-kaggle"))
COLUMNS = ["sku", "name", "brand", "category", "subcategory", "price", "mrp", "unit", "description", "tags", "on_hand", "reorder_point", "reorder_qty"]

# --- dataset profiles: how each catalogue becomes canonical rows -------------------------------------------------

BIGBASKET_DAILY = {"Fruits & Vegetables": 5, "Bakery, Cakes & Dairy": 4, "Foodgrains, Oil & Masala": 3, "Beverages": 2.5, "Snacks & Branded Foods": 2.5,
                   "Eggs, Meat & Fish": 2, "Cleaning & Household": 1.5, "Baby Care": 1, "Beauty & Hygiene": 1, "Gourmet & World Food": 0.8, "Kitchen, Garden & Pets": 0.5}


def bigbasket_row(r: dict, rng: random.Random) -> dict | None:
    if not r.get("product") or not r.get("sale_price"):
        return None
    price = float(r["sale_price"])
    staple = r["category"] in ("Foodgrains, Oil & Masala", "Bakery, Cakes & Dairy", "Fruits & Vegetables")
    return {"sku": f"BB-{int(r['index']):05d}", "name": r["product"].strip()[:120], "brand": (r.get("brand") or "").strip()[:60],
            "category": r["category"], "subcategory": (r.get("sub_category") or "").strip()[:60],
            "price": f"{price:.2f}", "mrp": f"{max(price, float(r.get('market_price') or price)):.2f}", "unit": "pc",
            "description": (r.get("description") or "").strip().replace("\n", " ")[:200], "tags": (r.get("type") or "").strip()[:60],
            "on_hand": 0 if rng.random() < 0.08 else rng.randint(3, 60), "reorder_point": 10 if staple else 5, "reorder_qty": 30 if staple else 20}


MYNTRA_CATEGORY = {"Women": "Women's Wear", "Men": "Men's Wear", "Boys": "Kids' Wear", "Girls": "Kids' Wear", "Unisex Kids": "Kids' Wear", "Unisex": "Unisex & Accessories"}
MYNTRA_DAILY = {"Women's Wear": 0.7, "Men's Wear": 0.6, "Kids' Wear": 0.4, "Unisex & Accessories": 0.3}
ARTICLES = ["Saree", "Kurta Set", "Kurta", "Kurti", "Lehenga", "Dupatta", "Salwar", "Palazzo", "T-shirt", "Tshirt", "Polo", "Shirt", "Jeans", "Trousers",
            "Track Pants", "Joggers", "Shorts", "Skirt", "Dress", "Top", "Jacket", "Blazer", "Sweater", "Sweatshirt", "Hoodie", "Night Suit", "Nightdress",
            "Leggings", "Socks", "Cap", "Trolley Bag", "Backpack", "Handbag", "Bag", "Sneakers", "Shoes", "Sandals", "Flip-Flops", "Watch", "Belt", "Wallet",
            "Sunglasses", "Innerwear", "Briefs", "Bra", "Boxers", "Vest", "Scarf", "Stole", "Tie"]


def article_of(name: str) -> str:
    low = name.lower()
    for a in ARTICLES:
        if re.search(r"\b" + re.escape(a.lower()) + r"s?\b", low):
            return "T-shirt" if a == "Tshirt" else a
    return "Apparel"


def myntra_row(r: dict, rng: random.Random) -> dict | None:
    if not r.get("ProductName") or not r.get("Price (INR)"):
        return None
    price = float(r["Price (INR)"])
    mrp = round(price * rng.choice((1.0, 1.0, 1.1, 1.2, 1.3)))          # the dataset has one price; a synthetic MRP shows savings
    return {"sku": f"MY-{r['ProductID']}", "name": r["ProductName"].strip()[:120], "brand": (r.get("ProductBrand") or "").strip()[:60],
            "category": MYNTRA_CATEGORY.get(r.get("Gender", ""), "Unisex & Accessories"), "subcategory": article_of(r["ProductName"]),
            "price": f"{price:.2f}", "mrp": f"{mrp:.2f}", "unit": "pc",
            "description": (r.get("Description") or "").strip().replace("\n", " ")[:200], "tags": (r.get("PrimaryColor") or "").strip()[:40],
            "on_hand": 0 if rng.random() < 0.08 else rng.randint(2, 25), "reorder_point": 3, "reorder_qty": 10}


PROFILES = {
    "bigbasket": {"dataset": "surajjha101/bigbasket-entire-product-list-28k-datapoints", "category_col": "category", "row": bigbasket_row, "daily": BIGBASKET_DAILY},
    "myntra": {"dataset": "shivamb/fashion-clothing-products-catalog", "category_col": "Gender", "row": myntra_row, "daily": MYNTRA_DAILY},
}

# --- shared pipeline -------------------------------------------------------------------------------------------------


def download(dataset: str) -> Path:
    import kagglehub
    os.environ.setdefault("KAGGLEHUB_CACHE", str(OUT / "kagglehub"))
    files = glob.glob(f"{kagglehub.dataset_download(dataset)}/**/*.csv", recursive=True)
    if not files:
        sys.exit("dataset downloaded but no CSV inside")
    return Path(files[0])


def sample(src: Path, category_col: str, limit: int, seed: int, categories: set[str] | None, per_category: int = 0) -> list[dict]:
    """A deterministic cross-section: every category represented, larger ones get more rows (or a fixed quota each)."""
    rng = random.Random(seed)
    rows = [r for r in csv.DictReader(src.open(encoding="utf-8-sig")) if not categories or r.get(category_col) in categories]
    if not rows:
        sys.exit(f"no products in categories {sorted(categories or [])}")
    by_cat: dict[str, list[dict]] = {}
    for r in rows:
        by_cat.setdefault(r.get(category_col, ""), []).append(r)
    picked, seen = [], set()
    for cat, items in sorted(by_cat.items()):
        rng.shuffle(items)
        want = per_category or max(10, round(limit * len(items) / len(rows)))
        taken = 0
        for r in items:
            if taken >= want:
                break
            key = next((r[k] for k in ("product", "ProductName") if k in r), None)
            if key in seen:
                continue
            seen.add(key)
            picked.append(r)
            taken += 1
    rng.shuffle(picked)
    return picked[:limit]


def sales_rows(rows: list[dict], daily: dict[str, float], seed: int, days: int = 90) -> list[dict]:
    """Ninety days of plausible sales for most products: weekends busier, a few lines fading out (dead stock)."""
    rng = random.Random(seed + 2)
    end = date.today()
    out = []
    for r in rows:
        if rng.random() < 0.35:
            continue
        base = daily.get(r["category"], 1) * rng.uniform(0.5, 1.5)
        fading = rng.random() < 0.05
        for d in range(days):
            day = end - timedelta(days=days - d)
            mean = base * (1.4 if day.weekday() >= 5 else 1.0) * (max(0.0, 1 - d / 60) if fading else 1.0)
            qty = max(0, int(rng.gauss(mean, mean * 0.4 + 0.3)))
            if qty:
                out.append({"sku": r["sku"], "day": day.isoformat(), "qty": qty})
    return out


def attach_existing_account(store_id: str, email: str) -> int:
    """A dashboard account that signed in before this store existed is not bootstrapped again; add the role directly."""
    from google.cloud.firestore_v1 import FieldFilter
    from app.services import db
    n = 0
    for d in db.users().where(filter=FieldFilter("email", "==", email.lower())).stream():
        data = d.to_dict()
        legacy = {s: "owner" for s in data.get("stores", [])}          # memberships recorded before roles existed
        d.reference.set({"stores": sorted(set(data.get("stores", [])) | {store_id}), "roles": {**legacy, **(data.get("roles") or {}), store_id: "owner"}}, merge=True)
        n += 1
    return n


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", choices=sorted(PROFILES), default="bigbasket")
    ap.add_argument("--store", required=True)
    ap.add_argument("--name", required=True)
    ap.add_argument("--owner-email", action="append", default=[])
    ap.add_argument("--seed", type=int, default=1, help="different seeds give different product subsets")
    ap.add_argument("--limit", type=int, default=300)
    ap.add_argument("--per-category", type=int, default=0, help="take this many from every source category instead of a proportional share")
    ap.add_argument("--file", help="use a local copy of the dataset instead of downloading")
    ap.add_argument("--categories", help="source categories to draw from, separated by | (names may contain commas); default: all")
    ap.add_argument("--append-sales", action="store_true", help="add to the store's sales history instead of replacing it")
    ap.add_argument("--no-embed", action="store_true")
    a = ap.parse_args()
    prof = PROFILES[a.dataset]

    src = Path(a.file) if a.file else download(prof["dataset"])
    OUT.mkdir(parents=True, exist_ok=True)
    wanted = {c.strip() for c in a.categories.split("|")} if a.categories else None
    rng = random.Random(a.seed + 1)
    limit = a.per_category * 20 if a.per_category else a.limit          # a quota run is capped by the quota, not the limit
    rows = [row for r in sample(src, prof["category_col"], limit, a.seed, wanted, a.per_category) if (row := prof["row"](r, rng))]
    products_csv, sales_csv = OUT / f"{a.store}-products.csv", OUT / f"{a.store}-sales.csv"
    with products_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(rows)
    sales = sales_rows(rows, prof["daily"], a.seed)
    with sales_csv.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["sku", "day", "qty"])
        w.writeheader()
        w.writerows(sales)
    print(f"{a.store}: {len(rows)} products across {len({r['category'] for r in rows})} categories, {len(sales)} sales rows -> {OUT}")

    cmd = [sys.executable, str(HERE / "import_dataset.py"), "--file", str(products_csv), "--store", a.store, "--name", a.name,
           "--sales", str(sales_csv), "--limit", str(len(rows)), "--mapping", json.dumps({c: c for c in COLUMNS})]
    for e in a.owner_email:
        cmd += ["--owner-email", e]
    if a.append_sales:
        cmd.append("--append-sales")
    subprocess.run(cmd, check=True)

    if not a.no_embed:
        from seed import seed_embeddings
        seed_embeddings(a.store)
    for e in a.owner_email:
        print(f"attached to {attach_existing_account(a.store, e)} existing dashboard account(s) for {e}")
    print("done. Next: cd backend && .venv/bin/python -m app.jobs.forecast --store", a.store)


if __name__ == "__main__":
    main()
