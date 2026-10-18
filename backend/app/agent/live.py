"""Bridge one browser websocket to one Gemini Live session: audio both ways, tools run locally."""

import asyncio
import difflib
import inspect
import json
import logging
import re
import time
from types import SimpleNamespace

from fastapi import WebSocket, WebSocketDisconnect
from google.genai import types

from app.agent import prompts
from app.agent.agent import ACTION_FOR_TOOL
from app.agent.tools import TOOLS_BY_MODE
from app.config import settings
from app.domain import languages
from app.domain.models import Mode, Session
from app.services import conversation, gemini

log = logging.getLogger(__name__)
_TYPES = {str: "STRING", int: "INTEGER", float: "NUMBER", bool: "BOOLEAN"}
MAX_SESSION_S = 1800         # with context compression a conversation can run long; the client reconnects after
MAX_AUDIO_FRAME = 32_000     # 1 s of PCM16 at 16 kHz; the worklet sends 3.2 KB chunks
_active: set[str] = set()    # session ids with an open live socket (one Vertex session each)
_resume_handles: dict[str, str] = {}   # session id -> latest Live resumption handle (reconnects continue the conversation)
VOICE_NAME = "Kore"
NOISE = re.compile(r"\s*[\[{<][^\]}>]{0,40}[\]}>]")   # transcriber markers such as {background} or <noise>: sounds, not words


class SessionBusy(Exception):
    pass

VOICE_BLOCK = """
You are speaking aloud. Keep each reply to one or two short sentences. Say prices and aisles
plainly. Say the key fact first (in stock or not, price, aisle), then one next step. When there are
several options, name at most three. After a tool call, tell the shopper what you did in a few words.
If they interrupt, stop and listen.
If you did not clearly hear or understand, say what you heard and ask the shopper to repeat.
Never guess a product name. Use the conversation so far: "that one", "the same", "add it" refer
to what was just discussed; call search_products to get its product_id before add_to_cart.
"""


def clean(text: str) -> str:
    """Transcript text without the transcriber's sound markers."""
    return NOISE.sub("", text)


def _norm(text: str) -> str:
    return " ".join(re.sub(r"[^\w\s]", "", text.lower()).split())


def _squash(text: str) -> str:
    return re.sub(r"[^\w]", "", text.lower())   # letters and digits only: "5 kg" and "5kg", "Rs 265" and "₹265" line up


def is_echo(heard: str, said: str) -> bool:
    """What the mic heard is the assistant's own words back through the loudspeaker: either the start of the reply
    (same first word, near-identical text) or a long stretch from anywhere in it (the browser guard holds the first
    part, so a leak starts later). Spacing and symbols are ignored; a shopper repeating a short product name or
    rephrasing a command ("Add" after "Added") does not match."""
    hw, sw = _norm(heard).split(), _norm(said).split()
    if len(hw) < 3 or not sw:
        return False
    h, s = _squash(heard), _squash(said)
    n = min(len(h), len(s)) + 2
    if hw[0] == sw[0] and difflib.SequenceMatcher(None, h[:n], s[:n], autojunk=False).ratio() >= 0.8:
        return True
    if len(h) >= 30:
        covered = sum(b.size for b in difflib.SequenceMatcher(None, h, s, autojunk=False).get_matching_blocks())
        return covered / len(h) >= 0.85
    return False


class CutCounter:
    """Echo without words: a reply that is interrupted within moments of starting, twice in a row, is the loudspeaker
    talking to the mic, whatever the transcriber made of it."""

    EARLY_S = 1.5
    STRIKES = 2

    def __init__(self, clock=time.monotonic) -> None:
        self._clock, self._started, self._early = clock, None, 0

    def reply_started(self) -> None:
        if self._started is None:
            self._started = self._clock()

    def completed(self) -> None:
        self._started, self._early = None, 0

    def interrupted(self) -> bool:
        """True when this interruption makes it echo."""
        early = self._started is not None and self._clock() - self._started < self.EARLY_S
        self._started = None
        self._early = self._early + 1 if early else 0
        if self._early >= self.STRIKES:
            self._early = 0
            return True
        return False


class TurnRecorder:
    """Accumulates live transcription chunks and saves whole turns through the callback. Turns that are the assistant's
    own voice echoed back are dropped, and a reply the shopper cut short is marked so memory does not claim it was said."""

    KEEP_SAID = 3

    def __init__(self, save) -> None:
        self._save, self._user, self._ai = save, "", ""
        self._said: list[str] = []      # recent assistant texts, to recognise echo
        self.echo = False               # the current user turn is echo

    def user(self, chunk: str) -> bool:
        """Adds a chunk of what the model heard. True the moment the turn turns out to be echo (reported once)."""
        if self.echo:
            return False
        self._user += chunk
        self.echo = any(is_echo(self._user, t) for t in self._said + [self._ai])
        return self.echo

    def assistant(self, chunk: str) -> None:
        self._ai += chunk

    def _flush(self, note: str = "") -> None:
        if self._user.strip() and not self.echo:
            self._save("user", self._user.strip())
        if self._ai.strip():
            self._said = (self._said + [self._ai])[-self.KEEP_SAID:]
            if not self.echo:
                self._save("assistant", self._ai.strip() + note)
        self._user, self._ai, self.echo = "", "", False

    def turn_complete(self) -> None:
        self._flush()

    def interrupted(self) -> None:
        self._flush(" [interrupted]")


