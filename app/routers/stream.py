from fastapi import APIRouter, Request
import logging
import traceback
from typing import Dict, List, Optional, Union
from app.schemas.stremio import StreamResponse, Stream
from app.providers.common import ProviderFactory
from app.utils.client_ip import make_ip_headers

router = APIRouter()
logger = logging.getLogger(__name__)

# Provider routing configuration
SERIES_PROVIDERS = {
    "francetv": {"name": "France TV", "episode_marker": "episode:"},
    "mytf1": {"name": "TF1+", "episode_marker": "episode:"},
    "6play": {"name": "6play", "episode_marker": "episode:"},
    "cbc": {"name": "CBC", "episode_marker": "episode-"},
}

CHANNEL_PROVIDERS = {
    "francetv": "France TV",
    "mytf1": "MyTF1",
    "6play": "6play",
}


def _merge_headers(provider_headers: Optional[Dict], include_ip: bool = True) -> Optional[Dict]:
    """Merge provider headers with viewer IP headers."""
    merged = {}
    if provider_headers:
        merged.update(provider_headers)
    if include_ip:
        merged.update(make_ip_headers())
    return merged if merged else None


def _build_stream_from_info(info: Dict, include_ip_headers: bool = True) -> Stream:
    """Build a Stream object from stream info dictionary."""
    merged_headers = _merge_headers(info.get('headers'), include_ip_headers)
    merged_license_headers = _merge_headers(info.get('licenseHeaders'), include_ip_headers)
    
    return Stream(
        url=info["url"],
        title=info.get('title', f"{info.get('manifest_type', 'stream').upper()} Stream"),
        headers=merged_headers,
        manifest_type=info.get('manifest_type'),
        licenseUrl=info.get('licenseUrl'),
        licenseHeaders=merged_license_headers,
        externalUrl=info.get('externalUrl')
    )


def _build_stream_response(
    stream_info: Union[Dict, List[Dict], None],
    provider_name: str,
    include_ip_headers: bool = True
) -> StreamResponse:
    """Build StreamResponse from provider stream info."""
    if not stream_info:
        logger.warning(f"⚠️ {provider_name} returned no stream info")
        return StreamResponse(streams=[{
            "url": "https://example.com/stream-not-available.mp4",
            "title": "Stream not available"
        }])
    
    if isinstance(stream_info, list):
        streams = [_build_stream_from_info(info, include_ip_headers) for info in stream_info]
        logger.info(f"✅ {provider_name} returned {len(streams)} streams")
        return StreamResponse(streams=streams)
    else:
        logger.info(f"✅ {provider_name} returned single stream: {stream_info.get('manifest_type', 'unknown')}")
        stream = _build_stream_from_info(stream_info, include_ip_headers)
        return StreamResponse(streams=[stream])


def _handle_channel_stream(id: str, request: Request) -> StreamResponse:
    """Handle live channel stream requests."""
    logger.info(f"📺 Processing live stream request for channel: {id}")
    
    # Determine provider from ID
    provider_key = None
    provider_name = None
    for key, name in CHANNEL_PROVIDERS.items():
        if key in id:
            provider_key = key
            provider_name = name
            break
    
    if not provider_key:
        logger.warning(f"⚠️ Unknown channel provider in ID: {id}")
        return StreamResponse(streams=[])
    
    logger.info(f"🎯 Using {provider_name} provider for channel: {id}")
    
    try:
        provider = ProviderFactory.create_provider(provider_key, request)
        stream_info = provider.get_channel_stream_url(id)
        return _build_stream_response(stream_info, provider_name, include_ip_headers=True)
    except Exception as e:
        logger.error(f"❌ Error getting {provider_name} stream for channel {id}: {e}")
        logger.error("   Full traceback:")
        logger.error(traceback.format_exc())
        return StreamResponse(streams=[{
            "url": "https://example.com/error-stream.mp4",
            "title": "Error getting stream"
        }])


def _handle_series_stream(provider_key: str, id: str, request: Request) -> StreamResponse:
    """Handle series/episode stream requests for any provider."""
    config = SERIES_PROVIDERS[provider_key]
    provider_name = config["name"]
    episode_marker = config["episode_marker"]
    
    logger.info(f"📺 Processing {provider_name} replay stream request: {id}")
    
    try:
        provider = ProviderFactory.create_provider(provider_key, request)
        
        # Check if episode is specified
        if episode_marker not in id:
            logger.warning(f"⚠️ No episode specified in series ID: {id}")
            return StreamResponse(streams=[{
                "url": "https://example.com/episode-not-specified.mp4",
                "title": "Please select a specific episode"
            }])
        
        episode_id = id
        logger.info(f"🎬 Getting stream for specific episode: {episode_id}")
        
        # CBC-specific debug logging
        if provider_key == "cbc":
            try:
                debug_info = provider.debug_episode_stream(episode_id)
                for step in debug_info.get("steps", []):
                    logger.info(f"DEBUG: {step}")
            except Exception:
                pass
        
        stream_info = provider.get_episode_stream_url(episode_id)
        
        # Determine if we need IP headers (some providers handle it internally)
        include_ip = provider_key in ["mytf1", "cbc"]  # Providers that need IP forwarding
        
        return _build_stream_response(stream_info, provider_name, include_ip_headers=include_ip)
        
    except Exception as e:
        logger.error(f"❌ Error getting {provider_name} stream: {e}")
        logger.error("   Full traceback:")
        logger.error(traceback.format_exc())
        return StreamResponse(streams=[{
            "url": "https://example.com/error-stream.mp4",
            "title": "Error getting stream"
        }])


@router.get("/stream/{type}/{id}.json")
async def get_stream(type: str, id: str, request: Request):
    """Get stream data with comprehensive error logging."""
    logger.info(f"🔍 STREAM REQUEST: type={type}, id={id}")
    
    # Handle live channel streams
    if type == "channel":
        return _handle_channel_stream(id, request)
    
    # Handle series/episode streams
    if type == "series":
        # Find matching provider
        for provider_key in SERIES_PROVIDERS:
            if provider_key in id:
                return _handle_series_stream(provider_key, id, request)
    
    logger.warning(f"⚠️ Unknown stream request: type={type}, id={id}")
    return StreamResponse(streams=[])
