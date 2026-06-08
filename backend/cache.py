"""Simple TTL cache to avoid recomputing expensive signals on every request."""
import time
import logging
from typing import Any, Callable, Optional

log = logging.getLogger(__name__)


class Cache:
    def __init__(self):
        self._store: dict = {}

    def get_or_compute(self, key: str, fn: Callable, ttl: int = 3600) -> Any:
        now = time.time()
        if key in self._store:
            value, expiry = self._store[key]
            if now < expiry:
                return value

        log.info(f"Cache miss: computing {key}...")
        t0 = time.time()
        value = fn()
        elapsed = time.time() - t0
        log.info(f"Computed {key} in {elapsed:.2f}s")
        self._store[key] = (value, now + ttl)
        return value

    def get(self, key: str) -> Optional[Any]:
        """Return cached value if still valid, else None."""
        now = time.time()
        if key in self._store:
            value, expiry = self._store[key]
            if now < expiry:
                return value
        return None

    def set(self, key: str, value: Any, ttl: int = 3600):
        """Store a value with the given TTL."""
        self._store[key] = (value, time.time() + ttl)

    def invalidate(self, key: str):
        self._store.pop(key, None)

    def clear(self):
        self._store.clear()

    def clear_all(self):
        """Alias for clear — used by scheduler deep refresh."""
        self._store.clear()
        log.info("Cache cleared")
