from abc import ABC, abstractmethod
from typing import List, Dict, Optional
from fastapi import Request

# Import French providers
from app.providers.fr.francetv import FranceTVProvider
from app.providers.fr.mytf1 import MyTF1Provider
from app.providers.fr.sixplay import SixPlayProvider

# Import Canadian providers
from app.providers.ca.cbc import CBCProvider

class Provider(ABC):
    """Abstract base class for all providers"""
    
    @abstractmethod
    def get_live_channels(self) -> List[Dict]:
        """Get list of live channels from the provider"""
        pass
    
    @abstractmethod
    def get_channel_stream_url(self, channel_id: str) -> Optional[Dict]:
        """Get stream URL for a specific channel"""
        pass

class ProviderFactory:
    """Factory to create provider instances"""
    
    @staticmethod
    def create_provider(provider_name: str, request: Optional[Request] = None) -> Provider:
        """Create a provider instance based on the provider name"""
        if provider_name == "francetv":
            return FranceTVProvider(request)
        elif provider_name == "mytf1":
            return MyTF1Provider(request)
        elif provider_name == "6play":
            return SixPlayProvider(request)
        elif provider_name == "cbc":
            return CBCProvider(request)
        else:
            raise ValueError(f"Unknown provider: {provider_name}")

