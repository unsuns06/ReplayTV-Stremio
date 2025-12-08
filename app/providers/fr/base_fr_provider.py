"""
Base provider class for French TV providers (6play, TF1, France TV).
Extends BaseProvider with France-specific functionality.
"""

import os
from typing import Dict, List, Optional

from app.providers.base_provider import BaseProvider
from app.utils.credentials import get_provider_credentials
from app.utils.proxy_config import get_proxy_config
from app.utils.safe_print import safe_print


class BaseFrenchProvider(BaseProvider):
    """
    Base class for French TV providers.
    
    Provides:
    - MediaFlow proxy configuration
    - French router proxy for geo-blocking bypass
    - Common French provider patterns
    """
    
    country = "fr"
    
    def __init__(self, request=None):
        super().__init__(request)
        
        # Initialize proxy configuration
        self.proxy_config = get_proxy_config()
        
        # Initialize MediaFlow
        self._init_mediaflow()
    
    def _init_mediaflow(self):
        """Initialize MediaFlow proxy configuration."""
        # Load from base method
        self.mediaflow_url, self.mediaflow_password = self._load_mediaflow_config()
        
        # Log MediaFlow status
        if self.mediaflow_url and self.mediaflow_password:
            safe_print(f"✅ [{self.provider_name}] MediaFlow configured: {self.mediaflow_url[:30]}...")
        else:
            safe_print(f"⚠️ [{self.provider_name}] MediaFlow not fully configured")
    
    def _get_fr_proxy_url(self, destination_url: str) -> Optional[str]:
        """
        Get proxied URL for French geo-restricted content.
        
        Args:
            destination_url: The URL to proxy
            
        Returns:
            Proxied URL or None if proxy not configured
        """
        from urllib.parse import quote
        
        proxy_base = self.proxy_config.get_proxy('fr_router')
        if proxy_base:
            return proxy_base + quote(destination_url, safe='')
        
        safe_print(f"⚠️ [{self.provider_name}] French proxy not configured")
        return None
    
    def get_live_channels(self) -> List[Dict]:
        """
        Get live channels - default implementation returns empty.
        Override in subclasses that support live channels.
        """
        return []
    
    def get_channel_stream_url(self, channel_id: str) -> Optional[Dict]:
        """
        Get live channel stream - default returns None.
        Override in subclasses that support live channels.
        """
        return None
