from types import SimpleNamespace

import pytest

from app.services import db, facts

PRODUCT = SimpleNamespace(name="Aashirvaad Atta 5kg", brand="Aashirvaad", category="Staples", barcode="8901234567890")
INTERNAL = SimpleNamespace(name="Store Rice 5kg", brand="", category="Staples", barcode="2000000000017")
GOOD = {"summary": "Whole wheat flour, nothing else. Contains gluten.", "sources": [{"title": "example.com", "url": "https://example.com/atta"}]}


@pytest.fixture(autouse=True)
def _fresh(monkeypatch):
    facts._used.clear()
    monkeypatch.setattr(facts, "_label", lambda code: {"ingredients": "Whole wheat", "allergens": ["gluten"], "nutrition_per_100g": {"fat": 1.5}, "nutriscore": "A"})


def _audits(store_id):
    return [d.to_dict() for d in db.audit(store_id).stream() if d.to_dict().get("action") == "product_facts"]


def test_clean_question_caps_and_strips():
    assert facts.clean_question("  what is\x00 in this?\n ") == "what is in this?"
    assert len(facts.clean_question("x" * 500)) == facts.MAX_QUESTION
    assert facts.real_barcode("8901234567890") and not facts.real_barcode("2000000000017") and not facts.real_barcode("abc")


def test_cited_answer_is_returned_cached_and_audited(store_id, monkeypatch):
    calls = []
    monkeypatch.setattr(facts, "grounded", lambda q, p, label, lang: calls.append((q, label, lang)) or GOOD)
    r = facts.lookup(store_id, "s1", "What is in this atta?", PRODUCT, "ta")
    assert r["ok"] and r["summary"].startswith("Whole wheat") and r["sources"][0]["url"].startswith("https://")
    assert r["label"]["allergens"] == ["gluten"] and r["note"] and r["cached"] is False
    assert calls[0][1]["nutriscore"] == "A" and calls[0][2] == "ta"             # label data goes into the grounded prompt
    again = facts.lookup(store_id, "s2", "what is in this atta?", PRODUCT)
    assert again["cached"] is True and again["summary"] == r["summary"] and len(calls) == 1
    outcomes = [(a["payload"]["outcome"], a["payload"]["cached"]) for a in _audits(store_id)]
    assert sorted(outcomes) == [("ok", False), ("ok", True)]


def test_out_of_scope_and_uncited_answers_are_refused(store_id, monkeypatch):
    monkeypatch.setattr(facts, "grounded", lambda *a: {"error": "out_of_scope"})
    r = facts.lookup(store_id, "s1", "Who won the match?", None)
    assert r == {"ok": False, "error": "out_of_scope", "note": facts.NOTE}
    monkeypatch.setattr(facts, "grounded", lambda *a: {"error": "not_found"})
    assert facts.lookup(store_id, "s1", "Is this atta organic?", PRODUCT)["error"] == "not_found"
    assert [a["payload"]["outcome"] for a in _audits(store_id)] .count("out_of_scope") == 1


def test_budget_per_visit(store_id, monkeypatch):
    monkeypatch.setattr(facts, "BUDGET_PER_SESSION", 2)
    monkeypatch.setattr(facts, "grounded", lambda q, *a: {**GOOD, "summary": q})
    assert facts.lookup(store_id, "s1", "q one", None)["ok"]
    assert facts.lookup(store_id, "s1", "q two", None)["ok"]
    assert facts.lookup(store_id, "s1", "q three", None)["error"] == "budget_exhausted"
    assert facts.lookup(store_id, "s1", "q one", None)["cached"]                 # cached answers cost nothing
    assert facts.lookup(store_id, "other", "q three", None)["ok"]


def test_label_only_for_real_barcodes(store_id, monkeypatch):
    seen = []
    monkeypatch.setattr(facts, "_label", lambda code: seen.append(code) or None)
    monkeypatch.setattr(facts, "grounded", lambda q, p, label, lang: {**GOOD, "summary": f"label={label}"})
    assert facts.lookup(store_id, "s1", "ingredients?", INTERNAL)["label"] is None
    facts.lookup(store_id, "s1", "ingredients please", PRODUCT)
    assert seen == ["8901234567890"]


def test_sanitize_strips_markup_and_caps():
    assert facts.sanitize("**Ingredients:** wheat\n* gluten") == "Ingredients: wheat gluten"
    assert len(facts.sanitize("a " * 1000)) <= facts.MAX_SUMMARY


def test_grounded_requires_sources(monkeypatch):
    class R:
        text = "A2 milk has only A2 beta-casein."
        candidates = [SimpleNamespace(grounding_metadata=SimpleNamespace(grounding_chunks=[]))]
    monkeypatch.setattr(facts.gemini, "client", lambda: SimpleNamespace(models=SimpleNamespace(generate_content=lambda **kw: R())))
    assert facts.grounded("What is A2 milk?", None, None, "auto") == {"error": "not_found"}
    R.candidates = [SimpleNamespace(grounding_metadata=SimpleNamespace(grounding_chunks=[
        SimpleNamespace(web=SimpleNamespace(uri="https://vertexaisearch.cloud.google.com/grounding-api-redirect/A", title="example.org")),
        SimpleNamespace(web=SimpleNamespace(uri="https://vertexaisearch.cloud.google.com/grounding-api-redirect/B", title="example.org")),
        SimpleNamespace(web=SimpleNamespace(uri="https://vertexaisearch.cloud.google.com/grounding-api-redirect/C", title="other.com"))]))]
    out = facts.grounded("What is A2 milk?", None, None, "auto")
    assert [x["title"] for x in out["sources"]] == ["example.org", "other.com"]      # one entry per site, redirect links kept
    R.text = "OUT_OF_SCOPE"
    assert facts.grounded("cricket", None, None, "auto") == {"error": "out_of_scope"}
