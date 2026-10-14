"""Writes products.csv for the demo grocery store. Deterministic, no network.

Usage: python infra/seed/make_products.py
"""

import csv
from pathlib import Path

OUT = Path(__file__).with_name("products.csv")

# category -> aisle
AISLE = {
    "Staples": "A1", "Oils & Ghee": "A1", "Dairy": "A2", "Bakery": "A2", "Beverages": "A3",
    "Snacks": "A3", "Sweets": "A3", "Personal Care": "A4", "Household": "A4", "Baby": "A5",
    "Pharmacy": "A5", "Fruits & Vegetables": "A6", "Frozen": "A6", "Pet": "A6",
}

# sku, name, brand, category, subcategory, price, mrp, unit, tags, on_hand, substitutes
ITEMS = [
    # Staples
    ("ATTA5", "Aashirvaad Whole Wheat Atta 5kg", "Aashirvaad", "Staples", "Flour", 265, 280, "pc", "atta|wheat flour|கோதுமை மாவு|आटा", 40, ""),
    ("ATTA10", "Aashirvaad Whole Wheat Atta 10kg", "Aashirvaad", "Staples", "Flour", 520, 545, "pc", "atta|wheat flour|आटा", 12, "ATTA5"),
    ("RICE5", "India Gate Basmati Rice 5kg", "India Gate", "Staples", "Rice", 650, 720, "pc", "basmati|rice|அரிசி|चावल", 18, ""),
    ("PONNI5", "Ponni Boiled Rice 5kg", "Udhayam", "Staples", "Rice", 320, 340, "pc", "ponni|rice|அரிசி|चावल", 30, ""),
    ("SONA10", "Sona Masoori Rice 10kg", "Daawat", "Staples", "Rice", 560, 600, "pc", "sona masoori|rice|अरिसी", 10, "PONNI5"),
    ("TOOR1", "Tata Sampann Toor Dal 1kg", "Tata Sampann", "Staples", "Pulses", 165, 180, "pc", "toor dal|arhar|துவரம் பருப்பு|दाल", 35, ""),
    ("MOONG1", "Tata Sampann Moong Dal 1kg", "Tata Sampann", "Staples", "Pulses", 150, 160, "pc", "moong dal|பாசிப்பருப்பு|मूंग", 25, ""),
    ("URAD1", "Udhayam Urad Dal 1kg", "Udhayam", "Staples", "Pulses", 140, 150, "pc", "urad dal|உளுந்து|उड़द", 22, ""),
    ("CHANA1", "Tata Sampann Chana Dal 1kg", "Tata Sampann", "Staples", "Pulses", 110, 120, "pc", "chana dal|கடலைப்பருப்பு|चना", 28, ""),
    ("RAJMA500", "Organic Tattva Rajma 500g", "Organic Tattva", "Staples", "Pulses", 95, 105, "pc", "rajma|kidney beans|राजमा", 15, ""),
    ("SUGAR1", "Madhur Sugar 1kg", "Madhur", "Staples", "Sugar", 48, 52, "pc", "sugar|சக்கரை|चीनी", 60, ""),
    ("SUGAR5", "Madhur Sugar 5kg", "Madhur", "Staples", "Sugar", 230, 250, "pc", "sugar|சக்கரை|चीनी", 20, "SUGAR1"),
    ("JAGG500", "Country Jaggery 500g", "Vellam", "Staples", "Sugar", 55, 60, "pc", "jaggery|வெல்லம்|गुड़", 25, ""),
    ("SALT1", "Tata Salt 1kg", "Tata", "Staples", "Salt", 26, 28, "pc", "salt|உப்பு|नमक", 80, ""),
    ("RAVA1", "Double Horse Rava 1kg", "Double Horse", "Staples", "Flour", 55, 60, "pc", "rava|sooji|ரவை|सूजी", 30, ""),
    ("MAIDA1", "Pillsbury Maida 1kg", "Pillsbury", "Staples", "Flour", 52, 56, "pc", "maida|मैदा", 24, ""),
    ("POHA500", "Shakti Bhog Poha 500g", "Shakti Bhog", "Staples", "Flour", 40, 45, "pc", "poha|aval|அவல்|पोहा", 26, ""),
    ("IDLIRAVA", "Udhayam Idli Rava 1kg", "Udhayam", "Staples", "Flour", 60, 65, "pc", "idli rava|இட்லி ரவை", 20, ""),
    ("TURM200", "Aachi Turmeric Powder 200g", "Aachi", "Staples", "Spices", 60, 65, "pc", "turmeric|மஞ்சள்|हल्दी", 40, ""),
    ("CHILLI200", "Aachi Chilli Powder 200g", "Aachi", "Staples", "Spices", 75, 80, "pc", "chilli powder|மிளகாய்|मिर्च", 38, ""),
    ("CORI200", "Aachi Coriander Powder 200g", "Aachi", "Staples", "Spices", 55, 60, "pc", "coriander|dhania|மல்லி|धनिया", 36, ""),
    ("SAMBAR100", "MTR Sambar Powder 100g", "MTR", "Staples", "Spices", 48, 50, "pc", "sambar powder|சாம்பார் பொடி", 44, ""),
    ("GARAM100", "Everest Garam Masala 100g", "Everest", "Staples", "Spices", 72, 78, "pc", "garam masala|गरम मसाला", 30, ""),
    ("MUSTARD200", "Aachi Mustard Seeds 200g", "Aachi", "Staples", "Spices", 40, 44, "pc", "mustard|கடுகு|सरसों", 32, ""),
    ("TAMAR500", "Aachi Tamarind 500g", "Aachi", "Staples", "Spices", 90, 95, "pc", "tamarind|புளி|इमली", 20, ""),
    # Oils & Ghee
    ("SUNOIL1", "Fortune Sunflower Oil 1L", "Fortune", "Oils & Ghee", "Oil", 145, 160, "pc", "sunflower oil|cooking oil|எண்ணெய்|तेल", 45, ""),
    ("SUNOIL5", "Fortune Sunflower Oil 5L", "Fortune", "Oils & Ghee", "Oil", 780, 820, "pc", "sunflower oil|cooking oil|तेल", 10, "SUNOIL1"),
    ("GINGOIL1", "Idhayam Gingelly Oil 1L", "Idhayam", "Oils & Ghee", "Oil", 320, 340, "pc", "gingelly oil|sesame oil|நல்லெண்ணெய்|तिल का तेल", 18, ""),
    ("COCOIL1", "Parachute Coconut Oil 1L", "Parachute", "Oils & Ghee", "Oil", 230, 245, "pc", "coconut oil|தேங்காய் எண்ணெய்|नारियल तेल", 22, ""),
    ("GROIL1", "Gold Winner Groundnut Oil 1L", "Gold Winner", "Oils & Ghee", "Oil", 210, 225, "pc", "groundnut oil|peanut oil|கடலை எண்ணெய்", 16, ""),
    ("OLIVE1", "Figaro Extra Virgin Olive Oil 1L", "Figaro", "Oils & Ghee", "Oil", 899, 999, "pc", "olive oil|जैतून", 6, ""),
    ("GHEE500", "Aavin Ghee 500ml", "Aavin", "Oils & Ghee", "Ghee", 340, 360, "pc", "ghee|நெய்|घी", 20, ""),
    ("GHEE1", "Amul Pure Ghee 1L", "Amul", "Oils & Ghee", "Ghee", 650, 690, "pc", "ghee|நெய்|घी", 8, "GHEE500"),
    ("BUTTER500", "Amul Butter 500g", "Amul", "Dairy", "Butter", 285, 295, "pc", "butter|வெண்ணெய்|मक्खन", 14, ""),
    # Dairy
    ("MILK500", "Aavin Toned Milk 500ml", "Aavin", "Dairy", "Milk", 28, 28, "pc", "milk|toned milk|பால்|दूध", 60, ""),
    ("MILK1", "Aavin Full Cream Milk 1L", "Aavin", "Dairy", "Milk", 66, 66, "pc", "milk|full cream|பால்|दूध", 35, ""),
    ("AMULMILK1", "Amul Taaza Milk 1L", "Amul", "Dairy", "Milk", 68, 70, "pc", "milk|पाल|दूध", 30, ""),
    ("CURD500", "Aavin Curd 500g", "Aavin", "Dairy", "Curd", 35, 36, "pc", "curd|yogurt|தயிர்|दही", 40, ""),
    ("CURD1", "Nestle A+ Curd 1kg", "Nestle", "Dairy", "Curd", 95, 99, "pc", "curd|yogurt|दही", 0, "CURD500"),
    ("PANEER200", "Amul Paneer 200g", "Amul", "Dairy", "Paneer", 90, 95, "pc", "paneer|पनीर", 18, ""),
    ("CHEESE200", "Amul Cheese Slices 200g", "Amul", "Dairy", "Cheese", 135, 140, "pc", "cheese|चीज़", 15, ""),
    ("SOYAMILK1", "Sofit Soya Milk 1L", "Sofit", "Dairy", "Plant milk", 110, 120, "pc", "soya milk|soy milk|plant milk|lactose free", 12, ""),
    ("ALMONDMILK1", "So Good Almond Milk 1L", "So Good", "Dairy", "Plant milk", 230, 250, "pc", "almond milk|plant milk|lactose free", 0, "SOYAMILK1"),
    ("BUTTERMILK200", "Aavin Buttermilk 200ml", "Aavin", "Dairy", "Milk", 10, 10, "pc", "buttermilk|மோர்|छाछ", 50, ""),
    ("LASSI200", "Amul Lassi 200ml", "Amul", "Dairy", "Milk", 20, 20, "pc", "lassi|लस्सी", 30, ""),
    ("EGGS12", "Farm Fresh Eggs 12pc", "Suguna", "Dairy", "Eggs", 84, 90, "pc", "eggs|முட்டை|अंडे", 40, ""),
    # Bakery
    ("BREAD400", "Modern White Bread 400g", "Modern", "Bakery", "Bread", 40, 42, "pc", "bread|ரொட்டி|ब्रेड", 30, ""),
    ("BROWNBREAD", "Britannia Brown Bread 400g", "Britannia", "Bakery", "Bread", 50, 52, "pc", "brown bread|wheat bread|ब्रेड", 20, "BREAD400"),
    ("BUNS6", "Modern Burger Buns 6pc", "Modern", "Bakery", "Bread", 45, 48, "pc", "buns|burger", 15, ""),
    ("RUSK300", "Britannia Toastea Rusk 300g", "Britannia", "Bakery", "Rusk", 55, 60, "pc", "rusk|toast", 25, ""),
    ("CAKE250", "Britannia Fruit Cake 250g", "Britannia", "Bakery", "Cake", 60, 65, "pc", "cake|केक", 12, ""),
    # Beverages
    ("TEA500", "Red Label Tea 500g", "Brooke Bond", "Beverages", "Tea", 260, 280, "pc", "tea|தேயிலை|चाय", 30, ""),
    ("TEA250", "Tata Tea Gold 250g", "Tata Tea", "Beverages", "Tea", 150, 160, "pc", "tea|चाय", 25, ""),
    ("COFFEE200", "Bru Instant Coffee 200g", "Bru", "Beverages", "Coffee", 390, 420, "pc", "coffee|காபி|कॉफी", 18, ""),
    ("FILTERCOF", "Narasus Filter Coffee 500g", "Narasus", "Beverages", "Coffee", 210, 220, "pc", "filter coffee|காபி", 20, ""),
    ("HORLICKS500", "Horlicks Classic 500g", "Horlicks", "Beverages", "Health drink", 260, 275, "pc", "horlicks|health drink", 15, ""),
    ("BOOST500", "Boost 500g", "Boost", "Beverages", "Health drink", 245, 260, "pc", "boost|health drink", 14, "HORLICKS500"),
    ("COKE2", "Coca-Cola 2L", "Coca-Cola", "Beverages", "Soft drink", 95, 99, "pc", "coke|cola|soft drink", 40, ""),
    ("SPRITE2", "Sprite 2L", "Sprite", "Beverages", "Soft drink", 95, 99, "pc", "sprite|lemon soda", 30, ""),
    ("WATER1", "Bisleri Water 1L", "Bisleri", "Beverages", "Water", 20, 20, "pc", "water|தண்ணீர்|पानी", 100, ""),
    ("JUICE1", "Real Mixed Fruit Juice 1L", "Real", "Beverages", "Juice", 120, 130, "pc", "juice|fruit juice|जूस", 22, ""),
    ("TENDER", "Tender Coconut Water 200ml", "Cocojal", "Beverages", "Juice", 45, 50, "pc", "coconut water|இளநீர்", 24, ""),
    ("GREENTEA", "Lipton Green Tea 25 bags", "Lipton", "Beverages", "Tea", 150, 165, "pc", "green tea", 12, ""),
    # Snacks
    ("LAYS52", "Lays Magic Masala 52g", "Lays", "Snacks", "Chips", 20, 20, "pc", "chips|lays|चिप्स", 60, ""),
    ("KURKURE", "Kurkure Masala Munch 90g", "Kurkure", "Snacks", "Chips", 20, 20, "pc", "kurkure|namkeen", 50, ""),
    ("MIXTURE", "Haldiram Mixture 400g", "Haldiram", "Snacks", "Namkeen", 95, 100, "pc", "mixture|namkeen|கலவை", 25, ""),
    ("MURUKKU", "Grand Sweets Murukku 200g", "Grand Sweets", "Snacks", "Namkeen", 80, 85, "pc", "murukku|முறுக்கு", 20, ""),
    ("BISCUIT", "Parle-G 800g", "Parle", "Snacks", "Biscuits", 80, 85, "pc", "biscuit|parle g|बिस्कुट", 40, ""),
    ("MARIE", "Britannia Marie Gold 600g", "Britannia", "Snacks", "Biscuits", 70, 75, "pc", "marie|biscuit", 30, ""),
    ("GOODDAY", "Britannia Good Day 600g", "Britannia", "Snacks", "Biscuits", 95, 100, "pc", "good day|cookies|biscuit", 28, ""),
    ("OREO", "Oreo Vanilla 120g", "Oreo", "Snacks", "Biscuits", 30, 30, "pc", "oreo|cookies", 35, ""),
    ("MAGGI", "Maggi Noodles 4 pack", "Maggi", "Snacks", "Instant", 56, 60, "pc", "maggi|noodles|नूडल्स", 45, ""),
    ("YIPPEE", "Yippee Noodles 4 pack", "Sunfeast", "Snacks", "Instant", 50, 55, "pc", "yippee|noodles", 20, "MAGGI"),
    ("PEANUT", "Jabsons Roasted Peanuts 200g", "Jabsons", "Snacks", "Nuts", 60, 65, "pc", "peanuts|groundnut|கடலை|मूंगफली", 25, ""),
    ("ALMOND500", "Happilo Almonds 500g", "Happilo", "Snacks", "Dry fruits", 599, 650, "pc", "almonds|badam|பாதாம்|बादाम", 8, ""),
    ("CASHEW500", "Happilo Cashews 500g", "Happilo", "Snacks", "Dry fruits", 720, 780, "pc", "cashew|முந்திரி|काजू", 6, ""),
    ("RAISIN250", "Happilo Raisins 250g", "Happilo", "Snacks", "Dry fruits", 120, 130, "pc", "raisins|kishmish|किशमिश", 15, ""),
    ("DATES500", "Lion Dates 500g", "Lion", "Snacks", "Dry fruits", 180, 190, "pc", "dates|பேரீச்சம்பழம்|खजूर", 14, ""),
    ("POPCORN", "Act II Popcorn 70g", "Act II", "Snacks", "Instant", 30, 30, "pc", "popcorn", 20, ""),
    # Sweets
    ("MYSORE250", "Sri Krishna Mysore Pak 250g", "Sri Krishna", "Sweets", "Sweets", 150, 160, "pc", "mysore pak|மைசூர் பாகு|sweets", 18, ""),
    ("LADDU250", "Grand Sweets Laddu 250g", "Grand Sweets", "Sweets", "Sweets", 120, 130, "pc", "laddu|லட்டு|लड्डू|sweets", 20, ""),
    ("SOAN", "Haldiram Soan Papdi 500g", "Haldiram", "Sweets", "Sweets", 160, 170, "pc", "soan papdi|sweets|मिठाई", 16, ""),
    ("GULAB", "Haldiram Gulab Jamun Tin 1kg", "Haldiram", "Sweets", "Sweets", 220, 240, "pc", "gulab jamun|गुलाब जामुन|sweets", 12, ""),
    ("RASGULLA", "Haldiram Rasgulla Tin 1kg", "Haldiram", "Sweets", "Sweets", 210, 230, "pc", "rasgulla|रसगुल्ला|sweets", 10, "GULAB"),
    ("DAIRYMILK", "Cadbury Dairy Milk 50g", "Cadbury", "Sweets", "Chocolate", 45, 45, "pc", "chocolate|dairy milk|चॉकलेट", 50, ""),
    ("KITKAT", "KitKat 4 finger 37g", "Nestle", "Sweets", "Chocolate", 30, 30, "pc", "kitkat|chocolate", 40, ""),
    ("CELEB", "Cadbury Celebrations 200g", "Cadbury", "Sweets", "Chocolate", 250, 260, "pc", "celebrations|chocolate|gift", 15, ""),
    ("HALWA", "Tirunelveli Halwa 500g", "Iruttukadai", "Sweets", "Sweets", 280, 300, "pc", "halwa|அல்வா|हलवा", 0, "MYSORE250"),
    # Personal Care
    ("SOAP4", "Lifebuoy Soap 4x125g", "Lifebuoy", "Personal Care", "Soap", 120, 128, "pc", "soap|சோப்பு|साबुन", 40, ""),
    ("DOVE", "Dove Cream Beauty Bar 100g", "Dove", "Personal Care", "Soap", 65, 70, "pc", "soap|dove", 25, ""),
    ("SHAMPOO180", "Clinic Plus Shampoo 180ml", "Clinic Plus", "Personal Care", "Hair", 110, 120, "pc", "shampoo|ஷாம்பு|शैम्पू", 25, ""),
    ("HEADSH", "Head & Shoulders 180ml", "Head & Shoulders", "Personal Care", "Hair", 190, 199, "pc", "shampoo|anti dandruff", 18, "SHAMPOO180"),
    ("HAIROIL", "Parachute Hair Oil 300ml", "Parachute", "Personal Care", "Hair", 130, 140, "pc", "hair oil|तेल", 22, ""),
    ("COLGATE200", "Colgate Strong Teeth 200g", "Colgate", "Personal Care", "Oral", 115, 120, "pc", "toothpaste|colgate|பற்பசை|टूथपेस्ट", 35, ""),
    ("BRUSH", "Oral-B Toothbrush 2pc", "Oral-B", "Personal Care", "Oral", 70, 75, "pc", "toothbrush|ब्रश", 30, ""),
    ("DEO", "Fogg Deodorant 150ml", "Fogg", "Personal Care", "Deo", 199, 220, "pc", "deodorant|deo|perfume", 15, ""),
    ("LOTION", "Vaseline Body Lotion 400ml", "Vaseline", "Personal Care", "Skin", 280, 299, "pc", "body lotion|moisturiser", 12, ""),
    ("SUNSCREEN", "Lakme Sunscreen SPF50 50g", "Lakme", "Personal Care", "Skin", 320, 350, "pc", "sunscreen|spf", 10, ""),
    ("RAZOR", "Gillette Guard Razor 1pc", "Gillette", "Personal Care", "Shaving", 35, 35, "pc", "razor|shaving", 25, ""),
    ("PADS", "Whisper Ultra Clean 30pc", "Whisper", "Personal Care", "Feminine", 260, 280, "pc", "sanitary pads|whisper", 20, ""),
    ("FACEWASH", "Himalaya Neem Face Wash 150ml", "Himalaya", "Personal Care", "Skin", 160, 175, "pc", "face wash|neem", 16, ""),
    ("TALC", "Pond's Talc 400g", "Pond's", "Personal Care", "Skin", 150, 160, "pc", "talcum powder|powder", 12, ""),
    # Household
    ("SURF1", "Surf Excel Matic 1kg", "Surf Excel", "Household", "Laundry", 230, 245, "pc", "detergent|washing powder|सर्फ", 25, ""),
    ("SURF4", "Surf Excel Easy Wash 4kg", "Surf Excel", "Household", "Laundry", 520, 560, "pc", "detergent|washing powder", 8, "SURF1"),
    ("RIN", "Rin Detergent Bar 250g", "Rin", "Household", "Laundry", 20, 20, "pc", "detergent bar|soap", 50, ""),
    ("COMFORT", "Comfort Fabric Conditioner 860ml", "Comfort", "Household", "Laundry", 230, 240, "pc", "fabric conditioner|softener", 10, ""),
    ("VIM", "Vim Dishwash Bar 300g", "Vim", "Household", "Dish", 30, 30, "pc", "dishwash|vim|बर्तन", 45, ""),
    ("VIMLIQ", "Vim Dishwash Liquid 750ml", "Vim", "Household", "Dish", 190, 199, "pc", "dishwash liquid|vim", 18, "VIM"),
    ("HARPIC", "Harpic Toilet Cleaner 1L", "Harpic", "Household", "Cleaning", 190, 199, "pc", "toilet cleaner|harpic", 20, ""),
    ("LIZOL", "Lizol Floor Cleaner 975ml", "Lizol", "Household", "Cleaning", 210, 220, "pc", "floor cleaner|phenyl|lizol", 16, ""),
    ("COLIN", "Colin Glass Cleaner 500ml", "Colin", "Household", "Cleaning", 95, 99, "pc", "glass cleaner", 12, ""),
    ("GOODKNIGHT", "Good Knight Refill 45ml", "Good Knight", "Household", "Insect", 85, 90, "pc", "mosquito repellent|good knight|कॉइल", 30, ""),
    ("HIT", "HIT Cockroach Spray 400ml", "HIT", "Household", "Insect", 210, 225, "pc", "cockroach spray|hit", 10, ""),
    ("GARBAGE", "Garbage Bags Medium 30pc", "Shalimar", "Household", "Cleaning", 90, 99, "pc", "garbage bags|dustbin bags", 25, ""),
    ("MATCH", "Ship Matchbox 10 pack", "Ship", "Household", "Kitchen", 20, 20, "pc", "matchbox|தீப்பெட்டி|माचिस", 60, ""),
    ("FOIL", "Freshwrapp Aluminium Foil 9m", "Freshwrapp", "Household", "Kitchen", 85, 90, "pc", "aluminium foil|foil", 15, ""),
    ("TISSUE", "Origami Kitchen Tissue 2 roll", "Origami", "Household", "Kitchen", 110, 120, "pc", "tissue|kitchen roll", 18, ""),
    ("AGARBATTI", "Cycle Three in One Agarbatti", "Cycle", "Household", "Pooja", 60, 65, "pc", "agarbatti|incense|ஊதுபத்தி|अगरबत्ती", 30, ""),
    ("CAMPHOR", "Mangalam Camphor 100g", "Mangalam", "Household", "Pooja", 70, 75, "pc", "camphor|கற்பூரம்|कपूर", 20, ""),
    ("DIYA", "Clay Diyas 12pc", "Local", "Household", "Pooja", 60, 60, "pc", "diya|lamp|விளக்கு|दीया|diwali", 40, ""),
    ("BATTERY", "Duracell AA 4pc", "Duracell", "Household", "Electrical", 180, 199, "pc", "battery|duracell|बैटरी", 20, ""),
    ("BULB", "Philips LED Bulb 9W", "Philips", "Household", "Electrical", 110, 120, "pc", "led bulb|bulb|बल्ब", 15, ""),
    # Baby
    ("PAMPERS", "Pampers Pants M 56pc", "Pampers", "Baby", "Diapers", 799, 899, "pc", "diapers|pampers|डायपर", 10, ""),
    ("HUGGIES", "Huggies Wonder Pants M 42pc", "Huggies", "Baby", "Diapers", 650, 720, "pc", "diapers|huggies", 0, "PAMPERS"),
    ("CERELAC", "Nestle Cerelac Wheat 300g", "Nestle", "Baby", "Food", 250, 265, "pc", "cerelac|baby food", 14, ""),
    ("LACTOGEN", "Nestle Lactogen 1 400g", "Nestle", "Baby", "Formula", 750, 790, "pc", "formula|lactogen|baby milk", 6, ""),
    ("JJSOAP", "Johnson's Baby Soap 100g", "Johnson's", "Baby", "Care", 75, 80, "pc", "baby soap|johnson", 20, ""),
    ("JJOIL", "Johnson's Baby Oil 200ml", "Johnson's", "Baby", "Care", 190, 199, "pc", "baby oil|johnson", 12, ""),
    ("WIPES", "Himalaya Baby Wipes 72pc", "Himalaya", "Baby", "Care", 150, 165, "pc", "baby wipes|wipes", 18, ""),
    # Pharmacy OTC
    ("DOLO", "Dolo 650 15 tablets", "Micro Labs", "Pharmacy", "Fever", 30, 31, "pc", "paracetamol|fever|headache|dolo|காய்ச்சல்|बुखार|सिरदर्द", 50, ""),
    ("CROCIN", "Crocin Advance 15 tablets", "GSK", "Pharmacy", "Fever", 32, 33, "pc", "paracetamol|fever|headache|crocin", 30, "DOLO"),
    ("ORS", "Electral ORS 21.8g", "FDC", "Pharmacy", "Hydration", 22, 22, "pc", "ors|electral|dehydration", 40, ""),
    ("BANDAID", "Band-Aid 10pc", "Band-Aid", "Pharmacy", "First aid", 30, 30, "pc", "band aid|plaster", 25, ""),
    ("DETTOL", "Dettol Antiseptic 250ml", "Dettol", "Pharmacy", "First aid", 110, 115, "pc", "dettol|antiseptic", 20, ""),
    ("VICKS", "Vicks VapoRub 50ml", "Vicks", "Pharmacy", "Cold", 150, 160, "pc", "vicks|cold|cough|सर्दी", 18, ""),
    ("STREPSILS", "Strepsils 8 lozenges", "Strepsils", "Pharmacy", "Cold", 40, 40, "pc", "strepsils|sore throat|cough", 22, ""),
    ("ENO", "Eno Fruit Salt 100g", "Eno", "Pharmacy", "Digestive", 85, 90, "pc", "eno|acidity|antacid", 20, ""),
    ("DIGENE", "Digene Tablets 15pc", "Digene", "Pharmacy", "Digestive", 35, 36, "pc", "digene|acidity|antacid", 18, "ENO"),
    ("MASK", "3-ply Face Mask 10pc", "Generic", "Pharmacy", "Hygiene", 50, 60, "pc", "mask|face mask", 30, ""),
    ("SANITIZER", "Dettol Hand Sanitizer 200ml", "Dettol", "Pharmacy", "Hygiene", 100, 110, "pc", "sanitizer|hand sanitizer", 15, ""),
    ("GLUCOSE", "Glucon-D 500g", "Glucon-D", "Pharmacy", "Hydration", 140, 150, "pc", "glucose|glucon d|energy", 12, ""),
    # Fruits & Vegetables (per kg)
    ("TOMATO", "Tomato", "Local", "Fruits & Vegetables", "Vegetables", 30, 30, "kg", "tomato|தக்காளி|टमाटर", 50, ""),
    ("ONION", "Onion", "Local", "Fruits & Vegetables", "Vegetables", 35, 35, "kg", "onion|வெங்காயம்|प्याज", 60, ""),
    ("POTATO", "Potato", "Local", "Fruits & Vegetables", "Vegetables", 28, 28, "kg", "potato|உருளைக்கிழங்கு|आलू", 55, ""),
    ("CARROT", "Carrot", "Local", "Fruits & Vegetables", "Vegetables", 50, 50, "kg", "carrot|கேரட்|गाजर", 25, ""),
    ("BEANS", "French Beans", "Local", "Fruits & Vegetables", "Vegetables", 60, 60, "kg", "beans|பீன்ஸ்", 15, ""),
    ("BRINJAL", "Brinjal", "Local", "Fruits & Vegetables", "Vegetables", 40, 40, "kg", "brinjal|eggplant|கத்தரிக்காய்|बैंगन", 20, ""),
    ("LADYFINGER", "Lady Finger", "Local", "Fruits & Vegetables", "Vegetables", 45, 45, "kg", "okra|lady finger|வெண்டைக்காய்|भिंडी", 18, ""),
    ("CORIANDER", "Coriander Leaves bunch", "Local", "Fruits & Vegetables", "Vegetables", 10, 10, "pc", "coriander leaves|கொத்தமல்லி|धनिया", 30, ""),
    ("CURRYLEAF", "Curry Leaves bunch", "Local", "Fruits & Vegetables", "Vegetables", 5, 5, "pc", "curry leaves|கறிவேப்பிலை", 30, ""),
    ("GINGER", "Ginger", "Local", "Fruits & Vegetables", "Vegetables", 80, 80, "kg", "ginger|இஞ்சி|अदरक", 10, ""),
    ("GARLIC", "Garlic", "Local", "Fruits & Vegetables", "Vegetables", 120, 120, "kg", "garlic|பூண்டு|लहसुन", 12, ""),
    ("LEMON", "Lemon 6pc", "Local", "Fruits & Vegetables", "Vegetables", 30, 30, "pc", "lemon|எலுமிச்சை|नींबू", 40, ""),
    ("BANANA", "Banana Robusta dozen", "Local", "Fruits & Vegetables", "Fruits", 50, 50, "pc", "banana|வாழைப்பழம்|केला", 30, ""),
    ("APPLE", "Apple Shimla", "Local", "Fruits & Vegetables", "Fruits", 180, 180, "kg", "apple|ஆப்பிள்|सेब", 20, ""),
    ("ORANGE", "Orange", "Local", "Fruits & Vegetables", "Fruits", 90, 90, "kg", "orange|ஆரஞ்சு|संतरा", 18, ""),
    ("GRAPES", "Grapes Green", "Local", "Fruits & Vegetables", "Fruits", 110, 110, "kg", "grapes|திராட்சை|अंगूर", 12, ""),
    ("MANGO", "Mango Banganapalli", "Local", "Fruits & Vegetables", "Fruits", 150, 150, "kg", "mango|மாம்பழம்|आम", 0, "APPLE"),
    ("PAPAYA", "Papaya", "Local", "Fruits & Vegetables", "Fruits", 40, 40, "kg", "papaya|பப்பாளி|पपीता", 10, ""),
    ("WATERMELON", "Watermelon", "Local", "Fruits & Vegetables", "Fruits", 25, 25, "kg", "watermelon|தர்பூசணி|तरबूज", 15, ""),
    ("COCONUT", "Coconut 1pc", "Local", "Fruits & Vegetables", "Vegetables", 35, 35, "pc", "coconut|தேங்காய்|नारियल", 40, ""),
    # Frozen
    ("PEAS500", "Safal Frozen Peas 500g", "Safal", "Frozen", "Vegetables", 90, 95, "pc", "frozen peas|peas|मटर", 15, ""),
    ("MCCAIN", "McCain French Fries 420g", "McCain", "Frozen", "Snacks", 110, 120, "pc", "french fries|fries", 12, ""),
    ("PARATHA", "ID Malabar Parota 5pc", "ID", "Frozen", "Ready", 85, 90, "pc", "parota|parotta|பரோட்டா", 14, ""),
    ("IDLIBATTER", "ID Idli Dosa Batter 1kg", "ID", "Frozen", "Ready", 95, 99, "pc", "idli batter|dosa batter|மாவு", 20, ""),
    ("ICECREAM", "Amul Vanilla Ice Cream 1L", "Amul", "Frozen", "Ice cream", 180, 199, "pc", "ice cream|vanilla|आइसक्रीम", 10, ""),
    ("CHICKEN", "Chicken Curry Cut 1kg", "Suguna", "Frozen", "Meat", 240, 250, "pc", "chicken|கோழி|चिकन", 8, ""),
    # Pet
    ("PEDIGREE", "Pedigree Adult 3kg", "Pedigree", "Pet", "Dog", 650, 700, "pc", "dog food|pedigree", 6, ""),
    ("WHISKAS", "Whiskas Adult 1.2kg", "Whiskas", "Pet", "Cat", 380, 400, "pc", "cat food|whiskas", 8, ""),
    ("DOGBISC", "Pedigree Biscrok 500g", "Pedigree", "Pet", "Dog", 150, 160, "pc", "dog biscuits|treats", 10, ""),
]

