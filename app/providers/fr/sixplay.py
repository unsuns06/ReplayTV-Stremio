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
from typing import Dict, List, Optional, Tuple
from app.utils.credentials import get_provider_credentials
from app.utils.metadata import metadata_processor

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
        
        # No MediaFlow - we'll use the exact Kodi addon approach
        
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': get_random_windows_ua()
        })
        self.account_id = None
        self.login_token = None
        self._authenticated = False
    
    def _safe_api_call(self, url: str, params: Dict = None, headers: Dict = None, data: Dict = None, method: str = 'GET', max_retries: int = 3) -> Optional[Dict]:
        """Make a safe API call with retry logic and error handling"""
        for attempt in range(max_retries):
            try:
                # Rotate User-Agent for each attempt
                current_headers = headers or {}
                current_headers['User-Agent'] = get_random_windows_ua()
                
                print(f"[6play] API call attempt {attempt + 1}/{max_retries}: {url}")
                
                if method.upper() == 'POST':
                    if data:
                        response = self.session.post(url, params=params, headers=current_headers, json=data, timeout=15)
                    else:
                        response = self.session.post(url, params=params, headers=current_headers, timeout=15)
                else:
                    response = self.session.get(url, params=params, headers=current_headers, timeout=15)
                
                if response.status_code == 200:
                    # Try to parse JSON with multiple strategies
                    try:
                        return response.json()
                    except json.JSONDecodeError as e:
                        print(f"[6play] JSON parse error on attempt {attempt + 1}: {e}")
                        
                        # Strategy 1: Try to fix common JSON issues
                        text = response.text
                        if "'" in text and '"' not in text:
                            # Replace single quotes with double quotes
                            text = text.replace("'", '"')
                            try:
                                return json.loads(text)
                            except:
                                pass
                        
                        # Strategy 2: Try to extract JSON from larger response
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
                    if attempt < max_retries - 1:
                        time.sleep(2 ** attempt)
                        continue
                else:
                    print(f"[6play] HTTP {response.status_code} on attempt {attempt + 1}")
                    
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
            
            # Lazy authentication - only authenticate when needed
            if not self._authenticated and not self._authenticate():
                print("[SixPlayProvider] 6play authentication failed")
                return None
            
            # Use the same approach as the reference plugin for replay content
            headers_video_stream = {
                "User-Agent": get_random_windows_ua(),
            }
            
            # Get video info using the same API call as the reference plugin
            url_json = f"https://android.middleware.6play.fr/6play/v2/platforms/m6group_androidmob/services/6play/videos/{actual_episode_id}?csa=6&with=clips,freemiumpacks"
            
            response = self.session.get(url_json, headers=headers_video_stream, timeout=10)
            
            if response.status_code == 200:
                json_parser = response.json()
                print(f"[SixPlayProvider] Video API response received for {actual_episode_id}")
                
                # Extract video assets (same as reference plugin)
                if 'clips' in json_parser and json_parser['clips']:
                    video_assets = json_parser['clips'][0].get('assets', [])
                    
                    if video_assets:
                        # Try to find HLS streams first
                        print(f"🔍 Looking for HLS streams in {len(video_assets)} assets...")
                        final_video_url = self._get_final_video_url(video_assets, 'http_h264')
                        
                        if final_video_url and 'http_h264' in final_video_url:
                            print(f"✅ HLS stream found: {final_video_url[:100]}...")
                            return {
                                "url": final_video_url,
                                "manifest_type": "hls"
                            }
                        else:
                            print("❌ No HLS streams found, trying MPD...")
                        
                        # Fallback to MPD if no HLS available - use exact Kodi addon approach
                        final_video_url = self._get_final_video_url(video_assets, 'usp_dashcenc_h264')
                        
                        if final_video_url:
                            print(f"✅ MPD stream found: {final_video_url[:100]}...")
                            
                            # Get DRM token for this video (exact Kodi addon approach)
                            try:
                                payload_headers = {
                                    'X-Customer-Name': 'm6web',
                                    'X-Client-Release': '5.103.3',
                                    'Authorization': f'Bearer {self.login_token}',
                                }
                                
                                # Use the exact URL from Kodi addon
                                token_url = f"https://drm.6cloud.fr/v1/customers/m6web/platforms/m6group_web/services/m6replay/users/{self.account_id}/videos/{actual_episode_id}/upfront-token"
                                token_response = self.session.get(token_url, headers=payload_headers, timeout=10)
                                
                                if token_response.status_code == 200:
                                    token_data = token_response.json()
                                    drm_token = token_data["token"]
                                    
                                    # Build license URL exactly like Kodi addon
                                    license_url = f"https://lic.drmtoday.com/license-proxy-widevine/cenc/|Content-Type=&User-Agent=Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/59.0.3041.0 Safari/537.36&Host=lic.drmtoday.com&Origin=https://www.6play.fr&Referer=https://www.6play.fr&x-dt-auth-token={drm_token}|R{{SSM}}|JBlicense"
                                    
                                    print(f"✅ DRM token obtained, license URL built")
                                    
                                    return {
                                        "url": final_video_url,
                                        "manifest_type": "mpd",
                                        "licenseUrl": license_url,
                                        "licenseHeaders": {
                                            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/59.0.3041.0 Safari/537.36"
                                        }
                                    }
                                else:
                                    print(f"❌ DRM token request failed: {token_response.status_code}")
                                    return {
                                        "url": final_video_url,
                                        "manifest_type": "mpd"
                                    }
                            except Exception as e:
                                print(f"❌ DRM setup failed: {e}")
                                return {
                                    "url": final_video_url,
                                    "manifest_type": "mpd"
                                }
                        else:
                            print("❌ No MPD streams found either")
                else:
                    print(f"[SixPlayProvider] No clips found in video response")
            else:
                print(f"[SixPlayProvider] Video API error: {response.status_code}")
                
        except Exception as e:
            print(f"[SixPlayProvider] Error getting stream for episode {episode_id}: {e}")
        
        return None
    
    def get_channel_stream_url(self, channel_id: str) -> Optional[Dict]:
        """Get stream URL for a specific channel"""
        # Extract the actual channel name from our ID format
        channel_name = channel_id.split(":")[-1]  # e.g., "m6"
        
        try:
            # Lazy authentication - only authenticate when needed
            if not self._authenticated and not self._authenticate():
                print("6play authentication failed")
                return None
                
            # Get live token
            payload_headers = {
                'X-Customer-Name': 'm6web',
                'X-Client-Release': '5.103.3',
                'Authorization': f'Bearer {self.login_token}',
            }
            
            live_item_id = channel_name.upper()
            if channel_name == '6ter':
                live_item_id = '6T'
            elif channel_name in {'fun_radio', 'rtl2', 'gulli'}:
                live_item_id = channel_name
            
            # Get token for live stream using correct URL pattern
            token_url = f"https://6cloud.fr/v1/customers/m6web/platforms/m6group_web/services/6play/users/{self.account_id}/live/dashcenc_{live_item_id}/upfront-token"
            token_response = self.session.get(token_url, headers=payload_headers, timeout=10)
            
            if token_response.status_code == 200:
                token_jsonparser = token_response.json()
                token = token_jsonparser["token"]
                
                # Get live stream information using correct URL
                params = {
                    'channel': live_item_id,
                    'with': 'service_display_images,nextdiffusion,extra_data'
                }
                
                video_response = self.session.get(
                    "https://android.middleware.6play.fr/6play/v2/platforms/m6group_androidmob/services/6play/live", 
                    params=params, 
                    headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'},
                    timeout=10
                )
                
                if video_response.status_code == 200:
                    json_parser = video_response.json()
                    if live_item_id in json_parser and len(json_parser[live_item_id]) > 0:
                        video_assets = json_parser[live_item_id][0]['live']['assets']
                        
                        if video_assets:
                            # Try to find HLS streams first
                            print(f"🔍 Looking for HLS streams in {len(video_assets)} assets...")
                            final_video_url = self._get_final_video_url(video_assets, 'http_h264')
                            
                            if final_video_url and 'http_h264' in final_video_url:
                                print(f"✅ HLS stream found: {final_video_url[:100]}...")
                                return {
                                    "url": final_video_url,
                                    "manifest_type": "hls"
                                }
                            else:
                                print("❌ No HLS streams found, trying MPD...")
                            
                            # Fallback to MPD if no HLS available
                            final_video_url = self._get_final_video_url(video_assets, 'delta_dashcenc_h264')
                            
                            if final_video_url:
                                print(f"✅ MPD stream found: {final_video_url[:100]}...")
                                return {
                                    "url": final_video_url,
                                    "manifest_type": "mpd"
                                }
                            else:
                                print("❌ No MPD streams found either")
                else:
                    print(f"6play live API error: {video_response.status_code}")
            else:
                print(f"6play token error: {token_response.status_code}")
            
            # Fallback - return None to indicate failure
            return None
            
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
            
            response = self.session.get(url, headers=headers, timeout=10)
            
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
            
            response = requests.post(search_url, headers=search_headers, json=search_data, timeout=10)
            
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
            
            response = self.session.get(url, headers=headers, timeout=10)
            
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
        """Resolve stream URL for a given stream ID"""
        # This method needs to be implemented based on the specific stream ID format
        # For now, return None as a placeholder
        print(f"SixPlayProvider: resolve_stream not implemented for {stream_id}")
        return None