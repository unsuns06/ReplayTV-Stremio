#!/usr/bin/env python3
"""
CBC (Canadian Broadcasting Corporation) provider for Stremio addon
Based on the catchuptv plugin reference implementation
"""

import re
import logging
from typing import List, Dict, Optional, Any
from fastapi import Request
from app.auth.cbc_auth import CBCAuthenticator
from app.utils.credentials import load_credentials
from app.utils.cache import cache
from app.utils.client_ip import get_client_ip, merge_ip_headers
from app.utils.base_url import  get_logo_url
from app.utils.http_utils import http_client
from app.utils.programs_loader import get_programs_for_provider

logger = logging.getLogger(__name__)

class CBCProvider:
    """CBC provider for Canadian content including Dragon's Den"""
    
    def __init__(self, request: Optional[Request] = None):
        self.request = request
        self.base_url = "https://gem.cbc.ca"
        self.api_base = "https://services.radio-canada.ca"
        self.catalog_api = f"{self.api_base}/ott/catalog/v2/gem"
        self.media_api = f"{self.api_base}/media/validation/v2"
        
        # Initialize CBC authenticator with cache handler
        self.authenticator = CBCAuthenticator(cache_handler=cache)
        self._authenticate_if_needed()
        
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
        """Get headers with viewer IP forwarding for geo-sensitive requests"""
        try:
            # Get the viewer's IP from the request context
            viewer_ip = get_client_ip()
            if viewer_ip:
                logger.info(f"🌍 Using viewer IP for CBC requests: {viewer_ip}")
                logger.info(f"🌍 IP forwarding headers: X-Forwarded-For={viewer_ip}, X-Real-IP={viewer_ip}, CF-Connecting-IP={viewer_ip}")
            else:
                logger.warning("⚠️ No viewer IP available for CBC requests - using server IP")
            
            # Start with base headers
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            # Add IP forwarding headers
            ip_headers = merge_ip_headers(ip=viewer_ip)
            headers.update(ip_headers)
            
            # Add any additional headers
            if additional_headers:
                headers.update(additional_headers)
            
            return headers
        except Exception as e:
            logger.error(f"❌ Error getting headers with viewer IP: {e}")
            # Fallback to base headers
            return {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
    
    def _authenticate_if_needed(self):
        """Authenticate with CBC if credentials are available with caching"""
        try:
            # Check if we're already authenticated and cache is valid
            if hasattr(self.authenticator, 'is_authenticated') and self.authenticator.is_authenticated():
                logger.info("✅ CBC already authenticated")
                return
            
            # Check cache for authentication status
            auth_cache_key = "cbc_auth_status"
            cached_auth = cache.get(auth_cache_key)
            if cached_auth and cached_auth.get('authenticated'):
                logger.info("✅ Using cached CBC authentication status")
                # Verify the authenticator actually has valid tokens
                if self.authenticator.is_authenticated():
                    return
                else:
                    logger.warning("⚠️ Cached auth status was stale, re-authenticating")
            
            credentials = load_credentials()
            cbc_creds = credentials.get('cbcgem', {})
            
            if cbc_creds.get('login') and cbc_creds.get('password'):
                logger.info("🇨🇦 Authenticating with CBC Gem")
                success = self.authenticator.login(
                    cbc_creds['login'], 
                    cbc_creds['password']
                )
                if success:
                    logger.info("✅ CBC authentication successful")
                    # Cache authentication status for 1 hour
                    cache.set(auth_cache_key, {'authenticated': True}, ttl=3600)
                else:
                    logger.warning("⚠️ CBC authentication failed")
                    # Cache failed authentication for 5 minutes
                    cache.set(auth_cache_key, {'authenticated': False}, ttl=300)
            else:
                logger.info("ℹ️ No CBC credentials provided, using unauthenticated access")
                # Cache unauthenticated status for 1 hour
                cache.set(auth_cache_key, {'authenticated': False}, ttl=3600)
        except Exception as e:
            logger.error(f"❌ Error during CBC authentication: {e}")
            # Cache error status for 5 minutes
            cache.set("cbc_auth_status", {'authenticated': False}, ttl=300)
    
    def get_shows(self) -> List[Dict[str, Any]]:
        """Get CBC shows/series from programs.json with caching"""
        try:
            logger.info("🇨🇦 Getting CBC shows...")
            
            # Check cache first
            cache_key = "cbc_shows"
            cached_shows = cache.get(cache_key)
            if cached_shows:
                logger.info(f"✅ Using cached CBC shows: {len(cached_shows)} shows")
                return cached_shows
            
            # Load shows from programs.json (single source of truth)
            cbc_shows = get_programs_for_provider('cbc')
            shows = []
            for slug, show_info in cbc_shows.items():
                shows.append({
                    "id": f"cutam:ca:cbc:{slug}",
                    "title": show_info.get('name', slug),
                    "description": show_info.get('description', ''),
                    "poster": show_info.get('poster') or get_logo_url("ca", "dragonsden", self.request),
                    "background": show_info.get('background', ''),
                    "type": "series",
                    "country": "CA",
                    "provider": "cbc"
                })
            
            # Cache shows for 2 hours
            cache.set(cache_key, shows, ttl=7200)
            logger.info(f"📺 Found and cached {len(shows)} CBC shows from programs.json")
            return shows
            
        except Exception as e:
            logger.error(f"❌ Error getting CBC shows: {e}")
            return []

    def get_live_channels(self) -> List[Dict[str, Any]]:
        """CBC live channels are not currently supported - returns empty list."""
        # Live channel functionality was removed as non-functional per project requirements
        logger.info("ℹ️ CBC live channels not available - using replay content only")
        return []
    

    def get_programs(self) -> List[Dict[str, Any]]:
        """Get CBC programs from programs.json with optional API enrichment"""
        try:
            logger.info("🇨🇦 Getting CBC programs...")
            
            # Check cache first
            cache_key = "cbc_programs"
            cached_programs = cache.get(cache_key)
            if cached_programs:
                logger.info(f"✅ Using cached CBC programs: {len(cached_programs)} programs")
                return cached_programs
            
            # Primary source: programs.json (single source of truth)
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
            
            # Optionally enrich with live API metadata (non-blocking)
            try:
                for program in programs:
                    slug = program['id'].split(':')[-1]
                    if slug == 'dragons-den':
                        api_enrichment = self._search_dragons_den()
                        if api_enrichment:
                            # Only update dynamic fields, preserve programs.json core data
                            if api_enrichment.get('gem_url'):
                                program['gem_url'] = api_enrichment['gem_url']
            except Exception as enrich_error:
                logger.warning(f"⚠️ API enrichment failed (non-critical): {enrich_error}")
            
            # Cache programs for 2 hours
            cache.set(cache_key, programs, ttl=7200)
            logger.info(f"✅ CBC returned and cached {len(programs)} programs from programs.json")
            return programs
            
        except Exception as e:
            logger.error(f"❌ Error getting CBC programs: {e}")
            return []
    
    def _search_dragons_den(self) -> Optional[Dict[str, Any]]:
        """Search for Dragon's Den on GEM website for API enrichment (live metadata)"""
        try:
            logger.info("🔍 Checking Dragon's Den on GEM for live metadata...")
            
            # Check cache first
            cache_key = "cbc_dragons_den_search"
            cached_result = cache.get(cache_key)
            if cached_result:
                logger.info("✅ Using cached Dragon's Den GEM metadata")
                return cached_result
            
            # Try to get Dragon's Den from GEM website directly
            gem_url = "https://gem.cbc.ca/dragons-den"
            response = http_client.safe_request("GET", gem_url, headers=self._get_headers_with_viewer_ip())
            if not response:
                return None
            
            # Parse the GEM page to extract live show information
            from bs4 import BeautifulSoup
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Extract show title from live page (for verification)
            title_element = soup.find('h1')
            show_title = title_element.get_text().strip() if title_element else None
            
            logger.info(f"✅ Found Dragon's Den on GEM: {show_title or 'title not found'}")
            
            # Return only the live API metadata (program data comes from programs.json)
            result = {
                "gem_url": gem_url,
                "live_title": show_title
            }
            
            # Cache the result for 1 hour
            cache.set(cache_key, result, ttl=3600)
            return result
            
        except Exception as e:
            logger.error(f"❌ Error searching for Dragon's Den on GEM: {e}")
            return None
    
    def get_episodes(self, series_id: str) -> List[Dict[str, Any]]:
        """Get episodes for a CBC series with caching"""
        try:
            logger.info(f"🇨🇦 Getting episodes for series: {series_id}")
            
            # Check cache first
            cache_key = f"cbc_episodes_{series_id}"
            cached_episodes = cache.get(cache_key)
            if cached_episodes:
                logger.info(f"✅ Using cached episodes for {series_id}: {len(cached_episodes)} episodes")
                return cached_episodes
            
            if "dragons-den" in series_id:
                # Try to get real episodes from CBC API
                episodes = self._get_dragons_den_episodes()
                if episodes:
                    logger.info(f"✅ CBC returned {len(episodes)} real episodes for Dragon's Den")
                    # Cache the episodes for 30 minutes
                    cache.set(cache_key, episodes, ttl=1800)
                    return episodes
                
                # Fallback to sample episodes
                episodes = [
                    {
                        "id": "cutam:ca:cbc:dragons-den:episode-1",
                        "title": "Season 19, Episode 1",
                        "season": 19,
                        "episode": 1,
                        "description": "Entrepreneurs pitch their business ideas to the Dragons",
                        "duration": "3600",  # 1 hour in seconds
                        "broadcast_date": "2024-01-01",
                        "rating": "G",
                        "channel": "CBC",
                        "program": "Dragon's Den",
                        "type": "episode",
                        "poster": get_logo_url("ca", "dragonsden", self.request)
                    },
                    {
                        "id": "cutam:ca:cbc:dragons-den:episode-2", 
                        "title": "Season 19, Episode 2",
                        "season": 19,
                        "episode": 2,
                        "description": "More entrepreneurs face the Dragons",
                        "duration": "3600",
                        "broadcast_date": "2024-01-08",
                        "rating": "G",
                        "channel": "CBC",
                        "program": "Dragon's Den",
                        "type": "episode",
                        "poster": get_logo_url("ca", "dragonsden", self.request)
                    }
                ]
                
                logger.info(f"✅ CBC returned {len(episodes)} fallback episodes for Dragon's Den")
                # Cache fallback episodes for 5 minutes
                cache.set(cache_key, episodes, ttl=300)
                return episodes
            
            logger.warning(f"⚠️ Unknown series ID: {series_id}")
            return []
            
        except Exception as e:
            logger.error(f"❌ Error getting CBC episodes: {e}")
            return []
    
    def _get_dragons_den_episodes(self) -> List[Dict[str, Any]]:
        """Get real Dragon's Den episodes from CBC API with optimized single call"""
        try:
            logger.info("🔍 Fetching real Dragon's Den episodes from CBC API...")
            
            # Check cache for all episodes first
            cache_key = "cbc_dragons_den_all_episodes"
            cached_episodes = cache.get(cache_key)
            if cached_episodes:
                logger.info(f"✅ Using cached Dragon's Den episodes: {len(cached_episodes)} episodes")
                return cached_episodes
            
            episodes = []
            
            # Fetch episodes from multiple seasons
            # Try recent seasons first, then older ones
            seasons_to_fetch = [20, 19, 18, 17, 16, 15, 14, 13, 12, 11, 10]
            logger.info(f"🔍 Fetching episodes from {len(seasons_to_fetch)} seasons: {seasons_to_fetch}")
            
            for season in seasons_to_fetch:
                try:
                    season_episodes = self._get_season_episodes_from_api(season)
                    if season_episodes:
                        episodes.extend(season_episodes)
                        logger.info(f"✅ Season {season}: {len(season_episodes)} episodes (Total: {len(episodes)})")
                    else:
                        logger.info(f"ℹ️ Season {season}: No episodes found")
                except Exception as e:
                    logger.warning(f"⚠️ Failed to get season {season}: {e}")
                    continue
            
            # Sort episodes by season and episode number
            episodes.sort(key=lambda x: (x['season'], x['episode']))
            
            # Cache all episodes for 1 hour
            if episodes:
                cache.set(cache_key, episodes, ttl=3600)
                # Count episodes by season for summary
                season_counts = {}
                for ep in episodes:
                    season = ep.get('season', 'Unknown')
                    season_counts[season] = season_counts.get(season, 0) + 1
                
                logger.info(f"✅ Found and cached {len(episodes)} total episodes from CBC API")
                logger.info(f"📊 Episodes by season: {dict(sorted(season_counts.items()))}")
            else:
                logger.warning("⚠️ No episodes found from any season")
            
            return episodes
            
        except Exception as e:
            logger.error(f"❌ Error fetching real Dragon's Den episodes: {e}")
            return []
    
    def _get_detailed_episode_info(self, episode_url: str, season_num: int, episode_num: int, episode_title: str) -> Optional[Dict[str, Any]]:
        """Get detailed information for a specific episode from GEM"""
        try:
            logger.info(f"🔍 Getting details for S{season_num}E{episode_num}: {episode_url}")
            
            response = http_client.safe_request("GET", episode_url, headers=self._get_headers_with_viewer_ip({
                'Referer': 'https://gem.cbc.ca/dragons-den',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate, br',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1'
            }))
            if not response:
                return None
            
            from bs4 import BeautifulSoup
            import re
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Extract episode title from the page
            title_element = soup.find('h1') or soup.find('h2') or soup.find('h3')
            if title_element:
                clean_title = title_element.get_text().strip()
                # Remove "Dragons' Den" prefix if present
                clean_title = re.sub(r'^Dragons\'?\s*Den\s*[-–]\s*', '', clean_title, flags=re.IGNORECASE)
            else:
                clean_title = f"Season {season_num}, Episode {episode_num}"
            
            # Extract description from the episode content
            description = self._extract_description_from_gem(soup)
            
            # Extract thumbnail/poster
            thumbnail = self._extract_thumbnail_from_gem(soup)
            
            # Extract air date
            air_date = self._extract_air_date_from_gem(soup)
            
            # Extract duration
            duration = self._extract_duration_from_gem(soup)
            
            # Extract rating
            rating = self._extract_rating_from_gem(soup)
            
            # Extract cast information
            cast = self._extract_cast_from_gem(soup)
            
            # Create episode data
            episode_data = {
                "id": f"cutam:ca:cbc:dragons-den:episode-{season_num}-{episode_num}",
                "title": clean_title,
                "season": season_num,
                "episode": episode_num,
                "description": description,
                "duration": duration,
                "broadcast_date": air_date,
                "rating": rating,
                "channel": "CBC",
                "program": "Dragon's Den",
                "type": "episode",
                "poster": thumbnail,
                "thumbnail": thumbnail,
                "gem_url": episode_url,
                "cast": cast,
                "genres": ["Reality", "Business", "Entrepreneurship"]
            }
            
            logger.info(f"✅ Extracted details for S{season_num}E{episode_num}: {clean_title}")
            return episode_data
            
        except Exception as e:
            logger.error(f"❌ Error getting episode details for S{season_num}E{episode_num}: {e}")
            return None
    
    def _extract_description_from_gem(self, soup) -> str:
        """Extract episode description from GEM page based on actual structure"""
        try:
            # Look for the episode description in the content
            # Based on the GEM site, descriptions are in paragraph elements
            description_selectors = [
                'p',  # General paragraph elements
                'div[class*="description"]',
                'div[class*="plot"]',
                'div[class*="summary"]',
                'div[class*="synopsis"]',
                '.episode-description',
                '.episode-plot',
                '.episode-summary'
            ]
            
            for selector in description_selectors:
                elements = soup.select(selector)
                for element in elements:
                    text = element.get_text().strip()
                    # Look for meaningful descriptions (longer than 50 characters)
                    if text and len(text) > 50 and 'Dragons' in text:
                        return text
            
            # Look for meta description
            meta_desc = soup.find('meta', attrs={'name': 'description'})
            if meta_desc and meta_desc.get('content'):
                content = meta_desc.get('content').strip()
                if len(content) > 20:
                    return content
            
            return "Canadian reality television series featuring entrepreneurs pitching their business ideas to a panel of venture capitalists"
            
        except Exception as e:
            logger.error(f"❌ Error extracting description: {e}")
            return "Dragon's Den episode"
    
    def _extract_thumbnail_from_gem(self, soup) -> str:
        """Extract episode thumbnail from GEM page based on actual structure"""
        try:
            # Look for thumbnail in various possible locations
            thumbnail_selectors = [
                'img[class*="thumbnail"]',
                'img[class*="poster"]',
                'img[class*="episode"]',
                'img[class*="card"]',
                'img[alt*="episode"]',
                'img[alt*="Episode"]',
                'img[alt*="Dragons"]',
                '.episode-thumbnail img',
                '.episode-poster img',
                '.episode-card img'
            ]
            
            for selector in thumbnail_selectors:
                element = soup.select_one(selector)
                if element and element.get('src'):
                    src = element.get('src')
                    if src and not src.startswith('data:'):
                        # Convert relative URLs to absolute
                        if src.startswith('//'):
                            return f"https:{src}"
                        elif src.startswith('/'):
                            return f"https://gem.cbc.ca{src}"
                        elif src.startswith('http'):
                            return src
            
            # Look for og:image meta tag
            og_image = soup.find('meta', property='og:image')
            if og_image and og_image.get('content'):
                return og_image.get('content')
            
            # Fallback to Dragon's Den default image
            return get_logo_url("ca", "dragonsden", self.request)
            
        except Exception as e:
            logger.error(f"❌ Error extracting thumbnail: {e}")
            return get_logo_url("ca", "dragonsden", self.request)
    
    def _extract_air_date_from_gem(self, soup) -> str:
        """Extract episode air date from GEM page based on actual structure"""
        try:
            # Look for air date in various possible locations
            date_selectors = [
                'time[datetime]',
                'span[class*="date"]',
                'div[class*="date"]',
                'p[class*="date"]',
                'span[class*="air"]',
                'div[class*="air"]',
                '.episode-date',
                '.air-date',
                '.broadcast-date'
            ]
            
            for selector in date_selectors:
                element = soup.select_one(selector)
                if element:
                    # Try to get datetime attribute first
                    datetime_attr = element.get('datetime')
                    if datetime_attr:
                        return datetime_attr
                    
                    # Otherwise get text content
                    date_text = element.get_text().strip()
                    if date_text:
                        return date_text
            
            return ""
            
        except Exception as e:
            logger.error(f"❌ Error extracting air date: {e}")
            return ""
    
    def _extract_duration_from_gem(self, soup) -> str:
        """Extract episode duration from GEM page based on actual structure"""
        try:
            # Look for duration in various possible locations
            duration_selectors = [
                'span[class*="duration"]',
                'div[class*="duration"]',
                'p[class*="duration"]',
                'span[class*="time"]',
                'div[class*="time"]',
                '.episode-duration',
                '.duration'
            ]
            
            for selector in duration_selectors:
                element = soup.select_one(selector)
                if element:
                    duration_text = element.get_text().strip()
                    if duration_text:
                        # Convert "44 min" to seconds
                        import re
                        duration_match = re.search(r'(\d+)\s*min', duration_text)
                        if duration_match:
                            return str(int(duration_match.group(1)) * 60)
                        # If already in seconds format
                        elif duration_text.isdigit():
                            return duration_text
            
            return "2640"  # Default 44 minutes in seconds
            
        except Exception as e:
            logger.error(f"❌ Error extracting duration: {e}")
            return "2640"
    
    def _extract_rating_from_gem(self, soup) -> str:
        """Extract episode rating from GEM page based on actual structure"""
        try:
            # Look for rating in various possible locations
            rating_selectors = [
                'span[class*="rating"]',
                'div[class*="rating"]',
                'p[class*="rating"]',
                'span[class*="age"]',
                'div[class*="age"]',
                '.episode-rating',
                '.rating',
                '.age-rating'
            ]
            
            for selector in rating_selectors:
                element = soup.select_one(selector)
                if element:
                    rating_text = element.get_text().strip()
                    if rating_text:
                        return rating_text
            
            return "PG"  # Default rating for Dragon's Den
            
        except Exception as e:
            logger.error(f"❌ Error extracting rating: {e}")
            return "PG"
    
    def _extract_cast_from_gem(self, soup) -> List[str]:
        """Extract cast information from GEM page based on actual structure"""
        try:
            cast = []
            
            # Look for cast information
            cast_selectors = [
                'div[class*="cast"]',
                'div[class*="actors"]',
                'ul[class*="cast"]',
                'ul[class*="actors"]',
                '.episode-cast',
                '.cast-list'
            ]
            
            for selector in cast_selectors:
                element = soup.select_one(selector)
                if element:
                    # Look for list items or spans within the cast element
                    cast_items = element.find_all(['li', 'span', 'div'])
                    for item in cast_items:
                        cast_text = item.get_text().strip()
                        if cast_text and len(cast_text) > 2:
                            cast.append(cast_text)
            
            # If no cast found, add default Dragon's Den cast
            if not cast:
                cast = [
                    "Jim Treliving",
                    "Michael Wekerle", 
                    "Michele Romanow",
                    "Manjit Minhas",
                    "Joe Mimran"
                ]
            
            return cast[:10]  # Limit to 10 cast members
            
        except Exception as e:
            logger.error(f"❌ Error extracting cast: {e}")
            return ["Jim Treliving", "Michael Wekerle", "Michele Romanow", "Manjit Minhas", "Joe Mimran"]
    
    def _get_season_episodes_from_api(self, season_num: int) -> List[Dict[str, Any]]:
        """Get episodes for a specific season from CBC API with caching"""
        try:
            # Check cache first
            cache_key = f"cbc_season_{season_num}_episodes"
            cached_episodes = cache.get(cache_key)
            if cached_episodes:
                logger.info(f"✅ Using cached episodes for season {season_num}: {len(cached_episodes)} episodes")
                return cached_episodes
            
            episodes = []
            
            # Get season data from any episode URL (they all return the same season list)
            api_url = f"https://services.radio-canada.ca/ott/catalog/v2/gem/show/dragons-den/s{season_num:02d}e01?device=web&tier=Member"
            
            logger.info(f"🌍 CBC Season API request using viewer IP: {get_client_ip()}")
            data = http_client.get_json(api_url, headers=self._get_headers_with_viewer_ip({
                'Accept': 'application/json, text/plain, */*',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate, br',
                'Referer': 'https://gem.cbc.ca/',
                'Origin': 'https://gem.cbc.ca',
                'DNT': '1',
                'Connection': 'keep-alive'
            }))
            
            if data:
                content = data.get('content', [])
                
                if content:
                    lineups = content[0].get('lineups', [])
                    
                    # Find the specific season
                    for lineup in lineups:
                        if lineup.get('seasonNumber') == season_num:
                            items = lineup.get('items', [])
                            
                            # Process each episode in the season
                            for item in items:
                                # Skip trailers and non-episode content
                                media_type = item.get('mediaType', '')
                                if media_type != 'Episode':
                                    logger.info(f"⏭️ Skipping non-episode: {item.get('title', 'Unknown')} ({media_type})")
                                    continue
                                
                                episode_data = self._parse_episode_from_season_data(item, season_num)
                                if episode_data:
                                    episodes.append(episode_data)
                                    logger.info(f"✅ Found S{season_num:02d}E{episode_data['episode']}")
                            
                            break
            
            # Cache the episodes for 2 hours
            if episodes:
                cache.set(cache_key, episodes, ttl=7200)
                logger.info(f"✅ Cached {len(episodes)} episodes for season {season_num}")
            
            return episodes
            
        except Exception as e:
            logger.error(f"❌ Error getting season {season_num} episodes: {e}")
            return []
    
    def _parse_episode_from_season_data(self, item: Dict[str, Any], season_num: int) -> Optional[Dict[str, Any]]:
        """Parse episode data from season lineup item"""
        try:
            # Get episode number
            episode_num = item.get('episodeNumber', 0)
            if not episode_num:
                return None
            
            # Get title - prefer callToActionTitle as it includes season info
            title = item.get('callToActionTitle', '')
            if not title:
                title = item.get('title', f"Season {season_num}, Episode {episode_num}")
            
            # Get description
            description = item.get('description', '')
            if not description:
                description = "Canadian reality television series featuring entrepreneurs pitching their business ideas to a panel of venture capitalists"
            
            # Get duration from metadata
            duration = 2640  # Default 44 minutes
            metadata = item.get('metadata', {})
            if 'duration' in metadata:
                duration = metadata['duration']
            
            # Get air date from infoTitle or metadata
            air_date = item.get('infoTitle', '')
            if not air_date:
                air_date = metadata.get('airDate', '')
            
            # Get rating from metadata
            rating = metadata.get('rating', 'PG')
            if not rating:
                rating = 'PG'
            
            # Get thumbnail from episode images
            thumbnail = self._generate_thumbnail_url(season_num, episode_num)
            images = item.get('images', {})
            if 'card' in images and 'url' in images['card']:
                thumbnail = images['card']['url']
            
            # Get cast information from metadata
            cast = ["Jim Treliving", "Michael Wekerle", "Michele Romanow", "Manjit Minhas", "Joe Mimran"]
            credits = metadata.get('credits', [])
            for credit in credits:
                if credit.get('title') == 'Actor(s)':
                    peoples = credit.get('peoples', '')
                    if peoples:
                        cast = [name.strip() for name in peoples.split(',') if name.strip()]
                        break
            
            # Get GEM URL
            gem_url = f"https://gem.cbc.ca/dragons-den/s{season_num:02d}e{episode_num:02d}"
            
            # Get the CBC media ID from the item - THIS IS CRITICAL FOR STREAM RESOLUTION
            cbc_media_id = item.get('idMedia')
            
            # Ensure we have a media ID; otherwise skip item
            if not cbc_media_id:
                logger.warning(f"\u26a0\ufe0f No media ID for S{season_num}E{episode_num}")
                return None
            
            # Create episode data with GUARANTEED media ID
            episode_data = {
                "id": f"cutam:ca:cbc:dragons-den:episode-{season_num}-{episode_num}",
                "title": title,
                "season": season_num,
                "episode": episode_num,
                "description": description,
                "duration": str(duration),
                "broadcast_date": air_date,
                "rating": rating,
                "channel": "CBC",
                "program": "Dragon's Den",
                "type": "episode",
                "poster": thumbnail,
                "thumbnail": thumbnail,
                "gem_url": gem_url,
                "cast": cast,
                "genres": ["Reality", "Business", "Entrepreneurship"],
                "cbc_media_id": str(cbc_media_id)
            }
            
            logger.info(f"\u2705 Created episode S{season_num}E{episode_num} with media ID: {cbc_media_id}")
            return episode_data
            
        except Exception as e:
            logger.error(f"\u274c Error parsing episode data from season item: {e}")
            return None
    
    def _get_episode_from_api(self, season_num: int, episode_num: int) -> Optional[Dict[str, Any]]:
        """Get episode data from CBC API"""
        try:
            # Use the CBC API endpoint format
            api_url = f"https://services.radio-canada.ca/ott/catalog/v2/gem/show/dragons-den/s{season_num:02d}e{episode_num:02d}?device=web&tier=Member"
            
            data = http_client.get_json(api_url, headers=self._get_headers_with_viewer_ip({
                'Accept': 'application/json, text/plain, */*',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate, br',
                'Referer': 'https://gem.cbc.ca/',
                'Origin': 'https://gem.cbc.ca',
                'DNT': '1',
                'Connection': 'keep-alive'
            }))
            
            if data:
                return self._parse_episode_from_api(data, season_num, episode_num)
            else:
                logger.warning(f"⚠️ API returned no data for S{season_num:02d}E{episode_num:02d}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Error getting episode S{season_num:02d}E{episode_num:02d} from API: {e}")
            return None
    
    def _parse_episode_from_api(self, data: Dict[str, Any], season_num: int, episode_num: int) -> Optional[Dict[str, Any]]:
        """Parse episode data from CBC API response"""
        try:
            # The API returns show-level data with episodes in content[0]['lineups']
            content = data.get('content', [])
            if not content or not isinstance(content, list):
                return None
            
            # Find the season in the lineups
            lineups = content[0].get('lineups', [])
            season_data = None
            for lineup in lineups:
                if lineup.get('seasonNumber') == season_num:
                    season_data = lineup
                    break
            
            if not season_data:
                return None
            
            # Find the specific episode in the season
            items = season_data.get('items', [])
            episode_info = None
            for item in items:
                if item.get('episodeNumber') == episode_num:
                    episode_info = item
                    break
            
            if not episode_info:
                return None
            
            # Get title - prefer callToActionTitle as it includes season info
            title = episode_info.get('callToActionTitle', '')
            if not title:
                title = episode_info.get('title', f"Season {season_num}, Episode {episode_num}")
            
            # Get description
            description = episode_info.get('description', '')
            if not description:
                description = "Canadian reality television series featuring entrepreneurs pitching their business ideas to a panel of venture capitalists"
            
            # Get duration from structured metadata
            duration = 2640  # Default 44 minutes
            structured_metadata = data.get('structuredMetadata', {})
            if 'duration' in structured_metadata:
                duration_str = structured_metadata['duration']
                # Parse PT0H44M format
                import re
                duration_match = re.search(r'PT(\d+)H(\d+)M', duration_str)
                if duration_match:
                    hours = int(duration_match.group(1))
                    minutes = int(duration_match.group(2))
                    duration = hours * 3600 + minutes * 60
            
            # Get air date from infoTitle or structured metadata
            air_date = episode_info.get('infoTitle', '')
            if not air_date:
                air_date = structured_metadata.get('datePublished', '')
            
            # Get rating from structured metadata
            rating = structured_metadata.get('contentRating', 'PG')
            if not rating:
                rating = 'PG'
            
            # Get thumbnail from episode images
            thumbnail = self._generate_thumbnail_url(season_num, episode_num)
            images = episode_info.get('images', {})
            if 'card' in images and 'url' in images['card']:
                thumbnail = images['card']['url']
            
            # Get cast information from structured metadata
            cast = ["Jim Treliving", "Michael Wekerle", "Michele Romanow", "Manjit Minhas", "Joe Mimran"]
            partof_series = structured_metadata.get('partofSeries', {})
            if 'actor' in partof_series:
                cast = [actor.get('name', '') for actor in partof_series['actor'] if actor.get('name')]
                if not cast:
                    cast = ["Jim Treliving", "Michael Wekerle", "Michele Romanow", "Manjit Minhas", "Joe Mimran"]
            
            # Get GEM URL
            gem_url = f"https://gem.cbc.ca/dragons-den/s{season_num:02d}e{episode_num:02d}"
            
            # Create episode data
            episode_data = {
                "id": f"cutam:ca:cbc:dragons-den:episode-{season_num}-{episode_num}",
                "title": title,
                "season": season_num,
                "episode": episode_num,
                "description": description,
                "duration": str(duration),
                "broadcast_date": air_date,
                "rating": rating,
                "channel": "CBC",
                "program": "Dragon's Den",
                "type": "episode",
                "poster": thumbnail,
                "thumbnail": thumbnail,
                "gem_url": gem_url,
                "cast": cast,
                "genres": ["Reality", "Business", "Entrepreneurship"]
            }
            
            return episode_data
            
        except Exception as e:
            logger.error(f"❌ Error parsing episode data from API: {e}")
            return None
    
    def _generate_thumbnail_url(self, season_num: int, episode_num: int) -> str:
        """Generate CBC thumbnail URL in the correct format"""
        try:
            # Format: https://images.radio-canada.ca/v1/synps-cbc/episode/perso/cbc_dragons_season_11e01_thumbnail_v01.jpg?impolicy=ott&im=Resize=680&quality=100
            season_str = f"{season_num:02d}"
            episode_str = f"{episode_num:02d}"
            
            thumbnail_url = f"https://images.radio-canada.ca/v1/synps-cbc/episode/perso/cbc_dragons_season_{season_str}e{episode_str}_thumbnail_v01.jpg?impolicy=ott&im=Resize=680&quality=100"
            
            logger.info(f"✅ Generated CBC thumbnail URL: {thumbnail_url}")
            return thumbnail_url
            
        except Exception as e:
            logger.error(f"❌ Error generating CBC thumbnail URL: {e}")
            # Fallback to a generic Dragon's Den image
            return get_logo_url("ca", "dragonsden", self.request)
    
    def _get_episode_details_from_gem(self, episode_url: str) -> Dict[str, str]:
        """Get detailed information for a specific episode from GEM"""
        try:
            response = http_client.safe_request("GET", episode_url, headers=self._get_headers_with_viewer_ip())
            if not response:
                return {}
            
            from bs4 import BeautifulSoup
            import re
            
            soup = BeautifulSoup(response.text, 'html.parser')
            details = {}
            
            # Extract description
            description_element = soup.find('p', class_='description') or soup.find('div', class_='description')
            if description_element:
                details['description'] = description_element.get_text().strip()
            
            # Extract air date
            date_element = soup.find('time') or soup.find('span', class_='date')
            if date_element:
                details['air_date'] = date_element.get_text().strip()
            
            # Extract duration
            duration_element = soup.find('span', class_='duration')
            if duration_element:
                duration_text = duration_element.get_text().strip()
                # Convert "44 min" to seconds
                duration_match = re.search(r'(\d+)\s*min', duration_text)
                if duration_match:
                    details['duration'] = str(int(duration_match.group(1)) * 60)
            
            # Extract poster
            poster_element = soup.find('img', class_='poster') or soup.find('img', {'alt': lambda x: x and 'episode' in x.lower()})
            if poster_element:
                details['poster'] = poster_element.get('src', '')
            
            return details
            
        except Exception as e:
            logger.error(f"❌ Error getting episode details from GEM: {e}")
            return {}
    
    def _extract_episodes_from_main_page(self, soup, start_counter: int) -> List[Dict[str, Any]]:
        """Extract episodes from the main Dragon's Den page if season links aren't found"""
        try:
            episodes = []
            episode_counter = start_counter
            
            # Look for episode information in the main page
            episode_elements = soup.find_all('div', class_='episode') or soup.find_all('article', class_='episode')
            
            for element in episode_elements:
                title_element = element.find('h3') or element.find('h2') or element.find('a')
                if not title_element:
                    continue
                
                title = title_element.get_text().strip()
                
                # Try to extract season and episode numbers from title
                season_match = re.search(r'season\s*(\d+)', title.lower())
                episode_match = re.search(r'episode\s*(\d+)', title.lower())
                
                season_num = int(season_match.group(1)) if season_match else 1
                episode_num = int(episode_match.group(1)) if episode_match else episode_counter
                
                episode_data = {
                    "id": f"cutam:ca:cbc:dragons-den:episode-{episode_counter}",
                    "title": title,
                    "season": season_num,
                    "episode": episode_num,
                    "description": "",
                    "duration": "2640",  # 44 minutes
                    "broadcast_date": "",
                    "rating": "PG",
                    "channel": "CBC",
                    "program": "Dragon's Den",
                    "type": "episode",
                    "poster": ""
                }
                episodes.append(episode_data)
                episode_counter += 1
            
            return episodes
            
        except Exception as e:
            logger.error(f"❌ Error extracting episodes from main page: {e}")
            return []
    
    def _get_season_episodes(self, season_url: str, season_title: str, start_counter: int) -> List[Dict[str, Any]]:
        """Get episodes for a specific season"""
        try:
            season_api_url = f"{self.catalog_api}/{season_url}"
            params = {'device': 'web'}
            
            data = http_client.get_json(season_api_url, params=params, headers=self._get_headers_with_viewer_ip())
            if not data:
                return []
            
            episodes = []
            episode_counter = start_counter
            
            if 'content' in data and len(data['content']) > 0:
                content = data['content'][0]
                
                # Get episodes from the first lineup
                for lineup in content.get('lineups', []):
                    for episode in lineup.get('items', []):
                        if episode.get('tier') == 'Standard':
                            episode_data = {
                                "id": f"cutam:ca:cbc:dragons-den:episode-{episode_counter}",
                                "title": episode.get('title', f'Episode {episode_counter}'),
                                "season": self._extract_season_number(season_title),
                                "episode": episode_counter,
                                "description": episode.get('description', ''),
                                "duration": str(episode.get('duration', 3600)),
                                "broadcast_date": episode.get('broadcastDate', ''),
                                "rating": "G",
                                "channel": "CBC",
                                "program": "Dragon's Den",
                                "type": "episode",
                                "poster": episode.get('images', {}).get('card', {}).get('url', ''),
                                "cbc_media_id": episode.get('idMedia', ''),
                                "cbc_url": episode.get('url', '')
                            }
                            episodes.append(episode_data)
                            episode_counter += 1
            
            return episodes
            
        except Exception as e:
            logger.error(f"❌ Error getting season episodes: {e}")
            return []
    
    def _extract_season_number(self, season_title: str) -> int:
        """Extract season number from season title"""
        try:
            # Look for patterns like "Season 19", "S19", etc.
            import re
            match = re.search(r'season\s*(\d+)', season_title.lower())
            if match:
                return int(match.group(1))
            
            match = re.search(r's(\d+)', season_title.lower())
            if match:
                return int(match.group(1))
            
            # Default to 1 if no season number found
            return 1
        except Exception:
            return 1
    
    def get_channel_stream_url(self, channel_id: str) -> Optional[Dict[str, Any]]:
        """Get live stream URL for a CBC channel"""
        try:
            logger.info(f"🇨🇦 Getting live stream for channel: {channel_id}")
            
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
                logger.error("Could not find live stream URL")
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
            
            logger.warning(f"⚠️ Could not find stream for channel: {channel_id}")
            return None
            
        except Exception as e:
            logger.error(f"❌ Error getting CBC live stream: {e}")
            return None
    
    def get_episode_stream_url(self, episode_id: str) -> Optional[Dict[str, Any]]:
        """Get stream URL for a CBC episode using proper CBC Gem API with caching"""
        try:
            logger.info(f"🇨🇦 Getting stream for episode: {episode_id}")
            
            # Check cache first for stream URL
            cache_key = f"cbc_stream_{episode_id}"
            cached_stream = cache.get(cache_key)
            if cached_stream:
                logger.info(f"✅ Using cached stream URL for episode: {episode_id}")
                return cached_stream
            
            # Extract media ID from episode ID
            media_id = self._extract_media_id_from_episode_id(episode_id)
            if not media_id:
                logger.error(f"❌ Could not extract media ID from episode: {episode_id}")
                return None
            
            # Get stream using CBC Gem API
            stream_info = self._get_stream_from_cbc_api(media_id)
            if stream_info:
                # Cache stream info for 30 minutes
                cache.set(cache_key, stream_info, ttl=1800)
                return stream_info
            
            logger.warning(f"⚠️ No stream found for episode: {episode_id}")
            return None
            
        except Exception as e:
            logger.error(f"❌ Error getting CBC episode stream: {e}")
            return None
    
    def _get_real_episode_stream(self, episode_id: str) -> Optional[Dict[str, Any]]:
        """Get real stream URL from GEM website"""
        try:
            logger.info(f"🔍 Getting real stream for episode: {episode_id}")
            
            # Get GEM URL for the episode
            gem_url = self._get_episode_gem_url(episode_id)
            if not gem_url:
                logger.warning(f"⚠️ No GEM URL found for episode: {episode_id}")
                return None
            
            # Extract stream URL from GEM page
            stream_url = self._extract_stream_from_gem(gem_url)
            if not stream_url:
                logger.warning(f"⚠️ No stream URL found in GEM page: {gem_url}")
                return None
            
            # Determine manifest type
            manifest_type = 'hls'  # Default for GEM
            if '.m3u8' in stream_url:
                manifest_type = 'hls'
            elif '.mpd' in stream_url:
                manifest_type = 'dash'
            elif '.ism' in stream_url:
                manifest_type = 'ism'
            
            # Prepare headers
            headers = {
                'User-Agent': self._get_headers_with_viewer_ip().get('User-Agent'),
                'Referer': 'https://gem.cbc.ca/',
                'Origin': 'https://gem.cbc.ca'
            }
            
            stream_info = {
                "url": stream_url,
                "manifest_type": manifest_type,
                "title": "Dragon's Den Episode Stream",
                "headers": headers
            }
            
            logger.info(f"✅ Got real stream from GEM: {manifest_type.upper()}")
            return stream_info
            
        except Exception as e:
            logger.error(f"❌ Error getting real episode stream: {e}")
            return None
    
    def _get_episode_gem_url(self, episode_id: str) -> Optional[str]:
        """Get GEM URL for an episode"""
        try:
            # Get episodes to find the GEM URL
            episodes = self.get_episodes("cutam:ca:cbc:dragons-den")
            
            for episode in episodes:
                if episode['id'] == episode_id and 'gem_url' in episode:
                    return episode['gem_url']
            
            logger.warning(f"⚠️ No GEM URL found for episode: {episode_id}")
            return None
            
        except Exception as e:
            logger.error(f"❌ Error getting episode GEM URL: {e}")
            return None
    
    def _extract_stream_from_gem(self, gem_url: str) -> Optional[str]:
        """Extract actual stream URL from GEM page"""
        try:
            response = http_client.safe_request("GET", gem_url, headers=self._get_headers_with_viewer_ip({
                'Referer': 'https://gem.cbc.ca/'
            }))
            if not response:
                return None
            
            import re
            
            # Look for various stream URL patterns in the page
            stream_patterns = [
                r'"url":\s*"(https?://[^"]*\.m3u8[^"]*)"',
                r'"src":\s*"(https?://[^"]*\.m3u8[^"]*)"',
                r'"streamUrl":\s*"(https?://[^"]*\.m3u8[^"]*)"',
                r'"manifestUrl":\s*"(https?://[^"]*\.m3u8[^"]*)"',
                r'"(https?://[^"]*\.m3u8[^"]*)"',
                r'"url":\s*"(https?://[^"]*\.mpd[^"]*)"',
                r'"src":\s*"(https?://[^"]*\.mpd[^"]*)"',
                r'"streamUrl":\s*"(https?://[^"]*\.mpd[^"]*)"',
                r'"manifestUrl":\s*"(https?://[^"]*\.mpd[^"]*)"',
                r'"(https?://[^"]*\.mpd[^"]*)"'
            ]
            
            for pattern in stream_patterns:
                matches = re.findall(pattern, response.text)
                for match in matches:
                    # Filter out non-stream URLs
                    if any(ext in match for ext in ['.m3u8', '.mpd', '.ism']):
                        logger.info(f"✅ Found stream URL: {match}")
                        return match
            
            # If no direct stream URLs found, look for API endpoints
            api_patterns = [
                r'"apiUrl":\s*"(https?://[^"]*)"',
                r'"endpoint":\s*"(https?://[^"]*)"',
                r'"serviceUrl":\s*"(https?://[^"]*)"'
            ]
            
            for pattern in api_patterns:
                matches = re.findall(pattern, response.text)
                for match in matches:
                    if 'api' in match.lower() or 'stream' in match.lower():
                        logger.info(f"✅ Found API endpoint: {match}")
                        # Try to get stream from API endpoint
                        api_stream = self._get_stream_from_api(match)
                        if api_stream:
                            return api_stream
            
            logger.warning("⚠️ No stream URL found in GEM page")
            return None
            
        except Exception as e:
            logger.error(f"❌ Error extracting stream from GEM: {e}")
            return None
    
    def _get_stream_from_api(self, api_url: str) -> Optional[str]:
        """Try to get stream URL from an API endpoint"""
        try:
            data = http_client.get_json(api_url, headers=self._get_headers_with_viewer_ip({
                'Referer': 'https://gem.cbc.ca/'
            }))
            if not data:
                return None
            
            # Look for stream URL in API response
            if 'url' in data:
                return data['url']
            elif 'streamUrl' in data:
                return data['streamUrl']
            elif 'manifestUrl' in data:
                return data['manifestUrl']
            
            return None
            
        except Exception as e:
            logger.error(f"❌ Error getting stream from API: {e}")
            return None
    
    def _extract_media_id_from_episode_id(self, episode_id: str) -> Optional[str]:
        """Extract CBC media ID from episode ID with optimized single lookup"""
        try:
            # Get episodes once and reuse
            episodes = self.get_episodes("cutam:ca:cbc:dragons-den")
            
            # Parse episode info from ID like: cutam:ca:cbc:dragons-den:episode-19-1
            if "dragons-den:episode-" in episode_id:
                parts = episode_id.split("-")
                if len(parts) >= 3:
                    try:
                        season_num = int(parts[-2])
                        episode_num = int(parts[-1])
                        # Look up episodes to find matching media id
                        for ep in episodes:
                            if (
                                ep.get('season') == season_num and
                                ep.get('episode') == episode_num and
                                'cbc_media_id' in ep and ep.get('cbc_media_id')
                            ):
                                media_id = str(ep['cbc_media_id'])
                                logger.info(f"✅ Found CBC media ID for S{season_num}E{episode_num}: {media_id}")
                                return media_id
                    except ValueError:
                        pass
            
            # Fallback: direct match by full id
            for ep in episodes:
                if ep.get('id') == episode_id and ep.get('cbc_media_id'):
                    media_id = str(ep['cbc_media_id'])
                    logger.info(f"✅ Found CBC media ID by direct match: {media_id}")
                    return media_id
            
            logger.warning(f"⚠️ No media ID found for episode: {episode_id}")
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
            viewer_ip = get_client_ip()
            final_headers = merge_ip_headers(headers, viewer_ip)
            
            if viewer_ip:
                logger.info(f"🌍 CBC Media API request using viewer IP: {viewer_ip}")
                logger.info(f"🌍 Media API IP headers: X-Forwarded-For={viewer_ip}, X-Real-IP={viewer_ip}, CF-Connecting-IP={viewer_ip}")
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
            logger.info(f"🔗 Full stream URL: {stream_url}")
            
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
                "title": "CBC Gem Dragon's Den"
            }
        except Exception as e:
            logger.error(f"❌ Error getting stream from CBC API: {e}")
            try:
                import traceback
                logger.error(traceback.format_exc())
            except Exception:
                pass
            return None

    def debug_episode_stream(self, episode_id: str) -> Dict[str, Any]:
        """Debug method to trace the entire stream resolution process"""
        debug_info: Dict[str, Any] = {"episode_id": episode_id, "steps": [], "final_result": None}
        try:
            debug_info["steps"].append("1. Extracting media ID...")
            media_id = self._extract_media_id_from_episode_id(episode_id)
            debug_info["media_id"] = media_id
            debug_info["steps"].append(f"   Media ID: {media_id}")
            if not media_id:
                debug_info["steps"].append("   ❌ FAILED: No media ID found")
                debug_info["final_result"] = "FAILED"
                return debug_info
            
            debug_info["steps"].append("2. Checking authentication...")
            is_auth = self.authenticator.is_authenticated()
            debug_info["authenticated"] = is_auth
            debug_info["steps"].append(f"   Authenticated: {is_auth}")
            if not is_auth:
                debug_info["steps"].append("   ❌ FAILED: Not authenticated")
                debug_info["final_result"] = "FAILED"
                return debug_info
            
            debug_info["steps"].append("3. Getting claims token...")
            claims_token = self.authenticator.get_claims_token()
            debug_info["has_claims_token"] = bool(claims_token)
            debug_info["steps"].append(f"   Claims token: {claims_token[:20] if claims_token else 'None'}...")
            if not claims_token:
                debug_info["steps"].append("   ❌ FAILED: No claims token")
                debug_info["final_result"] = "FAILED"
                return debug_info
            
            debug_info["steps"].append("4. Calling CBC stream API...")
            stream_info = self._get_stream_from_cbc_api(media_id)
            debug_info["stream_info"] = stream_info
            if stream_info:
                debug_info["steps"].append("   ✅ SUCCESS: Got stream info")
                debug_info["final_result"] = "SUCCESS"
            else:
                debug_info["steps"].append("   ❌ FAILED: No stream info returned")
                debug_info["final_result"] = "FAILED"
            return debug_info
        except Exception as e:
            debug_info["steps"].append(f"   ❌ EXCEPTION: {e}")
            debug_info["final_result"] = "EXCEPTION"
            return debug_info
    
    def clear_cache(self, cache_type: str = "all") -> None:
        """Clear specific cache entries or all cache"""
        try:
            if cache_type == "all":
                cache.clear()
                logger.info("✅ Cleared all CBC cache")
            elif cache_type == "episodes":
                # Clear episode-related caches
                cache.delete("cbc_episodes_cutam:ca:cbc:dragons-den")
                cache.delete("cbc_dragons_den_all_episodes")
                for season in range(10, 21):
                    cache.delete(f"cbc_season_{season}_episodes")
                logger.info("✅ Cleared CBC episode caches")
            elif cache_type == "programs":
                cache.delete("cbc_programs")
                cache.delete("cbc_shows")
                cache.delete("cbc_dragons_den_search")
                logger.info("✅ Cleared CBC program caches")
            elif cache_type == "streams":
                # Note: This would need to be more sophisticated in a real implementation
                # For now, we'll just clear the auth cache
                cache.delete("cbc_auth_status")
                logger.info("✅ Cleared CBC stream caches")
            else:
                logger.warning(f"⚠️ Unknown cache type: {cache_type}")
        except Exception as e:
            logger.error(f"❌ Error clearing cache: {e}")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics for monitoring"""
        try:
            # This is a simple implementation - in production you'd want more detailed stats
            return {
                "cache_type": "InMemoryCache",
                "status": "active",
                "note": "Cache statistics not available in simple implementation"
            }
        except Exception as e:
            logger.error(f"❌ Error getting cache stats: {e}")
            return {"error": str(e)}
    
    def force_reauthentication(self) -> bool:
        """Force re-authentication with CBC"""
        try:
            logger.info("🔄 Forcing CBC re-authentication...")
            
            # Clear all cached authentication data
            cache.delete("cbc_auth_status")
            cache.delete("cbc_refresh_token")
            cache.delete("cbc_access_token")
            cache.delete("cbc_claims_token")
            
            # Clear authenticator tokens
            self.authenticator.logout()
            
            # Re-authenticate
            self._authenticate_if_needed()
            
            # Verify authentication
            if self.authenticator.is_authenticated():
                logger.info("✅ Re-authentication successful")
                return True
            else:
                logger.error("❌ Re-authentication failed")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error during forced re-authentication: {e}")
            return False