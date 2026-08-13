import logging
import re
from typing import List, Dict, Optional, Any
from fastapi import Request
from app.providers.base_provider import BaseProvider, safe_provider_call
from app.auth.cbc_auth import CBCAuthenticator
from app.utils.cache import cache
from app.utils.cache_keys import CacheKeys, CacheTTL
from app.utils.client_ip import get_client_ip
from app.utils.programs_loader import get_programs_for_provider

logger = logging.getLogger(__name__)

# Auth-status cache TTLs (seconds)
_AUTH_SUCCESS_TTL = 3600   # 1 hour — re-check auth after token likely expired
_AUTH_FAILURE_TTL = 300    # 5 minutes — retry sooner after a failure


class CBCProvider(BaseProvider):
    # BaseProvider class attributes
    provider_name = "cbc"
    base_url = "https://gem.cbc.ca"
    country = "ca"
    credentials_key = "cbcgem"  # legacy section name in users' credentials files
    
    # Metadata
    display_name = "CBC"
    id_prefix = "cutam:ca:cbc"
    episode_marker = "episode:"
    catalog_id = "ca-cbc-dragons-den"
    supports_live = False
    default_channel = "dragonsden"
    default_rating = "G"

    
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

        # Load shows from external programs.json (consumed by the BaseProvider
        # get_programs template)
        self.shows = get_programs_for_provider('cbc')

    
    def _get_headers_with_viewer_ip(self, additional_headers: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        """Build headers with viewer IP forwarding for geo-sensitive requests."""
        return self._build_ip_headers({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            **(additional_headers or {}),
        })
    
    _AUTH_CACHE_KEY = CacheKeys.provider_resource("cbc", "auth_status")

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

            cbc_creds = self.credentials or {}

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
            logger.error("❌ [CBC] Error during authentication: %s", e)
            self._store_auth_result(False)
    
    # get_programs comes from the BaseProvider template; _get_show_api_metadata
    # below supplies the artwork, all of it read straight out of the show payload.
    _SHOW_IMAGES = {
        "logo": ("logo",),
        "background": ("background",),
        "fanart": ("background",),
    }

    @safe_provider_call(default={})
    def _get_show_api_metadata(self, show_id: str, show_info: Dict[str, Any]) -> Dict[str, Any]:
        """Fetch the show's artwork from the CBC catalog API."""
        data = self.api_client.get(
            f"{self.catalog_api}/show/{show_id}/s01e01?device=web&tier=Member",
            headers=self._get_headers_with_viewer_ip({
                'Accept': 'application/json, text/plain, */*',
                'Referer': 'https://gem.cbc.ca/',
                'Origin': 'https://gem.cbc.ca',
            }),
        )
        images = (data or {}).get('images') or {}
        candidates = {
            field: [(images.get(k) or {}).get('url') for k in keys]
            for field, keys in self._SHOW_IMAGES.items()
        }
        # No poster is published: derive it from the background URL, falling back
        # to the page's og:image. Skipped entirely when programs.json pins one.
        if not show_info.get('poster'):
            candidates['poster'] = [
                self._first_existing(self._poster_candidates(data)),
                ((data or {}).get('htmlMeta') or {}).get('og:image'),
            ]
        return self._pick_artwork(candidates, show_info)

    def _poster_candidates(self, data: Dict[str, Any]) -> List[str]:
        """Poster URLs derived from the background URL, most specific first.

        Two shapes exist, and which one a show uses is not predictable:
        ``season/perso/<stem>_s<latest>_ott_poster_v01.jpg`` (dragons-den) and
        ``show/perso/<stem>_ott_poster_v01.jpg`` (schitts-creek). Together they
        cover 12 of 16 shows sampled; the caller HEAD-checks them in order.

        ponytail: v01 only. The poster's version is independent of the
        background's (son-of-a-critch is v02, allegiance v03), so chasing it
        would mean a request per guess — og:image covers those shows instead.
        """
        background = ((data.get('images') or {}).get('background') or {}).get('url')
        if not background:
            return []
        seasons = self._season_numbers(data)
        candidates = []
        if seasons:
            candidates.append(re.sub(
                r'_ott_background_v\d+', f'_s{max(seasons)}_ott_poster_v01',
                background.replace('/show/', '/season/'),
            ))
        candidates.append(re.sub(r'_ott_background_v\d+', '_ott_poster_v01', background))
        return candidates

    def _first_existing(self, urls: List[str]) -> Optional[str]:
        """First URL the CDN actually serves, or None. Each result cached."""
        for url in urls:
            cache_key = CacheKeys.provider_resource(self.provider_name, f"url_ok:{url}")
            exists = cache.get(cache_key)
            if exists is None:
                try:
                    exists = self.session.head(url, timeout=10, allow_redirects=True).status_code == 200
                except Exception as exc:
                    logger.debug("⚠️ [CBC] Poster check failed for %s: %s", url, exc)
                    exists = False
                cache.set(cache_key, exists, ttl=CacheTTL.PROGRAMS)
            if exists:
                return url
        return None

    @staticmethod
    def _season_numbers(data: Dict[str, Any]) -> List[int]:
        """Season numbers CBC Gem offers for a show, ascending.

        One show request returns every season in ``lineups`` — which seasons to
        scrape for episodes and which season the poster belongs to both come
        from here, so the payload is only parsed one way.
        """
        lineups = ((data or {}).get('content') or [{}])[0].get('lineups') or []
        return sorted({
            lineup.get('seasonNumber') for lineup in lineups
            if isinstance(lineup.get('seasonNumber'), int)
        })


    def get_episodes(self, series_id: str) -> List[Dict[str, Any]]:
        """Get episodes for any CBC series."""
        try:
            logger.info("🔍 [CBC] Getting episodes for series: %s", series_id)

            # NOTE: Caching is handled by the meta router (CacheKeys.episodes).

            # Extract show_slug from series_id (format: cutam:ca:cbc:show-slug)
            show_slug = self._extract_slug(series_id)
            if not show_slug:
                logger.warning("⚠️ [CBC] Invalid series ID format: %s", series_id)
                return []

            # Get show info from programs.json for metadata
            cbc_shows = get_programs_for_provider('cbc')
            show_info = cbc_shows.get(show_slug, {})
            show_name = show_info.get('name', show_slug.replace('-', ' ').title())

            # Get episodes from CBC API (internally cached per show_slug)
            episodes = self._get_show_episodes(show_slug, show_name)
            if episodes:
                logger.info("✅ CBC returned %d episodes for %s", len(episodes), show_name)
                return episodes

            logger.warning("⚠️ [CBC] No episodes found for: %s", show_slug)
            return []

        except Exception as e:
            logger.error("❌ [CBC] Error getting CBC episodes: %s", e)
            return []
    
    def _get_show_episodes(self, show_slug: str, show_name: str) -> List[Dict[str, Any]]:
        """Get ALL episodes for a CBC show with single optimized API call"""
        try:
            logger.info("🔍 [CBC] Fetching %s episodes from CBC API...", show_name)

            # Check cache first — same key family the meta router uses, so the
            # episode list is cached exactly once with one TTL (previously this
            # was double-cached under a private key with a conflicting TTL).
            cache_key = CacheKeys.episodes(f"{self.id_prefix}:{show_slug}")
            cached_episodes = cache.get(cache_key)
            if cached_episodes:
                logger.info("✅ Using cached %s episodes: %d episodes", show_name, len(cached_episodes))
                return cached_episodes
            
            episodes = []
            
            # Single API call - s01e01 returns ALL seasons in lineups array
            api_url = f"{self.catalog_api}/show/{show_slug}/s01e01?device=web&tier=Member"
            
            logger.debug("🔍 [CBC] API request: %s", api_url)
            data = self.api_client.get(api_url, headers=self._get_headers_with_viewer_ip({
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
                seasons = self._season_numbers(data)
                logger.info("✅ [CBC] %s: scraping seasons %s", show_name,
                            ", ".join(str(s) for s in seasons) or "none")

                for lineup in lineups:
                    season_num = lineup.get('seasonNumber')
                    if season_num not in seasons:
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
                        logger.debug("🔍 [CBC] Season %s: %s episodes", season_num, season_episode_count)
            else:
                logger.warning("⚠️ [CBC] API returned no content for %s", show_slug)
            
            # Sort by season and episode
            episodes.sort(key=lambda x: (x['season'], x['episode']))
            
            if episodes:
                cache.set(cache_key, episodes, ttl=CacheTTL.EPISODES)
                logger.info("✅ [CBC] Found %d total episodes for %s", len(episodes), show_name)
            
            return episodes
            
        except Exception as e:
            logger.error("❌ [CBC] Error fetching %s episodes: %s", show_name, e)
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
                logger.warning("⚠️ [CBC] No media ID for S%sE%s", season_num, episode_num)
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
                "cast": cast,
                "cbc_media_id": str(cbc_media_id)
            }
            
            if released:
                episode_data["released"] = released
            
            logger.debug("🔍 [CBC] Created episode S%sE%s", season_num, episode_num)
            return episode_data
            
        except Exception as e:
            logger.error("❌ [CBC] Error parsing episode data: %s", e)
            return None
    

    
    def get_episode_stream_url(self, episode_id: str) -> Optional[List[Dict[str, Any]]]:
        """Get stream URL for a CBC episode using proper CBC Gem API with caching"""
        try:
            logger.info("🔍 [CBC] Getting stream for episode: %s", episode_id)
            
            # Lazy authentication - only authenticate when a stream is actually requested
            self._authenticate_if_needed()
            
            # Check cache first for stream URL
            cache_key = CacheKeys.stream(episode_id)
            cached_stream = cache.get(cache_key)
            if cached_stream:
                logger.info("✅ [CBC] Using cached stream URL for episode: %s", episode_id)
                return cached_stream
            
            # Extract media ID from episode ID
            media_id = self._extract_media_id_from_episode_id(episode_id)
            if not media_id:
                logger.error("❌ [CBC] Could not extract media ID from episode: %s", episode_id)
                return None
            
            # Get stream using CBC Gem API
            stream_info = self._get_stream_from_cbc_api(media_id)
            if stream_info:
                cache.set(cache_key, stream_info, ttl=CacheTTL.STREAM)
                return stream_info
            
            logger.warning("⚠️ [CBC] No stream found for episode: %s", episode_id)
            return None
            
        except Exception as e:
            logger.error("❌ [CBC] Error getting CBC episode stream: %s", e)
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
                logger.warning("⚠️ [CBC] Invalid episode ID format: %s", episode_id)
                return None
            
            # Get episodes for this show
            episodes = self.get_episodes(series_id)
            
            # Parse season/episode from ID: ...episode:S:E
            if len(parts) >= 7:
                try:
                    season_num = int(parts[-2])
                    episode_num = int(parts[-1])
                    for ep in episodes:
                        if (ep.get('season') == season_num and 
                            ep.get('episode') == episode_num and 
                            ep.get('cbc_media_id')):
                            media_id = str(ep['cbc_media_id'])
                            logger.debug("🔍 [CBC] Found media ID for S%sE%s: %s", season_num, episode_num, media_id)
                            return media_id
                except ValueError:
                    pass
            
            # Fallback: direct ID match
            for ep in episodes:
                if ep.get('id') == episode_id and ep.get('cbc_media_id'):
                    return str(ep['cbc_media_id'])
            
            logger.warning("⚠️ [CBC] No media ID found for: %s", episode_id)
            return None
            
        except Exception as e:
            logger.error("❌ Error extracting media ID: %s", e)
            return None
    
    def _get_stream_from_cbc_api(self, media_id: str) -> Optional[List[Dict[str, Any]]]:
        """Get stream URL from CBC Gem API with authentication and robust error handling.

        Retries once with a refreshed claims token when the API reports an
        invalid/expired token (errorCode 35).
        """
        try:
            logger.info("🔍 Getting stream from CBC API for media: %s", media_id)

            # Ensure we are authenticated
            if not self.authenticator.is_authenticated():
                logger.error("❌ Not authenticated with CBC Gem")
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

            viewer_ip = get_client_ip()
            if viewer_ip:
                logger.info("🌍 CBC Media API request using viewer IP: %s", viewer_ip)
            else:
                logger.warning("⚠️ CBC Media API request using server IP (no viewer IP available)")

            data = None
            headers: Dict[str, str] = {}
            for attempt in range(2):
                # Get authenticated headers (ensures claims token)
                headers = self.authenticator.get_authenticated_headers()
                claims_token = headers.get('x-claims-token')
                if not claims_token:
                    logger.error("❌ Missing claims token for CBC content")
                    return None

                # Merge viewer IP headers with authenticated headers
                data = self.api_client.get(
                    self.media_api,
                    params=params,
                    headers=self._merge_ip_headers(headers)
                )
                if not data:
                    return None

                error_code = data.get('errorCode', 0)
                if error_code == 0:
                    break
                if error_code == 1:
                    logger.error("❌ Content is geo-restricted to Canada")
                    return None
                if error_code == 35 and attempt == 0:
                    logger.error("❌ Claims token invalid/expired; refreshing once")
                    self.authenticator.claims_token = None
                    continue
                logger.error("❌ CBC API error %s: %s", error_code, data.get('message', 'Unknown error'))
                return None
            else:
                return None

            stream_url = data.get('url')
            if not stream_url:
                logger.error("❌ No stream URL in CBC API response")
                logger.error(str(data)[:500])
                return None

            manifest_type = self._detect_manifest_type(stream_url)

            logger.info("✅ Got CBC stream: %s", manifest_type.upper())
            logger.info("🔗 [CBC] Full stream URL: %s", stream_url)

            # Only return safe playback headers
            playback_headers = {
                'User-Agent': headers.get('User-Agent', self._get_headers_with_viewer_ip().get('User-Agent', '')),
                'Referer': headers.get('Referer', 'https://gem.cbc.ca/'),
                'Origin': headers.get('Origin', 'https://gem.cbc.ca')
            }

            return [{"url": stream_url, "manifest_type": manifest_type, "headers": playback_headers, "title": "CBC Gem Stream"}]
        except Exception:
            logger.exception("❌ Error getting stream from CBC API")
            return None

