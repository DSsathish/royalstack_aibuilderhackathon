"""Departments and placement: the single chain product → category → subcategory → storage → department → floor block.
Design: docs/lld/taxonomy.md."""

import hashlib
import re

from app.domain.models import Aisle, Location

ALL = "*"
FOOD = "Grocery and Food Products"
DEPARTMENTS: tuple[tuple[str, str, dict[str, set[str] | str]], ...] = (
    ("A1", "Staples & Cooking", {FOOD: {"Grains, Rice and Cereals", "Flours and Baking Ingredients", "Pulses and Legumes", "Cooking Essentials",
                                        "Spices and Seasonings", "Pickles, Preserves and Condiments", "Tinned and Canned Foods", "Organic and Health Foods",
                                        "Vegan and Plant-Based Products", "Ready-to-Eat Foods", "Ready-to-Cook Foods"}}),
    ("A2", "Snacks, Beverages & Sweets", {FOOD: {"Snacks", "Beverages", "Sweets and Desserts", "Bakery and Breads"}}),
    ("A3", "Personal Care & Baby", {"Personal Care and Hygiene": ALL, "Baby and Infant Products": ALL}),
    ("A4", "Household, Pooja & Pets", {"Household Cleaning and Maintenance": ALL, "Disposable and Eco-Friendly Products": ALL,
                                       "Pooja and Religious Products": ALL, "Pet Products": ALL}),
    ("A5", "Home, Kitchen & Hardware", {"Home and Kitchen Essentials": ALL, "Home Decor and Lifestyle": ALL, "Furniture and Furnishings": ALL,
                                        "Hardware and DIY": ALL, "Garden and Outdoor Living": ALL, "Automobile Care and Accessories": ALL,
                                        "Electronics and Technology": ALL}),
    ("A6", "Stationery, Toys & Sports", {"Stationery, Books and Office Supplies": ALL, "Toys, Games and Hobbies": ALL, "Sports, Fitness and Outdoor": ALL,
                                         "Travel and Luggage": ALL, "Gift Items and Seasonal Products": ALL}),
    ("Produce", "Fresh Produce", {FOOD: {"Fresh Fruits", "Fresh Vegetables"}}),
    ("Fashion", "Clothing & Footwear", {"Clothing and Accessories": ALL}),
)
LABELS = {block: label for block, label, _ in DEPARTMENTS} | {"Chiller": "Chiller", "Freezer": "Freezer"}
STORAGE_BLOCK = {"chilled": "chiller", "frozen": "freezer"}      # storage → block kind
BAYS, SHELVES = 8, 4

FLOOR_MAP = [Aisle(aisle=block, label=label, x=60 + i * 105, y=80, w=85, h=420) for i, (block, label, _) in enumerate(DEPARTMENTS)] + [
    Aisle(aisle="Chiller", label="Chiller", x=905, y=80, w=75, h=200, kind="chiller"),
    Aisle(aisle="Freezer", label="Freezer", x=905, y=320, w=75, h=180, kind="freezer")]


def department_for(category: str, subcategory: str = "") -> tuple[str, str] | None:
    """(block id, label) for a category and subcategory, None when the taxonomy does not know the category."""
    sub = (subcategory or "").strip()
    for block, label, members in DEPARTMENTS:
        want = members.get((category or "").strip())
        if want is None:
            continue
        if want == ALL or sub in want:
            return block, label
    return None


def _stable(text: str, n: int) -> int:
    return int(hashlib.sha1(text.lower().encode()).hexdigest(), 16) % n


def place(floor_map: list[dict], *, category: str, subcategory: str = "", storage: str = "ambient", name: str = "") -> dict | None:
    """The shelf spot the rules give: the chiller or freezer block for cold products, else the department's block when
    the floor plan has it (by id or label). Bay, shelf and side spread by subcategory and name so a re-run lands the same."""
    blocks = list(floor_map or [])
    kind = STORAGE_BLOCK.get(storage)
    block = None
    if kind:
        block = next((b for b in blocks if b.get("kind") == kind), None)
    if block is None:
        dept = department_for(category, subcategory)
        if dept:
            block = next((b for b in blocks if b.get("aisle") == dept[0] or (b.get("label") or "") == dept[1]), None)
    if block is None:
        return None
    key = subcategory or category or name
    return {"aisle": block["aisle"], "bay": 1 + _stable(key, BAYS), "shelf": 1 + _stable(name or key, SHELVES), "side": "left" if _stable(name + key, 2) == 0 else "right"}


def location(store_id: str, product_id: str, spot: dict) -> Location:
    return Location(product_id=product_id, store_id=store_id, **spot)


# --- section names ------------------------------------------------------------------------------------------------

STOPWORDS = frozenset({"and", "the", "of", "all", "list", "full", "products", "product", "items", "item", "section"})


