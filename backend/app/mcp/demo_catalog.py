"""Kirana Hub, a demo provider: sample prices and stock, generated once from the seed catalog. Every item says demo: true.
Not a real shop; never shown as live data."""

PROVIDER = "kirana-hub-demo"
LABEL = "Kirana Hub (demo data)"

ITEMS: list[dict] = [{'sku': 'KH-ATTA5', 'name': 'Aashirvaad Whole Wheat Atta 5kg', 'brand': 'Aashirvaad', 'category': 'Grocery and Food Products', 'barcode': '8900000000012', 'price': 257, 'mrp': 280, 'stock': 12, 'unit': 'pc', 'pack_size': '5 kg'},
    {'sku': 'KH-ATTA10', 'name': 'Aashirvaad Whole Wheat Atta 10kg', 'brand': 'Aashirvaad', 'category': 'Grocery and Food Products', 'barcode': '8900000000029', 'price': 478, 'mrp': 545, 'stock': 40, 'unit': 'pc', 'pack_size': '10 kg'},
    {'sku': 'KH-RICE5', 'name': 'India Gate Basmati Rice 5kg', 'brand': 'India Gate', 'category': 'Grocery and Food Products', 'barcode': '8900000000036', 'price': 598, 'mrp': 720, 'stock': 25, 'unit': 'pc', 'pack_size': '5 kg'},
    {'sku': 'KH-PONNI5', 'name': 'Ponni Boiled Rice 5kg', 'brand': 'Udhayam', 'category': 'Grocery and Food Products', 'barcode': '8900000000043', 'price': 310, 'mrp': 340, 'stock': 60, 'unit': 'pc', 'pack_size': '5 kg'},
    {'sku': 'KH-SONA10', 'name': 'Sona Masoori Rice 10kg', 'brand': 'Daawat', 'category': 'Grocery and Food Products', 'barcode': '8900000000050', 'price': 532, 'mrp': 600, 'stock': 4, 'unit': 'pc', 'pack_size': '10 kg'},
    {'sku': 'KH-TOOR1', 'name': 'Tata Sampann Toor Dal 1kg', 'brand': 'Tata Sampann', 'category': 'Grocery and Food Products', 'barcode': '8900000000067', 'price': 157, 'mrp': 180, 'stock': 0, 'unit': 'pc', 'pack_size': '1 kg'},
    {'sku': 'KH-MOONG1', 'name': 'Tata Sampann Moong Dal 1kg', 'brand': 'Tata Sampann', 'category': 'Grocery and Food Products', 'barcode': '8900000000074', 'price': 154, 'mrp': 160, 'stock': 60, 'unit': 'pc', 'pack_size': '1 kg'},
    {'sku': 'KH-URAD1', 'name': 'Udhayam Urad Dal 1kg', 'brand': 'Udhayam', 'category': 'Grocery and Food Products', 'barcode': '8900000000081', 'price': 133, 'mrp': 150, 'stock': 0, 'unit': 'pc', 'pack_size': '1 kg'},
    {'sku': 'KH-CHANA1', 'name': 'Tata Sampann Chana Dal 1kg', 'brand': 'Tata Sampann', 'category': 'Grocery and Food Products', 'barcode': '8900000000098', 'price': 113, 'mrp': 120, 'stock': 40, 'unit': 'pc', 'pack_size': '1 kg'},
    {'sku': 'KH-RAJMA500', 'name': 'Organic Tattva Rajma 500g', 'brand': 'Organic Tattva', 'category': 'Grocery and Food Products', 'barcode': '8900000000104', 'price': 92, 'mrp': 105, 'stock': 0, 'unit': 'pc', 'pack_size': '500 g'},
    {'sku': 'KH-SUGAR1', 'name': 'Madhur Sugar 1kg', 'brand': 'Madhur', 'category': 'Grocery and Food Products', 'barcode': '8900000000111', 'price': 51, 'mrp': 52, 'stock': 12, 'unit': 'pc', 'pack_size': '1 kg'},
    {'sku': 'KH-SUGAR5', 'name': 'Madhur Sugar 5kg', 'brand': 'Madhur', 'category': 'Grocery and Food Products', 'barcode': '8900000000128', 'price': 253, 'mrp': 253, 'stock': 25, 'unit': 'pc', 'pack_size': '5 kg'},
    {'sku': 'KH-JAGG500', 'name': 'Country Jaggery 500g', 'brand': 'Vellam', 'category': 'Grocery and Food Products', 'barcode': '8900000000135', 'price': 52, 'mrp': 60, 'stock': 40, 'unit': 'pc', 'pack_size': '500 g'},
    {'sku': 'KH-SALT1', 'name': 'Tata Salt 1kg', 'brand': 'Tata', 'category': 'Grocery and Food Products', 'barcode': '8900000000142', 'price': 24, 'mrp': 28, 'stock': 4, 'unit': 'pc', 'pack_size': '1 kg'},
    {'sku': 'KH-RAVA1', 'name': 'Double Horse Rava 1kg', 'brand': 'Double Horse', 'category': 'Grocery and Food Products', 'barcode': '8900000000159', 'price': 51, 'mrp': 60, 'stock': 25, 'unit': 'pc', 'pack_size': '1 kg'},
    {'sku': 'KH-MAIDA1', 'name': 'Pillsbury Maida 1kg', 'brand': 'Pillsbury', 'category': 'Grocery and Food Products', 'barcode': '8900000000166', 'price': 55, 'mrp': 56, 'stock': 4, 'unit': 'pc', 'pack_size': '1 kg'},
    {'sku': 'KH-POHA500', 'name': 'Shakti Bhog Poha 500g', 'brand': 'Shakti Bhog', 'category': 'Grocery and Food Products', 'barcode': '8900000000173', 'price': 37, 'mrp': 45, 'stock': 12, 'unit': 'pc', 'pack_size': '500 g'},
    {'sku': 'KH-IDLIRAVA', 'name': 'Udhayam Idli Rava 1kg', 'brand': 'Udhayam', 'category': 'Grocery and Food Products', 'barcode': '8900000000180', 'price': 66, 'mrp': 66, 'stock': 0, 'unit': 'pc', 'pack_size': '1 kg'},
    {'sku': 'KH-TURM200', 'name': 'Aachi Turmeric Powder 200g', 'brand': 'Aachi', 'category': 'Grocery and Food Products', 'barcode': '8900000000197', 'price': 58, 'mrp': 65, 'stock': 40, 'unit': 'pc', 'pack_size': '200 g'},
    {'sku': 'KH-CHILLI200', 'name': 'Aachi Chilli Powder 200g', 'brand': 'Aachi', 'category': 'Grocery and Food Products', 'barcode': '8900000000203', 'price': 73, 'mrp': 80, 'stock': 0, 'unit': 'pc', 'pack_size': '200 g'},
    {'sku': 'KH-CORI200', 'name': 'Aachi Coriander Powder 200g', 'brand': 'Aachi', 'category': 'Grocery and Food Products', 'barcode': '8900000000210', 'price': 57, 'mrp': 60, 'stock': 0, 'unit': 'pc', 'pack_size': '200 g'},
    {'sku': 'KH-SAMBAR100', 'name': 'MTR Sambar Powder 100g', 'brand': 'MTR', 'category': 'Grocery and Food Products', 'barcode': '8900000000227', 'price': 53, 'mrp': 53, 'stock': 12, 'unit': 'pc', 'pack_size': '100 g'},
    {'sku': 'KH-GARAM100', 'name': 'Everest Garam Masala 100g', 'brand': 'Everest', 'category': 'Grocery and Food Products', 'barcode': '8900000000234', 'price': 79, 'mrp': 79, 'stock': 25, 'unit': 'pc', 'pack_size': '100 g'},
    {'sku': 'KH-MUSTARD200', 'name': 'Aachi Mustard Seeds 200g', 'brand': 'Aachi', 'category': 'Grocery and Food Products', 'barcode': '8900000000241', 'price': 41, 'mrp': 44, 'stock': 40, 'unit': 'pc', 'pack_size': '200 g'},
    {'sku': 'KH-TAMAR500', 'name': 'Aachi Tamarind 500g', 'brand': 'Aachi', 'category': 'Grocery and Food Products', 'barcode': '8900000000258', 'price': 90, 'mrp': 95, 'stock': 4, 'unit': 'pc', 'pack_size': '500 g'},
    {'sku': 'KH-SUNOIL1', 'name': 'Fortune Sunflower Oil 1L', 'brand': 'Fortune', 'category': 'Grocery and Food Products', 'barcode': '8900000000265', 'price': 145, 'mrp': 160, 'stock': 12, 'unit': 'pc', 'pack_size': '1 l'},
    {'sku': 'KH-SUNOIL5', 'name': 'Fortune Sunflower Oil 5L', 'brand': 'Fortune', 'category': 'Grocery and Food Products', 'barcode': '8900000000272', 'price': 803, 'mrp': 820, 'stock': 12, 'unit': 'pc', 'pack_size': '5 l'},
    {'sku': 'KH-GINGOIL1', 'name': 'Idhayam Gingelly Oil 1L', 'brand': 'Idhayam', 'category': 'Grocery and Food Products', 'barcode': '8900000000289', 'price': 339, 'mrp': 340, 'stock': 40, 'unit': 'pc', 'pack_size': '1 l'},
    {'sku': 'KH-COCOIL1', 'name': 'Parachute Coconut Oil 1L', 'brand': 'Parachute', 'category': 'Grocery and Food Products', 'barcode': '8900000000296', 'price': 253, 'mrp': 253, 'stock': 40, 'unit': 'pc', 'pack_size': '1 l'},
    {'sku': 'KH-GROIL1', 'name': 'Gold Winner Groundnut Oil 1L', 'brand': 'Gold Winner', 'category': 'Grocery and Food Products', 'barcode': '8900000000302', 'price': 210, 'mrp': 225, 'stock': 25, 'unit': 'pc', 'pack_size': '1 l'},
    {'sku': 'KH-OLIVE1', 'name': 'Figaro Extra Virgin Olive Oil 1L', 'brand': 'Figaro', 'category': 'Grocery and Food Products', 'barcode': '8900000000319', 'price': 854, 'mrp': 999, 'stock': 12, 'unit': 'pc', 'pack_size': '1 l'},
    {'sku': 'KH-GHEE500', 'name': 'Aavin Ghee 500ml', 'brand': 'Aavin', 'category': 'Grocery and Food Products', 'barcode': '8900000000326', 'price': 330, 'mrp': 360, 'stock': 4, 'unit': 'pc', 'pack_size': '500 ml'},
    {'sku': 'KH-GHEE1', 'name': 'Amul Pure Ghee 1L', 'brand': 'Amul', 'category': 'Grocery and Food Products', 'barcode': '8900000000333', 'price': 715, 'mrp': 715, 'stock': 40, 'unit': 'pc', 'pack_size': '1 l'},
    {'sku': 'KH-BUTTER500', 'name': 'Amul Butter 500g', 'brand': 'Amul', 'category': 'Grocery and Food Products', 'barcode': '8900000000340', 'price': 276, 'mrp': 295, 'stock': 0, 'unit': 'pc', 'pack_size': '500 g'},
    {'sku': 'KH-MILK500', 'name': 'Aavin Toned Milk 500ml', 'brand': 'Aavin', 'category': 'Grocery and Food Products', 'barcode': '8900000000357', 'price': 27, 'mrp': 28, 'stock': 25, 'unit': 'pc', 'pack_size': '500 ml'},
    {'sku': 'KH-MILK1', 'name': 'Aavin Full Cream Milk 1L', 'brand': 'Aavin', 'category': 'Grocery and Food Products', 'barcode': '8900000000364', 'price': 70, 'mrp': 70, 'stock': 25, 'unit': 'pc', 'pack_size': '1 l'},
    {'sku': 'KH-AMULMILK1', 'name': 'Amul Taaza Milk 1L', 'brand': 'Amul', 'category': 'Grocery and Food Products', 'barcode': '8900000000371', 'price': 70, 'mrp': 70, 'stock': 0, 'unit': 'pc', 'pack_size': '1 l'},
    {'sku': 'KH-CURD500', 'name': 'Aavin Curd 500g', 'brand': 'Aavin', 'category': 'Grocery and Food Products', 'barcode': '8900000000388', 'price': 33, 'mrp': 36, 'stock': 40, 'unit': 'pc', 'pack_size': '500 g'},
    {'sku': 'KH-CURD1', 'name': 'Nestle A+ Curd 1kg', 'brand': 'Nestle', 'category': 'Grocery and Food Products', 'barcode': '8900000000395', 'price': 101, 'mrp': 101, 'stock': 25, 'unit': 'pc', 'pack_size': '1 kg'},
    {'sku': 'KH-PANEER200', 'name': 'Amul Paneer 200g', 'brand': 'Amul', 'category': 'Grocery and Food Products', 'barcode': '8900000000401', 'price': 95, 'mrp': 95, 'stock': 12, 'unit': 'pc', 'pack_size': '200 g'},
    {'sku': 'KH-CHEESE200', 'name': 'Amul Cheese Slices 200g', 'brand': 'Amul', 'category': 'Grocery and Food Products', 'barcode': '8900000000418', 'price': 128, 'mrp': 140, 'stock': 12, 'unit': 'pc', 'pack_size': '200 g'},
    {'sku': 'KH-SOYAMILK1', 'name': 'Sofit Soya Milk 1L', 'brand': 'Sofit', 'category': 'Grocery and Food Products', 'barcode': '8900000000425', 'price': 117, 'mrp': 120, 'stock': 4, 'unit': 'pc', 'pack_size': '1 l'},
    {'sku': 'KH-ALMONDMILK1', 'name': 'So Good Almond Milk 1L', 'brand': 'So Good', 'category': 'Grocery and Food Products', 'barcode': '8900000000432', 'price': 253, 'mrp': 253, 'stock': 60, 'unit': 'pc', 'pack_size': '1 l'},
    {'sku': 'KH-BUTTERMILK200', 'name': 'Aavin Buttermilk 200ml', 'brand': 'Aavin', 'category': 'Grocery and Food Products', 'barcode': '8900000000449', 'price': 10, 'mrp': 10, 'stock': 4, 'unit': 'pc', 'pack_size': '200 ml'},
    {'sku': 'KH-LASSI200', 'name': 'Amul Lassi 200ml', 'brand': 'Amul', 'category': 'Grocery and Food Products', 'barcode': '8900000000456', 'price': 19, 'mrp': 20, 'stock': 12, 'unit': 'pc', 'pack_size': '200 ml'},
    {'sku': 'KH-EGGS12', 'name': 'Farm Fresh Eggs 12pc', 'brand': 'Suguna', 'category': 'Grocery and Food Products', 'barcode': '8900000000463', 'price': 81, 'mrp': 90, 'stock': 25, 'unit': 'pc', 'pack_size': '12 pc'},
    {'sku': 'KH-BREAD400', 'name': 'Modern White Bread 400g', 'brand': 'Modern', 'category': 'Grocery and Food Products', 'barcode': '8900000000470', 'price': 40, 'mrp': 42, 'stock': 40, 'unit': 'pc', 'pack_size': '400 g'},
    {'sku': 'KH-BROWNBREAD', 'name': 'Britannia Brown Bread 400g', 'brand': 'Britannia', 'category': 'Grocery and Food Products', 'barcode': '8900000000487', 'price': 48, 'mrp': 52, 'stock': 12, 'unit': 'pc', 'pack_size': '400 g'},
    {'sku': 'KH-BUNS6', 'name': 'Modern Burger Buns 6pc', 'brand': 'Modern', 'category': 'Grocery and Food Products', 'barcode': '8900000000494', 'price': 43, 'mrp': 48, 'stock': 4, 'unit': 'pc', 'pack_size': '6 pc'},
    {'sku': 'KH-RUSK300', 'name': 'Britannia Toastea Rusk 300g', 'brand': 'Britannia', 'category': 'Grocery and Food Products', 'barcode': '8900000000500', 'price': 61, 'mrp': 61, 'stock': 60, 'unit': 'pc', 'pack_size': '300 g'},
    {'sku': 'KH-CAKE250', 'name': 'Britannia Fruit Cake 250g', 'brand': 'Britannia', 'category': 'Grocery and Food Products', 'barcode': '8900000000517', 'price': 60, 'mrp': 65, 'stock': 25, 'unit': 'pc', 'pack_size': '250 g'},
    {'sku': 'KH-TEA500', 'name': 'Red Label Tea 500g', 'brand': 'Brooke Bond', 'category': 'Grocery and Food Products', 'barcode': '8900000000524', 'price': 239, 'mrp': 280, 'stock': 0, 'unit': 'pc', 'pack_size': '500 g'},
    {'sku': 'KH-TEA250', 'name': 'Tata Tea Gold 250g', 'brand': 'Tata Tea', 'category': 'Grocery and Food Products', 'barcode': '8900000000531', 'price': 154, 'mrp': 160, 'stock': 0, 'unit': 'pc', 'pack_size': '250 g'},
    {'sku': 'KH-COFFEE200', 'name': 'Bru Instant Coffee 200g', 'brand': 'Bru', 'category': 'Grocery and Food Products', 'barcode': '8900000000548', 'price': 390, 'mrp': 420, 'stock': 4, 'unit': 'pc', 'pack_size': '200 g'},
    {'sku': 'KH-FILTERCOF', 'name': 'Narasus Filter Coffee 500g', 'brand': 'Narasus', 'category': 'Grocery and Food Products', 'barcode': '8900000000555', 'price': 210, 'mrp': 220, 'stock': 12, 'unit': 'pc', 'pack_size': '500 g'},
    {'sku': 'KH-HORLICKS500', 'name': 'Horlicks Classic 500g', 'brand': 'Horlicks', 'category': 'Grocery and Food Products', 'barcode': '8900000000562', 'price': 260, 'mrp': 275, 'stock': 12, 'unit': 'pc', 'pack_size': '500 g'},
    {'sku': 'KH-BOOST500', 'name': 'Boost 500g', 'brand': 'Boost', 'category': 'Grocery and Food Products', 'barcode': '8900000000579', 'price': 233, 'mrp': 260, 'stock': 4, 'unit': 'pc', 'pack_size': '500 g'},
    {'sku': 'KH-COKE2', 'name': 'Coca-Cola 2L', 'brand': 'Coca-Cola', 'category': 'Grocery and Food Products', 'barcode': '8900000000586', 'price': 95, 'mrp': 99, 'stock': 60, 'unit': 'pc', 'pack_size': '2 l'},
    {'sku': 'KH-SPRITE2', 'name': 'Sprite 2L', 'brand': 'Sprite', 'category': 'Grocery and Food Products', 'barcode': '8900000000593', 'price': 92, 'mrp': 99, 'stock': 0, 'unit': 'pc', 'pack_size': '2 l'},
    {'sku': 'KH-WATER1', 'name': 'Bisleri Water 1L', 'brand': 'Bisleri', 'category': 'Grocery and Food Products', 'barcode': '8900000000609', 'price': 21, 'mrp': 21, 'stock': 4, 'unit': 'pc', 'pack_size': '1 l'},
    {'sku': 'KH-OATMILK', 'name': 'Oatly Oat Drink 1 L', 'brand': 'Oatly', 'category': 'Dairy, Bread and Eggs', 'barcode': '8900000900028', 'price': 289, 'mrp': 299, 'stock': 10, 'unit': 'pc', 'pack_size': '1 L'},
    {'sku': 'KH-QUINOA', 'name': 'True Elements Quinoa 500 g', 'brand': 'True Elements', 'category': 'Grocery and Food Products', 'barcode': '8900000900035', 'price': 239, 'mrp': 260, 'stock': 18, 'unit': 'pc', 'pack_size': '500 g'},
    {'sku': 'KH-KOMBUCHA', 'name': 'Atmosphere Kombucha Ginger 300 ml', 'brand': 'Atmosphere', 'category': 'Beverages', 'barcode': '8900000900066', 'price': 115, 'mrp': 130, 'stock': 30, 'unit': 'pc', 'pack_size': '300 ml'}]


def _tokens(text: str) -> set[str]:
    return {t for t in "".join(c.lower() if c.isalnum() else " " for c in text).split() if len(t) > 1}


def _public(item: dict) -> dict:
    return {**item, "provider": LABEL, "demo": True}


def search(query: str, limit: int = 8) -> list[dict]:
    q = _tokens(query)
    scored = [(len(q & _tokens(i["name"] + " " + i["brand"])), i) for i in ITEMS]
    return [_public(i) for n, i in sorted(scored, key=lambda x: -x[0]) if n > 0][:max(1, min(50, int(limit)))]


def list_items(limit: int = 50, offset: int = 0) -> list[dict]:
    return [_public(i) for i in ITEMS[max(0, int(offset)):max(0, int(offset)) + max(1, min(200, int(limit)))]]


def get(sku: str) -> dict | None:
    return next((_public(i) for i in ITEMS if i["sku"].lower() == sku.strip().lower()), None)
