"""Expand products.csv: keep every existing product and SKU, add the catalogue in catalog_food.py and catalog_nonfood.py,
extend the schema (pack_size, cost_price, gst_rate, shelf_life_days, status, origin, data_status), and write a report.

    python infra/seed/make_catalog.py            # rewrites products.csv in place (backup in products.before-expansion.csv)

Rules: no duplicates (brand + name + size), existing names, prices and ids untouched, old categories mapped to the new
taxonomy, synthetic values clearly labelled in data_status, nothing claimed that is not known."""

import csv
import hashlib
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
import catalog_food as food  # noqa: E402
import catalog_nonfood as nonfood  # noqa: E402

SRC = HERE / "products.csv"
BACKUP = HERE / "products.before-expansion.csv"
REPORT = HERE / "catalog_report.md"
COLUMNS = ["sku", "name", "brand", "category", "subcategory", "price", "mrp", "unit", "tags", "on_hand", "substitutes", "barcode", "aisle", "bay",
           "shelf", "side", "supplier_id", "reorder_point", "reorder_qty", "lead_time_days", "image_url",
           "pack_size", "cost_price", "gst_rate", "shelf_life_days", "status", "origin", "data_status"]

# old category / subcategory -> new main category, subcategory
OLD_MAP = {
    ("Staples", "Rice"): (food.MAIN, "Grains, Rice and Cereals"), ("Staples", "Flour"): (food.MAIN, "Flours and Baking Ingredients"),
    ("Staples", "Pulses"): (food.MAIN, "Pulses and Legumes"), ("Staples", "Spices"): (food.MAIN, "Spices and Seasonings"),
    ("Staples", "Salt"): (food.MAIN, "Spices and Seasonings"), ("Staples", "Sugar"): (food.MAIN, "Cooking Essentials"),
    ("Oils & Ghee", None): (food.MAIN, "Cooking Essentials"), ("Dairy", "Eggs"): (food.MAIN, "Eggs"), ("Dairy", None): (food.MAIN, "Dairy Products"),
    ("Bakery", None): (food.MAIN, "Bakery and Breads"), ("Beverages", None): (food.MAIN, "Beverages"), ("Snacks", None): (food.MAIN, "Snacks"),
    ("Sweets", None): (food.MAIN, "Sweets and Desserts"), ("Frozen", None): (food.MAIN, "Frozen Foods"),
    ("Fruits & Vegetables", "Fruits"): (food.MAIN, "Fresh Fruits"), ("Fruits & Vegetables", None): (food.MAIN, "Fresh Vegetables"),
    ("Personal Care", "Hair"): ("Personal Care and Hygiene", "Hair Care"), ("Personal Care", "Deo"): ("Personal Care and Hygiene", "Fragrances"),
    ("Personal Care", "Feminine"): ("Personal Care and Hygiene", "Personal Hygiene and Wellness"), ("Personal Care", "Hygiene"): ("Personal Care and Hygiene", "Toiletries and Bath Products"),
    ("Personal Care", "Care"): ("Personal Care and Hygiene", "Skin Care"), ("Personal Care", None): ("Personal Care and Hygiene", "Toiletries and Bath Products"),
    ("Household", "Dish"): ("Household Cleaning and Maintenance", "Kitchen Cleaning"), ("Household", "Kitchen"): ("Household Cleaning and Maintenance", "Kitchen Cleaning"),
    ("Household", "Laundry"): ("Household Cleaning and Maintenance", "Laundry and Fabric Care"), ("Household", "Insect"): ("Household Cleaning and Maintenance", "Pest Control"),
    ("Household", "Electrical"): ("Household Cleaning and Maintenance", "Home Maintenance"), ("Household", None): ("Household Cleaning and Maintenance", "General Household Cleaning"),
    ("Baby", "Formula"): ("Baby and Infant Products", "Baby Feeding and Clothing"), ("Baby", "Food"): ("Baby and Infant Products", "Baby Feeding and Clothing"),
    ("Baby", None): ("Baby and Infant Products", "Baby Care"), ("Pharmacy", "First aid"): ("Health and First Aid", "First Aid"),
    ("Pharmacy", None): ("Health and First Aid", "Wellness and Protection"), ("Pet", None): ("Pet Products", "Pet Food"),
}
REGULATED_SUBS = {"Fever", "Digestive", "Cold"}         # over-the-counter medicines in the old list: keep, but flag