def stem(token: str) -> str:
    """Enough English stemming for section names, the same on both sides: healthy and health → health, dals → dal,
    groceries and grocery → grocer, pulses and pulse → puls, cleaning and clean → clean."""
    t = token
    if len(t) > 4 and t.endswith("ies"):
        t = t[:-3] + "y"
    if len(t) > 3 and t.endswith("s") and not t.endswith("ss"):
        t = t[:-1]
    if len(t) > 5 and t.endswith("ing"):
        t = t[:-3]
    if len(t) > 4 and t.endswith("y"):
        t = t[:-1]
    if len(t) > 4 and t.endswith("e"):
        t = t[:-1]
    return t


def tokens(text: str) -> list[str]:
    return [stem(t) for t in re.sub(r"[^a-z0-9 ]+", " ", (text or "").lower()).split() if t not in STOPWORDS and len(t) > 1]


# words shoppers use for a section that its name does not contain (stemmed with `stem`); product words such as "milk"
# or "chicken" are not here on purpose: those stay searches
ALIASES = {
    "Pulses and Legumes": ("dal", "pulse", "lentil", "legume", "paruppu"),
    "Fresh Vegetables": ("vegetable", "veg", "veggie", "greens", "keerai", "sabzi", "sabji"),
    "Fresh Fruits": ("fruit",),
    "Dairy Products": ("dairy",),
    "Fresh Meat and Seafood": ("meat", "seafood", "non veg", "nonveg"),
    "Frozen Foods": ("frozen",),
    "Bakery and Breads": ("bakery", "bread", "bake"),
    "Snacks": ("snack", "namkeen", "chip", "biscuit", "munchie"),
    "Sweets and Desserts": ("sweet", "dessert", "mithai", "chocolate"),
    "Beverages": ("beverage", "drink", "soft drink", "cool drink"),
    "Organic and Health Foods": ("health", "healthy", "organic", "diet", "wellness"),
    "Vegan and Plant-Based Products": ("vegan", "plant based", "plant"),
    "Pickles, Preserves and Condiments": ("pickle", "condiment", "sauce", "ketchup", "jam"),
    "Grains, Rice and Cereals": ("rice", "grain", "cereal", "millet"),
    "Flours and Baking Ingredients": ("flour", "atta", "maida", "rava"),
    "Spices and Seasonings": ("spice", "masala", "seasoning"),
    "Cooking Essentials": ("oil", "ghee", "sugar", "salt", "cooking"),
    "Ready-to-Eat Foods": ("ready to eat", "instant", "noodle"),
    "Ready-to-Cook Foods": ("ready to cook", "batter"),
    "Pet Food": ("pet food", "dog food", "cat food"),
    "Toys": ("toy",),
    "Baby Care": ("baby", "diaper", "infant"),
    "Hair Care": ("hair", "shampoo"),
    "Skin Care": ("skin", "face"),
    "Laundry and Fabric Care": ("laundry", "detergent", "washing"),
    "General Household Cleaning": ("cleaning", "cleaner", "household"),
    "Daily Pooja Essentials": ("pooja", "puja", "agarbatti", "incense"),
}
_ALIAS_INDEX = {stem(w): sub for sub, words in ALIASES.items() for w in [x for ws in words for x in [ws]]}
_ALIAS_PHRASES = {" ".join(stem(t) for t in ws.split()): sub for sub, words in ALIASES.items() for ws in words if " " in ws}


def section_matches(query: str, sections: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """Every (category, subcategory) the query names, scored on the combined name: the pairs with the most words in
    common win, a pair whose subcategory words matched is returned as that subcategory, one matched only on its
    category words as the whole category; else the section a known alias points at ("dals" -> Pulses and Legumes).
    Empty when the query does not read like a section."""
    want = tokens(query)
    if not want:
        return []
    best, best_hit = [], 0
    for category, sub in sorted(set(sections)):
        cat_t, sub_t = set(tokens(category)), set(tokens(sub))
        hit_sub = sum(1 for t in want if t in sub_t)
        hit = sum(1 for t in want if t in sub_t or t in cat_t)
        if not hit or hit / len(want) < 0.5:
            continue
        found = (category, sub) if hit_sub else (category, "")
        if hit > best_hit:
            best, best_hit = [found], hit
        elif hit == best_hit and found not in best:
            best.append(found)
    if best:
        return sorted(best)
    by_sub = {sub: cat for cat, sub in sections if sub}
    phrase = " ".join(want)
    for alias, sub in _ALIAS_PHRASES.items():
        if alias in phrase and sub in by_sub:
            return [(by_sub[sub], sub)]
    hits = [_ALIAS_INDEX[t] for t in want if t in _ALIAS_INDEX and _ALIAS_INDEX[t] in by_sub]
    if hits and len(hits) >= max(1, len(want) // 2):
        return [(by_sub[hits[0]], hits[0])]
    return []


def section_match(query: str, sections: list[tuple[str, str]]) -> tuple[str, str] | None:
    found = section_matches(query, sections)
    return found[0] if found else None
