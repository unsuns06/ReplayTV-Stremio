"""
Base provider class with common functionality.
All providers should inherit from this class.
"""

import logging
import os
import requests
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Dict, List, Optional, TypeVar
from urllib.parse import quote, urlencode

_T = TypeVar("_T")
_PARALLEL_FETCH_WORKERS = 5   # max threads for parallel metadata / image fetches

from app.utils.credentials import get_provider_credentials, load_credentials
from app.utils.api_client import ProviderAPIClient
from app.utils.user_agent import get_random_windows_ua
from app.utils.proxy_config import get_proxy_config
from app.utils.client_ip import make_ip_headers, merge_ip_headers as _merge_ip_util
from app.schemas.type_defs import EpisodeInfo, LiveChannelInfo, ShowInfo, StreamInfo

logger = logging.getLogger(__name__)


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
    
    # Metadata Configuration (Subclasses must override)
    display_name: str = "Unknown Provider"
    id_prefix: str = ""
    episode_marker: str = "episode:"
    catalog_id: str = ""
    supports_live: bool = False
    
    def __init__(self, request=None):
        """
        Initialize base provider.
        
        Args:
            request: Optional FastAPI Request object for base URL determination
        """
        self.request = request
        self.credentials = get_provider_credentials(self.provider_name)
        
        # Initialize session with rotating User-Agent
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': get_random_windows_ua()
        })
        
        # Initialize API client
        self.api_client = ProviderAPIClient(
            provider_name=self.provider_name,
            timeout=15,
            max_retries=3
        )
        
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
        """Get formatted logging prefix with provider display name."""
        display_names = {
            "mytf1": "MyTF1",
            "6play": "SixPlay",
            "francetv": "FranceTV",
            "cbc": "CBC"
        }
        name = display_names.get(self.provider_name, self.provider_name.capitalize())
        return f"[{name}]"
    
    def _parallel_map(self, fn: Callable[..., _T], items) -> List[_T]:
        """Apply *fn* to every item in *items* using a thread pool.

        Wraps the repeated ``ThreadPoolExecutor`` boilerplate so subclasses can
        write ``self._parallel_map(fetch_fn, items)`` instead of the 3-line
        executor pattern.
        """
        with ThreadPoolExecutor(max_workers=_PARALLEL_FETCH_WORKERS) as executor:
            return list(executor.map(fn, items))

    def _init_mediaflow(self):
        """Initialize MediaFlow proxy configuration."""
        self.mediaflow_url, self.mediaflow_password = self._load_mediaflow_config()
        if self.mediaflow_url and self.mediaflow_password:
            logger.debug("✅ %s MediaFlow configured", self.log_prefix)
        else:
            logger.debug("⚠️ %s MediaFlow not configured", self.log_prefix)
    
    def _load_mediaflow_config(self) -> tuple:
        """Load MediaFlow proxy configuration."""
        mediaflow_url = os.getenv('MEDIAFLOW_PROXY_URL')
        mediaflow_password = os.getenv('MEDIAFLOW_API_PASSWORD')
        
        if not mediaflow_url or not mediaflow_password:
            mediaflow_creds = get_provider_credentials('mediaflow')
            if not mediaflow_url:
                mediaflow_url = mediaflow_creds.get('url')
            if not mediaflow_password:
                mediaflow_password = mediaflow_creds.get('password')
        
        return mediaflow_url, mediaflow_password
    
    def _get_geo_proxy_url(self, destination_url: str, proxy_key: str = 'fr_default') -> Optional[str]:
        """Get proxied URL for geo-restricted content."""
        proxy_base = self.proxy_config.get_proxy(proxy_key)
        if proxy_base:
            return proxy_base + quote(destination_url, safe='')
        logger.debug("⚠️ %s Proxy '%s' not configured", self.log_prefix, proxy_key)
        return None

    def _fetch_with_proxy_fallback(self, url: str, params: Dict = None,
                                    headers: Dict = None, proxy_key: str = 'fr_default') -> Optional[Dict]:
        """Try geo-proxy first, fallback to direct call on failure."""
        dest_with_params = url + ("?" + urlencode(params) if params else "")
        proxied_url = self._get_geo_proxy_url(dest_with_params, proxy_key)

        if proxied_url:
            data = self.api_client.get(proxied_url, headers=headers, max_retries=1)
            if data and data.get('delivery', {}).get('code', 500) == 200:
                logger.debug("✅ %s Proxy success", self.log_prefix)
                return data

        logger.debug("⚠️ %s Proxy failed, trying direct", self.log_prefix)
        return self.api_client.get(url, params=params, headers=headers, max_retries=2)
    
    def _build_stream_headers(self, auth_token: str = None) -> Dict:
        """Build standard headers for stream requests."""
        headers = {
            "User-Agent": get_random_windows_ua(),
            "referer": self.base_url,
            "origin": self.base_url,
            "accept-language": "fr-FR,fr;q=0.9,en;q=0.8",
            "accept": "application/json, text/plain, */*",
        }
        if auth_token:
            headers["authorization"] = f"Bearer {auth_token}"
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
    
    def _get_static_base(self) -> str:
        """Get base URL for static assets"""
        return os.getenv('ADDON_BASE_URL', 'http://localhost:7860')
    
    @abstractmethod
    def get_programs(self) -> List[ShowInfo]:
        """Get list of available programs/shows"""
        pass
    
    @abstractmethod
    def get_episodes(self, show_id: str) -> List[EpisodeInfo]:
        """Get episodes for a specific show"""
        pass
    
    @abstractmethod
    def get_episode_stream_url(self, episode_id: str) -> Optional[StreamInfo]:
        """Get stream URL for a specific episode"""
        pass
    
    def get_live_channels(self) -> List[LiveChannelInfo]:
        """Get list of live channels. Override in subclasses that support live channels."""
        return []
    
    def get_channel_stream_url(self, channel_id: str) -> Optional[StreamInfo]:
        """
        Get stream URL for a live channel.
        Override in subclasses that support live channels.
        Default implementation returns None.
        """
        return None
    
    def resolve_stream(self, stream_id: str) -> Optional[StreamInfo]:
        """
        Resolve any stream ID to a playable URL.
        Determines if it's a live channel or episode and routes accordingly.
        """
        if ":channel:" in stream_id or stream_id.startswith("live_"):
            return self.get_channel_stream_url(stream_id)
        else:
            return self.get_episode_stream_url(stream_id)

