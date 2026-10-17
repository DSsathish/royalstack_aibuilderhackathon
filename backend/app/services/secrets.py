"""Per-store secrets in Secret Manager, cached briefly. Names: razorpay-{store} (payments), sync-{store} (webhooks)."""

import logging
import time

from app.config import settings

log = logging.getLogger(__name__)
_cache: dict[str, tuple[float, str]] = {}
TTL_S = 300


def get(name: str) -> str:
    """The latest version's value, or "" when the secret does not exist."""
    hit = _cache.get(name)
    if hit and time.time() - hit[0] < TTL_S:
        return hit[1]
    try:
        from google.cloud import secretmanager
        client = secretmanager.SecretManagerServiceClient()
        path = f"projects/{settings.google_cloud_project}/secrets/{name}/versions/latest"
        value = client.access_secret_version(name=path).payload.data.decode().strip()
    except Exception as exc:
        log.warning("no secret %s: %s", name, exc)
        value = ""
    _cache[name] = (time.time(), value)
    return value


def put(name: str, value: str) -> None:
    from google.cloud import secretmanager
    client = secretmanager.SecretManagerServiceClient()
    parent = f"projects/{settings.google_cloud_project}"
    full = f"{parent}/secrets/{name}"
    try:
        client.get_secret(name=full)
    except Exception:
        client.create_secret(parent=parent, secret_id=name, secret={"replication": {"automatic": {}}})
    client.add_secret_version(parent=full, payload={"data": value.encode()})
    _cache.pop(name, None)
