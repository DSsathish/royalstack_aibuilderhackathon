"""Grounded product facts against the real model. LIVE_GEMINI=1 only."""
import os

import pytest

from app.services import facts

pytestmark = pytest.mark.skipif(os.environ.get("LIVE_GEMINI") != "1", reason="set LIVE_GEMINI=1 to run")


@pytest.fixture(autouse=True)
def real_gemini(monkeypatch):
    from dotenv import dotenv_values
    env = dotenv_values(os.path.join(os.path.dirname(__file__), "..", ".env"))
    from app.config import settings
    from app.services import gemini as gemini_svc
    for key, attr in (("GOOGLE_CLOUD_PROJECT", "google_cloud_project"), ("GEMINI_LOCATION", "gemini_location")):
        monkeypatch.setattr(settings, attr, env.get(key, getattr(settings, attr)))
    monkeypatch.setattr(settings, "google_genai_use_vertexai", env.get("GOOGLE_GENAI_USE_VERTEXAI", "true") == "true")
    gemini_svc.client.cache_clear()
    facts._used.clear()


def test_grounded_answer_cites_sources(store_id):
    r = facts.lookup(store_id, "live", "What is A2 milk and how is it different from regular milk?", None)
    print("\n", r.get("summary"), r.get("sources"))
    assert r["ok"] and len(r["sources"]) >= 1 and "A2" in r["summary"]


def test_grounded_refuses_off_topic(store_id):
    r = facts.lookup(store_id, "live", "Who won the cricket match yesterday?", None)
    assert r == {"ok": False, "error": "out_of_scope", "note": facts.NOTE}
