"""Conversation memory shared by text chat and live voice. Turns are stored per session (shoppers) or per owner account."""

from app.domain.models import Session, now
from app.services import db

MAX_TURN_CHARS = 600
LINE_CHARS = 160


def key(s: Session) -> str:
    if s.mode == "owner" and s.user_id:
        return s.user_id
    return s.customer_id or s.session_id      # signed-in shoppers keep memory across visits; guests per visit


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
