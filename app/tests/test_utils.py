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


class TestDRMConsolidation:
    """Fix 3: DRM processors share a common ABC and are importable from drm package."""

    def test_base_drm_processor_is_abstract(self):
        """DRMProcessor cannot be instantiated directly."""
        from app.utils.drm.base import DRMProcessor
        import pytest
        with pytest.raises(TypeError):
            DRMProcessor()

    def test_simple_drm_processor_extends_base(self):
        """SimpleDRMProcessor must be a DRMProcessor."""
        from app.utils.drm.base import DRMProcessor
        from app.utils.drm.nm3u8_drm_processor import SimpleDRMProcessor
        assert issubclass(SimpleDRMProcessor, DRMProcessor)

    def test_sixplay_mpd_processor_extends_base(self):
        """SixPlayMPDProcessor must be a DRMProcessor."""
        from app.utils.drm.base import DRMProcessor
        from app.utils.drm.sixplay_mpd_processor import SixPlayMPDProcessor
        assert issubclass(SixPlayMPDProcessor, DRMProcessor)

    def test_direct_mpd_processor_extends_base(self):
        """DirectMPDProcessor must be a DRMProcessor."""
        from app.utils.drm.base import DRMProcessor
        from app.utils.drm.direct_mpd_processor import DirectMPDProcessor
        assert issubclass(DirectMPDProcessor, DRMProcessor)

    def test_drm_package_exports_all_symbols(self):
        """drm/__init__.py should export every public symbol."""
        import app.utils.drm as drm_pkg
        for name in [
            'DRMProcessor',
            'SimpleDRMProcessor', 'process_drm_simple',
            'SixPlayMPDProcessor', 'create_mediaflow_compatible_mpd', 'extract_drm_info_from_mpd',
            'DirectMPDProcessor', 'get_processed_mpd_content',
            'extract_pssh_from_mpd', 'extract_widevine_key', 'build_mediaflow_clearkey_stream',
        ]:
            assert hasattr(drm_pkg, name), f"drm package missing export: {name}"

    def test_backward_compat_stubs_importable(self):
        """Old import paths must still work after consolidation."""
        from app.utils.nm3u8_drm_processor import SimpleDRMProcessor, process_drm_simple
        from app.utils.sixplay_mpd_processor import (
            SixPlayMPDProcessor,
            create_mediaflow_compatible_mpd,
            extract_drm_info_from_mpd,
        )
        from app.utils.direct_mpd_processor import DirectMPDProcessor, get_processed_mpd_content

        assert SimpleDRMProcessor is not None
        assert process_drm_simple is not None
        assert SixPlayMPDProcessor is not None
        assert create_mediaflow_compatible_mpd is not None
        assert extract_drm_info_from_mpd is not None
        assert DirectMPDProcessor is not None
        assert get_processed_mpd_content is not None

    def test_sixplay_mpd_processor_rewrites_mpd(self):
        """SixPlayMPDProcessor should return a non-empty string for a minimal MPD."""
        from app.utils.drm.sixplay_mpd_processor import SixPlayMPDProcessor

        minimal_mpd = (
            '<?xml version="1.0"?>'
            '<MPD xmlns="urn:mpeg:dash:schema:mpd:2011">'
            '<Period><AdaptationSet>'
            '<ContentProtection schemeIdUri="urn:mpeg:dash:mp4protection:2011" value="cenc"/>'
            '</AdaptationSet></Period>'
            '</MPD>'
        )
        result = SixPlayMPDProcessor().process_mpd_for_mediaflow(minimal_mpd, 'https://example.com/manifest.mpd')
        assert isinstance(result, str)
        assert len(result) > 0

    def test_extract_drm_info_from_mpd_returns_dict(self):
        """extract_drm_info_from_mpd should return a dict for any input."""
        from app.utils.drm.sixplay_mpd_processor import extract_drm_info_from_mpd

        result = extract_drm_info_from_mpd('<MPD/>')
        assert isinstance(result, dict)

    def test_simple_drm_processor_requires_key(self):
        """process_drm_content should fail gracefully when no key is supplied."""
        from unittest.mock import patch
        from app.utils.drm.nm3u8_drm_processor import SimpleDRMProcessor

        with patch('app.utils.drm.nm3u8_drm_processor.get_proxy_config') as mock_cfg:
            mock_cfg.return_value.get_proxy.return_value = 'http://localhost:9000'
            processor = SimpleDRMProcessor()
            result = processor.process_drm_content(url='https://example.com/video.mpd', save_name='test')
        assert result['success'] is False
        assert 'key' in result['error'].lower()


