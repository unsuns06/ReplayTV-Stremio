import os
import time
from urllib.parse import urlparse, parse_qs

import pytest
import requests
from unittest.mock import patch

from app.providers.fr.sixplay import SixPlayProvider

MEDIAFLOW_BASE = os.environ.get("MEDIAFLOW_TEST_URL", "http://localhost:8888")
MEDIAFLOW_PASSWORD = os.environ.get("MEDIAFLOW_TEST_PASSWORD", "your_password")


@pytest.fixture(scope="session", autouse=True)
def ensure_mediaflow_running():
    tries = 0
    last_error = None
    while tries < 20:
        tries += 1
        try:
            response = requests.get(f"{MEDIAFLOW_BASE}/health", timeout=2)
            if response.status_code == 200 and response.json().get("status") == "healthy":
                return
        except Exception as exc:  # pragma: no cover - purely diagnostic
            last_error = exc
        time.sleep(0.5)
    pytest.skip(f"MediaFlow proxy not reachable at {MEDIAFLOW_BASE}: {last_error}")


def test_mediaflow_health_ok():
    response = requests.get(f"{MEDIAFLOW_BASE}/health", timeout=2)
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_mediaflow_proxies_public_mpd(tmp_path):
    params = {
        "d": "https://storage.googleapis.com/shaka-demo-assets/angel-one/dash.mpd",
        "api_password": MEDIAFLOW_PASSWORD,
    }
    response = requests.get(
        f"{MEDIAFLOW_BASE}/proxy/mpd/manifest.m3u8",
        params=params,
        timeout=10,
    )
    assert response.status_code == 200
    output = response.text
    assert output.startswith("#EXTM3U")
    assert "#EXT-X-STREAM-INF" in output


@pytest.fixture
def sixplay_provider():
    with patch(
        "app.providers.fr.sixplay.get_provider_credentials",
        side_effect=lambda name: {"url": MEDIAFLOW_BASE, "password": MEDIAFLOW_PASSWORD} if name == "mediaflow" else {},
    ), patch(
        "app.providers.fr.sixplay.get_processed_mpd_url_for_mediaflow",
        return_value="http://127.0.0.1/processed.mpd",
    ):
        provider = SixPlayProvider()
        provider.mediaflow_url = MEDIAFLOW_BASE
        provider.mediaflow_password = MEDIAFLOW_PASSWORD
        provider.login_token = "mock-login-token"
        yield provider


def test_build_mediaflow_clearkey_stream_includes_query(sixplay_provider):
    base_headers = {"User-Agent": "pytest-agent"}
    key_id_hex = "1d83a873b4d34f77b5f68424a0efc8c1"
    key_hex = "000102030405060708090a0b0c0d0e0f"

    stream_info = sixplay_provider._build_mediaflow_clearkey_stream(
        original_mpd_url="https://example.com/original.mpd",
        base_headers=base_headers,
        key_id_hex=key_id_hex,
        key_hex=key_hex,
        is_live=True,
    )

    assert stream_info is not None
    parsed = urlparse(stream_info["url"])
    query = parse_qs(parsed.query)
    assert query.get("key_id")
    assert query.get("key")
    assert query["key_id"][0] != key_id_hex  # should be base64 url encoded
    assert "externalUrl" in stream_info and stream_info["externalUrl"] == "https://example.com/original.mpd"
    assert stream_info["is_live"] is True


def test_normalize_decryption_key_variants(sixplay_provider):
    json_payload = (
        '{"keys": [{"kid": "1d83a873b4d34f77b5f68424a0efc8c1", "k": "AAECAwQFBgcICQoLDA0ODw"}]}'
    )
    normalized = sixplay_provider._normalize_decryption_key(
        json_payload,
        "1d83a873b4d34f77b5f68424a0efc8c1",
    )
    assert normalized == "000102030405060708090a0b0c0d0e0f"

    colon_payload = "1d83a873-b4d3-4f77-b5f6-8424a0efc8c1:000102030405060708090a0b0c0d0e0f"
    normalized2 = sixplay_provider._normalize_decryption_key(
        colon_payload,
        "1d83a873b4d34f77b5f68424a0efc8c1",
    )
    assert normalized2 == "000102030405060708090a0b0c0d0e0f"

