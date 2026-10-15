"""Reset the demo store to a clean state before a recording or a judging session.

    cd backend && .venv/bin/python ../infra/scripts/reset_demo.py --store demo-grocery [--keep-drafts]

Restores seed stock, clears carts, sessions, orders, verifications, counts, demand signals and (unless kept) purchase-order
drafts for the store. Products, forecasts, suppliers, owner emails and audit entries are left alone.
"""

import argparse
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent.parent / "backend"))

from google.cloud.firestore_v1 import FieldFilter  # noqa: E402

from app.services import db  # noqa: E402


def delete_all(query, label: str) -> int:
    n = 0
    batch = db.client().batch()
    for doc in query.stream():
        batch.delete(doc.reference)
        n += 1
        if n % 400 == 0:
            batch.commit()
            batch = db.client().batch()
    batch.commit()
    print(f"  {label}: {n} deleted")
    return n


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--store", default="demo-grocery")
    ap.add_argument("--keep-drafts", action="store_true")
    a = ap.parse_args()
    s = a.store
    print(f"resetting {s}")
    delete_all(db.sessions().where(filter=FieldFilter("store_id", "==", s)), "sessions")
    delete_all(db.carts().where(filter=FieldFilter("store_id", "==", s)), "carts")
    delete_all(db.orders().where(filter=FieldFilter("store_id", "==", s)), "orders")
    delete_all(db.verifications().where(filter=FieldFilter("store_id", "==", s)), "verifications")
    delete_all(db.counts(s), "quick counts")
    delete_all(db.demand_signals(s), "demand signals")
    if not a.keep_drafts:
        delete_all(db.po_drafts(s), "purchase-order drafts")
    # restore stock from the seed CSV (products/locations untouched except on_hand and reorder defaults)
    seed = HERE.parent / "seed" / "seed.py"
    subprocess.run([sys.executable, str(seed), "--store", s, "--skip-bq"], check=True, cwd=str(HERE.parent.parent / "backend"))
    # clear reservations left by abandoned carts
    batch, n = db.client().batch(), 0
    for doc in db.inventory(s).stream():
        if doc.to_dict().get("reserved"):
            batch.update(doc.reference, {"reserved": 0}); n += 1
    batch.commit()
    print(f"  reservations cleared: {n}")
    print("done")


if __name__ == "__main__":
    main()
