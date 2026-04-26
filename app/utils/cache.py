import logging
import time
from typing import Any, Dict, Optional
from collections import OrderedDict
from threading import Lock

logger = logging.getLogger(__name__)


class InMemoryCache:
    """Thread-safe in-memory cache with TTL and LRU eviction.

    Hit/miss counters are tracked and logged at DEBUG level on every access,
    and can be read at any time via :meth:`stats`.
    """

    def __init__(self, max_size: int = 1000):
        """Create a new cache.

        Args:
            max_size: Maximum number of entries before the least-recently-used
                item is evicted.  Defaults to 1 000.
        """
        self._cache: OrderedDict = OrderedDict()
        self._max_size = max_size
        self._lock = Lock()
        self._hits = 0
        self._misses = 0

    def get(self, key: str) -> Optional[Any]:
        """Return the cached value for *key*, or ``None`` on miss / expiry.

        Updates the LRU position on a cache hit.
        """
        with self._lock:
            if key in self._cache:
                value, expiry = self._cache[key]
                if time.time() < expiry:
                    self._cache.move_to_end(key)
                    self._hits += 1
                    logger.debug("Cache HIT  key=%s  (hits=%d misses=%d)", key, self._hits, self._misses)
                    return value
                del self._cache[key]
            self._misses += 1
            logger.debug("Cache MISS key=%s  (hits=%d misses=%d)", key, self._hits, self._misses)
        return None

    def set(self, key: str, value: Any, ttl: int = 60) -> None:
        """Store *value* under *key* with a TTL of *ttl* seconds.

        Evicts the least-recently-used entry when the cache is full.
        """
        with self._lock:
            expiry = time.time() + ttl
            if key in self._cache:
                self._cache.move_to_end(key)
            self._cache[key] = (value, expiry)
            if len(self._cache) > self._max_size:
                self._cache.popitem(last=False)

    def delete(self, key: str) -> None:
        """Remove *key* from the cache (no-op if the key does not exist)."""
        with self._lock:
            if key in self._cache:
                del self._cache[key]

    def clear(self) -> None:
        """Remove every entry from the cache."""
        with self._lock:
            self._cache.clear()

    def stats(self) -> Dict[str, Any]:
        """Return a snapshot of hit/miss counters.

        Returns:
            Dict with keys ``hits``, ``misses``, ``size``, and ``hit_rate``
            (as a percentage string, or ``"n/a"`` when no requests yet).
        """
        with self._lock:
            total = self._hits + self._misses
            hit_rate = f"{self._hits / total * 100:.1f}%" if total else "n/a"
            return {
                "hits": self._hits,
                "misses": self._misses,
                "size": len(self._cache),
                "hit_rate": hit_rate,
            }


# Global cache instance with safe default limit
cache = InMemoryCache(max_size=1000)
