from fastapi import APIRouter, Request
import logging
import traceback
from app.schemas.stremio import StreamResponse, Stream
from app.providers.common import ProviderFactory
from app.utils.client_ip import make_ip_headers

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/stream/{type}/{id}.json")
async def get_stream(type: str, id: str, request: Request):
    """Get stream data with comprehensive error logging"""
    logger.info(f"🔍 STREAM REQUEST: type={type}, id={id}")
    
    # Handle live streams
    if type == "channel":
        logger.info(f"📺 Processing live stream request for channel: {id}")
        
        # Determine which provider based on the ID
        if "francetv" in id:
            provider_name = "France TV"
            provider = ProviderFactory.create_provider("francetv", request)
        elif "mytf1" in id:
            provider_name = "MyTF1"
            provider = ProviderFactory.create_provider("mytf1", request)
        elif "6play" in id:
            provider_name = "6play"
            provider = ProviderFactory.create_provider("6play", request)
        else:
            logger.warning(f"⚠️ Unknown channel provider in ID: {id}")
            return StreamResponse(streams=[])
        
        logger.info(f"🎯 Using {provider_name} provider for channel: {id}")
        
        try:
            # Get the stream URL
            stream_info = provider.get_channel_stream_url(id)
            
            if stream_info:
                logger.info(f"✅ {provider_name} returned stream info: {stream_info.get('manifest_type', 'unknown')}")
                
                # Merge any provider-specified headers with viewer IP headers
                merged_headers = {}
                if stream_info.get('headers'):
                    merged_headers.update(stream_info.get('headers'))
                merged_headers.update(make_ip_headers())

                # Merge license headers too, if provided
                merged_license_headers = None
                if stream_info.get('licenseHeaders'):
                    merged_license_headers = dict(stream_info.get('licenseHeaders'))
                    merged_license_headers.update(make_ip_headers())

                stream = Stream(
                    url=stream_info["url"],
                    title=f"{stream_info.get('manifest_type', 'hls').upper()} Stream",
                    headers= merged_headers if merged_headers else None,
                    manifest_type=stream_info.get('manifest_type'),
                    licenseUrl=stream_info.get('licenseUrl'),
                    licenseHeaders=merged_license_headers
                )
                return StreamResponse(streams=[stream])
            else:
                logger.warning(f"⚠️ {provider_name} returned no stream info for channel: {id}")
                # Return fallback stream
                return StreamResponse(streams=[{
                    "url": "https://example.com/stream-not-available.mp4",
                    "title": "Stream not available"
                }])
                
        except Exception as e:
            logger.error(f"❌ Error getting {provider_name} stream for channel {id}: {e}")
            logger.error(f"   Full traceback:")
            logger.error(traceback.format_exc())
            
            # Return fallback stream
            return StreamResponse(streams=[{
                "url": "https://example.com/error-stream.mp4",
                "title": "Error getting stream"
            }])
    
    # Handle France TV replay streams
    elif type == "series" and "francetv" in id:
        logger.info(f"📺 Processing France TV replay stream request: {id}")
        try:
            provider = ProviderFactory.create_provider("francetv", request)
            
            # Extract episode ID from the series ID
            if "episode:" in id:
                episode_id = id
                logger.info(f"🎬 Getting stream for specific episode: {episode_id}")
            else:
                logger.warning(f"⚠️ No episode specified in series ID: {id}")
                # If it's a series ID, we need to get the first episode
                return StreamResponse(streams=[{
                    "url": "https://example.com/episode-not-specified.mp4",
                    "title": "Please select a specific episode"
                }])
            
            # Get stream URL for the episode
            stream_info = provider.get_episode_stream_url(episode_id)
            
            if stream_info:
                logger.info(f"✅ France TV returned stream info: {stream_info.get('manifest_type', 'unknown')}")
                stream = Stream(
                    url=stream_info["url"],
                    title=f"{stream_info.get('manifest_type', 'hls').upper()} Stream"
                )
                return StreamResponse(streams=[stream])
            else:
                logger.warning(f"⚠️ France TV returned no stream info for episode: {episode_id}")
                # Failed to get stream info
                return StreamResponse(streams=[{
                    "url": "https://example.com/stream-not-available.mp4",
                    "title": "Stream not available"
                }])
                
        except Exception as e:
            logger.error(f"❌ Error getting France TV stream: {e}")
            logger.error(f"   Full traceback:")
            logger.error(traceback.format_exc())
            return StreamResponse(streams=[{
                "url": "https://example.com/error-stream.mp4",
                "title": "Error getting stream"
            }])
    
    # Handle TF1+ replay streams
    elif type == "series" and "mytf1" in id:
        logger.info(f"📺 Processing TF1+ replay stream request: {id}")
        try:
            provider = ProviderFactory.create_provider("mytf1", request)
            
            # Extract episode ID from the series ID
            if "episode:" in id:
                episode_id = id
                logger.info(f"🎬 Getting stream for specific episode: {episode_id}")
            else:
                logger.warning(f"⚠️ No episode specified in series ID: {id}")
                # If it's a series ID, we need to get the first episode
                return StreamResponse(streams=[{
                    "url": "https://example.com/episode-not-specified.mp4",
                    "title": "Please select a specific episode"
                }])
            
            # Get stream URL for the episode
            stream_info = provider.get_episode_stream_url(episode_id)
            
            if stream_info:
                logger.info(f"✅ TF1+ returned stream info: {stream_info.get('manifest_type', 'unknown')}")

                # Merge any provider-specified headers with viewer IP headers
                merged_headers = {}
                if stream_info.get('headers'):
                    merged_headers.update(stream_info.get('headers'))
                merged_headers.update(make_ip_headers())

                # Merge license headers too, if provided
                merged_license_headers = None
                if stream_info.get('licenseHeaders'):
                    merged_license_headers = dict(stream_info.get('licenseHeaders'))
                    merged_license_headers.update(make_ip_headers())

                stream = Stream(
                    url=stream_info["url"],
                    title=f"{stream_info.get('manifest_type', 'hls').upper()} Stream",
                    headers= merged_headers if merged_headers else None,
                    manifest_type=stream_info.get('manifest_type'),
                    licenseUrl=stream_info.get('licenseUrl'),
                    licenseHeaders=merged_license_headers
                )
                return StreamResponse(streams=[stream])
            else:
                logger.warning(f"⚠️ TF1+ returned no stream info for episode: {episode_id}")
                # Failed to get stream info
                return StreamResponse(streams=[{
                    "url": "https://example.com/stream-not-available.mp4",
                    "title": "Stream not available"
                }])
                
        except Exception as e:
            logger.error(f"❌ Error getting TF1+ stream: {e}")
            logger.error(f"   Full traceback:")
            logger.error(traceback.format_exc())
            return StreamResponse(streams=[{
                "url": "https://example.com/error-stream.mp4",
                "title": "Error getting stream"
            }])
    
    # Handle 6play replay streams
    elif type == "series" and "6play" in id:
        logger.info(f"📺 Processing 6play replay stream request: {id}")
        try:
            provider = ProviderFactory.create_provider("6play", request)
            
            # Extract episode ID from the series ID
            if "episode:" in id:
                episode_id = id
                logger.info(f"🎬 Getting stream for specific episode: {episode_id}")
            else:
                logger.warning(f"⚠️ No episode specified in series ID: {id}")
                # If it's a series ID, we need to get the first episode
                return StreamResponse(streams=[{
                    "url": "https://example.com/episode-not-specified.mp4",
                    "title": "Please select a specific episode"
                }])
            
            # Get stream URL for the episode
            stream_info = provider.get_episode_stream_url(episode_id)
            
            if stream_info:
                logger.info(f"✅ 6play returned stream info: {stream_info.get('manifest_type', 'unknown')}")
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
                logger.warning(f"⚠️ 6play returned no stream info for episode: {episode_id}")
                # Failed to get stream info
                return StreamResponse(streams=[{
                    "url": "https://example.com/stream-not-available.mp4",
                    "title": "Stream not available"
                }])
                
        except Exception as e:
            logger.error(f"❌ Error getting 6play stream: {e}")
            logger.error(f"   Full traceback:")
            logger.error(traceback.format_exc())
            return StreamResponse(streams=[{
                "url": "https://example.com/error-stream.mp4",
                "title": "Error getting stream"
            }])
    
    # Handle CBC Dragon's Den streams
    elif type == "series" and "cbc" in id and "dragons-den" in id:
        logger.info(f"📺 Processing CBC Dragon's Den stream request: {id}")
        try:
            provider = ProviderFactory.create_provider("cbc", request)
            
            # Extract episode ID from the series ID
            if "episode-" in id:
                episode_id = id
                logger.info(f"🎬 Getting stream for specific episode: {episode_id}")
            else:
                logger.warning(f"⚠️ No episode specified in series ID: {id}")
                return StreamResponse(streams=[{
                    "url": "https://example.com/episode-not-specified.mp4",
                    "title": "Please select a specific episode"
                }])
            
            # Run debug trace for better logging
            try:
                debug_info = provider.debug_episode_stream(episode_id)
                for step in debug_info.get("steps", []):
                    logger.info(f"DEBUG: {step}")
            except Exception:
                pass
            
            # Get stream URL for the episode
            stream_info = provider.get_episode_stream_url(episode_id)
            
            if stream_info:
                logger.info(f"✅ CBC returned stream info: {stream_info.get('manifest_type', 'unknown')}")
                
                # Merge any provider-specified headers with viewer IP headers
                merged_headers = {}
                if stream_info.get('headers'):
                    merged_headers.update(stream_info.get('headers'))
                merged_headers.update(make_ip_headers())

                # Merge license headers too, if provided
                merged_license_headers = None
                if stream_info.get('licenseHeaders'):
                    merged_license_headers = dict(stream_info.get('licenseHeaders'))
                    merged_license_headers.update(make_ip_headers())

                stream = Stream(
                    url=stream_info["url"],
                    title=f"{stream_info.get('manifest_type', 'hls').upper()} Stream",
                    headers=merged_headers if merged_headers else None,
                    manifest_type=stream_info.get('manifest_type'),
                    licenseUrl=stream_info.get('licenseUrl'),
                    licenseHeaders=merged_license_headers
                )
                return StreamResponse(streams=[stream])
            else:
                logger.warning(f"⚠️ CBC returned no stream info for episode: {episode_id}")
                # Failed to get stream info
                return StreamResponse(streams=[{
                    "url": "https://example.com/stream-not-available.mp4",
                    "title": "Stream not available"
                }])
                
        except Exception as e:
            logger.error(f"❌ Error getting CBC Dragon's Den stream: {e}")
            logger.error(f"   Full traceback:")
            logger.error(traceback.format_exc())
            return StreamResponse(streams=[{
                "url": "https://example.com/error-stream.mp4",
                "title": "Error getting stream"
            }])
    
    # Handle CBC Dragon's Den streams
    elif type == "series" and "cbc" in id and "dragons-den" in id:
        logger.info(f"📺 Processing CBC Dragon's Den stream request: {id}")
        try:
            provider = ProviderFactory.create_provider("cbc", request)
            
            # Extract episode ID from the series ID
            if "episode-" in id:
                episode_id = id
                logger.info(f"🎬 Getting stream for specific episode: {episode_id}")
            else:
                logger.warning(f"⚠️ No episode specified in series ID: {id}")
                return StreamResponse(streams=[{
                    "url": "https://example.com/episode-not-specified.mp4",
                    "title": "Please select a specific episode"
                }])
            
            # Run debug trace for better logging
            try:
                debug_info = provider.debug_episode_stream(episode_id)
                for step in debug_info.get("steps", []):
                    logger.info(f"DEBUG: {step}")
            except Exception:
                pass
            
            # Get stream URL for the episode
            stream_info = provider.get_episode_stream_url(episode_id)
            
            if stream_info:
                logger.info(f"✅ CBC returned stream info: {stream_info.get('manifest_type', 'unknown')}")
                
                # Merge any provider-specified headers with viewer IP headers
                merged_headers = {}
                if stream_info.get('headers'):
                    merged_headers.update(stream_info.get('headers'))
                merged_headers.update(make_ip_headers())

                # Merge license headers too, if provided
                merged_license_headers = None
                if stream_info.get('licenseHeaders'):
                    merged_license_headers = dict(stream_info.get('licenseHeaders'))
                    merged_license_headers.update(make_ip_headers())

                stream = Stream(
                    url=stream_info["url"],
                    title=f"{stream_info.get('manifest_type', 'hls').upper()} Stream",
                    headers=merged_headers if merged_headers else None,
                    manifest_type=stream_info.get('manifest_type'),
                    licenseUrl=stream_info.get('licenseUrl'),
                    licenseHeaders=merged_license_headers
                )
                return StreamResponse(streams=[stream])
            else:
                logger.warning(f"⚠️ CBC returned no stream info for episode: {episode_id}")
                # Failed to get stream info
                return StreamResponse(streams=[{
                    "url": "https://example.com/stream-not-available.mp4",
                    "title": "Stream not available"
                }])
                
        except Exception as e:
            logger.error(f"❌ Error getting CBC Dragon's Den stream: {e}")
            logger.error(f"   Full traceback:")
            logger.error(traceback.format_exc())
            return StreamResponse(streams=[{
                "url": "https://example.com/error-stream.mp4",
                "title": "Error getting stream"
            }])
    
    logger.warning(f"⚠️ Unknown stream request: type={type}, id={id}")
    return StreamResponse(streams=[])
