import pytest
from app.utils.cache import InMemoryCache
from app.utils.ids import parse_channel_id, parse_program_id, parse_episode_id

def test_parse_channel_id():
    """Test parsing channel IDs"""
    # Valid channel ID
    result = parse_channel_id("cutam:fr:francetv:france2")
    assert result == {"provider": "francetv", "channel_slug": "france2"}
    
    # Channel ID with complex slug
    result = parse_channel_id("cutam:fr:francetv:france2-sport")
    assert result == {"provider": "francetv", "channel_slug": "france2-sport"}
    
    # Invalid channel ID
    result = parse_channel_id("invalid:id")
    assert result == {}

def test_parse_program_id():
    """Test parsing program IDs"""
    # Valid program ID
    result = parse_program_id("cutam:fr:francetv:prog:soiree100")
    assert result == {"provider": "francetv", "program_slug": "soiree100"}
    
    # Program ID with complex slug
    result = parse_program_id("cutam:fr:francetv:prog:soiree-100-special")
    assert result == {"provider": "francetv", "program_slug": "soiree-100-special"}
    
    # Invalid program ID
    result = parse_program_id("invalid:id")
    assert result == {}

def test_parse_episode_id():
    """Test parsing episode IDs"""
    # Valid episode ID
    result = parse_episode_id("cutam:fr:francetv:ep:soiree100:1:1")
    assert result == {"provider": "francetv", "program_slug": "soiree100", "season": 1, "episode": 1}
    
    # Episode ID with string season/episode
    result = parse_episode_id("cutam:fr:francetv:ep:soiree100:17:05")
    assert result == {"provider": "francetv", "program_slug": "soiree100", "season": 17, "episode": 5}
    
    # Invalid episode ID
    result = parse_episode_id("invalid:id")
    assert result == {}

def test_in_memory_cache():
    """Test the in-memory cache functionality"""
    cache = InMemoryCache()
    
    # Test setting and getting a value
    cache.set("test_key", "test_value", ttl=1)
    assert cache.get("test_key") == "test_value"
    
    # Test getting a non-existent key
    assert cache.get("nonexistent_key") is None
    
    # Test deleting a key
    cache.delete("test_key")
    assert cache.get("test_key") is None
    
    # Test clearing the cache
    cache.set("key1", "value1")
    cache.set("key2", "value2")
    cache.clear()
    assert cache.get("key1") is None
    assert cache.get("key2") is None