def map_old(category: str, subcategory: str) -> tuple[str, str]:
    return OLD_MAP.get((category, subcategory)) or OLD_MAP.get((category, None)) or (category, subcategory)


def internal_barcode(sku: str) -> str:
    """An in-store code: GS1 restricted-circulation prefix 20, then digits from the SKU, then the EAN-13 check digit.
    Never a real GTIN; the owner replaces it with the supplier's barcode through sync or add-by-scan."""
    body = "20" + str(int(hashlib.sha1(sku.encode()).hexdigest(), 16) % 10**10).zfill(10)
    total = sum(int(d) * (1 if i % 2 == 0 else 3) for i, d in enumerate(body))
    return body + str((10 - total % 10) % 10)


_CODES: dict[str, str] = {}      # code -> text that owns it, so "Fresh Fruits" and "Fresh Vegetables" never share a code


def code(text: str, n: int) -> str:
    words = re.findall(r"[A-Za-z]+", text)
    base = ("".join(w[0] for w in words)[:n] if len(words) >= n else re.sub(r"[^A-Za-z]", "", text)[:n]).upper()
    candidate = base
    for suffix in ("", *"ABCDEFGHJKLMNPQRSTUVWXYZ"):
        candidate = (base[: n - 1] + suffix) if suffix else base
        if _CODES.get(candidate, text) == text:
            _CODES[candidate] = text
            return candidate
    raise SystemExit(f"no free code for {text}")


def sample_stock(sku: str) -> int:
    h = int(hashlib.md5(sku.encode()).hexdigest(), 16)
    return 0 if h % 100 < 6 else 8 + h % 53


def aisle_for(main: str, sub: str, storage_hint: str) -> str:
    if storage_hint == "chilled":
        return "Chiller"
    if storage_hint == "frozen":
        return "Freezer"
    table = {food.MAIN: "A1", "Personal Care and Hygiene": "A4", "Household Cleaning and Maintenance": "A4", "Baby and Infant Products": "A5",
             "Health and First Aid": "A5", "Pet Products": "A6", "Home and Kitchen Essentials": "A2", "Pooja and Religious Products": "A3"}
    if main == food.MAIN and sub in ("Snacks", "Beverages", "Sweets and Desserts", "Bakery and Breads", "Pickles, Preserves and Condiments"):
        return "A3"
    if main == food.MAIN and sub in ("Fresh Vegetables", "Fresh Fruits"):
        return "A6"
    return table.get(main, "A2")


