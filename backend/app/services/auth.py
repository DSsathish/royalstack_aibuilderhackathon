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


_EMAILS: dict[str, str] = {}   # uid -> email seen on the last verified token (for owner bootstrap)


def current_uid(authorization: str | None = Header(default=None),
                x_test_uid: str | None = Header(default=None)) -> str:
    if settings.env == "test" and x_test_uid:
        return x_test_uid  # test-only shortcut, never active outside ENV=test
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "missing bearer token")
    claims = verify_id_token(authorization.removeprefix("Bearer "))
    if claims.get("email") and claims.get("email_verified"):
        _EMAILS[claims["sub"]] = claims["email"].lower()
    return claims["sub"]


def owned_stores(uid: str) -> list[str]:
    """Stores from users/{uid}; if none, bootstrap from stores whose owner_emails list this user's email."""
    doc = db.users().document(uid).get()
    stores = doc.to_dict().get("stores", []) if doc.exists else []
    email = _EMAILS.get(uid)
    if not stores and email:
        from google.cloud.firestore_v1 import FieldFilter
        stores = [d.id for d in db.client().collection("stores").where(filter=FieldFilter("owner_emails", "array_contains", email)).stream()]
        if stores:
            db.users().document(uid).set({"stores": stores, "email": email}, merge=True)
    return stores


def require_owner(store_id: str, uid: str) -> str:
    """Returns uid if it owns store_id, else 403."""
    if store_id not in owned_stores(uid):
        raise HTTPException(403, "not an owner of this store")
    return uid