class TestMetadataCaching:
    """Fix 2: get_programs and get_episodes results are cached between requests."""

    def test_cache_stores_and_retrieves_programs(self):
        """Programs should be retrievable from cache after being set."""
        from app.utils.cache import InMemoryCache

        c = InMemoryCache(max_size=10)
        programs = [{'id': 'show1', 'name': 'My Show'}]
        c.set('programs:francetv', programs, ttl=600)
        assert c.get('programs:francetv') == programs

    def test_cache_returns_none_for_missing_key(self):
        """Cache should return None for keys that were never set."""
        from app.utils.cache import InMemoryCache

        c = InMemoryCache(max_size=10)
        assert c.get('programs:nonexistent') is None

    def test_cache_expires_entries(self):
        """Cache should not return entries after their TTL has elapsed."""
        import time
        from app.utils.cache import InMemoryCache

        c = InMemoryCache(max_size=10)
        c.set('episodes:cutam:fr:francetv:show1', ['ep1'], ttl=1)
        time.sleep(1.1)
        assert c.get('episodes:cutam:fr:francetv:show1') is None

    def test_catalog_endpoint_caches_programs(self):
        """Second catalog request should be served from cache (get_programs called once)."""
        from unittest.mock import patch, MagicMock
        from fastapi.testclient import TestClient
        from app.main import app
        from app.utils.cache import cache

        cache.delete('programs:francetv')
        mock_shows = [{'id': 'cutam:fr:francetv:show1', 'type': 'series', 'name': 'Test Show'}]

        with patch('app.routers.catalog.ProviderFactory.create_provider') as mock_factory:
            mock_provider = MagicMock()
            mock_provider.get_programs.return_value = mock_shows
            mock_factory.return_value = mock_provider

            client = TestClient(app)
            # Use the real catalog ID from the registry (fr-francetv-replay)
            client.get('/catalog/series/fr-francetv-replay.json')
            client.get('/catalog/series/fr-francetv-replay.json')

            # Provider should only be asked for programs once; second hit served from cache
            assert mock_provider.get_programs.call_count == 1

        cache.delete('programs:francetv')

    def test_meta_endpoint_caches_episodes(self):
        """Second meta request for the same series should not call get_episodes again."""
        from unittest.mock import patch, MagicMock
        from fastapi.testclient import TestClient
        from app.main import app
        from app.utils.cache import cache

        series_id = 'cutam:fr:francetv:testshow'
        cache.delete(f'episodes:{series_id}')

        mock_episodes = [{'id': f'{series_id}:s01e01', 'title': 'Ep 1'}]

        with patch('app.routers.meta.ProviderFactory.create_provider') as mock_factory, \
             patch('app.routers.meta.get_programs_for_provider') as mock_programs:
            mock_provider = MagicMock()
            mock_provider.get_episodes.return_value = mock_episodes
            mock_factory.return_value = mock_provider
            mock_programs.return_value = {
                'testshow': {
                    'name': 'Test Show',
                    'description': '',
                    'logo': '',
                    'poster': '',
                    'background': '',
                    'channel': '',
                    'genres': [],
                    'year': 2024,
                    'rating': 'Tous publics',
                }
            }

            client = TestClient(app)
            client.get(f'/meta/series/{series_id}.json')
            client.get(f'/meta/series/{series_id}.json')

            assert mock_provider.get_episodes.call_count == 1

        cache.delete(f'episodes:{series_id}')


class TestLogLevelWiring:
    """Fix 1: LOG_LEVEL env var is respected by both Uvicorn and Python logging."""

    def test_run_server_passes_log_level_variable(self):
        """run_server.py source must not hard-code the log level string."""
        import ast
        import pathlib

        source = pathlib.Path('run_server.py').read_text(encoding='utf-8')
        tree = ast.parse(source)

        for node in ast.walk(tree):
            if isinstance(node, ast.keyword) and node.arg == 'log_level':
                # The value must NOT be a string literal "debug"
                assert not (
                    isinstance(node.value, ast.Constant) and node.value.value == 'debug'
                ), "run_server.py still hard-codes log_level='debug'"

    def test_main_log_level_reads_env_var(self):
        """app/main.py should derive the logging level from the LOG_LEVEL env var."""
        import importlib
        import logging
        import os
        from unittest.mock import patch

        with patch.dict(os.environ, {'LOG_LEVEL': 'warning'}):
            # Re-evaluate only the level-resolution logic, not the whole module
            import app.main as main_mod
            importlib.reload(main_mod)
            assert main_mod._LOG_LEVEL == logging.WARNING

        # Restore default
        importlib.reload(main_mod)

    def test_main_defaults_to_info_when_env_unset(self):
        """Without LOG_LEVEL env var the Python log level should default to INFO."""
        import importlib
        import logging
        import os
        from unittest.mock import patch

        env = {k: v for k, v in os.environ.items() if k != 'LOG_LEVEL'}
        with patch.dict(os.environ, env, clear=True):
            import app.main as main_mod
            importlib.reload(main_mod)
            assert main_mod._LOG_LEVEL == logging.INFO

        importlib.reload(main_mod)


