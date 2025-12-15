import time
from typing import Any, Optional
from collections import OrderedDict
from threading import Lock

class InMemoryCache:
    """
    Thread-safe in-memory cache with TTL (Time To Live) and LRU (Least Recently Used) eviction policy.
    """
    
    def __init__(self, max_size: int = 1000):
        self._cache = OrderedDict()
        self._max_size = max_size
        self._lock = Lock()
    
    def get(self, key: str) -> Optional[Any]:
        """
        Get a value from cache if it exists and hasn't expired.
        Updates LRU position on hit.
        """
        with self._lock:
            if key in self._cache:
                value, expiry = self._cache[key]
                if time.time() < expiry:
                    # Move to end (most recently used)
                    self._cache.move_to_end(key)
                    return value
                else:
                    # Expired, remove it
                    del self._cache[key]
        return None
    
    def set(self, key: str, value: Any, ttl: int = 60) -> None:
        """
        Set a value in cache with TTL in seconds.
        Evicts least recently used item if cache is full.
        """
        with self._lock:
            expiry = time.time() + ttl
            
            # If key exists, update and move to end
            if key in self._cache:
                self._cache.move_to_end(key)
            
            self._cache[key] = (value, expiry)
            
            # Enforce max size
            if len(self._cache) > self._max_size:
                # Remove first item (least recently used)
                self._cache.popitem(last=False)
    
    def delete(self, key: str) -> None:
        """Delete a value from cache"""
        with self._lock:
            if key in self._cache:
                del self._cache[key]
    
    def clear(self) -> None:
        """Clear all values from cache"""
        with self._lock:
            self._cache.clear()

# Global cache instance with safe default limit
cache = InMemoryCache(max_size=1000)
