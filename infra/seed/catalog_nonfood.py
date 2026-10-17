"""Non-food catalogue for the demo supermarket. Same entry format as catalog_food.py:
"Brand|Product name|size1/size2|price1/price2". Prices are indicative Indian MRPs for demonstration."""

# (main category, subcategory) -> (gst %, shelf life days or None for durables, default unit)
META = {
    ("Personal Care and Hygiene", "Skin Care"): (18, 730, "pc"), ("Personal Care and Hygiene", "Beauty and Cosmetics"): (18, 730, "pc"),
    ("Personal Care and Hygiene", "Hair Care"): (18, 730, "pc"), ("Personal Care and Hygiene", "Toiletries and Bath Products"): (18, 730, "pc"),
    ("Personal Care and Hygiene", "Fragrances"): (18, 1095, "pc"), ("Personal Care and Hygiene", "Personal Hygiene and Wellness"): (12, 1095, "pc"),
    ("Household Cleaning and Maintenance", "General Household Cleaning"): (18, 730, "pc"), ("Household Cleaning and Maintenance", "Toilet and Bathroom Products"): (18, 730, "pc"),
    ("Household Cleaning and Maintenance", "Kitchen Cleaning"): (18, 730, "pc"), ("Household Cleaning and Maintenance", "Laundry and Fabric Care"): (18, 730, "pc"),
    ("Household Cleaning and Maintenance", "Pest Control"): (18, 730, "pc"), ("Household Cleaning and Maintenance", "Home Maintenance"): (18, None, "pc"),
    ("Home and Kitchen Essentials", "Kitchen Utilities"): (18, None, "pc"), ("Home and Kitchen Essentials", "Cooking Equipment and Accessories"): (18, None, "pc"),
    ("Home and Kitchen Essentials", "Vessels and Tableware"): (18, None, "pc"), ("Home and Kitchen Essentials", "Food Storage and Serving"): (18, None, "pc"),
    ("Home and Kitchen Essentials", "Plastic Products"): (18, None, "pc"), ("Home and Kitchen Essentials", "Home Organization"): (18, None, "pc"),
    ("Furniture and Furnishings", "Furniture"): (18, None, "pc"), ("Furniture and Furnishings", "Home Furnishings"): (12, None, "pc"), ("Furniture and Furnishings", "Carpets and Floor Coverings"): (12, None, "pc"),
    ("Home Decor and Lifestyle", "Home Decor"): (18, None, "pc"), ("Home Decor and Lifestyle", "Lighting and Electrical Accessories"): (18, None, "pc"),
    ("Home Decor and Lifestyle", "Artificial and Natural Plants"): (5, None, "pc"), ("Home Decor and Lifestyle", "Fragrances and Ambience"): (18, 730, "pc"),
    ("Pooja and Religious Products", "Daily Pooja Essentials"): (5, 730, "pc"), ("Pooja and Religious Products", "Pooja Accessories"): (12, None, "pc"),
    ("Pooja and Religious Products", "Flowers and Offerings"): (0, 2, "pc"), ("Pooja and Religious Products", "Festive and Religious Products"): (12, 730, "pc"),
    ("Pooja and Religious Products", "Religious Books and Accessories"): (0, None, "pc"),
    ("Electronics and Technology", "Consumer Electronics"): (18, None, "pc"), ("Electronics and Technology", "Mobile Accessories"): (18, None, "pc"),
    ("Electronics and Technology", "Computer and Office Electronics"): (18, None, "pc"), ("Electronics and Technology", "Small Home Appliances"): (18, None, "pc"),
    ("Electronics and Technology", "Batteries and Power"): (18, 1095, "pc"), ("Electronics and Technology", "Smart Home Products"): (18, None, "pc"),
    ("Stationery, Books and Office Supplies", "Writing Instruments"): (12, None, "pc"), ("Stationery, Books and Office Supplies", "Paper Products"): (12, None, "pc"),
    ("Stationery, Books and Office Supplies", "School Supplies"): (12, None, "pc"), ("Stationery, Books and Office Supplies", "Office Supplies"): (18, None, "pc"),
    ("Stationery, Books and Office Supplies", "Books and Learning Materials"): (0, None, "pc"), ("Stationery, Books and Office Supplies", "Diaries and Planners"): (12, None, "pc"),
    ("Pet Products", "Pet Food"): (18, 365, "pc"), ("Pet Products", "Pet Accessories"): (18, None, "pc"), ("Pet Products", "Pet Grooming and Hygiene"): (18, 730, "pc"),
    ("Pet Products", "Products for Other Pets"): (18, 365, "pc"),
    ("Automobile Care and Accessories", "Vehicle Cleaning"): (18, 1095, "pc"), ("Automobile Care and Accessories", "Car Detailing"): (18, 1095, "pc"),
    ("Automobile Care and Accessories", "Automobile Accessories"): (18, None, "pc"), ("Automobile Care and Accessories", "Automotive Maintenance Essentials"): (18, 730, "pc"),
    ("Baby and Infant Products", "Baby Care"): (12, 730, "pc"), ("Baby and Infant Products", "Baby Feeding and Clothing"): (5, None, "pc"),
    ("Health and First Aid", "First Aid"): (12, 1095, "pc"), ("Health and First Aid", "Wellness and Protection"): (12, 1095, "pc"),
    ("Travel and Luggage", "Luggage and Bags"): (18, None, "pc"), ("Travel and Luggage", "Travel Accessories"): (18, None, "pc"),
    ("Clothing and Accessories", "Basic Apparel and Innerwear"): (5, None, "pc"), ("Clothing and Accessories", "Footwear and Accessories"): (12, None, "pc"),
    ("Sports, Fitness and Outdoor", "Fitness"): (18, None, "pc"), ("Sports, Fitness and Outdoor", "Sports and Outdoor"): (12, None, "pc"),
    ("Toys, Games and Hobbies", "Toys"): (12, None, "pc"), ("Toys, Games and Hobbies", "Games and Hobbies"): (12, None, "pc"),
    ("Hardware and DIY", "Hand Tools"): (18, None, "pc"), ("Hardware and DIY", "Fasteners, Locks and Repair"): (18, None, "pc"),
    ("Garden and Outdoor Living", "Gardening"): (5, None, "pc"), ("Garden and Outdoor Living", "Outdoor Living"): (18, None, "pc"),
    ("Gift Items and Seasonal Products", "Gifting and Party Supplies"): (12, None, "pc"), ("Gift Items and Seasonal Products", "Festive Decorations"): (12, None, "pc"),
    ("Disposable and Eco-Friendly Products", "Disposables"): (18, None, "pc"), ("Disposable and Eco-Friendly Products", "Reusable and Eco-Friendly"): (12, None, "pc"),
}

