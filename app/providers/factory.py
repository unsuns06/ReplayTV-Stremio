from typing import Optional
from fastapi import Request
from app.providers.base_provider import BaseProvider
from app.providers.registry import get_provider_class

class ProviderFactory:
    """Factory to create provider instances using dynamic registry."""

    @staticmethod
    def create_provider(provider_name: str, request: Optional[Request] = None) -> BaseProvider:
        """Return a provider instance, reusing one cached on request.state within a single request.

        Per-request caching avoids rebuilding ProviderAPIClient (and its session/retry adapters)
        multiple times for the same provider within one HTTP request cycle.
        """
        if request is not None:
            if not hasattr(request.state, '_providers'):
                request.state._providers = {}
            cached = request.state._providers.get(provider_name)
            if cached is not None:
                return cached

        provider_cls = get_provider_class(provider_name)
        if not provider_cls:
            raise ValueError(f"Unknown provider: {provider_name}")

        provider = provider_cls(request)

        if request is not None:
            request.state._providers[provider_name] = provider

        return provider