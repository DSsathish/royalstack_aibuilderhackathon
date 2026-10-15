"""Thin wrapper over the google-genai client. All Gemini calls go through here."""

import logging
from functools import lru_cache

from google import genai
from google.genai import types

from app.config import settings

log = logging.getLogger(__name__)
EMBEDDING_MODEL = "gemini-embedding-001"


def configured() -> bool:
    return settings.google_genai_use_vertexai or bool(settings.gemini_api_key)


# Free-tier capacity is bursty: retry 429/503 with backoff before giving up.
RETRY = types.HttpRetryOptions(attempts=4, initial_delay=2, max_delay=12, http_status_codes=[429, 503])
FAST = types.GenerateContentConfig(thinking_config=types.ThinkingConfig(thinking_level="low"))


def client_kwargs() -> dict:
    """How to build a genai.Client from settings. Shared with the ADK agent so both use the same endpoint."""
    if settings.google_genai_use_vertexai:
        return {"vertexai": True, "project": settings.google_cloud_project, "location": settings.gemini_location}
    return {"api_key": settings.gemini_api_key}


@lru_cache(maxsize=1)
def client() -> genai.Client:
    return genai.Client(**client_kwargs(), http_options=types.HttpOptions(retry_options=RETRY))


def embed_texts(texts: list[str], *, for_query: bool = False) -> list[list[float]]:
    """Returns one vector per text, or [] when Gemini is not configured or fails."""
    if not texts or not configured():
        return []
    try:
        res = client().models.embed_content(
            model=EMBEDDING_MODEL,
            contents=texts,
            config=types.EmbedContentConfig(
                task_type="RETRIEVAL_QUERY" if for_query else "RETRIEVAL_DOCUMENT",
                output_dimensionality=768,
            ),
        )
        return [e.values for e in res.embeddings]
    except Exception as exc:  # network, quota, bad key: degrade to keyword search
        log.warning("embed_texts failed: %s", exc)
        return []


def transcribe(audio: bytes, mime_type: str) -> str:
    """Speech to text with Gemini Flash. Keeps the spoken language. Returns "" on failure."""
    if not configured():
        return ""
    try:
        res = client().models.generate_content(
            model=settings.gemini_flash_model,
            contents=[types.Part.from_bytes(data=audio, mime_type=mime_type),
                      "Transcribe this audio exactly, in the language spoken. Output only the transcript."],
            config=FAST,
        )
        return (res.text or "").strip()
    except Exception as exc:
        log.warning("transcribe failed: %s", exc)
        return ""
