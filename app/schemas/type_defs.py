"""
Type definitions for provider return types.
Provides TypedDicts for better type safety and IDE autocompletion.

Composite ID format
-------------------
All Stremio IDs in this addon follow this colon-separated convention:

  cutam:{country}:{provider}:{slug}[:{episode_marker}{broadcast_id}]

Examples:
  cutam:fr:francetv:cash-investigation          — series (show slug)
  cutam:fr:francetv:episode:006194ea-117d-...   — episode (episode_marker="episode:")
  cutam:fr:mytf1:episode:V_123456789            — MyTF1 episode
  cutam:ca:cbc:dragons-den                      — CBC series
  cutam:ca:cbc:dragons-den:episode:S:E          — CBC episode (episode_marker="episode:")
  cutam:fr:francetv:france-2                    — live channel

Fields:
  cutam     — static namespace prefix
  country   — ISO 3166-1 alpha-2 code (fr, ca)
  provider  — lowercase provider key (francetv, mytf1, 6play, cbc)
  slug      — show slug or channel slug (from programs.json or provider API)
  episode_marker — provider-specific separator before the broadcast ID;
                   defined as BaseProvider.episode_marker / ProviderConfig.episode_marker
  broadcast_id   — opaque ID used by the upstream provider API
"""

from typing import TypedDict, Optional, List, Dict


class StreamInfo(TypedDict, total=False):
    """Stream information returned by get_episode_stream_url()"""
    url: str
    manifest_type: str  # 'hls', 'mpd' or 'video' (pre-processed file)
    title: str
    description: str
    headers: Optional[Dict[str, str]]
    filename: str       # pre-processed file name (DRM providers)
    externalUrl: Optional[str]

    # DRM-related fields
    drm_protected: bool
    drm_token: Optional[str]
    drm_keys: Optional[Dict[str, str]]   # kid -> key (MyTF1)
    licenseUrl: Optional[str]
    licenseHeaders: Optional[Dict[str, str]]
    decryption_key: Optional[str]
    default_kid: Optional[str]
    pssh: Optional[str]
    pssh_system_id: Optional[str]
    pssh_source: Optional[str]

    # Additional metadata
    proxied: bool
    quality: Optional[str]


class EpisodeInfo(TypedDict, total=False):
    """Episode metadata returned by get_episodes()"""
    id: str
    type: str            # always "episode"
    title: str
    season: int
    episode: int
    episode_number: int  # provisional number before chronological sort
    description: str
    poster: str
    fanart: str
    thumbnail: str
    duration: str        # In seconds as string
    broadcast_date: str
    broadcast_id: str    # FranceTV upstream media ID
    air_date: str
    released: str        # ISO 8601 — consumed by Stremio
    rating: str
    channel: str
    program: str
    genres: List[str]
    cast: List[str]
    note: str            # fallback-episode marker
    gem_url: str         # CBC web URL
    cbc_media_id: str    # CBC stream-resolution ID


class ShowInfo(TypedDict, total=False):
    """Show/program metadata returned by get_programs()"""
    id: str
    name: str
    type: str  # 'series' or 'movie'
    poster: str
    logo: str
    background: str
    fanart: str
    banner: str
    clearart: str
    clearlogo: str
    landscape: str
    description: str
    genres: List[str]
    year: int
    rating: str
    channel: str
    country: str


class LiveChannelInfo(TypedDict, total=False):
    """Live channel returned by get_live_channels()."""
    id: str          # cutam:{country}:{provider}:{slug}
    type: str        # always "channel"
    name: str
    logo: str
    poster: str
    description: str
    background: str


class ProviderConfig(TypedDict, total=False):
    """Provider configuration from PROVIDER_CONFIG"""
    provider_name: str
    display_name: str
    id_prefix: str
    country: str
    episode_marker: str
    supports_live: bool
