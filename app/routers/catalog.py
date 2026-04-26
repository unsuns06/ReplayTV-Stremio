from fastapi import APIRouter, Request
import os
import logging
import traceback
import json
from app.schemas.stremio import CatalogResponse
from app.providers.common import ProviderFactory
from app.utils.base_url import get_logo_url
from app.utils.programs_loader import get_programs_for_provider
from app.utils.cache import cache
from app.utils.cache_keys import CacheKeys

PROGRAMS_CACHE_TTL = 600   # 10 minutes
CHANNELS_CACHE_TTL = 300   # 5 minutes

router = APIRouter()
logger = logging.getLogger(__name__)


_PROVIDER_REGION = {"cbc": "ca"}
_PROVIDER_DEFAULT_CHANNEL = {"francetv": "france2", "mytf1": "tf1", "6play": "m6", "cbc": "dragonsden"}


def _build_fallback_shows_from_programs(provider_name: str, request: Request) -> list:
    """Build fallback show list from programs.json for a specific provider."""
    region = _PROVIDER_REGION.get(provider_name, "fr")
    default_channel = _PROVIDER_DEFAULT_CHANNEL.get(provider_name, "france2")
    try:
        programs = get_programs_for_provider(provider_name)
        fallback_shows = []
        for slug, show_info in programs.items():
            fallback_logo = get_logo_url("fr", default_channel, request)
            fallback_shows.append({
                "id": f"cutam:{region}:{provider_name}:{slug}",
                "type": "series",
                "name": show_info.get('name', slug),
                "poster": show_info.get('poster') or fallback_logo,
                "logo": show_info.get('logo') or fallback_logo,
                "background": show_info.get('background', ''),
                "description": show_info.get('description', ''),
                "genres": show_info.get('genres', []),
                "year": show_info.get('year', 2024),
                "rating": show_info.get('rating', 'Tous publics'),
                "channel": show_info.get('channel', '')
            })
        return fallback_shows
    except Exception as e:
        logger.error(f"❌ Error building fallback shows from programs.json: {e}")
        return []


def _log_json_decode_details(prefix: str, exc: Exception):
    if isinstance(exc, json.JSONDecodeError):
        logger.error(
            f"{prefix} JSONDecodeError at line {exc.lineno}, column {exc.colno} (char {exc.pos}): {exc.msg}"
        )
        # Credentials context hints
        repo_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        cred_primary = os.path.join(repo_root, 'credentials.json')
        cred_fallback = os.path.join(repo_root, 'credentials-test.json')
        logger.error(
            f"Credentials files: credentials.json exists={os.path.exists(cred_primary)}, credentials-test.json exists={os.path.exists(cred_fallback)}"
        )
        env_present = 'set' if os.getenv('CREDENTIALS_JSON') else 'not set'
        logger.error(f"Env CREDENTIALS_JSON is {env_present}")


from app.config.provider_config import get_provider_by_catalog_id, get_live_providers

@router.get("/catalog/{type}/{id}.json")
async def get_catalog(type: str, id: str, request: Request):
    """Get catalog data with comprehensive error logging"""
    logger.info(f"🔍 CATALOG REQUEST: type={type}, id={id}")
    
    # Base URL is now handled by the base_url utility
    
    # Get live TV channels
    if type == "channel" and id == "fr-live":
        logger.info("📺 Processing live TV channels request")
        import asyncio
        from starlette.concurrency import run_in_threadpool

        # Get all live-enabled providers dynamically
        live_provider_keys = get_live_providers()
        
        async def fetch_provider_channels(p_key: str):
            # Skip 6play as mentioned in original code (not supported yet)
            if p_key == "6play":
                return []

            cache_key = CacheKeys.channels(p_key)
            cached = cache.get(cache_key)
            if cached is not None:
                logger.info(f"📺 {p_key} channels served from cache ({len(cached)} items)")
                return cached

            try:
                logger.info(f"📺 Getting {p_key} channels...")
                provider = ProviderFactory.create_provider(p_key, request)
                # Run blocking I/O in thread pool
                channels = await run_in_threadpool(provider.get_live_channels)
                cache.set(cache_key, channels, ttl=CHANNELS_CACHE_TTL)
                logger.info(f"✅ {p_key} returned {len(channels)} channels")
                return channels
            except Exception as e:
                logger.error(f"❌ Error getting {p_key} channels: {e}")
                _log_json_decode_details(f"{p_key} channels:", e)
                return []

        # Create tasks for all providers
        tasks = [fetch_provider_channels(key) for key in live_provider_keys]
        
        # Run in parallel
        results = await asyncio.gather(*tasks)
        
        # Flatten results
        all_channels = [channel for result in results for channel in result]
        
        logger.info(f"📊 Total channels returned: {len(all_channels)}")
        return CatalogResponse(metas=all_channels)
    
    # Handle Series Catalogs Dynamically
    if type == "series":
        provider_key = get_provider_by_catalog_id(id)
        
        if provider_key:
            logger.info(f"📺 Processing {provider_key} catalog request: {id}")
            try:
                cache_key = CacheKeys.programs(provider_key)
                shows = cache.get(cache_key)
                if shows is not None:
                    logger.info(f"✅ {provider_key} shows served from cache ({len(shows)} items)")
                    return CatalogResponse(metas=shows)

                provider = ProviderFactory.create_provider(provider_key, request)
                shows = provider.get_programs()
                cache.set(cache_key, shows, ttl=PROGRAMS_CACHE_TTL)
                logger.info(f"✅ {provider_key} returned {len(shows)} shows")
                return CatalogResponse(metas=shows)
                
            except Exception as e:
                logger.error(f"❌ Error getting {provider_key} shows: {e}")
                _log_json_decode_details(f"{provider_key} replay:", e)
                logger.error("   Full traceback:")
                logger.error(traceback.format_exc())
                
                # Fallback to programs.json
                logger.info(f"🔄 Using fallback {provider_key} shows from programs.json")
                fallback_shows = _build_fallback_shows_from_programs(provider_key, request)
                return CatalogResponse(metas=fallback_shows)
    
    logger.warning(f"⚠️ Unknown catalog request: type={type}, id={id}")
    return CatalogResponse(metas=[])