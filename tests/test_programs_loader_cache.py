import pytest
from unittest.mock import patch, mock_open
from app.utils.programs_loader import _load_programs, reload_programs
from app.utils.cache import cache

def test_programs_loader_caching():
    """Test that programs loader uses the centralized cache."""
    
    # Mock data
    mock_json = '{"shows": [{"slug": "test-show", "name": "Test Show", "provider": "test"}]}'
    
    # Clear cache first
    cache.clear()
    
    # Mock open to verify file access
    with patch("builtins.open", mock_open(read_data=mock_json)) as mock_file:
        # First call - should read from file
        data1 = _load_programs()
        assert data1["shows"][0]["slug"] == "test-show"
        assert mock_file.call_count == 1
        
        # Second call - should use cache (no file read)
        data2 = _load_programs()
        assert data2 == data1
        assert mock_file.call_count == 1  # Still 1
        
        # Verify it's in the cache
        assert cache.get("programs_data") == data1
        
        # Reload - should clear cache
        reload_programs()
        assert cache.get("programs_data") is None
        
        # Third call - should read from file again
        data3 = _load_programs()
        assert data3["shows"][0]["slug"] == "test-show"
        assert mock_file.call_count == 2
