#!/usr/bin/env python3
"""
6play provider implementation
Hybrid approach with robust error handling, fallbacks, and retry logic
"""

import json
import requests
import time
import re
import random
import uuid
import os
import base64
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Optional, Tuple
from app.utils.credentials import get_provider_credentials, load_credentials
from app.auth.sixplay_auth import SixPlayAuth
from app.utils.metadata import metadata_processor
from app.utils.client_ip import merge_ip_headers
from app.utils.sixplay_mpd_processor import create_mediaflow_compatible_mpd, extract_drm_info_from_mpd
from app.utils.mediaflow import build_mediaflow_url
from app.utils.mpd_server import get_processed_mpd_url_for_mediaflow
from app.providers.fr.extract_pssh import extract_first_pssh, PsshRecord
from app.utils.nm3u8_drm_processor import process_drm_simple
from app.utils.safe_print import safe_print
from app.utils.proxy_config import get_proxy_config
from app.utils.user_agent import get_random_windows_ua
from app.utils.programs_loader import get_programs_for_provider
from app.providers.base_provider import BaseProvider

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

    @property
    def provider_key(self) -> str:
        return "6play"
    
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
                safe_print("✅ [SixPlay] Using preset 6play account_id/login_token from credentials")
                return True

            # If no credentials provided, allow unauthenticated access (HLS-only paths may still work)
            if not username or not password:
                safe_print("⚠️ [SixPlay] No 6play credentials found; continuing without authentication")
                safe_print("⚠️ [SixPlay] Note: DRM content will not be accessible without valid credentials")
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
                    safe_print(f"✅ [SixPlay] 6play authentication succeeded")
                    safe_print(f"🔑 [SixPlay] Account ID: {self.account_id}")
                    safe_print(f"🔑 [SixPlay] JWT Token: {self.login_token[:20]}...")
                    return True

            safe_print("❌ [SixPlay] 6play authentication failed")
            # Still mark as handled to allow non-DRM content access
            self._authenticated = True
            return False
        except Exception as e:
            safe_print(f"❌ [SixPlay] Authentication error: {e}")
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
                safe_print(f"⚠️ [SixPlay] Warning: Could not fetch API metadata for {show_id}: {e}")
                return (show_id, None)
        
        try:
            with ThreadPoolExecutor(max_workers=5) as executor:
                api_results = dict(executor.map(fetch_api_metadata, self.shows.items()))
            
            for show_id, show_info in self.shows.items():
                show_metadata = self._build_show_metadata(show_id, show_info)
                api_metadata = api_results.get(show_id)
                if api_metadata and 'fanart' in api_metadata:
                    show_metadata['fanart'] = api_metadata['fanart']
                shows.append(show_metadata)
        except Exception as e:
            safe_print(f"❌ [SixPlay] Error fetching show metadata: {e}")
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
            safe_print(f"🔍 [SixPlay] Getting episodes for 6play show: {actual_show_id}")
            
            # Use the same approach as the reference plugin
            # First, check if we have the program ID in our configuration (robustness fix)
            program_id = None
            if actual_show_id in self.shows:
                program_id = self.shows[actual_show_id].get('api_id')
                if program_id:
                    safe_print(f"✅ [SixPlay] Using hardcoded program ID: {program_id}")

            if not program_id:
                # First, we need to find the program ID for the show
                program_id = self._find_program_id(actual_show_id)
            
            if not program_id:
                safe_print(f"❌ [SixPlay] No program ID found for show: {actual_show_id}")
                return []
            
            # Get episodes using the program ID
            episodes = self._get_show_episodes(program_id)
            
            if episodes:
                # Sort episodes by released date ascending (oldest first, newest last)
                # Stremio expects videos sorted chronologically with newest episode having highest number
                episodes.sort(key=lambda ep: ep.get('released', '') or ep.get('broadcast_date', '') or '')
                
                # Re-number episodes after sorting (1, 2, 3... with 1 being oldest)
                for i, ep in enumerate(episodes):
                    ep['episode'] = i + 1
                
                safe_print(f"✅ [SixPlay] Found {len(episodes)} episodes for {actual_show_id} (sorted chronologically)")
            else:
                safe_print(f"⚠️ [SixPlay] No episodes found for {actual_show_id}")
            
            return episodes
            
        except Exception as e:
            safe_print(f"❌ [SixPlay] Error getting episodes for {actual_show_id}: {e}")
            return []
    def _check_processed_file(self, episode_id: str) -> Optional[Dict]:
        """Check if processed file exists in RD or processor URL. Returns stream dict if found."""
        proxy_config = get_proxy_config()
        processor_url = proxy_config.get_proxy('nm3u8_processor')
        if not processor_url:
            safe_print("❌ [SixPlay] ERROR: nm3u8_processor not configured in credentials.json")
            return None
        
        safe_print(f"✅ [SixPlay] Using processor API: {processor_url}")
        processed_filename = f"{episode_id}.mp4"
        processed_url = f"{processor_url}/stream/{processed_filename}"
        safe_print(f"🔍 [SixPlay] Looking for processed file: {processed_filename}")
        
        # Check Real-Debrid folder first
        try:
            safe_print("🔍 [SixPlay] Loading credentials for Real-Debrid check...")
            all_creds = load_credentials()
            safe_print(f"✅ [SixPlay] Credentials loaded. Keys: {list(all_creds.keys())}")
            rd_folder = all_creds.get('realdebridfolder')
            safe_print(f"🔍 [SixPlay] Real-Debrid folder from credentials: {rd_folder}")
            
            if rd_folder:
                safe_print(f"🔍 [SixPlay] Checking if '{processed_filename}' is listed in RD folder...")
                try:
                    rd_headers = {
                        'User-Agent': get_random_windows_ua(),
                        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                        'Accept-Language': 'en-US,en;q=0.9,fr;q=0.8',
                        'Accept-Encoding': 'gzip, deflate, br',
                        'DNT': '1', 'Connection': 'keep-alive',
                        'Upgrade-Insecure-Requests': '1', 'Sec-Fetch-Dest': 'document',
                        'Sec-Fetch-Mode': 'navigate', 'Sec-Fetch-Site': 'none', 'Cache-Control': 'max-age=0'
                    }
                    folder_response = requests.get(rd_folder, headers=rd_headers, timeout=10)
                    safe_print(f"🔍 [SixPlay] RD Folder HTTP Status: {folder_response.status_code}")
                    
                    if folder_response.status_code == 200 and processed_filename in folder_response.text:
                        rd_file_url = rd_folder.rstrip('/') + '/' + processed_filename
                        safe_print(f"✅ [SixPlay] File '{processed_filename}' found in RD folder listing!")
                        safe_print(f"✅ [SixPlay] Returning RD URL: {rd_file_url}")
                        return {"url": rd_file_url, "manifest_type": "video", "title": "✅ [RD] DRM-Free Video", "filename": processed_filename}
                    else:
                        safe_print(f"⚠️ [SixPlay] File '{processed_filename}' NOT found in RD folder listing, will check processor_url")
                except requests.exceptions.Timeout:
                    safe_print(f"⚠️ [SixPlay] RD folder request timed out, checking processor_url...")
                except requests.exceptions.RequestException as e:
                    safe_print(f"❌ [SixPlay] RD folder request error: {e}, checking processor_url...")
            else:
                safe_print("⚠️ [SixPlay] Real-Debrid folder not configured in credentials, checking processor_url...")
        except Exception as e:
            safe_print(f"❌ [SixPlay] Error checking Real-Debrid: {e}")
            safe_print(f"🔍 [SixPlay] Proceeding to processor_url check as fallback...")
        
        # Check processor URL
        safe_print(f"🔍 [SixPlay] Checking processor_url location: {processed_url}")
        try:
            check_response = requests.head(processed_url, timeout=5)
            safe_print(f"🔍 [SixPlay] PROCESSOR URL HTTP Status: {check_response.status_code}")
            if check_response.status_code == 200:
                safe_print(f"✅ [SixPlay] Processed file already exists: {processed_url}")
                return {"url": processed_url, "manifest_type": "video", "title": "✅ DRM-Free Video", "filename": processed_filename}
            else:
                safe_print(f"⚠️ [SixPlay] PROCESSOR file not found (HTTP {check_response.status_code})")
        except Exception as e:
            safe_print(f"⚠️ [SixPlay] Error checking processor_url: {e}")
        
        return None

    def get_episode_stream_url(self, episode_id: str) -> Optional[Dict]:
        """Get stream URL for a specific 6play episode"""
        # Extract the actual episode ID from our format
        if "episode:" in episode_id:
            actual_episode_id = episode_id.split("episode:")[-1]
        else:
            actual_episode_id = episode_id
        
        try:
            safe_print(f"🔍 [SixPlay] Getting replay stream for 6play episode: {actual_episode_id}")

            # Check if processed file already exists (RD or processor)
            existing_file = self._check_processed_file(actual_episode_id)
            if existing_file:
                return existing_file

            # Lazy authentication - only authenticate when needed
            if not self._authenticated and not self._authenticate():
                safe_print("❌ [SixPlay] 6play authentication failed")
                return None
            
            # Use the same approach as the reference plugin for replay content
            headers_video_stream = {
                "User-Agent": get_random_windows_ua(),
            }
            headers_video_stream = merge_ip_headers(headers_video_stream)
            
            # Get video info using the same API call as the reference plugin
            url_json = f"https://android.middleware.6play.fr/6play/v2/platforms/m6group_androidmob/services/6play/videos/{actual_episode_id}?csa=6&with=clips,freemiumpacks"

            response = self.session.get(url_json, headers=headers_video_stream, timeout=10)
            token_response = None
            
            if response.status_code == 200:
                json_parser = response.json()
                safe_print(f"✅ [SixPlay] Video API response received for {actual_episode_id}")
                
                # Extract video assets (same as reference plugin)
                if 'clips' in json_parser and json_parser['clips']:
                    video_assets = json_parser['clips'][0].get('assets', [])
                    
                    if video_assets:
                        # Dynamic format detection - analyze available assets to determine best format
                        safe_print(f"🔍 Analyzing {len(video_assets)} available assets for optimal format...")
                        
                        # Analyze available asset types
                        available_formats = self._analyze_available_formats(video_assets)
                        safe_print(f"📊 Available formats: {available_formats}")
                        
                        # Determine best format based on server response and client capabilities
                        best_format = self._determine_best_format(available_formats)
                        safe_print(f"🎯 Selected format: {best_format}")
                        
                        # Get the stream URL for the selected format
                        final_video_url = self._get_final_video_url(video_assets, best_format['asset_type'])
                        
                        if final_video_url:
                            safe_print(f"✅ {best_format['format_name']} stream found: {final_video_url}")
                            
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
                                    safe_print(f"🔑 [SixPlay] MPD default_KID: {key_id_hex}")

                                drm_token = None
                                if self.account_id and self.login_token:
                                    try:
                                        payload_headers = {
                                            'X-Customer-Name': 'm6web',
                                            'X-Client-Release': '5.103.3',
                                            'Authorization': f'Bearer {self.login_token}',
                                        }

                                        complete_headers = merge_ip_headers(payload_headers)

                                        safe_print(f"📋 [SixPlay] DRM Token Request Headers:")
                                        for header_name, header_value in complete_headers.items():
                                            if header_name.lower() in ['authorization', 'x-auth-token', 'token']:
                                                masked_value = f"{header_value[:20]}..." if len(str(header_value)) > 20 else "***"
                                                safe_print(f"📋   {header_name}: {masked_value}")
                                            else:
                                                safe_print(f"📋   {header_name}: {header_value}")

                                        token_url = f"https://drm.6cloud.fr/v1/customers/m6web/platforms/m6group_web/services/m6replay/users/{self.account_id}/videos/{actual_episode_id}/upfront-token"
                                        safe_print(f"📋 [SixPlay] DRM Token URL: {token_url}")

                                        token_response = self.session.get(token_url, headers=complete_headers, timeout=10)

                                        safe_print(f"📋 [SixPlay] DRM Token Response:")
                                        safe_print(f"📋   Status Code: {token_response.status_code}")
                                        safe_print(f"📋   Response Headers: {dict(token_response.headers)}")

                                        if token_response.status_code == 200:
                                            token_data = token_response.json()
                                            drm_token = token_data["token"]
                                            safe_print(f"✅ [SixPlay] DRM token obtained successfully")
                                            safe_print(f"🔑 [SixPlay] DRM Token Value: {drm_token}")
                                        else:
                                            safe_print(f"❌ DRM token request failed: {token_response.status_code}")
                                            safe_print(f"📋   Response content: {token_response.text[:500]}...")
                                            safe_print(f"⚠️   Check your 6play credentials and authentication")

                                    except Exception as e:
                                        safe_print(f"❌ [SixPlay] DRM setup failed: {e}")

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
                                    safe_print(f"✅ [SixPlay] PSSH data included in stream response")

                                    if drm_token:
                                        raw_key = self._extract_widevine_key(pssh_record.base64_text, drm_token)
                                        if raw_key:
                                            normalized_key = self._normalize_decryption_key(raw_key, key_id_hex)
                                            if normalized_key:
                                                original_stream["decryption_key"] = normalized_key
                                                safe_print(f"✅ [SixPlay] Widevine decryption key included in stream response")

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
                                                safe_print("❌ Unable to normalize Widevine key for MediaFlow usage")
                                        else:
                                            safe_print("❌ CDRM did not return a Widevine key")
                                else:
                                    safe_print(f"⚠️ [SixPlay] No PSSH found in MPD manifest")

                                if drm_token:
                                    license_url = f"https://lic.drmtoday.com/license-proxy-widevine/cenc/|Content-Type=&User-Agent=Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/59.0.3041.0 Safari/537.36&Host=lic.drmtoday.com&x-dt-auth-token={drm_token}|R{{SSM}}|JBlicense"

                                    license_headers = {
                                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/59.0.3041.0 Safari/537.36"
                                    }

                                    safe_print("📋 [SixPlay] DRM License Information:")
                                    safe_print(f"📋   License URL: {license_url}")
                                    safe_print(f"📋   License Headers: {license_headers}")
                                    safe_print(f"📋   Video URL: {final_video_url}")

                                    safe_print("🔍 [SixPlay] Using direct DRM approach with license")

                                    original_stream.update({
                                        "licenseUrl": license_url,
                                        "licenseHeaders": license_headers,
                                        "drm_token": drm_token,
                                        "drm_protected": True
                                    })

                                    return original_stream
                                else:
                                    safe_print(f"⚠️ [SixPlay] No DRM token available - returning basic MPD with PSSH")
                                    return original_stream
                            else:
                                safe_print(f"⚠️ No {best_format['format_name']} streams found")
                        else:
                            safe_print("⚠️ No MPD streams found either")
                else:
                    safe_print(f"❌ 6play API error: {response.status_code}")
            else:
                safe_print(f"❌ 6play token error: {token_response.status_code}")
            
            # Fallback - return None to indicate failure
            return None

        except Exception as e:
            safe_print(f"❌ [SixPlay] Error getting stream for {actual_episode_id}: {e}")

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
                    safe_print(f"⚠️ [SixPlay] Failed to parse DRM info: {e}")

            if not pssh_record and drm_info.get('widevine_pssh'):
                try:
                    raw = base64.b64decode(drm_info['widevine_pssh'])
                    pssh_record = PsshRecord(source='drm_info', parent='ContentProtection', base64_text=drm_info['widevine_pssh'], raw_length=len(raw), system_id='edef8ba9-79d6-4ace-a3c8-27dcd51d21ed')
                except Exception:
                    pass

            if pssh_record:
                safe_print(f"✅ [SixPlay] PSSH extracted successfully:")
                safe_print(f"📋   Base64 PSSH: {pssh_record.base64_text}")
            else:
                safe_print(f"⚠️ [SixPlay] No PSSH found in MPD manifest")
            return pssh_record, mpd_text, drm_info
        except Exception as e:
            safe_print(f"❌ [SixPlay] Error extracting PSSH from MPD: {e}")
            return None, None, {}

    def _extract_widevine_key(self, pssh_value: str, drm_token: str) -> Optional[str]:
        """Extract Widevine decryption key using CDRM API."""
        try:
            safe_print(f"🔑 [SixPlay] Extracting Widevine decryption key...")
            headers_data = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/59.0.3041.0 Safari/537.36', 'x-dt-auth-token': drm_token}
            payload = {'pssh': pssh_value, 'licurl': 'https://lic.drmtoday.com/license-proxy-widevine/cenc/?specConform=true', 'headers': str(headers_data)}
            
            safe_print(f"📋 [SixPlay] CDRM API request payload:")
            safe_print(f"📋   PSSH: {pssh_value[:50]}...")
            safe_print(f"📋   License URL: {payload['licurl']}")
            safe_print(f"📋   Headers: {headers_data}")
            
            response = requests.post('https://cdrm-project.com/api/decrypt', headers={'Content-Type': 'application/json'}, json=payload, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                if 'message' in result:
                    safe_print(f"✅ [SixPlay] Widevine decryption key extracted successfully:")
                    safe_print(f"🔑   Key: {result['message']}")
                    return result['message']
                safe_print(f"❌ [SixPlay] No decryption key in CDRM response: {result}")
                return None
            safe_print(f"❌ [SixPlay] CDRM API error: {response.status_code}")
            safe_print(f"📋   Response: {response.text[:500]}...")
            return None
        except Exception as e:
            safe_print(f"❌ [SixPlay] Error extracting Widevine key: {e}")
            return None

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
            
            safe_print(f"\n📥 N_m3u8DL-RE Download Command:")
            safe_print(f'./N_m3u8DL-RE "{video_url}" --save-name "{clean_name}" --select-video best --select-audio all --select-subtitle all -mt -M format=mkv --log-level OFF --binary-merge --key {decryption_key}')
            safe_print(f"\n🔗 URL: {display_url}")
            safe_print(f"🔑 Key: {decryption_key}")
            safe_print(f"💾 Save as: {clean_name}")
            
        except Exception as e:
            safe_print(f"❌ [SixPlay] Error printing download command: {e}")


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
            safe_print(f"⚠️ [SixPlay] MediaFlow configuration missing for ClearKey streaming")
            return None
        try:
            processed_mpd_url = get_processed_mpd_url_for_mediaflow(original_mpd_url, auth_token=self.login_token if self.login_token else None)
            mediaflow_headers = {'user-agent': base_headers.get('User-Agent', get_random_windows_ua()), 'origin': self.base_url, 'referer': self.base_url}
            if self.login_token: mediaflow_headers['authorization'] = f'Bearer {self.login_token}'

            extra = {'key_id': self._hex_to_base64url(key_id_hex) or key_id_hex, 'key': self._hex_to_base64url(key_hex) or key_hex}
            mf_url = build_mediaflow_url(base_url=self.mediaflow_url, password=self.mediaflow_password, destination_url=processed_mpd_url, endpoint='/proxy/mpd/manifest.m3u8', request_headers=mediaflow_headers, extra_params=extra)
            
            safe_print(f"✅ [SixPlay] MediaFlow ClearKey URL prepared: {mf_url}")
            return {'url': mf_url, 'manifest_type': 'mpd', 'externalUrl': original_mpd_url, 'is_live': is_live}
        except Exception as e:
            safe_print(f"❌ [SixPlay] MediaFlow ClearKey setup failed: {e}")
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
                safe_print(f"✅ [SixPlay] Using hardcoded program ID for metadata: {program_id}")
            else:
                program_id = self._find_program_id(show_id)
            
            if not program_id:
                safe_print(f"[SixPlay] No program ID found for {show_id}, cannot get metadata")
                return {}
            
            url = f"https://android.middleware.6play.fr/6play/v2/platforms/m6group_androidmob/services/6play/programs/{program_id}?with=links,subcats,rights"
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
            response = self.session.get(url, headers=merge_ip_headers(headers), timeout=10)
            
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
                
                safe_print(f"✅ [SixPlay] Found show metadata for {show_id}: fanart={fanart[:50] if fanart else 'N/A'}...")
                return {"fanart": fanart}
            else:
                safe_print(f"❌ [SixPlay] Failed to get program data for {show_id}: {response.status_code}")
            return {}
        except Exception as e:
            safe_print(f"❌ [SixPlay] Error fetching show metadata for {show_id}: {e}")
            return {}
    
    def _find_program_id(self, show_id: str) -> Optional[str]:
        """Find the program ID for a given show ID using Algolia search"""
        try:
            algolia_hosts = ['nhacvivxxk-dsn.algolia.net', 'NHACVIVXXK-1.algolianet.com', 'NHACVIVXXK-2.algolianet.com', 'NHACVIVXXK-3.algolianet.com']
            search_headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:140.0) Gecko/20100101 Firefox/140.0',
                'Content-Type': 'application/x-www-form-urlencoded',
                'x-algolia-api-key': '6ef59fc6d78ac129339ab9c35edd41fa', 'x-algolia-application-id': 'NHACVIVXXK',
            }
            show_search_mapping = {'capital': 'Capital', '66-minutes': '66 minutes', '66-minutes-le-doc': '66 minutes : le doc', 'zone-interdite': 'Zone interdite', 'enquete-exclusive': 'Enquête exclusive'}
            search_term = show_search_mapping.get(show_id, show_id)
            search_data = {'requests': [{'indexName': 'rtlmutu_prod_bedrock_layout_items_v2_m6web_main', 'query': search_term, 'params': 'clickAnalytics=true&hitsPerPage=10&facetFilters=[["metadata.item_type:program"], ["metadata.platforms_assets:m6group_web"]]'}]}
            
            response = None
            for host in algolia_hosts:
                try:
                    safe_print(f"🔍 [SixPlay] Trying Algolia host: {host}")
                    response = requests.post(f'https://{host}/1/indexes/*/queries', headers=merge_ip_headers(search_headers), json=search_data, timeout=5)
                    if response.status_code == 200:
                        break
                except Exception as e:
                    safe_print(f"⚠️ [SixPlay] Error with Algolia host {host}: {e}")
            
            if not response or response.status_code != 200:
                safe_print(f"❌ [SixPlay] All Algolia hosts failed or returned error")
                return None
            
            data = response.json()
            partial_match = None
            for result in data.get('results', []):
                for hit in result.get('hits', []):
                    title = hit['item']['itemContent']['title']
                    program_id = str(hit['content']['id'])
                    if title.lower() == search_term.lower():
                        safe_print(f"✅ [SixPlay] Found exact match for {show_id}: '{title}' (ID: {program_id})")
                        return program_id
                    if not partial_match and search_term.lower() in title.lower():
                        partial_match = (program_id, title)
            
            if partial_match:
                safe_print(f"✅ [SixPlay] Found partial match for {show_id}: '{partial_match[1]}' (ID: {partial_match[0]})")
                return partial_match[0]
            
            safe_print(f"❌ [SixPlay] No program ID found for show {show_id}")
            return None
        except Exception as e:
            safe_print(f"❌ [SixPlay] Error finding program ID for {show_id}: {e}")
            return None
    
    def _get_show_episodes(self, program_id: str) -> List[Dict]:
        """Get episodes for a specific program using 6play API"""
        try:
            # Use the same API call as the reference plugin
            url = f"https://android.middleware.6play.fr/6play/v2/platforms/m6group_androidmob/services/6play/programs/{program_id}/videos?csa=6&with=clips,freemiumpacks&type=vi&limit=999&offset=0"
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            response = self.session.get(url, headers=merge_ip_headers(headers), timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                episodes = []
                
                for video in data:
                    episode_info = self._parse_episode(video, len(episodes) + 1)
                    if episode_info:
                        episodes.append(episode_info)
                
                return episodes
            else:
                safe_print(f"❌ [SixPlay] Failed to get episodes: {response.status_code}")
                return []
                
        except Exception as e:
            safe_print(f"❌ [SixPlay] Error getting show episodes: {e}")
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
            safe_print(f"❌ [SixPlay] Error parsing episode: {e}")
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

            safe_print(f"❌ [SixPlay] Unrecognized stream id format: {stream_id}")
            return None
        except Exception as e:
            safe_print(f"❌ [SixPlay] resolve_stream error for {stream_id}: {e}")
            return None