def declarations(mode: Mode) -> list[types.FunctionDeclaration]:
    out = []
    for fn in TOOLS_BY_MODE[mode]:
        props, required = {}, []
        for name, param in inspect.signature(fn).parameters.items():
            if name == "tool_context":
                continue
            props[name] = types.Schema(type=_TYPES[param.annotation])
            if param.default is inspect.Parameter.empty:
                required.append(name)
        out.append(types.FunctionDeclaration(
            name=fn.__name__, description=inspect.getdoc(fn) or fn.__name__,
            parameters=types.Schema(type="OBJECT", properties=props, required=required)))
    return out


def extra_actions(name: str, result: dict, state: dict) -> list[dict]:
    """UI actions derived from tool results in code, so they never depend on the model remembering a follow-up call.
    In-store, a product search highlights the top product's shelf on the map."""
    if name == "search_products" and state.get("mode") == "instore":
        top = next((p for p in result.get("products") or [] if p.get("aisle")), None)
        if top:
            return [{"type": "action", "name": "highlight_map", "data": {
                "aisle": top["aisle"], "bay": top.get("bay") or 1, "shelf": 1, "side": "left", "x": 0, "y": 0,
                "product_id": top["product_id"], "name": top["name"]}}]
    return []


def _coerce(fn, args: dict) -> dict:
    """The live model sometimes sends numbers as strings; cast to the annotated type where it is int or float."""
    out = {}
    for k, v in args.items():
        ann = inspect.signature(fn).parameters.get(k)
        try:
            out[k] = (int(v) if ann and ann.annotation is int else float(v) if ann and ann.annotation is float else v)
        except (TypeError, ValueError):
            out[k] = v
    return out


def dispatch(name: str, args: dict, state: dict) -> dict:
    fn = next((f for f in TOOLS_BY_MODE[state["mode"]] if f.__name__ == name), None)
    if not fn:
        return {"error": "unknown_tool"}
    log.info("live tool %s %s", name, {k: str(v)[:80] for k, v in args.items()})
    try:
        return fn(**_coerce(fn, args), tool_context=SimpleNamespace(state=state))
    except Exception as exc:
        log.warning("tool %s failed: %s", name, exc)
        return {"error": str(exc)[:200]}


def _language_block(s: Session) -> str:
    return prompts.language_block(s.language, s.mode)


def _transcription(s: Session, store_languages: list[str]) -> types.AudioTranscriptionConfig:
    """Language hints for the live transcript. The model understands Tamil speech but writes it in another script unless
    hinted; a Tamil hint leaves English and Hindi speech intact (measured), while a hint that also lists Hindi tips
    Tamil into Devanagari. So: the chosen language alone, or the store's regional language plus English."""
    chosen = languages.bcp47(s.language)
    if chosen:
        return types.AudioTranscriptionConfig(language_codes=[chosen])
    regional = next((languages.bcp47(l) for l in store_languages if l != "en" and languages.bcp47(l)), None)
    return types.AudioTranscriptionConfig(language_codes=[regional, "en-IN"] if regional else ["en-IN"])


def _config(s: Session) -> types.LiveConnectConfig:
    history = conversation.history_text(s)
    store = prompts.store_state(s.store_id)
    return types.LiveConnectConfig(
        response_modalities=["AUDIO"],
        system_instruction=prompts.for_mode(s.mode) + prompts.store_block(store) + prompts.customer_block(prompts.customer_state(s)) + VOICE_BLOCK + (f"\n{history}\n" if history else "") + _language_block(s),
        tools=[types.Tool(function_declarations=declarations(s.mode))],
        input_audio_transcription=_transcription(s, store.get("languages") or []),
        output_audio_transcription=types.AudioTranscriptionConfig(),
        speech_config=types.SpeechConfig(voice_config=types.VoiceConfig(prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=VOICE_NAME))),
        realtime_input_config=types.RealtimeInputConfig(automatic_activity_detection=types.AutomaticActivityDetection(
            start_of_speech_sensitivity=types.StartSensitivity.START_SENSITIVITY_LOW,
            end_of_speech_sensitivity=types.EndSensitivity.END_SENSITIVITY_LOW,
            prefix_padding_ms=400, silence_duration_ms=1100)),
        enable_affective_dialog=True if settings.gemini_live_affective else None,
        context_window_compression=types.ContextWindowCompressionConfig(sliding_window=types.SlidingWindow()),
        session_resumption=types.SessionResumptionConfig(handle=_resume_handles.get(s.session_id)),
    )


async def run(ws: WebSocket, s: Session) -> None:
    if s.session_id in _active:
        raise SessionBusy()
    _active.add(s.session_id)
    try:
        await _run(ws, s)
    finally:
        _active.discard(s.session_id)


