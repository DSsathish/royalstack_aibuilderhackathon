"""Thin wrapper over the google-genai client. All Gemini calls go through here."""

import logging
from collections import OrderedDict
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



def live_client() -> genai.Client:
    """The client for speech-to-speech sessions: AI Studio when a live key is configured, else the same client as text."""
    if settings.gemini_live_api_key:
        return genai.Client(vertexai=False, api_key=settings.gemini_live_api_key)    # explicit: the Vertex env flag must not win
    return client()
QUERY_CACHE = 4096
_query_vectors: "OrderedDict[str, list[float]]" = OrderedDict()   # the same question embeds once per instance


AI_STUDIO = "ai-studio"


@lru_cache(maxsize=4)
def _embed_client(endpoint: str) -> genai.Client:
    if endpoint == AI_STUDIO:
        return genai.Client(vertexai=False, api_key=settings.gemini_api_key)
    kw = client_kwargs()
    if kw.get("vertexai"):
        kw["location"] = endpoint
    return genai.Client(**kw)


def embed_endpoints() -> list[str]:
    """Where a query embedding is tried, in order: the project's own Vertex region (its own quota, a second away), the
    global Vertex endpoint, and, when a Gemini API key is configured, the Gemini API as the last resort. All serve the
    same model, so the vectors match the ones stored with the products."""
    if not settings.google_genai_use_vertexai:
        return [AI_STUDIO]
    out = [settings.google_cloud_location, settings.gemini_location]
    out = [loc for i, loc in enumerate(out) if loc and loc not in out[:i]]
    if settings.gemini_api_key:
        out.append(AI_STUDIO)
    return out


def embed_texts(texts: list[str], *, for_query: bool = False) -> list[list[float]]:
    """Returns one vector per text, or [] when Gemini is not configured or every endpoint fails (keyword search then)."""
    if not texts or not configured():
        return []
    key = " ".join(texts[0].lower().split()) if for_query and len(texts) == 1 else None
    if key and key in _query_vectors:
        _query_vectors.move_to_end(key)
        return [_query_vectors[key]]
    cfg = types.EmbedContentConfig(
        task_type="RETRIEVAL_QUERY" if for_query else "RETRIEVAL_DOCUMENT", output_dimensionality=768,
        # a query embed sits on the shopper's critical path: answer fast or fall back to keywords
        http_options=types.HttpOptions(timeout=2500, retry_options=types.HttpRetryOptions(attempts=1)) if for_query else None)
    vectors: list[list[float]] = []
    for endpoint in embed_endpoints():
        try:
            res = _embed_client(endpoint).models.embed_content(model=EMBEDDING_MODEL, contents=texts, config=cfg)
            vectors = [e.values for e in res.embeddings]
            break
        except Exception as exc:  # quota, network, bad key: try the next endpoint, then degrade to keywords
            log.warning("embed_texts failed at %s: %s", endpoint, str(exc)[:160])
    if key and vectors:
        _query_vectors[key] = vectors[0]
        if len(_query_vectors) > QUERY_CACHE:
            _query_vectors.popitem(last=False)
    return vectors




def transcribe(audio: bytes, mime_type: str, language: str = "auto") -> str:
    """Speech to text with Gemini Flash. The transcript stays in the language and script that was spoken: Tamil in Tamil
    script, Hindi in Devanagari, English in Latin letters; never translated or transliterated. Returns "" on failure."""
    if not configured():
        return ""
    from app.domain import languages
    hint = f" The speaker is speaking {languages.name(language)}." if language in languages.LANGUAGES else ""
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
