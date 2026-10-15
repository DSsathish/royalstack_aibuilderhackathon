"""Import a real product dataset (Kaggle or any CSV export) into a store using the normalizer.

    cd backend && .venv/bin/python ../infra/seed/import_dataset.py --file ../infra/seed/data/products.csv --store kaggle-grocery \
        [--sales ../infra/seed/data/sales.csv] [--owner-email you@example.com] [--limit 2000] [--mapping '{"sku":"product_id",...}']

Steps: propose a mapping with the normalizer (or use --mapping) -> apply it with the CSV connector -> synthesise what
public datasets lack (barcodes, aisles, suppliers) -> optional sales history into BigQuery for the forecast job.
"""

import argparse
import csv
import hashlib
import io
import json
import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent.parent / "backend"))

from app.connectors import csv_connector as csvc  # noqa: E402
from app.connectors import normalizer  # noqa: E402
from app.domain.models import Inventory, Location, Store, Supplier  # noqa: E402
from app.services import db  # noqa: E402
from seed import FLOOR_MAP, seed_bigquery_rows  # noqa: E402

AISLES = [a.aisle for a in FLOOR_MAP]


def ean13(seed: str) -> str:
    body = "890" + str(int(hashlib.sha1(seed.encode()).hexdigest(), 16) % 10**9).zfill(9)
    total = sum(int(d) * (1 if i % 2 == 0 else 3) for i, d in enumerate(body))
    return body + str((10 - total % 10) % 10)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", required=True)
    ap.add_argument("--store", default="kaggle-grocery")
    ap.add_argument("--name", default="Kaggle Grocery (real dataset)")
    ap.add_argument("--sales", help="optional CSV with product_id/day/qty columns (any names; normalised)")
    ap.add_argument("--owner-email", action="append", default=[])
    ap.add_argument("--limit", type=int, default=5000, help="max products to import")
    ap.add_argument("--mapping", help="JSON mapping to skip the normalizer")
    a = ap.parse_args()

    raw = Path(a.file).read_bytes()
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig", errors="replace")))
    header = reader.fieldnames or []
    samples = [row for _, row in zip(range(5), reader)]
    if a.mapping:
        mapping = json.loads(a.mapping)
    else:
        proposal = normalizer.propose(header, samples)
        print(f"proposal ({proposal.source}, confidence {proposal.confidence}): {json.dumps(proposal.mapping)}")
        for n in proposal.notes:
            print("  note:", n)
        for q in proposal.questions:
            print("  question:", q)
        mapping = proposal.mapping
    missing = [f for f in csvc.REQUIRED if f not in mapping]
    if missing:
        sys.exit(f"cannot import: required fields not mapped {missing}. Pass --mapping to fix.")

    # limit rows before parsing
    lines = raw.decode("utf-8-sig", errors="replace").splitlines()
    data = "\n".join(lines[: a.limit + 1]).encode()
    rows, errors = csvc.parse(data, mapping)
    print(f"parsed {len(rows)} rows, {len(errors)} row errors")

    store = Store(store_id=a.store, name=a.name, floor_map=FLOOR_MAP, owner_emails=[e.lower() for e in a.owner_email])
    payload = store.model_dump()
    if not a.owner_email:
        payload.pop("owner_emails")
    db.store_ref(a.store).set(payload, merge=True)
    res = csvc.upsert(a.store, rows, high_value_threshold=store.high_value_threshold)
    print(f"products: created={res.created} updated={res.updated}")

    # synthesise barcodes, aisles and suppliers where the dataset has none
    categories = sorted({r.category for r in rows if r.category}) or ["General"]
    aisle_of = {c: AISLES[i % len(AISLES)] for i, c in enumerate(categories)}
    sup_of = {c: "sup-" + "".join(ch if ch.isalnum() else "-" for ch in c.lower())[:30] for c in categories}
    for c in categories:
        db.suppliers(a.store).document(sup_of[c]).set(Supplier(supplier_id=sup_of[c], store_id=a.store, name=f"{c} supplier", lead_time_days=3).model_dump())
    batch, n = db.client().batch(), 0
    for i, r in enumerate(rows):
        pid = f"{a.store}-{csvc.slug(r.sku)}"
        c = r.category or "General"
        updates = {}
        if not r.barcode:
            updates["barcode"] = ean13(pid)
        if updates:
            batch.update(db.products(a.store).document(pid), updates)
        if not r.aisle:
            batch.set(db.locations(a.store).document(pid), Location(product_id=pid, store_id=a.store, aisle=aisle_of[c], bay=i % 4 + 1, shelf=i % 3 + 1, side="left" if i % 2 == 0 else "right").model_dump())
        if not r.supplier_id:
            batch.update(db.inventory(a.store).document(pid), {"supplier_id": sup_of[c]})
        n += 3
        if n >= 400:
            batch.commit(); batch, n = db.client().batch(), 0
    if n:
        batch.commit()
    print(f"synthesised barcodes/aisles/suppliers for {len(rows)} products across {len(categories)} categories")

    if a.sales:
        sraw = Path(a.sales).read_bytes().decode("utf-8-sig", errors="replace")
        sreader = csv.DictReader(io.StringIO(sraw))
        sh = sreader.fieldnames or []
        pick = lambda names: next((h for h in sh if normalizer._norm(h) in names), None)
        col_p, col_d, col_q = pick({"product_id", "product", "sku", "item", "item code"}), pick({"day", "date", "order date"}), pick({"qty", "quantity", "units", "sales"})
        if not (col_p and col_d and col_q):
            sys.exit(f"sales file needs product/date/qty columns, found {sh}")
        out = []
        price_of = {f"{a.store}-{csvc.slug(r.sku)}": r.price for r in rows}
        for row in sreader:
            pid = f"{a.store}-{csvc.slug(row[col_p])}"
            if pid in price_of:
                out.append({"store_id": a.store, "product_id": pid, "day": row[col_d][:10], "channel": "store", "qty": int(float(row[col_q] or 0)), "unit_price": price_of[pid]})
        print(f"sales rows: {len(out)}")
        seed_bigquery_rows(a.store, out)
    print("done. Next: python -m app.jobs.forecast --store", a.store)


if __name__ == "__main__":
    main()
