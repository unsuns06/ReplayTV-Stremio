"""
Base provider class with common functionality.
All providers should inherit from this class.
"""

import os
import requests
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from urllib.parse import quote, urlencode

from app.utils.credentials import get_provider_credentials, load_credentials
from app.utils.api_client import ProviderAPIClient
from app.utils.user_agent import get_random_windows_ua
from app.utils.safe_print import safe_print
from app.utils.proxy_config import get_proxy_config
from app.schemas.type_defs import StreamInfo, EpisodeInfo, ShowInfo


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
    @abstractmethod
    def provider_key(self) -> str:
        """Unique identifier key for the provider (e.g., 'francetv', 'cbc')."""
        pass
        
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
    
    def _init_mediaflow(self):
        """Initialize MediaFlow proxy configuration."""
        self.mediaflow_url, self.mediaflow_password = self._load_mediaflow_config()
        if self.mediaflow_url and self.mediaflow_password:
            safe_print(f"✅ {self.log_prefix} MediaFlow configured")
        else:
            safe_print(f"⚠️ {self.log_prefix} MediaFlow not configured")
    
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
        safe_print(f"⚠️ {self.log_prefix} Proxy '{proxy_key}' not configured")
        return None
    
    def _check_processed_file(self, episode_id: str) -> Optional[Dict]:
        """Check if DRM-free processed file exists in RD folder or processor."""
        processor_url = self.proxy_config.get_proxy('nm3u8_processor')
        if not processor_url:
            return None
        
        processed_filename = f"{episode_id}.mp4"
        
        # Check Real-Debrid folder first
        try:
            all_creds = load_credentials()
            rd_folder = all_creds.get('realdebridfolder')
            if rd_folder:
                rd_headers = {'User-Agent': get_random_windows_ua()}
                response = requests.get(rd_folder, headers=rd_headers, timeout=10)
                if response.status_code == 200 and processed_filename in response.text:
                    rd_file_url = rd_folder.rstrip('/') + '/' + processed_filename
                    safe_print(f"✅ {self.log_prefix} Found in RD: {processed_filename}")
                    return {"url": rd_file_url, "manifest_type": "video", "title": "✅ [RD] DRM-Free Video"}
        except Exception:
            pass
        
        # Check processor URL
        try:
            processed_url = f"{processor_url}/stream/{processed_filename}"
            check_response = requests.head(processed_url, timeout=5)
            if check_response.status_code == 200:
                safe_print(f"✅ {self.log_prefix} Found processed: {processed_filename}")
                return {"url": processed_url, "manifest_type": "video", "title": "✅ DRM-Free Video"}
        except Exception:
            pass
        
        return None
    
    def _fetch_with_proxy_fallback(self, url: str, params: Dict = None, 
                                    headers: Dict = None, proxy_key: str = 'fr_default') -> Optional[Dict]:
        """Try geo-proxy first, fallback to direct call on failure."""
        dest_with_params = url + ("?" + urlencode(params) if params else "")
        proxied_url = self._get_geo_proxy_url(dest_with_params, proxy_key)
        
        # Try proxy first
        if proxied_url:
            data = self.api_client.get(proxied_url, headers=headers, max_retries=1)
            if data and data.get('delivery', {}).get('code', 500) == 200:
                safe_print(f"✅ {self.log_prefix} Proxy success")
                return data
        
        # Fallback to direct
        safe_print(f"⚠️ {self.log_prefix} Proxy failed, trying direct")
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
    
    def get_live_channels(self) -> List[Dict[str, Any]]:
        """
        Get list of live channels.
        Override in subclasses that support live channels.
        Default implementation returns empty list.
        """
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

