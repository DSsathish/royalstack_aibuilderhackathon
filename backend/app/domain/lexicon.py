"""Words the deterministic classifiers look for, by language, in one place. English carries the full lists used when
products are classified at import; Tamil and Hindi carry the words shoppers use when they ask, so a pet query in those
languages is still a pet query. Add a language by adding a key; nothing else changes."""

PET = {
    "en": ("dog ", "dogs", "puppy", "cat ", "cats", "kitten", "pet ", "pets", "aquarium", "fish food", "bird food", "bird seed",
           "pedigree", "whiskas", "royal canin", "drools", "cat food", "dog food", "cat litter", "chew stick", "pet toy",
           "animal feed", "cattle feed"),
    "ta": ("நாய்", "நாய்க்கு", "நாய்கள்", "பூனை", "பூனைக்கு", "செல்லப்பிராணி"),
    "hi": ("कुत्ता", "कुत्ते", "कुत्तों", "बिल्ली", "पालतू"),
}


def words(table: dict[str, tuple[str, ...]]) -> tuple[str, ...]:
    """All languages' words as one tuple, for the matchers."""
    return tuple(w for ws in table.values() for w in ws)


# Packaging and unit words describe the pack, not the product: "chocolate bar" is about chocolate, "milk 1l" about milk.
FORM_WORDS = frozenset({"pack", "packet", "pouch", "pc", "pcs", "piece", "pieces", "set", "combo", "box", "tin", "can", "jar",
                        "bottle", "bar", "roll", "tube", "sachet", "strip", "tablet", "kg", "g", "gm", "gram", "ml", "l", "ltr",
                        "litre", "liter", "cm", "mm", "inch", "x"})