def expand(main: str, sub: str, entry: str, meta: tuple, seen: set, counter: Counter) -> list[dict]:
    brand, name, sizes, prices = (entry.split("|") + ["", ""])[:4]
    gst, shelf, unit = meta
    sizes = [s.strip() for s in sizes.split("/")] if sizes.strip() else [""]
    prices = [p.strip() for p in prices.split("/")] if prices.strip() else [""]
    if len(prices) != len(sizes):
        raise SystemExit(f"{main}/{sub}: sizes and prices differ for {entry!r}")
    rows = []
    for size, price in zip(sizes, prices):
        shown = "" if size in ("1 pc", "1 set", "1 pair") else size            # "Pressure Cooker 3 L", not "Pressure Cooker 3 L 1 pc"
        full = f"{brand} {name} {shown}".strip() if brand not in ("Local", "Unbranded") else f"{name} {shown}".strip()
        full = re.sub(r"\s+", " ", full)
        key = (brand.lower(), name.lower(), size.lower())
        if key in seen:
            counter["duplicate_in_catalogue"] += 1
            continue
        seen.add(key)
        counter[sub] += 1
        sku = f"{code(main, 3)}-{code(sub, 3)}-{counter[sub]:03d}"
        from app.domain import classify  # noqa: E402  (storage decides chiller or freezer placement)
        storage = classify.storage_of(full, main, sub)
        rows.append({
            "sku": sku, "name": full, "brand": "" if brand in ("Local", "Unbranded") else brand, "category": main, "subcategory": sub,
            "price": price, "mrp": price, "unit": unit if size and not re.search(r"\d", size) else ("kg" if size.endswith("kg") and unit == "kg" else unit),
            "tags": "", "on_hand": sample_stock(sku), "substitutes": "", "barcode": internal_barcode(sku), "aisle": aisle_for(main, sub, storage),
            "bay": counter[sub] % 4 + 1, "shelf": counter[sub] % 3 + 1, "side": "left" if counter[sub] % 2 else "right", "supplier_id": "",
            "reorder_point": 5 if shelf else 2, "reorder_qty": 20 if shelf else 5, "lead_time_days": 3, "image_url": "",
            "pack_size": size, "cost_price": "", "gst_rate": gst, "shelf_life_days": shelf if shelf else "", "status": "seasonal" if "seasonal" in name.lower() else "active",
            "origin": "", "data_status": "sample-price;sample-stock;internal-barcode;pending-cost;pending-supplier" + (";indicative-gst" if gst is not None else ""),
        })
    return rows


