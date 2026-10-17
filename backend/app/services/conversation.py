"""Conversation memory shared by text chat and live voice. Turns are stored per session (shoppers) or per owner account."""

from app.domain.models import Session, now
from app.services import db

MAX_TURN_CHARS = 600
LINE_CHARS = 160


def key(s: Session) -> str:
    return s.user_id if s.mode == "owner" and s.user_id else s.session_id


def _turns(s: Session):
    return db.client().collection("conversations").document(key(s)).collection("turns")


def add_turn(s: Session, role: str, text: str) -> None:
    text = (text or "").strip()
    if not text:
        return
    _turns(s).add({"role": role, "text": text[:MAX_TURN_CHARS], "at": now()})


def recent(s: Session, limit: int = 12) -> list[dict]:
    docs = _turns(s).order_by("at", direction="DESCENDING").limit(limit).stream()
    return [d.to_dict() for d in docs][::-1]


def history_text(s: Session, limit: int = 12) -> str:
    turns = recent(s, limit)
    if not turns:
        return ""
    who = "Owner" if s.mode == "owner" else "Shopper"
    lines = [f"{who if t['role'] == 'user' else 'Assistant'}: {t['text'][:LINE_CHARS]}" for t in turns]
    return "Earlier in this conversation (most recent last):\n" + "\n".join(lines)