ITEMS = {
("Personal Care and Hygiene", "Skin Care"): [
    "Himalaya|Purifying Neem Face Wash|100 ml/200 ml|125/230", "Garnier|Men Oil Clear Face Wash|100 ml|165", "Cetaphil|Gentle Skin Cleanser|125 ml|420", "Plum|Green Tea Toner|200 ml|390",
    "Nivea|Soft Moisturising Cream|100 ml/200 ml|140/255", "Pond's|Super Light Gel|147 g|299", "Minimalist|10% Niacinamide Serum|30 ml|599", "Mamaearth|Vitamin C Serum|30 ml|599",
    "Lotus|Safe Sun Sunscreen SPF 40|100 g|340", "Minimalist|Sunscreen SPF 50|50 g|399", "Mamaearth|Ubtan Face Mask|100 g|499", "Himalaya|Gentle Exfoliating Walnut Scrub|100 g|150",
    "Nivea|Lip Balm Cherry|4.8 g|199", "Himalaya|Under Eye Cream|15 ml|199", "Clean & Clear|Acne Clearing Gel|20 g|160", "Vaseline|Intensive Care Body Lotion|400 ml|345",
    "The Body Shop|Shea Body Butter|200 ml|1395", "Parachute|Advansed Body Lotion|250 ml|175", "Boroline|Antiseptic Cream|20 g|45", "Local|Aloe Vera Gel|150 ml|120",
],
("Personal Care and Hygiene", "Beauty and Cosmetics"): [
    "Lakme|9 to 5 Primer + Matte Foundation|25 ml|425", "Maybelline|Fit Me Concealer|6.8 ml|299", "Lakme|Rose Powder|40 g|175", "Maybelline|Fit Me Compact|8 g|299",
    "Lakme|Absolute Blush|6 g|650", "Swiss Beauty|Highlighter|8 g|299", "Lakme|Eyeconic Kajal|0.35 g|250", "Maybelline|Colossal Kajal|0.35 g|199",
    "Maybelline|Lash Sensational Mascara|9.5 ml|499", "Lakme|9 to 5 Primer + Matte Lipstick|3.6 g|450", "Maybelline|Superstay Matte Ink|5 ml|699", "Nykaa|Lip Gloss|4 ml|399",
    "Garnier|Micellar Water Makeup Remover|125 ml|199", "Vega|Makeup Brush Set|6 pcs|450", "Real Techniques|Makeup Sponge|1 pc|399", "Colorbar|Nail Lacquer|12 ml|250",
    "Lakme|Sunscreen Tinted|50 g|250", "Local|Kumkum (Bindi) Liquid|10 ml|35", "Shilpa|Bindi Sheet|1 pc|20",
],
("Personal Care and Hygiene", "Hair Care"): [
    "Meera|Hairwash Powder|120 g|95", "Chik|Shampoo Egg|180 ml|115", "Dove|Daily Shine Shampoo|340 ml/650 ml|299/499", "Head & Shoulders|Anti-Dandruff Shampoo|340 ml|310",
    "Pantene|Hair Fall Control Shampoo|340 ml|285", "Tresemme|Keratin Smooth Conditioner|190 ml|210", "Dove|Hair Fall Rescue Conditioner|175 ml|199", "Parachute|Coconut Hair Oil|300 ml/600 ml|150/290",
    "Indulekha|Bringha Hair Oil|100 ml|432", "Bajaj|Almond Drops Hair Oil|300 ml|200", "Livon|Hair Serum|100 ml|240", "L'Oreal|Hair Spa Mask|490 g|650",
    "Godrej|Expert Hair Colour Black|20 g|35", "Garnier|Color Naturals Brown|70 ml|199", "Set Wet|Styling Gel|100 ml|120", "Gatsby|Hair Spray|250 ml|250",
    "Roots|Wooden Comb|1 pc|120", "Vega|Paddle Hair Brush|1 pc|250", "Local|Hair Rubber Bands|12 pcs|30", "Local|Hair Clips Set|6 pcs|50",
],
("Personal Care and Hygiene", "Toiletries and Bath Products"): [
    "Medimix|Ayurvedic Soap|125 g/4x125 g|40/150", "Mysore Sandal|Soap|125 g|50", "Chandrika|Ayurvedic Soap|125 g|45", "Hamam|Soap|150 g|48", "Dove|Cream Beauty Bar|100 g|60",
    "Lifebuoy|Total 10 Soap|125 g|35", "Pears|Pure & Gentle|125 g|65", "Dettol|Original Soap|125 g|45", "Nivea|Shower Gel Fresh|250 ml|250", "Fiama|Body Wash Lemongrass|250 ml|235",
    "Dettol|Hand Wash Original|200 ml/750 ml|99/199", "Lifebuoy|Hand Sanitizer|50 ml|40", "Colgate|Strong Teeth|200 g|120", "Colgate|MaxFresh|150 g|110", "Sensodyne|Sensitive|75 g|135",
    "Dabur|Red Toothpaste|200 g|115", "Closeup|Deep Action|150 g|95", "Colgate|Toothbrush ZigZag|3 pcs|90", "Oral-B|Toothbrush Pro-Health|1 pc|60", "Listerine|Mouthwash Cool Mint|250 ml|160",
    "Colgate|Dental Floss|50 m|120", "Local|Tongue Cleaner Copper|1 pc|60", "Gillette|Mach3 Razor|1 pc|299", "Gillette|Shaving Foam|418 g|299", "Bombay Shaving|Shaving Cream|100 g|199",
    "Veet|Hair Removal Cream|50 g|99", "Local|Bath Loofah|1 pc|60", "Local|Cotton Bath Towel|1 pc|350", "Paseo|Facial Tissues|200 pcs|120", "Himalaya|Wet Wipes|25 pcs|85",
    "Nivea|Deodorant Fresh Active|150 ml|210", "Fogg|Deo Marco|120 ml|230",
],
("Personal Care and Hygiene", "Fragrances"): [
    "Fogg|Scent Xtremo|100 ml|599", "Wild Stone|Edge Perfume|100 ml|450", "Engage|Eau de Parfum W1|90 ml|499", "Skinn by Titan|Raw EDP|50 ml|1850",
    "Bella Vita|CEO Man Perfume|100 ml|599", "Nivea|Body Mist Fresh|100 ml|250", "Yardley|London Lavender Body Spray|150 ml|210", "Rexona|Roll-On Shower Clean|50 ml|140",
    "Local|Attar Rose (Alcohol-free)|10 ml|250", "Local|Attar Sandal|10 ml|300", "Soulflower|Lavender Essential Oil|15 ml|350", "Godrej|Aer Room Freshener|240 ml|210",
    "Ambi Pur|Air Effects Lavender|275 g|299", "Engage|Gift Set Perfume Duo|2 pcs|799", "Fogg|Fragrant Body Spray Fresh Aqua|150 ml|199",
],
("Personal Care and Hygiene", "Personal Hygiene and Wellness"): [
    "Whisper|Ultra Clean XL|30 pcs|299", "Stayfree|Secure XL|40 pcs|260", "Sofy|Antibacteria XL|28 pcs|220", "Whisper|Choice Regular|20 pcs|70",
    "Pee Safe|Menstrual Cup|1 pc|499", "Sirona|Tampons Regular|20 pcs|280", "Carefree|Pantyliners|20 pcs|90", "Friends|Adult Diapers Large|10 pcs|550",
    "Johnson's|Cotton Buds|100 pcs|60", "Local|Cotton Roll|100 g|60", "Dettol|Antiseptic Liquid|250 ml|175", "Local|Hot Water Bag|1 pc|250",
    "Durex|Condoms Extra Thin|10 pcs|280", "Whisper|Intimate Wash|100 ml|199", "Local|Nail Cutter|1 pc|40", "Sirona|Period Pain Relief Patch|5 pcs|299",
],
("Household Cleaning and Maintenance", "General Household Cleaning"): [
    "Lizol|Floor Cleaner Citrus|975 ml/2 L|199/360", "Harpic|Bathroom Cleaner|1 L|199", "Dettol|Disinfectant Spray|170 g|285", "Colin|Glass Cleaner|500 ml|110",
    "Mr. Muscle|Kitchen Degreaser|500 ml|199", "Cif|Cream Cleaner|500 ml|160", "Scotch-Brite|Scrub Sponge|3 pcs|90", "Gala|Microfibre Cloth|2 pcs|150",
    "Gala|Spin Mop Set|1 pc|1299", "Local|Soft Broom (Kooda)|1 pc|120", "Local|Hard Broom (Coconut)|1 pc|60", "Gala|Dustpan with Brush|1 pc|180",
    "Nilkamal|Bucket 20 L|1 pc|320", "Local|Cleaning Gloves|1 pair|90", "Local|Floor Wiper|1 pc|190", "Gala|Toilet Brush|1 pc|160", "Local|Phenyl|1 L|70",
],
("Household Cleaning and Maintenance", "Toilet and Bathroom Products"): [
    "Harpic|Power Plus Toilet Cleaner|1 L|199", "Domex|Toilet Cleaner|500 ml|99", "Odonil|Toilet Air Freshener Block|75 g|60", "Harpic|Hygienic Toilet Freshener|1 pc|60",
    "Sanifresh|Shine|500 ml|95", "Drainex|Drain Cleaner|50 g|60", "Local|Bathroom Organizer Shelf|1 pc|350", "Local|Soap Dish|1 pc|60",
    "Local|Toilet Paper Holder Steel|1 pc|250", "Airwick|Freshmatic Refill Lavender|250 ml|299", "Godrej|Aer Pocket Bathroom Fragrance|10 g|55", "Local|Bathroom Mat Anti-slip|1 pc|280",
    "Local|Bathroom Storage Rack|1 pc|450", "Local|Toilet Paper Rolls|4 pcs|150", "Harpic|Flushmatic Blue|50 g|60",
],
("Household Cleaning and Maintenance", "Kitchen Cleaning"): [
    "Vim|Dishwash Liquid Gel Lemon|500 ml/1.8 L|110/350", "Pril|Perfect Dishwash Gel|750 ml|165", "Vim|Dishwash Bar|500 g|50", "Exo|Dishwash Bar|500 g|48",
    "Finish|Dishwasher Tablets|28 pcs|650", "Scotch-Brite|Scrub Pad|3 pcs|60", "Local|Steel Wool Scrubber|2 pcs|30", "Vim|Sink Cleaner Powder|500 g|45",
    "Local|Sink Strainer|1 pc|40", "Local|Garbage Bags Medium|30 pcs|95", "Local|Garbage Bags Large Black|30 pcs|140", "Scotch-Brite|Kitchen Wipe Cloth|3 pcs|90",
    "Local|Chimney Cleaner Spray|500 ml|180", "Local|Dish Drying Rack|1 pc|450", "Gala|Bottle Cleaning Brush|1 pc|90",
],
("Household Cleaning and Maintenance", "Laundry and Fabric Care"): [
    "Surf Excel|Easy Wash Powder|1 kg/4 kg|130/480", "Ariel|Matic Front Load Powder|2 kg|420", "Tide|Plus Powder|2 kg|250", "Nirma|Washing Powder|1 kg|65",
    "Surf Excel|Matic Liquid Top Load|2 L|400", "Comfort|Fabric Conditioner Blue|860 ml|240", "Vanish|Stain Remover Liquid|400 ml|200", "Rin|Detergent Bar|250 g|20",
    "Ujala|Supreme Whitener|250 ml|75", "Robin|Bleach Liquid|500 ml|60", "Nilkamal|Laundry Basket|1 pc|450", "Local|Cloth Clips|24 pcs|60",
    "Local|Cloth Drying Stand|1 pc|1200", "Local|Ironing Board|1 pc|1500", "Local|Lint Remover|1 pc|250", "Godrej|Ezee Liquid Detergent Woollens|500 ml|120",
],
("Household Cleaning and Maintenance", "Pest Control"): [
    "Good Knight|Gold Flash Liquid Refill|45 ml|85", "Good Knight|Machine + Refill|1 pc|120", "All Out|Ultra Refill|45 ml|80", "Mortein|Spray|425 ml|270",
    "Odomos|Mosquito Repellent Cream|100 g|90", "Local|Mosquito Net Double Bed|1 pc|450", "Hit|Cockroach Spray|400 ml|230", "Lal Hit|Crawling Insect|400 ml|230",
    "Local|Ant Chalk|1 pc|20", "Local|Rat Glue Trap|1 pc|60", "Local|Mosquito Coil|10 pcs|40", "Good Knight|Fabric Roll-On|8 ml|75", "Local|Fly Catcher Sheet|1 pc|40",
],
("Household Cleaning and Maintenance", "Home Maintenance"): [
    "Fevicol|MR Adhesive|100 g|45", "Fevikwik|Instant Adhesive|3 g|20", "3M|Scotch Transparent Tape|1 pc|30", "Local|Duct Tape|1 pc|120", "Local|Adhesive Wall Hooks|6 pcs|90",
    "Local|Nails Assorted|100 g|40", "Local|Screws Assorted|100 pcs|80", "Duracell|AA Batteries|4 pcs|140", "Eveready|AAA Batteries|4 pcs|70", "Philips|LED Bulb 9W|1 pc|120",
    "Anchor|Extension Cord 4 Socket|1 pc|450", "Stanley|Tool Kit 38 pcs|1 pc|1400", "WD-40|Lubricant Spray|170 g|250", "Local|Silicone Sealant|1 pc|150", "Local|Electrical Tape|1 pc|25",
],
("Home and Kitchen Essentials", "Kitchen Utilities"): [
    "Tupperware|Dry Storage Container 1.7 L|1 pc|450", "Cello|Lunch Box 3 Container|1 pc|550", "Milton|Thermosteel Flask 1 L|1 pc|1050", "Milton|Water Bottle 1 L|1 pc|250",
    "Borosil|Glass Jar 1 L|1 pc|320", "Local|Spice Box (Masala Dabba)|1 pc|350", "Local|Oil Dispenser|1 pc|180", "Local|Measuring Cup Set|4 pcs|150", "Local|Chopping Board Wooden|1 pc|250",
    "Local|Peeler Steel|1 pc|60", "Local|Grater Box|1 pc|180", "Victorinox|Kitchen Knife 8 inch|1 pc|950", "Local|Kitchen Scissors|1 pc|120", "Local|Strainer Steel|1 pc|90",
    "Local|Colander|1 pc|200", "Local|Funnel Set|3 pcs|60", "Local|Ladle Steel|1 pc|80", "Local|Spatula Silicone|1 pc|120", "Local|Tongs|1 pc|90", "Local|Kitchen Rack 3 Tier|1 pc|850",
],
("Home and Kitchen Essentials", "Cooking Equipment and Accessories"): [
    "Prestige|Pressure Cooker 3 L|1 pc|1650", "Prestige|Pressure Cooker 5 L|1 pc|2200", "Hawkins|Contura 3 L|1 pc|1900", "Prestige|Non-stick Fry Pan 24 cm|1 pc|950",
    "Prestige|Saucepan 1.5 L|1 pc|750", "Local|Iron Kadai Seasoned|1 pc|650", "Prestige|Omega Kadai 240 mm|1 pc|1100", "Local|Cast Iron Dosa Tawa|1 pc|850",
    "Prestige|Non-stick Dosa Tawa|1 pc|700", "Local|Idli Plate Stand 4 Tier|1 pc|450", "Local|Paniyaram Pan Iron|1 pc|450", "Borosil|Baking Tray|1 pc|550",
    "Borosil|Oven-safe Dish 1.5 L|1 pc|650", "Local|Kitchen Weighing Scale Digital|1 pc|650", "Local|Cooking Thermometer|1 pc|450", "Prestige|Milk Boiler|1 pc|900",
    "Local|Appam Pan|1 pc|400", "Local|Steel Idiyappam Maker|1 pc|350",
],
("Home and Kitchen Essentials", "Vessels and Tableware"): [
    "Local|Stainless Steel Plate 12 inch|1 pc|180", "Local|Steel Bowl Set|6 pcs|300", "Local|Steel Tumbler Set|6 pcs|360", "Local|Steel Spoon Set|6 pcs|120", "Local|Fork Set|6 pcs|120",
    "Local|Serving Tray Steel|1 pc|250", "Larah|Opalware Dinner Set 19 pcs|1 pc|1900", "Local|Copper Water Bottle|1 pc|650", "Local|Brass Uruli|1 pc|1800",
    "Local|Banana Leaf Shaped Steel Plate|1 pc|350", "Local|Dabara Tumbler Set (Filter Coffee)|1 pc|280", "Borosil|Glass Tumbler Set|6 pcs|450", "Local|Ceramic Dinner Plate|1 pc|220",
    "Local|Melamine Dinner Set 24 pcs|1 pc|1500", "Local|Kuzhi Karandi (Ladle) Set|3 pcs|250", "Local|Steel Water Jug 2 L|1 pc|450",
],
("Home and Kitchen Essentials", "Food Storage and Serving"): [
    "Milton|Casserole 2.5 L|1 pc|750", "Cello|Insulated Casserole Set 3 pcs|1 pc|1600", "Local|Serving Bowl Steel|1 pc|180", "Local|Food Cover Net|1 pc|120",
    "Milton|Insulated Water Jug 2 L|1 pc|850", "Tupperware|Fridge Container Set 4 pcs|1 pc|950", "Local|Glass Storage Box|1 pc|250", "Local|Disposable Foil Containers|10 pcs|120",
    "Local|Aluminium Foil 72 m|1 pc|220", "Local|Cling Film 30 m|1 pc|150", "Local|Hot Pot 1.5 L|1 pc|450", "Local|Salad Bowl Glass|1 pc|350",
],
("Home and Kitchen Essentials", "Plastic Products"): [
    "Nilkamal|Bucket 25 L|1 pc|380", "Local|Mug 1.5 L|1 pc|60", "Nilkamal|Tub 35 L|1 pc|450", "Nilkamal|Storage Box 60 L|1 pc|1200", "Local|Basket Medium|1 pc|150",
    "Nilkamal|Drawer Cabinet 4|1 pc|2400", "Local|Laundry Basket Plastic|1 pc|400", "Nilkamal|Stool|1 pc|350", "Nilkamal|Chair Armless|1 pc|750", "Local|Kitchen Container Set 6 pcs|1 pc|450",
    "Local|Dustbin Pedal 12 L|1 pc|450", "Local|Plastic Tray|1 pc|90", "Local|Hanging Organizer|1 pc|250", "Local|Water Drum 50 L|1 pc|900",
],
("Home and Kitchen Essentials", "Home Organization"): [
    "Local|Wardrobe Organizer 6 Cell|1 pc|450", "Local|Drawer Divider Set|1 pc|350", "Nilkamal|Shoe Rack 3 Tier|1 pc|1500", "Local|Storage Rack Steel 4 Tier|1 pc|2200",
    "Local|Hangers Plastic|12 pcs|180", "Local|Foldable Storage Box|1 pc|300", "Local|Under-bed Storage Bag|1 pc|450", "Local|Wall Hook Rail|1 pc|220", "Local|Floating Shelf|1 pc|650",
    "Local|Multipurpose Organizer Caddy|1 pc|280", "Local|Vacuum Storage Bags|4 pcs|400", "Local|Key Holder Wall|1 pc|250",
],
("Furniture and Furnishings", "Furniture"): [
    "Nilkamal|3-Seater Sofa Fabric|1 pc|24000", "Local|Armchair|1 pc|8500", "Local|Recliner Single|1 pc|18000", "Local|Coffee Table Wooden|1 pc|5500", "Nilkamal|Dining Table 4 Seater|1 pc|14000",
    "Local|Dining Chair|1 pc|2800", "Local|Queen Bed Engineered Wood|1 pc|16000", "Sleepwell|Mattress Queen 6 inch|1 pc|14000", "Local|Wardrobe 2 Door|1 pc|12500", "Local|Bedside Table|1 pc|3200",
    "Local|Dressing Table|1 pc|9500", "Local|Study Table|1 pc|4500", "Local|Office Desk|1 pc|7500", "Nilkamal|Office Chair|1 pc|6500", "Local|Bookshelf 5 Tier|1 pc|5500",
    "Local|Shoe Cabinet|1 pc|4200", "Local|TV Unit|1 pc|6800", "Local|Storage Cabinet|1 pc|5200", "Supreme|Plastic Folding Chair|1 pc|950", "Local|Garden Chair Set 2|1 pc|3200",
],
("Furniture and Furnishings", "Home Furnishings"): [
    "Local|Curtains Door Set|2 pcs|1200", "Local|Curtain Rod 6 ft|1 pc|450", "Local|Cushion Covers Set|5 pcs|600", "Local|Cushions|2 pcs|500", "Bombay Dyeing|Double Bedsheet Cotton|1 pc|1100",
    "Local|Pillow Covers|2 pcs|250", "Local|Blanket Single Fleece|1 pc|700", "Local|Comforter Double|1 pc|2200", "Local|Quilt Jaipuri Double|1 pc|1800", "Local|Mattress Protector Queen|1 pc|900",
    "Local|Bath Towel Set|2 pcs|700", "Local|Tablecloth 6 Seater|1 pc|650", "Local|Table Runner|1 pc|350", "Local|Sofa Cover 3 Seater|1 pc|1200", "Local|Throw Blanket|1 pc|850",
],
("Furniture and Furnishings", "Carpets and Floor Coverings"): [
    "Local|Area Rug 5x7 ft|1 pc|2800", "Local|Carpet Runner 2x6 ft|1 pc|1200", "Local|Door Mat Coir|1 pc|250", "Local|Welcome Mat|1 pc|350", "Local|Bathroom Mat Microfibre|1 pc|400",
    "Local|Kitchen Mat Anti-fatigue|1 pc|850", "Local|Anti-slip Mat|1 pc|300", "Local|Prayer Mat (Jaanamaz)|1 pc|450", "Local|Artificial Grass Mat 4x6 ft|1 pc|1500", "Local|Outdoor Mat Rubber|1 pc|550",
],
("Home Decor and Lifestyle", "Home Decor"): [
    "Local|Wall Art Canvas Set|3 pcs|1800", "Local|Framed Print Tanjore Style|1 pc|2500", "Local|Decorative Mirror Round|1 pc|1900", "Ajanta|Wall Clock|1 pc|650", "Local|Photo Frame 8x10|1 pc|250",
    "Local|Ceramic Vase|1 pc|750", "Local|Brass Nataraja Figurine|1 pc|2200", "Local|Decorative Bowl Wooden|1 pc|550", "Local|Showpiece Peacock|1 pc|900", "Local|Candle Holder Set|3 pcs|450",
    "Local|Artificial Flower Bunch|1 pc|250", "Local|Wall Hanging Macrame|1 pc|700", "Local|Table Lamp Ceramic|1 pc|1200", "Local|Bookends Metal|2 pcs|650",
],
("Home Decor and Lifestyle", "Lighting and Electrical Accessories"): [
    "Philips|LED Bulb 12W|1 pc|160", "Syska|LED Batten 20W|1 pc|350", "Wipro|Garnet LED 9W|2 pcs|250", "Local|Decorative Lamp Shade|1 pc|850", "Local|Floor Lamp|1 pc|2800",
    "Local|Night Light Plug-in|1 pc|180", "Eveready|Emergency Light|1 pc|950", "Local|Rechargeable Torch|1 pc|450", "Local|String Lights 10 m|1 pc|350", "Anchor|Extension Board 6 Socket|1 pc|650",
    "Local|Universal Plug Adapter|1 pc|250", "Anchor|Modular Switch|1 pc|60", "Havells|Ceiling Fan Regulator|1 pc|250", "Local|Doorbell Wireless|1 pc|550",
],
("Home Decor and Lifestyle", "Artificial and Natural Plants"): [
    "Local|Artificial Plant Pot|1 pc|450", "Local|Artificial Flowers Lily|1 pc|300", "Ugaoo|Money Plant with Pot|1 pc|350", "Ugaoo|Snake Plant|1 pc|450", "Local|Tulsi Plant with Pot|1 pc|120",
    "Local|Hibiscus Plant|1 pc|150", "Local|Areca Palm|1 pc|650", "Local|Succulent Set|3 pcs|450", "Local|Cactus Small|1 pc|180", "Local|Curry Leaf Plant|1 pc|120",
    "Local|Tomato Seedlings|6 pcs|80", "Local|Plant Pot Terracotta 10 inch|1 pc|150", "Local|Planter Self-watering|1 pc|450", "Local|Hanging Basket|1 pc|250", "Trustbasket|Potting Soil|5 kg|250",
    "Trustbasket|Vermicompost|5 kg|220", "Local|Organic Fertilizer|1 kg|150", "Local|Watering Can 5 L|1 pc|320", "Local|Pruning Shears|1 pc|350", "Local|Garden Gloves|1 pair|120",
],
("Home Decor and Lifestyle", "Fragrances and Ambience"): [
    "Local|Scented Candle Lavender|1 pc|350", "Local|Scented Candle Sandalwood|1 pc|380", "Cycle|Room Fragrance Incense|50 g|90", "Local|Reed Diffuser Jasmine|1 pc|650",
    "Local|Essential Oil Diffuser Electric|1 pc|1200", "Local|Potpourri Rose|1 pc|250", "Local|Aroma Oil Lemongrass|10 ml|150", "Local|Tealight Candles|50 pcs|250", "Local|Candle Gift Set|3 pcs|650",
],
("Pooja and Religious Products", "Daily Pooja Essentials"): [
    "Cycle|Three in One Agarbatti|150 g|85", "Mangaldeep|Sandal Agarbatti|100 g|70", "Cycle|Lia Jasmine Agarbatti|50 g|40", "Cycle|Dhoop Sticks|20 pcs|60", "Local|Sambrani Cups|12 pcs|90",
    "Mangalam|Camphor Tablets|50 g|60", "Local|Cotton Wicks (Thiri)|100 pcs|30", "Local|Brass Oil Lamp (Kuthu Vilakku) 12 inch|1 pc|1800", "Local|Clay Diya|12 pcs|60",
    "Local|Deepam Oil (Lamp Oil)|1 L|120", "GRB|Ghee for Lamps|500 ml|300", "Ship|Matchbox|10 pcs|25", "Local|Pooja Plate Brass|1 pc|450", "Local|Lighter Long|1 pc|90", "Local|Agarbatti Stand|1 pc|40",
],
("Pooja and Religious Products", "Pooja Accessories"): [
    "Local|Brass Bell|1 pc|350", "Local|Brass Kalash|1 pc|650", "Local|Kumkum Box Silver Plated|1 pc|250", "Local|Turmeric Box|1 pc|120", "Local|Panchapatra and Uddharani|1 pc|400",
    "Local|Copper Pooja Vessel Set|1 pc|1500", "Local|Incense Holder|1 pc|120", "Local|Aarti Plate with Camphor Holder|1 pc|550", "Local|Pooja Storage Box|1 pc|350", "Local|Conch Shell (Sangu)|1 pc|450",
    "Local|Brass Deepam Pair|2 pcs|900", "Local|Wooden Pooja Mandir Small|1 pc|3500",
],
("Pooja and Religious Products", "Flowers and Offerings"): [
    "Local|Jasmine (Malli) String|1 mozham|30", "Local|Marigold Garland|1 pc|60", "Local|Rose Garland|1 pc|80", "Local|Artificial Garland Door|1 pc|250", "Local|Flower Basket Mixed|1 pc|120",
    "Local|Lotus Flowers|2 pcs|40", "Local|Vibhuti (Sacred Ash)|100 g|30", "Local|Kumkum Powder|50 g|25", "Local|Turmeric Powder (Pooja)|50 g|20", "Local|Sandalwood Powder|50 g|150",
    "Local|Sacred Thread (Kaapu)|1 pc|20", "Local|Betel Leaves and Areca Nut|1 set|30", "Local|Banana Leaf|4 pcs|20", "Local|Offering Plate Leaf (Donnai)|20 pcs|30",
],
("Pooja and Religious Products", "Festive and Religious Products"): [
    "Local|Kolam Powder White|1 kg|40", "Local|Rangoli Colours Set|6 pcs|90", "Local|Mango Leaf Toran Artificial|1 pc|150", "Local|Decorative Door Toran|1 pc|350", "Local|Traditional Lamp Set Pongal|1 pc|650",
    "Local|Pongal Pot Clay|1 pc|120", "Local|Golu Dolls Set (Navaratri)|5 pcs|1200", "Local|Deepavali Diya Set Painted|12 pcs|150", "Local|Pooja Gift Set|1 pc|850", "Local|Vinayagar Clay Idol|1 pc|250",
    "Local|Sparklers Pack|10 pcs|120", "Local|Festival Decoration Lights|1 pc|450",
],
("Pooja and Religious Products", "Religious Books and Accessories"): [
    "Giri|Thiruppavai Book Tamil|1 pc|60", "Giri|Kanda Sashti Kavasam|1 pc|40", "Giri|Hanuman Chalisa|1 pc|30", "Local|Devotional Calendar Tamil|1 pc|60", "Local|Spiritual Poster Murugan|1 pc|80",
    "Local|Religious Picture Frame Lakshmi|1 pc|350", "Local|Bhagavad Gita|1 pc|150", "Local|Quran Stand|1 pc|450", "Local|Holy Bible Tamil|1 pc|250", "Local|Rudraksha Mala|1 pc|250",
],
("Electronics and Technology", "Consumer Electronics"): [
    "Samsung|LED TV 32 inch|1 pc|15500", "Mi|Smart TV 43 inch|1 pc|26000", "boAt|Stone 350 Bluetooth Speaker|1 pc|1799", "JBL|Flip 6|1 pc|9999", "Zebronics|Soundbar 2.1|1 pc|4500",
    "Saregama|Carvaan Radio|1 pc|6990", "boAt|Rockerz 450 Headphones|1 pc|1499", "boAt|Bassheads 100 Earphones|1 pc|399", "Sony|WH-CH520 Headphones|1 pc|4490", "Realme|Buds T110|1 pc|1299",
    "Philips|Portable Radio|1 pc|1800", "Local|TV Wall Mount|1 pc|650",
],
("Electronics and Technology", "Mobile Accessories"): [
    "boAt|Type-C Cable 1.5 m|1 pc|299", "Ambrane|USB-C Charger 20W|1 pc|599", "Mi|Power Bank 10000 mAh|1 pc|1199", "Ambrane|Power Bank 20000 mAh|1 pc|1699", "Local|Phone Case Transparent|1 pc|199",
    "Local|Tempered Glass Screen Protector|1 pc|199", "Portronics|Car Charger Dual|1 pc|499", "Local|Mobile Stand Desk|1 pc|249", "Portronics|Wireless Charger|1 pc|999", "Local|Lightning Cable|1 pc|349",
    "Local|Car Phone Holder|1 pc|399", "Local|Selfie Stick Tripod|1 pc|599",
],
("Electronics and Technology", "Computer and Office Electronics"): [
    "Logitech|K120 Keyboard|1 pc|699", "Logitech|M171 Wireless Mouse|1 pc|999", "Zebronics|Webcam HD|1 pc|1299", "Portronics|USB Hub 4 Port|1 pc|499", "SanDisk|USB Drive 64 GB|1 pc|549",
    "SanDisk|MicroSD 128 GB|1 pc|999", "Seagate|External HDD 1 TB|1 pc|4299", "Local|Laptop Stand Aluminium|1 pc|999", "TP-Link|WiFi Router AC1200|1 pc|2299", "D-Link|LAN Cable 5 m|1 pc|249",
    "Zebronics|Wired Headset with Mic|1 pc|699", "Local|Mouse Pad|1 pc|149",
],
("Electronics and Technology", "Small Home Appliances"): [
    "Prestige|Electric Kettle 1.5 L|1 pc|1299", "Butterfly|Mixer Grinder 750W|1 pc|4200", "Preethi|Zodiac Mixer Grinder|1 pc|7500", "Elgi Ultra|Wet Grinder 2 L|1 pc|8500", "Philips|Hand Blender|1 pc|2300",
    "Prestige|Pop-up Toaster|1 pc|1500", "Prestige|Sandwich Maker|1 pc|1600", "Panasonic|Rice Cooker 1.8 L|1 pc|3200", "Prestige|Induction Cooktop 1900W|1 pc|2800", "Philips|Steam Iron|1 pc|1800",
    "Crompton|Table Fan 400 mm|1 pc|2200", "Havells|Ceiling Fan 1200 mm|1 pc|2600", "Eureka Forbes|Vacuum Cleaner|1 pc|6500", "Philips|Air Purifier AC1215|1 pc|9500", "Philips|Garment Steamer|1 pc|3500",
    "Bajaj|Immersion Water Heater 1500W|1 pc|650", "Pigeon|Egg Boiler|1 pc|799", "Kent|Water Purifier Gravity 20 L|1 pc|2500",
],
("Electronics and Technology", "Batteries and Power"): [
    "Duracell|AA Alkaline|8 pcs|280", "Duracell|AAA Alkaline|8 pcs|280", "Eveready|AA Carbon Zinc|10 pcs|120", "Panasonic|Rechargeable AA 2000 mAh|4 pcs|750", "Panasonic|Battery Charger|1 pc|899",
    "Luminous|Inverter 900 VA|1 pc|6500", "Exide|Inverter Battery 150 Ah|1 pc|14500", "Belkin|Surge Protector 6 Socket|1 pc|1800", "APC|UPS 600 VA|1 pc|3200", "Local|9V Battery|1 pc|60", "Local|Button Cell CR2032|2 pcs|60",
],
("Electronics and Technology", "Smart Home Products"): [
    "Wipro|Smart Bulb 9W|1 pc|699", "Philips|Hue White Smart Bulb|1 pc|1499", "Wipro|Smart Plug 16A|1 pc|999", "Qubo|Motion Sensor|1 pc|1299", "Qubo|Video Doorbell|1 pc|4990",
    "Wipro|Smart Switch 4 Gang|1 pc|2499", "Amazon|Echo Dot|1 pc|4499", "Google|Nest Mini|1 pc|3999", "Qubo|Smart Camera Indoor|1 pc|2990",
],
("Stationery, Books and Office Supplies", "Writing Instruments"): [
    "Cello|Butterflow Ball Pen Blue|5 pcs|50", "Reynolds|045 Ball Pen|10 pcs|70", "Pilot|V5 Gel Pen|1 pc|60", "Parker|Vector Fountain Pen|1 pc|350", "Natraj|621 Pencils|10 pcs|40",
    "Apsara|Platinum Pencils|10 pcs|50", "Camlin|Mechanical Pencil 0.5|1 pc|40", "Luxor|Sketch Pens|12 pcs|60", "Faber-Castell|Highlighters|5 pcs|120", "Camlin|Permanent Marker Black|1 pc|30",
    "Faber-Castell|Wax Crayons|24 pcs|75", "Doms|Colour Pencils|24 pcs|140", "Camlin|Whiteboard Marker|4 pcs|120",
],
("Stationery, Books and Office Supplies", "Paper Products"): [
    "Classmate|Notebook Single Line 172 pages|1 pc|60", "Classmate|Long Notebook 200 pages|1 pc|80", "Local|Diary 2026|1 pc|180", "Local|Journal Hardbound|1 pc|250", "Local|Register 300 pages|1 pc|150",
    "Camlin|Drawing Book A4|1 pc|60", "Classmate|Graph Book|1 pc|50", "JK|Copier Paper A4 500 sheets|1 pc|320", "Local|Colour Paper A4|100 sheets|120", "3M|Post-it Notes|1 pc|90",
    "Local|Envelopes White|25 pcs|50", "Local|Index Cards|100 pcs|80", "Local|Chart Paper|5 pcs|50",
],
("Stationery, Books and Office Supplies", "School Supplies"): [
    "Skybags|School Bag 32 L|1 pc|1299", "Wildcraft|School Backpack|1 pc|1499", "Local|Pencil Box Magnetic|1 pc|150", "Camlin|Geometry Box|1 pc|120", "Natraj|Sharpener|5 pcs|25",
    "Apsara|Non-dust Eraser|5 pcs|25", "Camlin|Scale 30 cm|1 pc|20", "Fevistik|Glue Stick 15 g|1 pc|35", "Local|Craft Paper Pack|1 pc|80", "Local|Scissors Kids|1 pc|50",
    "Camlin|Water Colours Set|1 pc|120", "Camlin|Poster Colours 12 Shades|1 pc|180", "Local|Project Files|5 pcs|90", "Local|Lunch Bag Insulated|1 pc|350", "Local|Name Labels Sheet|1 pc|30",
],
("Stationery, Books and Office Supplies", "Office Supplies"): [
    "Local|Box File|1 pc|120", "Local|Folder Plastic L-Shape|10 pcs|90", "Local|Ring Binder A4|1 pc|180", "Kangaro|Stapler HD-10|1 pc|120", "Kangaro|Staples No. 10|1 pc|20",
    "Local|Paper Clips|100 pcs|40", "Local|Binder Clips Assorted|24 pcs|90", "Kangaro|Punch 2 Hole|1 pc|250", "Casio|Calculator MJ-120|1 pc|550", "Local|Labels Self-adhesive|1 pc|60",
    "Local|Rubber Stamp Date|1 pc|150", "Local|Desk Organizer|1 pc|350", "Local|Whiteboard 2x3 ft|1 pc|750", "Local|Whiteboard Duster|1 pc|60",
],
("Stationery, Books and Office Supplies", "Books and Learning Materials"): [
    "Local|Children's Story Book Tamil|1 pc|120", "Local|Panchatantra Stories|1 pc|150", "Local|Nursery Rhymes Book|1 pc|120", "Local|ABC Workbook|1 pc|90", "Local|Colouring Book Animals|1 pc|60",
    "Local|Activity Book Puzzles|1 pc|120", "Oxford|English Mini Dictionary|1 pc|250", "Local|Tamil-English Dictionary|1 pc|220", "Local|General Knowledge 2026|1 pc|180", "Local|TNPSC Guide|1 pc|450",
    "Local|Spoken English Course Book|1 pc|200", "Local|Hindi Learning Book for Beginners|1 pc|150", "Local|Atlas Student|1 pc|250",
],
("Stationery, Books and Office Supplies", "Diaries and Planners"): [
    "Local|Daily Diary 2026|1 pc|200", "Local|Executive Diary Leather|1 pc|450", "Local|Pocket Diary|1 pc|80", "Local|Appointment Book|1 pc|250", "Local|Academic Planner|1 pc|300",
    "Local|Yearly Planner Wall|1 pc|150", "Local|Desk Calendar 2026|1 pc|120", "Local|Wall Calendar Tamil Daily|1 pc|60", "Local|Habit Tracker Journal|1 pc|280", "Local|Budget Journal|1 pc|250",
],
("Pet Products", "Pet Food"): [
    "Pedigree|Adult Dog Food Chicken|3 kg/10 kg|750/2300", "Pedigree|Puppy Food|1.2 kg|420", "Drools|Adult Dog Food|3 kg|720", "Royal Canin|Maxi Adult|4 kg|2600", "Pedigree|Gravy Wet Dog Food|70 g|40",
    "Whiskas|Adult Cat Food Ocean Fish|1.2 kg|450", "Whiskas|Kitten Food|450 g|200", "Me-O|Cat Food Tuna|1.2 kg|480", "Sheba|Wet Cat Food|70 g|60", "Pedigree|Dentastix Treats|110 g|160",
    "Drools|Dog Biscuits|1 kg|250", "Gnawlers|Chew Sticks|6 pcs|250", "Royal Canin|Renal Dog Diet|2 kg|2200", "Farmina|N&D Kitten|1.5 kg|1500",
],
("Pet Products", "Pet Accessories"): [
    "Local|Dog Collar Nylon Medium|1 pc|250", "Local|Dog Leash 5 ft|1 pc|350", "Local|Dog Harness|1 pc|550", "Local|Feeding Bowl Steel|1 pc|200", "Local|Pet Water Dispenser|1 pc|650",
    "Local|Pet Carrier Small|1 pc|1500", "Local|Cat Cage|1 pc|2500", "Local|Dog Bed Medium|1 pc|1200", "Local|Pet Blanket|1 pc|400", "Local|Dog Chew Toy Rubber|1 pc|250",
    "Local|Cat Scratching Post|1 pc|900", "Local|Litter Tray|1 pc|450", "Local|Cat Toy Feather Wand|1 pc|150",
],
("Pet Products", "Pet Grooming and Hygiene"): [
    "Himalaya|Erina EP Pet Shampoo|200 ml|180", "Local|Pet Grooming Brush|1 pc|250", "Local|Pet Nail Clipper|1 pc|200", "Local|Pet Wipes|50 pcs|250", "Local|Pet Odour Remover Spray|500 ml|350",
    "Local|Cat Litter Bentonite|5 kg|550", "Local|Dog Waste Bags|60 pcs|200", "Local|Tick and Flea Powder|100 g|150", "Local|Pet Towel|1 pc|300",
],
("Pet Products", "Products for Other Pets"): [
    "Local|Bird Seed Mix|1 kg|150", "Local|Bird Cage Medium|1 pc|1500", "Taiyo|Fish Food Flakes|100 g|120", "Local|Aquarium 2 ft|1 pc|2500", "Sobo|Aquarium Filter|1 pc|650",
    "Local|Aquarium Gravel|2 kg|150", "Local|Rabbit Food Pellets|1 kg|250", "Local|Small Animal Bedding|1 kg|300", "Local|Bird Feeder Bowl|1 pc|120",
],
("Automobile Care and Accessories", "Vehicle Cleaning"): [
    "3M|Car Shampoo|500 ml|350", "Formula 1|Waterless Wash|500 ml|550", "3M|Dashboard Dresser|250 ml|320", "Local|Glass Cleaner Auto|500 ml|250", "3M|Upholstery Cleaner|250 ml|400",
    "Local|Tyre Shine|500 ml|300", "Local|Wheel Cleaner|500 ml|350", "Local|Degreaser|500 ml|300", "Local|Car Wash Bucket Kit|1 pc|800",
],
("Automobile Care and Accessories", "Car Detailing"): [
    "Turtle Wax|Car Wax|300 ml|550", "3M|Car Polish|200 ml|450", "Local|Ceramic Spray Coating|250 ml|900", "Local|Microfibre Towel Large|2 pcs|350", "Local|Detailing Brush Set|5 pcs|400",
    "Local|Car Sponge|1 pc|90", "Local|Applicator Pads|4 pcs|200", "Local|Clay Bar Kit|1 pc|650",
],
("Automobile Care and Accessories", "Automobile Accessories"): [
    "Ambi Pur|Car Freshener Vent Clip|7.5 ml|250", "Godrej|Aer Car Gel|45 g|199", "Local|Seat Covers Universal|1 set|2500", "Local|Floor Mats 5 pcs|1 set|900", "Local|Sunshade Windshield|1 pc|350",
    "Local|Car Phone Holder Dashboard|1 pc|450", "Local|Car Organizer Back Seat|1 pc|550", "Local|Car Duster|1 pc|250", "Local|Steering Cover|1 pc|350", "Local|Car Tissue Box|1 pc|250",
],
("Automobile Care and Accessories", "Automotive Maintenance Essentials"): [
    "Local|Windshield Washer Fluid|1 L|200", "Local|Wiper Blades 22 inch|1 pc|450", "Local|Tyre Pressure Gauge|1 pc|350", "Local|Car Emergency Kit|1 pc|1500", "Local|Jump Starter Cables|1 pc|650",
    "Local|Engine Coolant|1 L|350", "Local|Car Vacuum Cleaner 12V|1 pc|1500", "Local|Tyre Inflator 12V|1 pc|1800", "Local|Bike Chain Lube|150 ml|250",
],
("Baby and Infant Products", "Baby Care"): [
    "Pampers|Diaper Pants Medium|56 pcs|850", "Huggies|Wonder Pants Large|42 pcs|750", "MamyPoko|Pants Extra Absorb XL|40 pcs|720", "Himalaya|Baby Wipes|72 pcs|120", "Johnson's|Baby Soap|100 g|65",
    "Himalaya|Gentle Baby Shampoo|200 ml|160", "Johnson's|Baby Lotion|200 ml|190", "Himalaya|Baby Powder|200 g|140", "Sebamed|Baby Rash Cream|50 ml|250", "Mamaearth|Baby Massage Oil|200 ml|350",
    "Himalaya|Baby Cream|100 ml|120", "Local|Baby Nail Clipper|1 pc|120", "Dabur|Lal Tail Baby Oil|200 ml|150",
],
("Baby and Infant Products", "Baby Feeding and Clothing"): [
    "Philips Avent|Feeding Bottle 260 ml|1 pc|450", "Pigeon|Feeding Bottle 240 ml|1 pc|350", "Nestle|Cerelac Wheat|300 g|250", "Nestle|NAN Pro 1|400 g|750", "Local|Baby Bibs|3 pcs|250",
    "Local|Baby Rompers|3 pcs|600", "Local|Baby Blanket Soft|1 pc|450", "Local|Baby Sipper Cup|1 pc|250", "Local|Baby Spoon and Bowl Set|1 pc|200", "Local|Baby Mosquito Net Foldable|1 pc|550",
    "Local|Baby Carrier|1 pc|1500", "Local|Baby Towel Hooded|1 pc|350",
],
("Health and First Aid", "First Aid"): [
    "Band-Aid|Washproof Strips|20 pcs|60", "Local|Gauze Roll|1 pc|40", "Local|Adhesive Plaster Roll|1 pc|50", "Dettol|Antiseptic Liquid|500 ml|300", "Savlon|Antiseptic Liquid|500 ml|280",
    "Local|Digital Thermometer|1 pc|250", "Omron|Thermometer Infrared|1 pc|2200", "Local|Hot and Cold Gel Pack|1 pc|250", "Local|First Aid Kit Home|1 pc|750", "Local|Crepe Bandage|1 pc|90",
    "Volini|Pain Relief Spray|60 g|180", "Moov|Pain Relief Cream|50 g|160", "Local|Cotton Wool|100 g|60", "Local|Surgical Gloves|10 pairs|150",
],
("Health and First Aid", "Wellness and Protection"): [
    "Local|Face Masks 3-ply|50 pcs|200", "Local|N95 Mask|5 pcs|250", "Omron|Blood Pressure Monitor|1 pc|2500", "Accu-Chek|Glucometer Kit|1 pc|1200", "Local|Pulse Oximeter|1 pc|900",
    "Local|Knee Cap Support|1 pair|350", "Local|Lumbar Belt|1 pc|650", "Local|Weighing Scale Digital|1 pc|999", "Dabur|Honitus Lozenges|1 pc|60", "Vicks|VapoRub|50 ml|150",
    "Local|Electrolyte ORS Sachets|10 pcs|120", "Zandu|Balm|25 ml|80", "Local|Hot Water Bottle Electric|1 pc|550",
],
("Travel and Luggage", "Luggage and Bags"): [
    "American Tourister|Cabin Trolley 55 cm|1 pc|4500", "Safari|Check-in Trolley 65 cm|1 pc|5500", "Skybags|Backpack 30 L|1 pc|1600", "Wildcraft|Duffle Bag 60 L|1 pc|2500", "VIP|Luggage Set 2 pcs|1 pc|9000",
    "Local|Travel Organizer Packing Cubes|6 pcs|800", "Local|Toiletry Bag Hanging|1 pc|500", "Local|Laptop Bag|1 pc|1200", "Local|Sling Bag|1 pc|700", "Local|Gym Bag|1 pc|900",
],
("Travel and Luggage", "Travel Accessories"): [
    "Local|Luggage Lock TSA|1 pc|350", "Local|Travel Neck Pillow|1 pc|450", "Local|Umbrella 3-fold|1 pc|450", "Local|Raincoat|1 pc|650", "Local|Reusable Travel Bottle Set|4 pcs|250",
    "Local|Luggage Tag|2 pcs|150", "Local|Travel Adapter Universal|1 pc|650", "Local|Eye Mask and Ear Plugs|1 pc|200", "Local|Luggage Scale Digital|1 pc|450", "Local|Passport Holder|1 pc|300",
],
("Clothing and Accessories", "Basic Apparel and Innerwear"): [
    "Jockey|Men Vest|2 pcs|400", "Jockey|Men Briefs|3 pcs|540", "Jockey|Women Panties|3 pcs|480", "Lux|Cozi Vest|3 pcs|300", "Rupa|Frontline Briefs|3 pcs|350",
    "Local|Cotton T-shirt Round Neck|1 pc|350", "Local|Track Pants|1 pc|550", "Local|Nightwear Set Women|1 pc|650", "Local|Men Lungi Cotton|1 pc|300", "Local|Cotton Saree Daily Wear|1 pc|650",
    "Local|Veshti (Dhoti) Cotton|1 pc|450", "Local|Socks Ankle|3 pairs|200", "Local|Kids Shorts Set|2 pcs|400", "Local|Thermal Wear Set|1 pc|900",
],
("Clothing and Accessories", "Footwear and Accessories"): [
    "Paragon|Slippers Men|1 pair|250", "Bata|Sandals Women|1 pair|799", "Sparx|Sports Shoes Men|1 pair|1499", "Local|Flip Flops|1 pair|199", "Local|Belt Leather Men|1 pc|650",
    "Local|Cap Cotton|1 pc|250", "Local|Wallet Men|1 pc|550", "Local|Handbag Women|1 pc|1200", "Local|Sunglasses|1 pc|450", "Local|Monsoon Rain Shoes|1 pair|650", "Local|Winter Scarf|1 pc|350",
],
("Sports, Fitness and Outdoor", "Fitness"): [
    "Boldfit|Yoga Mat 6 mm|1 pc|799", "Strauss|Resistance Bands Set|5 pcs|499", "Local|Dumbbells 2 kg Pair|1 pair|650", "Local|Dumbbells 5 kg Pair|1 pair|1400", "Boldfit|Skipping Rope|1 pc|250",
    "Local|Gym Water Bottle 1 L|1 pc|350", "Local|Push-up Bars|1 pair|450", "Local|Kettlebell 8 kg|1 pc|1200", "Local|Fitness Gloves|1 pair|400", "Local|Ab Roller|1 pc|500",
],
("Sports, Fitness and Outdoor", "Sports and Outdoor"): [
    "Cosco|Cricket Tennis Ball|6 pcs|300", "SG|Cricket Bat Kashmir Willow|1 pc|1800", "Nivia|Football Size 5|1 pc|750", "Cosco|Volleyball|1 pc|650", "Yonex|Badminton Racket|1 pc|1200",
    "Yonex|Shuttlecock Nylon|6 pcs|450", "Local|Carrom Board|1 pc|1500", "Local|Cycling Helmet|1 pc|900", "Local|Camping Tent 2 Person|1 pc|2500", "Local|Sleeping Bag|1 pc|1500",
    "Local|Camping Lantern LED|1 pc|650", "Local|Picnic Mat Foldable|1 pc|500", "Local|Cooler Box 20 L|1 pc|1800", "Local|Swimming Goggles|1 pc|350",
],
("Toys, Games and Hobbies", "Toys"): [
    "Funskool|Giggles Stacking Rings|1 pc|250", "Lego|Classic Bricks 300|1 pc|1800", "Local|Building Blocks 100 pcs|1 pc|650", "Mattel|Barbie Doll|1 pc|999", "Hot Wheels|Car 5 Pack|1 pc|450",
    "Funskool|Marvel Action Figure|1 pc|699", "Local|Remote Control Car|1 pc|1200", "Local|Soft Toy Teddy 40 cm|1 pc|550", "Local|Kids Kitchen Set|1 pc|850", "Local|Wooden Alphabet Puzzle|1 pc|350",
    "Local|Pull-along Duck|1 pc|300", "Local|Kids Tricycle|1 pc|2500", "Local|Water Gun|1 pc|250", "Local|Kite with Thread|1 pc|60",
],
("Toys, Games and Hobbies", "Games and Hobbies"): [
    "Funskool|Monopoly|1 pc|1200", "Funskool|Scrabble|1 pc|999", "Local|Chess Board Wooden|1 pc|650", "Local|Ludo and Snakes & Ladders|1 pc|250", "Local|Jigsaw Puzzle 1000 pcs|1 pc|750",
    "Local|Playing Cards|1 pc|90", "Local|Uno Cards|1 pc|250", "Local|Rubik's Cube|1 pc|250", "Local|Craft Kit Beads|1 pc|450", "Camlin|Acrylic Paint Set|12 pcs|350",
    "Local|Canvas Board 12x16|1 pc|180", "Local|Embroidery Kit|1 pc|400", "Local|Origami Paper|100 sheets|150", "Local|Model Aircraft Kit|1 pc|900",
],
("Hardware and DIY", "Hand Tools"): [
    "Taparia|Screwdriver Set 6 pcs|1 pc|450", "Taparia|Combination Plier 8 inch|1 pc|350", "Stanley|Claw Hammer|1 pc|550", "Stanley|Measuring Tape 5 m|1 pc|250", "Taparia|Adjustable Wrench|1 pc|400",
    "Local|Hacksaw with Blade|1 pc|300", "Local|Spirit Level 12 inch|1 pc|250", "Bosch|Cordless Drill 12V|1 pc|4500", "Local|Allen Key Set|1 pc|150", "Local|Utility Knife|1 pc|120",
],
("Hardware and DIY", "Fasteners, Locks and Repair"): [
    "Godrej|Padlock 50 mm|1 pc|450", "Harrison|Door Lock Set|1 pc|1200", "Local|Door Hinges 4 inch|2 pcs|150", "Local|Tower Bolt 6 inch|1 pc|120", "Local|Wall Plugs and Screws|50 pcs|120",
    "Fevicol|SH Adhesive|500 g|180", "M-Seal|Epoxy Putty|100 g|90", "Local|Nylon Rope 10 m|1 pc|120", "Local|Cable Ties|100 pcs|90", "Local|Sandpaper Assorted|10 sheets|80",
    "Asian Paints|Wall Putty|1 kg|60", "Local|Paint Brush 2 inch|1 pc|60",
],
("Garden and Outdoor Living", "Gardening"): [
    "Local|Garden Tool Set 3 pcs|1 pc|450", "Local|Hand Trowel|1 pc|120", "Local|Garden Hose 15 m|1 pc|900", "Local|Spray Bottle 1 L|1 pc|150", "Trustbasket|Garden Soil|10 kg|400",
    "Local|Cocopeat Block|1 pc|120", "Local|Neem Cake Fertilizer|1 kg|120", "Local|Seeds Pack Vegetables|5 pcs|150", "Local|Grow Bags|5 pcs|250", "Local|Garden Netting|1 pc|350",
],
("Garden and Outdoor Living", "Outdoor Living"): [
    "Local|Balcony Chair Folding|1 pc|1500", "Local|Outdoor Table Plastic|1 pc|1200", "Local|Hammock|1 pc|1500", "Local|Bird Feeder Hanging|1 pc|350", "Local|Solar Garden Light|2 pcs|650",
    "Local|Outdoor Wall Light|1 pc|850", "Local|Garden Statue|1 pc|900", "Local|Wind Chime|1 pc|350", "Local|Balcony Rail Planter|1 pc|450", "Local|Outdoor Rug|1 pc|1200",
],
("Gift Items and Seasonal Products", "Gifting and Party Supplies"): [
    "Local|Gift Bag Medium|1 pc|50", "Local|Wrapping Paper Sheets|5 pcs|60", "Archies|Greeting Card Birthday|1 pc|60", "Local|Gift Box with Lid|1 pc|120", "Local|Birthday Balloons|50 pcs|150",
    "Local|Party Poppers|6 pcs|120", "Local|Birthday Banner|1 pc|150", "Local|Return Gift Pencil Set|10 pcs|300", "Local|Wedding Gift Silver Plated Bowl|1 pc|1200", "Local|Gift Set Dry Fruits Box|1 pc|850",
    "Local|Chocolate Gift Hamper|1 pc|650", "Local|Candles Birthday Number|1 pc|40", "Local|Ribbon Roll|1 pc|60",
],
("Gift Items and Seasonal Products", "Festive Decorations"): [
    "Local|Deepavali Lantern (Kandil)|1 pc|250", "Local|Fairy Lights 20 m|1 pc|450", "Local|Christmas Tree 4 ft|1 pc|1500", "Local|Christmas Star Lantern|1 pc|350", "Local|Pongal Sugarcane Decor Artificial|1 pc|250",
    "Local|Door Torans Beads|1 pc|300", "Local|Rangoli Stencil Set|1 pc|150", "Local|Diya Stand Decorative|1 pc|450", "Local|Marigold Garland Artificial 5 ft|1 pc|250", "Local|Festival Gift Wrap Set|1 pc|200",
],
("Disposable and Eco-Friendly Products", "Disposables"): [
    "Local|Paper Plates 10 inch|25 pcs|90", "Local|Paper Cups 150 ml|50 pcs|120", "Local|Disposable Spoons|50 pcs|60", "Local|Food Containers 500 ml|25 pcs|250", "Local|Aluminium Foil Trays|10 pcs|120",
    "Local|Garbage Bags Small|30 pcs|60", "Local|Disposable Gloves|100 pcs|250", "Local|Paper Napkins|100 pcs|80", "Local|Plastic Glasses|50 pcs|80",
],
("Disposable and Eco-Friendly Products", "Reusable and Eco-Friendly"): [
    "Local|Reusable Shopping Bag Jute|1 pc|120", "Local|Cloth Bag Cotton|3 pcs|150", "Local|Areca Leaf Plates|25 pcs|250", "Local|Bamboo Straws|6 pcs|150", "Local|Steel Straws with Brush|4 pcs|200",
    "Local|Bamboo Toothbrush|2 pcs|150", "Local|Coconut Shell Bowl|1 pc|200", "Local|Beeswax Food Wrap|3 pcs|450", "Local|Compostable Garbage Bags|30 pcs|180", "Local|Steel Lunch Box Eco|1 pc|450",
    "Local|Copper Bottle Hammered|1 pc|750", "Local|Cloth Produce Bags|5 pcs|250",
],
}
