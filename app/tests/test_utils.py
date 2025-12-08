"""
Utility function tests with mocked responses.
Tests http_utils, api_client, credentials, and other utilities.
"""

import pytest
from unittest.mock import patch, MagicMock, Mock
import json
import requests


class TestProviderAPIClient:
    """Test ProviderAPIClient functionality"""
    
    def test_client_initialization(self):
        """Client should initialize with correct attributes"""
        from app.utils.api_client import ProviderAPIClient
        
        client = ProviderAPIClient(
            provider_name="test_provider",
            timeout=20,
            max_retries=5
        )
        
        assert client.provider_name == "test_provider"
        assert client.timeout == 20
        assert client.max_retries == 5
        assert client.session is not None
    
    def test_prepare_headers_adds_user_agent(self):
        """Headers should include User-Agent"""
        from app.utils.api_client import ProviderAPIClient
        
        client = ProviderAPIClient(provider_name="test")
        headers = client._prepare_headers()
        
        assert "User-Agent" in headers
        assert len(headers["User-Agent"]) > 10  # Should be a real UA string
    
    def test_prepare_headers_preserves_custom_headers(self):
        """Custom headers should be preserved"""
        from app.utils.api_client import ProviderAPIClient
        
        client = ProviderAPIClient(provider_name="test")
        custom = {"X-Custom": "value", "Authorization": "Bearer token"}
        headers = client._prepare_headers(custom)
        
        assert headers["X-Custom"] == "value"
        assert headers["Authorization"] == "Bearer token"
        assert "User-Agent" in headers


class TestRobustHTTPClient:
    """Test RobustHTTPClient functionality"""
    
    def test_client_initialization(self):
        """Client should initialize with defaults"""
        from app.utils.http_utils import RobustHTTPClient
        
        client = RobustHTTPClient()
        
        assert client.timeout == 10
        assert client.max_retries == 3
    
    def test_safe_json_parse_valid_json(self):
        """Should parse valid JSON correctly"""
        from app.utils.http_utils import RobustHTTPClient
        
        client = RobustHTTPClient()
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "application/json"}
        mock_response.text = '{"key": "value", "number": 42}'
        mock_response.json.return_value = {"key": "value", "number": 42}
        
        result = client.safe_json_parse(mock_response, "test context")
        
        assert result == {"key": "value", "number": 42}
    
    def test_safe_json_parse_empty_response(self):
        """Should handle empty response gracefully"""
        from app.utils.http_utils import RobustHTTPClient
        
        client = RobustHTTPClient()
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "application/json"}
        mock_response.text = ""
        
        result = client.safe_json_parse(mock_response, "test context")
        
        assert result is None
    
    def test_safe_json_parse_html_response(self):
        """Should detect HTML error pages"""
        from app.utils.http_utils import RobustHTTPClient
        
        client = RobustHTTPClient()
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "text/html"}
        mock_response.text = "<html><body>Error</body></html>"
        
        result = client.safe_json_parse(mock_response, "test context")
        
        assert result is None


class TestCredentialsLoader:
    """Test credentials loading functionality"""
    
    def test_get_provider_credentials_returns_dict(self):
        """Should return a dict for any provider"""
        from app.utils.credentials import get_provider_credentials
        
        result = get_provider_credentials("nonexistent_provider")
        
        assert isinstance(result, dict)
    
    def test_load_credentials_handles_missing_file(self):
        """Should handle missing credentials file gracefully"""
        from app.utils.credentials import load_credentials
        
        # Should not raise an exception
        result = load_credentials()
        
        assert isinstance(result, dict)


class TestUserAgentRotation:
    """Test User-Agent rotation functionality"""
    
    def test_get_random_windows_ua_returns_string(self):
        """Should return a non-empty User-Agent string"""
        from app.utils.user_agent import get_random_windows_ua
        
        ua = get_random_windows_ua()
        
        assert isinstance(ua, str)
        assert len(ua) > 20
        assert "Mozilla" in ua or "Windows" in ua
    
    def test_get_random_windows_ua_varies(self):
        """Should return different UAs on multiple calls"""
        from app.utils.user_agent import get_random_windows_ua
        
        uas = set()
        for _ in range(10):
            uas.add(get_random_windows_ua())
        
        # Should have at least 2 different UAs in 10 calls
        assert len(uas) >= 2


class TestProgramsLoader:
    """Test programs.json loading functionality"""
    
    def test_get_programs_for_provider_returns_dict(self):
        """Should return a dict for any provider"""
        from app.utils.programs_loader import get_programs_for_provider
        
        result = get_programs_for_provider("6play")
        
        # Returns dict keyed by show ID
        assert isinstance(result, dict)
    
    def test_get_programs_for_provider_has_shows(self):
        """Known providers should have shows"""
        from app.utils.programs_loader import get_programs_for_provider
        
        sixplay_programs = get_programs_for_provider("6play")
        cbc_programs = get_programs_for_provider("cbc")
        
        # Each provider should have some programs
        assert len(sixplay_programs) > 0
        assert len(cbc_programs) > 0


class TestTypeDefs:
    """Test TypedDict definitions"""
    
    def test_typedicts_importable(self):
        """TypedDicts should be importable"""
        from app.schemas.type_defs import StreamInfo, EpisodeInfo, ShowInfo, ProviderConfig
        
        # Should not raise ImportError
        assert StreamInfo is not None
        assert EpisodeInfo is not None
        assert ShowInfo is not None
        assert ProviderConfig is not None
    
    def test_streaminfo_accepts_valid_data(self):
        """StreamInfo should accept valid stream data"""
        from app.schemas.type_defs import StreamInfo
        
        # TypedDicts are just type hints, so we can create dicts
        stream: StreamInfo = {
            "url": "https://example.com/stream.m3u8",
            "manifest_type": "hls",
            "title": "Test Stream"
        }
        
        assert stream["url"] == "https://example.com/stream.m3u8"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