class TestMetadataMovedToProvidersFr:
    """Fix 11: metadata.py moved to providers/fr/; old path still importable via re-export stub."""

    def test_new_canonical_path_importable(self):
        from app.providers.fr.metadata import FranceTVMetadataProcessor, metadata_processor
        assert FranceTVMetadataProcessor is not None
        assert metadata_processor is not None

    def test_legacy_path_still_importable(self):
        from app.utils.metadata import FranceTVMetadataProcessor, metadata_processor
        assert FranceTVMetadataProcessor is not None

    def test_both_paths_resolve_to_same_class(self):
        from app.providers.fr.metadata import FranceTVMetadataProcessor as A
        from app.utils.metadata import FranceTVMetadataProcessor as B
        assert A is B

    def test_francetv_imports_from_canonical_path(self):
        import pathlib
        src = pathlib.Path("app/providers/fr/francetv.py").read_text(encoding='utf-8')
        assert "from app.providers.fr.metadata import" in src

    def test_sixplay_imports_from_canonical_path(self):
        import pathlib
        src = pathlib.Path("app/providers/fr/sixplay.py").read_text(encoding='utf-8')
        assert "from app.providers.fr.metadata import" in src


class TestDocstrings:
    """Fix 12: key utility functions have docstrings."""

    def _has_docstring(self, func) -> bool:
        return bool(func.__doc__ and func.__doc__.strip())

    def test_proxy_config_load_proxies_has_docstring(self):
        from app.utils.proxy_config import ProxyConfig
        assert self._has_docstring(ProxyConfig.load_proxies)

    def test_proxy_config_get_proxy_has_docstring(self):
        from app.utils.proxy_config import ProxyConfig
        assert self._has_docstring(ProxyConfig.get_proxy)

    def test_proxy_config_get_instance_has_docstring(self):
        from app.utils.proxy_config import ProxyConfig
        assert self._has_docstring(ProxyConfig.get_instance)

    def test_get_proxy_config_has_docstring(self):
        from app.utils.proxy_config import get_proxy_config
        assert self._has_docstring(get_proxy_config)

    def test_cache_init_has_docstring(self):
        from app.utils.cache import InMemoryCache
        assert self._has_docstring(InMemoryCache.__init__)

    def test_cache_stats_has_docstring(self):
        from app.utils.cache import InMemoryCache
        assert self._has_docstring(InMemoryCache.stats)


class TestProgramsJsonValidation:
    """Fix 13: programs.json structure is validated on load."""

    def test_valid_data_produces_no_warnings(self):
        from app.utils.programs_loader import _validate_programs_data
        data = {
            "version": "1.0",
            "shows": [
                {"provider": "francetv", "slug": "cash-investigation", "name": "Cash Investigation",
                 "enabled": True, "genres": ["Documentary"], "year": 2024}
            ]
        }
        assert _validate_programs_data(data) == []

    def test_missing_version_produces_warning(self):
        from app.utils.programs_loader import _validate_programs_data
        warns = _validate_programs_data({"shows": []})
        assert any("version" in w for w in warns)

    def test_missing_shows_produces_warning(self):
        from app.utils.programs_loader import _validate_programs_data
        warns = _validate_programs_data({"version": "1.0"})
        assert any("shows" in w for w in warns)

    def test_unknown_provider_produces_warning(self):
        from app.utils.programs_loader import _validate_programs_data
        warns = _validate_programs_data({
            "version": "1.0",
            "shows": [{"provider": "unknown_tv", "slug": "show", "name": "Show", "enabled": True}]
        })
        assert any("unknown provider" in w for w in warns)

    def test_missing_required_field_produces_warning(self):
        from app.utils.programs_loader import _validate_programs_data
        warns = _validate_programs_data({
            "version": "1.0",
            "shows": [{"provider": "francetv", "name": "Show"}]   # slug missing
        })
        assert any("slug" in w for w in warns)

    def test_wrong_type_year_produces_warning(self):
        from app.utils.programs_loader import _validate_programs_data
        warns = _validate_programs_data({
            "version": "1.0",
            "shows": [{"provider": "francetv", "slug": "s", "name": "N", "enabled": True, "year": "2024"}]
        })
        assert any("year" in w for w in warns)

    def test_non_list_shows_produces_warning(self):
        from app.utils.programs_loader import _validate_programs_data
        warns = _validate_programs_data({"version": "1.0", "shows": "not-a-list"})
        assert any("array" in w for w in warns)

    def test_warnings_are_logged_on_load(self):
        """Validation warnings must be printed to safe_print during file load."""
        from app.utils.programs_loader import _load_programs
        from app.utils.cache import cache
        cache.delete("programs_data")

        bad_data = {"version": 999, "shows": [{"provider": "bad_tv", "slug": "s", "name": "N"}]}
        with patch('builtins.open', create=True) as mock_open, \
             patch('json.load', return_value=bad_data), \
             patch('app.utils.programs_loader.safe_print') as mock_sp:
            mock_open.return_value.__enter__ = lambda s: s
            mock_open.return_value.__exit__ = MagicMock(return_value=False)
            mock_open.return_value.read = MagicMock(return_value='')
            try:
                _load_programs()
            except Exception:
                pass
            warning_calls = [str(c) for c in mock_sp.call_args_list if "validation" in str(c).lower()]
            assert len(warning_calls) > 0, "Expected validation warnings to be printed"

        cache.delete("programs_data")


