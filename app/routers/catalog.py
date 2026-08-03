from fastapi import APIRouter, Request
import asyncio
import logging
from starlette.concurrency import run_in_threadpool
from app.schemas.stremio import CatalogResponse
from app.providers.factory import ProviderFactory
from app.utils.base_url import get_logo_url
from app.utils.programs_loader import get_programs_for_provider
from app.utils.show_meta import build_show_dict
from app.utils.cache import cache
from app.utils.cache_keys import CacheKeys, CacheTTL
from app.config.provider_config import get_provider_by_catalog_id, get_live_providers, get_provider_config

router = APIRouter()
logger = logging.getLogger(__name__)


def _build_fallback_shows_from_programs(provider_name: str, request: Request) -> list:
    """Build fallback show list from programs.json for a specific provider."""
    cfg = get_provider_config(provider_name) or {}
    region = cfg.get("country", "fr")
    default_channel = cfg.get("default_channel", "france2")
    id_prefix = cfg.get("id_prefix") or f"cutam:{region}:{provider_name}"
    try:
        programs = get_programs_for_provider(provider_name)
        fallback_logo = get_logo_url(region, default_channel, request)
        return [
            build_show_dict(id_prefix, slug, show_info, fallback_logo=fallback_logo)
            for slug, show_info in programs.items()
        ]
    except Exception as e:
        logger.error("❌ Error building fallback shows from programs.json: %s", e)
        return []


@router.get("/catalog/{type}/{id}.json")
async def get_catalog(type: str, id: str, request: Request):
    """Get catalog data with comprehensive error logging"""
    logger.info("🔍 CATALOG REQUEST: type=%s, id=%s", type, id)
    
    # Base URL is now handled by the base_url utility
    
    # Get live TV channels
    if type == "channel" and id == "fr-live":
        logger.info("📺 Processing live TV channels request")
        # Get all live-enabled providers dynamically
        live_provider_keys = get_live_providers()
        
        async def fetch_provider_channels(p_key: str):
            cache_key = CacheKeys.channels(p_key)
            cached = cache.get(cache_key)
            if cached is not None:
                logger.debug("📺 %s channels served from cache (%d items)", p_key, len(cached))
                return cached

            try:
                logger.debug("📺 Getting %s channels...", p_key)
                provider = ProviderFactory.create_provider(p_key, request)
                # Run blocking I/O in thread pool
                channels = await run_in_threadpool(provider.get_live_channels)
                cache.set(cache_key, channels, ttl=CacheTTL.CHANNELS)
                logger.debug("✅ %s returned %d channels", p_key, len(channels))
                return channels
            except Exception:
                logger.exception("❌ Error getting %s channels", p_key)
                return []

        # Create tasks for all providers
        tasks = [fetch_provider_channels(key) for key in live_provider_keys]
        
        # Run in parallel
        results = await asyncio.gather(*tasks)
        
        # Flatten results
        all_channels = [channel for result in results for channel in result]
        
        logger.info("📊 Total channels returned: %d", len(all_channels))
        return CatalogResponse(metas=all_channels)
    
    # Handle Series Catalogs Dynamically
    if type == "series":
        provider_key = get_provider_by_catalog_id(id)
        
        if provider_key:
            logger.info("📺 Processing %s catalog request: %s", provider_key, id)
            try:
                cache_key = CacheKeys.programs(provider_key)
                shows = cache.get(cache_key)
                if shows is not None:
                    logger.info("✅ %s shows served from cache (%d items)", provider_key, len(shows))
                    return CatalogResponse(metas=shows)

                provider = ProviderFactory.create_provider(provider_key, request)
                # Provider I/O is blocking (requests) — keep it off the event loop
                shows = await run_in_threadpool(provider.get_programs)
                cache.set(cache_key, shows, ttl=CacheTTL.PROGRAMS)
                logger.info("✅ %s returned %d shows", provider_key, len(shows))
                return CatalogResponse(metas=shows)
                
            except Exception:
                logger.exception("❌ Error getting %s shows", provider_key)
                logger.info("🔄 Using fallback %s shows from programs.json", provider_key)
                fallback_shows = _build_fallback_shows_from_programs(provider_key, request)
                return CatalogResponse(metas=fallback_shows)
    
    logger.warning("⚠️ Unknown catalog request: type=%s, id=%s", type, id)
    return CatalogResponse(metas=[])