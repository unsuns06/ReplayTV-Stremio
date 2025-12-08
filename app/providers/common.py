from typing import List, Dict, Optional
from fastapi import Request

# Import base provider for type hint
from app.providers.base_provider import BaseProvider

# Import French providers
from app.providers.fr.francetv import FranceTVProvider
from app.providers.fr.mytf1 import MyTF1Provider
from app.providers.fr.sixplay import SixPlayProvider

# Import Canadian providers
from app.providers.ca.cbc import CBCProvider


class ProviderFactory:
    """Factory to create provider instances"""
    
    @staticmethod
    def create_provider(provider_name: str, request: Optional[Request] = None) -> BaseProvider:
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

