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
_PHONES: dict[str, str] = {}   # uid -> phone number from a phone sign-in token (shopper identity)
_AUTH_TIMES: dict[str, int] = {}   # uid -> auth_time of the last verified token (freshness for points)


def current_uid(authorization: str | None = Header(default=None),
                x_test_uid: str | None = Header(default=None)) -> str:
    if settings.env == "test" and x_test_uid:
        return x_test_uid  # test-only shortcut, never active outside ENV=test
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "missing bearer token")
    claims = verify_id_token(authorization.removeprefix("Bearer "))
    if claims.get("email") and claims.get("email_verified"):
        _EMAILS[claims["sub"]] = claims["email"].lower()
    if claims.get("phone_number"):
        _PHONES[claims["sub"]] = claims["phone_number"]
    if claims.get("auth_time"):
        _AUTH_TIMES[claims["sub"]] = int(claims["auth_time"])
    return claims["sub"]


def require_phone(uid: str) -> str:
    """The phone number behind a shopper token; 403 for tokens without one."""
    phone = _PHONES.get(uid)
    if not phone:
        raise HTTPException(403, "a phone sign-in is required")
    return phone


RECENT_S = 600


def require_recent_phone(uid: str) -> str:
    """A phone sign-in whose code was verified in the last ten minutes: the OTP step before spending points."""
    import time
    phone = require_phone(uid)
    at = _AUTH_TIMES.get(uid)
    if not at or time.time() - at > RECENT_S:
        raise HTTPException(403, "verify your number again to use points")
    return phone


def _bootstrap(uid: str, field: str, role: str) -> list[str]:
    """Stores whose {field} lists this user's verified email; records membership on first sight."""
    email = _EMAILS.get(uid)
    if not email:
        return []
    from google.cloud.firestore_v1 import FieldFilter
    found = [d.id for d in db.client().collection("stores").where(filter=FieldFilter(field, "array_contains", email)).stream()]
    if found:
        doc = db.users().document(uid).get()
        data = doc.to_dict() if doc.exists else {}
        roles = {**data.get("roles", {}), **{s: role for s in found if data.get("roles", {}).get(s) != "owner"}}
        db.users().document(uid).set({"stores": sorted(set(data.get("stores", [])) | set(found)), "roles": roles, "email": email}, merge=True)
    return found


def roles_for(uid: str) -> dict[str, str]:
    """store_id -> owner | staff, bootstrapping from owner_emails / staff_emails on first sign-in."""
    doc = db.users().document(uid).get()
    roles = dict(doc.to_dict().get("roles", {})) if doc.exists else {}
    if doc.exists and not roles and doc.to_dict().get("stores"):      # memberships created before roles existed
        roles = {s: "owner" for s in doc.to_dict()["stores"]}
    if not roles:
        for s in _bootstrap(uid, "owner_emails", "owner"):
            roles[s] = "owner"
        for s in _bootstrap(uid, "staff_emails", "staff"):
            roles.setdefault(s, "staff")
    return roles


def owned_stores(uid: str) -> list[str]:
    return [s for s, r in roles_for(uid).items() if r == "owner"]


def require_owner(store_id: str, uid: str) -> str:
    """Returns uid if it owns store_id, else 403."""
    if roles_for(uid).get(store_id) != "owner":
        raise HTTPException(403, "not an owner of this store")
    return uid


def require_staff(store_id: str, uid: str) -> str:
    """Owner or staff of the store."""
    if roles_for(uid).get(store_id) not in ("owner", "staff"):
        raise HTTPException(403, "not a member of this store")
    return uid


def verified_email(uid: str) -> str:
    email = _EMAILS.get(uid)
    if not email:
        raise HTTPException(403, "a verified email is required: sign in with Google, or open the verification link we emailed you")
    return email
