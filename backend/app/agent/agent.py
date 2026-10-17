"""Build the per-mode agents, run a turn, translate ADK events into UI messages."""

import uuid
from functools import lru_cache
from typing import AsyncIterator, Iterator

from google.adk.agents import LlmAgent
from google.adk.agents.run_config import RunConfig, StreamingMode
from google.adk.events import Event
from google.adk.models.google_llm import Gemini
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from app.agent import prompts
from app.agent.tools import TOOLS_BY_MODE
from app.services import conversation, gemini
from app.config import settings
from app.domain.models import Mode, Session

APP_NAME = "retail-agent"
MAX_LLM_CALLS = 8

ACTION_FOR_TOOL = {
    "search_products": "show_products",
    "suggest_substitutes": "show_products",
    "get_product": "show_product",
    "navigate_to": "highlight_map",
    "add_to_cart": "cart_updated",
    "remove_from_cart": "cart_updated",
    "view_cart": "cart_updated",
    "start_checkout": "checkout_ready",
    "get_low_stock": "show_low_stock",
    "record_demand_signal": "signal_recorded",
    "forecast_demand": "show_forecast",
    "draft_purchase_order": "drafts_created",
    "get_anomalies": "show_anomalies",
}

_sessions = InMemorySessionService()


def instruction_for(mode: Mode, state: dict) -> str:
    """Mode prompt, the store's identity, and the conversation so far, read from the session state each turn."""
    history = state.get("history") or ""
    return prompts.for_mode(mode) + prompts.store_block(state) + prompts.customer_block(state) + (f"\n\n{history}\n" if history else "")


def build(mode: Mode) -> LlmAgent:
    return LlmAgent(
        name=f"retail_{mode}",
        model=Gemini(model=settings.gemini_flash_model, retry_options=gemini.RETRY,
                     client_kwargs=gemini.client_kwargs()),
        generate_content_config=gemini.FAST,
        instruction=lambda ctx: instruction_for(mode, dict(ctx.state)),
        tools=list(TOOLS_BY_MODE[mode]),
    )


@lru_cache(maxsize=3)
def runner(mode: Mode) -> Runner:
    return Runner(app_name=APP_NAME, agent=build(mode), session_service=_sessions)


def translate(event: Event) -> Iterator[dict]:
    """Map one ADK event to zero or more UI events. Only the agent's own events count."""
    if event.author == "user" or not event.content or not event.content.parts:
        return
    for part in event.content.parts:
        if part.function_call:
            if event.partial:
                continue  # streaming repeats the call in the final event; report it once
            yield {"type": "status", "tool": part.function_call.name}
        elif part.function_response:
            name = part.function_response.name
            yield {"type": "action", "name": ACTION_FOR_TOOL.get(name, name),
                   "data": dict(part.function_response.response or {})}
        elif part.text:
            yield {"type": "token" if event.partial else "done", "text": part.text}


async def _fresh_session(s: Session) -> str:
    """One ADK session per turn. Memory of record is the Firestore conversation, injected as state."""
    sid = uuid.uuid4().hex
    await _sessions.create_session(
        app_name=APP_NAME, user_id=s.session_id, session_id=sid,
        state={"store_id": s.store_id, "mode": s.mode, "cart_id": s.cart_id, "session_id": s.session_id,
               "language": s.language, "history": conversation.history_text(s), **prompts.store_state(s.store_id), **prompts.customer_state(s)})
    return sid


async def chat(s: Session, text: str, image: tuple[bytes, str] | None = None) -> AsyncIterator[dict]:
    sid = await _fresh_session(s)
    reply = ""
    parts = [types.Part(text=text)]
    if image:
        parts.append(types.Part.from_bytes(data=image[0], mime_type=image[1]))
    msg = types.Content(role="user", parts=parts)
    cfg = RunConfig(streaming_mode=StreamingMode.SSE, max_llm_calls=MAX_LLM_CALLS)
    try:
        async for event in runner(s.mode).run_async(user_id=s.session_id, session_id=sid,
                                                     new_message=msg, run_config=cfg):
            for ui in translate(event):
                if ui["type"] == "done":
                    reply = ui["text"]
                yield ui
    finally:
        conversation.add_turn(s, "user", text if not image else f"{text} (with a photo)")
        conversation.add_turn(s, "assistant", reply)
        try:
            await _sessions.delete_session(app_name=APP_NAME, user_id=s.session_id, session_id=sid)
        except Exception:
            pass
