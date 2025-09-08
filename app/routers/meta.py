from fastapi import APIRouter, Request
import os
from app.schemas.stremio import MetaResponse, Video
from app.providers.common import ProviderFactory

router = APIRouter()

# Dragon's Den metadata configuration
DRAGONS_DEN_META = {
    "id": "cutam:ca:cbc:dragons-den",
    "name": "Dragon's Den",
    "description": "Canadian reality television series featuring entrepreneurs pitching their business ideas to a panel of venture capitalists",
    "poster": "https://scontent.fyto3-1.fna.fbcdn.net/v/t39.30808-6/535392832_1195964615903965_9196960806522485851_n.jpg?_nc_cat=103&ccb=1-7&_nc_sid=833d8c&_nc_ohc=d_n3zKCq_iQQ7kNvwH1mtas&_nc_oc=Adkf5Kz1pVRBkmob--lrYe20hyj1YEYyQr4PTCiLZBJpRyXOQojD6F0dGt06TAkdtDM&_nc_zt=23&_nc_ht=scontent.fyto3-1.fna&_nc_gid=qAJepOriBG4vRnuRQV4gDg&oh=00_Afav6IQ9z6RXP43ynmBGPGn6y7mGjXgQ7oJVOfpo9YoMfQ&oe=68C2E83B",
    "logo": "https://images.gem.cbc.ca/v1/synps-cbc/show/perso/cbc_dragons_den_ott_logo_v05.png?impolicy=ott&im=Resize=(_Size_)&quality=75",
    "background": "https://images.gem.cbc.ca/v1/synps-cbc/show/perso/cbc_dragons_den_ott_program_v12.jpg?impolicy=ott&im=Resize=1920&quality=75",
    "channel": "CBC",
    "genres": ["Reality", "Business", "Entrepreneurship"],
    "year": 2024,
    "rating": "G"
}

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
            print(f"Error getting France TV channel metadata: {e}")
        
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
            print(f"Error getting TF1 channel metadata: {e}")
        
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
            print(f"Error getting 6play channel metadata: {e}")
    
    # Handle France TV series metadata with enhanced episode handling
    elif type == "series" and "francetv" in id:
        try:
            provider = ProviderFactory.create_provider("francetv", request)
            
            # Extract show ID from the series ID
            if "envoye-special" in id:
                show_id = "envoye-special"
                show_name = "Envoyé spécial"
                show_description = "Magazine d'information de France 2"
                show_logo = f"{static_base}/static/logos/fr/france2.png"
                show_channel = "France 2"
                show_genres = ["News", "Documentary", "Investigation"]
            elif "cash-investigation" in id:
                show_id = "cash-investigation"
                show_name = "Cash Investigation"
                show_description = "Magazine d'investigation économique de France 2"
                show_logo = f"{static_base}/static/logos/fr/france2.png"
                show_channel = "France 2"
                show_genres = ["News", "Documentary", "Investigation", "Economics"]
            elif "complement-enquete" in id:
                show_id = "complement-enquete"
                show_name = "Complément d'enquête"
                show_description = "Magazine d'investigation de France 2"
                show_logo = f"{static_base}/static/logos/fr/france2.png"
                show_channel = "France 2"
                show_genres = ["News", "Documentary", "Investigation"]
            else:
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
                    "thumbnail": episode.get("poster", show_logo),
                    "description": episode.get("description", ""),
                    "duration": episode.get("duration", ""),
                    "broadcast_date": episode.get("broadcast_date", ""),
                    "rating": episode.get("rating", ""),
                    "director": episode.get("director", ""),
                    "cast": episode.get("cast", []),
                    "channel": episode.get("channel", show_channel),
                    "program": episode.get("program", show_name),
                    "type": episode.get("type", "episode")
                }
                videos.append(video_data)
            
            # Create enhanced series metadata
            series_meta = {
                "id": f"cutam:fr:francetv:prog:{show_id}",
                "type": "series",
                "name": show_name,
                "poster": show_logo,
                "logo": show_logo,
                "description": show_description,
                "channel": show_channel,
                "genres": show_genres,
                "year": 2024,
                "rating": "Tous publics",
                "videos": videos
            }
            
            # Try to get additional metadata from the provider
            try:
                provider_metadata = provider._get_show_api_metadata(f"france-2_{show_id}")
                if provider_metadata:
                    # Enhance with API metadata (images, etc.)
                    from app.utils.metadata import metadata_processor
                    series_meta = metadata_processor.enhance_metadata_with_api(series_meta, provider_metadata)
            except Exception as e:
                print(f"Warning: Could not enhance series metadata: {e}")
            
            return MetaResponse(meta=series_meta)
            
        except Exception as e:
            print(f"Error getting France TV series metadata: {e}")
            # Fallback to basic metadata with enhanced structure
            if "envoye-special" in id:
                return MetaResponse(
                    meta={
                        "id": "cutam:fr:francetv:envoye-special",
                        "type": "series",
                        "name": "Envoyé spécial",
                        "poster": f"{static_base}/static/logos/fr/france2.png",
                        "logo": f"{static_base}/static/logos/fr/france2.png",
                        "description": "Magazine d'information de France 2",
                        "channel": "France 2",
                        "genres": ["News", "Documentary", "Investigation"],
                        "year": 2024,
                        "rating": "Tous publics",
                        "videos": []
                    }
                )
            elif "cash-investigation" in id:
                return MetaResponse(
                    meta={
                        "id": "cutam:fr:francetv:cash-investigation",
                        "type": "series",
                        "name": "Cash Investigation",
                        "poster": f"{static_base}/static/logos/fr/france2.png",
                        "logo": f"{static_base}/static/logos/fr/france2.png",
                        "description": "Magazine d'investigation économique de France 2",
                        "channel": "France 2",
                        "genres": ["News", "Documentary", "Investigation", "Economics"],
                        "year": 2024,
                        "rating": "Tous publics",
                        "videos": []
                    }
                )
            elif "complement-enquete" in id:
                return MetaResponse(
                    meta={
                        "id": "cutam:fr:francetv:prog:complement-enquete",
                        "type": "series",
                        "name": "Complément d'enquête",
                        "poster": f"{static_base}/static/logos/fr/france2.png",
                        "logo": f"{static_base}/static/logos/fr/france2.png",
                        "description": "Magazine d'investigation de France 2",
                        "channel": "France 2",
                        "genres": ["News", "Documentary", "Investigation"],
                        "year": 2024,
                        "rating": "Tous publics",
                        "videos": []
                    }
                )
    
    # Handle TF1+ series metadata with enhanced episode handling
    elif type == "series" and "mytf1" in id:
        try:
            provider = ProviderFactory.create_provider("mytf1", request)
            
            # Extract show ID from the series ID
            if "sept-a-huit" in id:
                show_id = "sept-a-huit"
                show_name = "Sept à huit"
                show_description = "Magazine d'information de TF1"
                show_logo = f"{static_base}/static/logos/fr/tf1.png"
                show_channel = "TF1"
                show_genres = ["News", "Documentary", "Magazine"]
            elif "quotidien" in id:
                show_id = "quotidien"
                show_name = "Quotidien"
                show_description = "Émission de divertissement et d'actualité de TMC"
                show_logo = f"{static_base}/static/logos/fr/tmc.png"
                show_channel = "TMC"
                show_genres = ["Entertainment", "News", "Talk Show"]
            else:
                return {"meta": {}}
            
            # Get episodes for the show
            episodes = provider.get_episodes(f"cutam:fr:mytf1:{show_id}")
            
            # Convert episodes to Stremio video format with enhanced metadata
            videos = []
            for episode in episodes:
                video_data = {
                    "id": episode["id"],
                    "title": episode["title"],
                    "season": episode.get("season", 1),
                    "episode": episode.get("episode", len(videos) + 1),
                    "thumbnail": episode.get("poster", show_logo),
                    "description": episode.get("description", ""),
                    "duration": episode.get("duration", ""),
                    "broadcast_date": episode.get("broadcast_date", ""),
                    "rating": episode.get("rating", ""),
                    "director": episode.get("director", ""),
                    "cast": episode.get("cast", []),
                    "channel": episode.get("channel", show_channel),
                    "program": episode.get("program", show_name),
                    "type": episode.get("type", "episode")
                }
                videos.append(video_data)
            
            # Create enhanced series metadata
            series_meta = {
                "id": f"cutam:fr:mytf1:prog:{show_id}",
                "type": "series",
                "name": show_name,
                "poster": show_logo,
                "logo": show_logo,
                "description": show_description,
                "channel": show_channel,
                "genres": show_genres,
                "year": 2024,
                "rating": "Tous publics",
                "videos": videos
            }
            
            return MetaResponse(meta=series_meta)
            
        except Exception as e:
            print(f"Error getting TF1+ series metadata: {e}")
            # Fallback to basic metadata with enhanced structure
            if "sept-a-huit" in id:
                return MetaResponse(
                    meta={
                        "id": "cutam:fr:mytf1:sept-a-huit",
                        "type": "series",
                        "name": "Sept à huit",
                        "poster": f"{static_base}/static/logos/fr/tf1.png",
                        "logo": f"{static_base}/static/logos/fr/tf1.png",
                        "description": "Magazine d'information de TF1",
                        "channel": "TF1",
                        "genres": ["News", "Documentary", "Magazine"],
                        "year": 2024,
                        "rating": "Tous publics",
                        "videos": []
                    }
                )
            elif "quotidien" in id:
                return MetaResponse(
                    meta={
                        "id": "cutam:fr:mytf1:quotidien",
                        "type": "series",
                        "name": "Quotidien",
                        "poster": f"{static_base}/static/logos/fr/tmc.png",
                        "logo": f"{static_base}/static/logos/fr/tmc.png",
                        "description": "Émission de divertissement et d'actualité de TMC",
                        "channel": "TMC",
                        "genres": ["Entertainment", "News", "Talk Show"],
                        "year": 2024,
                        "rating": "Tous publics",
                        "videos": []
                    }
                )
    
    # Handle 6play series metadata
    elif type == "series" and "6play" in id:
        try:
            provider = ProviderFactory.create_provider("6play", request)
            
            # Extract show ID from the series ID
            if "capital" in id:
                show_id = "capital"
                show_name = "Capital"
                show_description = "Magazine économique et financier de M6"
                show_logo = "https://images.6play.fr/v1/images/4242438/raw"
                show_channel = "M6"
                show_genres = ["Économie", "Finance", "Magazine"]
            elif "66-minutes" in id:
                show_id = "66-minutes"
                show_name = "66 minutes"
                show_description = "Magazine d'information de M6"
                show_logo = "https://images.6play.fr/v1/images/4654324/raw"
                show_channel = "M6"
                show_genres = ["Information", "Magazine", "Actualité"]
            elif "zone-interdite" in id:
                show_id = "zone-interdite"
                show_name = "Zone Interdite"
                show_description = "Magazine d'investigation de M6"
                show_logo = "https://images.6play.fr/v1/images/4639961/raw"
                show_channel = "M6"
                show_genres = ["Investigation", "Magazine", "Documentaire"]
            elif "enquete-exclusive" in id:
                show_id = "enquete-exclusive"
                show_name = "Enquête Exclusive"
                show_description = "Magazine d'investigation de M6"
                show_logo = "https://images.6play.fr/v1/images/4242429/raw"
                show_channel = "M6"
                show_genres = ["Investigation", "Magazine", "Documentaire"]
            else:
                return {"meta": {}}
            
            # Get episodes for the show
            episodes = provider.get_episodes(f"cutam:fr:6play:{show_id}")
            
            # Convert episodes to Stremio video format with enhanced metadata
            videos = []
            for episode in episodes:
                video_data = {
                    "id": episode["id"],
                    "title": episode["title"],
                    "season": episode.get("season", 1),
                    "episode": episode.get("episode", len(videos) + 1),
                    "thumbnail": episode.get("poster", show_logo),
                    "description": episode.get("description", ""),
                    "duration": episode.get("duration", ""),
                    "broadcast_date": episode.get("broadcast_date", ""),
                    "rating": episode.get("rating", ""),
                    "director": episode.get("director", ""),
                    "cast": episode.get("cast", []),
                    "channel": episode.get("channel", show_channel),
                    "program": episode.get("program", show_name),
                    "type": episode.get("type", "episode")
                }
                videos.append(video_data)
            
            # Create enhanced series metadata
            series_meta = {
                "id": f"cutam:fr:6play:prog:{show_id}",
                "type": "series",
                "name": show_name,
                "poster": show_logo,
                "logo": show_logo,
                "description": show_description,
                "channel": show_channel,
                "genres": show_genres,
                "year": 2024,
                "rating": "Tous publics",
                "videos": videos
            }
            
            return MetaResponse(meta=series_meta)
            
        except Exception as e:
            print(f"Error getting 6play series metadata: {e}")
            # Fallback to basic metadata with enhanced structure
            if "capital" in id:
                return MetaResponse(
                    meta={
                        "id": "cutam:fr:6play:capital",
                        "type": "series",
                        "name": "Capital",
                        "poster": f"{static_base}/static/logos/fr/m6.png",
                        "logo": "https://images.6play.fr/v1/images/4242438/raw",
                        "description": "Magazine économique et financier de M6",
                        "channel": "M6",
                        "genres": ["Économie", "Finance", "Magazine"],
                        "year": 2024,
                        "rating": "Tous publics",
                        "videos": []
                    }
                )
            elif "66-minutes" in id:
                return MetaResponse(
                    meta={
                        "id": "cutam:fr:6play:66-minutes",
                        "type": "series",
                        "name": "66 minutes",
                        "poster": f"{static_base}/static/logos/fr/m6.png",
                        "logo": "https://images.6play.fr/v1/images/4654324/raw",
                        "description": "Magazine d'information de M6",
                        "channel": "M6",
                        "genres": ["Information", "Magazine", "Actualité"],
                        "year": 2024,
                        "rating": "Tous publics",
                        "videos": []
                    }
                )
            elif "zone-interdite" in id:
                return MetaResponse(
                    meta={
                        "id": "cutam:fr:6play:zone-interdite",
                        "type": "series",
                        "name": "Zone Interdite",
                        "poster": f"{static_base}/static/logos/fr/m6.png",
                        "logo": "https://images.6play.fr/v1/images/4639961/raw",
                        "description": "Magazine d'investigation de M6",
                        "channel": "M6",
                        "genres": ["Investigation", "Magazine", "Documentaire"],
                        "year": 2024,
                        "rating": "Tous publics",
                        "videos": []
                    }
                )
            elif "enquete-exclusive" in id:
                return MetaResponse(
                    meta={
                        "id": "cutam:fr:6play:enquete-exclusive",
                        "type": "series",
                        "name": "Enquête Exclusive",
                        "poster": f"{static_base}/static/logos/fr/m6.png",
                        "logo": "https://images.6play.fr/v1/images/4242429/raw",
                        "description": "Magazine d'investigation de M6",
                        "channel": "M6",
                        "genres": ["Investigation", "Magazine", "Documentaire"],
                        "year": 2024,
                        "rating": "Tous publics",
                        "videos": []
                    }
                )
    
    # Handle CBC Dragon's Den series metadata
    elif type == "series" and "cbc" in id and "dragons-den" in id:
        try:
            provider = ProviderFactory.create_provider("cbc", request)
            
            # Get episodes for the show
            episodes = provider.get_episodes(DRAGONS_DEN_META["id"])
            
            # Convert episodes to Stremio video format with enhanced metadata
            videos = []
            for episode in episodes:
                video_data = {
                    "id": episode["id"],
                    "title": episode["title"],
                    "season": episode.get("season", 1),
                    "episode": episode.get("episode", len(videos) + 1),
                    "thumbnail": episode.get("poster", DRAGONS_DEN_META["poster"]),
                    "overview": episode.get("description", ""),  # Use 'overview' field for Stremio episode descriptions
                    "description": episode.get("description", ""),  # Keep for backward compatibility
                    "summary": episode.get("description", ""),  # Keep for backward compatibility
                    "duration": episode.get("duration", ""),
                    "broadcast_date": episode.get("broadcast_date", ""),
                    "rating": episode.get("rating", ""),
                    "director": episode.get("director", ""),
                    "cast": episode.get("cast", []),
                    "channel": episode.get("channel", DRAGONS_DEN_META["channel"]),
                    "program": episode.get("program", DRAGONS_DEN_META["name"]),
                    "type": episode.get("type", "episode")
                }
                videos.append(video_data)
            
            # Create enhanced series metadata using the configuration
            series_meta = {
                **DRAGONS_DEN_META,  # Spread all the configuration values
                "type": "series",
                "videos": videos
            }
            
            return MetaResponse(meta=series_meta)
            
        except Exception as e:
            print(f"Error getting CBC Dragon's Den metadata: {e}")
            # Fallback to basic metadata
            return MetaResponse(
                        meta={
                            "id": "cutam:ca:cbc:dragons-den",
                            "type": "series",
                            "name": "Dragon's Den",
                            "poster": "https://scontent.fyto3-1.fna.fbcdn.net/v/t39.30808-6/535392832_1195964615903965_9196960806522485851_n.jpg?_nc_cat=103&ccb=1-7&_nc_sid=833d8c&_nc_ohc=d_n3zKCq_iQQ7kNvwH1mtas&_nc_oc=Adkf5Kz1pVRBkmob--lrYe20hyj1YEYyQr4PTCiLZBJpRyXOQojD6F0dGt06TAkdtDM&_nc_zt=23&_nc_ht=scontent.fyto3-1.fna&_nc_gid=qAJepOriBG4vRnuRQV4gDg&oh=00_Afav6IQ9z6RXP43ynmBGPGn6y7mGjXgQ7oJVOfpo9YoMfQ&oe=68C2E83B",
                            "logo": "https://images.gem.cbc.ca/v1/synps-cbc/show/perso/cbc_dragons_den_ott_logo_v05.png?impolicy=ott&im=Resize=(_Size_)&quality=75",
                            "background": "https://images.gem.cbc.ca/v1/synps-cbc/show/perso/cbc_dragons_den_ott_program_v12.jpg?impolicy=ott&im=Resize=1920&quality=75",
                            "description": "Canadian reality television series featuring entrepreneurs pitching their business ideas to a panel of venture capitalists",
                            "channel": "CBC",
                            "genres": ["Reality", "Business", "Entrepreneurship"],
                            "year": 2024,
                            "rating": "G",
                            "videos": []
                        }
                    )
    
    return {"meta": {}}