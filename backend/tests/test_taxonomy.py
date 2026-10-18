import pytest
from fastapi.testclient import TestClient

from app.connectors import csv_connector as csvc
from app.domain import classify, taxonomy
from app.domain.models import Store
from app.main import app
from app.services import catalog, db

client = TestClient(app)
FOOD = "Grocery and Food Products"
FLOOR = [a.model_dump() for a in taxonomy.FLOOR_MAP]


@pytest.mark.parametrize("name,category,sub,storage", [
    ("Aavin Toned Milk 500ml", FOOD, "Dairy Products", "chilled"),
    ("Aavin Curd 500g", FOOD, "Dairy Products", "chilled"),
    ("Amul Cheese Slices 200 g", FOOD, "Dairy Products", "chilled"),
    ("Suguna Chicken Curry Cut 500 g", FOOD, "Fresh Meat and Seafood", "chilled"),
    ("Frozen Chicken Nuggets 500 g", FOOD, "Frozen Foods", "frozen"),
    ("Amul Vanilla Ice Cream 1L", FOOD, "Frozen Foods", "frozen"),
    ("Safal Frozen Green Peas 500 g", FOOD, "Ready-to-Cook Foods", "frozen"),
    ("McCain French Fries 420g", FOOD, "Ready-to-Cook Foods", "frozen"),
    ("Fresh Idli Dosa Batter 1 kg", FOOD, "Ready-to-Cook Foods", "chilled"),
    ("Tender Coconut Water 200ml", FOOD, "Beverages", "chilled"),
    ("Britannia Marie Gold 600g", FOOD, "Snacks", "ambient"),
    ("Ponni Boiled Rice 5kg", FOOD, "Grains, Rice and Cereals", "ambient"),
    ("Amul Milk Powder 500 g", FOOD, "Dairy Products", "chilled"),      # the subcategory decides: the shop shelves it with dairy
    ("Oatly Oat Milk 1 L", FOOD, "Vegan and Plant-Based Products", "ambient"),
    ("Tropicana Orange Juice 1 L", FOOD, "Beverages", "ambient"),
    ("Broom Grass", "Household Cleaning and Maintenance", "General Household Cleaning", "ambient"),
    ("Sparx Sports Shoes Men", "Clothing and Accessories", "Footwear and Accessories", "ambient"),
    ("Nightwear Set Women", "Clothing and Accessories", "Basic Apparel and Innerwear", "ambient"),
    ("Night Light Plug-in", "Home Decor and Lifestyle", "Lighting and Electrical Accessories", "ambient"),
    ("Lakme Cold Cream Milk 100 g", "Personal Care and Hygiene", "Skin Care", "ambient"),
    ("Cadbury Dairy Milk 50g", FOOD, "Sweets and Desserts", "ambient"),
    ("Amul Dark Chocolate 150 g", FOOD, "Sweets and Desserts", "ambient"),
    ("Epigamia Greek Yogurt 90 g", FOOD, "Dairy Products", "chilled"),
])
def test_storage_follows_the_product_not_the_word(name, category, sub, storage):
    assert classify.storage_of(name, category, sub) == storage


def test_departments_and_placement():
    assert taxonomy.department_for("Household Cleaning and Maintenance", "General Household Cleaning") == ("A4", "Household, Pooja & Pets")
    assert taxonomy.department_for("Clothing and Accessories", "Footwear and Accessories") == ("Fashion", "Clothing & Footwear")
    assert taxonomy.department_for(FOOD, "Fresh Fruits") == ("Produce", "Fresh Produce")
    assert taxonomy.department_for(FOOD, "Snacks") == ("A2", "Snacks, Beverages & Sweets")
    assert taxonomy.department_for(FOOD, "Grains, Rice and Cereals") == ("A1", "Staples & Cooking")
    assert taxonomy.department_for("Textiles", "Sarees") is None
    milk = taxonomy.place(FLOOR, category=FOOD, subcategory="Dairy Products", storage="chilled", name="Milk")
    peas = taxonomy.place(FLOOR, category=FOOD, subcategory="Ready-to-Cook Foods", storage="frozen", name="Frozen Peas")
    shoes = taxonomy.place(FLOOR, category="Clothing and Accessories", subcategory="Footwear and Accessories", storage="ambient", name="Sparx Shoes")
    assert milk["aisle"] == "Chiller" and peas["aisle"] == "Freezer" and shoes["aisle"] == "Fashion"
    again = taxonomy.place(FLOOR, category="Clothing and Accessories", subcategory="Footwear and Accessories", storage="ambient", name="Sparx Shoes")
    assert again == shoes and 1 <= shoes["bay"] <= taxonomy.BAYS and shoes["side"] in ("left", "right")
    assert taxonomy.place([{"aisle": "A1"}], category="Clothing and Accessories", subcategory="", storage="ambient", name="x") is None


def test_pet_category_is_pet_whatever_the_name():
    assert classify.use_of("Feeding Bowl Steel", "Pet Products", "Pet Accessories") == "pet"
    assert classify.use_of("Steel Bowl Set 6 pcs", "Home and Kitchen Essentials", "Vessels and Tableware") == "human"


def test_section_names_are_understood():
    sections = [(FOOD, "Organic and Health Foods"), (FOOD, "Pulses and Legumes"), (FOOD, "Snacks"), ("Furniture and Furnishings", "Furniture")]
    assert taxonomy.section_match("healthy food", sections) == (FOOD, "Organic and Health Foods")
    assert taxonomy.section_match("list all the dals", sections) == (FOOD, "Pulses and Legumes")
    assert taxonomy.section_match("full list of groceries", sections) == (FOOD, "")
    assert taxonomy.section_match("nilkamal chair armless", sections) is None


@pytest.fixture
def shop(store_id):
    db.store_ref(store_id).set(Store(store_id=store_id, name="Tax Mart", floor_map=taxonomy.FLOOR_MAP).model_dump())
    rows = [csvc.Row(line=1, sku="OATS", name="True Elements Rolled Oats 1 kg", price=250, on_hand=5, category=FOOD, subcategory="Organic and Health Foods"),
            csvc.Row(line=2, sku="NET", name="Food Cover Net", price=120, on_hand=5, category="Home and Kitchen Essentials", subcategory="Food Storage and Serving"),
            csvc.Row(line=3, sku="MILK", name="Aavin Toned Milk 500ml", price=28, on_hand=5, category=FOOD, subcategory="Dairy Products"),
            csvc.Row(line=4, sku="SHOE", name="Sparx Sports Shoes Men", price=999, on_hand=5, category="Clothing and Accessories", subcategory="Footwear and Accessories")]
    csvc.upsert(store_id, rows, high_value_threshold=500)
    catalog.invalidate(store_id)
    return store_id


def test_imported_products_are_placed_and_a_section_query_lists_the_section(shop):
    milk = catalog.get_product(shop, f"{shop}-milk")
    shoes = catalog.get_product(shop, f"{shop}-shoe")
    assert milk.storage == "chilled" and milk.location.aisle == "Chiller"
    assert shoes.location.aisle == "Fashion" and shoes.storage == "ambient"
    page = client.get(f"/stores/{shop}/products", params={"q": "healthy food"}).json()
    assert page["section"] == "Organic and Health Foods" and [p["name"] for p in page["products"]] == ["True Elements Rolled Oats 1 kg"]
    assert page["products"][0]["aisle_label"] == "Staples & Cooking"
    assert client.get(f"/stores/{shop}/products", params={"q": "shoes"}).json()["section"] is None
