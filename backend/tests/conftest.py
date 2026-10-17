"""Test setup: point Firestore at the emulator and give each test a fresh store id."""

import os
import uuid

import pytest

os.environ.setdefault("FIRESTORE_EMULATOR_HOST", "127.0.0.1:8089")
os.environ["ENV"] = "test"
os.environ["GOOGLE_CLOUD_PROJECT"] = "demo-test"
os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "false"   # no Gemini calls in unit tests
os.environ["GEMINI_API_KEY"] = ""
os.environ["JOB_KEY"] = "test-job-key"
os.environ["GEMINI_LIVE_API_KEY"] = ""          # unit tests never touch AI Studio; local .env values must not leak in
os.environ["GEMINI_LIVE_MODEL"] = "gemini-live-2.5-flash"
os.environ["GEMINI_LIVE_AFFECTIVE"] = "true"


@pytest.fixture
def store_id() -> str:
    return "t-" + uuid.uuid4().hex[:10]


@pytest.fixture(autouse=True)
def _reset_rate_limits():
    """Every test starts with empty limiter windows; the suite shares one client address."""
    from app.api import agent, exit as exit_api
    agent.limiter.clear()
    getattr(exit_api, "limiter", agent.limiter).clear()
