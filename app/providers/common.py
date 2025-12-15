from typing import Optional
from fastapi import Request
from app.providers.base_provider import BaseProvider
from app.providers.registry import get_provider_class

class ProviderFactory:
    """Factory to create provider instances using dynamic registry."""
    
    @staticmethod
    def create_provider(provider_name: str, request: Optional[Request] = None) -> BaseProvider:
        """Create a provider instance based on the provider name."""
        provider_cls = get_provider_class(provider_name)
        
        if not provider_cls:
            raise ValueError(f"Unknown provider: {provider_name}")
            
        return provider_cls(request)