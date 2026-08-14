"""Canonical builder for Stremio series dicts derived from programs.json data.

This replaces four near-identical copies that previously lived in
``BaseProvider._build_show_metadata``, ``catalog._build_fallback_shows_from_programs``,
``meta._get_show_metadata_from_programs`` and ``CBCProvider.get_programs``.
"""

from typing import Any, Dict, Optional

DEFAULT_YEAR = 2024
DEFAULT_RATING = "Tous publics"

# Everything a provider's _get_show_api_metadata may contribute to a show dict.
# programs.json only pins ``provider``/``slug``/``name``; these fields come from
# the provider's own metadata endpoint. Anything else in an API-metadata dict
# (FranceTV's raw ``images`` patterns, say) is provider-internal and never
# merged into the Stremio meta.
API_FIELDS = (
    "description", "channel", "genres", "year", "rating",
    "logo", "poster", "background", "fanart",
)


def build_show_dict(
    id_prefix: str,
    slug: str,
    info: Dict[str, Any],
    fallback_logo: Optional[str] = None,
    default_rating: str = DEFAULT_RATING,
) -> Dict[str, Any]:
    """Build a Stremio-compatible series dict from a programs.json entry.

    Args:
        id_prefix: Provider ID prefix, e.g. ``"cutam:fr:francetv"``.
        slug: Show slug (becomes the last ID segment).
        info: The show's entry from programs.json.
        fallback_logo: URL used for ``logo``/``poster`` when the entry has none.
        default_rating: Rating used when the entry has none.
    """
    return {
        "id": f"{id_prefix}:{slug}",
        "type": "series",
        "name": info.get("name", slug),
        "description": info.get("description", ""),
        "channel": info.get("channel", ""),
        "genres": info.get("genres", []),
        "year": info.get("year", DEFAULT_YEAR),
        "rating": info.get("rating", default_rating),
        "logo": info.get("logo") or fallback_logo,
        "poster": info.get("poster") or fallback_logo,
        "background": info.get("background", ""),
    }
