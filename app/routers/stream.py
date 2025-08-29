from fastapi import APIRouter
from app.schemas.stremio import StreamResponse, Stream
from app.providers.fr.common import ProviderFactory
from app.utils.ids import parse_channel_id, parse_episode_id
from app.utils.env import is_offline

router = APIRouter()

@router.get("/stream/{type}/{id}.json")
async def get_stream(type: str, id: str):
    # Handle live streams
    if type == "channel":
        parsed = parse_channel_id(id)
        provider_key = parsed.get("provider")
        if not provider_key:
            return StreamResponse(streams=[])
        try:
            provider = ProviderFactory.create_provider(provider_key)
        except Exception:
            return StreamResponse(streams=[])

        if is_offline():
            return StreamResponse(streams=[])

        stream_info = provider.get_channel_stream_url(id)
        if stream_info:
            stream = Stream(
                url=stream_info["url"],
                title=f"{stream_info.get('manifest_type', 'hls').upper()} Stream",
                headers=stream_info.get('headers'),
                manifest_type=stream_info.get('manifest_type'),
                licenseUrl=stream_info.get('licenseUrl'),
                licenseHeaders=stream_info.get('licenseHeaders')
            )
            return StreamResponse(streams=[stream])
        else:
            return StreamResponse(streams=[{"url": "https://example.com/stream-not-available.mp4", "title": "Stream not available"}])
    
    # Handle France TV replay streams
    elif type == "series":
        # Must be an episode to resolve a stream
        if "episode:" not in id:
            return StreamResponse(streams=[{"url": "https://example.com/episode-not-specified.mp4", "title": "Please select a specific episode"}])

        ep = parse_episode_id(id)
        provider_key = ep.get("provider")
        if not provider_key:
            return StreamResponse(streams=[])
        try:
            provider = ProviderFactory.create_provider(provider_key)
        except Exception:
            return StreamResponse(streams=[])

        if is_offline():
            return StreamResponse(streams=[Stream(url="https://example.com/offline.mp4", title="Offline mode")])

        stream_info = provider.get_episode_stream_url(id)
        if stream_info:
            stream = Stream(
                url=stream_info["url"],
                title=f"{stream_info.get('manifest_type', 'hls').upper()} Stream",
                headers=stream_info.get('headers'),
                manifest_type=stream_info.get('manifest_type'),
                licenseUrl=stream_info.get('licenseUrl'),
                licenseHeaders=stream_info.get('licenseHeaders')
            )
            return StreamResponse(streams=[stream])
        else:
            return StreamResponse(streams=[{"url": "https://example.com/stream-not-available.mp4", "title": "Stream not available"}])
    
    return StreamResponse(streams=[])