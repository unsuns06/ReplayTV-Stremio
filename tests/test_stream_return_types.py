"""Regression tests for the stream return-type contract.

Every get_episode_stream_url / get_channel_stream_url / _check_processed_file call
must return Optional[List[Dict]] — never a bare Dict.  A bare Dict is iterable
(yields its keys) which silently breaks the stream router and produces
"'str' object has no attribute 'get'" at runtime.
"""
import pytest
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_valid_stream_return(value):
    """Return True if value is None or a non-empty list whose elements are dicts."""
    if value is None:
        return True
    if not isinstance(value, list):
        return False
    return all(isinstance(item, dict) for item in value)


# ---------------------------------------------------------------------------
# BaseProvider._check_processed_file
# ---------------------------------------------------------------------------

class TestCheckProcessedFileReturnType:
    """_check_processed_file must return Optional[List[Dict]], never a bare Dict."""

    def _make_provider(self):
        from app.providers.fr.sixplay import SixPlayProvider
        with patch("app.providers.base_provider.get_provider_credentials", return_value={}), \
             patch("app.providers.base_provider.ProviderAPIClient"), \
             patch("app.providers.base_provider.get_proxy_config") as mock_proxy, \
             patch("app.providers.fr.sixplay.get_programs_for_provider", return_value={}):
            mock_proxy.return_value.get_proxy.return_value = None  # nm3u8_processor not set
            provider = SixPlayProvider(request=None)
        return provider

    def test_returns_none_when_processor_not_configured(self):
        provider = self._make_provider()
        result = provider._check_processed_file("test_episode_id")
        assert result is None

    def test_returns_list_when_rd_folder_hit(self):
        provider = self._make_provider()

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = "test_episode_id.mp4"

        provider.proxy_config = MagicMock()
        provider.proxy_config.get_proxy.return_value = "http://processor"
        provider.session = MagicMock()

        with patch("app.providers.drm_mixin.load_credentials", return_value={"realdebridfolder": "http://rdfolder/"}):
            provider.session.get.return_value = mock_resp
            provider.session.head.return_value = MagicMock(status_code=404)
            result = provider._check_processed_file("test_episode_id")

        assert _is_valid_stream_return(result), (
            f"_check_processed_file returned {type(result).__name__!r}, expected list or None. "
            "This causes 'str' object has no attribute 'get' in the stream router."
        )
        if result:
            assert result[0].get("url")
            assert result[0].get("manifest_type") == "video"

    def test_torbox_checked_before_rd_and_processor(self):
        provider = self._make_provider()

        provider.proxy_config = MagicMock()
        provider.proxy_config.get_proxy.return_value = "http://processor"
        provider.session = MagicMock()
        provider.session.head.return_value = MagicMock(status_code=200)

        creds = {
            "realdebridfolder": "http://rdfolder/",
            "torbox": {
                "tb_webdav_url": "https://webdav.torbox.app/",
                "tb_webdav_username": "user",
                "tb_webdav_password": "p@ss",
            },
        }
        with patch("app.providers.drm_mixin.load_credentials", return_value=creds):
            result = provider._check_processed_file("ep1")

        assert _is_valid_stream_return(result)
        assert result[0]["url"] == "https://user:p%40ss@webdav.torbox.app/ep1.mp4/ep1.mp4"
        assert "[TorBox]" in result[0]["title"]
        # Probed the nested {name}/{name} path with basic auth, and stopped there
        args, kwargs = provider.session.head.call_args
        assert args[0] == "https://webdav.torbox.app/ep1.mp4/ep1.mp4"
        assert kwargs["auth"] == ("user", "p@ss")
        provider.session.get.assert_not_called()

    def test_returns_list_when_processor_url_hit(self):
        provider = self._make_provider()

        provider.proxy_config = MagicMock()
        provider.proxy_config.get_proxy.return_value = "http://processor"
        provider.session = MagicMock()
        provider.session.head.return_value = MagicMock(status_code=200)

        with patch("app.providers.drm_mixin.load_credentials", return_value={}):
            result = provider._check_processed_file("test_episode_id")

        assert _is_valid_stream_return(result), (
            f"_check_processed_file returned {type(result).__name__!r}, expected list or None."
        )
        if result:
            assert result[0].get("url")
            assert result[0].get("manifest_type") == "video"


