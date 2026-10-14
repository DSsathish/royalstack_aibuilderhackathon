import pytest

from app.config import Settings


def test_default_signing_key_refused_outside_dev_and_test():
    with pytest.raises(ValueError, match="QR_SESSION_SIGNING_KEY"):
        Settings(env="prod", qr_session_signing_key="dev-only-change-me")
    assert Settings(env="prod", qr_session_signing_key="x" * 32).env == "prod"
    assert Settings(env="dev").qr_session_signing_key == "dev-only-change-me"
