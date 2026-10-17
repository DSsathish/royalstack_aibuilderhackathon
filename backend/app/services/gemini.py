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
RETRY = types.HttpRetryOptions(attempts=4, initial_delay=2, max_delay=12, http_status_codes=[429, 503, 504])
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
                # a query embed sits on the shopper's critical path: answer fast or fall back to keywords
                http_options=types.HttpOptions(timeout=2500, retry_options=types.HttpRetryOptions(attempts=1)) if for_query else None,
            ),
        )
        return [e.values for e in res.embeddings]
    except Exception as exc:  # network, quota, bad key: degrade to keyword search
        log.warning("embed_texts failed: %s", exc)
        return []


LANG_NAMES = {"en": "English", "ta": "Tamil", "hi": "Hindi"}


def transcribe(audio: bytes, mime_type: str, language: str = "auto") -> str:
    """Speech to text with Gemini Flash. The transcript stays in the language and script that was spoken: Tamil in Tamil
    script, Hindi in Devanagari, English in Latin letters; never translated or transliterated. Returns "" on failure."""
    if not configured():
        return ""
    hint = f" The speaker is speaking {LANG_NAMES[language]}." if language in LANG_NAMES else ""
    try:
        res = client().models.generate_content(
            model=settings.gemini_flash_model,
            contents=[types.Part.from_bytes(data=audio, mime_type=mime_type),
                      "Transcribe this audio word for word in the language and script the speaker used (Tamil in Tamil script, "
                      "Hindi in Devanagari, English in Latin letters). Do not translate or transliterate; keep mixed-language "
                      "words as spoken. Output only the transcript." + hint],
            config=FAST,
        )
        return (res.text or "").strip()
    except Exception as exc:
        log.warning("transcribe failed: %s", exc)
        return ""
