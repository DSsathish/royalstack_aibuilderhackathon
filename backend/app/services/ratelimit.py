"""Small in-memory sliding-window limiter. One Cloud Run instance serves the demo, so process memory is enough."""

import time


class Limiter:
    chat_per_minute = 20          # agent turns per session
    sessions_per_minute = 30      # session creations per client address
    WINDOW_S = 60
    PRUNE_AFTER_S = 3600

    def __init__(self) -> None:
        self._hits: dict[str, list[float]] = {}
        self._last_prune = 0.0

    def allow(self, key: str, *, limit: int) -> bool:
        now = time.time()
        if now - self._last_prune > 300:
            self._prune(now)
        hits = [t for t in self._hits.get(key, []) if now - t < self.WINDOW_S]
        if len(hits) >= limit:
            self._hits[key] = hits
            return False
        hits.append(now)
        self._hits[key] = hits
        return True

    def _prune(self, now: float) -> None:
        self._last_prune = now
        for key in [k for k, v in self._hits.items() if not v or now - v[-1] >= self.PRUNE_AFTER_S]:
            del self._hits[key]

    def clear(self) -> None:
        self._hits.clear()
