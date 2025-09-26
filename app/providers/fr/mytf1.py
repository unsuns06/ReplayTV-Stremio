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
import logging
import os
import urllib.parse
from urllib.parse import urlencode, quote, unquote
import random
from typing import Dict, List, Optional, Tuple
from fastapi import Request
from app.utils.credentials import get_provider_credentials
from app.utils.safe_print import safe_print
from app.utils.mediaflow import build_mediaflow_url
from app.utils.base_url import get_base_url, get_logo_url
from app.utils.client_ip import merge_ip_headers, make_ip_headers

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
    safe_print(f"✅ [TF1 URL Decoder] Original URL: {original_url}")
    decoded_url = unquote(original_url)
    safe_print(f"✅ [TF1 URL Decoder] Force-decoded URL: {decoded_url}")
    return decoded_url

class MyTF1Provider:
    """MyTF1 provider implementation with robust error handling and fallbacks"""
    
    def __init__(self, request: Optional[Request] = None):
        self.credentials = get_provider_credentials('mytf1')
        self.base_url = "https://www.tf1.fr"
        self.api_key = "3_hWgJdARhz_7l1oOp3a8BDLoR9cuWZpUaKG4aqF7gum9_iK3uTZ2VlDBl8ANf8FVk"
        self.api_url = "https://www.tf1.fr/graphql/web"
        self.video_stream_url = "https://mediainfo.tf1.fr/mediainfocombo"
        # MediaFlow config via env and credentials with deployment-friendly fallbacks
        # First try environment variables (for deployment)
        self.mediaflow_url = os.getenv('MEDIAFLOW_PROXY_URL')
        self.mediaflow_password = os.getenv('MEDIAFLOW_API_PASSWORD')
        
        # Fallback to credentials file (for local development)
        if not self.mediaflow_url or not self.mediaflow_password:
            mediaflow_creds = get_provider_credentials('mediaflow')
            if not self.mediaflow_url:
                self.mediaflow_url = mediaflow_creds.get('url')
            if not self.mediaflow_password:
                self.mediaflow_password = mediaflow_creds.get('password')
        
        # Final fallback for local development
        if not self.mediaflow_url:
            self.mediaflow_url = 'http://localhost:8888'
        
        # Log MediaFlow configuration for debugging
        safe_print(f"✅ [MyTF1Provider] MediaFlow URL: {self.mediaflow_url}")
        safe_print(f"✅ [MyTF1Provider] MediaFlow Password: {'***' if self.mediaflow_password else 'None'}")
        safe_print(f"✅ [MyTF1Provider] MediaFlow configured: {bool(self.mediaflow_url and self.mediaflow_password)}")
        
        # Store request for base URL determination
        self.request = request
        # Get base URL for static assets
        self.static_base = get_base_url(request)

        self.accounts_login = "https://compte.tf1.fr/accounts.login"
        self.accounts_bootstrap = "https://compte.tf1.fr/accounts.webSdkBootstrap"
        self.token_gigya_web = "https://www.tf1.fr/token/gigya/web"
        self.license_base_url = 'https://drm-wide.tf1.fr/proxy?id=%s' # Renamed to avoid conflict
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': get_random_windows_ua()
        })
        # Set timeouts for all requests
        self.session.timeout = 10
        self.auth_token = None
        self._authenticated = False

        # Initialize IP forwarding headers (critical for geo-restricted content)
        self.viewer_ip_headers = make_ip_headers(None, getattr(request, 'headers', {}) if request else {})

    # TF1+ shows configuration based on reference plugin
        self.shows = {
            "sept-a-huit": {
                "id": "sept-a-huit",
                "name": "Sept à huit",
                "description": "Magazine d'information de TF1",
                "channel": "TF1",
                "genres": ["News", "Documentary", "Magazine"],
                "year": 2024,
                "rating": "Tous publics"
            },
            "quotidien": {
                "id": "quotidien",
                "name": "Quotidien",
                "description": "Émission de divertissement et d'actualité de TMC",
                "channel": "TMC",
                "genres": ["Entertainment", "News", "Talk Show"],
                "year": 2024,
                "rating": "Tous publics"
            }
        }
    
    def _safe_api_call(self, url: str, params: Dict = None, headers: Dict = None, data: Dict = None, method: str = 'GET', max_retries: int = 3) -> Optional[Dict]:
        """Make a safe API call with retry logic and error handling"""
        for attempt in range(max_retries):
            try:
                # Rotate User-Agent for each attempt
                current_headers = headers or {}
                current_headers['User-Agent'] = get_random_windows_ua()

                # Forward viewer IP to upstream servers (critical for geo-restricted content)
                # Use the instance's pre-computed IP headers to ensure consistency
                for header_name, header_value in self.viewer_ip_headers.items():
                    current_headers[header_name] = header_value

                # Optional per-request proxy support via env
                proxy_env = os.getenv('MYTF1_HTTP_PROXY')
                proxies = {'http': proxy_env, 'https': proxy_env} if proxy_env else None

                
                safe_print(f"✅ [MyTF1] API call attempt {attempt + 1}/{max_retries}: {url}")
                if params:
                    safe_print(f"✅ [MyTF1] Request params: {params}")
                if headers:
                    safe_print(f"✅ [MyTF1] Request headers (pre-merge): {headers}")
                try:
                    safe_print(f"✅ [MyTF1] Request headers (effective): {current_headers}")
                except Exception:
                    pass
                
                if method.upper() == 'POST':
                    if data:
                        # Check if we need form data or JSON based on Content-Type
                        if current_headers.get('Content-Type') == 'application/x-www-form-urlencoded':
                            response = self.session.post(url, params=params, headers=current_headers, data=data, timeout=15, proxies=proxies)
                        else:
                            response = self.session.post(url, params=params, headers=current_headers, json=data, timeout=15, proxies=proxies)
                    else:
                        response = self.session.post(url, params=params, headers=current_headers, timeout=15, proxies=proxies)
                else:
                    response = self.session.get(url, params=params, headers=current_headers, timeout=15, proxies=proxies)
                
                if response.status_code == 200:
                    # Log response details for debugging
                    safe_print(f"✅ [MyTF1] Response headers: {dict(response.headers)}")
                    safe_print(f"✅ [MyTF1] Content-Type: {response.headers.get('content-type', 'Not set')}")
                    
                    # Try to parse JSON with multiple strategies
                    try:
                        return response.json()
                    except json.JSONDecodeError as e:
                        safe_print(f"❌ [MyTF1] JSON parse error on attempt {attempt + 1}: {e}")
                        safe_print(f"❌ [MyTF1] Error position: line {e.lineno}, column {e.colno}, char {e.pos}")
                        
                        # Log the raw response for debugging
                        text = response.text
                        safe_print(f"❌ [MyTF1] Raw response length: {len(text)} characters")
                        safe_print(f"❌ [MyTF1] Raw response (first 500 chars): {text[:500]}")
                        
                        # Log the problematic area around the error
                        if e.pos > 0:
                            start = max(0, e.pos - 50)
                            end = min(len(text), e.pos + 1)
                            safe_print(f"❌ [MyTF1] Context around error (chars {start}-{end}): {text[start:end]}")
                        
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
                                safe_print(f"✅ [MyTF1] Attempting to fix unquoted property names...")
                                return json.loads(fixed_text)
                        except:
                            pass
                        
                        # Strategy 3: Try to extract JSON from larger response
                        if '<html' in text.lower():
                            safe_print(f"❌ [MyTF1] Received HTML instead of JSON on attempt {attempt + 1}")
                        else:
                            safe_print(f"❌ [MyTF1] Malformed response on attempt {attempt + 1}: {text[:200]}...")
                        
                        # Wait before retry
                        if attempt < max_retries - 1:
                            time.sleep(2 ** attempt)  # Exponential backoff
                            continue
                        
                elif response.status_code in [403, 429, 500]:
                    safe_print(f"❌ [MyTF1] HTTP {response.status_code} on attempt {attempt + 1}")
                    safe_print(f"❌ [MyTF1] Response headers: {dict(response.headers)}")
                    safe_print(f"❌ [MyTF1] Response content: {response.text[:500]}...")
                    
                    # For 500 errors with max_retries=1, fail fast to enable proxy fallback
                    if response.status_code == 500 and max_retries == 1:
                        safe_print(f"❌ [MyTF1] HTTP 500 with max_retries=1, failing fast for proxy fallback")
                        return None
                    
                    if attempt < max_retries - 1:
                        time.sleep(2 ** attempt)
                        continue
                else:
                    safe_print(f"❌ [MyTF1] HTTP {response.status_code} on attempt {attempt + 1}")
                    safe_print(f"❌ [MyTF1] Response headers: {dict(response.headers)}")
                    safe_print(f"❌ [MyTF1] Response content: {response.text[:500]}...")
                    
            except Exception as e:
                safe_print(f"❌ [MyTF1] Request error on attempt {attempt + 1}: {e}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                    continue
        
        safe_print(f"❌ [MyTF1] All {max_retries} attempts failed for {url}")
        return None
    
    def _authenticate(self) -> bool:
        """Authenticate with TF1+ using provided credentials with robust error handling"""
        if not self.credentials.get('login') or not self.credentials.get('password'):
            safe_print("❌ [MyTF1Provider] MyTF1 credentials not provided")
            return False
            
        try:
            safe_print("✅ [MyTF1Provider] Attempting MyTF1 authentication...")
            
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
            safe_print(f"✅ [MyTF1Provider] Making DIRECT bootstrap request to: {self.accounts_bootstrap}")
            bootstrap_data = self._safe_api_call(self.accounts_bootstrap, headers=bootstrap_headers, params=bootstrap_params)
            if not bootstrap_data:
                safe_print("❌ [MyTF1Provider] Bootstrap failed")
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
            safe_print(f"✅ [MyTF1Provider] Making DIRECT login request to: {self.accounts_login}")
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
                safe_print(f"✅ [MyTF1Provider] Making DIRECT JWT token request to: {self.token_gigya_web}")
                jwt_data = self._safe_api_call(self.token_gigya_web, headers=headers_gigya, data=body_gigya, method='POST')
                
                if jwt_data and 'token' in jwt_data:
                    self.auth_token = jwt_data['token']
                    self._authenticated = True
                    safe_print("✅ [MyTF1Provider] MyTF1 authentication successful!")
                    safe_print(f"✅ [MyTF1Provider] Session token generated: {self.auth_token[:20]}...")
                    return True
                else:
                    safe_print(f"❌ [MyTF1Provider] Failed to get Gigya token")
            else:
                safe_print(f"❌ [MyTF1Provider] MyTF1 login failed: {login_data.get('errorMessage', 'Unknown error') if login_data else 'No response'}")
                
        except Exception as e:
            safe_print(f"❌ [MyTF1Provider] Error during MyTF1 authentication: {e}")
        
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
                    "genres": show_info["genres"],
                    "channel": show_info["channel"],
                    "year": show_info["year"],
                    "rating": show_info["rating"]
                })
        except Exception as e:
            safe_print(f"❌ [MyTF1Provider] Error fetching show metadata: {e}")
            # Fallback to basic channel logos
            for show_id, show_info in self.shows.items():
                shows.append({
                    "id": f"cutam:fr:mytf1:{show_id}",
                    "type": "series",
                    "name": show_info["name"],
                    "description": show_info["description"],
                    "logo": get_logo_url("fr", "tf1", self.request),
                    "poster": get_logo_url("fr", "tf1", self.request),
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
            safe_print("✅ [MyTF1Provider] Checking authentication for episodes...")
            if not self._authenticated and not self._authenticate():
                safe_print("❌ [MyTF1Provider] MyTF1 authentication failed")
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
            safe_print(f"✅ [MyTF1Provider] Making DIRECT GraphQL programs request (raw URL): {self.api_url}")
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
                        return available_episodes
                    else:
                        safe_print(f"❌ [MyTF1Provider] No episodes found for program: {program_slug}")
                else:
                    safe_print(f"❌ [MyTF1Provider] Program not found for show: {actual_show_id} on channel: {channel_filter}")
            else:
                safe_print(f"❌ [MyTF1Provider] Failed to get TF1+ programs or API failed")
            
            # Fallback: return a placeholder episode
            safe_print(f"✅ [MyTF1Provider] Using fallback episode for {actual_show_id}")
            return [self._create_fallback_episode(actual_show_id)]
                
        except Exception as e:
            safe_print(f"❌ [MyTF1Provider] Error getting show episodes: {e}")
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
            proxy_base = "https://8cyq9n1ebd.execute-api.eu-west-3.amazonaws.com/prod/?url="

            # Use simple URL encoding (Variant 2) - proven to work best and get successful responses
            proxied_url = proxy_base + quote(dest_with_params, safe="")

            safe_print(f"✅ [MyTF1Provider] Trying GraphQL TF1 REPLAY episodes through French proxy with SIMPLE URL ENCODING: {proxied_url}")
            data = self._safe_api_call(proxied_url, headers=headers, max_retries=1)  # Reduce retries for proxy
            
            # If proxy fails with 500 errors, try direct API call
            if not data:
                safe_print(f"❌ [MyTF1Provider] French proxy failed for GraphQL episodes, trying DIRECT call")
                safe_print(f"✅ [MyTF1Provider] Direct GraphQL URL: {self.api_url}")
                data = self._safe_api_call(self.api_url, headers=headers, params=params, max_retries=2)
            
            if data and 'data' in data and 'programBySlug' in data['data']:
                program_data = data['data']['programBySlug']
                
                # Check if videos are available
                if 'videos' in program_data and 'items' in program_data['videos']:
                    video_items = program_data['videos']['items']
                    safe_print(f"✅ [MyTF1Provider] Found {len(video_items)} video items")
                    
                    episodes = []
                    for video_data in video_items:
                        episode_info = self._parse_episode(video_data, video_data, len(episodes) + 1)
                        if episode_info:
                            episodes.append(episode_info)
                    
                    return episodes
                else:
                    safe_print(f"❌ [MyTF1Provider] No videos found in programBySlug")
                    safe_print(f"❌ [MyTF1Provider] Available keys: {list(program_data.keys())}")
            else:
                safe_print(f"❌ [MyTF1Provider] No programBySlug in response or API failed")
                safe_print(f"❌ [MyTF1Provider] Response keys: {list(data.keys()) if data else 'No data'}")
            
            return []
            
        except Exception as e:
            safe_print(f"❌ [MyTF1Provider] Error getting TF1+ show episodes: {e}")
            return []
    
    def _parse_episode(self, video: Dict, video_data: Dict, episode_number: int) -> Optional[Dict]:
        """Parse episode data from TF1+ API response with error handling"""
        try:
            # Extract episode information
            episode_id = video.get('id')
            title = video.get('decoration', {}).get('label', 'Unknown Title')
            description = video.get('decoration', {}).get('summary', '')
            duration = video.get('playingInfos', {}).get('duration', '')
            
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
                "type": "episode",
                "episode_number": episode_number,
                "season": 1,  # Default season
                "episode": episode_number
            }
            
            return episode_meta
            
        except Exception as e:
            safe_print(f"❌ [MyTF1Provider] Error parsing episode: {e}")
            return None
    
    def get_live_stream_url(self, channel_id: str) -> Optional[Dict]:
        """Get live stream URL for a specific channel - wrapper for get_channel_stream_url"""
        return self.get_channel_stream_url(channel_id)
    
    def get_channel_stream_url(self, channel_id: str) -> Optional[Dict]:
        """Get stream URL for a specific channel with robust error handling and fallbacks"""
        # Extract the actual channel name from our ID format
        channel_name = channel_id.split(":")[-1]  # e.g., "tf1"

        try:
            safe_print(f"✅ [MyTF1Provider] Getting stream for channel: {channel_name}")

            # Lazy authentication - only authenticate when needed
            safe_print("✅ [MyTF1Provider] Checking authentication...")
            if not self._authenticated and not self._authenticate():
                safe_print("❌ [MyTF1Provider] MyTF1 authentication failed")
                return None

            # TF1 live streams use 'L_' prefix (e.g., 'L_TF1')
            video_id = f'L_{channel_name.upper()}'
            safe_print(f"✅ [MyTF1Provider] Using video ID: {video_id}")

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
            proxy_base = "https://8cyq9n1ebd.execute-api.eu-west-3.amazonaws.com/prod/?url="

            json_parser = None

            # Try the proxy service
            try:
                # Use URL encoding (Variant 2) - proven to work best
                proxied_url = proxy_base + quote(dest_with_params, safe="")

                safe_print(f"✅ [MyTF1Provider] Trying TF1 LIVE stream through French proxy: {proxy_base[:50]}...")
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
                            safe_print(f"✅ [MyTF1Provider] French proxy successful for live stream - Country: {delivery_country}, Code: {delivery_code}")
                        else:
                            # We got a non-200 response (e.g., 403) - proxy might not be forwarding auth correctly
                            # Try direct call as fallback since direct calls work with authentication
                            safe_print(f"❌ [MyTF1Provider] French proxy returned non-200 code {delivery_code} - trying direct call")
                            safe_print(f"✅ [MyTF1Provider] Making DIRECT request for live feed: {url_json}")
                            safe_print(f"✅ *** FINAL DIRECT URL (LIVE): {url_json}")
                            json_parser = self._safe_api_call(url_json, headers=headers_video_stream, params=params)
                    else:
                        safe_print(f"❌ [MyTF1Provider] French proxy returned US country (still geo-blocked)")
                        # Try direct call as fallback
                        safe_print("❌ French proxy failed; trying direct call as fallback...")
                        safe_print(f"✅ [MyTF1Provider] Making DIRECT request for live feed: {url_json}")
                        safe_print(f"✅ *** FINAL DIRECT URL (LIVE): {url_json}")
                        json_parser = self._safe_api_call(url_json, headers=headers_video_stream, params=params)
                else:
                    safe_print(f"❌ [MyTF1Provider] French proxy failed or returned error code")
                    # Try direct call as fallback
                    safe_print("❌ French proxy failed; trying direct call as fallback...")
                    safe_print(f"✅ [MyTF1Provider] Making DIRECT request for live feed: {url_json}")
                    safe_print(f"✅ *** FINAL DIRECT URL (LIVE): {url_json}")
                    json_parser = self._safe_api_call(url_json, headers=headers_video_stream, params=params)

            except Exception as e:
                safe_print(f"❌ [MyTF1Provider] Error with French proxy: {e}")
                # Try direct call as fallback
                safe_print("❌ French proxy failed; trying direct call as fallback...")
                safe_print(f"✅ [MyTF1Provider] Making DIRECT request for live feed: {url_json}")
                safe_print(f"✅ *** FINAL DIRECT URL (LIVE): {url_json}")
                json_parser = self._safe_api_call(url_json, headers=headers_video_stream, params=params)

            # If proxy failed, try direct call as last resort
            if not json_parser:
                safe_print("❌ French proxy failed; trying direct call as last resort...")
                safe_print(f"✅ [MyTF1Provider] Making DIRECT request for live feed: {url_json}")
                safe_print(f"✅ *** FINAL DIRECT URL (LIVE): {url_json}")
                json_parser = self._safe_api_call(url_json, headers=headers_video_stream, params=params)

            if json_parser:
                safe_print(f"✅ [MyTF1Provider] Stream API response received for {video_id}")
                safe_print(f"✅ [MyTF1Provider] Response JSON: {json_parser}")
                
                if json_parser['delivery']['code'] <= 400:
                    video_url = json_parser['delivery']['url']
                    safe_print(f"✅ [MyTF1Provider] Stream URL obtained: {video_url[:50]}...")

                    license_url = None
                    license_headers = {}

                    # Enhanced DRM processing for TF1 live streams
                    if 'drms' in json_parser['delivery'] and json_parser['delivery']['drms']:
                        drm_info = json_parser['delivery']['drms'][0]
                        safe_print(f"✅ [MyTF1Provider] DRM Info found: {drm_info}")
                        
                        license_url = drm_info.get('url')
                        if not license_url:
                            safe_print(f"❌ [MyTF1Provider] No license URL in DRM info, using fallback")
                            license_url = self.license_base_url % video_id
                        else:
                            safe_print(f"✅ [MyTF1Provider] License URL from DRM: {license_url}")
                        
                        # Extract all headers from DRM info (like Kodi plugin does)
                        for header_item in drm_info.get('h', []):
                            header_key = header_item.get('k')
                            header_value = header_item.get('v')
                            if header_key and header_value:
                                license_headers[header_key] = header_value
                                safe_print(f"✅ [MyTF1Provider] DRM Header: {header_key} = {header_value}")
                    else:
                        # Fallback to generic license URL if no DRM info is present
                        safe_print(f"❌ [MyTF1Provider] No DRM info found, using fallback license URL")
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
                    
                    safe_print(f"✅ [MyTF1Provider] MyTF1 stream info prepared: manifest_type={stream_info['manifest_type']}")
                    return stream_info
                else:
                    safe_print(f"❌ [MyTF1Provider] MyTF1 delivery error: {json_parser['delivery']['code']}")
            else:
                safe_print(f"❌ [MyTF1Provider] MyTF1 API error: No valid JSON from mediainfo (proxy and direct attempts failed)")
                
        except Exception as e:
            safe_print(f"❌ [MyTF1Provider] Error getting stream for {channel_name}: {e}")
        
        return None
    
    def get_episode_stream_url(self, episode_id: str) -> Optional[Dict]:
        """Get stream URL for a specific episode (for replay content) with robust error handling"""
        # Extract the actual episode ID from our format
        if "episode:" in episode_id:
            actual_episode_id = episode_id.split("episode:")[-1]
        else:
            actual_episode_id = episode_id

        try:
            safe_print(f"✅ [MyTF1Provider] Getting replay stream for MyTF1 episode: {actual_episode_id}")

            # Lazy authentication - only authenticate when needed
            safe_print("✅ [MyTF1Provider] Checking authentication...")
            if not self._authenticated and not self._authenticate():
                safe_print("❌ [MyTF1Provider] MyTF1 authentication failed")
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
            proxy_base = "https://8cyq9n1ebd.execute-api.eu-west-3.amazonaws.com/prod/?url="

            json_parser = None

            # Try the proxy service for replay content
            try:
                # Use URL encoding (Variant 2) - proven to work best and get 200 responses
                proxied_url = proxy_base + quote(dest_with_params, safe="")

                safe_print(f"✅ [MyTF1Provider] Trying TF1 REPLAY stream through French proxy: {proxy_base[:50]}...")
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
                            safe_print(f"✅ [MyTF1Provider] French proxy successful for TF1 REPLAY - Country: {delivery_country}, Code: {delivery_code}")
                        else:
                            # We got a non-200 response (e.g., 403) - proxy might not be forwarding auth correctly
                            # Try direct call as fallback since direct calls work with authentication
                            safe_print(f"❌ [MyTF1Provider] French proxy returned non-200 code {delivery_code} - trying direct call")
                            safe_print(f"✅ [MyTF1Provider] Making DIRECT request for replay feed: {url_json}")
                            safe_print(f"✅ *** FINAL DIRECT URL (TF1 REPLAY): {url_json}")
                            json_parser = self._safe_api_call(url_json, headers=headers_video_stream, params=params)
                    else:
                        safe_print(f"❌ [MyTF1Provider] French proxy returned US country (still geo-blocked)")
                        # Try direct call as fallback
                        safe_print("❌ French proxy failed; trying direct call as fallback...")
                        safe_print(f"✅ [MyTF1Provider] Making DIRECT request for replay feed: {url_json}")
                        safe_print(f"✅ *** FINAL DIRECT URL (TF1 REPLAY): {url_json}")
                        json_parser = self._safe_api_call(url_json, headers=headers_video_stream, params=params)
                else:
                    safe_print(f"❌ [MyTF1Provider] French proxy failed or returned error code")
                    # Try direct call as fallback
                    safe_print("❌ French proxy failed; trying direct call as fallback...")
                    safe_print(f"✅ [MyTF1Provider] Making DIRECT request for replay feed: {url_json}")
                    safe_print(f"✅ *** FINAL DIRECT URL (TF1 REPLAY): {url_json}")
                    json_parser = self._safe_api_call(url_json, headers=headers_video_stream, params=params)

            except Exception as e:
                safe_print(f"❌ [MyTF1Provider] Error with French proxy: {e}")
                # Try direct call as fallback
                safe_print("❌ French proxy failed; trying direct call as fallback...")
                safe_print(f"✅ [MyTF1Provider] Making DIRECT request for replay feed: {url_json}")
                safe_print(f"✅ *** FINAL DIRECT URL (TF1 REPLAY): {url_json}")
                json_parser = self._safe_api_call(url_json, headers=headers_video_stream, params=params)

            # CRITICAL: If proxy failed, try direct call as last resort (will likely fail with 403)
            if not json_parser:
                safe_print("❌ French proxy failed; trying direct call as last resort (will likely fail)...")
                safe_print(f"✅ [MyTF1Provider] Making DIRECT request for replay feed: {url_json}")
                safe_print(f"✅ *** FINAL DIRECT URL (TF1 REPLAY): {url_json}")
                json_parser = self._safe_api_call(url_json, headers=headers_video_stream, params=params)

            if json_parser and json_parser.get('delivery', {}).get('code', 500) <= 400:
                video_url = json_parser['delivery']['url']
                safe_print(f"✅ [MyTF1Provider] Stream URL obtained: {video_url}")

                license_url = None
                license_headers = {}

                # Enhanced DRM processing for TF1 replay content (like Kodi plugin)
                if 'drms' in json_parser['delivery'] and json_parser['delivery']['drms']:
                    drm_info = json_parser['delivery']['drms'][0]
                    safe_print(f"✅ [MyTF1Provider] Replay DRM Info found: {drm_info}")
                    
                    license_url = drm_info.get('url')
                    if not license_url:
                        safe_print(f"❌ [MyTF1Provider] No license URL in replay DRM info, using fallback")
                        license_url = self.license_base_url % actual_episode_id
                    else:
                        safe_print(f"✅ [MyTF1Provider] Replay License URL from DRM: {license_url}")
                    
                    # Extract all headers from DRM info (comprehensive like Kodi)
                    for header_item in drm_info.get('h', []):
                        header_key = header_item.get('k')
                        header_value = header_item.get('v')
                        if header_key and header_value:
                            license_headers[header_key] = header_value
                            safe_print(f"✅ [MyTF1Provider] Replay DRM Header: {header_key} = {header_value}")
                else:
                    # Fallback to generic license URL if no DRM info is present
                    safe_print(f"❌ [MyTF1Provider] No replay DRM info found, using fallback license URL")
                    license_url = self.license_base_url % actual_episode_id

                # Check if the stream URL is MPD or HLS
                is_mpd = video_url.lower().endswith('.mpd') or 'mpd' in video_url.lower()
                is_hls = video_url.lower().endswith('.m3u8') or 'hls' in video_url.lower() or 'm3u8' in video_url.lower()

                # For DRM-protected MPD streams (replays only), use external DASH proxy
                if is_mpd and license_url:
                    try:
                        safe_print(f"✅ [MyTF1Provider] Using DASH proxy for DRM-protected MPD replay stream")

                        # URL encode the manifest and license URLs (NOT base64)
                        encoded_manifest = quote(video_url, safe='')
                        encoded_license = quote(license_url, safe='')

                        # Construct the DASH proxy URL
                        dash_proxy_base = "https://alphanet06-dash-proxy-server.hf.space"
                        proxy_params = f"mpd={encoded_manifest}&widevine.isActive=true&widevine.drmKeySystem=com.widevine.alpha&widevine.licenseServerUrl={encoded_license}&widevine.priority=0"

                        # Add common dash.js parameters
                        proxy_params += '&debug.logLevel=5'
                        proxy_params += '&streaming.capabilities.supportedEssentialProperties.0.schemeIdUri=urn%3Advb%3Adash%3Afontdownload%3A2014'
                        proxy_params += '&streaming.capabilities.supportedEssentialProperties.1.schemeIdUri=urn%3Ampeg%3AmpegB%3Acicp%3AColourPrimaries'

                        final_url = f"{dash_proxy_base}/proxy?{proxy_params}"
                        manifest_type = 'mpd'

                        safe_print(f"✅ [MyTF1Provider] DASH proxy URL generated: {final_url}")

                        # For DASH proxy streams, use externalUrl to open in browser (not url)
                        stream_info = {
                            "externalUrl": final_url,  # The DASH proxy URL to open in browser
                            "manifest_type": "external",  # Mark as external to prevent internal playback
                            "title": "DASH Stream (Browser Required)"
                        }

                        # Add license info if available
                        if license_url:
                            stream_info["licenseUrl"] = license_url
                            if license_headers:
                                stream_info["licenseHeaders"] = license_headers

                        safe_print(f"✅ [MyTF1Provider] MyTF1 DASH proxy stream info prepared: manifest_type={stream_info['manifest_type']}")
                        return stream_info

                    except Exception as e:
                        safe_print(f"❌ [MyTF1Provider] DASH proxy URL generation failed: {e}")
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
                                safe_print(f"✅ [MyTF1Provider] Using HLS proxy for HLS stream")
                            elif is_mpd:
                                endpoint = '/proxy/mpd/manifest.m3u8'
                                safe_print(f"✅ [MyTF1Provider] Using MPD proxy for MPD stream")
                            else:
                                # Default to HLS proxy for unknown formats
                                endpoint = '/proxy/hls/manifest.m3u8'
                                safe_print(f"✅ [MyTF1Provider] Using HLS proxy for unknown format")

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

                            safe_print(f"✅ [MyTF1Provider] MediaFlow URL with DRM support generated: {final_url[:50]}...")

                        except Exception as e:
                            safe_print(f"❌ [MyTF1Provider] MediaFlow URL generation failed: {e}")
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

                safe_print(f"✅ [MyTF1Provider] MyTF1 stream info prepared: manifest_type={stream_info['manifest_type']}")
                return stream_info
            else:
                safe_print(f"❌ [MyTF1Provider] MyTF1 delivery error: {json_parser.get('delivery', {}).get('code', 'Unknown') if json_parser else 'No response'}")
                
        except Exception as e:
            safe_print(f"❌ [MyTF1Provider] Error getting episode stream: {e}")
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
            safe_print(f"✅ [MyTF1Provider] Making DIRECT GraphQL programs metadata request (raw URL): {self.api_url}")
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
                            
                            safe_print(f"✅ [MyTF1Provider] Found show metadata for {show_id}: poster={poster[:50] if poster else 'N/A'}..., fanart={fanart[:50] if fanart else 'N/A'}...")
                            
                            return {
                                "poster": poster,
                                "fanart": fanart,
                                "logo": logo
                            }
            
            safe_print(f"❌ [MyTF1Provider] No show metadata found for {show_id}")
            return {}
            
        except Exception as e:
            safe_print(f"❌ [MyTF1Provider] Error fetching show metadata for {show_id}: {e}")
            return {}
    
    def resolve_stream(self, stream_id: str) -> Optional[Dict]:
        """Resolve stream URL for a given stream ID"""
        # This method needs to be implemented based on the specific stream ID format
        # For now, return None as a placeholder
        safe_print(f"❌ MyTF1Provider: resolve_stream not implemented for {stream_id}")
        return None
