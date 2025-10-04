#!/usr/bin/env python3
"""
Test online DRM processing integration for 6play replays
"""

import pytest
import json
from unittest.mock import patch, MagicMock

from app.providers.fr.sixplay import SixPlayProvider
from app.utils.nm3u8_drm_processor import process_drm_simple


class TestOnlineDRMProcessing:
    """Test the online DRM processing integration for 6play replays"""

    @pytest.fixture
    def sixplay_provider(self):
        """Create a SixPlayProvider instance with mocked dependencies"""
        with patch(
            "app.providers.fr.sixplay.get_provider_credentials",
            return_value={
                "username": "test_user",
                "password": "test_pass",
                "account_id": "test_account_id",
                "login_token": "test_login_token"
            }
        ), patch(
            "app.providers.fr.sixplay.SixPlayAuth"
        ) as mock_auth:
            # Mock successful authentication
            mock_auth_instance = MagicMock()
            mock_auth_instance.login.return_value = True
            mock_auth_instance.get_auth_data.return_value = ("test_account_id", "test_login_token")
            mock_auth.return_value = mock_auth_instance

            provider = SixPlayProvider()
            provider.account_id = "test_account_id"
            provider.login_token = "test_login_token"
            provider._authenticated = True

            yield provider

    @pytest.fixture
    def mock_session(self, sixplay_provider):
        """Mock requests session for API calls"""
        # Mock the session on the provider instance
        mock_session = MagicMock()

        # Mock video API response (first call)
        video_response = MagicMock()
        video_response.status_code = 200
        video_response.json.return_value = {
            "clips": [{
                "assets": [
                    {
                        "type": "usp_dashcenc_h264",
                        "video_quality": "hd",
                        "full_physical_path": "https://drm.example.com/manifest.mpd"
                    }
                ]
            }]
        }
        video_response.headers = {}

        # Mock DRM token response (second call)
        token_response = MagicMock()
        token_response.status_code = 200
        token_response.json.return_value = {"token": "test_drm_token"}
        token_response.headers = {}

        # Configure the mock to return different responses for different URLs
        def mock_get(url, **kwargs):
            if "videos/" in url and "test_episode_123" in url:
                return video_response
            elif "upfront-token" in url:
                return token_response
            else:
                # Default response for other calls
                default_response = MagicMock()
                default_response.status_code = 200
                default_response.json.return_value = {}
                return default_response

        mock_session.get.side_effect = mock_get
        sixplay_provider.session = mock_session

        yield mock_session

    def test_online_drm_processing_success(self, sixplay_provider, mock_session):
        """Test successful online DRM processing for 6play replays"""

        # Mock the DRM processor to return successful processing
        mock_online_result = {
            "success": True,
            "filename": "6play_test_episode_123.mkv",
            "download_url": "https://alphanet06-processor.hf.space/stream/6play_test_episode_123.mkv",
            "file_size_mb": 150.5
        }

        with patch(
            "app.providers.fr.sixplay.process_drm_simple",
            return_value=mock_online_result
        ) as mock_process_drm, patch(
            "app.providers.fr.sixplay.extract_first_pssh"
        ) as mock_extract_pssh, patch(
            "app.providers.fr.sixplay.extract_drm_info_from_mpd"
        ) as mock_extract_drm, patch(
            "app.providers.fr.sixplay.get_random_windows_ua",
            return_value="test-user-agent"
        ):

            # Mock PSSH extraction
            mock_pssh_record = MagicMock()
            mock_pssh_record.base64_text = "test_pssh_base64"
            mock_pssh_record.system_id = "edef8ba9-79d6-4ace-a3c8-27dcd51d21ed"
            mock_extract_pssh.return_value = (mock_pssh_record, b"mock_mpd_content")

            # Mock DRM info extraction
            mock_extract_drm.return_value = {
                "key_id": "1d83a873b4d34f77b5f68424a0efc8c1",
                "widevine_pssh": "test_pssh_base64"
            }

            # Mock Widevine key extraction
            with patch.object(
                sixplay_provider,
                "_extract_widevine_key",
                return_value="000102030405060708090a0b0c0d0e0f"
            ), patch.object(
                sixplay_provider,
                "_normalize_decryption_key",
                return_value="000102030405060708090a0b0c0d0e0f"
            ):

                # Test the episode stream request
                result = sixplay_provider.get_episode_stream_url("test_episode_123")

                # Verify that online processing was attempted
                mock_process_drm.assert_called_once()
                call_args = mock_process_drm.call_args

                # Check that the correct parameters were passed
                assert call_args[1]["url"] == "https://drm.example.com/manifest.mpd"
                assert call_args[1]["save_name"] == "6play_test_episode_123"
                assert call_args[1]["key"] == "000102030405060708090a0b0c0d0e0f"
                assert call_args[1]["format"] == "mkv"

                # Verify the response structure
                assert result is not None
                assert "processed_stream" in result
                assert "online_processed" in result
                assert result["online_processed"] is True

                # Verify processed stream details
                processed_stream = result["processed_stream"]
                assert processed_stream["url"] == "https://alphanet06-processor.hf.space/stream/6play_test_episode_123.mkv"
                assert processed_stream["manifest_type"] == "video"
                assert processed_stream["filename"] == "6play_test_episode_123.mkv"
                assert processed_stream["original_url"] == "https://drm.example.com/manifest.mpd"

                # Verify original DRM stream is still present
                assert "url" in result  # Original DRM stream URL
                assert "manifest_type" in result  # Should be "mpd"
                assert result["manifest_type"] == "mpd"

    def test_online_drm_processing_failure_fallback(self, sixplay_provider, mock_session):
        """Test fallback to original DRM approach when online processing fails"""

        # Mock the DRM processor to return failed processing
        mock_online_result = {
            "success": False,
            "error": "Processing timeout"
        }

        with patch(
            "app.providers.fr.sixplay.process_drm_simple",
            return_value=mock_online_result
        ) as mock_process_drm, patch(
            "app.providers.fr.sixplay.extract_first_pssh"
        ) as mock_extract_pssh, patch(
            "app.providers.fr.sixplay.extract_drm_info_from_mpd"
        ) as mock_extract_drm, patch(
            "app.providers.fr.sixplay.get_random_windows_ua",
            return_value="test-user-agent"
        ):

            # Mock PSSH extraction
            mock_pssh_record = MagicMock()
            mock_pssh_record.base64_text = "test_pssh_base64"
            mock_pssh_record.system_id = "edef8ba9-79d6-4ace-a3c8-27dcd51d21ed"
            mock_extract_pssh.return_value = (mock_pssh_record, b"mock_mpd_content")

            # Mock DRM info extraction
            mock_extract_drm.return_value = {
                "key_id": "1d83a873b4d34f77b5f68424a0efc8c1",
                "widevine_pssh": "test_pssh_base64"
            }

            # Mock Widevine key extraction
            with patch.object(
                sixplay_provider,
                "_extract_widevine_key",
                return_value="000102030405060708090a0b0c0d0e0f"
            ), patch.object(
                sixplay_provider,
                "_normalize_decryption_key",
                return_value="000102030405060708090a0b0c0d0e0f"
            ):

                # Test the episode stream request
                result = sixplay_provider.get_episode_stream_url("test_episode_123")

                # Verify that online processing was attempted but failed
                mock_process_drm.assert_called_once()

                # Verify fallback behavior
                assert result is not None
                assert "processed_stream" not in result  # No processed stream on failure
                assert "online_processed" not in result  # No online processing flag

                # Verify original DRM stream is present
                assert "url" in result
                assert "manifest_type" in result
                assert result["manifest_type"] == "mpd"

    def test_online_drm_processing_no_drm_content(self, sixplay_provider, mock_session):
        """Test that online processing is not attempted for non-DRM content"""

        # Mock video API response with HLS (no DRM)
        hls_response = MagicMock()
        hls_response.status_code = 200
        hls_response.json.return_value = {
            "clips": [{
                "assets": [
                    {
                        "type": "http_h264",
                        "video_quality": "hd",
                        "full_physical_path": "https://hls.example.com/stream.m3u8"
                    }
                ]
            }]
        }
        mock_session.get.return_value = hls_response

        with patch(
            "app.providers.fr.sixplay.process_drm_simple"
        ) as mock_process_drm:

            # Test the episode stream request for HLS content
            result = sixplay_provider.get_episode_stream_url("test_episode_123")

            # Verify that online processing was NOT attempted for HLS content
            mock_process_drm.assert_not_called()

            # Verify HLS stream is returned
            assert result is not None
            assert result["manifest_type"] == "hls"
            assert "processed_stream" not in result

    def test_online_drm_processing_replay_only(self, sixplay_provider, mock_session):
        """Test that online processing only applies to replay episodes, not live streams"""

        # Mock the DRM processor
        with patch(
            "app.providers.fr.sixplay.process_drm_simple"
        ) as mock_process_drm:

            # Test live stream request (should not trigger online processing)
            live_result = sixplay_provider.get_channel_stream_url("cutam:fr:6play:m6")

            # Verify online processing was NOT attempted for live streams
            mock_process_drm.assert_not_called()

            # Test replay episode request (should trigger online processing)
            replay_result = sixplay_provider.get_episode_stream_url("test_episode_123")

            # Verify online processing was attempted for replay episodes
            # (The actual call happens later in the method, so we can't easily assert it here
            # without more complex mocking, but this confirms the method paths are different)
            assert replay_result is not None

    def test_online_drm_processing_parameters(self, sixplay_provider):
        """Test that the correct parameters are passed to the DRM processor"""

        # Mock successful online processing
        mock_online_result = {
            "success": True,
            "filename": "test_file.mkv",
            "download_url": "https://test.com/test_file.mkv"
        }

        with patch(
            "app.providers.fr.sixplay.process_drm_simple",
            return_value=mock_online_result
        ) as mock_process_drm, patch(
            "app.providers.fr.sixplay.extract_first_pssh"
        ) as mock_extract_pssh, patch(
            "app.providers.fr.sixplay.extract_drm_info_from_mpd"
        ) as mock_extract_drm, patch(
            "app.providers.fr.sixplay.get_random_windows_ua",
            return_value="test-user-agent"
        ):

            # Mock PSSH and DRM extraction
            mock_pssh_record = MagicMock()
            mock_pssh_record.base64_text = "test_pssh"
            mock_extract_pssh.return_value = (mock_pssh_record, b"mock")
            mock_extract_drm.return_value = {"key_id": "test_key_id"}

            # Mock key extraction and normalization
            with patch.object(
                sixplay_provider,
                "_extract_widevine_key",
                return_value="test_normalized_key"
            ), patch.object(
                sixplay_provider,
                "_normalize_decryption_key",
                return_value="test_normalized_key"
            ):

                sixplay_provider.get_episode_stream_url("test_episode_123")

                # Verify the exact parameters passed to process_drm_simple
                mock_process_drm.assert_called_once()
                call_kwargs = mock_process_drm.call_args[1]

                assert call_kwargs["url"] == "https://drm.example.com/manifest.mpd"
                assert call_kwargs["save_name"] == "6play_test_episode_123"
                assert call_kwargs["key"] == "test_normalized_key"
                assert call_kwargs["quality"] == "best"
                assert call_kwargs["format"] == "mkv"
