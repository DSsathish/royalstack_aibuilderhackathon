"""Classify an existing store's products (storage: ambient/chilled/frozen; use: human/pet/household/personal care),
add Chiller and Freezer blocks to the floor map when the store has none, and move chilled and frozen products there.

    cd backend && .venv/bin/python ../infra/scripts/reclassify.py --store demo-grocery --yes
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "backend"))

from app.domain import classify  # noqa: E402
from app.domain.models import Location  # noqa: E402
from app.services import catalog, db  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--store", required=True)
    ap.add_argument("--yes", action="store_true")
    ap.add_argument("--no-blocks", action="store_true", help="classify only; do not add chiller and freezer blocks or move products")
    a = ap.parse_args()
    if not a.yes:
        sys.exit("add --yes to confirm")
    ref = db.store_ref(a.store)
    doc = ref.get().to_dict()
    if not doc:
        sys.exit("store not found")
    floor_map = doc.get("floor_map", [])
    products = {d.id: d.to_dict() for d in db.products(a.store).stream()}
    counts = {"chilled": 0, "frozen": 0, "pet": 0, "household": 0, "personal_care": 0}
    updates = {}
    for pid, p in products.items():
        storage = classify.storage_of(p.get("name", ""), p.get("category", ""), p.get("subcategory", ""), p.get("tags"))
        use = classify.use_of(p.get("name", ""), p.get("category", ""), p.get("subcategory", ""), p.get("tags"))
        if storage != "ambient":
            counts[storage] += 1
        if use != "human":
            counts[use] += 1
        if p.get("storage") != storage or p.get("use") != use:
            updates[pid] = {"storage": storage, "use": use}
    db.batched(list(updates), lambda b, pid: b.update(db.products(a.store).document(pid), updates[pid]), size=50)
    moved = 0
    cold_blocks = {b["aisle"] for b in floor_map if b.get("kind") in ("chiller", "freezer")}
    aisles = [b["aisle"] for b in floor_map if b.get("kind", "aisle") == "aisle"]
    if cold_blocks and aisles:                 # ambient products that an earlier pass put in a chiller go back to a shelf aisle
        back = 0
        for pid, p in products.items():
            storage = updates.get(pid, {}).get("storage", p.get("storage", "ambient"))
            loc = db.locations(a.store).document(pid).get().to_dict() or {}
            if storage == "ambient" and loc.get("aisle") in cold_blocks:
                db.locations(a.store).document(pid).set(Location(product_id=pid, store_id=a.store, aisle=aisles[back % len(aisles)], bay=back % 4 + 1, shelf=back % 3 + 1).model_dump())
                back += 1
        if back:
            print(f"moved {back} ambient products back to shelf aisles")
    if not a.no_blocks and not counts["chilled"] and not counts["frozen"] and cold_blocks:
        floor_map = [b for b in floor_map if b.get("kind") not in ("chiller", "freezer")]      # nothing cold here: no empty chiller on the map
        ref.update({"floor_map": floor_map})
    if not a.no_blocks and (counts["chilled"] or counts["frozen"]):
        new_map = classify.ensure_storage_blocks(floor_map)
        if new_map != floor_map:
            ref.update({"floor_map": new_map})
            floor_map = new_map
        bays = {"chilled": 0, "frozen": 0}
        for pid, p in products.items():
            storage = updates.get(pid, {}).get("storage", p.get("storage", "ambient"))
            block = classify.block_for(floor_map, storage)
            if not block:
                continue
            loc = db.locations(a.store).document(pid).get().to_dict() or {}
            if loc.get("aisle") == block:
                continue
            bays[storage] += 1
            db.locations(a.store).document(pid).set(Location(product_id=pid, store_id=a.store, aisle=block, bay=bays[storage] % 4 + 1, shelf=bays[storage] % 3 + 1, side="left" if bays[storage] % 2 == 0 else "right").model_dump())
            moved += 1
    catalog.bump(a.store)
    print(f"{a.store}: {len(products)} products, {len(updates)} reclassified, moved {moved} to chiller/freezer; counts {counts}; blocks {[b['aisle'] for b in floor_map]}")


if __name__ == "__main__":
    main()