SUPPLIER = {
    "Staples": "sup-metro-cash", "Oils & Ghee": "sup-metro-cash", "Dairy": "sup-aavin",
    "Bakery": "sup-aavin", "Beverages": "sup-metro-cash", "Snacks": "sup-metro-cash",
    "Sweets": "sup-metro-cash", "Personal Care": "sup-hul", "Household": "sup-hul",
    "Baby": "sup-hul", "Pharmacy": "sup-apollo", "Fruits & Vegetables": "sup-koyambedu",
    "Frozen": "sup-aavin", "Pet": "sup-hul",
}


def ean13(seed: int) -> str:
    body = f"890{seed:09d}"
    total = sum(int(d) * (1 if i % 2 == 0 else 3) for i, d in enumerate(body))
    return body + str((10 - total % 10) % 10)


HEADERS = ["sku", "name", "brand", "category", "subcategory", "price", "mrp", "unit", "tags",
           "on_hand", "substitutes", "barcode", "aisle", "bay", "shelf", "side", "supplier_id",
           "reorder_point", "reorder_qty", "lead_time_days", "image_url"]


def main() -> None:
    counters: dict[str, int] = {}
    with OUT.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(HEADERS)
        for i, (sku, name, brand, cat, sub, price, mrp, unit, tags, on_hand, subs) in enumerate(ITEMS, 1):
            aisle = AISLE[cat]
            n = counters.get(aisle, 0)
            counters[aisle] = n + 1
            bay, shelf, side = n // 6 % 4 + 1, n % 3 + 1, "left" if (n // 3) % 2 == 0 else "right"
            lead = 1 if cat in ("Dairy", "Bakery", "Fruits & Vegetables") else 3
            w.writerow([sku, name, brand, cat, sub, price, mrp, unit, tags, on_hand, subs, ean13(i),
                        aisle, bay, shelf, side, SUPPLIER[cat], max(3, on_hand // 4), max(10, on_hand // 2),
                        lead, f"/products/{sku.lower()}.png"])
    print(f"wrote {len(ITEMS)} products to {OUT}")


if __name__ == "__main__":
    main()
