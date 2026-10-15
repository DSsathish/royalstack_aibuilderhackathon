"""Bag check: one Gemini Flash call comparing a photo with the receipt. Never blocks an exit."""

import logging

from google.genai import types

from app.config import settings
from app.domain.models import VisionResult
from app.services import gemini

log = logging.getLogger(__name__)

PROMPT = """You are checking a grocery self-checkout at the store exit.
The shopper paid for these items: {lines}
Look at the photo of the shopper's bag or basket and compare.
Be conservative: items can hide under other items, so do not list hidden receipt items as missing.
Only list something as unexpected if you clearly see a product that is not on the receipt.
Confidence is how sure you are that the bag matches the receipt (1.0 = clearly matches)."""


def check_bag(image: bytes, mime: str, lines: list[str]) -> VisionResult:
    if not gemini.configured():
        return VisionResult(skipped=True)
    try:
        res = gemini.client().models.generate_content(
            model=settings.gemini_flash_model,
            contents=[types.Part.from_bytes(data=image, mime_type=mime), PROMPT.format(lines="; ".join(lines))],
            config=types.GenerateContentConfig(
                response_mime_type="application/json", response_schema=VisionResult,
                thinking_config=types.ThinkingConfig(thinking_level="low"),
                http_options=types.HttpOptions(timeout=8000),
            ),
        )
        out = VisionResult.model_validate_json(res.text)
        out.skipped = False
        return out
    except Exception as exc:
        log.warning("check_bag failed, skipping vision: %s", exc)
        return VisionResult(skipped=True)
