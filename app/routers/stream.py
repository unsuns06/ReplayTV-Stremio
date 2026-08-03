from fastapi import APIRouter, Request
import logging
from starlette.concurrency import run_in_threadpool
from typing import Any, Dict, List, Optional
from app.schemas.stremio import StreamResponse, Stream
from app.providers.factory import ProviderFactory
from app.utils.client_ip import make_ip_headers
from app.utils.ids import parse_stremio_id
from app.config.provider_config import PROVIDER_REGISTRY, get_live_providers, get_provider_by_id_prefix

router = APIRouter()
logger = logging.getLogger(__name__)

_LIVE_PROVIDERS = get_live_providers()  # list of provider keys that support live


def _merge_headers(provider_headers: Optional[Dict[str, str]], include_ip: bool = True) -> Optional[Dict[str, str]]:
    """Merge provider headers with viewer IP headers."""
    merged = {}
    if provider_headers:
        merged.update(provider_headers)
    if include_ip:
        merged.update(make_ip_headers())
    return merged if merged else None


def _build_stream_from_info(info: Dict[str, Any], include_ip_headers: bool = True) -> Stream:
    """Build a Stream object from stream info dictionary."""
    merged_headers = _merge_headers(info.get('headers'), include_ip_headers)
    merged_license_headers = _merge_headers(info.get('licenseHeaders'), include_ip_headers)

    # ponytail: every URL we return is already a self-contained MediaFlow/dash-proxy
    # URL with upstream headers baked into the query string, so it's web-ready and
    # must NOT carry notWebReady/proxyHeaders — that makes Stremio re-proxy it and
    # inject the wrong headers, killing playback. Add proxyHeaders back (gated on a
    # per-stream "raw url" flag) only if a provider ever returns an un-proxied URL.

    return Stream(
        url=info["url"],
        title=info.get('title', f"{info.get('manifest_type', 'stream').upper()} Stream"),
        behaviorHints=None,
        headers=merged_headers,
        manifest_type=info.get('manifest_type'),
        licenseUrl=info.get('licenseUrl'),
        licenseHeaders=merged_license_headers,
        externalUrl=info.get('externalUrl')
    )


def _build_stream_response(
    stream_info: Optional[List[Dict[str, Any]]],
    provider_name: str,
    include_ip_headers: bool = True
) -> StreamResponse:
    """Build StreamResponse from provider stream info (always a list)."""
    if not stream_info:
        logger.warning("⚠️ %s returned no stream info", provider_name)
        return StreamResponse(streams=[])
    streams = [_build_stream_from_info(info, include_ip_headers) for info in stream_info]
    logger.info("✅ %s returned %d streams", provider_name, len(streams))
    return StreamResponse(streams=streams)


def _handle_channel_stream(id: str, request: Request) -> StreamResponse:
    """Handle live channel stream requests."""
    logger.info("📺 Processing live stream request for channel: %s", id)

    # Determine provider by parsing the composite ID (no substring matching)
    parsed = parse_stremio_id(id)
    provider_key = parsed.provider if parsed and parsed.provider in _LIVE_PROVIDERS else None

    if not provider_key:
        logger.warning("⚠️ Unknown channel provider in ID: %s", id)
        return StreamResponse(streams=[])

    provider_name = PROVIDER_REGISTRY[provider_key]["display_name"]
    
    logger.info("🎯 Using %s provider for channel: %s", provider_name, id)
    
    try:
        provider = ProviderFactory.create_provider(provider_key, request)
        stream_info = provider.get_channel_stream_url(id)
        return _build_stream_response(stream_info, provider_name, include_ip_headers=True)
    except Exception:
        logger.exception("❌ Error getting %s stream for channel %s", provider_name, id)
        return StreamResponse(streams=[])


def _handle_series_stream(provider_key: str, id: str, request: Request) -> StreamResponse:
    """Handle series/episode stream requests for any provider."""
    config = PROVIDER_REGISTRY[provider_key]
    provider_name = config["display_name"]
    episode_marker = config["episode_marker"]
    
    logger.info("📺 Processing %s replay stream request: %s", provider_name, id)
    
    try:
        provider = ProviderFactory.create_provider(provider_key, request)
        
        # Check if episode is specified
        if episode_marker not in id:
            logger.warning("⚠️ No episode specified in series ID: %s", id)
            return StreamResponse(streams=[])
        
        episode_id = id
        logger.info("🎬 Getting stream for specific episode: %s", episode_id)
        
        stream_info = provider.get_episode_stream_url(episode_id)
        
        # Determine if we need IP headers using provider property
        include_ip = provider.needs_ip_forwarding
        
        return _build_stream_response(stream_info, provider_name, include_ip_headers=include_ip)

    except Exception:
        logger.exception("❌ Error getting %s stream", provider_name)
        return StreamResponse(streams=[])


@router.get("/stream/{type}/{id}.json")
async def get_stream(type: str, id: str, request: Request):
    """Get stream data with comprehensive error logging."""
    logger.info("🔍 STREAM REQUEST: type=%s, id=%s", type, id)

    # Provider I/O is blocking (requests) — keep it off the event loop
    # Handle live channel streams
    if type == "channel":
        return await run_in_threadpool(_handle_channel_stream, id, request)

    # Handle series/episode streams
    if type == "series":
        provider_key = get_provider_by_id_prefix(id)
        if provider_key:
            return await run_in_threadpool(_handle_series_stream, provider_key, id, request)

    logger.warning("⚠️ Unknown stream request: type=%s, id=%s", type, id)
    return StreamResponse(streams=[])
