"""In-memory Cache implementation: a dict with lazy TTL expiry.

Dev/single-process default (see docs/decisions.md, 7) - no size limit, no
background sweep, and get/set have no `await` inside them so nothing can
interleave mid-operation under concurrent asyncio.gather callers, even
without a lock. The one accepted gap: two concurrent requests for the
same uncached key can both miss and both do the underlying work (a
"cache stampede") - not a correctness bug, just a missed optimization,
not worth solving with locking for this scope. The Cache port means
swapping in Redis later is a bootstrap-level config change, not a
rewrite of anything that depends on this interface.
"""
import time
from typing import Any

from src.domain.interfaces import Cache


class InMemoryCache(Cache):
    def __init__(self) -> None:
        self._store: dict[str, tuple[Any, float]] = {}

    async def get(self, key: str) -> Any | None:
        entry = self._store.get(key)
        if entry is None:
            return None

        value, expires_at = entry
        if time.monotonic() >= expires_at:
            del self._store[key]
            return None

        return value

    async def set(self, key: str, value: Any, ttl_seconds: int) -> None:
        self._store[key] = (value, time.monotonic() + ttl_seconds)
