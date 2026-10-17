"""Create a store from the Kaggle BigBasket product list (27,555 real Indian grocery products, public dataset).

    cd backend && .venv/bin/python ../infra/seed/kaggle_bigbasket.py --store captain-jack-mart --name "Captain Jack Mart" \
        --owner-email thecaptainjackssparrow@gmail.com --seed 1 --limit 300 [--file "BigBasket Products.csv"] [--no-embed]

Steps: download with kagglehub (no credentials needed for a public dataset) -> sample products across categories ->
canonical CSV with synthetic stock levels -> 90 days of synthetic sales -> import_dataset.py (store, products, aisles,
suppliers, BigQuery) -> Gemini embeddings -> attach the store to a dashboard account that already exists for the email.
"""

import argparse
import csv
import glob
import os
import random
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent.parent / "backend"))
sys.path.insert(0, str(HERE))

DATASET = "surajjha101/bigbasket-entire-product-list-28k-datapoints"
OUT = Path(os.environ.get("KAGGLE_OUT", Path.home() / ".cache" / "royalstack-kaggle"))
COLUMNS = ["sku", "name", "brand", "category", "subcategory", "price", "mrp", "unit", "description", "tags", "on_hand", "reorder_point", "reorder_qty"]
BASE_DAILY = {"Fruits & Vegetables": 5, "Bakery, Cakes & Dairy": 4, "Foodgrains, Oil & Masala": 3, "Beverages": 2.5, "Snacks & Branded Foods": 2.5,
              "Eggs, Meat & Fish": 2, "Cleaning & Household": 1.5, "Baby Care": 1, "Beauty & Hygiene": 1, "Gourmet & World Food": 0.8, "Kitchen, Garden & Pets": 0.5}


def download() -> Path:
    import kagglehub
    os.environ.setdefault("KAGGLEHUB_CACHE", str(OUT / "kagglehub"))
    path = kagglehub.dataset_download(DATASET)
    files = glob.glob(f"{path}/**/*.csv", recursive=True)
    if not files:
        sys.exit("dataset downloaded but no CSV inside")
    return Path(files[0])


def sample(src: Path, limit: int, seed: int, categories: set[str] | None = None) -> list[dict]:
    """A deterministic cross-section of the catalogue: every category represented, larger ones get more rows."""
    rng = random.Random(seed)
    rows = [r for r in csv.DictReader(src.open(encoding="utf-8-sig")) if r.get("product") and r.get("sale_price")
            and (not categories or r["category"] in categories)]
    if not rows:
        sys.exit(f"no products in categories {sorted(categories or [])}")
    by_cat: dict[str, list[dict]] = {}
    for r in rows:
        by_cat.setdefault(r["category"], []).append(r)
    total = len(rows)
    picked, seen_names = [], set()
    for cat, items in sorted(by_cat.items()):
        rng.shuffle(items)
        want = max(10, round(limit * len(items) / total))
        for r in items:
            if len([p for p in picked if p["category"] == cat]) >= want:
                break
            if r["product"] in seen_names:
                continue
            seen_names.add(r["product"])
            picked.append(r)
    rng.shuffle(picked)
    return picked[:limit]


def to_rows(items: list[dict], seed: int) -> list[dict]:
    rng = random.Random(seed + 1)
    out = []
    for r in items:
        price = float(r["sale_price"])
        mrp = max(price, float(r.get("market_price") or price))
        staple = r["category"] in ("Foodgrains, Oil & Masala", "Bakery, Cakes & Dairy", "Fruits & Vegetables")
        on_hand = 0 if rng.random() < 0.08 else rng.randint(3, 60)
        out.append({"sku": f"BB-{int(r['index']):05d}", "name": r["product"].strip()[:120], "brand": (r.get("brand") or "").strip()[:60],
                    "category": r["category"], "subcategory": (r.get("sub_category") or "").strip()[:60], "price": f"{price:.2f}", "mrp": f"{mrp:.2f}",
                    "unit": "pc", "description": (r.get("description") or "").strip().replace("\n", " ")[:200], "tags": (r.get("type") or "").strip()[:60],
                    "on_hand": on_hand, "reorder_point": 10 if staple else 5, "reorder_qty": 30 if staple else 20})
    return out


def sales_rows(rows: list[dict], seed: int, days: int = 90) -> list[dict]:
    """Ninety days of plausible sales for most products: weekends busier, a few lines fading out (dead stock)."""
    rng = random.Random(seed + 2)
    end = date.today()
    out = []
    for r in rows:
        if rng.random() < 0.35:
            continue
        base = BASE_DAILY.get(r["category"], 1) * rng.uniform(0.5, 1.5)
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
        stores = sorted(set(data.get("stores", [])) | {store_id})
        legacy = {s: "owner" for s in data.get("stores", [])}          # memberships recorded before roles existed
        d.reference.set({"stores": stores, "roles": {**legacy, **(data.get("roles") or {}), store_id: "owner"}}, merge=True)
        n += 1
    return n


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--store", required=True)
    ap.add_argument("--name", required=True)
    ap.add_argument("--owner-email", action="append", default=[])
    ap.add_argument("--seed", type=int, default=1, help="different seeds give different product subsets")
    ap.add_argument("--limit", type=int, default=300)
    ap.add_argument("--file", help="use a local copy of the dataset instead of downloading")
    ap.add_argument("--categories", help="comma-separated BigBasket categories to draw from (default: all)")
    ap.add_argument("--no-embed", action="store_true")
    a = ap.parse_args()

    src = Path(a.file) if a.file else download()
    OUT.mkdir(parents=True, exist_ok=True)
    wanted = {c.strip() for c in a.categories.split(",")} if a.categories else None
    rows = to_rows(sample(src, a.limit, a.seed, wanted), a.seed)
    products_csv, sales_csv = OUT / f"{a.store}-products.csv", OUT / f"{a.store}-sales.csv"
    with products_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(rows)
    sales = sales_rows(rows, a.seed)
    with sales_csv.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["sku", "day", "qty"])
        w.writeheader()
        w.writerows(sales)
    print(f"{a.store}: {len(rows)} products across {len({r['category'] for r in rows})} categories, {len(sales)} sales rows -> {OUT}")

    mapping = {c: c for c in COLUMNS}
    cmd = [sys.executable, str(HERE / "import_dataset.py"), "--file", str(products_csv), "--store", a.store, "--name", a.name,
           "--sales", str(sales_csv), "--limit", str(a.limit), "--mapping", __import__("json").dumps(mapping)]
    for e in a.owner_email:
        cmd += ["--owner-email", e]
    subprocess.run(cmd, check=True)

    if not a.no_embed:
        from seed import seed_embeddings
        seed_embeddings(a.store)
    for e in a.owner_email:
        print(f"attached to {attach_existing_account(a.store, e)} existing dashboard account(s) for {e}")
    print("done. Next: cd backend && .venv/bin/python -m app.jobs.forecast --store", a.store)


if __name__ == "__main__":
    main()