async def _run(ws: WebSocket, s: Session) -> None:
    state = {"store_id": s.store_id, "mode": s.mode, "cart_id": s.cart_id, "session_id": s.session_id, "language": s.language, "customer_id": s.customer_id, "user_id": s.user_id}
    recorder = TurnRecorder(lambda role, text: conversation.add_turn(s, role, text))
    cuts = CutCounter()
    try:
        cm = gemini.live_client().aio.live.connect(model=settings.gemini_live_model, config=_config(s))
        live = await cm.__aenter__()
    except Exception:
        if not _resume_handles.pop(s.session_id, None):
            raise
        cm = gemini.live_client().aio.live.connect(model=settings.gemini_live_model, config=_config(s))   # stale handle: start fresh
        live = await cm.__aenter__()
    try:
        await ws.send_text(json.dumps({"type": "ready"}))

        async def uplink() -> None:
            while True:
                msg = await ws.receive()
                if msg.get("type") == "websocket.disconnect":
                    return
                if msg.get("bytes"):
                    if len(msg["bytes"]) > MAX_AUDIO_FRAME:
                        continue
                    await live.send_realtime_input(audio=types.Blob(data=msg["bytes"], mime_type="audio/pcm;rate=16000"))
                elif msg.get("text"):
                    try:
                        frame = json.loads(msg["text"])
                    except ValueError:
                        continue
                    if not isinstance(frame, dict):
                        continue
                    if frame.get("type") == "text" and frame.get("text"):
                        recorder.user(str(frame["text"])[:2000])   # typed frames have no audio transcription
                        await live.send_client_content(
                            turns=types.Content(role="user", parts=[types.Part(text=str(frame["text"])[:2000])]), turn_complete=True)
                    elif frame.get("type") == "end":
                        _resume_handles.pop(s.session_id, None)   # a deliberate end: the next conversation starts a fresh model context
                        return

        async def downlink() -> None:
            while True:  # receive() yields one turn and stops at turn_complete; the session stays open
              async for msg in live.receive():
                  if msg.session_resumption_update and msg.session_resumption_update.new_handle:
                      _resume_handles[s.session_id] = msg.session_resumption_update.new_handle
                  if msg.go_away:
                      await ws.send_text(json.dumps({"type": "reconnect"}))
                  sc = msg.server_content
                  if sc:
                      if sc.interrupted:
                          recorder.interrupted()
                          await ws.send_text(json.dumps({"type": "interrupted"}))
                          if cuts.interrupted():
                              log.info("live echo by timing session=%s", s.session_id[:8])
                              await ws.send_text(json.dumps({"type": "echo"}))
                      if sc.input_transcription and sc.input_transcription.text and not recorder.echo:
                          heard = clean(sc.input_transcription.text)
                          if heard.strip() and recorder.user(heard):       # the assistant's own voice came back: tell the client, show nothing more of it
                              log.info("live echo by text session=%s words=%d", s.session_id[:8], len(heard.split()))
                              await ws.send_text(json.dumps({"type": "echo"}))
                          elif heard.strip():
                              await ws.send_text(json.dumps({"type": "transcript", "role": "user", "text": heard}))
                      if sc.output_transcription and sc.output_transcription.text:
                          recorder.assistant(sc.output_transcription.text)
                          await ws.send_text(json.dumps({"type": "transcript", "role": "assistant", "text": sc.output_transcription.text}))
                      if sc.model_turn:
                          for part in sc.model_turn.parts:
                              if part.inline_data and part.inline_data.data:
                                  cuts.reply_started()
                                  await ws.send_bytes(part.inline_data.data)
                      if sc.turn_complete:
                          recorder.turn_complete()
                          cuts.completed()
                          await ws.send_text(json.dumps({"type": "turn_complete"}))
                  if msg.tool_call:
                      responses = []
                      for call in msg.tool_call.function_calls:
                          await ws.send_text(json.dumps({"type": "status", "tool": call.name}))
                          result = await asyncio.to_thread(dispatch, call.name, dict(call.args or {}), state)
                          await ws.send_text(json.dumps({"type": "action", "name": ACTION_FOR_TOOL.get(call.name, call.name), "data": result}, ensure_ascii=False))
                          for extra in extra_actions(call.name, result, state):
                              await ws.send_text(json.dumps(extra, ensure_ascii=False))
                          responses.append(types.FunctionResponse(id=call.id, name=call.name, response=result))
                      await live.send_tool_response(function_responses=responses)

        up = asyncio.create_task(uplink())
        down = asyncio.create_task(downlink())
        try:
            done, _ = await asyncio.wait({up, down}, return_when=asyncio.FIRST_COMPLETED, timeout=MAX_SESSION_S)
            for t in done:
                exc = t.exception()
                if exc and not isinstance(exc, WebSocketDisconnect):
                    raise exc   # the endpoint tells the client and closes
        finally:
            for t in (up, down):
                t.cancel()
            recorder.turn_complete()
    finally:
        await cm.__aexit__(None, None, None)
