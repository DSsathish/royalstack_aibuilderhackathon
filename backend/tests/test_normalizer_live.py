"""Real model mapping of a messy POS export header. LIVE_GEMINI=1 only."""

import os

import pytest

from app.connectors import normalizer

pytestmark = pytest.mark.skipif(os.environ.get("LIVE_GEMINI") != "1", reason="set LIVE_GEMINI=1 to run")


@pytest.fixture(autouse=True)
def real_gemini(monkeypatch):
    from dotenv import dotenv_values
    env = dotenv_values(os.path.join(os.path.dirname(__file__), "..", ".env"))
    from app.config import settings
    from app.services import gemini as gemini_svc
    monkeypatch.setattr(settings, "google_cloud_project", env.get("GOOGLE_CLOUD_PROJECT", settings.google_cloud_project))
    monkeypatch.setattr(settings, "gemini_location", env.get("GEMINI_LOCATION", settings.gemini_location))
    monkeypatch.setattr(settings, "google_genai_use_vertexai", env.get("GOOGLE_GENAI_USE_VERTEXAI", "true") == "true")
    gemini_svc.client.cache_clear()


def test_messy_pos_export_is_mapped():
    header = ["Art. No.", "Description", "Mfr", "Dept Name", "Sell Rate", "M.R.P.", "Closing Qty", "EAN Code", "Rack", "Vendor Code"]
    samples = [{"Art. No.": "10023", "Description": "AASHIRVAAD ATTA 5KG", "Mfr": "ITC", "Dept Name": "STAPLES", "Sell Rate": "Rs 265.00",
                "M.R.P.": "280", "Closing Qty": "40 PCS", "EAN Code": "8901725012345", "Rack": "A1", "Vendor Code": "V07"}]
    p = normalizer.propose(header, samples)
    print(f"\nsource={p.source} confidence={p.confidence}\nmapping={p.mapping}\nnotes={p.notes}\nquestions={p.questions}")
    assert p.source == "model"
    assert p.mapping["sku"] == "Art. No." and p.mapping["name"] == "Description" and p.mapping["price"] == "Sell Rate"
    assert p.mapping["on_hand"] == "Closing Qty" and p.mapping["barcode"] == "EAN Code" and p.mapping.get("mrp") == "M.R.P."
    assert p.mapping.get("category") == "Dept Name" and p.mapping.get("brand") == "Mfr"
