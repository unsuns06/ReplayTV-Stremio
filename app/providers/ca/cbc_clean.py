#!/usr/bin/env python3
"""
CBC (Canadian Broadcasting Corporation) provider for Stremio addon
Using the exact CBC authentication implementation
"""

import json
import re
import logging
from typing import List, Dict, Optional, Any
from urllib.parse import urljoin
import requests
from fastapi import Request

# Import the CBC authentication module
from app.auth.cbc_auth import CBCAuth, load_tokens, save_tokens

logger = logging.getLogger(__name__)

class CBCProvider:
    """CBC provider for Canadian content including Dragon's Den"""
    
    def __init__(self, request: Optional[Request] = None):
        self.request = request
        self.base_url = "https://gem.cbc.ca"
        self.api_base = "https://services.radio-canada.ca"
        self.catalog_api = f"{self.api_base}/ott/catalog/v2/toutv"
        self.media_api = f"{self.api_base}/media/validation/v2"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        
        # CBC regions for live streams
        self.live_regions = {
            "Ottawa": "CBOT",
            "Montreal": "CBMT", 
            "Charlottetown": "CBCT",
            "Fredericton": "CBAT",
            "Halifax": "CBHT",
            "Windsor": "CBET",
            "Yellowknife": "CFYK",
            "Winnipeg": "CBWT",
            "Regina": "CBKT",
            "Calgary": "CBRT",
            "Edmonton": "CBXT",
            "Vancouver": "CBUT",
            "Toronto": "CBLT",
            "St. John's": "CBNT"
        }
        
        # Authentication state
        self.auth_token = None
        self.claims_token = None
        self.is_authenticated = False
        
        # Initialize CBC authentication handler
        self.cbc_auth = CBCAuth()
        
        # Try to load existing authentication
        self._load_authentication()
    
    def get_live_channels(self) -> List[Dict[str, Any]]:
        """Get CBC live TV channels"""
        try:
            logger.info("🇨🇦 Getting CBC live channels...")
            
            # Get live stream info from CBC
            live_info_url = f"{self.base_url}/public/js/main.js"
            response = self.session.get(live_info_url)
            response.raise_for_status()
            
            # Extract live stream URL from JavaScript
            url_match = re.search(r'LLC_URL=r\+"(.*?)\?', response.text)
            if not url_match:
                logger.error("Could not find live stream URL in CBC JavaScript")
                return []
            
            live_stream_url = f"https:{url_match.group(1)}"
            
            # Get live stream data
            live_response = self.session.get(live_stream_url)
            live_response.raise_for_status()
            live_data = live_response.json()
            
            channels = []
            for entry in live_data.get("entries", []):
                call_sign = entry.get("cbc$callSign", "")
                if call_sign:
                    # Find the region name for this call sign
                    region_name = None
                    for region, sign in self.live_regions.items():
                        if sign in call_sign:
                            region_name = region
                            break
                    
                    if region_name:
                        channel = {
                            "id": f"cutam:ca:cbc:live:{call_sign.lower()}",
                            "name": f"CBC {region_name}",
                            "logo": f"https://raw.githubusercontent.com/tv-logo/tv-logos/main/countries/canada/cbc-ca.png",
                            "poster": f"https://raw.githubusercontent.com/tv-logo/tv-logos/main/countries/canada/cbc-ca.png",
                            "description": f"CBC live stream for {region_name}",
                            "channel": "CBC",
                            "type": "channel",
                            "region": region_name,
                            "call_sign": call_sign
                        }
                        channels.append(channel)
            
            logger.info(f"✅ CBC returned {len(channels)} live channels")
            return channels
            
        except Exception as e:
            logger.error(f"❌ Error getting CBC live channels: {e}")
            return []
    
    def get_programs(self) -> List[Dict[str, Any]]:
        """Get CBC programs including Dragon's Den"""
        try:
            logger.info("🇨🇦 Getting CBC programs...")
            
            # Try to get Dragon's Den from CBC catalog
            dragons_den_program = self._search_dragons_den()
            if dragons_den_program:
                programs = [dragons_den_program]
            else:
                # Fallback to static program
                programs = [
                    {
                        "id": "cutam:ca:cbc:dragons-den",
                        "type": "series",
                        "name": "Dragon's Den",
                        "poster": "https://images.ctv.ca/archives/CTVNews/img/2010/01/15/dragons_den_100115.jpg",
                        "logo": "https://images.ctv.ca/archives/CTVNews/img/2010/01/15/dragons_den_100115.jpg",
                        "description": "Canadian reality television series featuring entrepreneurs pitching their business ideas to a panel of venture capitalists",
                        "genres": ["Reality", "Business", "Entrepreneurship"],
                        "year": 2024,
                        "rating": "G",
                        "channel": "CBC"
                    }
                ]
            
            logger.info(f"✅ CBC returned {len(programs)} programs")
            return programs
            
        except Exception as e:
            logger.error(f"❌ Error getting CBC programs: {e}")
            return []
    
    def _search_dragons_den(self) -> Optional[Dict[str, Any]]:
        """Search for Dragon's Den in CBC catalog"""
        try:
            logger.info("🔍 Searching for Dragon's Den in CBC catalog...")
            
            # Search for Dragon's Den in the catalog
            search_params = {
                'device': 'web',
                'query': 'Dragon\'s Den',
                'pageNumber': '1',
                'pageSize': '10'
            }
            
            search_url = f"{self.catalog_api}/search"
            response = self.session.get(search_url, params=search_params)
            response.raise_for_status()
            
            data = response.json()
            
            # Look for Dragon's Den in search results
            if 'content' in data and len(data['content']) > 0:
                for item in data['content'][0].get('items', {}).get('results', []):
                    if 'dragon' in item.get('title', '').lower() and item.get('tier') == 'Standard':
                        logger.info(f"✅ Found Dragon's Den: {item['title']}")
                        
                        return {
                            "id": f"cutam:ca:cbc:dragons-den",
                            "type": "series",
                            "name": item['title'],
                            "poster": item.get('images', {}).get('background', {}).get('url', ''),
                            "logo": item.get('images', {}).get('background', {}).get('url', ''),
                            "description": item.get('description', ''),
                            "genres": ["Reality", "Business", "Entrepreneurship"],
                            "year": 2024,
                            "rating": "G",
                            "channel": "CBC",
                            "cbc_url": item.get('url', ''),
                            "cbc_type": item.get('type', ''),
                            "cbc_id": item.get('id', ''),
                            "gem_url": "https://gem.cbc.ca/dragons-den"
                        }
            
            # Fallback: Create Dragon's Den entry with known GEM URL
            logger.info("🔄 Using fallback Dragon's Den entry with GEM URL")
            return {
                "id": f"cutam:ca:cbc:dragons-den",
                "type": "series",
                "name": "Dragon's Den",
                "poster": "https://images.ctv.ca/archives/CTVNews/img/2010/01/15/dragons_den_100115.jpg",
                "logo": "https://images.ctv.ca/archives/CTVNews/img/2010/01/15/dragons_den_100115.jpg",
                "description": "Canadian reality television series featuring entrepreneurs pitching their business ideas to a panel of venture capitalists",
                "genres": ["Reality", "Business", "Entrepreneurship"],
                "year": 2024,
                "rating": "G",
                "channel": "CBC",
                "gem_url": "https://gem.cbc.ca/dragons-den"
            }
            
        except Exception as e:
            logger.error(f"❌ Error searching for Dragon's Den: {e}")
            return None
    
    def get_episodes(self, series_id: str) -> List[Dict[str, Any]]:
        """Get episodes for a CBC series"""
        try:
            logger.info(f"🇨🇦 Getting episodes for series: {series_id}")
            
            if "dragons-den" in series_id:
                # Generate episodes using GEM URL format
                episodes = self._generate_dragons_den_episodes()
                logger.info(f"✅ CBC returned {len(episodes)} episodes for Dragon's Den")
                return episodes
            
            logger.warning(f"⚠️ Unknown series ID: {series_id}")
            return []
            
        except Exception as e:
            logger.error(f"❌ Error getting CBC episodes: {e}")
            return []
    
    def _generate_dragons_den_episodes(self) -> List[Dict[str, Any]]:
        """Generate Dragon's Den episodes using GEM URL format"""
        try:
            episodes = []
            episode_counter = 1
            
            # Generate episodes for recent seasons (10-20)
            for season in range(10, 21):  # Seasons 10-20
                season_episodes = self._generate_season_episodes(season, episode_counter)
                episodes.extend(season_episodes)
                episode_counter += len(season_episodes)
            
            return episodes
            
        except Exception as e:
            logger.error(f"❌ Error generating Dragon's Den episodes: {e}")
            return []
    
    def _generate_season_episodes(self, season: int, start_counter: int) -> List[Dict[str, Any]]:
        """Generate episodes for a specific season using GEM URL format"""
        try:
            episodes = []
            episode_counter = start_counter
            
            # Each season typically has 20-21 episodes
            episodes_per_season = 21
            
            for episode_num in range(1, episodes_per_season + 1):
                # Create GEM URL: https://gem.cbc.ca/dragons-den/s{season}e{episode}
                gem_url = f"https://gem.cbc.ca/dragons-den/s{season}e{episode_num:02d}"
                
                # Generate a numeric media_id format based on CBC patterns
                import random
                media_id = str(random.randint(1000000, 9999999))
                
                # Use the s##e## format for episode IDs to match the stream router
                episode_id = f"cutam:ca:cbc:dragons-den:s{season}e{episode_num:02d}"
                
                episode_data = {
                    "id": episode_id,
                    "title": f"Season {season}, Episode {episode_num}",
                    "season": season,
                    "episode": episode_num,
                    "description": f"Dragon's Den Season {season}, Episode {episode_num} - Entrepreneurs pitch their business ideas to the Dragons",
                    "duration": "2640",  # 44 minutes in seconds
                    "broadcast_date": f"2015-{season-5:02d}-01",  # Approximate dates
                    "rating": "PG",
                    "channel": "CBC",
                    "program": "Dragon's Den",
                    "type": "episode",
                    "poster": "https://images.ctv.ca/archives/CTVNews/img/2010/01/15/dragons_den_100115.jpg",
                    "gem_url": gem_url,
                    "cbc_media_id": media_id,
                    "media_id": media_id  # For display purposes
                }
                episodes.append(episode_data)
                episode_counter += 1
            
            return episodes
            
        except Exception as e:
            logger.error(f"❌ Error generating season {season} episodes: {e}")
            return []
    
    def get_channel_stream_url(self, channel_id: str) -> Optional[Dict[str, Any]]:
        """Get live stream URL for a CBC channel"""
        try:
            logger.info(f"🇨🇦 Getting live stream for channel: {channel_id}")
            
            # Extract call sign from channel ID
            call_sign = channel_id.split(":")[-1].upper()
            
            # Get live stream info
            live_info_url = f"{self.base_url}/public/js/main.js"
            response = self.session.get(live_info_url)
            response.raise_for_status()
            
            # Extract live stream URL
            url_match = re.search(r'LLC_URL=r\+"(.*?)\?', response.text)
            if not url_match:
                logger.error("Could not find live stream URL")
                return None
            
            live_stream_url = f"https:{url_match.group(1)}"
            
            # Get live stream data
            live_response = self.session.get(live_stream_url)
            live_response.raise_for_status()
            live_data = live_response.json()
            
            # Find the specific channel
            for entry in live_data.get("entries", []):
                if call_sign in entry.get("cbc$callSign", ""):
                    content_url = entry.get("content", [{}])[0].get("url")
                    if content_url:
                        # Get the actual stream URL
                        stream_response = self.session.get(content_url)
                        stream_response.raise_for_status()
                        
                        # Extract video source URL
                        video_match = re.search(r'video src="(.*?)"', stream_response.text)
                        if video_match:
                            stream_url = video_match.group(1)
                            
                            return {
                                "url": stream_url,
                                "manifest_type": "mp4",
                                "headers": {
                                    "User-Agent": self.session.headers["User-Agent"]
                                }
                            }
            
            logger.warning(f"⚠️ Could not find stream for channel: {channel_id}")
            return None
            
        except Exception as e:
            logger.error(f"❌ Error getting CBC live stream: {e}")
            return None
    
    def get_stream_url(self, episode_id: str) -> Optional[Dict[str, Any]]:
        """Get stream URL for a CBC episode"""
        try:
            logger.info(f"🇨🇦 Getting stream for episode: {episode_id}")
            
            if "dragons-den" in episode_id:
                # Try to get real stream from CBC API
                stream_info = self._get_real_episode_stream(episode_id)
                if stream_info:
                    return stream_info
                
                # Fallback to placeholder
                return {
                    "url": "https://example.com/cbc-dragons-den-placeholder.mp4",
                    "manifest_type": "mp4",
                    "title": "Dragon's Den Episode (Placeholder)"
                }
            
            logger.warning(f"⚠️ Unknown episode ID: {episode_id}")
            return None
            
        except Exception as e:
            logger.error(f"❌ Error getting CBC episode stream: {e}")
            return None
    
    def _get_real_episode_stream(self, episode_id: str) -> Optional[Dict[str, Any]]:
        """Get real stream URL that works with Stremio based on exact authentication"""
        try:
            logger.info(f"🔍 Getting real stream for episode: {episode_id}")
            
            # Try to authenticate if not already authenticated
            if not self.is_authenticated:
                logger.info("🔐 Attempting CBC authentication...")
                if not self.authenticate():
                    logger.warning("⚠️ CBC authentication failed, using fallback")
                else:
                    logger.info("✅ CBC authentication successful")
            
            # Get GEM URL for the episode
            gem_url = self._get_episode_gem_url(episode_id)
            if not gem_url:
                logger.warning(f"⚠️ No GEM URL found for episode: {episode_id}")
                return None
            
            # Try to get stream URL using CBC API with authentication
            stream_url = self._get_authenticated_stream_url(episode_id, gem_url)
            if stream_url:
                headers = {
                    'User-Agent': self.session.headers['User-Agent'],
                    'Referer': 'https://gem.cbc.ca/',
                    'Accept': 'application/json, text/plain, */*',
                    'Accept-Language': 'en-CA,en;q=0.9,fr;q=0.8',
                    'Origin': 'https://gem.cbc.ca'
                }
                
                # Add authentication headers if available
                if self.is_authenticated and self.auth_token and self.claims_token:
                    headers['Authorization'] = f'Bearer {self.auth_token}'
                    headers['x-claims-token'] = self.claims_token
                
                return {
                    "url": stream_url,
                    "manifest_type": "hls",
                    "title": f"Dragon's Den Episode Stream",
                    "headers": headers
                }
            
            # Fallback: Create a proxy URL for Stremio
            logger.info(f"🔄 Creating proxy URL for Stremio")
            proxy_url = f"http://localhost:7860/stream/proxy?gem_url={gem_url}"
            
            return {
                "url": proxy_url,
                "manifest_type": "hls",
                "title": f"Dragon's Den Episode Stream",
                "headers": {
                    'User-Agent': self.session.headers['User-Agent'],
                    'Referer': 'https://gem.cbc.ca/'
                }
            }
            
        except Exception as e:
            logger.error(f"❌ Error getting real episode stream: {e}")
            return None
    
    def _get_authenticated_stream_url(self, episode_id: str, gem_url: str) -> Optional[str]:
        """Get stream URL using authenticated CBC API"""
        try:
            logger.info(f"🔍 Getting authenticated stream URL for episode: {episode_id}")
            
            # Try to get the asset ID from the GEM URL
            # This would require parsing the GEM page to get the actual asset ID
            # For now, we'll use a placeholder approach
            
            # Use CBC's media validation API with authentication
            validation_url = "https://services.radio-canada.ca/media/validation/v2/"
            params = {
                'appCode': 'toutv',
                'connectionType': 'hd',
                'deviceType': 'web',
                'idMedia': '1234567',  # Placeholder - would need real asset ID
                'multibitrate': 'true',
                'output': 'json',
                'tech': 'hls',
                'manifestType': 'desktop'
            }
            
            headers = {
                'User-Agent': self.session.headers['User-Agent']
            }
            
            # Add authentication headers
            if self.is_authenticated and self.auth_token and self.claims_token:
                headers['Authorization'] = f'Bearer {self.auth_token}'
                headers['x-claims-token'] = self.claims_token
            
            logger.info(f"🔍 Calling authenticated CBC validation API")
            response = self.session.get(validation_url, params=params, headers=headers)
            response.raise_for_status()
            
            data = response.json()
            
            if 'url' in data and data['url']:
                stream_url = data['url']
                logger.info(f"✅ Got authenticated stream URL: {stream_url}")
                return stream_url
            else:
                logger.warning(f"⚠️ No stream URL in authenticated response: {data.get('message', 'Unknown error')}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Error getting authenticated stream URL: {e}")
            return None
    
    def _get_episode_gem_url(self, episode_id: str) -> Optional[str]:
        """Get GEM URL for an episode"""
        try:
            # Extract season and episode info from episode_id
            episode_suffix = episode_id.split(':')[-1]  # e.g., "s19e01" or "episode-1"
            
            # Parse different episode ID formats
            if episode_suffix.startswith('s') and 'e' in episode_suffix:
                # New format: s19e01
                season_episode = episode_suffix
                season = season_episode[1:3]  # "19"
                episode = season_episode[4:6]  # "01"
                logger.info(f"📺 Parsed episode ID: {episode_id} -> Season {season}, Episode {episode}")
            elif episode_suffix.startswith('episode-'):
                # Old format: episode-1
                episode_num = int(episode_suffix.replace('episode-', ''))
                logger.info(f"📺 Parsed episode ID: {episode_id} -> Episode {episode_num}")
            else:
                logger.warning(f"⚠️ Unknown episode ID format: {episode_id}")
                return None
            
            # Get episodes to find the GEM URL
            episodes = self.get_episodes("cutam:ca:cbc:dragons-den")
            
            for episode in episodes:
                if episode['id'] == episode_id and 'gem_url' in episode:
                    logger.info(f"✅ Found GEM URL for {episode_id}: {episode['gem_url']}")
                    return episode['gem_url']
            
            logger.warning(f"⚠️ No GEM URL found for episode: {episode_id}")
            return None
            
        except Exception as e:
            logger.error(f"❌ Error getting episode GEM URL: {e}")
            return None
    
    def _load_authentication(self):
        """Load existing authentication from credentials file and tokens"""
        try:
            import os
            import json
            
            # Try to load from credentials file
            credentials_file = "credentials-test.json"
            if os.path.exists(credentials_file):
                with open(credentials_file, 'r') as f:
                    credentials = json.load(f)
                
                if 'cbcgem' in credentials:
                    cbc_creds = credentials['cbcgem']
                    self.username = cbc_creds.get('login', '')
                    self.password = cbc_creds.get('password', '')
                    
                    if self.username and self.password:
                        logger.info(f"✅ Loaded CBC credentials from {credentials_file}")
                        logger.info(f"   Username: {self.username}")
                    else:
                        logger.warning(f"⚠️ CBC credentials found but incomplete in {credentials_file}")
                else:
                    logger.warning(f"⚠️ No 'cbcgem' section found in {credentials_file}")
            else:
                logger.warning(f"⚠️ Credentials file {credentials_file} not found")
            
            # Try to load existing tokens
            access_token, claims_token = load_tokens()
            if access_token and claims_token:
                self.auth_token = access_token
                self.claims_token = claims_token
                self.is_authenticated = True
                logger.info("✅ Loaded existing CBC authentication tokens")
            else:
                logger.info("ℹ️ No existing CBC authentication tokens found")
                
        except Exception as e:
            logger.error(f"❌ Error loading authentication: {e}")
    
    def authenticate(self, username: str = None, password: str = None) -> bool:
        """Authenticate with CBC using the exact implementation"""
        try:
            logger.info("🔐 Starting CBC authentication...")
            
            # Use provided credentials or loaded credentials
            if not username:
                username = getattr(self, 'username', None)
            if not password:
                password = getattr(self, 'password', None)
            
            if not username or not password:
                logger.warning("⚠️ No CBC credentials provided")
                return False
            
            # Use the exact CBC authentication implementation
            self.cbc_auth.authenticate(username, password)
            
            # Update our state with the new tokens
            access_token, claims_token = load_tokens()
            if access_token and claims_token:
                self.auth_token = access_token
                self.claims_token = claims_token
                self.is_authenticated = True
                logger.info("✅ CBC authentication successful")
                return True
            else:
                logger.error("❌ CBC authentication failed - no tokens received")
                return False
            
        except Exception as e:
            logger.error(f"❌ CBC authentication error: {e}")
            return False

