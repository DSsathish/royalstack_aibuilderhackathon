from app.domain import classify


def test_storage_rules():
    chilled = ["Aavin Toned Milk 500ml", "Amul Butter 100 g", "Fresh Chicken Breast", "Real Apple Juice 1L", "Nandini Curd", "Amul Cheese Slices", "Country Eggs 6"]
    ambient = ["Amul Milk Powder", "Parle-G Biscuits", "Britannia Butter Cookies", "Chicken Masala", "Ponni Rice 5kg", "Coconut Milk 200ml", "Dabur Honey", "Milk Chocolate Bar", "Sofit Soya Milk 1L"]
    frozen = ["McCain Frozen French Fries", "Amul Vanilla Ice Cream", "Frozen Green Peas"]
    assert all(classify.storage_of(n) == "chilled" for n in chilled), [n for n in chilled if classify.storage_of(n) != "chilled"]
    assert all(classify.storage_of(n) == "ambient" for n in ambient), [n for n in ambient if classify.storage_of(n) != "ambient"]
    assert all(classify.storage_of(n) == "frozen" for n in frozen), [n for n in frozen if classify.storage_of(n) != "frozen"]
    assert classify.storage_of("Paneer 200g", category="Dairy") == "chilled"
    assert classify.storage_of("Peanut Butter", category="Bakery, Cakes & Dairy") == "ambient"


def test_use_rules_and_query_intent():
    assert classify.use_of("Pedigree Adult Dog Food 3kg") == "pet"
    assert classify.use_of("Whiskas Cat Food", category="Kitchen, Garden & Pets") == "pet"
    assert classify.use_of("Parle-G Biscuits") == "human"
    assert classify.use_of("Surf Excel Detergent 1kg") == "household"
    assert classify.use_of("Dove Shampoo 340ml") == "personal_care"
    assert classify.use_of("Face Cream", category="Beauty & Hygiene") == "personal_care"
    assert classify.query_use("biscuits") is None and classify.query_use("dog biscuits") == "pet"
    assert classify.query_use("cat food") == "pet" and classify.query_use("floor cleaner") == "household" and classify.query_use("milk") is None


def test_storage_blocks():
    fm = [{"aisle": "A1", "kind": "aisle"}]
    assert classify.block_for(fm, "chilled") is None
    fm2 = classify.ensure_storage_blocks(fm)
    assert [b["aisle"] for b in fm2] == ["A1", "Chiller", "Freezer"] and classify.block_for(fm2, "chilled") == "Chiller" and classify.block_for(fm2, "frozen") == "Freezer"
    assert classify.ensure_storage_blocks(fm2) == fm2


def test_whole_words_and_apparel_never_match_food_or_pet_rules():
    for name in ("Roadster Men Blue Chambray Shirt", "Women Black Leggings", "Lambswool Sweater", "Fishnet Stockings", "Cat Eye Sunglasses", "Petite Fit Jeans"):
        assert classify.storage_of(name, category="Men's Wear") == "ambient", name
        assert classify.use_of(name, category="Women's Wear") == "human", name
    assert classify.storage_of("Chambray Shirt") == "ambient" and classify.use_of("Petite Jeans") == "human"
    assert classify.use_of("Cat Eye Sunglasses") == "human"
