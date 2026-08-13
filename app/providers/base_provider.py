import functools
import logging
import os
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Dict, List, Optional, TypeVar
from urllib.parse import quote, urlencode

from app.utils.credentials import get_provider_credentials
from app.utils.api_client import ProviderAPIClient
from app.utils.base_url import get_logo_url
from app.utils.show_meta import DEFAULT_RATING, build_show_dict
from app.utils.user_agent import get_random_windows_ua
from app.utils.proxy_config import get_proxy_config
from app.utils.client_ip import make_ip_headers, merge_ip_headers as _merge_ip_util
from app.utils.mediaflow import build_mediaflow_url
from app.schemas.type_defs import EpisodeInfo, LiveChannelInfo, ShowInfo, StreamInfo

logger = logging.getLogger(__name__)

_T = TypeVar("_T")
_PARALLEL_FETCH_WORKERS = 5   # max threads for parallel metadata / image fetches


def safe_provider_call(default=None):
    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(self, *a, **k):
            try:
                return fn(self, *a, **k)
            except Exception as e:
                logger.error("%s %s failed: %s", self.log_prefix, fn.__name__, e)
                return default
        return wrapper
    return decorator


class LiveProviderMixin:
    """Mixin for providers that support live channel streaming.

    Inherit alongside BaseProvider to signal live support.  Consumers can use
    ``isinstance(provider, LiveProviderMixin)`` instead of reading the
    ``supports_live`` attribute.  The mixin sets ``supports_live = True`` so
    existing registry code that reads the class attribute still works.
    """
    supports_live: bool = True


