"""Tests for Phase 2 BaseProvider utilities."""
import pytest

class TestDetectManifestType:
    def test_m3u8(self):
        from app.providers.base_provider import BaseProvider
        assert BaseProvider._detect_manifest_type("https://x.com/stream.m3u8") == "hls"

    def test_mpd(self):
        from app.providers.base_provider import BaseProvider
        assert BaseProvider._detect_manifest_type("https://x.com/stream.mpd") == "mpd"

    def test_hls_in_url(self):
        from app.providers.base_provider import BaseProvider
        assert BaseProvider._detect_manifest_type("https://x.com/hls/master") == "hls"

    def test_dash_in_url(self):
        from app.providers.base_provider import BaseProvider
        assert BaseProvider._detect_manifest_type("https://x.com/dash/manifest") == "mpd"

    def test_ism(self):
        from app.providers.base_provider import BaseProvider
        assert BaseProvider._detect_manifest_type("https://x.com/stream.ism") == "ism"

    def test_default_hls(self):
        from app.providers.base_provider import BaseProvider
        assert BaseProvider._detect_manifest_type("https://x.com/unknown") == "hls"

    def test_none_url(self):
        from app.providers.base_provider import BaseProvider
        assert BaseProvider._detect_manifest_type(None) == "hls"


class TestIdParsing:
    def _make_provider(self):
        """Create a minimal concrete provider for testing."""
        from app.providers.base_provider import BaseProvider
        class Stub(BaseProvider):
            provider_name = "test"
            episode_marker = "episode:"
            def get_programs(self): return []
            def get_episodes(self, _): return []
            def get_episode_stream_url(self, _): return None
        return Stub()

    def test_extract_slug(self):
        p = self._make_provider()
        assert p._extract_slug("cutam:fr:mytf1:sept-a-huit") == "sept-a-huit"

    def test_extract_slug_simple(self):
        p = self._make_provider()
        assert p._extract_slug("simple-id") == "simple-id"

    def test_extract_after_marker(self):
        p = self._make_provider()
        assert p._extract_after_marker("cutam:fr:mytf1:episode:V_123") == "V_123"

    def test_extract_after_marker_no_marker(self):
        p = self._make_provider()
        assert p._extract_after_marker("no-marker-here") == "no-marker-here"

    def test_extract_after_marker_custom(self):
        p = self._make_provider()
        assert p._extract_after_marker("prefix:6play:slug", marker="6play:") == "slug"
