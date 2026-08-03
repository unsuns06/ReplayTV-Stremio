from fastapi import APIRouter, Request
import asyncio
import logging
from starlette.concurrency import run_in_threadpool
from typing import Dict, List, Optional, Any
from app.schemas.stremio import MetaResponse
from app.providers.factory import ProviderFactory
from app.utils.base_url import get_base_url
from app.utils.ids import parse_stremio_id
from app.utils.programs_loader import get_programs_for_provider
from app.utils.cache import cache
from app.utils.cache_keys import CacheKeys, CacheTTL
from app.config.provider_config import (
    PROVIDER_REGISTRY,
    get_live_providers,
    get_provider_by_id_prefix,
    get_provider_config,
)

router = APIRouter()
logger = logging.getLogger(__name__)

CHANNEL_PROVIDERS = get_live_providers()


def _get_show_metadata_from_programs(provider_name: str, show_slug: str, static_base: str) -> Optional[Dict[str, Any]]:
    """Get show metadata from programs.json for a specific show."""
    programs = get_programs_for_provider(provider_name)
    if show_slug in programs:
        show = programs[show_slug]
        cfg = get_provider_config(provider_name) or {}
        country = cfg.get("country", "fr")
        default_channel = cfg.get("default_channel", "france2")
        fallback_logo = f"{static_base}/static/logos/{country}/{default_channel}.png"
        return {
            "id": show_slug,
            "name": show.get('name', show_slug),
            "description": show.get('description', ''),
            "logo": show.get('logo') or fallback_logo,
            "poster": show.get('poster', ''),
            "background": show.get('background', ''),
            "channel": show.get('channel', ''),
            "genres": show.get('genres', []),
            "year": show.get('year', 2024),
            "rating": show.get('rating', 'Tous publics')
        }
    return None


def _build_video_data(episode: Dict[str, Any], show_meta: Dict[str, Any], index: int) -> Dict[str, Any]:
    """Build video data dict from episode and show metadata."""
    video_data = {
        "id": episode["id"],
        "title": episode["title"],
        "season": episode.get("season", 1),
        "episode": episode.get("episode", index + 1),
        "thumbnail": episode.get("poster", show_meta.get("poster") or show_meta.get("logo", "")),
        "description": episode.get("description", ""),
        "overview": episode.get("description", ""),
        "summary": episode.get("description", ""),
        "duration": episode.get("duration", ""),
        "broadcast_date": episode.get("broadcast_date", ""),
        "rating": episode.get("rating", ""),
        "director": episode.get("director", ""),
        "cast": episode.get("cast", []),
        "channel": episode.get("channel", show_meta.get("channel", "")),
        "program": episode.get("program", show_meta.get("name", "")),
        "type": episode.get("type", "episode")
    }
    
    # Only add 'released' if it exists and is non-empty (optional for Stremio)
    if episode.get("released"):
        video_data["released"] = episode["released"]
    
    return video_data


def _build_series_meta(show_meta: Dict[str, Any], id_prefix: str, videos: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Build series metadata dict from show metadata and videos."""
    return {
        "id": f"{id_prefix}:{show_meta['id']}",
        "type": "series",
        "name": show_meta["name"],
        "poster": show_meta.get("poster") or show_meta.get("logo", ""),
        "logo": show_meta.get("logo", ""),
        "background": show_meta.get("background", ""),
        "description": show_meta.get("description", ""),
        "channel": show_meta.get("channel", ""),
        "genres": show_meta.get("genres", []),
        "year": show_meta.get("year", 2024),
        "rating": show_meta.get("rating", "Tous publics"),
        "videos": videos
    }


async def _handle_channel_metadata(id: str, request: Request) -> Optional[MetaResponse]:
    """Search for channel metadata across all channel providers in parallel."""
    
    async def fetch_from_provider(provider_key: str):
        """Fetch channels from a single provider and find matching channel."""
        cache_key = CacheKeys.channels(provider_key)
        channels = cache.get(cache_key)
        if channels is None:
            try:
                provider = ProviderFactory.create_provider(provider_key, request)
                channels = await run_in_threadpool(provider.get_live_channels)
                cache.set(cache_key, channels, ttl=CacheTTL.CHANNELS)
            except Exception as e:
                logger.error("Error getting %s channel metadata: %s", provider_key, e)
                return None
        for channel in channels:
            if channel["id"] == id:
                return channel
        return None

    # Run all provider fetches in parallel
    tasks = [fetch_from_provider(key) for key in CHANNEL_PROVIDERS]
    results = await asyncio.gather(*tasks)

    # Return first matching result
    for result in results:
        if result:
            return MetaResponse(
                meta={
                    "id": result["id"],
                    "type": "channel",
                    "name": result["name"],
                    "logo": result.get("logo", ""),
                    "poster": result.get("poster", ""),
                    "description": result.get("description", ""),
                    "videos": []
                }
            )
    
    return None


def _extract_show_id_from_id(id: str) -> Optional[str]:
    """Extract show slug from series ID."""
    parsed = parse_stremio_id(id)
    return parsed.slug if parsed else None


def _handle_series_metadata(
    provider_key: str,
    show_id: str,
    request: Request,
    static_base: str
) -> MetaResponse:
    """Handle series metadata for any provider."""
    config = PROVIDER_REGISTRY[provider_key]
    provider_name = config["provider_name"]
    display_name = config["display_name"]
    id_prefix = config["id_prefix"]
    
    try:
        provider = ProviderFactory.create_provider(provider_name, request)
        
        # Get show metadata from programs.json
        show_meta = _get_show_metadata_from_programs(provider_name, show_id, static_base)
        if not show_meta:
            return MetaResponse()
        
        # Get episodes for the show (cached)
        series_id = f"{id_prefix}:{show_id}"
        episodes_cache_key = CacheKeys.episodes(series_id)
        episodes = cache.get(episodes_cache_key)
        if episodes is None:
            episodes = provider.get_episodes(series_id)
            cache.set(episodes_cache_key, episodes, ttl=CacheTTL.EPISODES)
        
        # Convert episodes to Stremio video format
        videos = [_build_video_data(ep, show_meta, i) for i, ep in enumerate(episodes)]
        
        # Build series metadata
        series_meta = _build_series_meta(show_meta, id_prefix, videos)
        
        series_meta = provider.enhance_series_meta(series_meta, show_id)
        
        return MetaResponse(meta=series_meta)
        
    except Exception as e:
        logger.error("Error getting %s series metadata: %s", display_name, e)
        
        # Fallback to programs.json data only
        show_meta = _get_show_metadata_from_programs(provider_name, show_id, static_base)
        if show_meta:
            series_meta = _build_series_meta(show_meta, id_prefix, [])
            return MetaResponse(meta=series_meta)
        
        return MetaResponse()


@router.get("/meta/{type}/{id}.json")
async def get_meta(type: str, id: str, request: Request):
    """Get metadata for a channel or series."""
    # Get base URL for static assets (env override or derived from the request)
    static_base = get_base_url(request)
    
    # Handle live TV channel metadata
    if type == "channel":
        result = await _handle_channel_metadata(id, request)
        if result:
            return result
        return MetaResponse()
    
    # Handle series metadata
    if type == "series":
        provider_key = get_provider_by_id_prefix(id)
        if provider_key:
            show_id = _extract_show_id_from_id(id)
            if show_id:
                # Provider I/O is blocking (requests) — keep it off the event loop
                return await run_in_threadpool(
                    _handle_series_metadata, provider_key, show_id, request, static_base
                )

    return MetaResponse()