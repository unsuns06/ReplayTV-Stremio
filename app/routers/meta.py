from fastapi import APIRouter, Request
import os
from app.schemas.stremio import MetaResponse
from app.providers.common import ProviderFactory
from app.utils.safe_print import safe_print
from app.utils.programs_loader import get_programs_for_provider

router = APIRouter()


def _get_show_metadata_from_programs(provider_name: str, show_slug: str, static_base: str):
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

@router.get("/meta/{type}/{id}.json")
async def get_meta(type: str, id: str, request: Request):
    # Get base URL for static assets
    static_base = os.getenv('ADDON_BASE_URL', 'http://localhost:7860')
    
    # Handle live TV channel metadata
    if type == "channel":
        # Try to get channel from France TV provider
        try:
            francetv = ProviderFactory.create_provider("francetv", request)
            channels = francetv.get_live_channels()
            
            for channel in channels:
                if channel["id"] == id:
                    return MetaResponse(
                        meta={
                            "id": channel["id"],
                            "type": "channel",
                            "name": channel["name"],
                            "logo": channel.get("logo", ""),
                            "poster": channel.get("poster", ""),
                            "description": f"Live stream for {channel['name']}",
                            "videos": []
                        }
                    )
        except Exception as e:
            safe_print(f"Error getting France TV channel metadata: {e}")
        
        # Try to get channel from TF1 provider
        try:
            mytf1 = ProviderFactory.create_provider("mytf1", request)
            channels = mytf1.get_live_channels()
            
            for channel in channels:
                if channel["id"] == id:
                    return MetaResponse(
                        meta={
                            "id": channel["id"],
                            "type": "channel",
                            "name": channel["name"],
                            "logo": channel.get("logo", ""),
                            "poster": channel.get("poster", ""),
                            "description": f"Live stream for {channel['name']}",
                            "videos": []
                        }
                    )
        except Exception as e:
            safe_print(f"Error getting TF1 channel metadata: {e}")
        
        # Try to get channel from 6play provider
        try:
            sixplay = ProviderFactory.create_provider("sixplay", request)
            channels = sixplay.get_live_channels()
            
            for channel in channels:
                if channel["id"] == id:
                    return MetaResponse(
                        meta={
                            "id": channel["id"],
                            "type": "channel",
                            "name": channel["name"],
                            "logo": channel.get("logo", ""),
                            "poster": channel.get("poster", ""),
                            "description": f"Live stream for {channel['name']}",
                            "videos": []
                        }
                    )
        except Exception as e:
            safe_print(f"Error getting 6play channel metadata: {e}")
    
    # Handle France TV series metadata with enhanced episode handling
    elif type == "series" and "francetv" in id:
        try:
            provider = ProviderFactory.create_provider("francetv", request)
            
            # Extract show ID from the series ID dynamically
            # ID format: cutam:fr:francetv:show-slug or cutam:fr:francetv:prog:show-slug
            parts = id.split(":")
            show_id = parts[-1] if parts else None
            
            if not show_id:
                return {"meta": {}}
            
            # Get show metadata from programs.json
            show_meta = _get_show_metadata_from_programs("francetv", show_id, static_base)
            if not show_meta:
                return {"meta": {}}
            
            # Get episodes for the show
            episodes = provider.get_episodes(f"cutam:fr:francetv:{show_id}")
            
            # Convert episodes to Stremio video format with enhanced metadata
            videos = []
            for episode in episodes:
                video_data = {
                    "id": episode["id"],
                    "title": episode["title"],
                    "season": episode.get("season", 1),
                    "episode": episode.get("episode", len(videos) + 1),
                    "thumbnail": episode.get("poster", show_meta["logo"]),
                    "description": episode.get("description", ""),
                    "duration": episode.get("duration", ""),
                    "broadcast_date": episode.get("broadcast_date", ""),
                    "rating": episode.get("rating", ""),
                    "director": episode.get("director", ""),
                    "cast": episode.get("cast", []),
                    "channel": episode.get("channel", show_meta["channel"]),
                    "program": episode.get("program", show_meta["name"]),
                    "type": episode.get("type", "episode")
                }
                videos.append(video_data)
            
            # Create enhanced series metadata from programs.json
            series_meta = {
                "id": f"cutam:fr:francetv:{show_meta['id']}",
                "type": "series",
                "name": show_meta["name"],
                "poster": show_meta["poster"] or show_meta["logo"],
                "logo": show_meta["logo"],
                "background": show_meta.get("background", ""),
                "description": show_meta["description"],
                "channel": show_meta["channel"],
                "genres": show_meta["genres"],
                "year": show_meta["year"],
                "rating": show_meta["rating"],
                "videos": videos
            }
            
            # Try to get additional metadata from the provider
            try:
                provider_metadata = provider._get_show_api_metadata(f"france-2_{show_id}")
                if provider_metadata:
                    from app.utils.metadata import metadata_processor
                    series_meta = metadata_processor.enhance_metadata_with_api(series_meta, provider_metadata)
            except Exception as e:
                safe_print(f"Warning: Could not enhance series metadata: {e}")
            
            return MetaResponse(meta=series_meta)
            
        except Exception as e:
            safe_print(f"Error getting France TV series metadata: {e}")
            # Fallback to programs.json data
            parts = id.split(":")
            show_id = parts[-1] if parts else None
            if show_id:
                show_meta = _get_show_metadata_from_programs("francetv", show_id, static_base)
                if show_meta:
                    return MetaResponse(
                        meta={
                            "id": f"cutam:fr:francetv:{show_meta['id']}",
                            "type": "series",
                            "name": show_meta["name"],
                            "poster": show_meta["poster"] or show_meta["logo"],
                            "logo": show_meta["logo"],
                            "description": show_meta["description"],
                            "channel": show_meta["channel"],
                            "genres": show_meta["genres"],
                            "year": show_meta["year"],
                            "rating": show_meta["rating"],
                            "videos": []
                        }
                    )
            return {"meta": {}}
    
    # Handle TF1+ series metadata with enhanced episode handling
    elif type == "series" and "mytf1" in id:
        try:
            provider = ProviderFactory.create_provider("mytf1", request)
            
            # Extract show ID from the series ID dynamically
            parts = id.split(":")
            show_id = parts[-1] if parts else None
            
            if not show_id:
                return {"meta": {}}
            
            # Get show metadata from programs.json
            show_meta = _get_show_metadata_from_programs("mytf1", show_id, static_base)
            if not show_meta:
                return {"meta": {}}
            
            # Get episodes for the show
            episodes = provider.get_episodes(f"cutam:fr:mytf1:{show_id}")
            
            # Convert episodes to Stremio video format
            videos = []
            for episode in episodes:
                video_data = {
                    "id": episode["id"],
                    "title": episode["title"],
                    "season": episode.get("season", 1),
                    "episode": episode.get("episode", len(videos) + 1),
                    "thumbnail": episode.get("poster", show_meta["logo"]),
                    "description": episode.get("description", ""),
                    "duration": episode.get("duration", ""),
                    "broadcast_date": episode.get("broadcast_date", ""),
                    "rating": episode.get("rating", ""),
                    "director": episode.get("director", ""),
                    "cast": episode.get("cast", []),
                    "channel": episode.get("channel", show_meta["channel"]),
                    "program": episode.get("program", show_meta["name"]),
                    "type": episode.get("type", "episode")
                }
                videos.append(video_data)
            
            # Create enhanced series metadata from programs.json
            series_meta = {
                "id": f"cutam:fr:mytf1:{show_meta['id']}",
                "type": "series",
                "name": show_meta["name"],
                "poster": show_meta["poster"] or show_meta["logo"],
                "logo": show_meta["logo"],
                "background": show_meta.get("background", ""),
                "description": show_meta["description"],
                "channel": show_meta["channel"],
                "genres": show_meta["genres"],
                "year": show_meta["year"],
                "rating": show_meta["rating"],
                "videos": videos
            }
            
            return MetaResponse(meta=series_meta)
            
        except Exception as e:
            safe_print(f"Error getting TF1+ series metadata: {e}")
            # Fallback to programs.json data
            parts = id.split(":")
            show_id = parts[-1] if parts else None
            if show_id:
                show_meta = _get_show_metadata_from_programs("mytf1", show_id, static_base)
                if show_meta:
                    return MetaResponse(
                        meta={
                            "id": f"cutam:fr:mytf1:{show_meta['id']}",
                            "type": "series",
                            "name": show_meta["name"],
                            "poster": show_meta["poster"] or show_meta["logo"],
                            "logo": show_meta["logo"],
                            "background": show_meta.get("background", ""),
                            "description": show_meta["description"],
                            "channel": show_meta["channel"],
                            "genres": show_meta["genres"],
                            "year": show_meta["year"],
                            "rating": show_meta["rating"],
                            "videos": []
                        }
                    )
            return {"meta": {}}
    
    # Handle 6play series metadata
    elif type == "series" and "6play" in id:
        try:
            provider = ProviderFactory.create_provider("6play", request)
            
            # Extract show ID from the series ID dynamically
            parts = id.split(":")
            show_id = parts[-1] if parts else None
            
            if not show_id:
                return {"meta": {}}
            
            # Get show metadata from programs.json
            show_meta = _get_show_metadata_from_programs("6play", show_id, static_base)
            if not show_meta:
                return {"meta": {}}
            
            # Get episodes for the show
            episodes = provider.get_episodes(f"cutam:fr:6play:{show_id}")
            
            # Convert episodes to Stremio video format
            videos = []
            for episode in episodes:
                video_data = {
                    "id": episode["id"],
                    "title": episode["title"],
                    "season": episode.get("season", 1),
                    "episode": episode.get("episode", len(videos) + 1),
                    "thumbnail": episode.get("poster", show_meta["logo"]),
                    "description": episode.get("description", ""),
                    "duration": episode.get("duration", ""),
                    "broadcast_date": episode.get("broadcast_date", ""),
                    "rating": episode.get("rating", ""),
                    "director": episode.get("director", ""),
                    "cast": episode.get("cast", []),
                    "channel": episode.get("channel", show_meta["channel"]),
                    "program": episode.get("program", show_meta["name"]),
                    "type": episode.get("type", "episode")
                }
                videos.append(video_data)
            
            # Create enhanced series metadata from programs.json
            series_meta = {
                "id": f"cutam:fr:6play:{show_meta['id']}",
                "type": "series",
                "name": show_meta["name"],
                "poster": show_meta["poster"] or show_meta["logo"],
                "logo": show_meta["logo"],
                "background": show_meta.get("background", ""),
                "description": show_meta["description"],
                "channel": show_meta["channel"],
                "genres": show_meta["genres"],
                "year": show_meta["year"],
                "rating": show_meta["rating"],
                "videos": videos
            }
            
            return MetaResponse(meta=series_meta)
            
        except Exception as e:
            safe_print(f"Error getting 6play series metadata: {e}")
            # Fallback to programs.json data
            parts = id.split(":")
            show_id = parts[-1] if parts else None
            if show_id:
                show_meta = _get_show_metadata_from_programs("6play", show_id, static_base)
                if show_meta:
                    return MetaResponse(
                        meta={
                            "id": f"cutam:fr:6play:{show_meta['id']}",
                            "type": "series",
                            "name": show_meta["name"],
                            "poster": show_meta["poster"] or show_meta["logo"],
                            "logo": show_meta["logo"],
                            "background": show_meta.get("background", ""),
                            "description": show_meta["description"],
                            "channel": show_meta["channel"],
                            "genres": show_meta["genres"],
                            "year": show_meta["year"],
                            "rating": show_meta["rating"],
                            "videos": []
                        }
                    )
            return {"meta": {}}
    
    # Handle CBC Dragon's Den series metadata
    elif type == "series" and "cbc" in id and "dragons-den" in id:
        try:
            provider = ProviderFactory.create_provider("cbc", request)
            
            # Get show metadata from programs.json
            show_meta = _get_show_metadata_from_programs("cbc", "dragons-den", static_base)
            if not show_meta:
                return {"meta": {}}
            
            # Get episodes for the show
            episodes = provider.get_episodes(f"cutam:ca:cbc:dragons-den")
            
            # Convert episodes to Stremio video format with enhanced metadata
            videos = []
            for episode in episodes:
                video_data = {
                    "id": episode["id"],
                    "title": episode["title"],
                    "season": episode.get("season", 1),
                    "episode": episode.get("episode", len(videos) + 1),
                    "thumbnail": episode.get("poster", show_meta["poster"]),
                    "overview": episode.get("description", ""),
                    "description": episode.get("description", ""),
                    "summary": episode.get("description", ""),
                    "duration": episode.get("duration", ""),
                    "broadcast_date": episode.get("broadcast_date", ""),
                    "rating": episode.get("rating", ""),
                    "director": episode.get("director", ""),
                    "cast": episode.get("cast", []),
                    "channel": episode.get("channel", show_meta["channel"]),
                    "program": episode.get("program", show_meta["name"]),
                    "type": episode.get("type", "episode")
                }
                videos.append(video_data)
            
            # Create enhanced series metadata from programs.json
            series_meta = {
                "id": f"cutam:ca:cbc:{show_meta['id']}",
                "type": "series",
                "name": show_meta["name"],
                "description": show_meta["description"],
                "poster": show_meta["poster"],
                "logo": show_meta["logo"],
                "background": show_meta["background"],
                "channel": show_meta["channel"],
                "genres": show_meta["genres"],
                "year": show_meta["year"],
                "rating": show_meta["rating"],
                "videos": videos
            }
            
            return MetaResponse(meta=series_meta)
            
        except Exception as e:
            safe_print(f"Error getting CBC Dragon's Den metadata: {e}")
            # Fallback to programs.json data
            show_meta = _get_show_metadata_from_programs("cbc", "dragons-den", static_base)
            if show_meta:
                return MetaResponse(
                    meta={
                        "id": f"cutam:ca:cbc:{show_meta['id']}",
                        "type": "series",
                        "name": show_meta["name"],
                        "description": show_meta["description"],
                        "poster": show_meta["poster"],
                        "logo": show_meta["logo"],
                        "background": show_meta["background"],
                        "channel": show_meta["channel"],
                        "genres": show_meta["genres"],
                        "year": show_meta["year"],
                        "rating": show_meta["rating"],
                        "videos": []
                    }
                )
            return {"meta": {}}
    
    return {"meta": {}}