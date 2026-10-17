"""Per-store payment secrets in Secret Manager, cached briefly. Only the key id is ever public."""

import logging
import time

from app.config import settings

log = logging.getLogger(__name__)
_cache: dict[str, tuple[float, str]] = {}
TTL_S = 300


def _name(store_id: str) -> str:
    return f"razorpay-{store_id}"


def secret_for(store_id: str) -> str:
    hit = _cache.get(store_id)
    if hit and time.time() - hit[0] < TTL_S:
        return hit[1]
    try:
        from google.cloud import secretmanager
        client = secretmanager.SecretManagerServiceClient()
        path = f"projects/{settings.google_cloud_project}/secrets/{_name(store_id)}/versions/latest"
        value = client.access_secret_version(name=path).payload.data.decode().strip()
    except Exception as exc:
        log.warning("no payment secret for %s: %s", store_id, exc)
        value = ""
    _cache[store_id] = (time.time(), value)
    return value


def store_secret(store_id: str, value: str) -> None:
    from google.cloud import secretmanager
    client = secretmanager.SecretManagerServiceClient()
    parent = f"projects/{settings.google_cloud_project}"
    name = f"{parent}/secrets/{_name(store_id)}"
    try:
        client.get_secret(name=name)
    except Exception:
        client.create_secret(parent=parent, secret_id=_name(store_id), secret={"replication": {"automatic": {}}})
    client.add_secret_version(parent=name, payload={"data": value.encode()})
    _cache.pop(store_id, None)
