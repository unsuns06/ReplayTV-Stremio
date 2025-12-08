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
        
        # France.tv channels
        try:
            logger.info("🇫🇷 Getting France.tv channels...")
            francetv = ProviderFactory.create_provider("francetv", request)
            francetv_channels = francetv.get_live_channels()
            logger.info(f"✅ France.tv returned {len(francetv_channels)} channels")
            all_channels.extend(francetv_channels)
        except Exception as e:
            logger.error(f"❌ Error getting France.tv channels: {e}")
            _log_json_decode_details("France.tv channels:", e)
            logger.error(f"   Error type: {type(e).__name__}")
            logger.error("   Full traceback:")
            logger.error(traceback.format_exc())
            # Continue with other providers
        
        # TF1 channels
        try:
            logger.info("📺 Getting TF1 channels...")
            mytf1 = ProviderFactory.create_provider("mytf1", request)
            mytf1_channels = mytf1.get_live_channels()
            logger.info(f"✅ TF1 returned {len(mytf1_channels)} channels")
            all_channels.extend(mytf1_channels)
        except Exception as e:
            logger.error(f"❌ Error getting TF1 channels: {e}")
            _log_json_decode_details("TF1 channels:", e)
            logger.error(f"   Error type: {type(e).__name__}")
            logger.error("   Full traceback:")
            logger.error(traceback.format_exc())
            # Continue with other providers
        
        # 6play channels (currently disabled in code)
        # try:
        #     logger.info("🎬 Getting 6play channels...")
        #     sixplay = ProviderFactory.create_provider("6play")
        #     sixplay_channels = sixplay.get_live_channels()
        #     logger.info(f"✅ 6play returned {len(sixplay_channels)} channels")
        #     all_channels.extend(sixplay_channels)
        # except Exception as e:
        #     logger.error(f"❌ Error getting 6play channels: {e}")
        #     _log_json_decode_details("6play channels:", e)
        #     logger.error(f"   Error type: {type(e).__name__}")
        #     logger.error(f"   Full traceback:")
        #     logger.error(traceback.format_exc())
            
            # Continue with other providers
        
        logger.info(f"📊 Total channels returned: {len(all_channels)}")
        return CatalogResponse(metas=all_channels)
    
    # Return France 2 TV show replays with enhanced metadata
    elif type == "series" and id == "fr-francetv-replay":
        logger.info("📺 Processing France TV replay shows request")
        try:
            francetv = ProviderFactory.create_provider("francetv", request)
            shows = francetv.get_programs()
            logger.info(f"✅ France TV returned {len(shows)} shows")
            
            # The provider now returns enhanced metadata, so we can use it directly
            return CatalogResponse(metas=shows)
            
        except Exception as e:
            logger.error(f"❌ Error getting France TV replay shows: {e}")
            _log_json_decode_details("France TV replay:", e)
            logger.error("   Full traceback:")
            logger.error(traceback.format_exc())
            
            # Fallback to programs.json (single source of truth)
            logger.info("🔄 Using fallback France TV shows from programs.json")
            fallback_shows = _build_fallback_shows_from_programs("francetv", request)
            return CatalogResponse(metas=fallback_shows)
    
    # Return TF1+ TV show replays
    elif type == "series" and id == "fr-mytf1-replay":
        logger.info("📺 Processing TF1+ replay shows request")
        try:
            mytf1 = ProviderFactory.create_provider("mytf1", request)
            shows = mytf1.get_programs()
            logger.info(f"✅ TF1+ returned {len(shows)} shows")
            
            # The provider now returns enhanced metadata, so we can use it directly
            return CatalogResponse(metas=shows)
            
        except Exception as e:
            logger.error(f"❌ Error getting TF1+ replay shows: {e}")
            _log_json_decode_details("TF1+ replay:", e)
            logger.error("   Full traceback:")
            logger.error(traceback.format_exc())
            
            # Fallback to programs.json (single source of truth)
            logger.info("🔄 Using fallback TF1+ shows from programs.json")
            fallback_shows = _build_fallback_shows_from_programs("mytf1", request)
            return CatalogResponse(metas=fallback_shows)
    
    # Return 6play TV show replays
    elif type == "series" and id == "fr-6play-replay":
        logger.info("📺 Processing 6play replay shows request")
        try:
            sixplay = ProviderFactory.create_provider("6play", request)
            shows = sixplay.get_programs()
            logger.info(f"✅ 6play returned {len(shows)} shows")
            
            # The provider now returns enhanced metadata, so we can use it directly
            return CatalogResponse(metas=shows)
            
        except Exception as e:
            logger.error(f"❌ Error getting 6play replay shows: {e}")
            _log_json_decode_details("6play replay:", e)
            logger.error("   Full traceback:")
            logger.error(traceback.format_exc())
            
            # Fallback to programs.json (single source of truth)
            logger.info("🔄 Using fallback 6play shows from programs.json")
            fallback_shows = _build_fallback_shows_from_programs("6play", request)
            return CatalogResponse(metas=fallback_shows)
    
    # Return CBC Dragon's Den series
    elif type == "series" and id == "ca-cbc-dragons-den":
        logger.info("📺 Processing CBC Dragon's Den request")
        try:
            cbc = ProviderFactory.create_provider("cbc", request)
            shows = cbc.get_programs()
            logger.info(f"✅ CBC returned {len(shows)} shows")
            
            # The provider now returns enhanced metadata, so we can use it directly
            return CatalogResponse(metas=shows)
            
        except Exception as e:
            logger.error(f"❌ Error getting CBC Dragon's Den: {e}")
            _log_json_decode_details("CBC Dragon's Den:", e)
            logger.error("   Full traceback:")
            logger.error(traceback.format_exc())
            
            # Fallback to programs.json (single source of truth)
            logger.info("🔄 Using fallback CBC shows from programs.json")
            fallback_shows = _build_fallback_shows_from_programs("cbc", request)
            return CatalogResponse(metas=fallback_shows)
    
    logger.warning(f"⚠️ Unknown catalog request: type={type}, id={id}")
    return CatalogResponse(metas=[])