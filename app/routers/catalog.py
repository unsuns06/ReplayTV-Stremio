from fastapi import APIRouter, Request
import os
import logging
import traceback
import json
from app.schemas.stremio import CatalogResponse
from app.providers.common import ProviderFactory
from app.utils.base_url import get_logo_url
from app.utils.programs_loader import get_programs_for_provider

router = APIRouter()
logger = logging.getLogger(__name__)


def _build_fallback_shows_from_programs(provider_name: str, request: Request):
    """Build fallback show list from programs.json for a specific provider."""
    try:
        programs = get_programs_for_provider(provider_name)
        fallback_shows = []
        for slug, show_info in programs.items():
            fallback_shows.append({
                "id": f"cutam:{_get_region(provider_name)}:{provider_name}:{slug}",
                "type": "series",
                "name": show_info.get('name', slug),
                "poster": show_info.get('poster') or get_logo_url("fr", _get_default_channel(provider_name), request),
                "logo": show_info.get('logo') or get_logo_url("fr", _get_default_channel(provider_name), request),
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


def _get_region(provider_name: str) -> str:
    """Get region code for provider ID format."""
    return "ca" if provider_name == "cbc" else "fr"


def _get_default_channel(provider_name: str) -> str:
    """Get default channel logo for provider."""
    return {
        "francetv": "france2",
        "mytf1": "tf1",
        "6play": "m6",
        "cbc": "dragonsden"
    }.get(provider_name, "france2")


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
        # Combine channels from all French providers
        all_channels = []
        
        # Get all live-enabled providers dynamically
        live_provider_keys = get_live_providers()
        
        for p_key in live_provider_keys:
            # Skip 6play as mentioned in original code (not supported yet)
            if p_key == "6play": 
                continue
                
            try:
                logger.info(f"📺 Getting {p_key} channels...")
                provider = ProviderFactory.create_provider(p_key, request)
                channels = provider.get_live_channels()
                logger.info(f"✅ {p_key} returned {len(channels)} channels")
                all_channels.extend(channels)
            except Exception as e:
                logger.error(f"❌ Error getting {p_key} channels: {e}")
                _log_json_decode_details(f"{p_key} channels:", e)
                # Continue with other providers
        
        logger.info(f"📊 Total channels returned: {len(all_channels)}")
        return CatalogResponse(metas=all_channels)
    
    # Handle Series Catalogs Dynamically
    if type == "series":
        provider_key = get_provider_by_catalog_id(id)
        
        if provider_key:
            logger.info(f"📺 Processing {provider_key} catalog request: {id}")
            try:
                provider = ProviderFactory.create_provider(provider_key, request)
                shows = provider.get_programs()
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