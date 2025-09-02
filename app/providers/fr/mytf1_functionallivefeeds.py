import json
import requests
import time
import logging
import os
import urllib.parse
import random
from typing import Dict, List, Optional, Tuple
from app.utils.client_ip import merge_ip_headers
from app.utils.credentials import get_provider_credentials

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

class MyTF1Provider:
    """MyTF1 provider implementation with authentication"""
    
    def __init__(self):
        self.credentials = get_provider_credentials('mytf1')
        self.base_url = "https://www.tf1.fr"
        self.api_key = "3_hWgJdARhz_7l1oOp3a8BDLoR9cuWZpUaKG4aqF7gum9_iK3uTZ2VlDBl8ANf8FVk"
        self.api_url = "https://www.tf1.fr/graphql/web"
        self.video_stream_url = "https://mediainfo.tf1.fr/mediainfocombo"
        # MediaFlow config via env
        mediaflow_creds = get_provider_credentials('mediaflow')
        self.mediaflow_url = mediaflow_creds.get('url', 'http://localhost:8888') # Default to localhost if not specified
        self.mediaflow_password = mediaflow_creds.get('password')
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

    def _with_ip_headers(self, headers: Dict[str, str]) -> Dict[str, str]:
        """Return headers merged with viewer IP forwarding headers."""
        return merge_ip_headers(headers)
    
    def _authenticate(self) -> bool:
        """Authenticate with TF1+ using provided credentials"""
        if not self.credentials.get('login') or not self.credentials.get('password'):
            print("[MyTF1Provider] MyTF1 credentials not provided")
            return False
            
        try:
            print("[MyTF1Provider] Attempting MyTF1 authentication...")
            
            # Bootstrap
            bootstrap_headers = {
                "User-Agent": get_random_windows_ua(),
                "referrer": self.base_url
            }
            bootstrap_params = {
                'apiKey': self.api_key,
                'pageURL': 'https%3A%2F%2Fwww.tf1.fr%2F',
                'sd': 'js_latest',
                'sdkBuild': '13987',
                'format': 'json'
            }
            self.session.get(self.accounts_bootstrap, headers=self._with_ip_headers(bootstrap_headers), params=bootstrap_params, timeout=10)
            
            # Login
            headers_login = {
                "User-Agent": get_random_windows_ua(),
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
            
            response = self.session.post(self.accounts_login, headers=self._with_ip_headers(headers_login), data=post_body_login, timeout=10)
            if response.status_code == 200:
                login_json = response.json()
                if login_json.get('errorCode') == 0:
                    # Get Gigya token
                    headers_gigya = {
                        "User-Agent": get_random_windows_ua(),
                        "content-type": "application/json"
                    }
                    body_gigya = "{\"uid\":\"%s\",\"signature\":\"%s\",\"timestamp\":%s,\"consent_ids\":[\"1\",\"2\",\"3\",\"4\",\"10001\",\"10003\",\"10005\",\"10007\",\"10013\",\"10015\",\"10017\",\"10019\",\"10009\",\"10011\",\"13002\",\"13001\",\"10004\",\"10014\",\"10016\",\"10018\",\"10020\",\"10010\",\"10012\",\"10006\",\"10008\"]}" % (
                        login_json['userInfo']['UID'],
                        login_json['userInfo']['UIDSignature'],
                        int(login_json['userInfo']['signatureTimestamp'])
                    )
                    response = self.session.post(self.token_gigya_web, headers=self._with_ip_headers(headers_gigya), data=body_gigya, timeout=10)
                    if response.status_code == 200:
                        json_token = response.json()
                        self.auth_token = json_token['token']
                        self._authenticated = True
                        print("[MyTF1Provider] MyTF1 authentication successful!")
                        print(f"[MyTF1Provider] Session token generated: {self.auth_token[:20]}...")
                        return True
                    else:
                        print(f"[MyTF1Provider] Failed to get Gigya token: {response.status_code}")
                else:
                    print(f"[MyTF1Provider] MyTF1 login failed: {login_json.get('errorMessage', 'Unknown error')}")
            else:
                print(f"[MyTF1Provider] MyTF1 login failed with status {response.status_code}")
                
        except Exception as e:
            print(f"[MyTF1Provider] Error during MyTF1 authentication: {e}")
        
        return False
    
    def get_live_channels(self) -> List[Dict]:
        """Get list of live channels from TF1"""
        channels = []
        
        # Get base URL for static assets
        static_base = os.getenv('ADDON_BASE_URL', 'http://localhost:8000')
        
        # Known TF1 channels - updated to use local logos
        channel_data = [
            {"id": "tf1", "name": "TF1", "logo": f"{static_base}/static/logos/fr/tf1.png"},
            {"id": "tmc", "name": "TMC", "logo": f"{static_base}/static/logos/fr/tmc.png"},
            {"id": "tfx", "name": "TFX", "logo": f"{static_base}/static/logos/fr/tfx.png"},
            {"id": "tf1-series-films", "name": "TF1 Séries Films", "logo": f"{static_base}/static/logos/fr/tf1seriesfilms.png"}
        ]
        
        for channel_info in channel_data:
            channels.append({
                "id": f"cutam:fr:mytf1:{channel_info['id']}",
                "name": channel_info['name'],
                "poster": channel_info['logo'],  # Use logo as poster for menu display
                "logo": channel_info['logo'],
                "type": "channel"
            })
        
        return channels

    def get_programs(self) -> List[Dict]:
        """Get list of TF1+ replay shows with dynamic images from API"""
        shows = []
        
        try:
            # Fetch show metadata from TF1+ API (same as reference plugin)
            for show_id, show_info in self.shows.items():
                show_metadata = self._get_show_api_metadata(show_id, show_info)
                
                shows.append({
                    "id": f"cutam:fr:mytf1:{show_id}",
                    "type": "series",
                    "name": show_info["name"],
                    "description": show_info["description"],
                    "logo": show_metadata.get("logo", f"https://www.tf1.fr/static/logos/{show_info['channel'].lower()}.png"),
                    "poster": show_metadata.get("poster", f"https://www.tf1.fr/static/logos/{show_info['channel'].lower()}.png"),
                    "fanart": show_metadata.get("fanart"),
                    "genres": show_info["genres"],
                    "channel": show_info["channel"],
                    "year": show_info["year"],
                    "rating": show_info["rating"]
                })
        except Exception as e:
            print(f"[MyTF1Provider] Error fetching show metadata: {e}")
            # Fallback to basic channel logos
            for show_id, show_info in self.shows.items():
                shows.append({
                    "id": f"cutam:fr:mytf1:{show_id}",
                    "type": "series",
                    "name": show_info["name"],
                    "description": show_info["description"],
                    "logo": f"https://www.tf1.fr/static/logos/{show_info['channel'].lower()}.png",
                    "poster": f"https://www.tf1.fr/static/logos/{show_info['channel'].lower()}.png",
                    "genres": show_info["genres"],
                    "channel": show_info["channel"],
                    "year": show_info["year"],
                    "rating": show_info["rating"]
                })
        
        return shows

    def get_episodes(self, show_id: str) -> List[Dict]:
        """Get episodes for a specific TF1+ show"""
        # Extract the actual show ID from our format
        actual_show_id = show_id.split(":")[-1]
        
        if actual_show_id not in self.shows:
            return []
        
        try:
            # Use the TF1+ GraphQL API to get episodes
            # Based on the reference plugin implementation
            headers = {
                'content-type': 'application/json',
                'referer': 'https://www.tf1.fr/programmes-tv',
                'User-Agent': get_random_windows_ua()
            }
            
            # Get the channel for this show
            show_channel = self.shows[actual_show_id]['channel']
            channel_filter = show_channel.lower()
            
            # First, get the program ID for the show
            program_params = {
                'id': '483ce0f',
                'variables': f'{{"context":{{"persona":"PERSONA_2","application":"WEB","device":"DESKTOP","os":"WINDOWS"}},"filter":{{"channel":"{channel_filter}"}},"offset":0,"limit":500}}'
            }
            
            response = self.session.get(self.api_url, params=program_params, headers=self._with_ip_headers(headers), timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                program_id = None
                program_slug = None
                
                # Find the specific show in the programs list
                if 'data' in data and 'programs' in data['data']:
                    for program in data['data']['programs']['items']:
                        if program.get('name', '').lower() == self.shows[actual_show_id]['name'].lower():
                            program_id = program.get('id')
                            program_slug = program.get('slug')
                            break
                
                if program_id and program_slug:
                    # Get episodes for the show
                    episodes = self._get_show_episodes(program_slug, program_id, headers)
                    return episodes
                else:
                    print(f"Program not found for show: {actual_show_id} on channel: {channel_filter}")
                    return []
            else:
                print(f"Failed to get TF1+ programs: {response.status_code}")
                return []
                
        except Exception as e:
            print(f"Error getting TF1+ episodes: {e}")
            return []
    
    def _get_show_episodes(self, program_slug: str, program_id: str, headers: Dict) -> List[Dict]:
        """Get episodes for a specific show using TF1+ API"""
        try:
            # Use the TF1+ API to get episodes directly
            # Based on the reference plugin's list_videos function
            params = {
                'id': 'a6f9cf0e',
                'variables': f'{{"programSlug":"{program_slug}","offset":0,"limit":50,"sort":{{"type":"DATE","order":"DESC"}},"types":["REPLAY"]}}'
            }
            
            response = self.session.get(self.api_url, params=params, headers=self._with_ip_headers(headers), timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                episodes = []
                
                if 'data' in data and 'programBySlug' in data['data']:
                    program_data = data['data']['programBySlug']
                    
                    # Check if videos are available
                    if 'videos' in program_data and 'items' in program_data['videos']:
                        video_items = program_data['videos']['items']
                        print(f"Found {len(video_items)} video items")
                        
                        for video_data in video_items:
                            episode_info = self._parse_episode(video_data, video_data, len(episodes) + 1)
                            if episode_info:
                                episodes.append(episode_info)
                    else:
                        print(f"No videos found in programBySlug")
                        print(f"Available keys: {list(program_data.keys())}")
                else:
                    print(f"No programBySlug in response")
                    print(f"Response keys: {list(data.keys())}")
                
                return episodes
            else:
                print(f"Failed to get TF1+ episodes: {response.status_code}")
                return []
                
        except Exception as e:
            print(f"Error getting TF1+ show episodes: {e}")
        return []
    
    def _parse_episode(self, video: Dict, video_data: Dict, episode_number: int) -> Optional[Dict]:
        """Parse episode data from TF1+ API response"""
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
            print(f"Error parsing TF1+ episode: {e}")
            return None
    
    def get_channel_stream_url(self, channel_id: str) -> Optional[Dict]:
        """Get stream URL for a specific channel"""
        # Extract the actual channel name from our ID format
        channel_name = channel_id.split(":")[-1]  # e.g., "tf1"
        
        try:
            print(f"[MyTF1Provider] Getting stream for channel: {channel_name}")
            
            # Lazy authentication - only authenticate when needed
            print("[MyTF1Provider] Checking authentication...")
            if not self._authenticated and not self._authenticate():
                print("[MyTF1Provider] MyTF1 authentication failed")
                return None
                
            # TF1 live streams use 'L_' prefix (e.g., 'L_TF1')
            video_id = f'L_{channel_name.upper()}'
            print(f"[MyTF1Provider] Using video ID: {video_id}")
            
            # Get the actual stream URL using the mediainfo API
            headers_video_stream = {
                "User-Agent": get_random_windows_ua(),
                "authorization": f"Bearer {self.auth_token}",
            }
            # Params follow reference; LCI could be treated specially but we align to reference pver block
            params = {
                'context': 'MYTF1',
                'pver': '5029000',
                'platform': 'web',
                'device': 'desktop',
                'os': 'windows',
                'osVersion': '10.0',
                'topDomain': self.base_url,  # Use actual TF1 domain instead of 'unknown'
                'playerVersion': '5.29.0',
                'productName': 'mytf1',
                'productVersion': '3.37.0',
                'format': 'hls'  # Try to force HLS format for all channels
            }
            
            url_json = f"https://mediainfo.tf1.fr/mediainfocombo/{video_id}"
            print(f"[MyTF1Provider] Requesting stream info from: {url_json}")
            
            response = self.session.get(url_json, headers=self._with_ip_headers(headers_video_stream), params=params, timeout=10)
            
            if response.status_code == 200:
                json_parser = response.json()
                print(f"[MyTF1Provider] Stream API response received for {video_id}")
                
                if json_parser['delivery']['code'] <= 400:
                    video_url = json_parser['delivery']['url']
                    print(f"[MyTF1Provider] Stream URL obtained: {video_url[:50]}...")

                    license_url = None
                    license_headers = {}

                    if 'drms' in json_parser['delivery'] and json_parser['delivery']['drms']:
                        drm_info = json_parser['delivery']['drms'][0]
                        license_url = drm_info['url']
                        # Extract Authorization header if present in DRM info
                        for header_item in drm_info.get('h', []):
                            if header_item.get('k') == 'Authorization':
                                license_headers['Authorization'] = header_item['v']
                                break
                        if not license_url: # Fallback if URL is missing from DRM info
                            license_url = self.license_base_url % video_id
                    else:
                        # Fallback to generic license URL if no DRM info is present
                        license_url = self.license_base_url % video_id

                    # Prefer HLS if present, else MPD
                    lower_url = (video_url or '').lower()
                    is_hls = lower_url.endswith('.m3u8') or 'hls' in lower_url or 'm3u8' in lower_url

                    # Build MediaFlow URL
                    if self.mediaflow_url and self.mediaflow_password:
                        base = self.mediaflow_url.rstrip('/')
                        if is_hls:
                            endpoint = '/proxy/hls/manifest.m3u8'
                        else:
                            endpoint = '/proxy/mpd/manifest.m3u8'
                        dest = urllib.parse.quote(video_url, safe='')
                        # build query with api_password + request headers
                        q = [
                            ('d', video_url),
                            ('api_password', self.mediaflow_password),
                            ('h_user-agent', headers_video_stream['User-Agent']),
                            ('h_referer', self.base_url),
                            ('h_origin', self.base_url),
                            ('h_authorization', f"Bearer {self.auth_token}")  # Add authorization header
                        ]
                        # Add license URL and headers to MediaFlow proxy request if present
                        if license_url:
                            q.append(('h_x-license-url', license_url))
                        if license_headers:
                            q.append(('h_x-license-authorization', license_headers.get('Authorization', '')))

                        mediaflow_url = f"{base}{endpoint}?" + urllib.parse.urlencode(q)
                        final_url = mediaflow_url
                        manifest_type = 'hls' if is_hls else 'hls'  # MPD proxied as HLS
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
                    
                    print(f"[MyTF1Provider] MyTF1 stream info prepared: manifest_type={stream_info['manifest_type']}")
                    return stream_info
                else:
                    print(f"[MyTF1Provider] MyTF1 delivery error: {json_parser['delivery']['code']}")
            else:
                print(f"[MyTF1Provider] MyTF1 API error: {response.status_code}")
                
        except Exception as e:
            print(f"[MyTF1Provider] Error getting stream for {channel_name}: {e}")
        
        return None
    
    def get_episode_stream_url(self, episode_id: str) -> Optional[Dict]:
        """Get stream URL for a specific episode (for replay content)"""
        # Extract the actual episode ID from our format
        if "episode:" in episode_id:
            actual_episode_id = episode_id.split("episode:")[-1]
        else:
            actual_episode_id = episode_id
        
        try:
            print(f"[MyTF1Provider] Getting replay stream for MyTF1 episode: {actual_episode_id}")
            
            # Lazy authentication - only authenticate when needed
            print("[MyTF1Provider] Checking authentication...")
            if not self._authenticated and not self._authenticate():
                print("[MyTF1Provider] MyTF1 authentication failed")
                return None
            
            # Use the same approach as the reference plugin for replay content
            headers_video_stream = {
                "User-Agent": get_random_windows_ua(),
                "authorization": f"Bearer {self.auth_token}",
            }
            params = {
                'context': 'MYTF1',
                'pver': '5010000',
                'platform': 'web',
                'device': 'desktop',
                'os': 'linux',
                'osVersion': 'unknown',
                'topDomain': self.base_url,
                'playerVersion': '5.19.0',
                'productName': 'mytf1',
                'productVersion': '3.22.0',
                'format': 'hls'  # Force HLS format to avoid MPD parsing issues
            }
            
            url_json = f"{self.video_stream_url}/{actual_episode_id}"
            print(f"[MyTF1Provider] Requesting stream info from: {url_json}")
            
            response = self.session.get(url_json, headers=self._with_ip_headers(headers_video_stream), params=params, timeout=10)
            
            if response.status_code == 200:
                json_parser = response.json()
                print(f"[MyTF1Provider] Stream API response received for {actual_episode_id}")
                
                if json_parser['delivery']['code'] <= 400:
                    video_url = json_parser['delivery']['url']
                    print(f"[MyTF1Provider] Stream URL obtained: {video_url[:50]}...")

                    license_url = None
                    license_headers = {}

                    if 'drms' in json_parser['delivery'] and json_parser['delivery']['drms']:
                        drm_info = json_parser['delivery']['drms'][0]
                        license_url = drm_info['url']
                        # Extract Authorization header if present in DRM info
                        for header_item in drm_info.get('h', []):
                            if header_item.get('k') == 'Authorization':
                                license_headers['Authorization'] = header_item['v']
                                break
                        if not license_url: # Fallback if URL is missing from DRM info
                            license_url = self.license_base_url % actual_episode_id
                    else:
                        # Fallback to generic license URL if no DRM info is present
                        license_url = self.license_base_url % actual_episode_id

                    # Check if the stream URL is MPD or HLS
                    is_mpd = video_url.lower().endswith('.mpd') or 'mpd' in video_url.lower()
                    is_hls = video_url.lower().endswith('.m3u8') or 'hls' in video_url.lower() or 'm3u8' in video_url.lower()
                    
                    # Build MediaFlow URL only if we have MediaFlow configured
                    if self.mediaflow_url and self.mediaflow_password:
                        try:
                            base = self.mediaflow_url.rstrip('/')
                            
                            # Prefer HLS proxy to avoid MPD parsing issues
                            if is_hls:
                                endpoint = '/proxy/hls/manifest.m3u8'
                                print(f"[MyTF1Provider] Using HLS proxy for HLS stream")
                            elif is_mpd:
                                endpoint = '/proxy/mpd/manifest.m3u8'
                                print(f"[MyTF1Provider] Using MPD proxy for MPD stream")
                            else:
                                # Default to HLS proxy for unknown formats
                                endpoint = '/proxy/hls/manifest.m3u8'
                                print(f"[MyTF1Provider] Using HLS proxy for unknown format")
                            
                            # build query with api_password + request headers
                            q = [
                                ('d', video_url),
                                ('api_password', self.mediaflow_password),
                                ('h_user-agent', headers_video_stream['User-Agent']),
                                ('h_referer', self.base_url),
                                ('h_origin', self.base_url),
                                ('h_authorization', f"Bearer {self.auth_token}")
                            ]
                            
                            # Add license URL and headers to MediaFlow proxy request if present
                            if license_url:
                                q.append(('h_x-license-url', license_url))
                            if license_headers:
                                q.append(('h_x-license-authorization', license_headers.get('Authorization', '')))

                            mediaflow_url = f"{base}{endpoint}?" + urllib.parse.urlencode(q)
                            final_url = mediaflow_url
                            manifest_type = 'hls'  # Always return HLS from MediaFlow
                            
                            print(f"[MyTF1Provider] MediaFlow URL generated: {final_url[:50]}...")
                            
                        except Exception as e:
                            print(f"[MyTF1Provider] MediaFlow URL generation failed: {e}")
                            # Fallback to direct URL
                            final_url = video_url
                            manifest_type = 'hls' if is_hls else ('mpd' if is_mpd else 'hls')
                    else:
                        # No MediaFlow, use direct URL
                        final_url = video_url
                        manifest_type = 'hls' if is_hls else ('mpd' if is_mpd else 'hls')

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
                    
                    print(f"[MyTF1Provider] MyTF1 stream info prepared: manifest_type={stream_info['manifest_type']}")
                    return stream_info
                else:
                    print(f"[MyTF1Provider] MyTF1 delivery error: {json_parser['delivery']['code']}")
            else:
                print(f"[MyTF1Provider] MyTF1 API error: {response.status_code}")
            
        except Exception as e:
            print(f"[MyTF1Provider] Error getting stream for episode {episode_id}: {e}")
        
        return None
    
    def _get_show_api_metadata(self, show_id: str, show_info: Dict) -> Dict:
        """Get show metadata from TF1+ API (same as reference plugin)"""
        try:
            # Use the same API call as the reference plugin
            params = {
                'id': '483ce0f',
                'variables': '{"context":{"persona":"PERSONA_2","application":"WEB","device":"DESKTOP","os":"WINDOWS"},"filter":{"channel":"%s"},"offset":0,"limit":500}' % show_info['channel'].lower()
            }
            headers = {
                'content-type': 'application/json',
                'referer': 'https://www.tf1.fr/programmes-tv',
                'User-Agent': get_random_windows_ua()
            }
            
            response = self.session.get(self.api_url, params=params, headers=self._with_ip_headers(headers), timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                if 'data' in data and 'programs' in data['data'] and 'items' in data['data']['programs']:
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
                                logo = poster if poster else f"https://www.tf1.fr/static/logos/{show_info['channel'].lower()}.png"
                                
                                print(f"[MyTF1Provider] Found show metadata for {show_id}: poster={poster[:50] if poster else 'N/A'}..., fanart={fanart[:50] if fanart else 'N/A'}...")
                                
                                return {
                                    "poster": poster,
                                    "fanart": fanart,
                                    "logo": logo
                                }
            
            print(f"[MyTF1Provider] No show metadata found for {show_id}")
            return {}
            
        except Exception as e:
            print(f"[MyTF1Provider] Error fetching show metadata for {show_id}: {e}")
            return {}
    
    def resolve_stream(self, stream_id: str) -> Optional[Dict]:
        """Resolve stream URL for a given stream ID"""
        # This method needs to be implemented based on the specific stream ID format
        # For now, return None as a placeholder
        print(f"MyTF1Provider: resolve_stream not implemented for {stream_id}")
        return None