class TestCacheHitMissLogging:
    """Fix 15: InMemoryCache tracks and reports hit/miss statistics."""

    def test_stats_start_at_zero(self):
        from app.utils.cache import InMemoryCache
        c = InMemoryCache(max_size=10)
        s = c.stats()
        assert s["hits"] == 0
        assert s["misses"] == 0
        assert s["hit_rate"] == "n/a"

    def test_miss_increments_counter(self):
        from app.utils.cache import InMemoryCache
        c = InMemoryCache(max_size=10)
        c.get("nonexistent")
        assert c.stats()["misses"] == 1
        assert c.stats()["hits"] == 0

    def test_hit_increments_counter(self):
        from app.utils.cache import InMemoryCache
        c = InMemoryCache(max_size=10)
        c.set("k", "v", ttl=60)
        c.get("k")
        assert c.stats()["hits"] == 1
        assert c.stats()["misses"] == 0

    def test_expired_entry_counts_as_miss(self):
        import time
        from app.utils.cache import InMemoryCache
        c = InMemoryCache(max_size=10)
        c.set("k", "v", ttl=1)
        time.sleep(1.1)
        c.get("k")
        assert c.stats()["misses"] == 1

    def test_hit_rate_calculation(self):
        from app.utils.cache import InMemoryCache
        c = InMemoryCache(max_size=10)
        c.set("k", "v", ttl=60)
        c.get("k")        # hit
        c.get("k")        # hit
        c.get("missing")  # miss
        s = c.stats()
        assert s["hits"] == 2
        assert s["misses"] == 1
        assert s["hit_rate"] == "66.7%"

    def test_stats_size_reflects_entries(self):
        from app.utils.cache import InMemoryCache
        c = InMemoryCache(max_size=10)
        c.set("a", 1, ttl=60)
        c.set("b", 2, ttl=60)
        assert c.stats()["size"] == 2

    def test_health_endpoint_includes_cache_stats(self):
        from fastapi.testclient import TestClient
        from app.main import app
        data = TestClient(app).get("/health").json()
        assert "cache" in data
        for field in ("hits", "misses", "hit_rate", "size"):
            assert field in data["cache"], f"Missing cache field: {field}"


class TestConfigureEndpoint:
    """Fix 14: configure endpoint returns HTML with provider status."""

    def test_configure_returns_200(self):
        from fastapi.testclient import TestClient
        from app.main import app
        r = TestClient(app).get("/configure")
        assert r.status_code == 200

    def test_configure_returns_html(self):
        from fastapi.testclient import TestClient
        from app.main import app
        r = TestClient(app).get("/configure")
        assert "text/html" in r.headers.get("content-type", "")

    def test_configure_mentions_all_providers(self):
        from fastapi.testclient import TestClient
        from app.main import app
        body = TestClient(app).get("/configure").text
        for name in ("France TV", "TF1+", "CBC"):
            assert name in body, f"Provider name missing from configure page: {name}"

    def test_configure_status_endpoint_returns_json(self):
        from fastapi.testclient import TestClient
        from app.main import app
        data = TestClient(app).get("/configure/status").json()
        assert "all_configured" in data
        assert "providers" in data
        assert isinstance(data["providers"], dict)

    def test_configure_status_lists_known_providers(self):
        from fastapi.testclient import TestClient
        from app.main import app
        data = TestClient(app).get("/configure/status").json()
        for key in ("francetv", "mytf1", "6play", "cbc"):
            assert key in data["providers"], f"Missing provider in status: {key}"

    def test_configure_page_contains_env_var_instructions(self):
        from fastapi.testclient import TestClient
        from app.main import app
        body = TestClient(app).get("/configure").text
        assert "CREDENTIALS_JSON" in body


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
