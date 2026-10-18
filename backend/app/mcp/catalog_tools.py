"""Tool sets: a store's public catalog, and the Kirana Hub demo provider."""

from app.api.catalog import PUBLIC_EXCLUDE
from app.mcp import demo_catalog
from app.mcp.server import Tool, schema
from app.services import catalog, db

HIDDEN = PUBLIC_EXCLUDE | {"cost_price", "gst_rate", "is_high_value", "substitutes", "storage", "use"}


def _card(p) -> dict:
    d = p.model_dump(exclude=HIDDEN)
    loc = d.pop("location", None)
    d["aisle"] = loc["aisle"] if loc else ""
    return d


def store_tools(store_id: str) -> dict[str, Tool]:
    def store_info(_: dict) -> dict:
        doc = db.store_ref(store_id).get()
        if not doc.exists:
            raise ValueError("store not found")
        x = doc.to_dict()
        products, _ = catalog.product_map(store_id)
        return {"store_id": store_id, "name": x.get("name"), "city": x.get("city", ""), "currency": x.get("currency", "INR"),
                "languages": x.get("languages", []), "products": len(products), "categories": sorted({p.category for p in products.values() if p.category})}

    def search_products(a: dict) -> list[dict]:
        q = str(a.get("query", "")).strip()
        if not q:
            raise ValueError("query is required")
        return [_card(p) for p in catalog.search(store_id, q, k=max(1, min(25, int(a.get("limit", 8)))))]

    def get_product(a: dict) -> dict:
        pid, sku, barcode = str(a.get("product_id", "")), str(a.get("sku", "")), str(a.get("barcode", ""))
        p = (catalog.get_product(store_id, pid) if pid else None) or (catalog.get_by_sku(store_id, sku) if sku else None) or (catalog.get_by_barcode(store_id, barcode) if barcode else None)
        if not p:
            raise ValueError("product not found")
        return _card(p)

    def list_category(a: dict) -> dict:
        key = str(a.get("category", "")).strip().lower()
        limit, offset = max(1, min(100, int(a.get("limit", 40)))), max(0, int(a.get("offset", 0)))
        products, _ = catalog.product_map(store_id)
        pool = sorted((p for p in products.values() if p.status == "active" and (not key or key in (p.category.lower(), p.subcategory.lower()))), key=lambda p: p.name)
        return {"items": [_card(catalog.get_product(store_id, p.product_id) or p) for p in pool[offset:offset + limit]], "total": len(pool)}

    return {
        "store_info": Tool("store_info", "Name, city, languages, size and categories of this shop.", schema(), store_info),
        "search_products": Tool("search_products", "Find products by words in any language; returns price, MRP, stock and aisle.", schema(query="string!", limit="integer"), search_products),
        "get_product": Tool("get_product", "One product by product_id, sku or barcode.", schema(product_id="string", sku="string", barcode="string"), get_product),
        "list_category": Tool("list_category", "Products in a category or subcategory, paged.", schema(category="string", limit="integer", offset="integer"), list_category),
    }


def demo_tools() -> dict[str, Tool]:
    return {
        "search_products": Tool("search_products", "Search Kirana Hub's demo catalog. Sample prices, not live data.", schema(query="string!", limit="integer"),
                                lambda a: demo_catalog.search(str(a.get("query", "")), int(a.get("limit", 8)))),
        "list_products": Tool("list_products", "Page through Kirana Hub's demo catalog.", schema(limit="integer", offset="integer"),
                              lambda a: demo_catalog.list_items(int(a.get("limit", 50)), int(a.get("offset", 0)))),
        "get_product": Tool("get_product", "One demo item by sku.", schema(sku="string!"),
                            lambda a: demo_catalog.get(str(a.get("sku", ""))) or (_ for _ in ()).throw(ValueError("not found"))),
    }
