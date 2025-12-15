import pytest
import time
from app.utils.cache import InMemoryCache

def test_cache_ttl():
    """Test that items expire after their TTL"""
    cache = InMemoryCache(max_size=10)
    
    # Set item with 1 second TTL
    cache.set("short_lived", "value", ttl=1)
    assert cache.get("short_lived") == "value"
    
    # Wait for expiry
    time.sleep(1.1)
    assert cache.get("short_lived") is None

def test_cache_lru_eviction():
    """Test that the cache enforces max_size and evicts least recently used items"""
    # Create small cache
    cache = InMemoryCache(max_size=3)
    
    # Fill cache
    cache.set("a", 1)
    cache.set("b", 2)
    cache.set("c", 3)
    
    assert cache.get("a") == 1
    assert cache.get("b") == 2
    assert cache.get("c") == 3
    
    # Access "a" to make it recently used. Order is now: b, c, a
    cache.get("a")
    
    # Add new item, triggering eviction of LRU item ("b")
    cache.set("d", 4)
    
    # "b" should be gone
    assert cache.get("b") is None
    # "a" (recently used), "c", "d" should exist
    assert cache.get("a") == 1
    assert cache.get("c") == 3
    assert cache.get("d") == 4

def test_cache_explicit_delete():
    cache = InMemoryCache()
    cache.set("key", "value")
    assert cache.get("key") == "value"
    
    cache.delete("key")
    assert cache.get("key") is None

def test_cache_clear():
    cache = InMemoryCache()
    cache.set("a", 1)
    cache.set("b", 2)
    
    cache.clear()
    assert cache.get("a") is None
    assert cache.get("b") is None
