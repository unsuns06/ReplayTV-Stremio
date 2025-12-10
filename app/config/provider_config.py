"""
Centralized provider configuration registry.
Eliminates duplicate provider configuration across routers.
"""

from typing import Dict, List, Any, Optional


# Centralized provider registry - single source of truth
PROVIDER_REGISTRY: Dict[str, Dict[str, Any]] = {
    "francetv": {
        "provider_name": "francetv",
        "display_name": "France TV",
        "id_prefix": "cutam:fr:francetv",
        "country": "fr",
        "episode_marker": "episode:",
        "catalog_id": "fr-francetv-replay",
        "supports_live": True,
    },
    "mytf1": {
        "provider_name": "mytf1",
        "display_name": "TF1+",
        "id_prefix": "cutam:fr:mytf1",
        "country": "fr",
        "episode_marker": "episode:",
        "catalog_id": "fr-mytf1-replay",
        "supports_live": True,
    },
    "6play": {
        "provider_name": "6play",
        "display_name": "6play",
        "id_prefix": "cutam:fr:6play",
        "country": "fr",
        "episode_marker": "episode:",
        "catalog_id": "fr-6play-replay",
        "supports_live": False,
    },
    "cbc": {
        "provider_name": "cbc",
        "display_name": "CBC",
        "id_prefix": "cutam:ca:cbc",
        "country": "ca",
        "episode_marker": "episode-",
        "catalog_id": "ca-cbc-dragons-den",
        "supports_live": False,
    },
}


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
