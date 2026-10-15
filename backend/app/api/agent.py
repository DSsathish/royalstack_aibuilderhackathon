"""Sessions and the agent chat stream (Server-Sent Events)."""

import json
import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile, WebSocket
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.agent import agent, live
from app.config import settings
from app.domain.models import Mode, Session
from app.services import db, gemini, sessions
from app.services.ratelimit import Limiter

log = logging.getLogger(__name__)
router = APIRouter(tags=["agent"])
MAX_UPLOAD = 4 * 1024 * 1024
limiter = Limiter()


def client_key(request: Request) -> str:
    return (request.headers.get("x-forwarded-for") or (request.client.host if request.client else "?")).split(",")[0].strip()


def limit_sessions(request: Request) -> None:
    if not limiter.allow("sess:" + client_key(request), limit=limiter.sessions_per_minute):
        raise HTTPException(429, "too many sessions, slow down")


def limit_chat(session_id: str) -> None:
    if not limiter.allow("chat:" + session_id, limit=limiter.chat_per_minute):
        raise HTTPException(429, "too many requests for this session, please wait a moment")


class SessionIn(BaseModel):
    store_id: str
    mode: Mode


@router.post("/sessions", response_model=Session, dependencies=[Depends(limit_sessions)])
def create_session(body: SessionIn):
    if not db.store_ref(body.store_id).get().exists:
        raise HTTPException(404, "store not found")
    if body.mode == "instore":
        raise HTTPException(403, "in-store sessions start from the entrance QR")
    if body.mode == "owner" and settings.env not in ("dev", "test"):
        raise HTTPException(403, "owner sessions require owner sign-in")  # wired in phase 6
    return sessions.create(body.store_id, body.mode)


def _session(session_id: str) -> Session:
    s = sessions.get(session_id)
    if not s:
        raise HTTPException(404, "session not found or expired")
    return s


async def _read_upload(upload: UploadFile | None, kind: str) -> tuple[bytes, str] | None:
    if upload is None:
        return None
    if not (upload.content_type or "").startswith(f"{kind}/"):
        raise HTTPException(415, f"expected {kind}/* upload")
    data = await upload.read(MAX_UPLOAD + 1)
    if len(data) > MAX_UPLOAD:
        raise HTTPException(413, "upload larger than 4 MB")
    return data, upload.content_type


def _sse(events):
    async def gen():
        try:
            async for e in events:
                yield f"data: {json.dumps(e, ensure_ascii=False)}\n\n"
        except Exception as exc:  # model/tool failure mid-stream: tell the client, keep the stream well-formed
            log.warning("agent stream failed: %s", exc)
            msg = "The assistant is temporarily unavailable (model credits or quota). Scan, cart and checkout still work."
            yield f"data: {json.dumps({'type': 'error', 'text': msg})}\n\n"
    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.post("/agent/chat")
async def chat(session_id: str = Form(...), message: str = Form(min_length=1, max_length=2000),
               image: UploadFile | None = File(default=None)):
    s = _session(session_id)
    limit_chat(s.session_id)
    img = await _read_upload(image, "image")
    return _sse(agent.chat(s, message, img))


@router.post("/agent/audio")
async def audio(session_id: str = Form(...), audio: UploadFile = File(...)):
    s = _session(session_id)
    limit_chat(s.session_id)
    data, mime = await _read_upload(audio, "audio")
    transcript = gemini.transcribe(data, mime)
    if not transcript:
        raise HTTPException(422, "Could not transcribe audio. The assistant may be temporarily unavailable.")

    async def with_transcript():
        yield {"type": "transcript", "text": transcript}
        async for e in agent.chat(s, transcript):
            yield e

    return _sse(with_transcript())


@router.websocket("/agent/live")
async def live_voice(ws: WebSocket, session_id: str = Query(pattern=r"^[a-f0-9]{32}$")):
    s = sessions.get(session_id)
    # owner sessions are valid when minted by the authenticated owner endpoint (user_id set); the dev path only in dev/test
    if not s or (s.mode == "owner" and not s.user_id and settings.env not in ("dev", "test")):
        await ws.close(code=4404)
        return
    await ws.accept()
    try:
        await live.run(ws, s)
    except live.SessionBusy:
        await ws.send_text(json.dumps({"type": "error", "text": "Live voice is already open in another tab for this visit."}))
    except Exception as exc:  # model or network failure: tell the client, then close
        log.warning("live session ended with error: %s", exc)
        try:
            await ws.send_text(json.dumps({"type": "error", "text": "Live voice is unavailable right now. Use the microphone button instead."}))
        except Exception:
            pass
    finally:
        try:
            await ws.close()
        except Exception:
            pass
