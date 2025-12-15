#!/usr/bin/env python3
"""
MyTF1 provider implementation
Hybrid approach with robust error handling, fallbacks, and retry logic

FIXED: French proxy authentication issue
- Direct requests work with authentication and return 200 + stream URLs
- French proxy returns 403 even with proper authentication headers
- ROOT CAUSE: French proxy strips critical headers (Authorization, X-Forwarded-For, etc.)
- Solution: Try proxy first, but fallback to direct calls when proxy returns non-200 delivery codes
- This maintains geo-restriction bypass while ensuring authentication works

PROXY LIMITATIONS DISCOVERED:
- Only forwards: User-Agent, Accept (but modifies values)
- STRIPS: Authorization, X-Forwarded-For, Referer, Origin, Security headers
- This explains why authentication fails through proxy
- Direct calls work perfectly with full header set
"""

import json
import requests
import time
import os
from urllib.parse import urlencode, quote, unquote
from typing import Dict, List, Optional
from fastapi import Request
from app.utils.credentials import get_provider_credentials, load_credentials
from app.utils.safe_print import safe_print
from app.utils.mediaflow import build_mediaflow_url
from app.utils.base_url import get_base_url, get_logo_url
from app.utils.client_ip import make_ip_headers
from app.utils.proxy_config import get_proxy_config
from app.utils.user_agent import get_random_windows_ua
from app.utils.api_client import ProviderAPIClient
from app.utils.programs_loader import get_programs_for_provider
from app.providers.base_provider import BaseProvider



def force_decode_tf1_replay_url(original_url: str) -> str:
    """
    Force decode TF1 replay URLs to prevent double-encoding issues when routing through proxy.
    
    This is critical for TF1 replay content as the mediainfo URLs often contain encoded parameters
    that need to be properly decoded before being passed through the French IP proxy.
    
    Args:
        original_url (str): The original URL with potential encoding
        
    Returns:
        str: The force-decoded URL ready for proxy routing
    """
    safe_print(f"✅ [MyTF1] URL Decoder: Original URL: {original_url}")
    decoded_url = unquote(original_url)
    safe_print(f"✅ [MyTF1] URL Decoder: Force-decoded URL: {decoded_url}")
    return decoded_url

