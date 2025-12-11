from fastapi import APIRouter, Request
import os
from typing import Dict, List, Optional, Any
from app.schemas.stremio import MetaResponse
from app.providers.common import ProviderFactory
from app.utils.safe_print import safe_print
from app.utils.programs_loader import get_programs_for_provider
from app.config.provider_config import PROVIDER_REGISTRY, get_live_providers

router = APIRouter()

# Use centralized provider registry
SERIES_PROVIDERS = PROVIDER_REGISTRY

# Providers that support live channels (derived from registry)
CHANNEL_PROVIDERS = get_live_providers()


def _get_show_metadata_from_programs(provider_name: str, show_slug: str, static_base: str) -> Optional[Dict]:
    """Get show metadata from programs.json for a specific show."""
    programs = get_programs_for_provider(provider_name)
    if show_slug in programs:
        show = programs[show_slug]
        return {
            "id": show_slug,
            "name": show.get('name', show_slug),
            "description": show.get('description', ''),
            "logo": show.get('logo') or f"{static_base}/static/logos/fr/france2.png",
            "poster": show.get('poster', ''),
            "background": show.get('background', ''),
            "channel": show.get('channel', ''),
            "genres": show.get('genres', []),
            "year": show.get('year', 2024),
            "rating": show.get('rating', 'Tous publics')
        }
    return None


def _build_video_data(episode: Dict, show_meta: Dict, index: int) -> Dict:
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


def _build_series_meta(show_meta: Dict, id_prefix: str, videos: List[Dict]) -> Dict:
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


def _handle_channel_metadata(id: str, request: Request) -> Optional[MetaResponse]:
    """Search for channel metadata across all channel providers."""
    for provider_key in CHANNEL_PROVIDERS:
        try:
            provider = ProviderFactory.create_provider(provider_key, request)
            channels = provider.get_live_channels()
            
            for channel in channels:
                if channel["id"] == id:
                    return MetaResponse(
                        meta={
                            "id": channel["id"],
                            "type": "channel",
                            "name": channel["name"],
                            "logo": channel.get("logo", ""),
                            "poster": channel.get("poster", ""),
                            "description": channel.get("description", ""),
                            "videos": []
                        }
                    )
        except Exception as e:
            safe_print(f"Error getting {provider_key} channel metadata: {e}")
    
    return None


def _extract_show_id_from_id(id: str) -> Optional[str]:
    """Extract show slug from series ID."""
    parts = id.split(":")
    return parts[-1] if parts else None


def _handle_series_metadata(
    provider_key: str,
    show_id: str,
    request: Request,
    static_base: str
) -> MetaResponse:
    """Handle series metadata for any provider."""
    config = SERIES_PROVIDERS[provider_key]
    provider_name = config["provider_name"]
    display_name = config["display_name"]
    id_prefix = config["id_prefix"]
    
    try:
        provider = ProviderFactory.create_provider(provider_name, request)
        
        # Get show metadata from programs.json
        show_meta = _get_show_metadata_from_programs(provider_name, show_id, static_base)
        if not show_meta:
            return MetaResponse(meta={})
        
        # Get episodes for the show
        series_id = f"{id_prefix}:{show_id}"
        episodes = provider.get_episodes(series_id)
        
        # Convert episodes to Stremio video format
        videos = [_build_video_data(ep, show_meta, i) for i, ep in enumerate(episodes)]
        
        # Build series metadata
        series_meta = _build_series_meta(show_meta, id_prefix, videos)
        
        # FranceTV-specific: Try to enhance with API metadata
        if provider_key == "francetv":
            try:
                # Get the correct api_id from the provider's show data
                programs = get_programs_for_provider(provider_name)
                show_data = programs.get(show_id, {})
                api_id = show_data.get('api_id') or show_data.get('id', show_id)
                
                provider_metadata = provider._get_show_api_metadata(api_id)
                if provider_metadata:
                    from app.utils.metadata import metadata_processor
                    series_meta = metadata_processor.enhance_metadata_with_api(series_meta, provider_metadata)
                    # Apply logo if extracted from API
                    if provider_metadata.get('logo'):
                        series_meta['logo'] = provider_metadata['logo']
            except Exception as e:
                safe_print(f"Warning: Could not enhance series metadata: {e}")
        
        return MetaResponse(meta=series_meta)
        
    except Exception as e:
        safe_print(f"Error getting {display_name} series metadata: {e}")
        
        # Fallback to programs.json data only
        show_meta = _get_show_metadata_from_programs(provider_name, show_id, static_base)
        if show_meta:
            series_meta = _build_series_meta(show_meta, id_prefix, [])
            return MetaResponse(meta=series_meta)
        
        return MetaResponse(meta={})


@router.get("/meta/{type}/{id}.json")
async def get_meta(type: str, id: str, request: Request):
    """Get metadata for a channel or series."""
    # Get base URL for static assets
    static_base = os.getenv('ADDON_BASE_URL', 'http://localhost:7860')
    
    # Handle live TV channel metadata
    if type == "channel":
        result = _handle_channel_metadata(id, request)
        if result:
            return result
        return MetaResponse(meta={})
    
    # Handle series metadata
    if type == "series":
        # Find matching provider
        for provider_key in SERIES_PROVIDERS:
            if provider_key in id:
                show_id = _extract_show_id_from_id(id)
                if show_id:
                    return _handle_series_metadata(provider_key, show_id, request, static_base)
                break
    
    return MetaResponse(meta={})