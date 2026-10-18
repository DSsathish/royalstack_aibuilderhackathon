"""Audit a store's classification and placement against the rules, and fix the data when asked (docs/lld/taxonomy.md).

  backend/.venv/bin/python infra/scripts/audit_catalog.py --store dailygoods            # report only
  backend/.venv/bin/python infra/scripts/audit_catalog.py --store dailygoods --fix      # catalog file, store, upload files

The report lists, per product, the storage, use and block the rules give against the catalog file and the store, plus
names that contradict their category. --fix rewrites the catalog file's aisle, bay, shelf and side, sets the store's
floor plan to the labelled layout, updates every product's storage and use, rewrites every location, and regenerates
the upload files. Deterministic: a second run changes nothing.
"""

import argparse
import csv
import io
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app.connectors import schema  # noqa: E402
from app.connectors.csv_connector import slug  # noqa: E402
from app.domain import classify, taxonomy  # noqa: E402
from app.domain.models import Location  # noqa: E402
from app.services import catalog, db  # noqa: E402

SEED = ROOT / "infra" / "seed"
# a name that says one thing while the category says another
HINTS = {
    "A5": ("chair", "sofa", "table", "bed ", "wardrobe", "mattress", "bulb", "lamp", "light ", "night light", "kettle", "mixer", "cooker", "pan ", "kadai"),
    "A4": ("broom", "mop", "detergent", "toilet cleaner", "floor cleaner", "dog ", "cat ", "pet ", "agarbatti", "camphor", "garbage bag"),
    "Fashion": ("shoe", "sandal", "slipper", "nightwear", "t-shirt", "tshirt", "jeans", "saree", "kurta", "leggings", "socks", "vest", "briefs"),
    "A2": ("laddu", "mysore pak", "soan papdi", "gulab jamun", "chips", "biscuit", "cookies", "chocolate", "namkeen", "murukku", "tea ", "coffee", "juice", "cola"),
    "A3": ("shampoo", "toothpaste", "face wash", "deodorant", "diaper", "sanitary", "lotion"),
    "Produce": ("tomato", "onion", "potato", "banana", "apple", "mango", "spinach", "coriander"),
}


def hinted_block(name: str) -> str | None:
    n = " " + name.lower() + " "
    for block, words in HINTS.items():
        if any(w in n for w in words):
            return block
    return None


def audit(store_id: str, csv_path: Path, fix: bool) -> dict:
    floor = [a.model_dump() for a in taxonomy.FLOOR_MAP]
    with csv_path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        fields, rows = reader.fieldnames, list(reader)
    stored = {d.id: d.to_dict() for d in db.products(store_id).select(["name", "category", "subcategory", "storage", "use", "tags"]).stream()}
    located = {d.id: d.to_dict() for d in db.locations(store_id).stream()}
    changes = Counter()
    suspects, moves = [], Counter()
    plan = {}
    for r in rows:
        pid = f"{store_id}-{slug(r['sku'])}"
        tags = [t for t in (r.get("tags") or "").split("|") if t]
        storage = classify.storage_of(r["name"], r["category"], r["subcategory"], tags)
        use = classify.use_of(r["name"], r["category"], r["subcategory"], tags)
        spot = taxonomy.place(floor, category=r["category"], subcategory=r["subcategory"], storage=storage, name=r["name"])
        if spot is None:
            changes["unplaced"] += 1
            continue
        if r["aisle"] != spot["aisle"]:
            moves[(r["aisle"] or "none", spot["aisle"])] += 1
            changes["file_aisle"] += 1
        cur = stored.get(pid)
        if cur:
            if cur.get("storage") != storage:
                changes["store_storage"] += 1
            if cur.get("use") != use:
                changes["store_use"] += 1
            loc = located.get(pid)
            if not loc or loc.get("aisle") != spot["aisle"]:
                changes["store_aisle"] += 1
        hint = hinted_block(r["name"])
        dept = taxonomy.department_for(r["category"], r["subcategory"])
        if hint and dept and hint != dept[0] and not taxonomy.STORAGE_BLOCK.get(storage):
            suspects.append((r["name"], r["category"], r["subcategory"], "name suggests " + taxonomy.LABELS.get(hint, hint)))
        plan[pid] = (r, storage, use, spot)
    report = {"products": len(rows), "changes": dict(changes), "moves": {f"{a} -> {b}": n for (a, b), n in moves.most_common()}, "suspects": suspects[:40]}
    if not fix:
        return report
    # 1. the catalog file
    for pid, (r, storage, use, spot) in plan.items():
        r.update({"aisle": spot["aisle"], "bay": str(spot["bay"]), "shelf": str(spot["shelf"]), "side": spot["side"]})
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields); w.writeheader(); w.writerows(rows)
    # 2. the store: floor plan, product classification, locations
    db.store_ref(store_id).update({"floor_map": floor})
    batch, n = db.client().batch(), 0
    for pid, (r, storage, use, spot) in plan.items():
        if pid not in stored:
            continue
        batch.update(db.products(store_id).document(pid), {"storage": storage, "use": use}); n += 1
        batch.set(db.locations(store_id).document(pid), Location(product_id=pid, store_id=store_id, **spot).model_dump()); n += 1
        if n >= 400:
            batch.commit(); batch, n = db.client().batch(), 0
    if n:
        batch.commit()
    catalog.bump(store_id)
    # 3. the upload files
    import openpyxl
    wb = openpyxl.load_workbook(io.BytesIO(schema.template_xlsx())); ws = wb["Inventory"]
    for r in rows:
        ws.append([r.get(h, "") for h in schema.headers()])
    wb.save(SEED / "DailyGoods inventory.xlsx")
    report["fixed"] = True
    return report


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--store", required=True)
    ap.add_argument("--csv", default=str(SEED / "products.csv"))
    ap.add_argument("--fix", action="store_true")
    a = ap.parse_args()
    out = audit(a.store, Path(a.csv), a.fix)
    print({k: v for k, v in out.items() if k != "suspects"})
    for s in out["suspects"]:
        print("  suspect:", s)
