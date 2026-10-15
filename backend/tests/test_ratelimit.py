import time

from app.services.ratelimit import Limiter


def test_bucket_allows_then_blocks_then_refills(monkeypatch):
    lim = Limiter()
    now = [1000.0]
    monkeypatch.setattr(time, "time", lambda: now[0])
    assert all(lim.allow("k", limit=3) for _ in range(3))
    assert lim.allow("k", limit=3) is False
    now[0] += 61
    assert lim.allow("k", limit=3) is True


def test_keys_are_independent_and_old_keys_are_pruned(monkeypatch):
    lim = Limiter()
    now = [0.0]
    monkeypatch.setattr(time, "time", lambda: now[0])
    assert lim.allow("a", limit=1) and lim.allow("b", limit=1)
    assert lim.allow("a", limit=1) is False
    now[0] += 3600
    assert lim.allow("c", limit=1)
    assert "a" not in lim._hits   # pruned after an hour of silence
