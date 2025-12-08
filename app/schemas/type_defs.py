"""
Type definitions for provider return types.
Provides TypedDicts for better type safety and IDE autocompletion.
"""

from typing import TypedDict, Optional, List, Dict


class StreamInfo(TypedDict, total=False):
    """Stream information returned by get_episode_stream_url()"""
    url: str
    manifest_type: str  # 'hls' or 'mpd'
    title: str
    headers: Optional[Dict[str, str]]
    
    # DRM-related fields
    drm_protected: bool
    licenseUrl: Optional[str]
    licenseHeaders: Optional[Dict[str, str]]
    decryption_key: Optional[str]
    pssh: Optional[str]
    
    # Additional metadata
    proxied: bool
    quality: Optional[str]


class EpisodeInfo(TypedDict, total=False):
    """Episode metadata returned by get_episodes()"""
    id: str
    title: str
    season: int
    episode: int
    description: str
    poster: str
    thumbnail: str
    duration: str  # In seconds as string
    broadcast_date: str
    air_date: str
    rating: str
    channel: str
    program: str


class ShowInfo(TypedDict, total=False):
    """Show/program metadata returned by get_programs()"""
    id: str
    name: str
    type: str  # 'series' or 'movie'
    poster: str
    logo: str
    background: str
    fanart: str
    description: str
    genres: List[str]
    year: int
    rating: str
    channel: str
    country: str


class ProviderConfig(TypedDict, total=False):
    """Provider configuration from PROVIDER_CONFIG"""
    provider_name: str
    display_name: str
    id_prefix: str
    country: str
    episode_marker: str
    supports_live: bool
