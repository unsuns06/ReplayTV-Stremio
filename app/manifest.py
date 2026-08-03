"""Stremio addon manifest, generated from the provider registry.

Catalog entries and ID prefixes are derived from ``PROVIDER_REGISTRY`` and
``programs.json`` so that adding or renaming a provider never requires a
manual manifest edit — only the static addon identity lives here.
"""

from app.config.provider_config import PROVIDER_REGISTRY
from app.utils.programs_loader import get_programs_for_provider

ADDON_ID = "org.catchuptvandmore.stremio"
ADDON_VERSION = "1.1.0"
ADDON_NAME = "Catch-up TV & More"


def _catalog_name(provider_key: str, display_name: str) -> str:
    """Build a catalog display name listing the provider's shows."""
    try:
        shows = get_programs_for_provider(provider_key)
        names = ", ".join(info.get("name", slug) for slug, info in shows.items())
    except Exception:
        names = ""
    return f"{display_name} TV Shows: {names}" if names else f"{display_name} TV Shows"


def get_manifest():
    catalogs = [
        {
            "id": "fr-live",
            "type": "channel",
            "name": "French Live TV",
        }
    ]
    for key, cfg in PROVIDER_REGISTRY.items():
        if cfg.get("catalog_id"):
            catalogs.append({
                "id": cfg["catalog_id"],
                "type": "series",
                "name": _catalog_name(key, cfg["display_name"]),
            })

    id_prefixes = sorted({
        f"cutam:{cfg['country']}:"
        for cfg in PROVIDER_REGISTRY.values()
        if cfg.get("country")
    })

    return {
        "id": ADDON_ID,
        "version": ADDON_VERSION,
        "name": ADDON_NAME,
        "description": (
            "French and Canadian live TV and TV show replays from "
            + ", ".join(cfg["display_name"] for cfg in PROVIDER_REGISTRY.values())
        ),
        "logo": "https://catch-up-tv-and-more.github.io/images/logo.png",
        "background": "https://catch-up-tv-and-more.github.io/images/background.jpg",
        "resources": ["catalog", "meta", "stream"],
        "types": ["channel", "series"],
        "catalogs": catalogs,
        "idPrefixes": id_prefixes,
        "behaviorHints": {
            "configurable": True,
            "configurationRequired": False,
        },
    }
