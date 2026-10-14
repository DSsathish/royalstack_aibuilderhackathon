"""Firebase ID token verification and owner membership checks."""

from fastapi import Header, HTTPException, Path
from google.auth.transport import requests as g_requests
from google.oauth2 import id_token

from app.config import settings
from app.services import db

STORE_ID = Path(pattern=r"^[a-z0-9-]{3,40}$")


def verify_id_token(token: str) -> dict:
    try:
        return id_token.verify_firebase_token(token, g_requests.Request(), audience=settings.google_cloud_project)
    except Exception:
        raise HTTPException(401, "invalid token")


def current_uid(authorization: str | None = Header(default=None),
                x_test_uid: str | None = Header(default=None)) -> str:
    if settings.env == "test" and x_test_uid:
        return x_test_uid  # test-only shortcut, never active outside ENV=test
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "missing bearer token")
    return verify_id_token(authorization.removeprefix("Bearer "))["sub"]


def require_owner(store_id: str, uid: str) -> str:
    """Returns uid if it is a member of store_id, else 403."""
    doc = db.users().document(uid).get()
    if not doc.exists or store_id not in doc.to_dict().get("stores", []):
        raise HTTPException(403, "not an owner of this store")
    return uid
