"""Per-store payment secrets. Only the key id is ever public; the secret lives in Secret Manager."""

from app.services import secrets


def secret_for(store_id: str) -> str:
    return secrets.get(f"razorpay-{store_id}")


def store_secret(store_id: str, value: str) -> None:
    secrets.put(f"razorpay-{store_id}", value)
