#!/usr/bin/env python3
"""
CBC (Canadian Broadcasting Corporation) provider for Stremio addon
Based on the catchuptv plugin reference implementation
"""

import re
import logging
import traceback
from bs4 import BeautifulSoup
from typing import List, Dict, Optional, Any
from fastapi import Request
from app.providers.base_provider import BaseProvider
from app.auth.cbc_auth import CBCAuthenticator
from app.utils.credentials import load_credentials
from app.utils.cache import cache
from app.utils.cache_keys import CacheKeys
from app.utils.client_ip import get_client_ip
from app.utils.base_url import get_logo_url
from app.utils.http_utils import http_client
from app.utils.programs_loader import get_programs_for_provider

logger = logging.getLogger(__name__)

# Cache TTL constants (seconds)
_AUTH_SUCCESS_TTL = 3600   # 1 hour — re-check auth after token likely expired
_AUTH_FAILURE_TTL = 300    # 5 minutes — retry sooner after a failure
_CATALOG_TTL = 7200        # 2 hours — show/episode lists change infrequently
_STREAM_TTL = 1800         # 30 minutes — signed URLs have limited lifetime


class CBCProvider(BaseProvider):
    """CBC provider for Canadian content including Dragon's Den"""
    
    # BaseProvider class attributes
    provider_name = "cbc"
    base_url = "https://gem.cbc.ca"
    country = "ca"
    
    # Metadata
    display_name = "CBC"
    id_prefix = "cutam:ca:cbc"
    episode_marker = "episode:"
    catalog_id = "ca-cbc-dragons-den"
    supports_live = False

    
    @property
    def needs_ip_forwarding(self) -> bool:
        return True
    
    def __init__(self, request: Optional[Request] = None):
        # Call parent class init for session, api_client, credentials
        super().__init__(request)
        
        # CBC-specific API URLs
        self.api_base = "https://services.radio-canada.ca"
        self.catalog_api = f"{self.api_base}/ott/catalog/v2/gem"
        self.media_api = f"{self.api_base}/media/validation/v2"
        
        # Initialize CBC authenticator with cache handler (lazy auth - only authenticate when needed)
        self.authenticator = CBCAuthenticator(cache_handler=cache)
        # NOTE: Authentication is now lazy - only called in get_episode_stream_url()
        
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
    
    def _get_headers_with_viewer_ip(self, additional_headers: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        """Build headers with viewer IP forwarding for geo-sensitive requests."""
        base = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        viewer_ip = get_client_ip()
        if viewer_ip:
            logger.debug(f"🌍 [CBC] IP forwarding enabled for viewer IP: {viewer_ip}")
        else:
            logger.warning("⚠️ [CBC] No viewer IP available - using server IP")
        return self._build_ip_headers({**base, **(additional_headers or {})})
    
    _AUTH_CACHE_KEY = "cbc_auth_status"

    def _check_auth_cache(self) -> bool:
        """Return True if a valid, non-stale auth entry exists in the cache."""
        cached = cache.get(self._AUTH_CACHE_KEY)
        if cached and cached.get('authenticated'):
            if self.authenticator.is_authenticated():
                return True
            logger.warning("⚠️ [CBC] Cached auth status was stale, re-authenticating")
        return False

    def _store_auth_result(self, success: bool) -> None:
        """Persist the authentication outcome to cache with an appropriate TTL."""
        ttl = _AUTH_SUCCESS_TTL if success else _AUTH_FAILURE_TTL
        cache.set(self._AUTH_CACHE_KEY, {'authenticated': success}, ttl=ttl)

    def _authenticate_if_needed(self):
        """Authenticate with CBC if credentials are available, using caching."""
        try:
            if hasattr(self.authenticator, 'is_authenticated') and self.authenticator.is_authenticated():
                logger.debug("✅ [CBC] Already authenticated")
                return

            if self._check_auth_cache():
                logger.debug("✅ [CBC] Using cached authentication status")
                return

            credentials = load_credentials()
            cbc_creds = credentials.get('cbcgem', {})

            if cbc_creds.get('login') and cbc_creds.get('password'):
                logger.info("🔍 [CBC] Authenticating with CBC Gem")
                success = self.authenticator.login(cbc_creds['login'], cbc_creds['password'])
                self._store_auth_result(success)
                if success:
                    logger.info("✅ [CBC] Authentication successful")
                else:
                    logger.warning("⚠️ [CBC] Authentication failed")
            else:
                logger.info("ℹ️ [CBC] No credentials provided, using unauthenticated access")
                self._store_auth_result(False)
        except Exception as e:
            logger.error(f"❌ [CBC] Error during authentication: {e}")
            self._store_auth_result(False)
    
    def get_live_channels(self) -> List[Dict[str, Any]]:
        """CBC live channels are not currently supported - returns empty list."""
        # Live channel functionality was removed as non-functional per project requirements
        logger.info("ℹ️ [CBC] CBC live channels not available - using replay content only")
        return []
    

    def get_programs(self) -> List[Dict[str, Any]]:
        """Get CBC programs from programs.json."""
        try:
            logger.info("🔍 [CBC] Getting CBC programs...")

            # Primary source: programs.json (single source of truth)
            # NOTE: Caching is handled by the catalog router (CacheKeys.programs).
            cbc_shows = get_programs_for_provider('cbc')
            programs = []
            for slug, show_info in cbc_shows.items():
                program = {
                    "id": f"cutam:ca:cbc:{slug}",
                    "type": "series",
                    "name": show_info.get('name', slug),
                    "poster": show_info.get('poster') or get_logo_url("ca", "dragonsden", self.request),
                    "logo": show_info.get('logo', ''),
                    "background": show_info.get('background', ''),
                    "description": show_info.get('description', ''),
                    "genres": show_info.get('genres', []),
                    "year": show_info.get('year', 2024),
                    "rating": show_info.get('rating', 'G'),
                    "channel": show_info.get('channel', 'CBC')
                }
                programs.append(program)

            logger.info(f"✅ [CBC] CBC returned {len(programs)} programs from programs.json")
            return programs

        except Exception as e:
            logger.error(f"❌ [CBC] Error getting CBC programs: {e}")
            return []
    

    
    def get_episodes(self, series_id: str) -> List[Dict[str, Any]]:
        """Get episodes for any CBC series."""
        try:
            logger.info(f"🔍 [CBC] Getting episodes for series: {series_id}")

            # NOTE: Caching is handled by the meta router (CacheKeys.episodes).

            # Extract show_slug from series_id (format: cutam:ca:cbc:show-slug)
            parts = series_id.split(':')
            if len(parts) >= 4:
                show_slug = parts[3]  # e.g., "dragons-den"
            else:
                logger.warning(f"⚠️ [CBC] Invalid series ID format: {series_id}")
                return []

            # Get show info from programs.json for metadata
            cbc_shows = get_programs_for_provider('cbc')
            show_info = cbc_shows.get(show_slug, {})
            show_name = show_info.get('name', show_slug.replace('-', ' ').title())

            # Get episodes from CBC API (internally cached per show_slug)
            episodes = self._get_show_episodes(show_slug, show_name)
            if episodes:
                logger.info(f"✅ CBC returned {len(episodes)} episodes for {show_name}")
                return episodes

            logger.warning(f"⚠️ [CBC] No episodes found for: {show_slug}")
            return []

        except Exception as e:
            logger.error(f"❌ [CBC] Error getting CBC episodes: {e}")
            return []
    
    def _get_show_episodes(self, show_slug: str, show_name: str) -> List[Dict[str, Any]]:
        """Get ALL episodes for a CBC show with single optimized API call"""
        try:
            logger.info(f"🔍 [CBC] Fetching {show_name} episodes from CBC API...")
            
            # Check cache first
            cache_key = f"cbc_show_episodes:{show_slug}"
            cached_episodes = cache.get(cache_key)
            if cached_episodes:
                logger.info(f"✅ Using cached {show_name} episodes: {len(cached_episodes)} episodes")
                return cached_episodes
            
            episodes = []
            
            # Single API call - s01e01 returns ALL seasons in lineups array
            api_url = f"{self.catalog_api}/show/{show_slug}/s01e01?device=web&tier=Member"
            
            logger.debug(f"🔍 [CBC] API request: {api_url}")
            data = http_client.get_json(api_url, headers=self._get_headers_with_viewer_ip({
                'Accept': 'application/json, text/plain, */*',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate, br',
                'Referer': 'https://gem.cbc.ca/',
                'Origin': 'https://gem.cbc.ca',
                'DNT': '1',
                'Connection': 'keep-alive'
            }))
            
            if data and 'content' in data and data['content']:
                lineups = data['content'][0].get('lineups', [])
                logger.info(f"✅ [CBC] API returned {len(lineups)} seasons for {show_name}")
                
                for lineup in lineups:
                    season_num = lineup.get('seasonNumber')
                    if not season_num:
                        continue
                    
                    items = lineup.get('items', [])
                    season_episode_count = 0
                    
                    for item in items:
                        if item.get('mediaType') != 'Episode':
                            continue
                        
                        episode_data = self._parse_episode_from_season_data(item, season_num, show_slug, show_name)
                        if episode_data:
                            episodes.append(episode_data)
                            season_episode_count += 1
                    
                    if season_episode_count > 0:
                        logger.debug(f"🔍 [CBC] Season {season_num}: {season_episode_count} episodes")
            else:
                logger.warning(f"⚠️ [CBC] API returned no content for {show_slug}")
            
            # Sort by season and episode
            episodes.sort(key=lambda x: (x['season'], x['episode']))
            
            # Cache for 2 hours
            if episodes:
                cache.set(cache_key, episodes, ttl=_CATALOG_TTL)
                logger.info(f"✅ [CBC] Found {len(episodes)} total episodes for {show_name}")
            
            return episodes
            
        except Exception as e:
            logger.error(f"❌ [CBC] Error fetching {show_name} episodes: {e}")
            return []


    
    def _parse_episode_from_season_data(self, item: Dict[str, Any], season_num: int, show_slug: str = "", show_name: str = "") -> Optional[Dict[str, Any]]:
        """Parse episode data from season lineup item"""
        try:
            episode_num = item.get('episodeNumber', 0)
            if not episode_num:
                return None
            
            # Get title
            title = item.get('callToActionTitle', '') or item.get('title', f"Season {season_num}, Episode {episode_num}")
            
            # Get description from API or leave empty
            description = item.get('description', '')
            
            # Get duration from metadata
            duration = 2640  # Default 44 minutes
            metadata = item.get('metadata', {})
            if 'duration' in metadata:
                duration = metadata['duration']
            
            # Get air date
            air_date = item.get('infoTitle', '') or metadata.get('airDate', '') or metadata.get('availabilityDate', '')
            
            # Extract released date for Stremio
            released = ""
            availability_date = metadata.get('availabilityDate', '')
            if availability_date:
                released = f"{availability_date}T00:00:00.000Z"
            
            # Get rating
            rating = metadata.get('rating', 'PG') or 'PG'
            
            # Get thumbnail from images
            thumbnail = ""
            images = item.get('images', {})
            if 'card' in images and 'url' in images['card']:
                thumbnail = images['card']['url']
            
            # Get cast from API credits
            cast = []
            credits = metadata.get('credits', [])
            for credit in credits:
                if credit.get('title') == 'Actor(s)':
                    peoples = credit.get('peoples', '')
                    if peoples:
                        cast = [name.strip() for name in peoples.split(',') if name.strip()]
                        break
            
            # Get genres from API or empty
            genres = metadata.get('genres', [])
            
            # GEM URL
            gem_url = f"https://gem.cbc.ca/{show_slug}/s{season_num:02d}e{episode_num:02d}"
            
            # Media ID - critical for stream resolution
            cbc_media_id = item.get('idMedia')
            if not cbc_media_id:
                logger.warning(f"⚠️ [CBC] No media ID for S{season_num}E{episode_num}")
                return None
            
            episode_data = {
                "id": f"cutam:ca:cbc:{show_slug}:episode:{season_num}:{episode_num}",
                "title": title,
                "season": season_num,
                "episode": episode_num,
                "description": description,
                "duration": str(duration),
                "broadcast_date": air_date,
                "rating": rating,
                "channel": "CBC",
                "program": show_name,
                "type": "episode",
                "poster": thumbnail,
                "thumbnail": thumbnail,
                "gem_url": gem_url,
                "genres": genres,
                "cbc_media_id": str(cbc_media_id)
            }
            
            if released:
                episode_data["released"] = released
            
            logger.debug(f"🔍 [CBC] Created episode S{season_num}E{episode_num}")
            return episode_data
            
        except Exception as e:
            logger.error(f"❌ [CBC] Error parsing episode data: {e}")
            return None
    

    
    def get_channel_stream_url(self, channel_id: str) -> Optional[Dict[str, Any]]:
        """Get live stream URL for a CBC channel"""
        try:
            logger.info(f"🔍 [CBC] Getting live stream for channel: {channel_id}")
            
            # Extract call sign from channel ID
            call_sign = channel_id.split(":")[-1].upper()
            
            # Get live stream info
            live_info_url = f"{self.base_url}/public/js/main.js"
            response = http_client.safe_request("GET", live_info_url, headers=self._get_headers_with_viewer_ip())
            if not response:
                return None
            
            # Extract live stream URL
            url_match = re.search(r'LLC_URL=r\\+"(.*?)\\?', response.text)
            if not url_match:
                logger.error("❌ [CBC] Could not find live stream URL")
                return None
            
            live_stream_url = f"https:{url_match.group(1)}"
            
            # Get live stream data
            live_data = http_client.get_json(live_stream_url, headers=self._get_headers_with_viewer_ip())
            if not live_data:
                return None
            
            # Find the specific channel
            for entry in live_data.get("entries", []):
                if call_sign in entry.get("cbc$callSign", ""):
                    content_url = entry.get("content", [{}])[0].get("url")
                    if content_url:
                        # Get the actual stream URL
                        stream_response = http_client.safe_request("GET", content_url, headers=self._get_headers_with_viewer_ip())
                        if not stream_response:
                            return None
                        
                        # Extract video source URL
                        video_match = re.search(r'video src="(.*?)"', stream_response.text)
                        if video_match:
                            stream_url = video_match.group(1)
                            
                            return {
                                "url": stream_url,
                                "manifest_type": "mp4",
                                "headers": {
                                    "User-Agent": self._get_headers_with_viewer_ip().get('User-Agent')
                                }
                            }
            
            logger.warning(f"⚠️ [CBC] Could not find stream for channel: {channel_id}")
            return None
            
        except Exception as e:
            logger.error(f"❌ [CBC] Error getting CBC live stream: {e}")
            return None
    
    def get_episode_stream_url(self, episode_id: str) -> Optional[Dict[str, Any]]:
        """Get stream URL for a CBC episode using proper CBC Gem API with caching"""
        try:
            logger.info(f"🔍 [CBC] Getting stream for episode: {episode_id}")
            
            # Lazy authentication - only authenticate when a stream is actually requested
            self._authenticate_if_needed()
            
            # Check cache first for stream URL
            cache_key = CacheKeys.stream(episode_id)
            cached_stream = cache.get(cache_key)
            if cached_stream:
                logger.info(f"✅ [CBC] Using cached stream URL for episode: {episode_id}")
                return cached_stream
            
            # Extract media ID from episode ID
            media_id = self._extract_media_id_from_episode_id(episode_id)
            if not media_id:
                logger.error(f"❌ [CBC] Could not extract media ID from episode: {episode_id}")
                return None
            
            # Get stream using CBC Gem API
            stream_info = self._get_stream_from_cbc_api(media_id)
            if stream_info:
                # Cache stream info for 30 minutes
                cache.set(cache_key, stream_info, ttl=_STREAM_TTL)
                return stream_info
            
            logger.warning(f"⚠️ [CBC] No stream found for episode: {episode_id}")
            return None
            
        except Exception as e:
            logger.error(f"❌ [CBC] Error getting CBC episode stream: {e}")
            return None
    

    def _extract_media_id_from_episode_id(self, episode_id: str) -> Optional[str]:
        """Extract CBC media ID from episode ID with dynamic show detection"""
        try:
            # Parse episode_id format: cutam:ca:cbc:show-slug:episode:S:E
            parts = episode_id.split(':')
            if len(parts) >= 5:
                show_slug = parts[3]
                series_id = f"cutam:ca:cbc:{show_slug}"
            else:
                logger.warning(f"⚠️ [CBC] Invalid episode ID format: {episode_id}")
                return None
            
            # Get episodes for this show
            episodes = self.get_episodes(series_id)
            
            # Parse season/episode from ID: ...episode:S:E
            colon_parts = episode_id.split(':')
            if len(colon_parts) >= 7:
                try:
                    season_num = int(colon_parts[-2])
                    episode_num = int(colon_parts[-1])
                    for ep in episodes:
                        if (ep.get('season') == season_num and 
                            ep.get('episode') == episode_num and 
                            ep.get('cbc_media_id')):
                            media_id = str(ep['cbc_media_id'])
                            logger.debug(f"🔍 [CBC] Found media ID for S{season_num}E{episode_num}: {media_id}")
                            return media_id
                except ValueError:
                    pass
            
            # Fallback: direct ID match
            for ep in episodes:
                if ep.get('id') == episode_id and ep.get('cbc_media_id'):
                    return str(ep['cbc_media_id'])
            
            logger.warning(f"⚠️ [CBC] No media ID found for: {episode_id}")
            return None
            
        except Exception as e:
            logger.error(f"❌ Error extracting media ID: {e}")
            return None
    
    def _get_stream_from_cbc_api(self, media_id: str) -> Optional[Dict[str, Any]]:
        """Get stream URL from CBC Gem API with authentication and robust error handling"""
        try:
            logger.info(f"🔍 Getting stream from CBC API for media: {media_id}")
            
            # Ensure we are authenticated
            if not self.authenticator.is_authenticated():
                logger.error("❌ Not authenticated with CBC Gem")
                return None
            
            # Get authenticated headers (ensures claims token)
            headers = self.authenticator.get_authenticated_headers()
            claims_token = headers.get('x-claims-token')
            if not claims_token:
                logger.error("❌ Missing claims token for CBC content")
                return None
            
            params = {
                'appCode': 'gem',
                'connectionType': 'hd',
                'deviceType': 'ipad',
                'multibitrate': 'true',
                'output': 'json',
                'tech': 'hls',
                'manifestVersion': '2',
                'manifestType': 'desktop',
                'idMedia': str(media_id),
            }
            
            # Merge viewer IP headers with authenticated headers
            final_headers = self._merge_ip_headers(headers)
            viewer_ip = get_client_ip()
            if viewer_ip:
                logger.info(f"🌍 CBC Media API request using viewer IP: {viewer_ip}")
            else:
                logger.warning("⚠️ CBC Media API request using server IP (no viewer IP available)")
            
            data = http_client.get_json(
                self.media_api,
                params=params,
                headers=final_headers
            )
            if not data:
                return None
            
            error_code = data.get('errorCode', 0)
            if error_code == 1:
                logger.error("❌ Content is geo-restricted to Canada")
                return None
            if error_code == 35:
                logger.error("❌ Authentication required or claims token invalid; attempting refresh once")
                # Clear cached claims token and retry once
                self.authenticator.claims_token = None
                refreshed_headers = self.authenticator.get_authenticated_headers()
                if refreshed_headers.get('x-claims-token') and refreshed_headers.get('x-claims-token') != claims_token:
                    return self._get_stream_from_cbc_api(media_id)
                return None
            if error_code != 0:
                logger.error(f"❌ CBC API error {error_code}: {data.get('message', 'Unknown error')}")
                return None
            
            stream_url = data.get('url')
            if not stream_url:
                logger.error("❌ No stream URL in CBC API response")
                logger.error(str(data)[:500])
                return None
            
            manifest_type = 'hls'
            if '.m3u8' in stream_url:
                manifest_type = 'hls'
            elif '.mpd' in stream_url:
                manifest_type = 'dash'
            elif '.ism' in stream_url:
                manifest_type = 'ism'
            
            logger.info(f"✅ Got CBC stream: {manifest_type.upper()}")
            logger.info(f"🔗 [CBC] Full stream URL: {stream_url}")
            
            # Only return safe playback headers
            playback_headers = {
                'User-Agent': headers.get('User-Agent', self._get_headers_with_viewer_ip().get('User-Agent', '')),
                'Referer': headers.get('Referer', 'https://gem.cbc.ca/'),
                'Origin': headers.get('Origin', 'https://gem.cbc.ca')
            }
            
            return {
                "url": stream_url,
                "manifest_type": manifest_type,
                "headers": playback_headers,
                "title": "CBC Gem Stream"
            }
        except Exception as e:
            logger.error(f"❌ Error getting stream from CBC API: {e}")
            logger.error(traceback.format_exc())
            return None