class BaseProvider(ABC):
    """
    Abstract base class for all content providers.
    
    Provides common functionality:
    - Credential loading
    - Session management with User-Agent rotation
    - API client with retry logic
    - MediaFlow configuration
    """
    
    # Subclasses should override these
    provider_name: str = "base"
    base_url: str = ""
    country: str = ""
    # Section name in the credentials document; defaults to provider_name.
    # Override only for backward compatibility with existing user files
    # (e.g. CBC reads the legacy "cbcgem" section).
    credentials_key: str = ""
    
    # Metadata Configuration (Subclasses must override)
    display_name: str = "Unknown Provider"
    id_prefix: str = ""
    episode_marker: str = "episode:"
    catalog_id: str = ""
    supports_live: bool = False
    default_channel: str = ""
    default_rating: str = DEFAULT_RATING
    # Accept-Language sent with stream requests; override per provider/region.
    default_locale: str = "fr-FR,fr;q=0.9,en;q=0.8"
    # Geo-proxy key used by _get_geo_proxy_url / _fetch_with_proxy_fallback.
    geo_proxy_key: str = "fr_default"
    
    def __init__(self, request=None):
        """
        Initialize base provider.
        
        Args:
            request: Optional FastAPI Request object for base URL determination
        """
        self.request = request
        self.credentials = get_provider_credentials(self.credentials_key or self.provider_name)

        # Initialize API client (has retry adapters + connection pooling configured)
        self.api_client = ProviderAPIClient(
            provider_name=self.provider_name,
            timeout=15,
            max_retries=3
        )

        # Expose the API client's session as self.session so any provider code that
        # uses self.session directly benefits from the same retry adapters and pool.
        self.session = self.api_client.session
        self.session.headers.update({
            'User-Agent': get_random_windows_ua()
        })

        # Track authentication state
        self._authenticated = False

        # Initialize proxy configuration
        self.proxy_config = get_proxy_config()

        # Initialize MediaFlow
        self._init_mediaflow()

    @property
    def needs_ip_forwarding(self) -> bool:
        """
        Whether this provider requires client IP forwarding headers.
        Defaults to False. Override in subclasses if True.
        """
        return False
        
    @property
    def log_prefix(self) -> str:
        return f"[{self.display_name}]"

    def close(self) -> None:
        """Release the API client session and its connection pool."""
        self.api_client.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False

    def _parallel_map(self, fn: Callable[..., _T], items) -> List[_T]:
        """Apply *fn* to every item in *items* using a thread pool.

        Wraps the repeated ``ThreadPoolExecutor`` boilerplate so subclasses can
        write ``self._parallel_map(fetch_fn, items)`` instead of the 3-line
        executor pattern.
        """
        with ThreadPoolExecutor(max_workers=_PARALLEL_FETCH_WORKERS) as executor:
            return list(executor.map(fn, items))

    def _init_mediaflow(self):
        """Load and log MediaFlow proxy configuration."""
        self.mediaflow_url = os.getenv('MEDIAFLOW_PROXY_URL')
        self.mediaflow_password = os.getenv('MEDIAFLOW_API_PASSWORD')

        if not self.mediaflow_url or not self.mediaflow_password:
            creds = get_provider_credentials('mediaflow')
            self.mediaflow_url = self.mediaflow_url or creds.get('url')
            self.mediaflow_password = self.mediaflow_password or creds.get('password')

        if self.mediaflow_url and self.mediaflow_password:
            logger.debug("✅ %s MediaFlow configured", self.log_prefix)
        else:
            logger.debug("⚠️ %s MediaFlow not configured", self.log_prefix)

    @staticmethod
    def _detect_manifest_type(url: str) -> str:
        """Detect manifest type from URL. Returns 'hls', 'mpd', or 'ism'."""
        lower = (url or '').lower()
        if '.m3u8' in lower or 'hls' in lower:
            return 'hls'
        if '.mpd' in lower or 'dash' in lower:
            return 'mpd'
        if '.ism' in lower:
            return 'ism'
        return 'hls'

    def _extract_slug(self, composite_id: str) -> str:
        """Extract trailing slug from 'cutam:country:provider:slug'."""
        return composite_id.split(":")[-1]

    def _extract_after_marker(self, composite_id: str, marker: str = None) -> str:
        """Extract portion after episode_marker."""
        m = marker or getattr(self, 'episode_marker', None)
        if not m:
            return composite_id
        return composite_id.split(m)[-1] if m in composite_id else composite_id
    
    def _get_geo_proxy_url(self, destination_url: str, proxy_key: str = None) -> Optional[str]:
        """Get proxied URL for geo-restricted content (defaults to geo_proxy_key)."""
        key = proxy_key or self.geo_proxy_key
        proxy_base = self.proxy_config.get_proxy(key)
        if proxy_base:
            return proxy_base + quote(destination_url, safe='')
        logger.debug("⚠️ %s Proxy '%s' not configured", self.log_prefix, key)
        return None

    def _fetch_with_proxy_fallback(
        self, url: str, params: Dict = None,
        headers: Dict = None, proxy_key: str = None,
        validate: Callable[[Dict], bool] = None,
    ) -> Optional[Dict]:
        """Try geo-proxy first, fallback to direct call on failure."""
        dest_with_params = url + ("?" + urlencode(params) if params else "")
        proxied_url = self._get_geo_proxy_url(dest_with_params, proxy_key)

        if proxied_url:
            data = self.api_client.get(proxied_url, headers=headers, max_retries=1)
            if data:
                if validate is None or validate(data):
                    logger.debug("✅ %s Proxy success", self.log_prefix)
                    return data
                logger.debug("⚠️ %s Proxy response failed validation", self.log_prefix)

        logger.debug("⚠️ %s Trying direct", self.log_prefix)
        return self.api_client.get(url, params=params, headers=headers, max_retries=2)
    
    def _build_mediaflow_proxied_url(
        self, video_url: str, manifest_type: str,
        extra_headers: Optional[Dict] = None,
        license_url: str = None, license_headers: Dict = None,
        extra_params: Optional[Dict] = None,
    ) -> Optional[str]:
        """Build a MediaFlow-proxied URL. Returns None if MediaFlow is not configured.

        ``extra_params`` goes straight into the query string — used for the
        ``key_id``/``key`` pair MediaFlow needs to decrypt Widevine DASH.
        """
        if not self.mediaflow_url or not self.mediaflow_password:
            return None
        endpoint = '/proxy/hls/manifest.m3u8' if manifest_type == 'hls' else '/proxy/mpd/manifest.m3u8'
        headers = {'user-agent': get_random_windows_ua(), 'referer': self.base_url, 'origin': self.base_url}
        if extra_headers:
            headers.update(extra_headers)
        return build_mediaflow_url(
            base_url=self.mediaflow_url, password=self.mediaflow_password,
            destination_url=video_url, endpoint=endpoint, request_headers=headers,
            license_url=license_url, license_headers=license_headers,
            extra_params=extra_params,
        )

    def _build_stream_headers(self, auth_token: str = None, **extra) -> Dict:
        """Build standard headers for stream requests.

        Subclasses can pass additional headers via ``**extra`` without
        needing to duplicate the base set.
        """
        headers = {
            "User-Agent": get_random_windows_ua(),
            "referer": self.base_url,
            "origin": self.base_url,
            "accept-language": self.default_locale,
            "accept": "application/json, text/plain, */*",
        }
        if auth_token:
            headers["authorization"] = f"Bearer {auth_token}"
        if extra:
            headers.update(extra)
        return headers
    
    def _build_ip_headers(self, extra: Optional[Dict] = None) -> Dict:
        """Return IP-forwarding headers for the current request context."""
        headers = make_ip_headers()
        if extra:
            headers.update(extra)
        return headers

    def _merge_ip_headers(self, headers: Dict, extra: Optional[Dict] = None) -> Dict:
        """Merge IP-forwarding headers into an existing headers dict."""
        result = _merge_ip_util(headers)
        if extra:
            result.update(extra)
        return result

    def _sort_episodes_chronologically(self, episodes: List[Dict]) -> List[Dict]:
        """Sort episodes by date (oldest first) and re-number them."""
        episodes.sort(key=lambda ep: ep.get('released', '') or ep.get('broadcast_date', '') or '')
        for i, ep in enumerate(episodes):
            ep['episode'] = i + 1
            ep['episode_number'] = i + 1
        return episodes
    
    def _build_show_metadata(self, slug: str, info: Dict, extra: Dict = None) -> ShowInfo:
        """Build a Stremio-compatible series dict from programs.json data.

        Providers may pass *extra* to override or extend any field (e.g. fanart
        fetched from a live API).  Non-``None`` keys in *extra* win over the
        base values.
        """
        fallback_logo = get_logo_url(self.country, self.default_channel, self.request) \
            if self.country and self.default_channel else None
        result = build_show_dict(
            self.id_prefix, slug, info,
            fallback_logo=fallback_logo,
            default_rating=self.default_rating,
        )
        if extra:
            result.update({k: v for k, v in extra.items() if v is not None})
        return result

    def _create_fallback_episode(self, show_id: str) -> EpisodeInfo:
        """Return a placeholder episode dict when the live episode API fails."""
        shows = getattr(self, 'shows', {})
        show_info = shows.get(show_id, {})
        show_name = show_info.get('name', show_id.replace('-', ' ').title())
        return {
            "id": f"{self.id_prefix}:episode:{show_id}_fallback",
            "type": "episode",
            "title": f"Latest {show_name}",
            "description": f"Latest episode of {show_name}",
            "poster": show_info.get('logo'),
            "fanart": show_info.get('logo'),
            "episode": 1,
            "season": 1,
            "note": "Fallback episode - API unavailable",
        }

    def _pick_artwork(self, candidates: Dict[str, List[Optional[str]]], show_info: Dict) -> Dict[str, str]:
        """Resolve artwork fields from ordered candidate URLs.

        The precedence rule shared by every self-fetching provider lives here:
        a URL pinned in programs.json wins outright, otherwise the first
        non-empty candidate is used, and a field with nothing to offer is left
        out so ``build_show_dict``'s own fallback still applies.  Providers only
        supply the candidates, since extracting them is API-specific.
        """
        picked = {}
        for field, urls in candidates.items():
            if show_info.get(field):
                continue
            url = next((u for u in urls if u), None)
            if url:
                picked[field] = url
        return picked

    def enhance_series_meta(self, series_meta: Dict, show_id: str) -> Dict:
        """Enrich series metadata with the provider's API artwork.

        The /meta route builds the detail page from programs.json alone, so
        without this a show that pins no URL falls back to the channel logo.
        Providers needing a different merge (FranceTV) override this.
        """
        show_info = getattr(self, 'shows', {}).get(show_id) or {}
        for field, url in (self._get_show_api_metadata(show_id, show_info) or {}).items():
            if url and isinstance(url, str):
                series_meta[field] = url
        return series_meta

    # ------------------------------------------------------------------
    # Template-method skeleton for episode listing
    # Providers that have a simple fetch→parse→sort flow should implement
    # _fetch_episodes_raw and _parse_episode instead of overriding get_episodes.
    # Providers with complex flows (auth, multi-step lookups) may override
    # get_episodes directly.
    # ------------------------------------------------------------------

    def _fetch_episodes_raw(self, slug: str) -> Optional[List[Dict]]:
        """Return the raw list of episode dicts for *slug*.

        Implement this in providers that use the template get_episodes below.
        Providers that override get_episodes directly do not need this.
        """
        raise NotImplementedError(
            f"{type(self).__name__} must implement _fetch_episodes_raw or override get_episodes"
        )

    def _parse_episode(self, raw: Dict, index: int) -> Optional[Dict]:
        """Parse one raw episode dict into an EpisodeInfo dict.

        Implement this in providers that use the template get_episodes below.
        The index is a 1-based provisional number; _sort_episodes_chronologically
        will re-number after sorting.
        """
        raise NotImplementedError(
            f"{type(self).__name__} must implement _parse_episode or override get_episodes"
        )

    def _fallback_episodes(self, slug: str) -> List[Dict]:
        """Return fallback episodes when the API yields nothing.

        Default: empty list.  Override to return a placeholder episode.
        """
        return []

    def _get_show_api_metadata(self, show_id: str, show_info: Dict) -> Optional[Dict]:
        """Return extra metadata from a live API, or None to use programs.json only.
        Override in providers that enrich show data via a network request.
        """
        return None

    def get_programs(self) -> List[ShowInfo]:
        """Return show list with optional per-show API enrichment (parallel).
        Override entirely for providers that need a custom flow (FranceTV, CBC).
        """
        shows = getattr(self, 'shows', {})
        if not shows:
            return []

        def fetch(item):
            show_id, show_info = item
            try:
                return (show_id, show_info, self._get_show_api_metadata(show_id, show_info))
            except Exception as e:
                logger.warning("⚠️ %s Could not fetch API metadata for %s: %s", self.log_prefix, show_id, e)
                return (show_id, show_info, None)

        try:
            results = self._parallel_map(fetch, shows.items())
            return [self._build_show_metadata(sid, sinfo, meta) for sid, sinfo, meta in results]
        except Exception as e:
            logger.error("❌ %s Error fetching show metadata: %s", self.log_prefix, e)
            return [self._build_show_metadata(sid, sinfo) for sid, sinfo in shows.items()]

    def get_episodes(self, show_id: str) -> List[EpisodeInfo]:
        """Fetch, parse and sort episodes for *show_id*.

        Default implementation uses _fetch_episodes_raw + _parse_episode.
        Override entirely for providers with complex multi-step flows.
        """
        slug = self._extract_slug(show_id)
        if slug not in getattr(self, 'shows', {}):
            return []
        raw = self._fetch_episodes_raw(slug)
        if not raw:
            return self._fallback_episodes(slug)
        episodes = [ep for ep in (self._parse_episode(item, i) for i, item in enumerate(raw, 1)) if ep]
        return self._sort_episodes_chronologically(episodes)

    @abstractmethod
    def get_episode_stream_url(self, episode_id: str) -> Optional[List[StreamInfo]]:
        """Get stream URL for a specific episode. Returns a list of stream dicts or None."""
        pass

    def get_live_channels(self) -> List[LiveChannelInfo]:
        """Get list of live channels. Override in subclasses that support live channels."""
        return []

    def get_channel_stream_url(self, channel_id: str) -> Optional[List[StreamInfo]]:
        """Get stream URL for a live channel. Returns a list of stream dicts or None."""
        return None

    def resolve_stream(self, stream_id: str) -> Optional[List[StreamInfo]]:
        """
        Resolve any stream ID to a playable URL.
        Determines if it's a live channel or episode and routes accordingly.
        """
        if ":channel:" in stream_id or stream_id.startswith("live_"):
            return self.get_channel_stream_url(stream_id)
        else:
            return self.get_episode_stream_url(stream_id)

