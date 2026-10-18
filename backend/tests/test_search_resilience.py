"""Query side: embeddings are cached and fall back across endpoints; pet words in Tamil and Hindi; no duplicate names."""
from types import SimpleNamespace

from app.domain import classify
from app.domain.models import Inventory, Product, Store
from app.services import catalog, db, gemini


def _fake_client(calls, fail_at=()):
    def make(location):
        def embed_content(model, contents, config):
            calls.append(location)
            if location in fail_at:
                raise RuntimeError("429 RESOURCE_EXHAUSTED")
            return SimpleNamespace(embeddings=[SimpleNamespace(values=[0.1] * 768) for _ in contents])
        return SimpleNamespace(models=SimpleNamespace(embed_content=embed_content))
    return make


def test_embedding_endpoint_order(monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "google_genai_use_vertexai", True)
    monkeypatch.setattr(settings, "google_cloud_location", "asia-south1")
    monkeypatch.setattr(settings, "gemini_location", "global")
    monkeypatch.setattr(settings, "gemini_api_key", "")
    assert gemini.embed_endpoints() == ["asia-south1", "global"]
    monkeypatch.setattr(settings, "gemini_api_key", "key")
    assert gemini.embed_endpoints() == ["asia-south1", "global", gemini.AI_STUDIO]      # the Gemini API only as the last resort
    monkeypatch.setattr(settings, "google_genai_use_vertexai", False)
    assert gemini.embed_endpoints() == [gemini.AI_STUDIO]


def test_query_embeddings_are_cached_and_fall_back_across_endpoints(monkeypatch):
    calls = []
    monkeypatch.setattr(gemini, "configured", lambda: True)
    monkeypatch.setattr(gemini, "embed_endpoints", lambda: ["asia-south1", "global", gemini.AI_STUDIO])
    monkeypatch.setattr(gemini, "_embed_client", _fake_client(calls, fail_at=("asia-south1",)))
    gemini._query_vectors.clear()
    assert len(gemini.embed_texts(["Dog Food"], for_query=True)[0]) == 768
    assert calls == ["asia-south1", "global"]                    # regional quota gone: the global endpoint answered
    assert gemini.embed_texts(["dog  food"], for_query=True)      # same question, normalised: no call at all
    assert calls == ["asia-south1", "global"]
    monkeypatch.setattr(gemini, "_embed_client", _fake_client(calls, fail_at=("asia-south1", "global")))
    assert gemini.embed_texts(["something new"], for_query=True)  # both Vertex endpoints down: the Gemini API answers
    assert calls[-3:] == ["asia-south1", "global", gemini.AI_STUDIO]
    monkeypatch.setattr(gemini, "_embed_client", _fake_client(calls, fail_at=("asia-south1", "global", gemini.AI_STUDIO)))
    assert gemini.embed_texts(["nothing works"], for_query=True) == []      # every endpoint down: keyword search takes over
    monkeypatch.setattr(gemini, "_embed_client", _fake_client(calls))
    assert len(gemini.embed_texts(["a", "b"])) == 2                          # documents embed without the cache


def test_pet_queries_in_tamil_and_hindi_are_pet_queries():
    assert classify.query_use("நாய் உணவு இருக்கா") == "pet"
    assert classify.query_use("कुत्ते का खाना") == "pet"
    assert classify.query_use("அரிசி") is None


def test_search_shows_one_listing_per_name(store_id, monkeypatch):
    db.store_ref(store_id).set(Store(store_id=store_id, name="S").model_dump())
    for sku, sub in (("bulb-a", "Home Maintenance"), ("bulb-b", "Lighting")):
        p = Product.from_row(store_id=store_id, sku=sku, name="Philips LED Bulb 9W", price=99, mrp=99, threshold=500, subcategory=sub, tags=["bulb"])
        db.products(store_id).document(p.product_id).set(p.model_dump())
        db.inventory(store_id).document(p.product_id).set(Inventory(product_id=p.product_id, store_id=store_id, on_hand=3).model_dump())
    catalog.invalidate(store_id)
    monkeypatch.setattr(gemini, "embed_texts", lambda texts, for_query=False: [])
    assert [h.name for h in catalog.search(store_id, "led bulb", k=5)] == ["Philips LED Bulb 9W"]
