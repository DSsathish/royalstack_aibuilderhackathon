"""Bridge one browser websocket to one Gemini Live session: audio both ways, tools run locally."""

import asyncio
import inspect
import json
import logging
from types import SimpleNamespace

from fastapi import WebSocket, WebSocketDisconnect
from google.genai import types

from app.agent import prompts
from app.agent.agent import ACTION_FOR_TOOL
from app.agent.tools import TOOLS_BY_MODE
from app.config import settings
from app.domain.models import Mode, Session
from app.services import gemini

log = logging.getLogger(__name__)
_TYPES = {str: "STRING", int: "INTEGER", float: "NUMBER", bool: "BOOLEAN"}

VOICE_BLOCK = """
You are speaking aloud. Keep each reply to one or two short sentences. Say prices and aisles
plainly. After a tool call, tell the shopper what you did in a few words. If they interrupt, stop
and listen.
"""


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


def dispatch(name: str, args: dict, state: dict) -> dict:
    fn = next((f for f in TOOLS_BY_MODE[state["mode"]] if f.__name__ == name), None)
    if not fn:
        return {"error": "unknown_tool"}
    try:
        return fn(**args, tool_context=SimpleNamespace(state=state))
    except Exception as exc:
        log.warning("tool %s failed: %s", name, exc)
        return {"error": str(exc)[:200]}


def _config(mode: Mode) -> types.LiveConnectConfig:
    return types.LiveConnectConfig(
        response_modalities=["AUDIO"],
        system_instruction=prompts.for_mode(mode) + VOICE_BLOCK,
        tools=[types.Tool(function_declarations=declarations(mode))],
        input_audio_transcription=types.AudioTranscriptionConfig(),
        output_audio_transcription=types.AudioTranscriptionConfig(),
    )


async def run(ws: WebSocket, s: Session) -> None:
    state = {"store_id": s.store_id, "mode": s.mode, "cart_id": s.cart_id, "session_id": s.session_id, "language": s.language}
    client = gemini.client()
    async with client.aio.live.connect(model=settings.gemini_live_model, config=_config(s.mode)) as live:
        await ws.send_text(json.dumps({"type": "ready"}))

        async def uplink() -> None:
            while True:
                msg = await ws.receive()
                if msg.get("type") == "websocket.disconnect":
                    return
                if msg.get("bytes"):
                    await live.send_realtime_input(audio=types.Blob(data=msg["bytes"], mime_type="audio/pcm;rate=16000"))
                elif msg.get("text"):
                    frame = json.loads(msg["text"])
                    if frame.get("type") == "text" and frame.get("text"):
                        await live.send_client_content(
                            turns=types.Content(role="user", parts=[types.Part(text=str(frame["text"])[:2000])]), turn_complete=True)
                    elif frame.get("type") == "end":
                        return

        async def downlink() -> None:
            while True:  # receive() yields one turn and stops at turn_complete; the session stays open
              async for msg in live.receive():
                  sc = msg.server_content
                  if sc:
                      if sc.interrupted:
                          await ws.send_text(json.dumps({"type": "interrupted"}))
                      if sc.input_transcription and sc.input_transcription.text:
                          await ws.send_text(json.dumps({"type": "transcript", "role": "user", "text": sc.input_transcription.text}))
                      if sc.output_transcription and sc.output_transcription.text:
                          await ws.send_text(json.dumps({"type": "transcript", "role": "assistant", "text": sc.output_transcription.text}))
                      if sc.model_turn:
                          for part in sc.model_turn.parts:
                              if part.inline_data and part.inline_data.data:
                                  await ws.send_bytes(part.inline_data.data)
                      if sc.turn_complete:
                          await ws.send_text(json.dumps({"type": "turn_complete"}))
                  if msg.tool_call:
                      responses = []
                      for call in msg.tool_call.function_calls:
                          await ws.send_text(json.dumps({"type": "status", "tool": call.name}))
                          result = await asyncio.to_thread(dispatch, call.name, dict(call.args or {}), state)
                          await ws.send_text(json.dumps({"type": "action", "name": ACTION_FOR_TOOL.get(call.name, call.name), "data": result}, ensure_ascii=False))
                          responses.append(types.FunctionResponse(id=call.id, name=call.name, response=result))
                      await live.send_tool_response(function_responses=responses)

        up = asyncio.create_task(uplink())
        down = asyncio.create_task(downlink())
        try:
            done, pending = await asyncio.wait({up, down}, return_when=asyncio.FIRST_COMPLETED)
            for t in done:
                if t.exception() and not isinstance(t.exception(), WebSocketDisconnect):
                    log.warning("live task failed: %s", t.exception())
        finally:
            for t in (up, down):
                t.cancel()
