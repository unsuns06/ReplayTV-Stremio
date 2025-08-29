from fastapi import APIRouter
import os
from app.schemas.stremio import CatalogResponse
from app.providers.fr.common import ProviderFactory

router = APIRouter()

@router.get("/catalog/{type}/{id}.json")
async def get_catalog(type: str, id: str):
    # Get base URL for static assets
    static_base = os.getenv('ADDON_BASE_URL', 'http://localhost:7860')
    
    # Get live TV channels
    if type == "channel" and id == "fr-live":
        # Combine channels from all French providers
        all_channels = []
        
        # France.tv channels
        try:
            francetv = ProviderFactory.create_provider("francetv")
            all_channels.extend(francetv.get_live_channels())
        except Exception as e:
            print(f"Error getting France.tv channels: {e}")
        
        # TF1 channels
        try:
            mytf1 = ProviderFactory.create_provider("mytf1")
            all_channels.extend(mytf1.get_live_channels())
        except Exception as e:
            print(f"Error getting TF1 channels: {e}")
        
        
        return CatalogResponse(metas=all_channels)
    
    # Return France 2 TV show replays with enhanced metadata
    elif type == "series" and id == "fr-francetv-replay":
        try:
            francetv = ProviderFactory.create_provider("francetv")
            shows = francetv.get_programs()
            
            # The provider now returns enhanced metadata, so we can use it directly
            return CatalogResponse(metas=shows)
            
        except Exception as e:
            print(f"Error getting France TV replay shows: {e}")
            # Fallback to basic show list with enhanced metadata
            return CatalogResponse(
                metas=[
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
            )
    
    # Return TF1+ TV show replays
    elif type == "series" and id == "fr-mytf1-replay":
        try:
            mytf1 = ProviderFactory.create_provider("mytf1")
            shows = mytf1.get_programs()
            
            # The provider now returns enhanced metadata, so we can use it directly
            return CatalogResponse(metas=shows)
            
        except Exception as e:
            print(f"Error getting TF1+ replay shows: {e}")
            # Fallback to basic show list with enhanced metadata
            return CatalogResponse(
                metas=[
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
            )
    
    # Return 6play TV show replays
    elif type == "series" and id == "fr-6play-replay":
        try:
            sixplay = ProviderFactory.create_provider("6play")
            shows = sixplay.get_programs()
            
            # The provider now returns enhanced metadata, so we can use it directly
            return CatalogResponse(metas=shows)
            
        except Exception as e:
            print(f"Error getting 6play replay shows: {e}")
            # Fallback to basic show list with enhanced metadata
            return CatalogResponse(
                metas=[
                    {
                        "id": "cutam:fr:6play:capital",
                        "type": "series",
                        "name": "Capital",
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
                        "type": "series",
                        "name": "66 minutes",
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
                        "type": "series",
                        "name": "Zone Interdite",
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
                        "type": "series",
                        "name": "Enquête Exclusive",
                        "poster": "https://images-fio.6play.fr/v2/images/4654307/raw",
                        "logo": "https://images.6play.fr/v1/images/4242429/raw",
                        "description": "Magazine d'investigation de M6",
                        "genres": ["Investigation", "Magazine", "Documentaire"],
                        "year": 2024,
                        "rating": "Tous publics",
                        "channel": "M6"
                    }
                ]
            )
    
    return CatalogResponse(metas=[])