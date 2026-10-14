"""Test setup: point Firestore at the emulator and give each test a fresh store id."""

import os
import uuid

import pytest

os.environ.setdefault("FIRESTORE_EMULATOR_HOST", "127.0.0.1:8089")
os.environ["ENV"] = "test"
os.environ["GOOGLE_CLOUD_PROJECT"] = "demo-test"
os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "false"   # no Gemini calls in unit tests
os.environ["GEMINI_API_KEY"] = ""


@pytest.fixture
def store_id() -> str:
    return "t-" + uuid.uuid4().hex[:10]
