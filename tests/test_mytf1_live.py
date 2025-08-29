import pytest
import requests_mock
import json
from unittest import mock
from app.providers.fr.mytf1 import MyTF1Provider
from app.utils.credentials import get_provider_credentials

# Mock credentials for testing
MOCK_CREDENTIALS = {
    "mytf1": {
        "login": "test@example.com",
        "password": "testpassword"
    }
}

@pytest.fixture
def mytf1_provider():
    """Fixture to provide a MyTF1Provider instance with mocked credentials."""
    # Patch get_provider_credentials to return mock credentials
    with requests_mock.Mocker() as m:
        # Mock the credential retrieval
        m.get("mock://credentials/mytf1", json=MOCK_CREDENTIALS["mytf1"])
        # Patch the actual get_provider_credentials for mytf1
        with mock.patch('app.utils.credentials.get_provider_credentials', return_value=MOCK_CREDENTIALS["mytf1"]) as mock_get_creds:
            provider = MyTF1Provider()
            # Manually set credentials as get_provider_credentials is mocked
            provider.credentials = MOCK_CREDENTIALS["mytf1"]
            yield provider

@pytest.fixture
def mock_authentication(requests_mock):
    """Mocks the entire TF1 authentication process."""
    # Mock bootstrap
    requests_mock.get(
        "https://compte.tf1.fr/accounts.webSdkBootstrap",
        status_code=200,
        json={"status": "ok"}
    )
    # Mock login
    requests_mock.post(
        "https://compte.tf1.fr/accounts.login",
        status_code=200,
        json={
            "errorCode": 0,
            "userInfo": {
                "UID": "mock_uid",
                "UIDSignature": "mock_uid_signature",
                "signatureTimestamp": 1234567890
            }
        }
    )
    # Mock Gigya token
    requests_mock.post(
        "https://www.tf1.fr/token/gigya/web",
        status_code=200,
        json={"token": "mock_auth_token"}
    )

def test_authentication_success(mytf1_provider, mock_authentication):
    """Test successful authentication."""
    assert mytf1_provider._authenticate() is True
    assert mytf1_provider.auth_token == "mock_auth_token"
    assert mytf1_provider._authenticated is True

def test_authentication_failure_invalid_credentials(mytf1_provider, requests_mock):
    """Test authentication failure due to invalid credentials."""
    requests_mock.get(
        "https://compte.tf1.fr/accounts.webSdkBootstrap",
        status_code=200,
        json={"status": "ok"}
    )
    requests_mock.post(
        "https://compte.tf1.fr/accounts.login",
        status_code=200,
        json={
            "errorCode": 403001,
            "errorMessage": "Invalid credentials"
        }
    )
    assert mytf1_provider._authenticate() is False
    assert mytf1_provider.auth_token is None
    assert mytf1_provider._authenticated is False

def test_authentication_failure_gigya_token(mytf1_provider, requests_mock):
    """Test authentication failure when getting Gigya token."""
    requests_mock.get(
        "https://compte.tf1.fr/accounts.webSdkBootstrap",
        status_code=200,
        json={"status": "ok"}
    )
    requests_mock.post(
        "https://compte.tf1.fr/accounts.login",
        status_code=200,
        json={
            "errorCode": 0,
            "userInfo": {
                "UID": "mock_uid",
                "UIDSignature": "mock_uid_signature",
                "signatureTimestamp": 1234567890
            }
        }
    )
    requests_mock.post(
        "https://www.tf1.fr/token/gigya/web",
        status_code=500,
        json={"error": "Internal Server Error"}
    )
    assert mytf1_provider._authenticate() is False
    assert mytf1_provider.auth_token is None
    assert mytf1_provider._authenticated is False

