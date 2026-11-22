"""In-memory sliding-window rate limiter for radar-online's write endpoints."""

from __future__ import annotations

import math
import time
from collections import defaultdict, deque
from collections.abc import Callable
from threading import Lock


class SlidingWindowLimiter:
    """Allow `limit` hits per key within any `window_seconds`.

    shortcut: state lives in this process, right for the single uvicorn worker radar-online
    runs; move it to SQLite or Redis before running several workers or replicas.
    """

    def __init__(
        self, limit: int, window_seconds: float, clock: Callable[[], float] = time.monotonic
    ) -> None:
        self._limit = limit
        self._window = window_seconds
        self._clock = clock
        self._hits: defaultdict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def hit(self, key: str) -> int | None:
        """Record a hit for `key`, or refuse it and return the seconds until a slot frees up.

        A refused hit is not recorded, so retrying never extends the wait.
        """
        with self._lock:
            now = self._clock()
            hits = self._hits[key]
            while hits and hits[0] <= now - self._window:
                hits.popleft()
            if len(hits) >= self._limit:
                return max(1, math.ceil(hits[0] + self._window - now))
            hits.append(now)
            return None

    def reset(self) -> None:
        """Forget every hit (tests, or an operator clearing a mistaken lockout)."""
        with self._lock:
            self._hits.clear()
