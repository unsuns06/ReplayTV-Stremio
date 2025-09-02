from fastapi import APIRouter
import os
import logging
import traceback
import json
from app.schemas.stremio import CatalogResponse
from app.providers.fr.common import ProviderFactory

router = APIRouter()
logger = logging.getLogger(__name__)


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
async def get_catalog(type: str, id: str):
    """Get catalog data with comprehensive error logging"""
    logger.info(f"🔍 CATALOG REQUEST: type={type}, id={id}")
    
    # Get base URL for static assets
    static_base = os.getenv('ADDON_BASE_URL', 'http://localhost:7860')
    
    # Get live TV channels
    if type == "channel" and id == "fr-live":
        logger.info("📺 Processing live TV channels request")
        # Combine channels from all French providers
        all_channels = []
        
        # France.tv channels
        try:
            logger.info("🇫🇷 Getting France.tv channels...")
            francetv = ProviderFactory.create_provider("francetv")
            francetv_channels = francetv.get_live_channels()
            logger.info(f"✅ France.tv returned {len(francetv_channels)} channels")
            all_channels.extend(francetv_channels)
        except Exception as e:
            logger.error(f"❌ Error getting France.tv channels: {e}")
            _log_json_decode_details("France.tv channels:", e)
            logger.error(f"   Error type: {type(e).__name__}")
            logger.error(f"   Full traceback:")
            logger.error(traceback.format_exc())
            # Continue with other providers
        
        # TF1 channels
        try:
            logger.info("📺 Getting TF1 channels...")
            mytf1 = ProviderFactory.create_provider("mytf1")
            mytf1_channels = mytf1.get_live_channels()
            logger.info(f"✅ TF1 returned {len(mytf1_channels)} channels")
            all_channels.extend(mytf1_channels)
        except Exception as e:
            logger.error(f"❌ Error getting TF1 channels: {e}")
            _log_json_decode_details("TF1 channels:", e)
            logger.error(f"   Error type: {type(e).__name__}")
            logger.error(f"   Full traceback:")
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
            francetv = ProviderFactory.create_provider("francetv")
            shows = francetv.get_programs()
            logger.info(f"✅ France TV returned {len(shows)} shows")
            
            # The provider now returns enhanced metadata, so we can use it directly
            return CatalogResponse(metas=shows)
            
        except Exception as e:
            logger.error(f"❌ Error getting France TV replay shows: {e}")
            _log_json_decode_details("France TV replay:", e)
            logger.error(f"   Full traceback:")
            logger.error(traceback.format_exc())
            
            # Fallback to basic show list with enhanced metadata
            logger.info("🔄 Using fallback France TV shows")
            fallback_shows = [
                {
                    "id": "cutam:fr:francetv:envoye-special",
                    "type": "series",
                    "name": "Envoyé spécial",
                    "poster": f"{static_base}/static/logos/fr/france2.png",
                    "logo": f"{static_base}/static/logos/fr/france2.png",
                    "description": "Magazine d'information de France 2",
                    "genres": ["News", "Documentary", "Investigation"],
                    "year": 2024,
                    "rating": "Tous publics",
                    "channel": "France 2"
                },
                {
                    "id": "cutam:fr:francetv:cash-investigation",
                    "type": "series",
                    "name": "Cash Investigation",
                    "poster": f"{static_base}/static/logos/fr/france2.png",
                    "logo": f"{static_base}/static/logos/fr/france2.png",
                    "description": "Magazine d'investigation économique de France 2",
                    "genres": ["News", "Documentary", "Investigation", "Economics"],
                    "year": 2024,
                    "rating": "Tous publics",
                    "channel": "France 2"
                },
                {
                    "id": "cutam:fr:francetv:complement-enquete",
                    "type": "series",
                    "name": "Complément d'enquête",
                    "poster": f"{static_base}/static/logos/fr/france2.png",
                    "logo": f"{static_base}/static/logos/fr/france2.png",
                    "description": "Magazine d'investigation de France 2",
                    "genres": ["News", "Documentary", "Investigation"],
                    "year": 2024,
                    "rating": "Tous publics",
                    "channel": "France 2"
                }
            ]
            return CatalogResponse(metas=fallback_shows)
    
    # Return TF1+ TV show replays
    elif type == "series" and id == "fr-mytf1-replay":
        logger.info("📺 Processing TF1+ replay shows request")
        try:
            mytf1 = ProviderFactory.create_provider("mytf1")
            shows = mytf1.get_programs()
            logger.info(f"✅ TF1+ returned {len(shows)} shows")
            
            # The provider now returns enhanced metadata, so we can use it directly
            return CatalogResponse(metas=shows)
            
        except Exception as e:
            logger.error(f"❌ Error getting TF1+ replay shows: {e}")
            _log_json_decode_details("TF1+ replay:", e)
            logger.error(f"   Full traceback:")
            logger.error(traceback.format_exc())
            
            # Fallback to basic show list with enhanced metadata
            logger.info("🔄 Using fallback TF1+ shows")
            fallback_shows = [
                {
                    "id": "cutam:fr:mytf1:sept-a-huit",
                    "type": "series",
                    "name": "Sept à huit",
                    "poster": f"{static_base}/static/logos/fr/tf1.png",
                    "logo": f"{static_base}/static/logos/fr/tf1.png",
                    "description": "Magazine d'information de TF1",
                    "genres": ["News", "Documentary", "Magazine"],
                    "year": 2024,
                    "rating": "Tous publics",
                    "channel": "TF1"
                },
                {
                    "id": "cutam:fr:mytf1:quotidien",
                    "type": "series",
                    "name": "Quotidien",
                    "poster": f"{static_base}/static/logos/fr/tmc.png",
                    "logo": f"{static_base}/static/logos/fr/tmc.png",
                    "description": "Émission de divertissement et d'actualité de TMC",
                    "genres": ["Entertainment", "News", "Talk Show"],
                    "year": 2024,
                    "rating": "Tous publics",
                    "channel": "TMC"
                }
            ]
            return CatalogResponse(metas=fallback_shows)
    
    # Return 6play TV show replays
    elif type == "series" and id == "fr-6play-replay":
        logger.info("📺 Processing 6play replay shows request")
        try:
            sixplay = ProviderFactory.create_provider("6play")
            shows = sixplay.get_programs()
            logger.info(f"✅ 6play returned {len(shows)} shows")
            
            # The provider now returns enhanced metadata, so we can use it directly
            return CatalogResponse(metas=shows)
            
        except Exception as e:
            logger.error(f"❌ Error getting 6play replay shows: {e}")
            _log_json_decode_details("6play replay:", e)
            logger.error(f"   Full traceback:")
            logger.error(traceback.format_exc())
            
            # Fallback to basic show list with enhanced metadata
            logger.info("🔄 Using fallback 6play shows")
            fallback_shows = [
                {
                    "id": "cutam:fr:6play:capital",
                    "poster": "https://images-fio.6play.fr/v2/images/4654297/raw",
                    "logo": "https://images.6play.fr/v1/images/4242438/raw",
                    "description": "Magazine économique et financier de M6",
                    "genres": ["Économie", "Finance", "Magazine"],
                    "year": 2024,
                    "rating": "Tous publics",
                    "channel": "M6"
                },
                {
                    "id": "cutam:fr:6play:66-minutes",
                    "poster": "https://images-fio.6play.fr/v2/images/4654325/raw",
                    "logo": "https://images.6play.fr/v1/images/4654324/raw",
                    "description": "Magazine d'information de M6",
                    "genres": ["Information", "Magazine", "Actualité"],
                    "year": 2024,
                    "rating": "Tous publics",
                    "channel": "M6"
                },
                {
                    "id": "cutam:fr:6play:zone-interdite",
                    "poster": "https://images-fio.6play.fr/v2/images/4654281/raw",
                    "logo": "https://images.6play.fr/v1/images/4639961/raw",
                    "description": "Magazine d'investigation de M6",
                    "genres": ["Investigation", "Magazine", "Documentaire"],
                    "year": 2024,
                    "rating": "Tous publics",
                    "channel": "M6"
                },
                {
                    "id": "cutam:fr:6play:enquete-exclusive",
                    "poster": "https://images-fio.6play.fr/v2/images/4654307/raw",
                    "logo": "https://images.6play.fr/v1/images/4242429/raw",
                    "description": "Magazine d'investigation de M6",
                    "genres": ["Investigation", "Magazine", "Documentaire"],
                    "year": 2024,
                    "rating": "Tous publics",
                    "channel": "M6"
                }
            ]
            return CatalogResponse(metas=fallback_shows)
    
    logger.warning(f"⚠️ Unknown catalog request: type={type}, id={id}")
    return CatalogResponse(metas=[])