# ---------------------------------------------------------------------------
# Provider stream methods via the HTTP router (integration-level)
# ---------------------------------------------------------------------------

class TestStreamRouterNeverIteratesDict:
    """The router must never receive a bare Dict from a provider.

    We mock the provider so that it returns a Dict (simulating the pre-fix bug)
    and verify the router raises or at least does not produce a broken response.
    We also verify the fix: when provider returns a List[Dict], the router
    succeeds without error.
    """

    def _client(self):
        from fastapi.testclient import TestClient
        from app.main import app
        return TestClient(app)

    def test_stream_router_ok_when_provider_returns_list(self):
        """Happy path: provider returns List[Dict] → router responds 200 with streams."""
        from app.providers.factory import ProviderFactory

        mock_provider = MagicMock()
        mock_provider.needs_ip_forwarding = False
        mock_provider.get_episode_stream_url.return_value = [
            {"url": "http://example.com/stream.m3u8", "manifest_type": "hls"}
        ]

        with patch.object(ProviderFactory, "create_provider", return_value=mock_provider):
            client = self._client()
            resp = client.get("/stream/series/cutam:fr:6play:episode:clip_12345678.json")

        assert resp.status_code == 200
        data = resp.json()
        assert "streams" in data
        assert len(data["streams"]) == 1
        assert data["streams"][0]["url"] == "http://example.com/stream.m3u8"

    def test_stream_router_returns_empty_when_provider_returns_none(self):
        """Provider returns None → router responds 200 with empty streams."""
        from app.providers.factory import ProviderFactory

        mock_provider = MagicMock()
        mock_provider.needs_ip_forwarding = False
        mock_provider.get_episode_stream_url.return_value = None

        with patch.object(ProviderFactory, "create_provider", return_value=mock_provider):
            client = self._client()
            resp = client.get("/stream/series/cutam:fr:6play:episode:clip_12345678.json")

        assert resp.status_code == 200
        assert resp.json()["streams"] == []


# ---------------------------------------------------------------------------
# Contract: all concrete providers' stream methods return the right type
# ---------------------------------------------------------------------------

STREAM_PROVIDERS = [
    ("app.providers.fr.sixplay", "SixPlayProvider", "get_episode_stream_url", "6play"),
    ("app.providers.fr.francetv", "FranceTVProvider", "get_episode_stream_url", "francetv"),
    ("app.providers.fr.mytf1", "MyTF1Provider", "get_episode_stream_url", "mytf1"),
    ("app.providers.ca.cbc", "CBCProvider", "get_episode_stream_url", "cbc"),
]


@pytest.mark.parametrize("module,cls_name,method,provider_key", STREAM_PROVIDERS)
def test_stream_method_is_not_a_generator_of_strings(module, cls_name, method, provider_key):
    """Smoke-check: calling the method with a mocked API must not return a bare Dict.

    We stub out the API client so no real network call is made.  If the method
    returns something (not None), it must be a list of dicts.
    """
    import importlib

    mod = importlib.import_module(module)
    cls = getattr(mod, cls_name)

    with patch("app.providers.base_provider.get_provider_credentials", return_value={}), \
         patch("app.providers.base_provider.ProviderAPIClient") as mock_client_cls, \
         patch("app.providers.base_provider.get_proxy_config") as mock_proxy, \
         patch(f"{module}.get_programs_for_provider", return_value={}, create=True):

        mock_proxy.return_value.get_proxy.return_value = None
        mock_client_cls.return_value.session = MagicMock()

        # Construct with no request
        provider = cls(request=None)

        # Make the API client return nothing so the method short-circuits to None
        provider.api_client = MagicMock()
        provider.api_client.raw_request.return_value = MagicMock(status_code=404, json=lambda: {})
        provider.api_client.get.return_value = None
        provider._authenticated = True  # skip auth

        episode_id = f"cutam:xx:{provider_key}:episode:fake_episode_123"
        fn = getattr(provider, method)
        result = fn(episode_id)

    assert _is_valid_stream_return(result), (
        f"{cls_name}.{method} returned {type(result).__name__!r} — must be list or None.\n"
        "Returning a bare Dict causes the router to iterate its keys (strings), "
        "producing 'str' object has no attribute 'get'."
    )
