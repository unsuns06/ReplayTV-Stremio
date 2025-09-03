#!/usr/bin/env python3
"""
Tests for MyTF1 URL logging functionality
Verifies that all proxy URLs are properly logged with the new logging system
"""

import pytest
import requests_mock
import io
import sys
import re
from unittest import mock
from unittest.mock import patch, MagicMock
from app.providers.fr.mytf1 import MyTF1Provider
from app.utils.credentials import get_provider_credentials

# Mock credentials for testing
MOCK_CREDENTIALS = {
    "mytf1": {
        "login": "test@example.com",
        "password": "testpassword"
    },
    "mediaflow": {
        "url": "http://localhost:8888",
        "password": "test_password"
    }
}

@pytest.fixture
def mock_credentials():
    """Mock credentials for testing."""
    def side_effect(provider):
        return MOCK_CREDENTIALS.get(provider, {})
    
    with patch('app.utils.credentials.get_provider_credentials', side_effect=side_effect):
        yield

@pytest.fixture
def mytf1_provider(mock_credentials):
    """Fixture to provide a MyTF1Provider instance with mocked credentials."""
    provider = MyTF1Provider()
    provider.credentials = MOCK_CREDENTIALS["mytf1"]
    return provider

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

@pytest.fixture
def capture_logs():
    """Fixture to capture safe_print output."""
    captured_output = []
    
    def mock_safe_print(message):
        captured_output.append(message)
        print(message)  # Still print to console for debugging
    
    with patch('app.providers.fr.mytf1.safe_print', side_effect=mock_safe_print):
        yield captured_output

