#!/usr/bin/env python3
"""
6play provider implementation
Hybrid approach with robust error handling, fallbacks, and retry logic
"""
import logging

import json
import requests
import re
import uuid
import os
import base64

from typing import Dict, List, Optional, Tuple
from app.utils.credentials import get_provider_credentials
from app.auth.sixplay_auth import SixPlayAuth
from app.providers.fr.metadata import metadata_processor
from app.utils.sixplay_mpd_processor import create_mediaflow_compatible_mpd, extract_drm_info_from_mpd
from app.utils.mediaflow import build_mediaflow_url
from app.utils.mpd_server import get_processed_mpd_url_for_mediaflow
from app.providers.fr.extract_pssh import extract_first_pssh, PsshRecord
from app.utils.nm3u8_drm_processor import process_drm_simple
from app.utils.user_agent import get_random_windows_ua
from app.utils.programs_loader import get_programs_for_provider
from app.providers.base_provider import BaseProvider
from app.providers.fr.common import check_processed_file

logger = logging.getLogger(__name__)

class SixPlayProvider(BaseProvider):
    """6play provider implementation with robust error handling and fallbacks"""
    
    # Class attributes for BaseProvider
    provider_name = "6play"
    base_url = "https://www.6play.fr"
    country = "fr"
    
    # Metadata
    display_name = "6play"
    id_prefix = "cutam:fr:6play"
    episode_marker = "episode:"
    catalog_id = "fr-6play-replay"
    supports_live = False

    
    def __init__(self, request=None):
        # Initialize base class (handles credentials, session, mediaflow, proxy_config)
        super().__init__(request)
        
        # 6play-specific API endpoints
        self.api_url = "https://android.middleware.6play.fr/6play/v2/platforms/m6group_androidmob/services/6play"
        self.auth_url = "https://login-gigya.m6.fr/accounts.login"
        self.token_url = "https://6cloud.fr/v1/customers/m6web/platforms/m6group_web/services/6play/users"
        self.live_url = "https://android.middleware.6play.fr/6play/v2/platforms/m6group_androidmob/services/6play/live"
        self.api_key = "3_hH5KBv25qZTd_sURpixbQW6a4OsiIzIEF2Ei_2H7TXTGLJb_1Hr4THKZianCQhWK"
        
        # 6play-specific authentication state
        self.account_id = None
        self.login_token = None
        
        # Load shows from external programs.json
        self.shows = get_programs_for_provider('6play')

    def _authenticate(self) -> bool:
        """Authenticate the session for 6play using real Gigya authentication.

        This implementation follows the Kodi plugin approach:
        - Uses Gigya API for real authentication
        - Obtains JWT tokens for DRM content access
        - Falls back gracefully for unauthenticated access to free content
        - Caches authentication state to avoid repeated logins
        """
        try:
            if self._authenticated:
                return True

            username = (self.credentials or {}).get("username") or (self.credentials or {}).get("login")
            password = (self.credentials or {}).get("password")

            # If tokens are pre-provisioned, use them directly
            preset_account_id = (self.credentials or {}).get("account_id")
            preset_login_token = (self.credentials or {}).get("login_token")
            if preset_account_id and preset_login_token:
                self.account_id = preset_account_id
                self.login_token = preset_login_token
                self._authenticated = True
                logger.debug("✅ [SixPlay] Using preset 6play account_id/login_token from credentials")
                return True

            # If no credentials provided, allow unauthenticated access (HLS-only paths may still work)
            if not username or not password:
                logger.warning("⚠️ [SixPlay] No 6play credentials found; continuing without authentication")
                logger.warning("⚠️ [SixPlay] Note: DRM content will not be accessible without valid credentials")
                self._authenticated = True  # Mark as 'handled' so callers can proceed to non-DRM paths
                return True

            # Perform real authentication using Gigya API
            auth = SixPlayAuth(username=username, password=password)
            if auth.login():
                # Get real authentication data
                auth_data = auth.get_auth_data()
                if auth_data:
                    self.account_id, self.login_token = auth_data
                    self._authenticated = True
                    logger.debug(f"✅ [SixPlay] 6play authentication succeeded")
                    logger.debug(f"🔑 [SixPlay] Account ID: {self.account_id}")
                    logger.debug(f"🔑 [SixPlay] JWT Token: {self.login_token[:20]}...")
                    return True

            logger.error("❌ [SixPlay] 6play authentication failed")
            # Still mark as handled to allow non-DRM content access
            self._authenticated = True
            return False
        except Exception as e:
            logger.error(f"❌ [SixPlay] Authentication error: {e}")
            # Mark as handled but authentication failed
            self._authenticated = True
            return False
    
    def _safe_api_call(self, url: str, params: Dict = None, headers: Dict = None, data: Dict = None, method: str = 'GET', max_retries: int = 3) -> Optional[Dict]:
        """Delegate to shared ProviderAPIClient for consistent retry/error handling."""
        return self.api_client.safe_request(
            method=method,
            url=url,
            params=params,
            headers=headers,
            data=data if method.upper() == 'POST' else None,
            max_retries=max_retries
        )
    
    def get_live_channels(self) -> List[Dict]:
        """Live channels not supported for 6play - returns empty list."""
        return []


    def _build_show_metadata(self, show_id: str, show_info: Dict) -> Dict:
        """Build show metadata dictionary from show configuration."""
        return {
            'id': f"cutam:fr:6play:{show_id}",
            'type': 'series',
            'name': show_info['name'],
            'description': show_info['description'],
            'channel': show_info['channel'],
            'genres': show_info['genres'],
            'year': show_info['year'],
            'rating': show_info['rating'],
            'logo': show_info['logo'],
            'poster': show_info['poster'],
            'background': show_info.get('background', '')
        }

    def get_programs(self) -> List[Dict]:
        """Get list of 6play replay shows with enhanced metadata (parallel fetching)"""
        shows = []
        self.shows = get_programs_for_provider('6play')
        
        def fetch_api_metadata(item):
            """Fetch API metadata for a single show."""
            show_id, show_info = item
            try:
                return (show_id, self._get_show_api_metadata(show_id, show_info))
            except Exception as e:
                logger.warning(f"⚠️ [SixPlay] Warning: Could not fetch API metadata for {show_id}: {e}")
                return (show_id, None)
        
        try:
            api_results = dict(self._parallel_map(fetch_api_metadata, self.shows.items()))
            
            for show_id, show_info in self.shows.items():
                show_metadata = self._build_show_metadata(show_id, show_info)
                api_metadata = api_results.get(show_id)
                if api_metadata and 'fanart' in api_metadata:
                    show_metadata['fanart'] = api_metadata['fanart']
                shows.append(show_metadata)
        except Exception as e:
            logger.error(f"❌ [SixPlay] Error fetching show metadata: {e}")
            for show_id, show_info in self.shows.items():
                shows.append(self._build_show_metadata(show_id, show_info))
        
        return shows

    def get_episodes(self, show_id: str) -> List[Dict]:
        """Get episodes for a specific 6play show"""
        # Extract the actual show ID from our format
        if "6play:" in show_id:
            actual_show_id = show_id.split("6play:")[-1]
        else:
            actual_show_id = show_id
        
        try:
            logger.debug(f"🔍 [SixPlay] Getting episodes for 6play show: {actual_show_id}")
            
            # Use the same approach as the reference plugin
            # First, check if we have the program ID in our configuration (robustness fix)
            program_id = None
            if actual_show_id in self.shows:
                program_id = self.shows[actual_show_id].get('api_id')
                if program_id:
                    logger.debug(f"✅ [SixPlay] Using hardcoded program ID: {program_id}")

            if not program_id:
                # First, we need to find the program ID for the show
                program_id = self._find_program_id(actual_show_id)
            
            if not program_id:
                logger.error(f"❌ [SixPlay] No program ID found for show: {actual_show_id}")
                return []
            
            # Get episodes using the program ID
            episodes = self._get_show_episodes(program_id)
            
            if episodes:
                # Sort chronologically and re-number (oldest = 1, newest = highest)
                episodes = self._sort_episodes_chronologically(episodes)
                logger.debug(f"✅ [SixPlay] Found {len(episodes)} episodes for {actual_show_id} (sorted chronologically)")
            else:
                logger.warning(f"⚠️ [SixPlay] No episodes found for {actual_show_id}")
            
            return episodes
            
        except Exception as e:
            logger.error(f"❌ [SixPlay] Error getting episodes for {actual_show_id}: {e}")
            return []
    def _check_processed_file(self, episode_id: str) -> Optional[Dict]:
        """Delegate to shared helper (see app.providers.fr.common.check_processed_file)."""
        return check_processed_file(episode_id, provider_tag="SixPlay")

    def get_episode_stream_url(self, episode_id: str) -> Optional[Dict]:
        """Get stream URL for a specific 6play episode"""
        # Extract the actual episode ID from our format
        if "episode:" in episode_id:
            actual_episode_id = episode_id.split("episode:")[-1]
        else:
            actual_episode_id = episode_id
        
        try:
            logger.debug(f"🔍 [SixPlay] Getting replay stream for 6play episode: {actual_episode_id}")

            # Check if processed file already exists (RD or processor)
            existing_file = self._check_processed_file(actual_episode_id)
            if existing_file:
                return existing_file

            # Lazy authentication - only authenticate when needed
            if not self._authenticated and not self._authenticate():
                logger.error("❌ [SixPlay] 6play authentication failed")
                return None
            
            # Use the same approach as the reference plugin for replay content
            headers_video_stream = {
                "User-Agent": get_random_windows_ua(),
            }
            headers_video_stream = self._merge_ip_headers(headers_video_stream)
            
            # Get video info using the same API call as the reference plugin
            url_json = f"https://android.middleware.6play.fr/6play/v2/platforms/m6group_androidmob/services/6play/videos/{actual_episode_id}?csa=6&with=clips,freemiumpacks"

            response = self.session.get(url_json, headers=headers_video_stream, timeout=10)
            token_response = None
            
            if response.status_code == 200:
                json_parser = response.json()
                logger.debug(f"✅ [SixPlay] Video API response received for {actual_episode_id}")
                
                # Extract video assets (same as reference plugin)
                if 'clips' in json_parser and json_parser['clips']:
                    video_assets = json_parser['clips'][0].get('assets', [])
                    
                    if video_assets:
                        # Dynamic format detection - analyze available assets to determine best format
                        logger.debug(f"🔍 Analyzing {len(video_assets)} available assets for optimal format...")
                        
                        # Analyze available asset types
                        available_formats = self._analyze_available_formats(video_assets)
                        logger.debug(f"📊 Available formats: {available_formats}")
                        
                        # Determine best format based on server response and client capabilities
                        best_format = self._determine_best_format(available_formats)
                        logger.debug(f"🎯 Selected format: {best_format}")
                        
                        # Get the stream URL for the selected format
                        final_video_url = self._get_final_video_url(video_assets, best_format['asset_type'])
                        
                        if final_video_url:
                            logger.debug(f"✅ {best_format['format_name']} stream found: {final_video_url}")
                            
                            # Handle HLS streams (no DRM required)
                            if best_format['format_type'] == 'hls':
                                return [{
                                    "url": final_video_url,
                                    "manifest_type": "hls"
                                }]
                            
                            # Handle MPD/DASH streams (DRM required)
                            elif best_format['format_type'] == 'mpd':
                                # Extract DRM metadata from the MPD manifest
                                pssh_record, mpd_text, drm_info = self._extract_pssh_from_mpd(final_video_url)

                                key_id_hex = self._normalize_key_id((drm_info or {}).get('key_id'))
                                if key_id_hex:
                                    logger.debug(f"🔑 [SixPlay] MPD default_KID: {key_id_hex}")

                                drm_token = None
                                if self.account_id and self.login_token:
                                    try:
                                        payload_headers = {
                                            'X-Customer-Name': 'm6web',
                                            'X-Client-Release': '5.103.3',
                                            'Authorization': f'Bearer {self.login_token}',
                                        }

                                        complete_headers = self._merge_ip_headers(payload_headers)

                                        logger.debug(f"📋 [SixPlay] DRM Token Request Headers:")
                                        for header_name, header_value in complete_headers.items():
                                            if header_name.lower() in ['authorization', 'x-auth-token', 'token']:
                                                masked_value = f"{header_value[:20]}..." if len(str(header_value)) > 20 else "***"
                                                logger.debug(f"📋   {header_name}: {masked_value}")
                                            else:
                                                logger.debug(f"📋   {header_name}: {header_value}")

                                        token_url = f"https://drm.6cloud.fr/v1/customers/m6web/platforms/m6group_web/services/m6replay/users/{self.account_id}/videos/{actual_episode_id}/upfront-token"
                                        logger.debug(f"📋 [SixPlay] DRM Token URL: {token_url}")

                                        token_response = self.session.get(token_url, headers=complete_headers, timeout=10)

                                        logger.debug(f"📋 [SixPlay] DRM Token Response:")
                                        logger.debug(f"📋   Status Code: {token_response.status_code}")
                                        logger.debug(f"📋   Response Headers: {dict(token_response.headers)}")

                                        if token_response.status_code == 200:
                                            token_data = token_response.json()
                                            drm_token = token_data["token"]
                                            logger.debug(f"✅ [SixPlay] DRM token obtained successfully")
                                            logger.debug(f"🔑 [SixPlay] DRM Token Value: {drm_token}")
                                        else:
                                            logger.error(f"❌ DRM token request failed: {token_response.status_code}")
                                            logger.debug(f"📋   Response content: {token_response.text[:500]}...")
                                            logger.warning(f"⚠️   Check your 6play credentials and authentication")

                                    except Exception as e:
                                        logger.error(f"❌ [SixPlay] DRM setup failed: {e}")

                                # Build the original DRM stream
                                original_stream = {
                                    "url": final_video_url,
                                    "manifest_type": "mpd"
                                }
                                if key_id_hex:
                                    original_stream["default_kid"] = key_id_hex

                                if pssh_record:
                                    original_stream["pssh"] = pssh_record.base64_text
                                    original_stream["pssh_system_id"] = pssh_record.system_id
                                    original_stream["pssh_source"] = pssh_record.source
                                    logger.debug(f"✅ [SixPlay] PSSH data included in stream response")

                                    if drm_token:
                                        raw_key = self._extract_widevine_key(pssh_record.base64_text, drm_token)
                                        if raw_key:
                                            normalized_key = self._normalize_decryption_key(raw_key, key_id_hex)
                                            if normalized_key:
                                                original_stream["decryption_key"] = normalized_key
                                                logger.debug(f"✅ [SixPlay] Widevine decryption key included in stream response")

                                                self._print_download_command(final_video_url, normalized_key, actual_episode_id)

                                                # Trig��er online DRM processing since file doesn't exist
                                                online_result = process_drm_simple(
                                                    url=final_video_url,
                                                    save_name=f"{actual_episode_id}",
                                                    key=normalized_key,
                                                    quality="best",
                                                    format="mkv",
                                                    binary_merge=True
                                                )

                                                if online_result.get("success"):
                                                    # Processing successfully triggered - return processed stream as primary result
                                                    return {
                                                        "url": "https://stream-not-available",
                                                        "manifest_type": "video",
                                                        "title": "⏳ DRM-Free Video (Processing in background...)",
                                                        "description": "Stream not available - Processing in progress. Please check back in a few minutes."
                                                    }
                                                else:
                                                    # Processing failed - return failure stream
                                                    return {
                                                        "url": "https://stream-not-available",
                                                        "manifest_type": "video",
                                                        "title": "❌ DRM Processing Failed",
                                                        "description": "Stream not available - DRM processing could not be started. Please try again later."
                                                    }
                                            else:
                                                logger.error("❌ Unable to normalize Widevine key for MediaFlow usage")
                                        else:
                                            logger.error("❌ CDRM did not return a Widevine key")
                                else:
                                    logger.warning(f"⚠️ [SixPlay] No PSSH found in MPD manifest")

                                if drm_token:
                                    license_url = f"https://lic.drmtoday.com/license-proxy-widevine/cenc/|Content-Type=&User-Agent=Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/59.0.3041.0 Safari/537.36&Host=lic.drmtoday.com&x-dt-auth-token={drm_token}|R{{SSM}}|JBlicense"

                                    license_headers = {
                                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/59.0.3041.0 Safari/537.36"
                                    }

                                    logger.debug("📋 [SixPlay] DRM License Information:")
                                    logger.debug(f"📋   License URL: {license_url}")
                                    logger.debug(f"📋   License Headers: {license_headers}")
                                    logger.debug(f"📋   Video URL: {final_video_url}")

                                    logger.debug("🔍 [SixPlay] Using direct DRM approach with license")

                                    original_stream.update({
                                        "licenseUrl": license_url,
                                        "licenseHeaders": license_headers,
                                        "drm_token": drm_token,
                                        "drm_protected": True
                                    })

                                    return original_stream
                                else:
                                    logger.warning(f"⚠️ [SixPlay] No DRM token available - returning basic MPD with PSSH")
                                    return original_stream
                            else:
                                logger.warning(f"⚠️ No {best_format['format_name']} streams found")
                        else:
                            logger.warning("⚠️ No MPD streams found either")
                else:
                    logger.error(f"❌ 6play API error: {response.status_code}")
            else:
                logger.error(f"❌ 6play token error: {token_response.status_code}")
            
            # Fallback - return None to indicate failure
            return None

        except Exception as e:
            logger.error(f"❌ [SixPlay] Error getting stream for {actual_episode_id}: {e}")

        return None

    def get_channel_stream_url(self, channel_id: str) -> Optional[Dict]:
        """Live channel streaming not supported for 6play - returns None."""
        return None
    
    
    def _get_final_video_url(self, video_assets, asset_type=None):
        """Get final video URL from assets (based on reference get_final_video_url)"""
        RES_PRIORITY = {"sd": 0, "hd": 1}
        manifests = []
        
        if video_assets is None:
            return None
        
        for asset in video_assets:
            if asset_type is None:
                if 'http_h264' in asset.get("type", ""):
                    manifest = (asset.get("video_quality", "sd").lower(), asset["full_physical_path"])
                    if manifest not in manifests:
                        manifests.append(manifest)
                    continue
            elif asset.get("type") == asset_type:
                manifest = (asset.get("video_quality", "sd").lower(), asset["full_physical_path"])
                if manifest not in manifests:
                    manifests.append(manifest)
        
        if not manifests:
            # Fallback: try any dashcenc asset
            for asset in video_assets:
                if 'dashcenc' in asset.get("type", ""):
                    manifest = (asset.get("video_quality", "sd").lower(), asset["full_physical_path"])
                    if manifest not in manifests:
                        manifests.append(manifest)
        
        if not manifests:
            return None
        
        # Sort by quality and get the best one
        final_video_url = sorted(manifests, key=lambda m: RES_PRIORITY.get(m[0], 0), reverse=True)[0][1]
        
        if len(final_video_url) == 0:
            return None
        
        # Handle redirects for usp_dashcenc_h264 (from reference)
        if asset_type and 'usp_dashcenc_h264' in asset_type:
            try:
                dummy_req = self.session.head(final_video_url, allow_redirects=False, timeout=10)
                if 'location' in dummy_req.headers:
                    final_video_url = dummy_req.headers['location']
            except Exception:
                pass  # Use original URL if redirect check fails
        
        return final_video_url

    def _extract_pssh_from_mpd(self, mpd_url: str) -> Tuple[Optional[PsshRecord], Optional[str], Dict]:
        """Extract PSSH data and DRM metadata from MPD manifest."""
        mpd_text, drm_info = None, {}
        try:
            result = extract_first_pssh(mpd_url, include_mpd=True)
            pssh_record, mpd_bytes = (result if isinstance(result, tuple) else (result, None))

            if mpd_bytes:
                mpd_text = mpd_bytes.decode('utf-8', errors='ignore')
            if mpd_text:
                try:
                    drm_info = extract_drm_info_from_mpd(mpd_text) or {}
                except Exception as e:
                    logger.warning(f"⚠️ [SixPlay] Failed to parse DRM info: {e}")

            if not pssh_record and drm_info.get('widevine_pssh'):
                try:
                    raw = base64.b64decode(drm_info['widevine_pssh'])
                    pssh_record = PsshRecord(source='drm_info', parent='ContentProtection', base64_text=drm_info['widevine_pssh'], raw_length=len(raw), system_id='edef8ba9-79d6-4ace-a3c8-27dcd51d21ed')
                except Exception:
                    pass

            if pssh_record:
                logger.debug(f"✅ [SixPlay] PSSH extracted successfully:")
                logger.debug(f"📋   Base64 PSSH: {pssh_record.base64_text}")
            else:
                logger.warning(f"⚠️ [SixPlay] No PSSH found in MPD manifest")
            return pssh_record, mpd_text, drm_info
        except Exception as e:
            logger.error(f"❌ [SixPlay] Error extracting PSSH from MPD: {e}")
            return None, None, {}

    def _extract_widevine_key(self, pssh_value: str, drm_token: str) -> Optional[str]:
        """Extract Widevine decryption key using local pywidevine CDM.

        Sends the license challenge directly to lic.drmtoday.com with the
        supplied DRM token — no external key-extraction API required.
        Returns a ``kid:key_hex`` string on success, or None on failure.
        """
        try:
            from pywidevine.cdm import Cdm
            from pywidevine.device import Device
            from pywidevine.pssh import PSSH
        except ImportError:
            logger.error("❌ [SixPlay] pywidevine not installed — cannot extract Widevine key")
            return None

        # Locate the WVD device file
        wvd_candidates = [
            "app/providers/fr/device.wvd",
            "./device.wvd",
            os.path.expanduser("~/.pywidevine/device.wvd"),
        ]
        device = None
        for path in wvd_candidates:
            if os.path.exists(path):
                try:
                    device = Device.load(path)
                    logger.debug(f"✅ [SixPlay] WVD device loaded from {path}")
                    break
                except Exception as load_err:
                    logger.warning(f"⚠️ [SixPlay] Failed to load WVD {path}: {load_err}")

        if not device:
            logger.error("❌ [SixPlay] No valid WVD device file found")
            return None

        session_id = None
        try:
            logger.debug(f"🔑 [SixPlay] Extracting Widevine key (local pywidevine)...")
            logger.debug(f"📋   PSSH: {pssh_value[:50]}...")

            pssh = PSSH(pssh_value)
            cdm = Cdm.from_device(device)
            session_id = cdm.open()

            challenge = cdm.get_license_challenge(session_id, pssh)
            logger.debug(f"📋 [SixPlay] License challenge generated: {len(challenge)} bytes")

            license_url = "https://lic.drmtoday.com/license-proxy-widevine/cenc/?specConform=true"
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/59.0.3041.0 Safari/537.36",
                "x-dt-auth-token": drm_token,
                "Content-Type": "application/octet-stream",
            }

            response = requests.post(license_url, data=challenge, headers=headers, timeout=15)
            logger.debug(f"📋 [SixPlay] License server: {response.status_code}")

            if response.status_code != 200:
                logger.error(f"❌ [SixPlay] License server error {response.status_code}: {response.text[:300]}")
                return None

            cdm.parse_license(session_id, response.content)

            for key in cdm.get_keys(session_id):
                if hasattr(key, 'type') and key.type == 'CONTENT':
                    kid_hex = str(key.kid).replace('-', '')
                    key_hex = key.key.hex()
                    logger.debug(f"✅ [SixPlay] Widevine key extracted: {kid_hex}:{key_hex}")
                    return f"{kid_hex}:{key_hex}"

            logger.error("❌ [SixPlay] No CONTENT keys found in license response")
            return None

        except Exception as e:
            logger.error(f"❌ [SixPlay] Widevine key extraction failed: {e}")
            return None
        finally:
            if session_id is not None and 'cdm' in locals():
                try:
                    cdm.close(session_id)
                except Exception:
                    pass

    def _print_download_command(self, video_url: str, decryption_key: str, content_id: str):
        """Print N_m3u8DL-RE download command with decryption key.
        
        Args:
            video_url: URL to the MPD manifest
            decryption_key: Widevine decryption key
            content_id: Content identifier for save name
        """
        try:
            # Clean content ID for filename
            clean_name = content_id.replace(":", "_").replace("/", "_").replace("\\", "_")
            
            # Truncate URL for display (keep first 100 chars)
            display_url = video_url[:100] + "..." if len(video_url) > 100 else video_url
            
            logger.debug(f"\n📥 N_m3u8DL-RE Download Command:")
            logger.debug(f'./N_m3u8DL-RE "{video_url}" --save-name "{clean_name}" --select-video best --select-audio all --select-subtitle all -mt -M format=mkv --log-level OFF --binary-merge --key {decryption_key}')
            logger.debug(f"\n🔗 URL: {display_url}")
            logger.debug(f"🔑 Key: {decryption_key}")
            logger.debug(f"💾 Save as: {clean_name}")
            
        except Exception as e:
            logger.error(f"❌ [SixPlay] Error printing download command: {e}")


    @staticmethod
    def _pad_base64(value: str) -> str:
        """Pad base64 strings to a valid length."""
        if value is None:
            return ''
        padding = (4 - len(value) % 4) % 4
        return value + ('=' * padding)

    def _normalize_key_id(self, key_id: Optional[str]) -> Optional[str]:
        """Return the key ID as 32-char lowercase hex if possible."""
        if not key_id:
            return None
        candidate = key_id.strip()
        if not candidate:
            return None
        try:
            return uuid.UUID(candidate).hex
        except Exception:
            pass
        candidate = candidate.replace('-', '').replace(' ', '')
        if re.fullmatch(r'[0-9a-fA-F]{32}', candidate):
            return candidate.lower()
        try:
            decoded = base64.urlsafe_b64decode(self._pad_base64(candidate))
            if len(decoded) == 16:
                return decoded.hex()
        except Exception:
            pass
        return None

    def _ensure_hex_key(self, key_value: Optional[str]) -> Optional[str]:
        """Coerce provided key data into a 32-character hex string."""
        if not key_value:
            return None
        candidate = key_value.strip().replace(' ', '')
        if not candidate:
            return None
        if re.fullmatch(r'[0-9a-fA-F]{32}', candidate):
            return candidate.lower()
        try:
            decoded = base64.urlsafe_b64decode(self._pad_base64(candidate))
            hex_value = decoded.hex()
            if len(hex_value) == 32:
                return hex_value
        except Exception:
            pass
        return None

    def _normalize_decryption_key(self, raw_key: Optional[str], key_id_hex: Optional[str]) -> Optional[str]:
        """Extract the matching hex key from various key string formats."""
        if not raw_key or not raw_key.strip(): return None
        value, target_kid = raw_key.strip(), key_id_hex.lower() if key_id_hex else None

        def match(kid, key):
            k_hex = self._ensure_hex_key(key)
            if not k_hex: return None
            if not target_kid: return k_hex
            norm_kid = self._normalize_key_id(kid)
            return k_hex if norm_kid and norm_kid.lower() == target_kid else None

        # Try JSON
        try:
            data = json.loads(value)
            keys = (data.get('keys') or []) if isinstance(data, dict) else (data if isinstance(data, list) else [])
            for item in (k for k in keys if isinstance(k, dict)):
                if (found := match(item.get('kid') or item.get('keyid'), item.get('k') or item.get('key'))): return found
            if len(keys) == 1 and isinstance(keys[0], dict) and (found := self._ensure_hex_key(keys[0].get('k') or keys[0].get('key'))): return found
        except json.JSONDecodeError: pass

        # Try text format
        normalized = value.replace('\r\n', ',').replace('\n', ',').replace('\r', ',').replace(';', ',').replace('|', ',')
        fallback = None
        for segment in (s.strip() for s in normalized.split(',') if s.strip()):
            if ':' in segment:
                kid_part, key_part = segment.split(':', 1)
                if (found := match(kid_part, key_part)): return found
            elif (candidate := self._ensure_hex_key(segment)) and not fallback:
                fallback = candidate
        return fallback

    @staticmethod
    def _hex_to_base64url(hex_value: Optional[str]) -> Optional[str]:
        """Convert hex strings to base64url without padding."""
        if not hex_value:
            return None
        try:
            raw = bytes.fromhex(hex_value)
            return base64.urlsafe_b64encode(raw).decode('utf-8').rstrip('=')
        except Exception:
            return None

    def _build_mediaflow_clearkey_stream(self, original_mpd_url: str, base_headers: Dict[str, str], key_id_hex: Optional[str], key_hex: Optional[str], is_live: bool = False) -> Optional[Dict]:
        """Create a MediaFlow ClearKey MPD stream if configuration allows."""
        if not key_id_hex or not key_hex: return None
        if not self.mediaflow_url or not self.mediaflow_password:
            logger.warning(f"⚠️ [SixPlay] MediaFlow configuration missing for ClearKey streaming")
            return None
        try:
            processed_mpd_url = get_processed_mpd_url_for_mediaflow(original_mpd_url, auth_token=self.login_token if self.login_token else None)
            mediaflow_headers = {'user-agent': base_headers.get('User-Agent', get_random_windows_ua()), 'origin': self.base_url, 'referer': self.base_url}
            if self.login_token: mediaflow_headers['authorization'] = f'Bearer {self.login_token}'

            extra = {'key_id': self._hex_to_base64url(key_id_hex) or key_id_hex, 'key': self._hex_to_base64url(key_hex) or key_hex}
            mf_url = build_mediaflow_url(base_url=self.mediaflow_url, password=self.mediaflow_password, destination_url=processed_mpd_url, endpoint='/proxy/mpd/manifest.m3u8', request_headers=mediaflow_headers, extra_params=extra)
            
            logger.debug(f"✅ [SixPlay] MediaFlow ClearKey URL prepared: {mf_url}")
            return {'url': mf_url, 'manifest_type': 'mpd', 'externalUrl': original_mpd_url, 'is_live': is_live}
        except Exception as e:
            logger.error(f"❌ [SixPlay] MediaFlow ClearKey setup failed: {e}")
            return None
    def _analyze_available_formats(self, video_assets: List[Dict]) -> Dict:
        """Analyze available video formats from assets and return format information"""
        formats = {'hls': {'available': False, 'asset_types': [], 'qualities': []}, 'mpd': {'available': False, 'asset_types': [], 'qualities': []}}
        for asset in video_assets:
            atype, qual = asset.get('type', ''), asset.get('video_quality', 'sd').lower()
            if 'http_h264' in atype:
                key = 'hls'
            elif 'dashcenc' in atype or 'mpd' in atype:
                key = 'mpd'
            else: continue
            
            formats[key]['available'] = True
            formats[key]['asset_types'].append(atype)
            if qual not in formats[key]['qualities']: formats[key]['qualities'].append(qual)
        return formats

    def _determine_best_format(self, available_formats: Dict, is_live: bool = False) -> Dict:
        """Determine the best format based on available options and content type"""
        format_prefs = {
            'hls': {'format_name': 'HLS', 'asset_type': 'http_h264', 'drm_required': False, 'description': 'HTTP Live Streaming (no DRM)'},
            'mpd': {'format_name': 'MPD/DASH', 'asset_type': 'usp_dashcenc_h264' if not is_live else 'delta_dashcenc_h264', 'drm_required': True, 'description': 'Dynamic Adaptive Streaming (DRM protected)'}
        }
        
        # Live prefers HLS, replay prefers MPD
        order = ['hls', 'mpd'] if is_live else ['mpd', 'hls']
        # Also try fallback order if preferred not available
        for fmt in order + [f for f in ['hls', 'mpd'] if f not in order]:
            if available_formats.get(fmt, {}).get('available'):
                qualities = available_formats[fmt].get('qualities', [])
                pref = format_prefs[fmt]
                return {
                    'format_type': fmt, 'format_name': pref['format_name'], 'asset_type': pref['asset_type'],
                    'quality': 'hd' if 'hd' in qualities else 'sd',
                    'drm_required': pref['drm_required'], 'description': pref['description']
                }
        
        # Ultimate fallback
        return {'format_type': 'hls', 'format_name': 'HLS', 'asset_type': 'http_h264', 'quality': 'sd', 'drm_required': False, 'description': 'Default HLS fallback'}

    def _get_show_api_metadata(self, show_id: str, show_info: Dict) -> Dict:
        """Get show metadata from 6play API using program ID from Algolia search"""
        try:
            program_id = show_info.get('api_id')
            if program_id:
                logger.debug(f"✅ [SixPlay] Using hardcoded program ID for metadata: {program_id}")
            else:
                program_id = self._find_program_id(show_id)
            
            if not program_id:
                logger.debug(f"[SixPlay] No program ID found for {show_id}, cannot get metadata")
                return {}
            
            url = f"https://android.middleware.6play.fr/6play/v2/platforms/m6group_androidmob/services/6play/programs/{program_id}?with=links,subcats,rights"
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
            response = self.session.get(url, headers=self._merge_ip_headers(headers), timeout=10)
            
            if response.status_code == 200:
                program_data = response.json()
                fanart = None
                
                if 'images' in program_data:
                    # Look for fanart in specific image types
                    for img in program_data['images']:
                        external_key = img.get('external_key', '')
                        if external_key and not fanart and img.get('role') in ['backdropWide', 'backdropTall', 'banner_31']:
                            fanart = f"https://images.6play.fr/v1/images/{external_key}/raw"
                    
                    # Fallback to other image types
                    if not fanart:
                        for img in program_data['images']:
                            if img.get('role') in ['cover', 'portrait', 'square'] and img.get('external_key'):
                                fanart = f"https://images.6play.fr/v1/images/{img['external_key']}/raw"
                                break
                
                logger.debug(f"✅ [SixPlay] Found show metadata for {show_id}: fanart={fanart[:50] if fanart else 'N/A'}...")
                return {"fanart": fanart}
            else:
                logger.error(f"❌ [SixPlay] Failed to get program data for {show_id}: {response.status_code}")
            return {}
        except Exception as e:
            logger.error(f"❌ [SixPlay] Error fetching show metadata for {show_id}: {e}")
            return {}
    
    def _find_program_id(self, show_id: str) -> Optional[str]:
        """Find the program ID for a given show using the 6play programs API.

        Strategy:
        1. Look up the show's display name from programs.json (e.g. "66 minutes").
        2. Query the 6play programs API filtered by the first letter of that name
           (inspired by the Catch-up TV & More plugin's URL_ALL_PROGRAMS approach).
        3. Match the API's ``title`` against the show name (exact then partial).
        4. Fall back to Algolia search if the programs API fails.
        """

        # ------------------------------------------------------------------
        # Resolve the human-readable show name from programs.json
        # ------------------------------------------------------------------
        show_name = None
        if show_id in self.shows:
            show_name = self.shows[show_id].get('name')
        if not show_name:
            # Derive a reasonable search term from the slug
            show_name = show_id.replace('-', ' ')

        def _normalize(s: str) -> str:
            """Lowercase, collapse hyphens/colons/extra spaces for comparison."""
            return re.sub(r'\s+', ' ', s.lower().replace('-', ' ').replace(':', ' ')).strip()

        norm_search = _normalize(show_name)

        # ------------------------------------------------------------------
        # Strategy 1 – 6play programs API (universal, no hard-coded mapping)
        # ------------------------------------------------------------------
        try:
            first_letter = show_name[0].lower() if show_name else 'a'
            # '@' is used by the API for names starting with a digit / special char
            if not first_letter.isalpha():
                first_letter = '@'

            programs_url = (
                "https://android.middleware.6play.fr/6play/v2/platforms/"
                "m6group_androidmob/services/6play/programs"
            )
            params = {
                'limit': '999',
                'offset': '0',
                'csa': '6',
                'firstLetter': first_letter,
                'with': 'rights',
            }
            headers = {
                'User-Agent': get_random_windows_ua(),
                'x-customer-name': 'm6web',
            }

            logger.debug(f"🔍 [SixPlay] Searching programs API for '{show_name}' (letter={first_letter})")
            response = self.session.get(
                programs_url,
                params=params,
                headers=self._merge_ip_headers(headers),
                timeout=10,
            )

            if response.status_code == 200:
                programs = response.json()
                partial_match = None

                for prog in programs:
                    prog_title = prog.get('title', '')
                    prog_id = str(prog.get('id', ''))
                    norm_title = _normalize(prog_title)

                    if norm_title == norm_search:
                        logger.debug(f"✅ [SixPlay] Programs API exact match: '{prog_title}' (ID: {prog_id})")
                        return prog_id
                    if not partial_match and (norm_search in norm_title or norm_title in norm_search):
                        partial_match = (prog_id, prog_title)

                if partial_match:
                    logger.debug(f"✅ [SixPlay] Programs API partial match: '{partial_match[1]}' (ID: {partial_match[0]})")
                    return partial_match[0]

                logger.warning(f"⚠️ [SixPlay] Programs API returned no match for '{show_name}', trying Algolia…")
            else:
                logger.warning(f"⚠️ [SixPlay] Programs API HTTP {response.status_code}, trying Algolia…")
        except Exception as e:
            logger.error(f"⚠️ [SixPlay] Programs API error: {e}, trying Algolia…")

        # ------------------------------------------------------------------
        # Strategy 2 – Algolia search (fallback)
        # ------------------------------------------------------------------
        try:
            algolia_hosts = [
                'nhacvivxxk-dsn.algolia.net',
                'NHACVIVXXK-1.algolianet.com',
                'NHACVIVXXK-2.algolianet.com',
                'NHACVIVXXK-3.algolianet.com',
            ]
            search_headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:140.0) Gecko/20100101 Firefox/140.0',
                'Content-Type': 'application/x-www-form-urlencoded',
                'x-algolia-api-key': '6ef59fc6d78ac129339ab9c35edd41fa',
                'x-algolia-application-id': 'NHACVIVXXK',
            }
            search_data = {
                'requests': [{
                    'indexName': 'rtlmutu_prod_bedrock_layout_items_v2_m6web_main',
                    'query': show_name,
                    'params': 'clickAnalytics=true&hitsPerPage=10&facetFilters=[["metadata.item_type:program"], ["metadata.platforms_assets:m6group_web"]]',
                }]
            }

            response = None
            for host in algolia_hosts:
                try:
                    logger.debug(f"🔍 [SixPlay] Trying Algolia host: {host}")
                    response = requests.post(
                        f'https://{host}/1/indexes/*/queries',
                        headers=self._merge_ip_headers(search_headers),
                        json=search_data,
                        timeout=5,
                    )
                    if response.status_code == 200:
                        break
                except Exception as e:
                    logger.error(f"⚠️ [SixPlay] Error with Algolia host {host}: {e}")

            if not response or response.status_code != 200:
                logger.error(f"❌ [SixPlay] All Algolia hosts failed or returned error")
                return None

            data = response.json()
            partial_match = None

            for result in data.get('results', []):
                for hit in result.get('hits', []):
                    title = hit['item']['itemContent']['title']
                    program_id = str(hit['content']['id'])
                    norm_title = _normalize(title)
                    if norm_title == norm_search:
                        logger.debug(f"✅ [SixPlay] Algolia exact match: '{title}' (ID: {program_id})")
                        return program_id
                    if not partial_match and (norm_search in norm_title or norm_title in norm_search):
                        partial_match = (program_id, title)

            if partial_match:
                logger.debug(f"✅ [SixPlay] Algolia partial match: '{partial_match[1]}' (ID: {partial_match[0]})")
                return partial_match[0]

            logger.error(f"❌ [SixPlay] No program ID found for show '{show_name}' (slug={show_id})")
            return None
        except Exception as e:
            logger.error(f"❌ [SixPlay] Error finding program ID for {show_id}: {e}")
            return None
    
    def _get_show_episodes(self, program_id: str) -> List[Dict]:
        """Get episodes for a specific program using 6play API"""
        try:
            # Use the same API call as the reference plugin
            url = f"https://android.middleware.6play.fr/6play/v2/platforms/m6group_androidmob/services/6play/programs/{program_id}/videos?csa=6&with=clips,freemiumpacks&type=vi&limit=999&offset=0"
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            response = self.session.get(url, headers=self._merge_ip_headers(headers), timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                episodes = []
                
                for video in data:
                    episode_info = self._parse_episode(video, len(episodes) + 1)
                    if episode_info:
                        episodes.append(episode_info)
                
                return episodes
            else:
                logger.error(f"❌ [SixPlay] Failed to get episodes: {response.status_code}")
                return []
                
        except Exception as e:
            logger.error(f"❌ [SixPlay] Error getting show episodes: {e}")
            return []
    
    def _parse_episode(self, video: Dict, episode_number: int) -> Optional[Dict]:
        """Parse episode data from 6play API response"""
        try:
            video_id, title, description, duration = str(video.get('id', '')), video.get('title', ''), video.get('description', ''), video.get('duration', '')
            poster = fanart = None
            
            if 'images' in video:
                for img in video['images']:
                    if img.get('role') in ['vignette', 'carousel'] and img.get('external_key'):
                        poster = fanart = f"https://images.6play.fr/v1/images/{img['external_key']}/raw"
                        break
            
            broadcast_date, released = None, ""
            # Try clips[0].product.first_diffusion first
            if video.get('clips'):
                first_diff = video['clips'][0].get('product', {}).get('first_diffusion', '')
                if first_diff:
                    broadcast_date = first_diff[:10]
                    released = first_diff.replace(' ', 'T') + '.000Z'
            
            # Fallback to publication_date
            if not released and video.get('publication_date'):
                pub_date = video['publication_date']
                broadcast_date = broadcast_date or pub_date[:10]
                released = pub_date.replace(' ', 'T') + '.000Z'
            
            episode_info = {"id": f"cutam:fr:6play:episode:{video_id}", "type": "episode", "title": title, "description": description, "poster": poster, "fanart": fanart, "episode": episode_number, "duration": duration, "broadcast_date": broadcast_date}
            if released:
                episode_info["released"] = released
            return episode_info
        except Exception as e:
            logger.error(f"❌ [SixPlay] Error parsing episode: {e}")
            return None

    def resolve_stream(self, stream_id: str) -> Optional[Dict]:
        """Resolve stream URL for a given stream ID.

        Supported IDs:
        - `cutam:fr:6play:episode:<video_id>` → replay episode
        - `cutam:fr:6play:<channel>` → live channel (e.g., m6, w9, 6ter)
        - Raw `<video_id>` (treated as 6play episode id)
        """
        try:
            if not stream_id:
                return None

            if ":episode:" in stream_id or stream_id.startswith("episode:"):
                return self.get_episode_stream_url(stream_id)

            # Live channel pattern
            if stream_id.startswith("cutam:fr:6play:") and ":episode:" not in stream_id:
                return self.get_channel_stream_url(stream_id)

            # If it's a bare 6play video id, treat as episode
            if re.fullmatch(r"[A-Za-z0-9_]+", stream_id):
                return self.get_episode_stream_url(stream_id)

            logger.error(f"❌ [SixPlay] Unrecognized stream id format: {stream_id}")
            return None
        except Exception as e:
            logger.error(f"❌ [SixPlay] resolve_stream error for {stream_id}: {e}")
            return None
