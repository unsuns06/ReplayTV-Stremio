from fastapi import APIRouter
from app.schemas.stremio import StreamResponse, Stream
from app.providers.fr.common import ProviderFactory

router = APIRouter()

@router.get("/stream/{type}/{id}.json")
async def get_stream(type: str, id: str):
    # Handle live streams
    if type == "channel":
        # Determine which provider based on the ID
        if "francetv" in id:
            provider = ProviderFactory.create_provider("francetv")
        elif "mytf1" in id:
            provider = ProviderFactory.create_provider("mytf1")
        elif "6play" in id:
            provider = ProviderFactory.create_provider("6play")
        else:
            return StreamResponse(streams=[])
        
        # Get the stream URL
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
            # Return fallback stream
            return StreamResponse(streams=[{
                "url": "https://example.com/stream-not-available.mp4",
                "title": "Stream not available"
            }])
    
    # Handle France TV replay streams
    elif type == "series" and "francetv" in id:
        try:
            provider = ProviderFactory.create_provider("francetv")
            
            # Extract episode ID from the series ID
            if "episode:" in id:
                episode_id = id
            else:
                # If it's a series ID, we need to get the first episode
                # This is a simplified approach - in a real scenario, you'd get the specific episode
                return StreamResponse(streams=[{
                    "url": "https://example.com/episode-not-specified.mp4",
                    "title": "Please select a specific episode"
                }])
            
            # Get stream URL for the episode
            stream_info = provider.get_episode_stream_url(episode_id)
            
            if stream_info:
                stream = Stream(
                    url=stream_info["url"],
                    title=f"{stream_info.get('manifest_type', 'hls').upper()} Stream"
                )
                return StreamResponse(streams=[stream])
            else:
                # Failed to get stream info
                return StreamResponse(streams=[{
                    "url": "https://example.com/stream-not-available.mp4",
                    "title": "Stream not available"
                }])
                
        except Exception as e:
            print(f"Error getting France TV stream: {e}")
            return StreamResponse(streams=[{
                "url": "https://example.com/error-stream.mp4",
                "title": "Error getting stream"
            }])
    
    # Handle TF1+ replay streams
    elif type == "series" and "mytf1" in id:
        try:
            provider = ProviderFactory.create_provider("mytf1")
            
            # Extract episode ID from the series ID
            if "episode:" in id:
                episode_id = id
            else:
                # If it's a series ID, we need to get the first episode
                return StreamResponse(streams=[{
                    "url": "https://example.com/episode-not-specified.mp4",
                    "title": "Please select a specific episode"
                }])
            
            # Get stream URL for the episode
            stream_info = provider.get_episode_stream_url(episode_id)
            
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
                # Failed to get stream info
                return StreamResponse(streams=[{
                    "url": "https://example.com/stream-not-available.mp4",
                    "title": "Stream not available"
                }])
                
        except Exception as e:
            print(f"Error getting TF1+ stream: {e}")
            return StreamResponse(streams=[{
                "url": "https://example.com/error-stream.mp4",
                "title": "Error getting stream"
            }])
    
    # Handle 6play replay streams
    elif type == "series" and "6play" in id:
        try:
            provider = ProviderFactory.create_provider("6play")
            
            # Extract episode ID from the series ID
            if "episode:" in id:
                episode_id = id
            else:
                # If it's a series ID, we need to get the first episode
                return StreamResponse(streams=[{
                    "url": "https://example.com/episode-not-specified.mp4",
                    "title": "Please select a specific episode"
                }])
            
            # Get stream URL for the episode
            stream_info = provider.get_episode_stream_url(episode_id)
            
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
                # Failed to get stream info
                return StreamResponse(streams=[{
                    "url": "https://example.com/stream-not-available.mp4",
                    "title": "Stream not available"
                }])
                
        except Exception as e:
            print(f"Error getting 6play stream: {e}")
            return StreamResponse(streams=[{
                "url": "https://example.com/error-stream.mp4",
                "title": "Error getting stream"
            }])
    
    return StreamResponse(streams=[])