def main() -> None:
    sys.path.insert(0, str(HERE.parent.parent / "backend"))
    if not BACKUP.exists():
        BACKUP.write_text(SRC.read_text(encoding="utf-8"), encoding="utf-8")
    existing = list(csv.DictReader(BACKUP.open(encoding="utf-8")))      # always expand from the original file, so re-runs are idempotent
    seen = set()
    out, changed = [], Counter()
    for r in existing:
        main_cat, sub = map_old(r["category"], r["subcategory"])
        if (main_cat, sub) != (r["category"], r["subcategory"]):
            changed["recategorised"] += 1
        row = {c: r.get(c, "") for c in COLUMNS}
        row["category"], row["subcategory"] = main_cat, sub
        flags = ["real-brand-sample-price", "sample-stock", "synthetic-barcode", "pending-cost"]
        if r["subcategory"] in REGULATED_SUBS:
            flags.append("regulated-otc-medicine")
        row["data_status"] = ";".join(flags)
        row["status"] = row.get("status") or "active"
        m = re.search(r"(\d+(?:\.\d+)?)\s*(kg|g|ml|l|pcs|pc)\b", r["name"], re.I)
        row["pack_size"] = row.get("pack_size") or (f"{m.group(1)} {m.group(2).lower()}" if m else "")
        gst_meta = food.META.get(sub) or nonfood.META.get((main_cat, sub))
        row["gst_rate"] = row.get("gst_rate") or (gst_meta[0] if gst_meta else "")
        row["shelf_life_days"] = row.get("shelf_life_days") or (gst_meta[1] if gst_meta and gst_meta[1] else "")
        seen.add((r["brand"].lower(), re.sub(r"\s*\d+(?:\.\d+)?\s*(kg|g|ml|l|pcs|pc)\b", "", r["name"].replace(r["brand"], "").strip(), flags=re.I).lower().strip(), (row["pack_size"] or "").lower()))
        out.append(row)
    counter: Counter = Counter()
    added = []
    for sub, entries in food.ITEMS.items():
        for e in entries:
            added += expand(food.MAIN, sub, e, food.META[sub], seen, counter)
    for (main_cat, sub), entries in nonfood.ITEMS.items():
        for e in entries:
            added += expand(main_cat, sub, e, nonfood.META[(main_cat, sub)], seen, counter)
    # a catalogue entry that matches an existing product by brand and name (any size) is not added twice
    existing_names = {re.sub(r"\s*\d+(?:\.\d+)?\s*(kg|g|ml|l|pcs|pc)\b", "", r["name"], flags=re.I).strip().lower() for r in existing}
    kept = []
    for row in added:
        bare = re.sub(r"\s*\d+(?:\.\d+)?\s*(kg|g|ml|l|pcs|pc|dozen|bunch|m|mm|cm|inch|ft|w|v|mah|ah|va)\b", "", row["name"], flags=re.I).strip().lower()
        if bare in existing_names:
            counter["duplicate_of_existing"] += 1
            continue
        kept.append(row)
    all_rows = out + kept
    skus = Counter(r["sku"] for r in all_rows)
    assert all(n == 1 for n in skus.values()), [s for s, n in skus.items() if n > 1]
    with SRC.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(all_rows)

    by_main = defaultdict(Counter)
    for r in all_rows:
        by_main[r["category"]][r["subcategory"]] += 1
    new_by_main = Counter(r["category"] for r in kept)
    missing_fields = Counter()
    for r in all_rows:
        for field in ("brand", "barcode", "cost_price", "supplier_id", "origin", "gst_rate", "shelf_life_days", "tags", "image_url"):
            if not r.get(field):
                missing_fields[field] += 1
    lines = ["# Catalogue expansion report", "",
             f"Existing products kept: {len(existing)} (ids, names and prices untouched; {changed['recategorised']} moved to the new category tree).",
             f"New products added: {len(kept)}. Catalogue entries skipped as duplicates: {counter['duplicate_of_existing']} matched an existing product, {counter['duplicate_in_catalogue']} repeated inside the catalogue.",
             f"Total products: {len(all_rows)} across {len(by_main)} main categories and {sum(len(v) for v in by_main.values())} subcategories.", "",
             "## Category summary (products per subcategory)", ""]
    for main_cat in sorted(by_main):
        lines.append(f"- **{main_cat}** ({sum(by_main[main_cat].values())}): " + ", ".join(f"{s} {n}" for s, n in sorted(by_main[main_cat].items())))
    lines += ["", "## New products per main category", ""] + [f"- {m}: {n}" for m, n in sorted(new_by_main.items())]
    lines += ["", "## Data quality", "",
              "- Prices: indicative Indian MRPs for demonstration (`sample-price`); existing products keep the prices they had. Selling price equals MRP for new items.",
              "- Stock quantities: deterministic sample values (`sample-stock`), 6% of new items at zero so low-stock views have content.",
              "- Barcodes: new items carry in-store codes with the GS1 restricted-circulation prefix 20 (`internal-barcode`); existing items keep their synthetic 890 codes (`synthetic-barcode`). Neither is a real GTIN; replace through sync or add-by-scan.",
              "- GST rates are the usual slab for the subcategory (`indicative-gst`); confirm with your accountant before invoicing.",
              "- Shelf life is a typical value per subcategory; durable goods have none. Expiry and batch tracking per lot is not in this inventory.",
              "- Storage class (ambient, chilled, frozen) and intended use (people, pets, household, personal care) are derived by the classifier at import; chilled and frozen items are placed in the Chiller and Freezer blocks.",
              "- Over-the-counter medicines from the original list are flagged `regulated-otc-medicine`; keep them subject to local rules.",
              "- Seasonal fruit and festive items are marked `seasonal` in status when the name says so.",
              "", "## Pending information (count of products missing each field)", ""]
    lines += [f"- {k}: {n}" for k, n in missing_fields.most_common()]
    lines += ["", "## Change summary", "",
              "- Added columns: pack_size, cost_price, gst_rate, shelf_life_days, status, origin, data_status (the last is report-only and not imported).",
              "- Mapped the original 14 categories into the new taxonomy; names unchanged.",
              "- Existing rows: filled pack_size from the name, gst_rate and shelf_life_days from the subcategory defaults; everything else as before.",
              "- Backup of the original file: products.before-expansion.csv."]
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"products.csv: {len(existing)} kept + {len(kept)} added = {len(all_rows)}; report -> {REPORT.name}")


if __name__ == "__main__":
    main()
