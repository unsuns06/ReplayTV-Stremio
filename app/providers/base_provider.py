"""
Base provider class with common functionality.
All providers should inherit from this class.
"""

import os
import requests
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any

from app.utils.credentials import get_provider_credentials
from app.utils.api_client import ProviderAPIClient
from app.utils.user_agent import get_random_windows_ua
from app.utils.safe_print import safe_print
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
    
    def _load_mediaflow_config(self) -> tuple:
        """
        Load MediaFlow proxy configuration.
        
        Returns:
            Tuple of (mediaflow_url, mediaflow_password)
        """
        # First try environment variables
        mediaflow_url = os.getenv('MEDIAFLOW_PROXY_URL')
        mediaflow_password = os.getenv('MEDIAFLOW_API_PASSWORD')
        
        # Fallback to credentials file
        if not mediaflow_url or not mediaflow_password:
            mediaflow_creds = get_provider_credentials('mediaflow')
            if not mediaflow_url:
                mediaflow_url = mediaflow_creds.get('url')
            if not mediaflow_password:
                mediaflow_password = mediaflow_creds.get('password')
        
        return mediaflow_url, mediaflow_password
    
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