def test_live_channel_french_proxy_logging(mytf1_provider, mock_authentication, requests_mock, capture_logs):
    """Test that live channel requests log the French IP proxy URLs correctly."""
    # Setup authentication
    mytf1_provider._authenticate()
    
    mock_url = "https://live-tf1-hls-ssai.cdn-0.diff.tf1.fr/mock_stream_tf1.m3u8"
    
    # Mock the French IP proxy endpoints
    proxy_url_pattern = re.compile(r'https://tvff3tyk1e\.execute-api\.eu-west-3\.amazonaws\.com/api/router.*')
    requests_mock.get(
        proxy_url_pattern,  # Match any URL starting with proxy pattern
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
    
    # Verify that the proxy URLs were logged
    log_messages = capture_logs
    
    # Check for the specific logging patterns we added
    proxy_logs = [msg for msg in log_messages if "*** FINAL PROXY URL (LIVE)" in msg]
    assert len(proxy_logs) >= 1, f"Expected at least one proxy URL log, found: {proxy_logs}"
    
    # Verify the log contains the French IP proxy URL
    found_proxy_log = False
    for log in proxy_logs:
        if "tvff3tyk1e.execute-api.eu-west-3.amazonaws.com" in log:
            found_proxy_log = True
            break
    
    assert found_proxy_log, f"French IP proxy URL not found in logs: {proxy_logs}"
    
    # Verify the log contains expected components
    proxy_log = proxy_logs[0]
    assert "api/router" in proxy_log
    # URL is encoded in the proxy URL, so check for encoded version
    assert "mediainfo.tf1.fr%2Fmediainfocombo%2FL_TF1" in proxy_log or "mediainfo.tf1.fr/mediainfocombo/L_TF1" in proxy_log
    assert "context%3DMYTF1" in proxy_log or "context=MYTF1" in proxy_log
    
def test_live_channel_fallback_logging(mytf1_provider, mock_authentication, requests_mock, capture_logs):
    """Test that fallback URLs are logged when primary proxy fails."""
    mytf1_provider._authenticate()
    
    mock_url = "https://live-tf1-hls-ssai.cdn-0.diff.tf1.fr/mock_stream_tf1.m3u8"
    
    # Mock primary proxy to fail, fallback to succeed
    def request_callback(request, context):
        if "router?url=" in request.url and not "router/?url=" in request.url:
            # Primary proxy (no slash) fails
            context.status_code = 500
            return {"error": "proxy failed"}
        elif "router/?url=" in request.url:
            # Fallback proxy (with slash) succeeds
            context.status_code = 200
            return {
                "delivery": {
                    "code": 200,
                    "url": mock_url
                }
            }
        else:
            # Direct call
            context.status_code = 200
            return {
                "delivery": {
                    "code": 200,
                    "url": mock_url
                }
            }
    
    requests_mock.get(re.compile(r'.*'), json=request_callback)
    
    channel_id = "cutam:fr:mytf1:tf1"
    stream_info = mytf1_provider.get_channel_stream_url(channel_id)
    
    log_messages = capture_logs
    
    # Should see both primary attempt and fallback attempt logged
    proxy_logs = [msg for msg in log_messages if "*** FINAL PROXY URL (LIVE)" in msg]
    assert len(proxy_logs) >= 2, f"Expected at least 2 proxy URL logs (primary + fallback), found: {proxy_logs}"
    
    # Check for fallback logging
    fallback_logs = [msg for msg in log_messages if "FR-IP proxy (no slash) failed" in msg]
    assert len(fallback_logs) >= 1, "Expected fallback attempt message"

def test_replay_episode_proxy_logging(mytf1_provider, mock_authentication, requests_mock, capture_logs):
    """Test that replay episode requests log the French IP proxy URLs correctly."""
    mytf1_provider._authenticate()
    
    mock_url = "https://tf1-hls-live-ssl.tf1.fr/tf1/mock_replay.m3u8"
    
    # Mock the French IP proxy for replay content
    requests_mock.get(
        re.compile(r'.*'),
        status_code=200,
        json={
            "delivery": {
                "code": 200,
                "url": mock_url
            }
        }
    )
    
    episode_id = "cutam:fr:mytf1:episode:12345"
    stream_info = mytf1_provider.get_episode_stream_url(episode_id)
    
    log_messages = capture_logs
    
    # Check for replay proxy logging
    replay_proxy_logs = [msg for msg in log_messages if "*** FINAL PROXY URL (REPLAY)" in msg]
    assert len(replay_proxy_logs) >= 1, f"Expected at least one replay proxy URL log, found: {replay_proxy_logs}"
    
    # Verify the log contains the French IP proxy URL for replay
    found_replay_proxy_log = False
    for log in replay_proxy_logs:
        if "tvff3tyk1e.execute-api.eu-west-3.amazonaws.com" in log:
            found_replay_proxy_log = True
            break
    
    assert found_replay_proxy_log, f"French IP proxy URL for replay not found in logs: {replay_proxy_logs}"
    
    # Verify the log contains expected replay-specific components
    replay_log = replay_proxy_logs[0]
    assert "api/router" in replay_log
    # URL is encoded in the proxy URL, so check for encoded version
    assert "mediainfo.tf1.fr%2Fmediainfocombo%2F12345" in replay_log or "mediainfo.tf1.fr/mediainfocombo/12345" in replay_log
    assert "context%3DMYTF1" in replay_log or "context=MYTF1" in replay_log

def test_mediaflow_proxy_logging_live(mytf1_provider, mock_authentication, requests_mock, capture_logs):
    """Test that MediaFlow proxy URLs are logged for live streams."""
    # Enable MediaFlow for this test
    mytf1_provider.mediaflow_url = "http://localhost:8888"
    mytf1_provider.mediaflow_password = "test_password"
    
    mytf1_provider._authenticate()
    
    mock_url = "https://live-tf1-hls-ssai.cdn-0.diff.tf1.fr/mock_stream_tf1.m3u8"
    
    # Mock the French IP proxy to return stream URL
    requests_mock.get(
        re.compile(r'.*'),
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
    
    log_messages = capture_logs
    
    # Check for MediaFlow proxy logging
    mediaflow_logs = [msg for msg in log_messages if "*** FINAL MEDIAFLOW URL (LIVE)" in msg]
    assert len(mediaflow_logs) >= 1, f"Expected at least one MediaFlow URL log for live, found: {mediaflow_logs}"
    
    # Verify the log contains the MediaFlow proxy URL
    mediaflow_log = mediaflow_logs[0]
    assert "localhost:8888" in mediaflow_log
    assert "proxy" in mediaflow_log
    assert "api_password=test_password" in mediaflow_log
    assert mock_url in mediaflow_log or "d=" in mediaflow_log  # Either raw URL or encoded

def test_mediaflow_proxy_logging_replay(mytf1_provider, mock_authentication, requests_mock, capture_logs, monkeypatch):
    """Test that MediaFlow proxy URLs are logged for replay streams when enabled."""
    # Enable MediaFlow for replays via environment variable
    monkeypatch.setenv('MYTF1_REPLAY_VIA_MEDIAFLOW', 'true')
    
    # Enable MediaFlow for this test
    mytf1_provider.mediaflow_url = "http://localhost:8888"
    mytf1_provider.mediaflow_password = "test_password"
    
    mytf1_provider._authenticate()
    
    mock_url = "https://tf1-hls-live-ssl.tf1.fr/tf1/mock_replay.m3u8"
    
    # Mock the French IP proxy to return stream URL
    requests_mock.get(
        re.compile(r'.*'),
        status_code=200,
        json={
            "delivery": {
                "code": 200,
                "url": mock_url
            }
        }
    )
    
    episode_id = "cutam:fr:mytf1:episode:12345"
    stream_info = mytf1_provider.get_episode_stream_url(episode_id)
    
    log_messages = capture_logs
    
    # Check for MediaFlow proxy logging for replay
    mediaflow_logs = [msg for msg in log_messages if "*** FINAL MEDIAFLOW URL (REPLAY)" in msg]
    assert len(mediaflow_logs) >= 1, f"Expected at least one MediaFlow URL log for replay, found: {mediaflow_logs}"
    
    # Verify the log contains the MediaFlow proxy URL
    mediaflow_log = mediaflow_logs[0]
    assert "localhost:8888" in mediaflow_log
    assert "proxy" in mediaflow_log
    assert "api_password=test_password" in mediaflow_log
    assert mock_url in mediaflow_log or "d=" in mediaflow_log  # Either raw URL or encoded

def test_direct_url_logging_when_proxy_fails(mytf1_provider, mock_authentication, requests_mock, capture_logs):
    """Test that direct URLs are logged when both proxy variants fail."""
    mytf1_provider._authenticate()
    
    mock_url = "https://live-tf1-hls-ssai.cdn-0.diff.tf1.fr/mock_stream_tf1.m3u8"
    
    # Mock both proxy variants to fail, direct call to succeed
    def request_callback(request, context):
        if "tvff3tyk1e.execute-api.eu-west-3.amazonaws.com" in request.url:
            # Both proxy variants fail
            context.status_code = 500
            return {"error": "proxy failed"}
        else:
            # Direct call succeeds
            context.status_code = 200
            return {
                "delivery": {
                    "code": 200,
                    "url": mock_url
                }
            }
    
    requests_mock.get(re.compile(r'.*'), json=request_callback)
    
    channel_id = "cutam:fr:mytf1:tf1"
    stream_info = mytf1_provider.get_channel_stream_url(channel_id)
    
    log_messages = capture_logs
    
    # Should see direct URL logging
    direct_logs = [msg for msg in log_messages if "*** FINAL DIRECT URL (LIVE)" in msg]
    assert len(direct_logs) >= 1, f"Expected at least one direct URL log, found: {direct_logs}"
    
    # Verify the direct URL log
    direct_log = direct_logs[0]
    assert "mediainfo.tf1.fr/mediainfocombo/L_TF1" in direct_log
    # Direct URL logs just show the base URL, params are passed separately

def test_all_logging_patterns_present(mytf1_provider, mock_authentication, requests_mock, capture_logs):
    """Test that all expected logging patterns are present in the code."""
    # This test verifies that our logging additions are working as expected
    mytf1_provider._authenticate()
    
    mock_url = "https://live-tf1-hls-ssai.cdn-0.diff.tf1.fr/mock_stream_tf1.m3u8"
    
    # Mock proxy to fail so we get all logging patterns
    def request_callback(request, context):
        if "router?url=" in request.url and not "router/?url=" in request.url:
            context.status_code = 500
            return {"error": "proxy failed"}
        elif "router/?url=" in request.url:
            context.status_code = 500  
            return {"error": "proxy failed"}
        else:
            # Direct call succeeds
            context.status_code = 200
            return {
                "delivery": {
                    "code": 200,
                    "url": mock_url
                }
            }
    
    requests_mock.get(re.compile(r'.*'), json=request_callback)
    
    channel_id = "cutam:fr:mytf1:tf1"
    stream_info = mytf1_provider.get_channel_stream_url(channel_id)
    
    log_messages = capture_logs
    all_logs = '\n'.join(log_messages)
    
    # Verify all our logging patterns are present
    assert "*** FINAL PROXY URL (LIVE)" in all_logs, "Missing live proxy URL logging"
    assert "*** FINAL DIRECT URL (LIVE)" in all_logs, "Missing direct URL logging"
    assert "FR-IP proxy (no slash) failed" in all_logs, "Missing proxy failure message"
    
    # Test episode logging too
    episode_id = "cutam:fr:mytf1:episode:12345"
    mytf1_provider.get_episode_stream_url(episode_id)
    
    log_messages_after_episode = capture_logs
    all_logs_after = '\n'.join(log_messages_after_episode)
    
    assert "*** FINAL PROXY URL (REPLAY)" in all_logs_after, "Missing replay proxy URL logging"
    # Note: Direct URL logging for replay only happens when both proxy variants fail
    # In this test, the first proxy succeeds for replay, so no direct URL logging occurs

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
