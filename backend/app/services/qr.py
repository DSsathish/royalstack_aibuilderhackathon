"""Signed tokens for entrance QR codes and exit receipts. HMAC-SHA256, no external library."""

import base64
import hashlib
import hmac
import json
import time

from app.config import settings

RECEIPT_TTL_S = 30 * 60


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _mac(body: str) -> str:
    return hmac.new(settings.qr_session_signing_key.encode(), body.encode(), hashlib.sha256).hexdigest()


def sign(payload: dict, ttl_s: int | None = None) -> str:
    data = dict(payload)
    if ttl_s is not None:
        data["exp"] = int(time.time()) + ttl_s
    body = _b64(json.dumps(data, separators=(",", ":"), sort_keys=True).encode())
    return f"{body}.{_mac(body)}"


def verify(token: str) -> dict | None:
    try:
        body, mac = token.split(".", 1)
    except ValueError:
        return None
    if not hmac.compare_digest(mac, _mac(body)):
        return None
    try:
        data = json.loads(_unb64(body))
    except (ValueError, UnicodeDecodeError):
        return None
    if "exp" in data and data["exp"] < time.time():
        return None
    return data


def entrance_token(store_id: str) -> str:
    return sign({"kind": "entrance", "store_id": store_id})


def receipt_token(order_id: str, store_id: str, count: int) -> str:
    return sign({"kind": "receipt", "order_id": order_id, "store_id": store_id, "count": count}, ttl_s=RECEIPT_TTL_S)