@pytest.mark.parametrize("channel_name, expected_video_id", [
    ("tf1", "L_TF1"),
    ("tmc", "L_TMC"),
    ("tfx", "L_TFX"),
    ("tf1-series-films", "L_TF1-SERIES-FILMS"),
])
def test_get_channel_stream_url_success(mytf1_provider, mock_authentication, requests_mock, channel_name, expected_video_id):
    """Test successful retrieval of stream URL for various channels."""
    # Ensure authentication is successful before testing stream retrieval
    mytf1_provider._authenticate()

    mock_url = f"https://live-tf1-hls-ssai.cdn-0.diff.tf1.fr/mock_stream_{channel_name}.m3u8"
    requests_mock.get(
        f"https://mediainfo.tf1.fr/mediainfocombo/{expected_video_id}",
        status_code=200,
        json={
            "delivery": {
                "code": 200,
                "url": mock_url
            }
        }
    )

    channel_id = f"cutam:fr:mytf1:{channel_name}"
    stream_info = mytf1_provider.get_channel_stream_url(channel_id)

    assert stream_info is not None
    
    # Since mediaflow is configured in the test environment, expect mediaflow proxy URL
    if mytf1_provider.mediaflow_url and mytf1_provider.mediaflow_password:
        assert "localhost:8888" in stream_info["url"]
        assert "proxy" in stream_info["url"]
        assert "d=" in stream_info["url"]
        assert "api_password" in stream_info["url"]
    else:
        assert stream_info["url"] == mock_url
    
    assert stream_info["manifest_type"] == "hls"
    assert "authorization" in stream_info["headers"]
    assert stream_info["headers"]["authorization"] == f"Bearer {mytf1_provider.auth_token}"

def test_get_channel_stream_url_api_error(mytf1_provider, mock_authentication, requests_mock):
    """Test stream URL retrieval when mediainfo API returns an error."""
    mytf1_provider._authenticate()

    requests_mock.get(
        "https://mediainfo.tf1.fr/mediainfocombo/L_TF1",
        status_code=500,
        json={"error": "Internal Server Error"}
    )

    channel_id = "cutam:fr:mytf1:tf1"
    stream_info = mytf1_provider.get_channel_stream_url(channel_id)
    assert stream_info is None

def test_get_channel_stream_url_delivery_error(mytf1_provider, mock_authentication, requests_mock):
    """Test stream URL retrieval when mediainfo API returns a delivery error code."""
    mytf1_provider._authenticate()

    requests_mock.get(
        "https://mediainfo.tf1.fr/mediainfocombo/L_TF1",
        status_code=200,
        json={
            "delivery": {
                "code": 403, # Forbidden
                "url": None
            }
        }
    )

    channel_id = "cutam:fr:mytf1:tf1"
    stream_info = mytf1_provider.get_channel_stream_url(channel_id)
    assert stream_info is None

def test_get_channel_stream_url_no_authentication(mytf1_provider):
    """Test stream URL retrieval when authentication fails."""
    # Do not call mock_authentication fixture
    mytf1_provider._authenticated = False # Ensure it's not authenticated
    mytf1_provider.auth_token = None # Ensure no token

    # Mock _authenticate to fail
    with requests_mock.Mocker() as m:
        m.get(
            "https://compte.tf1.fr/accounts.webSdkBootstrap",
            status_code=200,
            json={"status": "ok"}
        )
        m.post(
            "https://compte.tf1.fr/accounts.login",
            status_code=200,
            json={
                "errorCode": 403001,
                "errorMessage": "Invalid credentials"
            }
        )
        channel_id = "cutam:fr:mytf1:tf1"
        stream_info = mytf1_provider.get_channel_stream_url(channel_id)
        assert stream_info is None

def test_get_channel_stream_url_mediaflow_proxy(mytf1_provider, mock_authentication, requests_mock, monkeypatch):
    """Test stream URL retrieval with MediaFlow proxy enabled."""
    mytf1_provider._authenticate()

    # Mock environment variables for MediaFlow
    monkeypatch.setenv("MEDIAFLOW_PROXY_URL", "http://localhost:8888") # Keep this for proxy URL
    
    # Directly mock the mediaflow_url and mediaflow_password attributes
    with (mock.patch.object(mytf1_provider, 'mediaflow_url', "http://localhost:8888"), 
          mock.patch.object(mytf1_provider, 'mediaflow_password', "proxy_pass")):

        mock_url = "https://live-tf1-hls-ssai.cdn-0.diff.tf1.fr/mock_stream_tf1.m3u8"
        requests_mock.get(
            "https://mediainfo.tf1.fr/mediainfocombo/L_TF1",
            status_code=200,
            json={
                "delivery": {
                    "code": 200,
                    "url": mock_url
                }
            }
        )

        channel_id = "cutam:fr:mytf1:tf1"
        stream_info = mytf1_provider.get_channel_stream_url(channel_id)

        assert stream_info is not None
        assert "localhost:8888" in stream_info["url"]
        assert "proxy_pass" in stream_info["url"]
        assert "d=" in stream_info["url"]
        assert "h_user-agent" in stream_info["url"]
        assert stream_info["manifest_type"] == "hls"
        assert "authorization" in stream_info["headers"]
        assert stream_info["headers"]["authorization"] == f"Bearer {mytf1_provider.auth_token}"