class MyTF1Provider(BaseProvider):
    """MyTF1 provider implementation with robust error handling and fallbacks"""
    
    # Class attributes for BaseProvider
    provider_name = "mytf1"
    base_url = "https://www.tf1.fr"
    country = "fr"

    @property
    def provider_key(self) -> str:
        return "mytf1"
        
    @property
    def needs_ip_forwarding(self) -> bool:
        return True
    
    def __init__(self, request: Optional[Request] = None):
        # Initialize base class (handles credentials, session, proxy_config, mediaflow)
        super().__init__(request)
        
        # TF1-specific API configuration
        self.api_key = "3_hWgJdARhz_7l1oOp3a8BDLoR9cuWZpUaKG4aqF7gum9_iK3uTZ2VlDBl8ANf8FVk"
        self.api_url = "https://www.tf1.fr/graphql/web"
        self.video_stream_url = "https://mediainfo.tf1.fr/mediainfocombo"
        
        # Log MediaFlow configuration for debugging (already set by base class)
        if self.mediaflow_url:
            safe_print(f"✅ [MyTF1] MediaFlow configured: {self.mediaflow_url[:30]}...")
        safe_print(f"✅ [MyTF1] MediaFlow Password: {'***' if self.mediaflow_password else 'None'}")
        
        # Get base URL for static assets
        self.static_base = get_base_url(request)

        # TF1-specific auth endpoints
        self.accounts_login = "https://compte.tf1.fr/accounts.login"
        self.accounts_bootstrap = "https://compte.tf1.fr/accounts.webSdkBootstrap"
        self.token_gigya_web = "https://www.tf1.fr/token/gigya/web"
        self.license_base_url = 'https://drm-wide.tf1.fr/proxy?id=%s'
        
        # TF1-specific authentication state
        self.auth_token = None

        # Initialize IP forwarding headers (critical for geo-restricted content)
        self.viewer_ip_headers = make_ip_headers(None, getattr(request, 'headers', {}) if request else {})

        # Load shows from external programs.json
        self.shows = get_programs_for_provider('mytf1')
    
    def _safe_api_call(self, url: str, params: Dict = None, headers: Dict = None, data: Dict = None, method: str = 'GET', max_retries: int = 3) -> Optional[Dict]:
        """Delegate to shared ProviderAPIClient for consistent retry/error handling."""
        # Merge viewer IP headers
        merged_headers = headers.copy() if headers else {}
        for k, v in self.viewer_ip_headers.items():
            merged_headers[k] = v
        
        if method.upper() == 'POST':
            return self.api_client.post(url, params=params, headers=merged_headers, data=data, max_retries=max_retries)
        return self.api_client.get(url, params=params, headers=merged_headers, max_retries=max_retries)
    
    def _authenticate(self) -> bool:
        """Authenticate with TF1+ using provided credentials with robust error handling"""
        if not self.credentials.get('login') or not self.credentials.get('password'):
            safe_print("❌ [MyTF1] MyTF1 credentials not provided")
            return False
            
        try:
            safe_print("✅ [MyTF1] Attempting MyTF1 authentication...")
            
            # Bootstrap
            bootstrap_headers = {
                "referrer": self.base_url
            }
            bootstrap_params = {
                'apiKey': self.api_key,
                'pageURL': 'https%3A%2F%2Fwww.tf1.fr%2F',
                'sd': 'js_latest',
                'sdkBuild': '13987',
                'format': 'json'
            }
            
            # Authentication calls should be DIRECT - not through proxy
            safe_print(f"✅ [MyTF1] Making DIRECT bootstrap request to: {self.accounts_bootstrap}")
            bootstrap_data = self._safe_api_call(self.accounts_bootstrap, headers=bootstrap_headers, params=bootstrap_params)
            if not bootstrap_data:
                safe_print("❌ [MyTF1] Bootstrap failed")
                return False
            
            # Login
            headers_login = {
                "Content-Type": "application/x-www-form-urlencoded",
                "referrer": self.base_url
            }
            
            post_body_login = {
                "loginID": self.credentials['login'],
                "password": self.credentials['password'],
                "sessionExpiration": 31536000,
                "targetEnv": "jssdk",
                "include": "identities-all,data,profile,preferences,",
                "includeUserInfo": "true",
                "loginMode": "standard",
                "lang": "fr",
                "APIKey": self.api_key,
                "sdk": "js_latest",
                "authMode": "cookie",
                "pageURL": self.base_url,
                "sdkBuild": 13987,
                "format": "json"
            }
            
            # Login calls should be DIRECT - not through proxy
            safe_print(f"✅ [MyTF1] Making DIRECT login request to: {self.accounts_login}")
            login_data = self._safe_api_call(self.accounts_login, headers=headers_login, data=post_body_login, method='POST')
            
            if login_data and login_data.get('errorCode') == 0:
                # Get Gigya token
                headers_gigya = {
                    "content-type": "application/json"
                }
                body_gigya = {
                    "uid": login_data['userInfo']['UID'],
                    "signature": login_data['userInfo']['UIDSignature'],
                    "timestamp": int(login_data['userInfo']['signatureTimestamp']),
                    "consent_ids": ["1", "2", "3", "4", "10001", "10003", "10005", "10007", "10013", "10015", "10017", "10019", "10009", "10011", "13002", "13001", "10004", "10014", "10016", "10018", "10020", "10010", "10012", "10006", "10008"]
                }
                
                # JWT token calls should be DIRECT - not through proxy
                safe_print(f"✅ [MyTF1] Making DIRECT JWT token request to: {self.token_gigya_web}")
                jwt_data = self._safe_api_call(self.token_gigya_web, headers=headers_gigya, data=body_gigya, method='POST')
                
                if jwt_data and 'token' in jwt_data:
                    self.auth_token = jwt_data['token']
                    self._authenticated = True
                    safe_print("✅ [MyTF1] MyTF1 authentication successful!")
                    safe_print(f"✅ [MyTF1] Session token generated: {self.auth_token[:20]}...")
                    return True
                else:
                    safe_print("❌ [MyTF1] Failed to get Gigya token")
            else:
                safe_print(f"❌ [MyTF1] MyTF1 login failed: {login_data.get('errorMessage', 'Unknown error') if login_data else 'No response'}")
                
        except Exception as e:
            safe_print(f"❌ [MyTF1] Error during MyTF1 authentication: {e}")
        
        return False
    

    
    def get_live_channels(self) -> List[Dict]:
        """Get list of live TV channels from TF1+"""
        channels = []
        
        # TF1+ live channels (based on source addon)
        tf1_channels = [
            {
                "id": "cutam:fr:mytf1:tf1",
                "type": "channel",
                "name": "TF1",
                "poster": get_logo_url("fr", "tf1", self.request),
                "logo": get_logo_url("fr", "tf1", self.request),
                "description": "Première chaîne de télévision privée française"
            },
            {
                "id": "cutam:fr:mytf1:tmc",
                "type": "channel",
                "name": "TMC",
                "poster": get_logo_url("fr", "tmc", self.request),
                "logo": get_logo_url("fr", "tmc", self.request),
                "description": "Chaîne de télévision du groupe TF1"
            },
            {
                "id": "cutam:fr:mytf1:tfx",
                "type": "channel",
                "name": "TFX",
                "poster": get_logo_url("fr", "tfx", self.request),
                "logo": get_logo_url("fr", "tfx", self.request),
                "description": "Chaîne de divertissement du groupe TF1"
            },
            {
                "id": "cutam:fr:mytf1:tf1-series-films",
                "type": "channel",
                "name": "TF1 Séries Films",
                "poster": get_logo_url("fr", "tf1seriesfilms", self.request),
                "logo": get_logo_url("fr", "tf1seriesfilms", self.request),
                "description": "Chaîne dédiée aux séries et films du groupe TF1"
            }
        ]
        
        channels.extend(tf1_channels)
        return channels
    
    def get_programs(self) -> List[Dict]:
        """Get list of TF1+ replay shows with enhanced metadata and fallbacks"""
        shows = []
        
        try:
            # Fetch show metadata from TF1+ API with fallback
            for show_id, show_info in self.shows.items():
                show_metadata = self._get_show_api_metadata(show_id, show_info)
                
                shows.append({
                    "id": f"cutam:fr:mytf1:{show_id}",
                    "type": "series",
                    "name": show_info["name"],
                    "description": show_info["description"],
                    "logo": show_metadata.get("logo", get_logo_url("fr", "tf1", self.request)),
                    "poster": show_metadata.get("poster", get_logo_url("fr", "tf1", self.request)),
                    "fanart": show_metadata.get("fanart"),
                    "background": show_info.get("background", ""),  # Background image from programs.json
                    "genres": show_info["genres"],
                    "channel": show_info["channel"],
                    "year": show_info["year"],
                    "rating": show_info["rating"]
                })
        except Exception as e:
            safe_print(f"❌ [MyTF1] Error fetching show metadata: {e}")
            # Fallback to basic channel logos
            for show_id, show_info in self.shows.items():
                shows.append({
                    "id": f"cutam:fr:mytf1:{show_id}",
                    "type": "series",
                    "name": show_info["name"],
                    "description": show_info["description"],
                    "logo": get_logo_url("fr", "tf1", self.request),
                    "poster": get_logo_url("fr", "tf1", self.request),
                    "background": show_info.get("background", ""),  # Background image from programs.json
                    "genres": show_info["genres"],
                    "channel": show_info["channel"],
                    "year": show_info["year"],
                    "rating": show_info["rating"]
                })
        
        return shows
    
    def get_episodes(self, show_id: str) -> List[Dict]:
        """Get episodes for a specific TF1+ show with robust error handling and fallbacks"""
        # Extract the actual show ID from our format
        actual_show_id = show_id.split(":")[-1]
        
        if actual_show_id not in self.shows:
            return []
        
        try:
            # Lazy authentication - only authenticate when needed
            safe_print("✅ [MyTF1] Checking authentication for episodes...")
            if not self._authenticated and not self._authenticate():
                safe_print("❌ [MyTF1] MyTF1 authentication failed")
                return []

            # Use the TF1+ GraphQL API to get episodes with error handling
            # Based on the reference plugin implementation
            headers = {
                'content-type': 'application/json',
                'referer': 'https://www.tf1.fr/programmes-tv',
                'User-Agent': get_random_windows_ua(),
                'origin': self.base_url,
                'accept-language': 'fr-FR,fr;q=0.9',
                'accept': 'application/json, text/plain, */*',
                'authorization': f'Bearer {self.auth_token}'
            }

            
            # Get the channel for this show
            show_channel = self.shows[actual_show_id]['channel']
            channel_filter = show_channel.lower()
            
            # First, get the program ID for the show
            program_params = {
                'id': '483ce0f',
                'variables': f'{{"context":{{"persona":"PERSONA_2","application":"WEB","device":"DESKTOP","os":"WINDOWS"}},"filter":{{"channel":"{channel_filter}"}},"offset":0,"limit":500}}'
            }
            
            # TF1 GraphQL programs - Use DIRECT raw URL only (no proxy)
            safe_print(f"✅ [MyTF1] Making DIRECT GraphQL programs request (raw URL): {self.api_url}")
            data = self._safe_api_call(self.api_url, headers=headers, params=program_params, max_retries=3)
            
            if data and 'data' in data and 'programs' in data['data']:
                program_id = None
                program_slug = None
                
                # Find the specific show in the programs list
                for program in data['data']['programs']['items']:
                    if program.get('name', '').lower() == self.shows[actual_show_id]['name'].lower():
                        program_id = program.get('id')
                        program_slug = program.get('slug')
                        break
                
                if program_id and program_slug:
                    # Get episodes for the show
                    episodes = self._get_show_episodes(program_slug, program_id, headers)
                    if episodes:
                        # Filter episodes based on subscription access
                        available_episodes = self._filter_available_episodes(episodes)
                        
                        # Sort episodes by released date ascending (oldest first, newest last)
                        # Stremio expects videos sorted chronologically with newest episode having highest number
                        available_episodes.sort(key=lambda ep: ep.get('released', '') or '')
                        
                        # Re-number episodes after sorting (1, 2, 3... with 1 being oldest)
                        for i, ep in enumerate(available_episodes):
                            ep['episode'] = i + 1
                            ep['episode_number'] = i + 1
                        
                        safe_print(f"✅ [MyTF1] Found {len(available_episodes)} episodes (sorted chronologically)")
                        return available_episodes
                    else:
                        safe_print(f"❌ [MyTF1] No episodes found for program: {program_slug}")
                else:
                    safe_print(f"❌ [MyTF1] Program not found for show: {actual_show_id} on channel: {channel_filter}")
            else:
                safe_print("❌ [MyTF1] Failed to get TF1+ programs or API failed")
            
            # Fallback: return a placeholder episode
            safe_print(f"✅ [MyTF1] Using fallback episode for {actual_show_id}")
            return [self._create_fallback_episode(actual_show_id)]
                
        except Exception as e:
            safe_print(f"❌ [MyTF1] Error getting show episodes: {e}")
            # Fallback: return a placeholder episode
            return [self._create_fallback_episode(actual_show_id)]
    
    def _create_fallback_episode(self, show_id: str) -> Dict:
        """Create a fallback episode when API fails"""
        show_info = self.shows.get(show_id, {})
        return {
            "id": f"cutam:fr:mytf1:episode:{show_id}_fallback",
            "type": "episode",
            "title": f"Latest {show_info.get('name', show_id.replace('-', ' ').title())}",
            "description": f"Latest episode of {show_info.get('name', show_id.replace('-', ' ').title())}",
            "poster": get_logo_url("fr", "tf1", self.request),
            "fanart": get_logo_url("fr", "tf1", self.request),
            "episode": 1,
            "season": 1,
            "note": "Fallback episode - API unavailable"
        }
    
    def _filter_available_episodes(self, episodes: List[Dict]) -> List[Dict]:
        """Filter episodes to only return those accessible with current subscription"""
        available_episodes = []
        
        for episode in episodes:
            episode_id = episode.get('id', '').split(':')[-1]
            if not episode_id or episode_id.endswith('_fallback'):
                # Always include fallback episodes
                available_episodes.append(episode)
                continue
            
            # Quick check if episode is accessible (without full stream resolution)
            try:
                # Test with a lightweight HEAD request or similar check
                # For now, we'll include all episodes and let the stream resolution handle premium content
                available_episodes.append(episode)
                

                
            except Exception:
                # If any error, skip this episode
                continue
        
        return available_episodes
    
    def _get_show_episodes(self, program_slug: str, program_id: str, headers: Dict) -> List[Dict]:
        """Get episodes for a specific show using TF1+ API with error handling"""
        try:
            # Use the TF1+ API to get episodes directly
            # Based on the reference plugin's list_videos function
            params = {
                'id': 'a6f9cf0e',
                'variables': f'{{"programSlug":"{program_slug}","offset":0,"limit":50,"sort":{{"type":"DATE","order":"DESC"}},"types":["REPLAY"]}}'
            }
            
            # TF1 GraphQL REPLAY episodes - Try proxy first, fallback to direct if 500 errors
            dest_with_params = self.api_url + ("?" + urlencode(params) if params else "")
            proxy_base = self.proxy_config.get_proxy('fr_default')

            # Use simple URL encoding (Variant 2) - proven to work best and get successful responses
            proxied_url = proxy_base + quote(dest_with_params, safe="")

            safe_print(f"✅ [MyTF1] Trying GraphQL TF1 REPLAY episodes through French proxy with SIMPLE URL ENCODING: {proxied_url}")
            data = self._safe_api_call(proxied_url, headers=headers, max_retries=1)  # Reduce retries for proxy
            
            # If proxy fails with 500 errors, try direct API call
            if not data:
                safe_print("❌ [MyTF1] French proxy failed for GraphQL episodes, trying DIRECT call")
                safe_print(f"✅ [MyTF1] Direct GraphQL URL: {self.api_url}")
                data = self._safe_api_call(self.api_url, headers=headers, params=params, max_retries=2)
            
            if data and 'data' in data and 'programBySlug' in data['data']:
                program_data = data['data']['programBySlug']
                
                # Check if videos are available
                if 'videos' in program_data and 'items' in program_data['videos']:
                    video_items = program_data['videos']['items']
                    safe_print(f"✅ [MyTF1] Found {len(video_items)} video items")
                    
                    episodes = []
                    for video_data in video_items:
                        episode_info = self._parse_episode(video_data, video_data, len(episodes) + 1)
                        if episode_info:
                            episodes.append(episode_info)
                    
                    return episodes
                else:
                    safe_print("❌ [MyTF1] No videos found in programBySlug")
                    safe_print(f"❌ [MyTF1] Available keys: {list(program_data.keys())}")
            else:
                safe_print("❌ [MyTF1] No programBySlug in response or API failed")
                safe_print(f"❌ [MyTF1] Response keys: {list(data.keys()) if data else 'No data'}")
            
            return []
            
        except Exception as e:
            safe_print(f"❌ [MyTF1] Error getting TF1+ show episodes: {e}")
            return []
    
    def _parse_episode(self, video: Dict, video_data: Dict, episode_number: int) -> Optional[Dict]:
        """Parse episode data from TF1+ API response with error handling"""
        try:
            # Extract episode information
            episode_id = video.get('id')
            title = video.get('decoration', {}).get('label', 'Unknown Title')
            # The API uses 'description' in the decoration, not 'summary'
            description = video.get('decoration', {}).get('description', '')
            duration = video.get('playingInfos', {}).get('duration', '')
            # Get the release date in ISO 8601 format for Stremio
            released = video.get('date', '')  # e.g., "2025-12-06T18:07:51Z"
            
            # Get images from decoration fields (like the reference plugin)
            poster = None
            fanart = None
            
            # Try to get image from video decoration (like reference plugin)
            if 'decoration' in video and 'images' in video['decoration']:
                try:
                    # Use the second image as poster (like reference plugin)
                    if len(video['decoration']['images']) > 1:
                        poster = video['decoration']['images'][1]['sources'][0].get('url', '')
                    elif len(video['decoration']['images']) > 0:
                        poster = video['decoration']['images'][0]['sources'][0].get('url', '')
                except (IndexError, KeyError):
                    pass
            
            # Fallback to image from video_data
            if not poster and 'image' in video_data and 'sourcesWithScales' in video_data['image']:
                poster = video_data['image']['sourcesWithScales'][0].get('url', '')
            
            # Create episode metadata
            episode_meta = {
                "id": f"cutam:fr:mytf1:episode:{episode_id}",
                "title": title,
                "description": description,
                "poster": poster,
                "fanart": fanart,
                "duration": duration,
                "released": released,  # ISO 8601 date for Stremio
                "type": "episode",
                "episode_number": episode_number,
                "season": 1,  # Default season
                "episode": episode_number
            }
            
            return episode_meta
            
        except Exception as e:
            safe_print(f"❌ [MyTF1] Error parsing episode: {e}")
            return None
    
    def get_live_stream_url(self, channel_id: str) -> Optional[Dict]:
        """Get live stream URL for a specific channel - wrapper for get_channel_stream_url"""
        return self.get_channel_stream_url(channel_id)
    
    def get_channel_stream_url(self, channel_id: str) -> Optional[Dict]:
        """Get stream URL for a specific channel with robust error handling and fallbacks"""
        # Extract the actual channel name from our ID format
        channel_name = channel_id.split(":")[-1]  # e.g., "tf1"

        try:
            safe_print(f"✅ [MyTF1] Getting stream for channel: {channel_name}")

            # Lazy authentication - only authenticate when needed
            safe_print("✅ [MyTF1] Checking authentication...")
            if not self._authenticated and not self._authenticate():
                safe_print("❌ [MyTF1] MyTF1 authentication failed")
                return None

            # TF1 live streams use 'L_' prefix (e.g., 'L_TF1')
            video_id = f'L_{channel_name.upper()}'
            safe_print(f"✅ [MyTF1] Using video ID: {video_id}")

            # Get the actual stream URL using the mediainfo API
            headers_video_stream = {
                "User-Agent": get_random_windows_ua(),
                "authorization": f"Bearer {self.auth_token}",
                # Help upstream validate request context like a browser
                "referer": self.base_url,
                "origin": self.base_url,
                # Hint FR locale to upstream
                "accept-language": "fr-FR,fr;q=0.9,en;q=0.8,en-US;q=0.7",
                # Some stacks require explicit Accept for JSON
                "accept": "application/json, text/plain, */*",
                # Additional headers to help with geo-blocking
                "Accept-Encoding": "gzip, deflate, br",
                "Accept-Charset": "UTF-8,*;q=0.5",
                "Cache-Control": "no-cache",
                "Pragma": "no-cache",
                # Additional security headers that might help
                "Sec-Fetch-Dest": "empty",
                "Sec-Fetch-Mode": "cors",
                "Sec-Fetch-Site": "same-site",
                "Sec-GPC": "1",
                # Content Security Policy headers that might be checked
                "DNT": "1",
                "Upgrade-Insecure-Requests": "1",
            }
            # Params follow reference; LCI could be treated specially but we align to reference pver block
            params = {
                'context': 'MYTF1',
                'pver': '5029000',
                'platform': 'web',
                'device': 'desktop',
                'os': 'windows',
                'osVersion': '10.0',
                'topDomain': 'www.tf1.fr',  # Use actual TF1 host
                'playerVersion': '5.29.0',
                'productName': 'mytf1',
                'productVersion': '3.37.0',
                'format': 'hls'  # Try to force HLS format for all channels
            }
            
            url_json = f"https://mediainfo.tf1.fr/mediainfocombo/{video_id}"
            
            # Try multiple proxy services to avoid geo-blocking
            dest_with_params = url_json + ("?" + urlencode(params) if params else "")

            # Use primary French proxy service
            proxy_base = self.proxy_config.get_proxy('fr_default')

            json_parser = None

            # Try the proxy service
            try:
                # Use URL encoding (Variant 2) - proven to work best
                proxied_url = proxy_base + quote(dest_with_params, safe="")

                safe_print(f"✅ [MyTF1] Trying TF1 LIVE stream through French proxy: {proxy_base[:50]}...")
                data_try = self._safe_api_call(proxied_url, headers=headers_video_stream, max_retries=2)
                safe_print(f"✅ *** FINAL PROXY URL (LIVE): {proxied_url}")

                # Check if the response is successful and not geo-blocked
                if data_try and data_try.get('delivery', {}).get('code', 500) <= 400:
                    # Additional check: ensure the country is not US (geo-blocked)
                    delivery_country = data_try.get('delivery', {}).get('country', 'UNKNOWN')
                    delivery_code = data_try.get('delivery', {}).get('code', 500)

                    if delivery_country != 'US':
                        # Check if we got a successful delivery code (200) or acceptable error (403 might be auth-related)
                        if delivery_code == 200:
                            json_parser = data_try
                            safe_print(f"✅ [MyTF1] French proxy successful for live stream - Country: {delivery_country}, Code: {delivery_code}")
                        else:
                            # We got a non-200 response (e.g., 403) - proxy might not be forwarding auth correctly
                            # Try direct call as fallback since direct calls work with authentication
                            safe_print(f"❌ [MyTF1] French proxy returned non-200 code {delivery_code} - trying direct call")
                            safe_print(f"✅ [MyTF1] Making DIRECT request for live feed: {url_json}")
                            safe_print(f"✅ *** FINAL DIRECT URL (LIVE): {url_json}")
                            json_parser = self._safe_api_call(url_json, headers=headers_video_stream, params=params)
                    else:
                        safe_print("❌ [MyTF1] French proxy returned US country (still geo-blocked)")
                        # Try direct call as fallback
                        safe_print("❌ [MyTF1] French proxy failed; trying direct call as fallback...")
                        safe_print(f"✅ [MyTF1] Making DIRECT request for live feed: {url_json}")
                        safe_print(f"✅ *** FINAL DIRECT URL (LIVE): {url_json}")
                        json_parser = self._safe_api_call(url_json, headers=headers_video_stream, params=params)
                else:
                    safe_print("❌ [MyTF1] French proxy failed or returned error code")
                    # Try direct call as fallback
                    safe_print("❌ [MyTF1] French proxy failed; trying direct call as fallback...")
                    safe_print(f"✅ [MyTF1] Making DIRECT request for live feed: {url_json}")
                    safe_print(f"✅ *** FINAL DIRECT URL (LIVE): {url_json}")
                    json_parser = self._safe_api_call(url_json, headers=headers_video_stream, params=params)

            except Exception as e:
                safe_print(f"❌ [MyTF1] Error with French proxy: {e}")
                # Try direct call as fallback
                safe_print("❌ [MyTF1] French proxy failed; trying direct call as fallback...")
                safe_print(f"✅ [MyTF1] Making DIRECT request for live feed: {url_json}")
                safe_print(f"✅ *** FINAL DIRECT URL (LIVE): {url_json}")
                json_parser = self._safe_api_call(url_json, headers=headers_video_stream, params=params)

            # If proxy failed, try direct call as last resort
            if not json_parser:
                safe_print("❌ [MyTF1] French proxy failed; trying direct call as last resort...")
                safe_print(f"✅ [MyTF1] Making DIRECT request for live feed: {url_json}")
                safe_print(f"✅ *** FINAL DIRECT URL (LIVE): {url_json}")
                json_parser = self._safe_api_call(url_json, headers=headers_video_stream, params=params)

            if json_parser:
                safe_print(f"✅ [MyTF1] Stream API response received for {video_id}")
                safe_print(f"✅ [MyTF1] Response JSON: {json_parser}")
                
                if json_parser['delivery']['code'] <= 400:
                    video_url = json_parser['delivery']['url']
                    safe_print(f"✅ [MyTF1] Stream URL obtained: {video_url[:50]}...")

                    license_url = None
                    license_headers = {}

                    # Enhanced DRM processing for TF1 live streams
                    if 'drms' in json_parser['delivery'] and json_parser['delivery']['drms']:
                        drm_info = json_parser['delivery']['drms'][0]
                        safe_print(f"✅ [MyTF1] DRM Info found: {drm_info}")
                        
                        license_url = drm_info.get('url')
                        if not license_url:
                            safe_print("❌ [MyTF1] No license URL in DRM info, using fallback")
                            license_url = self.license_base_url % video_id
                        else:
                            safe_print(f"✅ [MyTF1] License URL from DRM: {license_url}")
                        
                        # Extract all headers from DRM info (like Kodi plugin does)
                        for header_item in drm_info.get('h', []):
                            header_key = header_item.get('k')
                            header_value = header_item.get('v')
                            if header_key and header_value:
                                license_headers[header_key] = header_value
                                safe_print(f"✅ [MyTF1] DRM Header: {header_key} = {header_value}")
                    else:
                        # Fallback to generic license URL if no DRM info is present
                        safe_print("❌ [MyTF1] No DRM info found, using fallback license URL")
                        license_url = self.license_base_url % video_id

                    # Prefer HLS if present, else MPD
                    lower_url = (video_url or '').lower()
                    is_hls = lower_url.endswith('.m3u8') or 'hls' in lower_url or 'm3u8' in lower_url

                    # Build MediaFlow URL with DRM support
                    if self.mediaflow_url and self.mediaflow_password:
                        # Determine endpoint based on stream type
                        if is_hls:
                            endpoint = '/proxy/hls/manifest.m3u8'
                        else:
                            endpoint = '/proxy/mpd/manifest.m3u8'
                        
                        # Build request headers for MediaFlow
                        mediaflow_headers = {
                            'user-agent': headers_video_stream['User-Agent'],
                            'referer': self.base_url,
                            'origin': self.base_url,
                            'authorization': f"Bearer {self.auth_token}"
                        }
                        
                        # Use enhanced MediaFlow utility with DRM support
                        final_url = build_mediaflow_url(
                            base_url=self.mediaflow_url,
                            password=self.mediaflow_password,
                            destination_url=video_url,
                            endpoint=endpoint,
                            request_headers=mediaflow_headers,
                            license_url=license_url,
                            license_headers=license_headers
                        )
                        safe_print(f"✅ *** FINAL MEDIAFLOW URL (LIVE): {final_url}")
                        manifest_type = 'hls' if is_hls else 'mpd'
                    else:
                        final_url = video_url
                        manifest_type = 'hls' if is_hls else 'mpd'

                    # Extract current program title from API response for enhanced stream title
                    # API provides: media.programName (e.g., "Chicago Police Department")
                    # and media.shortTitle (e.g., "Le protecteur" - episode title)
                    current_program = None
                    if 'media' in json_parser:
                        media_info = json_parser['media']
                        # Prefer programName, fallback to title
                        current_program = media_info.get('programName') or media_info.get('title', '')
                        safe_print(f"✅ [MyTF1] Current program: {current_program}")
                    
                    # Build enhanced stream title: [FORMAT] Current Program Name
                    format_label = 'HLS' if manifest_type == 'hls' else 'MPD'
                    if current_program:
                        stream_title = f"[{format_label}] {current_program}"
                    else:
                        stream_title = f"[{format_label}] {channel_name.upper()}"

                    stream_info = {
                        "url": final_url,
                        "manifest_type": manifest_type,
                        "title": stream_title,
                        "headers": headers_video_stream
                    }
                    
                    # Add license info to stream_info if available
                    if license_url:
                        stream_info["licenseUrl"] = license_url
                        if license_headers:
                            stream_info["licenseHeaders"] = license_headers
                    
                    safe_print(f"✅ [MyTF1] MyTF1 stream info prepared: manifest_type={stream_info['manifest_type']}, title={stream_title}")
                    return stream_info
                else:
                    safe_print(f"❌ [MyTF1] MyTF1 delivery error: {json_parser['delivery']['code']}")
            else:
                safe_print("❌ [MyTF1] MyTF1 API error: No valid JSON from mediainfo (proxy and direct attempts failed)")
                
        except Exception as e:
            safe_print(f"❌ [MyTF1] Error getting stream for {channel_name}: {e}")
        
        return None
    
    def get_episode_stream_url(self, episode_id: str) -> Optional[Dict]:
        """Get stream URL for a specific episode (for replay content) with robust error handling"""
        # Extract the actual episode ID from our format
        if "episode:" in episode_id:
            actual_episode_id = episode_id.split("episode:")[-1]
        else:
            actual_episode_id = episode_id

        try:
            safe_print(f"✅ [MyTF1] Getting replay stream for MyTF1 episode: {actual_episode_id}")

            # Lazy authentication - only authenticate when needed
            safe_print("✅ [MyTF1] Checking authentication...")
            if not self._authenticated and not self._authenticate():
                safe_print("❌ [MyTF1] MyTF1 authentication failed")
                return None

            # Use the same approach as the reference plugin for replay content
            headers_video_stream = {
                "authorization": f"Bearer {self.auth_token}",
                "User-Agent": get_random_windows_ua(),
                "referer": self.base_url,
                "origin": self.base_url,
                # Hint FR locale to upstream
                "accept-language": "fr-FR,fr;q=0.9,en;q=0.8,en-US;q=0.7",
                # Some stacks require explicit Accept for JSON
                "accept": "application/json, text/plain, */*",
                # Additional headers to help with geo-blocking
                "Accept-Encoding": "gzip, deflate, br",
                "Accept-Charset": "UTF-8,*;q=0.5",
                "Cache-Control": "no-cache",
                "Pragma": "no-cache",
                # Additional security headers that might help
                "Sec-Fetch-Dest": "empty",
                "Sec-Fetch-Mode": "cors",
                "Sec-Fetch-Site": "same-site",
                "Sec-GPC": "1",
                # Content Security Policy headers that might be checked
                "DNT": "1",
                "Upgrade-Insecure-Requests": "1",
            }
            params = {
                'context': 'MYTF1',
                'pver': '5010000',
                'platform': 'web',
                'device': 'desktop',
                'os': 'linux',
                'osVersion': 'unknown',
                'topDomain': 'www.tf1.fr',
                'playerVersion': '5.19.0',
                'productName': 'mytf1',
                'productVersion': '3.22.0',
            }
            
            url_json = f"{self.video_stream_url}/{actual_episode_id}"
            
            # Try French proxy service for replay streams (CRITICAL for success)
            dest_with_params = url_json + ("?" + urlencode(params) if params else "")

            # Use primary French proxy service for replay content
            proxy_base = self.proxy_config.get_proxy('fr_default')

            json_parser = None

            # Try the proxy service for replay content
            try:
                # Use URL encoding (Variant 2) - proven to work best and get 200 responses
                proxied_url = proxy_base + quote(dest_with_params, safe="")

                safe_print(f"✅ [MyTF1] Trying TF1 REPLAY stream through French proxy: {proxy_base[:50]}...")
                data_try = self._safe_api_call(proxied_url, headers=headers_video_stream, max_retries=2)
                safe_print(f"✅ *** FINAL PROXY URL (TF1 REPLAY): {proxied_url}")

                # Check if the response is successful and not geo-blocked
                if data_try and data_try.get('delivery', {}).get('code', 500) <= 400:
                    # Additional check: ensure the country is not US (geo-blocked)
                    delivery_country = data_try.get('delivery', {}).get('country', 'UNKNOWN')
                    delivery_code = data_try.get('delivery', {}).get('code', 500)

                    if delivery_country != 'US':
                        # Check if we got a successful delivery code (200) or acceptable error (403 might be auth-related)
                        if delivery_code == 200:
                            json_parser = data_try
                            safe_print(f"✅ [MyTF1] French proxy successful for TF1 REPLAY - Country: {delivery_country}, Code: {delivery_code}")
                        else:
                            # We got a non-200 response (e.g., 403) - proxy might not be forwarding auth correctly
                            # Try direct call as fallback since direct calls work with authentication
                            safe_print(f"❌ [MyTF1] French proxy returned non-200 code {delivery_code} - trying direct call")
                            safe_print(f"✅ [MyTF1] Making DIRECT request for replay feed: {url_json}")
                            safe_print(f"✅ *** FINAL DIRECT URL (TF1 REPLAY): {url_json}")
                            json_parser = self._safe_api_call(url_json, headers=headers_video_stream, params=params)
                    else:
                        safe_print("❌ [MyTF1] French proxy returned US country (still geo-blocked)")
                        # Try direct call as fallback
                        safe_print("❌ French proxy failed; trying direct call as fallback...")
                        safe_print(f"✅ [MyTF1] Making DIRECT request for replay feed: {url_json}")
                        safe_print(f"✅ *** FINAL DIRECT URL (TF1 REPLAY): {url_json}")
                        json_parser = self._safe_api_call(url_json, headers=headers_video_stream, params=params)
                else:
                    safe_print("❌ [MyTF1] French proxy failed or returned error code")
                    # Try direct call as fallback
                    safe_print("❌ French proxy failed; trying direct call as fallback...")
                    safe_print(f"✅ [MyTF1] Making DIRECT request for replay feed: {url_json}")
                    safe_print(f"✅ *** FINAL DIRECT URL (TF1 REPLAY): {url_json}")
                    json_parser = self._safe_api_call(url_json, headers=headers_video_stream, params=params)

            except Exception as e:
                safe_print(f"❌ [MyTF1] Error with French proxy: {e}")
                # Try direct call as fallback
                safe_print("❌ French proxy failed; trying direct call as fallback...")
                safe_print(f"✅ [MyTF1] Making DIRECT request for replay feed: {url_json}")
                safe_print(f"✅ *** FINAL DIRECT URL (TF1 REPLAY): {url_json}")
                json_parser = self._safe_api_call(url_json, headers=headers_video_stream, params=params)

            # CRITICAL: If proxy failed, try direct call as last resort (will likely fail with 403)
            if not json_parser:
                safe_print("❌ French proxy failed; trying direct call as last resort (will likely fail)...")
                safe_print(f"✅ [MyTF1] Making DIRECT request for replay feed: {url_json}")
                safe_print(f"✅ *** FINAL DIRECT URL (TF1 REPLAY): {url_json}")
                json_parser = self._safe_api_call(url_json, headers=headers_video_stream, params=params)

            if json_parser and json_parser.get('delivery', {}).get('code', 500) <= 400:
                video_url = json_parser['delivery']['url']
                safe_print(f"✅ [MyTF1] Stream URL obtained: {video_url}")

                license_url = None
                license_headers = {}

                # Enhanced DRM processing for TF1 replay content (like Kodi plugin)
                if 'drms' in json_parser['delivery'] and json_parser['delivery']['drms']:
                    drm_info = json_parser['delivery']['drms'][0]
                    safe_print(f"✅ [MyTF1] Replay DRM Info found: {drm_info}")
                    
                    license_url = drm_info.get('url')
                    if not license_url:
                        safe_print("❌ [MyTF1] No license URL in replay DRM info, using fallback")
                        license_url = self.license_base_url % actual_episode_id
                    else:
                        safe_print(f"✅ [MyTF1] Replay License URL from DRM: {license_url}")
                    
                    # Extract all headers from DRM info (comprehensive like Kodi)
                    for header_item in drm_info.get('h', []):
                        header_key = header_item.get('k')
                        header_value = header_item.get('v')
                        if header_key and header_value:
                            license_headers[header_key] = header_value
                            safe_print(f"✅ [MyTF1] Replay DRM Header: {header_key} = {header_value}")
                else:
                    # Fallback to generic license URL if no DRM info is present
                    safe_print("❌ [MyTF1] No replay DRM info found, using fallback license URL")
                    license_url = self.license_base_url % actual_episode_id

                # Check if the stream URL is MPD or HLS
                is_mpd = video_url.lower().endswith('.mpd') or 'mpd' in video_url.lower()
                is_hls = video_url.lower().endswith('.m3u8') or 'hls' in video_url.lower() or 'm3u8' in video_url.lower()

                # Check if processed file already exists (for TF1 replays only)
                # Get processor URL from proxy config
                proxy_config = get_proxy_config()
                processor_url = proxy_config.get_proxy('nm3u8_processor')
                if not processor_url:
                    safe_print("❌ [MyTF1] ERROR: nm3u8_processor not configured in credentials.json")
                    return None
                
                safe_print(f"✅ [MyTF1] Using processor API: {processor_url}")
                processed_filename = f"{actual_episode_id}.mp4"
                safe_print(f"✅ [MyTF1] Looking for processed file: {processed_filename}")
                
                # First check Real-Debrid folder
                try:
                    safe_print("✅ [MyTF1] Loading credentials for Real-Debrid check...")
                    all_creds = load_credentials()
                    safe_print(f"✅ [MyTF1] Credentials loaded. Keys: {list(all_creds.keys())}")
                    
                    rd_folder = all_creds.get('realdebridfolder')
                    safe_print(f"✅ [MyTF1] Real-Debrid folder from credentials: {rd_folder}")
                    
                    if rd_folder:
                        safe_print(f"✅ [MyTF1] Checking if '{processed_filename}' is listed in RD folder...")
                        
                        try:
                            # Fetch the folder listing page with browser-like headers
                            rd_headers = {
                                'User-Agent': get_random_windows_ua(),
                                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                                'Accept-Language': 'en-US,en;q=0.9,fr;q=0.8',
                                'Accept-Encoding': 'gzip, deflate, br',
                                'DNT': '1',
                                'Connection': 'keep-alive',
                                'Upgrade-Insecure-Requests': '1',
                                'Sec-Fetch-Dest': 'document',
                                'Sec-Fetch-Mode': 'navigate',
                                'Sec-Fetch-Site': 'none',
                                'Cache-Control': 'max-age=0'
                            }
                            folder_response = requests.get(rd_folder, headers=rd_headers, timeout=10)
                            safe_print(f"✅ [MyTF1] RD Folder HTTP Status: {folder_response.status_code}")
                            
                            if folder_response.status_code == 200:
                                # Check if filename appears in the folder listing
                                folder_content = folder_response.text
                                if processed_filename in folder_content:
                                    rd_file_url = rd_folder.rstrip('/') + '/' + processed_filename
                                    safe_print(f"✅ [MyTF1] File '{processed_filename}' found in RD folder listing!")
                                    safe_print(f"✅ [MyTF1] Returning RD URL: {rd_file_url}")
                                    return {
                                        "url": rd_file_url,
                                        "manifest_type": "video",
                                        "title": "✅ [RD] DRM-Free Video",
                                        "filename": processed_filename
                                    }
                                else:
                                    safe_print(f"⚠️ [MyTF1] File '{processed_filename}' NOT found in RD folder listing, will check processor_url")
                            else:
                                safe_print(f"⚠️ [MyTF1] Could not access RD folder (HTTP {folder_response.status_code}), checking processor_url...")
                        except Exception: # requests.exceptions.Timeout
                            safe_print(f"⚠️ [MyTF1] RD folder request timed out, checking processor_url...")
                        except Exception as e:
                            safe_print(f"❌ [MyTF1] RD folder request error: {e}, checking processor_url...")
                    else:
                        safe_print("⚠️ [MyTF1] Real-Debrid folder not configured in credentials, checking processor_url...")
                except Exception as e:
                    safe_print(f"❌ [MyTF1] Error checking Real-Debrid: {e}")
                    safe_print(f"❌ [MyTF1] Proceeding to processor_url check as fallback...")
                
                # Then check processor_url location
                processed_url = f"{processor_url}/stream/{processed_filename}"
                safe_print(f"✅ [MyTF1] Checking processor_url location: {processed_url}")

                
                processed_file_exists = False
                try:
                    check_response = requests.head(processed_url, timeout=5)
                    safe_print(f"✅ [MyTF1] PROCESSOR URL HTTP Status: {check_response.status_code}")
                    
                    if check_response.status_code == 200:
                        # File exists - return immediately
                        safe_print(f"✅ [MyTF1] Processed file already exists: {processed_url}")
                        processed_file_exists = True
                        return {
                            "url": processed_url,
                            "manifest_type": "video",
                            "title": "✅ DRM-Free Video",
                            "filename": processed_filename
                        }
                    else:
                        safe_print(f"⚠️ [MyTF1] PROCESSOR URL file not found (HTTP {check_response.status_code})")
                except Exception as e:
                    # Error checking file - proceed with normal flow
                    safe_print(f"⚠️ [MyTF1] Error checking processor_url: {e}")
                    pass

                # For DRM-protected MPD streams (replays only), use external DASH proxy
                if is_mpd and license_url:
                    try:
                        safe_print("✅ [MyTF1] Using DASH proxy for DRM-protected MPD replay stream")

                        # Extract DRM keys using TF1 DRM extractor
                        drm_keys_dict = {}
                        try:
                            from app.providers.fr.tf1_drm_key_extractor import TF1DRMExtractor
                            safe_print("✅ [MyTF1] Extracting DRM keys for TF1 replay...")
                            
                            extractor = TF1DRMExtractor(wvd_path="app/providers/fr/device.wvd")
                            drm_keys_dict = extractor.get_keys(
                                video_url=video_url,
                                license_url=license_url,
                                verbose=False
                            )
                            
                            if drm_keys_dict:
                                safe_print(f"✅ [MyTF1] Extracted {len(drm_keys_dict)} DRM key(s)")
                                for kid, key in drm_keys_dict.items():
                                    safe_print(f"   KID: {kid} -> KEY: {key}")
                                    
                                # Format keys for N_m3u8DL-RE (kid:key format)
                                formatted_keys = [f"{kid}:{key}" for kid, key in drm_keys_dict.items()]
                                
                                # Print full N_m3u8DL-RE command with all keys
                                keys_param = " ".join([f"--key {key}" for key in formatted_keys])
                                safe_print(f'./N_m3u8DL-RE "{video_url}" --save-name "{actual_episode_id}" --select-video best --select-audio all --select-subtitle all -mt -M format=mkv --log-level OFF --binary-merge {keys_param}')
                                
                                # Trigger background processing with multiple keys
                                from app.utils.nm3u8_drm_processor import process_drm_simple
                                safe_print("✅ [MyTF1] Triggering background DRM processing...")
                                
                                online_result = process_drm_simple(
                                    url=video_url,
                                    save_name=f"{actual_episode_id}",
                                    keys=formatted_keys,
                                    quality="best",
                                    format="mkv",
                                    binary_merge=True
                                )
                                
                                if online_result.get("success"):
                                    safe_print("✅ [MyTF1] Background processing started successfully")
                                else:
                                    safe_print(f"⚠️ [MyTF1] Background processing failed to start: {online_result.get('error')}")
                            else:
                                safe_print("⚠️ [MyTF1] No DRM keys extracted")
                                
                        except ImportError:
                            safe_print("⚠️ [MyTF1] TF1 DRM extractor not available (pywidevine not installed)")
                        except Exception as drm_error:
                            safe_print(f"⚠️ [MyTF1] DRM key extraction failed: {drm_error}")

                        # URL encode the manifest and license URLs (NOT base64)
                        encoded_manifest = quote(video_url, safe='')
                        encoded_license = quote(license_url, safe='')

                        # Construct the DASH proxy URL
                        dash_proxy_base = self.proxy_config.get_proxy('dash_proxy')
                        proxy_params = f"mpd={encoded_manifest}&widevine.isActive=true&widevine.drmKeySystem=com.widevine.alpha&widevine.licenseServerUrl={encoded_license}"

                        final_url = f"{dash_proxy_base}/proxy?{proxy_params}"
                        manifest_type = 'mpd'

                        safe_print(f"✅ [MyTF1] DASH proxy URL generated: {final_url}")

                        # Build primary DASH proxy stream
                        primary_stream = {
                            "url": final_url,  # This will be opened externally
                            "manifest_type": manifest_type,
                            "title": "DASH Proxy Stream (DRM)",
                            "headers": headers_video_stream
                        }

                        # Add license info if available
                        if license_url:
                            primary_stream["licenseUrl"] = license_url
                            if license_headers:
                                primary_stream["licenseHeaders"] = license_headers
                        
                        # Add DRM keys to stream info if extracted
                        if drm_keys_dict:
                            primary_stream["drm_keys"] = drm_keys_dict

                        # Build secondary processed stream (if processing was triggered)
                        streams = [primary_stream]

                        if drm_keys_dict:
                            # Add a second stream pointing to the processed file
                            # Check if processing was successfully triggered
                            if online_result.get("success"):
                                # Processing successfully triggered - file doesn't exist yet (checked earlier)
                                processed_stream = {
                                    "url": "https://stream-not-available",
                                    "manifest_type": "video",
                                    "title": "⏳ DRM-Free Video (Processing in background...)",
                                    "description": "Stream not available - Processing in progress. Please check back in a few minutes."
                                }
                            else:
                                # Processing failed to start
                                processed_stream = {
                                    "url": "https://stream-not-available",
                                    "manifest_type": "video",
                                    "title": "❌ DRM Processing Failed",
                                    "description": "Stream not available - DRM processing could not be started. Please try again later."
                                }
                            
                            streams.append(processed_stream)
                            safe_print("✅ [MyTF1] Returning 2 streams: DASH proxy + processed file")
                        else:
                            safe_print("✅ [MyTF1] Returning 1 stream: DASH proxy only")

                        safe_print("✅ [MyTF1] MyTF1 stream(s) prepared")
                        return streams

                    except Exception as e:
                        safe_print(f"❌ [MyTF1] DASH proxy URL generation failed: {e}")
                        # Fallback to MediaFlow or direct URL
                        final_url = video_url
                        manifest_type = 'mpd'
                        # Continue to MediaFlow fallback logic
                else:
                    # Use existing MediaFlow proxy for HLS streams or non-DRM MPD streams
                    if self.mediaflow_url and self.mediaflow_password:
                        try:
                            # Determine the appropriate endpoint based on stream type
                            if is_hls:
                                endpoint = '/proxy/hls/manifest.m3u8'
                                safe_print("✅ [MyTF1] Using HLS proxy for HLS stream")
                            elif is_mpd:
                                endpoint = '/proxy/mpd/manifest.m3u8'
                                safe_print("✅ [MyTF1] Using MPD proxy for MPD stream")
                            else:
                                # Default to HLS proxy for unknown formats
                                endpoint = '/proxy/hls/manifest.m3u8'
                                safe_print("✅ [MyTF1] Using HLS proxy for unknown format")

                            # Build request headers for MediaFlow
                            mediaflow_headers = {
                                'user-agent': headers_video_stream['User-Agent'],
                                'referer': self.base_url,
                                'origin': self.base_url,
                                'authorization': f"Bearer {self.auth_token}"
                            }

                            # Use enhanced MediaFlow utility with full DRM support
                            final_url = build_mediaflow_url(
                                base_url=self.mediaflow_url,
                                password=self.mediaflow_password,
                                destination_url=video_url,
                                endpoint=endpoint,
                                request_headers=mediaflow_headers,
                                license_url=license_url,
                                license_headers=license_headers
                            )

                            safe_print(f"✅ *** FINAL MEDIAFLOW URL (REPLAY): {final_url}")
                            manifest_type = 'hls' if is_hls else ('mpd' if is_mpd else 'hls')

                            safe_print(f"✅ [MyTF1] MediaFlow URL with DRM support generated: {final_url[:50]}...")

                        except Exception as e:
                            safe_print(f"❌ [MyTF1] MediaFlow URL generation failed: {e}")
                            # Fallback to direct URL
                            final_url = video_url
                            manifest_type = 'hls' if is_hls else ('mpd' if is_mpd else 'hls')
                    else:
                        # No MediaFlow, use direct URL
                        final_url = video_url
                        manifest_type = 'hls' if is_hls else ('mpd' if is_mpd else 'hls')

                # For non-DASH proxy streams, construct stream_info normally
                stream_info = {
                    "url": final_url,
                    "manifest_type": manifest_type,
                    "headers": headers_video_stream
                }

                # Add license info to stream_info if available
                if license_url:
                    stream_info["licenseUrl"] = license_url
                    if license_headers:
                        stream_info["licenseHeaders"] = license_headers

                safe_print(f"✅ [MyTF1] MyTF1 stream info prepared: manifest_type={stream_info['manifest_type']}")
                return stream_info
            else:
                safe_print(f"❌ [MyTF1] MyTF1 delivery error: {json_parser.get('delivery', {}).get('code', 'Unknown') if json_parser else 'No response'}")
                
        except Exception as e:
            safe_print(f"❌ [MyTF1] Error getting episode stream: {e}")
            import traceback
            traceback.print_exc()
        
        return None
    
    def _get_show_api_metadata(self, show_id: str, show_info: Dict) -> Dict:
        """Get show metadata from TF1+ API with error handling and fallbacks"""
        try:
            # Use the same API call as the reference plugin
            params = {
                'id': '483ce0f',
                'variables': '{"context":{"persona":"PERSONA_2","application":"WEB","device":"DESKTOP","os":"WINDOWS"},"filter":{"channel":"%s"},"offset":0,"limit":500}' % show_info['channel'].lower()
            }
            headers = {
                'content-type': 'application/json',
                'referer': 'https://www.tf1.fr/programmes-tv'
            }

            # TF1 GraphQL programs metadata - Use DIRECT raw URL only (no proxy)
            safe_print(f"✅ [MyTF1] Making DIRECT GraphQL programs metadata request (raw URL): {self.api_url}")
            data = self._safe_api_call(self.api_url, headers=headers, params=params, max_retries=3)
            
            if data and 'data' in data and 'programs' in data['data'] and 'items' in data['data']['programs']:
                programs = data['data']['programs']['items']
                
                # Find the specific show
                for program in programs:
                    program_name = program.get('name', '')
                    if show_id in program_name.lower() or show_info['name'].lower() in program_name.lower():
                        # Extract images from decoration (same as reference plugin)
                        if 'decoration' in program:
                            decoration = program['decoration']
                            
                            # Get poster image
                            poster = None
                            if 'image' in decoration and 'sources' in decoration['image']:
                                poster = decoration['image']['sources'][0].get('url', '')
                            
                            # Get fanart/background
                            fanart = None
                            if 'background' in decoration and 'sources' in decoration['background']:
                                fanart = decoration['background']['sources'][0].get('url', '')
                            
                            # Get logo (use poster as logo if available)
                            logo = poster if poster else get_logo_url("fr", "tf1", self.request)
                            
                            safe_print(f"✅ [MyTF1] Found show metadata for {show_id}: poster={poster[:50] if poster else 'N/A'}..., fanart={fanart[:50] if fanart else 'N/A'}...")
                            
                            return {
                                "poster": poster,
                                "fanart": fanart,
                                "logo": logo
                            }
            
            safe_print(f"❌ [MyTF1] No show metadata found for {show_id}")
            return {}
            
        except Exception as e:
            safe_print(f"❌ [MyTF1] Error fetching show metadata for {show_id}: {e}")
            return {}
    
    def resolve_stream(self, stream_id: str) -> Optional[Dict]:
        """Resolve stream URL for a given stream ID"""
        # This method needs to be implemented based on the specific stream ID format
        # For now, return None as a placeholder
        safe_print(f"❌ MyTF1Provider: resolve_stream not implemented for {stream_id}")
        return None
