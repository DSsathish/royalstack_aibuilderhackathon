"""Deterministic product classification from master data, applied at import, add-by-scan and sync and used by search.

storage: ambient | chilled | frozen decides where a product lives on the floor (aisle, chiller, freezer).
use: human | pet | household | personal_care keeps pet food out of a biscuit search and out of alternatives for people.
Rules are keyword lists over name, category, subcategory and tags; an owner can still move a product by hand."""

import re

from app.domain import lexicon
from typing import Literal

Storage = Literal["ambient", "chilled", "frozen"]
Use = Literal["human", "pet", "household", "personal_care"]

FROZEN = ("frozen", "ice cream", "icecream", "ice-cream", "kulfi", "popsicle", "frozen dessert", "ice lolly")
CHILLED = ("milk", "curd", "dahi", "yogurt", "yoghurt", "paneer", "cheese", "butter", "fresh cream", "whipping cream", "lassi",
           "buttermilk", "chaas", "egg", "chicken", "mutton", "lamb", "meat", "pork", "beef", "fish", "prawn", "shrimp", "crab",
           "sausage", "salami", "ham", "bacon", "tofu", "juice", "smoothie", "kombucha", "cold coffee", "probiotic", "khoa", "kheer")
NOT_CHILLED = ("milk powder", "powder", "coconut milk", "condensed milk", "milk chocolate", "milkshake", "peanut butter", "cocoa butter",
               "shea butter", "butter cookie", "butter biscuit", "butter cracker", "cheese ball", "cheese puff", "cheese cracker",
               "cheese popcorn", "cheese flavour", "cheese flavor", "egg noodle", "eggless", "egg tray", "egg boiler", "masala",
               "flavour", "flavor", "spread", "seasoning", "soya milk", "soy milk", "almond milk", "oat milk", "soya chunks", "juicer",
               "chicken nuggets", "fish food", "cat ", "dog ", "pet ", "shampoo", "soap", "lotion", "cream biscuit", "cream wafer")
PET = lexicon.words(lexicon.PET)      # every language in one place: app/domain/lexicon.py
HOUSEHOLD = ("detergent", "floor cleaner", "dishwash", "dish wash", "toilet cleaner", "mop", "broom", "phenyl", "repellent", "insect",
             "mosquito", "disinfectant", "bleach", "scrubber", "garbage bag", "air freshener", "glass cleaner", "laundry", "fabric conditioner")
PERSONAL = ("shampoo", "conditioner", "soap", "body wash", "toothpaste", "toothbrush", "face wash", "deodorant", "perfume", "lotion",
            "moisturiser", "moisturizer", "razor", "shaving", "sanitary", "diaper", "hair oil", "sunscreen", "lipstick", "nail polish",
            "talc", "hand wash", "mouthwash")


def _text(name: str, category: str = "", subcategory: str = "", tags: list[str] | None = None) -> str:
    return " " + " ".join([name, category, subcategory, *(tags or [])]).lower().replace("-", " ") + " "


APPAREL = ("wear", "apparel", "clothing", "fashion", "footwear", "accessories", "textile", "garment")


def _has(text: str, words: tuple[str, ...], loose: bool = False) -> bool:
    """Whole-word matches for the positive lists ("chambray" is not ham, "leggings" is not egg, "petite" is not pet);
    exclusion lists match loosely so "butter cookies" still excludes "butter cookie"."""
    if loose:
        return any(w.strip() in text for w in words)
    return any(re.search(r"(?<![a-z])" + re.escape(w.strip()) + r"(?![a-z])", text) for w in words)


NOT_PET = ("cat eye", "cateye", "hot dog", "dog tag", "catwalk", "cat walk", "pet bottle", "pet jar")


def _apparel(category: str, subcategory: str = "") -> bool:
    return _has(" " + f"{category} {subcategory}".lower() + " ", APPAREL)


def storage_of(name: str, category: str = "", subcategory: str = "", tags: list[str] | None = None) -> Storage:
    if _apparel(category, subcategory):
        return "ambient"
    t = _text(name, category, subcategory, tags)
    if _has(t, FROZEN):
        return "frozen"
    if _has(t, ("dairy", "meat", "fish", "poultry", "eggs")) and not _has(" " + name.lower() + " ", NOT_CHILLED, loose=True):
        return "chilled"
    n = " " + name.lower().replace("-", " ") + " "
    if _has(n, CHILLED) and not _has(n, NOT_CHILLED, loose=True):
        return "chilled"
    return "ambient"


def use_of(name: str, category: str = "", subcategory: str = "", tags: list[str] | None = None) -> Use:
    if _apparel(category, subcategory):
        return "human"
    t = _text(name, category, subcategory, tags)
    if _has(t, PET) and not _has(t, NOT_PET, loose=True):
        return "pet"
    if _has(t, HOUSEHOLD) or _has(" " + category.lower() + " ", ("cleaning", "household")):
        return "household"
    if _has(t, PERSONAL) or _has(" " + category.lower() + " ", ("beauty", "hygiene", "personal care")):
        return "personal_care"
    return "human"


def query_use(query: str) -> Use | None:
    """What the shopper asked for, when they said so: "dog biscuits" is pet, "biscuits" is unspecified (people first)."""
    q = " " + re.sub(r"[!-/:-@\[-`{-~]", " ", query.lower()) + " "      # ASCII punctuation only: Tamil and Hindi vowel signs must survive
    if _has(q, PET) and not _has(q, NOT_PET, loose=True):
        return "pet"
    if _has(q, HOUSEHOLD):
        return "household"
    if _has(q, PERSONAL):
        return "personal_care"
    return None


KIND_FOR_STORAGE = {"chilled": "chiller", "frozen": "freezer"}


def block_for(floor_map: list[dict], storage: str) -> str | None:
    """The name of the first floor-map block whose kind matches the storage class (chiller or freezer), else None."""
    kind = KIND_FOR_STORAGE.get(storage)
    if not kind:
        return None
    return next((b["aisle"] for b in floor_map if b.get("kind") == kind), None)


DEFAULT_BLOCKS = [{"aisle": "Chiller", "x": 880, "y": 80, "w": 90, "h": 200, "floor": 1, "kind": "chiller"},
                  {"aisle": "Freezer", "x": 880, "y": 320, "w": 90, "h": 180, "floor": 1, "kind": "freezer"}]


def ensure_storage_blocks(floor_map: list[dict]) -> list[dict]:
    """A floor map with at least one chiller and one freezer block, adding the defaults when missing."""
    out = list(floor_map)
    for block in DEFAULT_BLOCKS:
        if not any(b.get("kind") == block["kind"] for b in out):
            out.append(dict(block))
    return out
