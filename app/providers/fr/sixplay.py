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
from typing import Dict, List, Optional, Tuple
from app.utils.credentials import get_provider_credentials
from app.auth.sixplay_auth import SixPlayAuth
from app.utils.metadata import metadata_processor
from app.utils.client_ip import merge_ip_headers
from app.utils.sixplay_mpd_processor import create_mediaflow_compatible_mpd, extract_drm_info_from_mpd
from app.utils.mediaflow import build_mediaflow_url
from app.utils.mpd_server import get_processed_mpd_url_for_mediaflow
from app.providers.fr.extract_pssh import extract_first_pssh, PsshRecord
from app.utils.nm3u8_drm_processor import process_drm_simple

def get_random_windows_ua():
    """Generates a random Windows User-Agent string."""
    # A selection of common Windows User-Agent strings
    user_agents = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/109.0.1518.78',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Firefox/109.0',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/109.0'
    ]
    return random.choice(user_agents)

class SixPlayProvider:
    """6play provider implementation with robust error handling and fallbacks"""
    
    def __init__(self):
        self.credentials = get_provider_credentials('6play')
        self.base_url = "https://www.6play.fr"
        self.api_url = "https://android.middleware.6play.fr/6play/v2/platforms/m6group_androidmob/services/6play"
        self.auth_url = "https://login.6play.fr/accounts.login"
        self.token_url = "https://6cloud.fr/v1/customers/m6web/platforms/m6group_web/services/6play/users"
        self.live_url = "https://android.middleware.6play.fr/6play/v2/platforms/m6group_androidmob/services/6play/live"
        self.api_key = "3_hH5KBv25qZTd_sURpixbQW6a4OsiIzIEF2Ei_2H7TXTGLJb_1Hr4THKZianCQhWK"
        
        # MediaFlow config for enhanced DRM compatibility (optional)
        self.mediaflow_url = os.getenv('MEDIAFLOW_PROXY_URL')
        self.mediaflow_password = os.getenv('MEDIAFLOW_API_PASSWORD')
        
        # Fallback to credentials file
        if not self.mediaflow_url or not self.mediaflow_password:
            mediaflow_creds = get_provider_credentials('mediaflow')
            if not self.mediaflow_url:
                self.mediaflow_url = mediaflow_creds.get('url')
            if not self.mediaflow_password:
                self.mediaflow_password = mediaflow_creds.get('password')
        
        # Final fallback for local development
        if not self.mediaflow_url:
            self.mediaflow_url = 'http://localhost:8888'
        
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': get_random_windows_ua()
        })
        self.account_id = None
        self.login_token = None
        self._authenticated = False

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
                print("[SixPlayProvider] Using preset 6play account_id/login_token from credentials")
                return True

            # If no credentials provided, allow unauthenticated access (HLS-only paths may still work)
            if not username or not password:
                print("[SixPlayProvider] No 6play credentials found; continuing without authentication")
                print("[SixPlayProvider] Note: DRM content will not be accessible without valid credentials")
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
                    print(f"[SixPlayProvider] 6play authentication succeeded")
                    print(f"[SixPlayProvider] Account ID: {self.account_id}")
                    print(f"[SixPlayProvider] JWT Token: {self.login_token[:20]}...")
                    return True

            print("[SixPlayProvider] 6play authentication failed")
            # Still mark as handled to allow non-DRM content access
            self._authenticated = True
            return False
        except Exception as e:
            print(f"[SixPlayProvider] Authentication error: {e}")
            # Mark as handled but authentication failed
            self._authenticated = True
            return False
    
    def _safe_api_call(self, url: str, params: Dict = None, headers: Dict = None, data: Dict = None, method: str = 'GET', max_retries: int = 3) -> Optional[Dict]:
        """Make a safe API call with retry logic and error handling"""
        for attempt in range(max_retries):
            try:
                # Rotate User-Agent for each attempt
                current_headers = headers or {}
                current_headers['User-Agent'] = get_random_windows_ua()
                # Forward viewer IP to upstream
                current_headers = merge_ip_headers(current_headers)
                
                print(f"[6play] API call attempt {attempt + 1}/{max_retries}: {url}")
                if params:
                    print(f"[6play] Request params: {params}")
                if headers:
                    print(f"[6play] Request headers (pre-merge): {headers}")
                try:
                    print(f"[6play] Request headers (effective): {current_headers}")
                except Exception:
                    pass
                
                if method.upper() == 'POST':
                    if data:
                        response = self.session.post(url, params=params, headers=current_headers, json=data, timeout=15)
                    else:
                        response = self.session.post(url, params=params, headers=current_headers, timeout=15)
                else:
                    response = self.session.get(url, params=params, headers=current_headers, timeout=15)
                
                if response.status_code == 200:
                    # Log response details for debugging
                    print(f"[6play] Response headers: {dict(response.headers)}")
                    print(f"[6play] Content-Type: {response.headers.get('content-type', 'Not set')}")
                    
                    # Try to parse JSON with multiple strategies
                    try:
                        return response.json()
                    except json.JSONDecodeError as e:
                        print(f"[6play] JSON parse error on attempt {attempt + 1}: {e}")
                        print(f"[6play] Error position: line {e.lineno}, column {e.colno}, char {e.pos}")
                        
                        # Log the raw response for debugging
                        text = response.text
                        print(f"[6play] Raw response length: {len(text)} characters")
                        print(f"[6play] Raw response (first 500 chars): {text[:500]}")
                        
                        # Log the problematic area around the error
                        if e.pos > 0:
                            start = max(0, e.pos - 50)
                            end = min(len(text), e.pos + 50)
                            print(f"[6play] Context around error (chars {start}-{end}): {text[start:end]}")
                        
                        # Strategy 1: Try to fix common JSON issues
                        if "'" in text and '"' not in text:
                            # Replace single quotes with double quotes
                            text = text.replace("'", '"')
                            try:
                                return json.loads(text)
                            except:
                                pass
                        
                        # Strategy 2: Try to fix unquoted property names
                        try:
                            # This regex looks for property names that aren't properly quoted
                            import re
                            fixed_text = re.sub(r'([{,])\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*:', r'\1"\2":', text)
                            if fixed_text != text:
                                print(f"[6play] Attempting to fix unquoted property names...")
                                return json.loads(fixed_text)
                        except:
                            pass
                        
                        # Strategy 3: Try to extract JSON from larger response
                        if '<html' in text.lower():
                            print(f"[6play] Received HTML instead of JSON on attempt {attempt + 1}")
                        else:
                            print(f"[6play] Malformed response on attempt {attempt + 1}: {text[:200]}...")
                        
                        # Wait before retry
                        if attempt < max_retries - 1:
                            time.sleep(2 ** attempt)  # Exponential backoff
                            continue
                        
                elif response.status_code in [403, 429, 500]:
                    print(f"[6play] HTTP {response.status_code} on attempt {attempt + 1}")
                    print(f"[6play] Response headers: {dict(response.headers)}")
                    print(f"[6play] Response content: {response.text[:500]}...")
                    if attempt < max_retries - 1:
                        time.sleep(2 ** attempt)
                        continue
                else:
                    print(f"[6play] HTTP {response.status_code} on attempt {attempt + 1}")
                    print(f"[6play] Response headers: {dict(response.headers)}")
                    print(f"[6play] Response content: {response.text[:500]}...")
                    
            except Exception as e:
                print(f"[6play] Request error on attempt {attempt + 1}: {e}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                    continue
        
        print(f"[6play] All {max_retries} attempts failed for {url}")
        return None
    
    def get_live_channels(self) -> List[Dict]:
        """Get list of live channels from 6play"""
        channels = []
        
        # Get base URL for static assets
        static_base = os.getenv('ADDON_BASE_URL', 'http://localhost:7860')
        
        # Known 6play channels - updated to use local logos
        channel_data = [
            {"id": "m6", "name": "M6", "logo": f"{static_base}/static/logos/fr/m6.png"},
            {"id": "w9", "name": "W9", "logo": f"{static_base}/static/logos/fr/w9.png"},
            {"id": "6ter", "name": "6ter", "logo": f"{static_base}/static/logos/fr/6ter.png"},
            {"id": "fun_radio", "name": "Fun Radio", "logo": f"{static_base}/static/logos/fr/funradio.png"},
        ]
        
        for channel_info in channel_data:
            channels.append({
                "id": f"cutam:fr:6play:{channel_info['id']}",
                "name": channel_info['name'],
                "poster": channel_info['logo'],  # Use logo as poster for menu display
                "logo": channel_info['logo'],
                "type": "channel"
            })
        
        return channels

    def get_programs(self) -> List[Dict]:
        """Get list of 6play replay shows with enhanced metadata"""
        shows = []
        
        # Get base URL for static assets
        static_base = os.getenv('ADDON_BASE_URL', 'http://localhost:7860')
        
        # 6play shows configuration with specific poster URLs and specific logo URLs
        self.shows = {
            "capital": {
                "id": "capital",
                "name": "Capital",
                "description": "Magazine économique et financier de M6",
                "channel": "M6",
                "logo": "https://images.6play.fr/v1/images/4242438/raw",  # Specific logo as requested
                "poster": "https://images-fio.6play.fr/v2/images/4654297/raw",
                "genres": ["Économie", "Finance", "Magazine"],
                "year": 2025,
                "rating": "Tout public"
            },
            "66-minutes-le-doc": {
                "id": "66-minutes-le-doc",
                "name": "66 minutes le Doc",
                "description": "Magazine d'investigation de M6",
                "channel": "M6",
                "logo": "https://images.6play.fr/v1/images/4248692/raw",
                "poster": "https://images-fio.6play.fr/v2/images/4248693/raw",
                "genres": ["Investigation", "Magazine", "Documentaire"],
                "year": 2024,
                "rating": "Tous publics"
            },
            "66-minutes": {
                "id": "66-minutes",
                "name": "66 minutes",
                "description": "Magazine d'information de M6",
                "channel": "M6",
                "logo": "https://images.6play.fr/v1/images/4654324/raw",  # Specific logo as requested
                "poster": "https://images-fio.6play.fr/v2/images/4654325/raw",
                "genres": ["Information", "Magazine", "Actualité"],
                "year": 2025,
                "rating": "Tout public"
            },
            "zone-interdite": {
                "id": "zone-interdite",
                "name": "Zone Interdite",
                "description": "Magazine d'investigation de M6",
                "channel": "M6",
                "logo": "https://images.6play.fr/v1/images/4639961/raw",  # Specific basic logo as requested
                "poster": "https://images-fio.6play.fr/v2/images/4654281/raw",
                "genres": ["Investigation", "Magazine", "Documentaire"],
                "year": 2025,
                "rating": "Tout public"
            },
            "enquete-exclusive": {
                "id": "enquete-exclusive",
                "name": "Enquête Exclusive",
                "description": "Magazine d'investigation de M6",
                "channel": "M6",
                "logo": "https://images.6play.fr/v1/images/4242429/raw",  # Specific logo as requested
                "poster": "https://images-fio.6play.fr/v2/images/4654307/raw",
                "genres": ["Investigation", "Magazine", "Documentaire"],
                "year": 2025,
                "rating": "Tout public"
            }
        }
        
        try:
            # Process each show with proper poster and logo handling
            for show_id, show_info in self.shows.items():
                # Create base metadata with the specific poster and logo URLs already set
                show_metadata = {
                    'id': f"cutam:fr:6play:{show_id}",
                    'type': 'series',
                    'name': show_info['name'],
                    'description': show_info['description'],
                    'channel': show_info['channel'],
                    'genres': show_info['genres'],
                    'year': show_info['year'],
                    'rating': show_info['rating'],
                    'logo': show_info['logo'],  # Use the specific logo URL
                    'poster': show_info['poster']  # Use the specific poster URL
                }
                
                # Try to get additional metadata from 6play API (but preserve our poster and logo)
                try:
                    api_metadata = self._get_show_api_metadata(show_id, show_info)
                    if api_metadata:
                        # Only update fanart from API, keep our specific poster and logo
                        if 'fanart' in api_metadata:
                            show_metadata['fanart'] = api_metadata['fanart']
                        # Note: We don't override poster or logo from API to keep our specific URLs
                except Exception as e:
                    print(f"Warning: Could not fetch API metadata for {show_id}: {e}")
                
                shows.append(show_metadata)
        except Exception as e:
            print(f"[SixPlayProvider] Error fetching show metadata: {e}")
            # Fallback to basic metadata with specific posters and logos
            for show_id, show_info in self.shows.items():
                show_metadata = {
                    'id': f"cutam:fr:6play:{show_id}",
                    'type': 'series',
                    'name': show_info['name'],
                    'description': show_info['description'],
                    'channel': show_info['channel'],
                    'genres': show_info['genres'],
                    'year': show_info['year'],
                    'rating': show_info['rating'],
                    'logo': show_info['logo'],  # Use the specific logo URL
                    'poster': show_info['poster']  # Use the specific poster URL
                }
                shows.append(show_metadata)
        
        return shows

    def get_episodes(self, show_id: str) -> List[Dict]:
        """Get episodes for a specific 6play show"""
        # Extract the actual show ID from our format
        if "6play:" in show_id:
            actual_show_id = show_id.split("6play:")[-1]
        else:
            actual_show_id = show_id
        
        try:
            print(f"[SixPlayProvider] Getting episodes for 6play show: {actual_show_id}")
            
            # Use the same approach as the reference plugin
            # First, we need to find the program ID for the show
            program_id = self._find_program_id(actual_show_id)
            
            if not program_id:
                print(f"[SixPlayProvider] No program ID found for show: {actual_show_id}")
                return []
            
            # Get episodes using the program ID
            episodes = self._get_show_episodes(program_id)
            
            if episodes:
                print(f"[SixPlayProvider] Found {len(episodes)} episodes for {actual_show_id}")
            else:
                print(f"[SixPlayProvider] No episodes found for {actual_show_id}")
            
            return episodes
            
        except Exception as e:
            print(f"[SixPlayProvider] Error getting episodes for {actual_show_id}: {e}")
            return []
    
    def get_episode_stream_url(self, episode_id: str) -> Optional[Dict]:
        """Get stream URL for a specific 6play episode"""
        # Extract the actual episode ID from our format
        if "episode:" in episode_id:
            actual_episode_id = episode_id.split("episode:")[-1]
        else:
            actual_episode_id = episode_id
        
        try:
            print(f"[SixPlayProvider] Getting replay stream for 6play episode: {actual_episode_id}")

            # Check if processed file already exists before authentication
            api_url = "https://alphanet06-processor.hf.space"
            processed_filename = f"{actual_episode_id}.mkv"
            processed_url = f"{api_url}/stream/{processed_filename}"

            try:
                check_response = requests.head(processed_url, timeout=5)
                if check_response.status_code == 200:
                    # File exists - return immediately
                    return {
                        "url": processed_url,
                        "manifest_type": "video",
                        "title": "Processed Version (No DRM)",
                        "filename": processed_filename
                    }
            except Exception:
                # Error checking file - proceed with normal flow
                pass

            # Lazy authentication - only authenticate when needed
            if not self._authenticated and not self._authenticate():
                print("[SixPlayProvider] 6play authentication failed")
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
                print(f"[SixPlayProvider] Video API response received for {actual_episode_id}")
                
                # Extract video assets (same as reference plugin)
                if 'clips' in json_parser and json_parser['clips']:
                    video_assets = json_parser['clips'][0].get('assets', [])
                    
                    if video_assets:
                        # Dynamic format detection - analyze available assets to determine best format
                        print(f"🔍 Analyzing {len(video_assets)} available assets for optimal format...")
                        
                        # Analyze available asset types
                        available_formats = self._analyze_available_formats(video_assets)
                        print(f"📊 Available formats: {available_formats}")
                        
                        # Determine best format based on server response and client capabilities
                        best_format = self._determine_best_format(available_formats)
                        print(f"🎯 Selected format: {best_format}")
                        
                        # Get the stream URL for the selected format
                        final_video_url = self._get_final_video_url(video_assets, best_format['asset_type'])
                        
                        if final_video_url:
                            print(f"✅ {best_format['format_name']} stream found: {final_video_url}")
                            
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
                                    print(f"? [SixPlayProvider] MPD default_KID: {key_id_hex}")

                                drm_token = None
                                if self.account_id and self.login_token:
                                    try:
                                        payload_headers = {
                                            'X-Customer-Name': 'm6web',
                                            'X-Client-Release': '5.103.3',
                                            'Authorization': f'Bearer {self.login_token}',
                                        }

                                        complete_headers = merge_ip_headers(payload_headers)

                                        print(f"?? [SixPlay] DRM Token Request Headers:")
                                        for header_name, header_value in complete_headers.items():
                                            if header_name.lower() in ['authorization', 'x-auth-token', 'token']:
                                                masked_value = f"{header_value[:20]}..." if len(str(header_value)) > 20 else "***"
                                                print(f"   {header_name}: {masked_value}")
                                            else:
                                                print(f"   {header_name}: {header_value}")

                                        token_url = f"https://drm.6cloud.fr/v1/customers/m6web/platforms/m6group_web/services/m6replay/users/{self.account_id}/videos/{actual_episode_id}/upfront-token"
                                        print(f"?? [SixPlay] DRM Token URL: {token_url}")

                                        token_response = self.session.get(token_url, headers=complete_headers, timeout=10)

                                        print(f"?? [SixPlay] DRM Token Response:")
                                        print(f"   Status Code: {token_response.status_code}")
                                        print(f"   Response Headers: {dict(token_response.headers)}")

                                        if token_response.status_code == 200:
                                            token_data = token_response.json()
                                            drm_token = token_data["token"]
                                            print(f"? DRM token obtained successfully")
                                            print(f"?? [SixPlay] DRM Token Value: {drm_token}")
                                        else:
                                            print(f"? DRM token request failed: {token_response.status_code}")
                                            print(f"   Response content: {token_response.text[:500]}...")
                                            print(f"   Check your 6play credentials and authentication")

                                    except Exception as e:
                                        print(f"? DRM setup failed: {e}")

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
                                    print(f"? PSSH data included in stream response")

                                    if drm_token:
                                        raw_key = self._extract_widevine_key(pssh_record.base64_text, drm_token)
                                        if raw_key:
                                            normalized_key = self._normalize_decryption_key(raw_key, key_id_hex)
                                            if normalized_key:
                                                original_stream["decryption_key"] = normalized_key
                                                print(f"? Widevine decryption key included in stream response")

                                                self._print_download_command(final_video_url, normalized_key, actual_episode_id)

                                                # Trigger online DRM processing since file doesn't exist
                                                online_result = process_drm_simple(
                                                    url=final_video_url,
                                                    save_name=f"{actual_episode_id}",
                                                    key=normalized_key,
                                                    quality="best",
                                                    format="mkv"
                                                )

                                                if online_result.get("success"):
                                                    # Return the processed stream as the primary result
                                                    return processed_stream
                                                else:
                                                    # Processing failed - continue with DRM approach
                                                    pass

                                                if key_id_hex:
                                                    mediaflow_stream = self._build_mediaflow_clearkey_stream(
                                                        original_mpd_url=final_video_url,
                                                        base_headers=headers_video_stream,
                                                        key_id_hex=key_id_hex,
                                                        key_hex=normalized_key,
                                                        is_live=False,
                                                    )
                                                    if mediaflow_stream:
                                                        print("? Serving stream via MediaFlow ClearKey proxy")
                                                        return mediaflow_stream
                                            else:
                                                print("? Unable to normalize Widevine key for MediaFlow usage")
                                        else:
                                            print("? CDRM did not return a Widevine key")
                                else:
                                    print(f"[SixPlayProvider] No PSSH found in MPD manifest")

                                if drm_token:
                                    license_url = f"https://lic.drmtoday.com/license-proxy-widevine/cenc/|Content-Type=&User-Agent=Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/59.0.3041.0 Safari/537.36&Host=lic.drmtoday.com&x-dt-auth-token={drm_token}|R{{SSM}}|JBlicense"

                                    license_headers = {
                                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/59.0.3041.0 Safari/537.36"
                                    }

                                    print(f"?? [SixPlay] DRM License Information:")
                                    print(f"   License URL: {license_url}")
                                    print(f"   License Headers: {license_headers}")
                                    print(f"   Video URL: {final_video_url}")

                                    print(f"? Using direct DRM approach with license")

                                    original_stream.update({
                                        "licenseUrl": license_url,
                                        "licenseHeaders": license_headers,
                                        "drm_token": drm_token,
                                        "drm_protected": True
                                    })

                                    return original_stream
                                else:
                                    print(f"? No DRM token available - returning basic MPD with PSSH")
                                    return original_stream
                            else:
                                print(f"? No {best_format['format_name']} streams found")
                        else:
                            print("? No MPD streams found either")
                else:
                    print(f"6play live API error: {video_response.status_code}")
            else:
                print(f"6play token error: {token_response.status_code}")
            
            # Fallback - return None to indicate failure
            return None

        except Exception as e:
            print(f"Error getting stream for {actual_episode_id}: {e}")

        return None

    def get_channel_stream_url(self, channel_id: str) -> Optional[Dict]:
        """Get stream URL for a specific channel"""
        channel_name = channel_id.split(":")[-1]
    
        try:
            if not self._authenticated and not self._authenticate():
                print("6play authentication failed")
                return None
    
            payload_headers = {
                'X-Customer-Name': 'm6web',
                'X-Client-Release': '5.103.3',
                'Authorization': f'Bearer {self.login_token}',
            }
    
            complete_headers = merge_ip_headers(payload_headers)
    
            print(f"?? [SixPlay] Live Token Request Headers:")
            for header_name, header_value in complete_headers.items():
                if header_name.lower() in ['authorization', 'x-auth-token', 'token']:
                    masked_value = f"{header_value[:20]}..." if len(str(header_value)) > 20 else "***"
                    print(f"   {header_name}: {masked_value}")
                else:
                    print(f"   {header_name}: {header_value}")
    
            live_item_id = channel_name.upper()
            if channel_name == '6ter':
                live_item_id = '6T'
            elif channel_name in {'fun_radio', 'rtl2', 'gulli'}:
                live_item_id = channel_name
    
            token_url = f"https://6cloud.fr/v1/customers/m6web/platforms/m6group_web/services/6play/users/{self.account_id}/live/dashcenc_{live_item_id}/upfront-token"
            print(f"?? [SixPlay] Live Token URL: {token_url}")
    
            token_response = self.session.get(token_url, headers=complete_headers, timeout=10)
    
            print(f"?? [SixPlay] Live Token Response:")
            print(f"   Status Code: {token_response.status_code}")
            print(f"   Response Headers: {dict(token_response.headers)}")
    
            if token_response.status_code != 200:
                print(f"6play token error: {token_response.status_code}")
                return None
    
            token_json = token_response.json()
            token = token_json["token"]
            print(f"? Live token obtained successfully")
            print(f"?? [SixPlay] Live Token Value: {token[:50]}...")
    
            params = {
                'channel': live_item_id,
                'with': 'service_display_images,nextdiffusion,extra_data'
            }
    
            headers_video_stream = merge_ip_headers({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'})
    
            video_response = self.session.get(
                "https://android.middleware.6play.fr/6play/v2/platforms/m6group_androidmob/services/6play/live",
                params=params,
                headers=headers_video_stream,
                timeout=10
            )
    
            if video_response.status_code != 200:
                print(f"6play live API error: {video_response.status_code}")
                return None
    
            json_parser = video_response.json()
            if live_item_id not in json_parser or len(json_parser[live_item_id]) == 0:
                print(f"? No live data returned for {live_item_id}")
                return None
    
            video_assets = json_parser[live_item_id][0]['live']['assets']
            if not video_assets:
                print("? No MPD streams found either")
                return None
    
            print(f"?? Analyzing {len(video_assets)} live assets for optimal format...")
            available_formats = self._analyze_available_formats(video_assets)
            print(f"?? Available live formats: {available_formats}")
    
            best_format = self._determine_best_format(available_formats, is_live=True)
            print(f"?? Selected live format: {best_format}")
    
            final_video_url = self._get_final_video_url(video_assets, best_format['asset_type'])
            if not final_video_url:
                print("? No MPD streams found either")
                return None
    
            print(f"? {best_format['format_name']} live stream found: {final_video_url}")
    
            if best_format['format_type'] == 'hls':
                return {
                    "url": final_video_url,
                    "manifest_type": "hls"
                }
    
            if best_format['format_type'] != 'mpd':
                print(f"? No {best_format['format_name']} live streams found")
                return None
    
            pssh_record, mpd_text, drm_info = self._extract_pssh_from_mpd(final_video_url)
            key_id_hex = self._normalize_key_id((drm_info or {}).get('key_id'))
            if key_id_hex:
                print(f"? [SixPlayProvider] Live MPD default_KID: {key_id_hex}")
    
            stream_response = {
                "url": final_video_url,
                "manifest_type": "mpd"
            }
            if key_id_hex:
                stream_response["default_kid"] = key_id_hex
    
            if pssh_record:
                stream_response["pssh"] = pssh_record.base64_text
                stream_response["pssh_system_id"] = pssh_record.system_id
                stream_response["pssh_source"] = pssh_record.source
                print(f"? Live PSSH data included in stream response")
    
                raw_key = self._extract_widevine_key(pssh_record.base64_text, token)
                if raw_key:
                    normalized_key = self._normalize_decryption_key(raw_key, key_id_hex)
                    if normalized_key:
                        stream_response["decryption_key"] = normalized_key
                        print(f"? Live Widevine decryption key included in stream response")
    
                        self._print_download_command(final_video_url, normalized_key, f"live_{channel_name}")
    
                        if key_id_hex:
                            mediaflow_stream = self._build_mediaflow_clearkey_stream(
                                original_mpd_url=final_video_url,
                                base_headers=headers_video_stream,
                                key_id_hex=key_id_hex,
                                key_hex=normalized_key,
                                is_live=True,
                            )
                            if mediaflow_stream:
                                print("? Serving live stream via MediaFlow ClearKey proxy")
                                return mediaflow_stream
                    else:
                        print("? Unable to normalize Widevine key for MediaFlow usage")
                else:
                    print("? CDRM did not return a Widevine key")
    
            if token:
                license_url = f"https://lic.drmtoday.com/license-proxy-widevine/cenc/|Content-Type=&User-Agent=Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/59.0.3041.0 Safari/537.36&Host=lic.drmtoday.com&x-dt-auth-token={token}|R{{SSM}}|JBlicense"
                license_headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/59.0.3041.0 Safari/537.36"
                }
    
                print(f"?? [SixPlay] Live DRM License Information:")
                print(f"   License URL: {license_url}")
                print(f"   License Headers: {license_headers}")
                print(f"   Live Token: {token[:50]}...")
                print(f"   Video URL: {final_video_url}")
    
                print(f"? Live DRM stream configured")
    
                stream_response.update({
                    "licenseUrl": license_url,
                    "licenseHeaders": license_headers,
                    "live_token": token,
                    "drm_protected": True
                })
    
                return stream_response
    
            print(f"??  No authentication for live DRM content")
            return stream_response
    
        except Exception as e:
            print(f"Error getting stream for {channel_name}: {e}")
    
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
        """Extract PSSH data and DRM metadata from an MPD manifest.

        Args:
            mpd_url: URL to the MPD manifest

        Returns:
            Tuple containing the PSSH record (if any), raw MPD text, and extracted DRM info
        """
        mpd_text: Optional[str] = None
        drm_info: Dict = {}
        try:
            result = extract_first_pssh(mpd_url, include_mpd=True)
            pssh_record: Optional[PsshRecord]
            mpd_bytes: Optional[bytes]

            if isinstance(result, tuple):
                pssh_record, mpd_bytes = result
            else:
                pssh_record, mpd_bytes = result, None

            if mpd_bytes:
                try:
                    mpd_text = mpd_bytes.decode('utf-8')
                except Exception:
                    mpd_text = mpd_bytes.decode('utf-8', errors='ignore')

            if mpd_text:
                try:
                    drm_info = extract_drm_info_from_mpd(mpd_text) or {}
                except Exception as drm_error:
                    drm_info = {}
                    print(f"[SixPlayProvider] Failed to parse DRM info: {drm_error}")

            if not pssh_record and drm_info.get('widevine_pssh'):
                try:
                    raw = base64.b64decode(drm_info['widevine_pssh'])
                    pssh_record = PsshRecord(
                        source='drm_info',
                        parent='ContentProtection',
                        base64_text=drm_info['widevine_pssh'],
                        raw_length=len(raw),
                        system_id='edef8ba9-79d6-4ace-a3c8-27dcd51d21ed'
                    )
                except Exception:
                    pass

            if pssh_record:
                print(f"[SixPlayProvider] PSSH extracted successfully:")
                print(f"  Base64 PSSH: {pssh_record.base64_text}")
            else:
                print(f"[SixPlayProvider] No PSSH found in MPD manifest")

            return pssh_record, mpd_text, drm_info

        except Exception as e:
            print(f"[SixPlayProvider] Error extracting PSSH from MPD: {e}")
            return None, None, {}

    def _extract_widevine_key(self, pssh_value: str, drm_token: str) -> Optional[str]:
        """Extract Widevine decryption key using CDRM API.
        
        Args:
            pssh_value: Base64-encoded PSSH box
            drm_token: DRM authentication token
            
        Returns:
            Decryption key or None if extraction fails
        """
        try:
            print(f"[SixPlayProvider] Extracting Widevine decryption key...")
            
            # Prepare headers for CDRM API
            headers_data = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/59.0.3041.0 Safari/537.36',
                'x-dt-auth-token': drm_token
            }
            
            # Prepare request payload
            payload = {
                'pssh': pssh_value,
                'licurl': 'https://lic.drmtoday.com/license-proxy-widevine/cenc/?specConform=true',
                'headers': str(headers_data)
            }
            
            print(f"[SixPlayProvider] CDRM API request payload:")
            print(f"  PSSH: {pssh_value[:50]}...")
            print(f"  License URL: {payload['licurl']}")
            print(f"  Headers: {headers_data}")
            
            # Make request to CDRM API
            response = requests.post(
                url='https://cdrm-project.com/api/decrypt',
                headers={
                    'Content-Type': 'application/json',
                },
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                if 'message' in result:
                    decryption_key = result['message']
                    print(f"[SixPlayProvider] ✅ Widevine decryption key extracted successfully:")
                    print(f"  Key: {decryption_key}")
                    return decryption_key
                else:
                    print(f"[SixPlayProvider] ❌ No decryption key in CDRM response: {result}")
                    return None
            else:
                print(f"[SixPlayProvider] ❌ CDRM API error: {response.status_code}")
                print(f"  Response: {response.text[:500]}...")
                return None
                
        except Exception as e:
            print(f"[SixPlayProvider] Error extracting Widevine key: {e}")
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
            
            print(f"\n📥 N_m3u8DL-RE Download Command:")
            print(f'./N_m3u8DL-RE "{video_url}" --save-name "{clean_name}" --select-video best --select-audio all --select-subtitle all -mt -M format=mkv --log-level OFF --binary-merge --key {decryption_key}')
            print(f"\n🔗 URL: {display_url}")
            print(f"🔑 Key: {decryption_key}")
            print(f"💾 Save as: {clean_name}")
            
        except Exception as e:
            print(f"[SixPlayProvider] Error printing download command: {e}")


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
        if not raw_key:
            return None
        value = raw_key.strip()
        if not value:
            return None

        target_kid = key_id_hex.lower() if key_id_hex else None

        def match_candidate(kid_candidate: Optional[str], key_candidate: Optional[str]) -> Optional[str]:
            key_hex = self._ensure_hex_key(key_candidate)
            if not key_hex:
                return None
            if not target_kid:
                return key_hex
            kid_hex = self._normalize_key_id(kid_candidate)
            if kid_hex and kid_hex.lower() == target_kid:
                return key_hex
            return None

        # Try JSON payloads first
        try:
            data = json.loads(value)
            keys = []
            if isinstance(data, dict):
                keys = data.get('keys') or []
            elif isinstance(data, list):
                keys = data
            if isinstance(keys, list):
                for item in keys:
                    if not isinstance(item, dict):
                        continue
                    key_hex = match_candidate(item.get('kid') or item.get('keyid'), item.get('k') or item.get('key'))
                    if key_hex:
                        return key_hex
                if len(keys) == 1:
                    key_hex = self._ensure_hex_key(keys[0].get('k') or keys[0].get('key'))
                    if key_hex:
                        return key_hex
        except json.JSONDecodeError:
            pass

        normalized = (
            value.replace('\r\n', ',')
            .replace('\n', ',')
            .replace('\r', ',')
            .replace(';', ',')
            .replace('|', ',')
        )
        fallback_key = None

        for segment in normalized.split(','):
            piece = segment.strip()
            if not piece:
                continue
            if ':' in piece:
                kid_part, key_part = piece.split(':', 1)
                key_hex = match_candidate(kid_part, key_part)
                if key_hex:
                    return key_hex
            else:
                candidate = self._ensure_hex_key(piece)
                if candidate and not fallback_key:
                    fallback_key = candidate

        return fallback_key

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

    def _build_mediaflow_clearkey_stream(
        self,
        original_mpd_url: str,
        base_headers: Dict[str, str],
        key_id_hex: Optional[str],
        key_hex: Optional[str],
        is_live: bool = False,
    ) -> Optional[Dict]:
        """Create a MediaFlow ClearKey MPD stream if configuration allows."""
        if not key_id_hex or not key_hex:
            return None
        if not self.mediaflow_url or not self.mediaflow_password:
            print('[SixPlayProvider] MediaFlow configuration missing for ClearKey streaming')
            return None
        try:
            processed_mpd_url = get_processed_mpd_url_for_mediaflow(
                original_mpd_url,
                auth_token=self.login_token if self.login_token else None,
            )

            mediaflow_headers = {
                'user-agent': base_headers.get('User-Agent', get_random_windows_ua()),
                'origin': self.base_url,
                'referer': self.base_url,
            }
            if self.login_token:
                mediaflow_headers['authorization'] = f'Bearer {self.login_token}'

            key_id_param = self._hex_to_base64url(key_id_hex) or key_id_hex
            key_param = self._hex_to_base64url(key_hex) or key_hex

            extra_params = {
                'key_id': key_id_param,
                'key': key_param,
            }

            mediaflow_url = build_mediaflow_url(
                base_url=self.mediaflow_url,
                password=self.mediaflow_password,
                destination_url=processed_mpd_url,
                endpoint='/proxy/mpd/manifest.m3u8',
                request_headers=mediaflow_headers,
                extra_params=extra_params,
            )

            print(f"[SixPlayProvider] MediaFlow ClearKey URL prepared: {mediaflow_url}")

            return {
                'url': mediaflow_url,
                'manifest_type': 'mpd',
                'externalUrl': original_mpd_url,
                'is_live': is_live,
            }
        except Exception as e:
            print(f"[SixPlayProvider] MediaFlow ClearKey setup failed: {e}")
            return None
    def _analyze_available_formats(self, video_assets: List[Dict]) -> Dict:
        """Analyze available video formats from assets and return format information"""
        formats = {
            'hls': {'available': False, 'asset_types': [], 'qualities': []},
            'mpd': {'available': False, 'asset_types': [], 'qualities': []}
        }
        
        for asset in video_assets:
            asset_type = asset.get('type', '')
            quality = asset.get('video_quality', 'sd').lower()
            
            # Check for HLS formats
            if 'http_h264' in asset_type:
                formats['hls']['available'] = True
                formats['hls']['asset_types'].append(asset_type)
                if quality not in formats['hls']['qualities']:
                    formats['hls']['qualities'].append(quality)
            
            # Check for MPD/DASH formats
            elif 'dashcenc' in asset_type or 'mpd' in asset_type:
                formats['mpd']['available'] = True
                formats['mpd']['asset_types'].append(asset_type)
                if quality not in formats['mpd']['qualities']:
                    formats['mpd']['qualities'].append(quality)
        
        return formats

    def _determine_best_format(self, available_formats: Dict, is_live: bool = False) -> Dict:
        """Determine the best format based on available options and content type"""
        
        # Format priority and characteristics
        format_preferences = [
            {
                'format_type': 'hls',
                'format_name': 'HLS',
                'asset_type': 'http_h264',
                'priority': 1,
                'drm_required': False,
                'description': 'HTTP Live Streaming (no DRM)'
            },
            {
                'format_type': 'mpd', 
                'format_name': 'MPD/DASH',
                'asset_type': 'usp_dashcenc_h264' if not is_live else 'delta_dashcenc_h264',
                'priority': 2,
                'drm_required': True,
                'description': 'Dynamic Adaptive Streaming (DRM protected)'
            }
        ]
        
        # For live content, prefer HLS if available (better for live streaming)
        # For replay content, prefer MPD if available (better quality, adaptive bitrate)
        if is_live:
            # Live content: prefer HLS for better live streaming performance
            preferred_order = ['hls', 'mpd']
        else:
            # Replay content: prefer MPD for better quality and adaptive streaming
            preferred_order = ['mpd', 'hls']
        
        # Find the best available format
        for format_type in preferred_order:
            if available_formats[format_type]['available']:
                for pref in format_preferences:
                    if pref['format_type'] == format_type:
                        # Select the best quality available
                        qualities = available_formats[format_type]['qualities']
                        best_quality = 'hd' if 'hd' in qualities else 'sd'
                        
                        return {
                            'format_type': format_type,
                            'format_name': pref['format_name'],
                            'asset_type': pref['asset_type'],
                            'quality': best_quality,
                            'drm_required': pref['drm_required'],
                            'description': pref['description']
                        }
        
        # Fallback: if no preferred format is available, use whatever is available
        for format_type in ['hls', 'mpd']:
            if available_formats[format_type]['available']:
                for pref in format_preferences:
                    if pref['format_type'] == format_type:
                        qualities = available_formats[format_type]['qualities']
                        best_quality = 'hd' if 'hd' in qualities else 'sd'
                        
                        return {
                            'format_type': format_type,
                            'format_name': pref['format_name'],
                            'asset_type': pref['asset_type'],
                            'quality': best_quality,
                            'drm_required': pref['drm_required'],
                            'description': pref['description']
                        }
        
        # Ultimate fallback: default to HLS
        return {
            'format_type': 'hls',
            'format_name': 'HLS',
            'asset_type': 'http_h264',
            'quality': 'sd',
            'drm_required': False,
            'description': 'Default HLS fallback'
        }

    def _get_show_api_metadata(self, show_id: str, show_info: Dict) -> Dict:
        """Get show metadata from 6play API using program ID from Algolia search"""
        try:
            # First, find the program ID using Algolia search (same as reference plugin)
            program_id = self._find_program_id(show_id)
            
            if not program_id:
                print(f"[SixPlayProvider] No program ID found for {show_id}, cannot get metadata")
                return {}
            
            # Now get the program details using the program ID
            url = f"https://android.middleware.6play.fr/6play/v2/platforms/m6group_androidmob/services/6play/programs/{program_id}?with=links,subcats,rights"
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            response = self.session.get(url, headers=merge_ip_headers(headers), timeout=10)
            
            if response.status_code == 200:
                program_data = response.json()
                
                # Extract images from program data with proper mapping
                fanart = None
                logo = None
                
                # Note: We don't set poster here to preserve the specific poster URLs from show configuration
                # The specific posters are already set in the show configuration:
                # - capital: https://images-fio.6play.fr/v2/images/4654297/raw
                # - 66-minutes: https://images-fio.6play.fr/v2/images/4654325/raw
                # - zone-interdite: https://images-fio.6play.fr/v2/images/4654281/raw
                # - enquete-exclusive: https://images-fio.6play.fr/v2/images/4654307/raw
                
                if 'images' in program_data:
                    # First pass: look for specific image types for fanart and logo
                    for img in program_data['images']:
                        role = img.get('role', '')
                        external_key = img.get('external_key', '')
                        
                        if external_key:
                            image_url = f"https://images.6play.fr/v1/images/{external_key}/raw"
                            
                            # Fanart/Background: prefer backdropWide, then backdropTall, then banner_31
                            if not fanart and role in ['backdropWide', 'backdropTall', 'banner_31']:
                                fanart = image_url
                            
                            # Logo: prefer logo, then fullColorLogo, then singleColorLogo
                            if not logo and role in ['logo', 'fullColorLogo', 'singleColorLogo']:
                                logo = image_url
                    
                    # If no specific fanart found, use a different image type as fallback
                    if not fanart:
                        for img in program_data['images']:
                            if img.get('role') in ['cover', 'portrait', 'square']:
                                external_key = img.get('external_key', '')
                                if external_key:
                                    fanart = f"https://images.6play.fr/v1/images/{external_key}/raw"
                                    break
                    
                    # Logo fallback - use the channel logo if no specific logo found
                    if not logo:
                        logo = f"https://www.6play.fr/static/logos/{show_info['channel'].lower()}.png"
                
                print(f"[SixPlayProvider] Found show metadata for {show_id}: fanart={fanart[:50] if fanart else 'N/A'}..., logo={logo[:50] if logo else 'N/A'}...")
                
                return {
                    "fanart": fanart
                    # Note: poster and logo are intentionally not included to preserve specific URLs
                }
            else:
                print(f"[SixPlayProvider] Failed to get program data for {show_id}: {response.status_code}")
            
            return {}
            
        except Exception as e:
            print(f"[SixPlayProvider] Error fetching show metadata for {show_id}: {e}")
            return {}
    
    def _find_program_id(self, show_id: str) -> Optional[str]:
        """Find the program ID for a given show ID (exact from Kodi addon)"""
        try:
            # Use the exact search API from Kodi addon instead of the programs API
            search_url = 'https://nhacvivxxk-dsn.algolia.net/1/indexes/*/queries'
            search_headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:140.0) Gecko/20100101 Firefox/140.0',
                'Content-Type': 'application/x-www-form-urlencoded',
                'x-algolia-api-key': '6ef59fc6d78ac129339ab9c35edd41fa',
                'x-algolia-application-id': 'NHACVIVXXK',
            }
            
            # Map our show IDs to the actual search terms used by 6play
            show_search_mapping = {
                'capital': 'Capital',
                '66-minutes': '66 minutes',
                '66-minutes-le-doc': '66 minutes : le doc',
                'zone-interdite': 'Zone interdite',
                'enquete-exclusive': 'Enquête exclusive'
            }
            
            search_term = show_search_mapping.get(show_id, show_id)
            
            search_data = {
                'requests': [
                    {
                        'indexName': 'rtlmutu_prod_bedrock_layout_items_v2_m6web_main',
                        'query': search_term,
                        'params': 'clickAnalytics=true&hitsPerPage=10&facetFilters=[["metadata.item_type:program"], ["metadata.platforms_assets:m6group_web"]]',
                    }
                ]
            }
            
            response = requests.post(search_url, headers=merge_ip_headers(search_headers), json=search_data, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                # Find the specific show in search results
                for result in data.get('results', []):
                    for hit in result.get('hits', []):
                        title = hit['item']['itemContent']['title']
                        # Look for exact match first
                        if title.lower() == search_term.lower():
                            program_id = str(hit['content']['id'])
                            print(f"[SixPlayProvider] Found exact match for {show_id}: '{title}' (ID: {program_id})")
                            return program_id
                
                # If no exact match, look for partial match
                for result in data.get('results', []):
                    for hit in result.get('hits', []):
                        title = hit['item']['itemContent']['title']
                        if search_term.lower() in title.lower():
                            program_id = str(hit['content']['id'])
                            print(f"[SixPlayProvider] Found partial match for {show_id}: '{title}' (ID: {program_id})")
                            return program_id
            
            print(f"[SixPlayProvider] No program ID found for show {show_id}")
            return None
            
        except Exception as e:
            print(f"[SixPlayProvider] Error finding program ID for {show_id}: {e}")
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
                print(f"[SixPlayProvider] Failed to get episodes: {response.status_code}")
                return []
                
        except Exception as e:
            print(f"[SixPlayProvider] Error getting show episodes: {e}")
            return []
    
    def _parse_episode(self, video: Dict, episode_number: int) -> Optional[Dict]:
        """Parse episode data from 6play API response"""
        try:
            video_id = str(video.get('id', ''))
            title = video.get('title', '')
            description = video.get('description', '')
            duration = video.get('duration', '')
            
            # Get images from video data (same as reference plugin)
            poster = None
            fanart = None
            
            if 'images' in video:
                for img in video['images']:
                    if img.get('role') in ['vignette', 'carousel']:
                        external_key = img.get('external_key', '')
                        if external_key:
                            poster = f"https://images.6play.fr/v1/images/{external_key}/raw"
                            fanart = poster  # Use same image for both
                            break
            
            # Get broadcast date
            broadcast_date = None
            if 'product' in video and 'last_diffusion' in video['product']:
                broadcast_date = video['product']['last_diffusion'][:10]  # YYYY-MM-DD format
            
            episode_info = {
                "id": f"cutam:fr:6play:episode:{video_id}",
                "type": "episode",
                "title": title,
                "description": description,
                "poster": poster,
                "fanart": fanart,
                "episode": episode_number,
                "duration": duration,
                "broadcast_date": broadcast_date
            }
            
            return episode_info
            
        except Exception as e:
            print(f"[SixPlayProvider] Error parsing episode: {e}")
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

            print(f"[SixPlayProvider] Unrecognized stream id format: {stream_id}")
            return None
        except Exception as e:
            print(f"[SixPlayProvider] resolve_stream error for {stream_id}: {e}")
            return None
