"""Tests for the unified ProviderAPIClient."""
from unittest.mock import patch, MagicMock


def test_provider_api_client_has_session_and_json_parse():
    """ProviderAPIClient should own its session and expose safe_json_parse."""
    from app.utils.api_client import ProviderAPIClient
    client = ProviderAPIClient("test")
    assert client.session is not None
    assert callable(client.safe_json_parse)


def test_api_client_has_raw_request():
    from app.utils.api_client import ProviderAPIClient
    client = ProviderAPIClient("test")
    assert callable(client.raw_request)


def test_transport_adapter_performs_no_retries():
    """Retries are owned by safe_request's loop — the adapter must do none.

    (Previously the urllib3 Retry adapter and the manual loop stacked,
    producing up to 3 × 3 network attempts per request.)
    """
    from app.utils.api_client import ProviderAPIClient
    client = ProviderAPIClient("test", max_retries=3)
    adapter = client.session.get_adapter("https://example.com")
    assert adapter.max_retries.total == 0


def test_safe_request_retries_then_gives_up():
    """safe_request makes exactly max_retries attempts on persistent failure."""
    import requests
    from app.utils.api_client import ProviderAPIClient

    client = ProviderAPIClient("test", max_retries=2)
    client.session = MagicMock()
    client.session.get.side_effect = requests.exceptions.ConnectionError("boom")

    with patch("app.utils.api_client.time.sleep"):
        result = client.safe_request("GET", "https://example.com/api")

    assert result is None
    assert client.session.get.call_count == 2
