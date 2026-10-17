# Catalogue expansion report

Existing products kept: 170 (ids, names and prices untouched; 170 moved to the new category tree).
New products added: 1409. Catalogue entries skipped as duplicates: 26 matched an existing product, 29 repeated inside the catalogue.
Total products: 1579 across 21 main categories and 91 subcategories.

## Category summary (products per subcategory)

- **Automobile Care and Accessories** (36): Automobile Accessories 10, Automotive Maintenance Essentials 9, Car Detailing 8, Vehicle Cleaning 9
- **Baby and Infant Products** (29): Baby Care 16, Baby Feeding and Clothing 13
- **Clothing and Accessories** (25): Basic Apparel and Innerwear 14, Footwear and Accessories 11
- **Disposable and Eco-Friendly Products** (21): Disposables 9, Reusable and Eco-Friendly 12
- **Electronics and Technology** (74): Batteries and Power 11, Computer and Office Electronics 12, Consumer Electronics 12, Mobile Accessories 12, Small Home Appliances 18, Smart Home Products 9
- **Furniture and Furnishings** (45): Carpets and Floor Coverings 10, Furniture 20, Home Furnishings 15
- **Garden and Outdoor Living** (20): Gardening 10, Outdoor Living 10
- **Gift Items and Seasonal Products** (23): Festive Decorations 10, Gifting and Party Supplies 13
- **Grocery and Food Products** (587): Bakery and Breads 18, Beverages 51, Cooking Essentials 41, Dairy Products 31, Eggs 9, Flours and Baking Ingredients 29, Fresh Fruits 28, Fresh Meat and Seafood 18, Fresh Vegetables 43, Frozen Foods 25, Grains, Rice and Cereals 38, Organic and Health Foods 16, Pickles, Preserves and Condiments 20, Pulses and Legumes 26, Ready-to-Cook Foods 18, Ready-to-Eat Foods 21, Snacks 56, Spices and Seasonings 38, Sweets and Desserts 27, Tinned and Canned Foods 16, Vegan and Plant-Based Products 18
- **Hardware and DIY** (22): Fasteners, Locks and Repair 12, Hand Tools 10
- **Health and First Aid** (38): First Aid 16, Wellness and Protection 22
- **Home Decor and Lifestyle** (57): Artificial and Natural Plants 20, Fragrances and Ambience 9, Home Decor 14, Lighting and Electrical Accessories 14
- **Home and Kitchen Essentials** (92): Cooking Equipment and Accessories 18, Food Storage and Serving 12, Home Organization 12, Kitchen Utilities 20, Plastic Products 14, Vessels and Tableware 16
- **Household Cleaning and Maintenance** (109): General Household Cleaning 24, Home Maintenance 17, Kitchen Cleaning 19, Laundry and Fabric Care 20, Pest Control 14, Toilet and Bathroom Products 15
- **Personal Care and Hygiene** (140): Beauty and Cosmetics 19, Fragrances 16, Hair Care 25, Personal Hygiene and Wellness 17, Skin Care 22, Toiletries and Bath Products 41
- **Pet Products** (49): Pet Accessories 13, Pet Food 18, Pet Grooming and Hygiene 9, Products for Other Pets 9
- **Pooja and Religious Products** (62): Daily Pooja Essentials 14, Festive and Religious Products 12, Flowers and Offerings 14, Pooja Accessories 12, Religious Books and Accessories 10
- **Sports, Fitness and Outdoor** (24): Fitness 10, Sports and Outdoor 14
- **Stationery, Books and Office Supplies** (78): Books and Learning Materials 13, Diaries and Planners 10, Office Supplies 14, Paper Products 13, School Supplies 15, Writing Instruments 13
- **Toys, Games and Hobbies** (28): Games and Hobbies 14, Toys 14
- **Travel and Luggage** (20): Luggage and Bags 10, Travel Accessories 10

## New products per main category

- Automobile Care and Accessories: 36
- Baby and Infant Products: 22
- Clothing and Accessories: 25
- Disposable and Eco-Friendly Products: 21
- Electronics and Technology: 74
- Furniture and Furnishings: 45
- Garden and Outdoor Living: 20
- Gift Items and Seasonal Products: 23
- Grocery and Food Products: 473
- Hardware and DIY: 22
- Health and First Aid: 26
- Home Decor and Lifestyle: 57
- Home and Kitchen Essentials: 92
- Household Cleaning and Maintenance: 89
- Personal Care and Hygiene: 126
- Pet Products: 46
- Pooja and Religious Products: 62
- Sports, Fitness and Outdoor: 24
- Stationery, Books and Office Supplies: 78
- Toys, Games and Hobbies: 28
- Travel and Luggage: 20

## Data quality

- Prices: indicative Indian MRPs for demonstration (`sample-price`); existing products keep the prices they had. Selling price equals MRP for new items.
- Stock quantities: deterministic sample values (`sample-stock`), 6% of new items at zero so low-stock views have content.
- Barcodes: new items carry in-store codes with the GS1 restricted-circulation prefix 20 (`internal-barcode`); existing items keep their synthetic 890 codes (`synthetic-barcode`). Neither is a real GTIN; replace through sync or add-by-scan.
- GST rates are the usual slab for the subcategory (`indicative-gst`); confirm with your accountant before invoicing.
- Shelf life is a typical value per subcategory; durable goods have none. Expiry and batch tracking per lot is not in this inventory.
- Storage class (ambient, chilled, frozen) and intended use (people, pets, household, personal care) are derived by the classifier at import; chilled and frozen items are placed in the Chiller and Freezer blocks.
- Over-the-counter medicines from the original list are flagged `regulated-otc-medicine`; keep them subject to local rules.
- Seasonal fruit and festive items are marked `seasonal` in status when the name says so.

## Pending information (count of products missing each field)

- cost_price: 1579
- origin: 1579
- supplier_id: 1409
- tags: 1409
- image_url: 1409
- brand: 670
- shelf_life_days: 584
- gst_rate: 135

## Change summary

- Added columns: pack_size, cost_price, gst_rate, shelf_life_days, status, origin, data_status (the last is report-only and not imported).
- Mapped the original 14 categories into the new taxonomy; names unchanged.
- Existing rows: filled pack_size from the name, gst_rate and shelf_life_days from the subcategory defaults; everything else as before.
- Backup of the original file: products.before-expansion.csv.
