"""
Centralized provider configuration registry.
Eliminates duplicate provider configuration across routers.
Dyanmically built from the provider registry to ensure single source of truth.
"""

from typing import Dict, List, Any, Optional
from app.providers.registry import PROVIDER_CLASSES


def _build_registry() -> Dict[str, Dict[str, Any]]:
    """Build the provider registry from registered classes."""
    registry = {}
    for key, cls in PROVIDER_CLASSES.items():
        registry[key] = {
            "provider_name": cls.provider_name,
            "display_name": cls.display_name,
            "id_prefix": cls.id_prefix,
            "country": cls.country,
            "episode_marker": cls.episode_marker,
            "catalog_id": cls.catalog_id,
            "supports_live": cls.supports_live,
        }
    return registry

# Centralized provider registry - single source of truth (Dynamically Built)
PROVIDER_REGISTRY: Dict[str, Dict[str, Any]] = _build_registry()


def get_provider_config(provider_key: str) -> Optional[Dict[str, Any]]:
    """
    Get configuration for a specific provider.
    
    Args:
        provider_key: Provider identifier (e.g., "francetv", "mytf1")
        
    Returns:
        Provider configuration dict or None if not found
    """
    return PROVIDER_REGISTRY.get(provider_key)


def get_all_providers() -> Dict[str, Dict[str, Any]]:
    """Get all provider configurations."""
    return PROVIDER_REGISTRY


def get_providers_by_country(country: str) -> List[str]:
    """
    Get provider keys filtered by country.
    
    Args:
        country: Two-letter country code (e.g., "fr", "ca")
        
    Returns:
        List of provider keys for the specified country
    """
    return [
        key for key, config in PROVIDER_REGISTRY.items()
        if config.get("country") == country
    ]


def get_live_providers() -> List[str]:
    """Get provider keys that support live channels."""
    return [
        key for key, config in PROVIDER_REGISTRY.items()
        if config.get("supports_live", False)
    ]


def get_provider_by_catalog_id(catalog_id: str) -> Optional[str]:
    """
    Find provider key by catalog ID.
    
    Args:
        catalog_id: Catalog identifier (e.g., "fr-francetv-replay")
        
    Returns:
        Provider key or None if not found
    """
    for key, config in PROVIDER_REGISTRY.items():
        if config.get("catalog_id") == catalog_id:
            return key
    return None


def get_provider_by_id_prefix(id_string: str) -> Optional[str]:
    """
    Identify provider from an ID string by matching prefix.
    
    Args:
        id_string: Full ID string (e.g., "cutam:fr:francetv:show-name")
        
    Returns:
        Provider key or None if no match
    """
    for key, config in PROVIDER_REGISTRY.items():
        if id_string.startswith(config.get("id_prefix", "")):
            return key
    return None