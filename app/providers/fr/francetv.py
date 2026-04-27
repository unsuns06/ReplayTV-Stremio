#!/usr/bin/env python3
"""
France TV provider implementation
Hybrid approach with robust error handling, fallbacks, and retry logic
"""
import logging
import html
import json
import os
import traceback
from datetime import datetime
from typing import Dict, List, Optional
from urllib.parse import urlencode, quote
from fastapi import Request
from app.providers.fr.metadata import metadata_processor, image_extractor
from app.utils.base_url import get_base_url, get_logo_url
from app.utils.user_agent import get_random_windows_ua
from app.utils.api_client import ProviderAPIClient
from app.utils.programs_loader import get_programs_for_provider
from app.providers.base_provider import BaseProvider

logger = logging.getLogger(__name__)

class FranceTVProvider(BaseProvider):
    """France TV provider implementation with robust error handling and fallbacks"""
    
    # Class attributes for BaseProvider
    provider_name = "francetv"
    base_url = "https://www.france.tv"
    country = "fr"
    
    # Metadata
    display_name = "France TV"
    id_prefix = "cutam:fr:francetv"
    episode_marker = "episode:"
    catalog_id = "fr-francetv-replay"
    supports_live = True

    
    def __init__(self, request: Optional[Request] = None):
        # Initialize base class (handles credentials, session, proxy_config, mediaflow)
        super().__init__(request)
        
        # France TV specific API endpoints
        self.api_mobile = "https://api-mobile.yatta.francetv.fr"
        self.api_front = "http://api-front.yatta.francetv.fr"
        
        # Get base URL for static assets
        self.static_base = get_base_url(request)
        
        # Load shows from external programs.json
        self.shows = get_programs_for_provider('francetv')
        
        # Fallback channel data for when APIs fail
        self.fallback_channels = {
            "france-2": {
                "id": "006194ea-117d-4bcf-94a9-153d999c59ae",
                "name": "France 2",
                "logo": get_logo_url("fr", "france2", self.request)
            },
            "france-3": {
                "id": "29bdf749-7082-4426-a4f3-595cc436aa0d",
                "name": "France 3", 
                "logo": get_logo_url("fr", "france3", self.request)
            },
            "france-4": {
                "id": "9a6a7670-dde9-4264-adbc-55b89558594b",
                "name": "France 4",
                "logo": get_logo_url("fr", "france4", self.request)
            },
            "france-5": {
                "id": "45007886-f3ff-4b3e-9706-1ef1014c5a60",
                "name": "France 5",
                "logo": get_logo_url("fr", "france5", self.request)
            },
            "franceinfo": {
                "id": "35be22fb-1569-43ff-857c-99bf81defa2e",
                "name": "franceinfo:",
                "logo": get_logo_url("fr", "franceinfo", self.request)
            }
        }
    
    def get_programs(self) -> List[Dict]:
        """Get list of replay shows with enhanced metadata (parallel API fetching)"""
        shows = []
        
        def fetch_api_metadata(item):
            """Fetch API metadata for a single show."""
            show_id, show_info = item
            api_show_id = show_info.get('api_id') or show_info.get('id', show_id)
            try:
                return (show_id, self._get_show_api_metadata(api_show_id))
            except Exception as e:
                logger.warning(f"⚠️ [FranceTV] Warning: Could not fetch API metadata for {show_id}: {e}")
                return (show_id, None)
        
        # Fetch all API metadata in parallel
        api_results = dict(self._parallel_map(fetch_api_metadata, self.shows.items()))
        
        # Build shows using fetched metadata
        for show_id, show_info in self.shows.items():
            # Get base metadata from our enhanced show info
            show_metadata = metadata_processor.get_show_metadata(
                f"cutam:fr:francetv:{show_id}", 
                show_info
            )
            
            # Apply API metadata if available
            api_metadata = api_results.get(show_id)
            if api_metadata:
                show_metadata = metadata_processor.enhance_metadata_with_api(
                    show_metadata, api_metadata
                )
                # Apply logo if extracted from API
                if api_metadata.get('logo'):
                    show_metadata['logo'] = api_metadata['logo']
            
            shows.append(show_metadata)
        
        return shows
    
    def _get_show_api_metadata(self, show_api_id: str) -> Optional[Dict]:
        """Get additional metadata for a show from France TV API with error handling"""
        try:
            # Get show information from the front API
            api_url = f"{self.api_front}/standard/publish/taxonomies/{show_api_id}"
            params = {'platform': 'apps'}
            
            data = self.api_client.get(api_url, params=params)
            if not data:
                return None
            
            # Extract show metadata
            images = data.get('media_image', {}).get('patterns', []) if 'media_image' in data else []
            description = data.get('description', '')
            text = data.get('seo', '')  # SEO field often contains rich text
            
            extracted = image_extractor.extract(images, {"logo": "logo"})
            metadata = {
                'images': images,
                'description': description,
                'text': text,
                'logo': extracted.get('logo'),
            }
            
            return metadata
            
        except Exception as e:
            logger.error(f"❌ [FranceTV] Error getting show API metadata: {e}")
            return None
    
    def _get_channel_images(self, channel_id: str) -> Dict[str, str]:
        """Get poster and logo images for a channel from the FranceTV API.
        
        Args:
            channel_id: Channel identifier (e.g., 'france-2', 'franceinfo')
            
        Returns:
            Dict with 'poster' and 'logo' URLs, or empty strings if not found
        """
        try:
            api_url = f"{self.api_front}/standard/publish/taxonomies/{channel_id}"
            params = {'platform': 'apps'}
            
            data = self.api_client.get(api_url, params=params)
            if not data:
                return {'poster': '', 'logo': ''}
            
            images = data.get('media_image', {}).get('patterns', []) if 'media_image' in data else []
            extracted = image_extractor.extract(images, {"poster": "vignette_3x4", "logo": "logo"})
            return {'poster': extracted.get('poster', ''), 'logo': extracted.get('logo', '')}
            
        except Exception as e:
            logger.error(f"❌ [FranceTV] Error getting channel images for {channel_id}: {e}")
            return {'poster': '', 'logo': ''}
    
    def get_live_channels(self) -> List[Dict]:
        """Get list of live TV channels from France TV with dynamic images from API (parallel fetching)"""
        channels = []
        
        # France TV live channels configuration
        channel_configs = [
            {
                "id": "cutam:fr:francetv:france-2",
                "channel_api_id": "france-2",
                "name": "France 2",
                "fallback_logo": "france2",
                "description": "Chaîne de télévision française de service public"
            },
            {
                "id": "cutam:fr:francetv:france-3",
                "channel_api_id": "france-3",
                "name": "France 3",
                "fallback_logo": "france3",
                "description": "Chaîne de télévision française de service public"
            },
            {
                "id": "cutam:fr:francetv:france-4",
                "channel_api_id": "france-4",
                "name": "France 4",
                "fallback_logo": "france4",
                "description": "Chaîne de télévision française de service public"
            },
            {
                "id": "cutam:fr:francetv:france-5",
                "channel_api_id": "france-5",
                "name": "France 5",
                "fallback_logo": "france5",
                "description": "Chaîne de télévision française de service public"
            },
            {
                "id": "cutam:fr:francetv:franceinfo",
                "channel_api_id": "franceinfo",
                "name": "franceinfo:",
                "fallback_logo": "franceinfo",
                "description": "Chaîne d'information continue française de service public"
            }
        ]
        
        def fetch_images(cfg):
            """Fetch images for a single channel."""
            return (cfg["id"], self._get_channel_images(cfg["channel_api_id"]))
        
        # Fetch all channel images in parallel
        image_results = dict(self._parallel_map(fetch_images, channel_configs))
        
        # Build channels using fetched images (preserving original order)
        for config in channel_configs:
            images = image_results.get(config["id"], {})
            
            # Use API images if available, otherwise fallback to static logos
            fallback_url = get_logo_url("fr", config["fallback_logo"], self.request)
            poster = images.get('poster') or fallback_url
            logo = images.get('logo') or fallback_url
            
            channels.append({
                "id": config["id"],
                "type": "channel",
                "name": config["name"],
                "poster": poster,
                "logo": logo,
                "description": config["description"]
            })
        
        return channels
    
    def _get_broadcast_id(self, channel_name: str) -> tuple:
        """Look up the live broadcast ID and current programme title for *channel_name*.

        Tries three sources in order:
        1. Mobile API  (``api-mobile.yatta.francetv.fr``)
        2. Front API   (``api-front.yatta.francetv.fr``)
        3. Hard-coded ``fallback_channels`` dict

        Returns:
            ``(broadcast_id, current_program_title)`` — either value may be ``None``.
        """
        broadcast_id = None
        current_program_title = None

        try:
            data = self.api_client.get(
                f"{self.api_mobile}/apps/channels/{channel_name}",
                params={'platform': 'apps'},
            )
            if data:
                for collection in data.get('collections', []):
                    if collection.get('type') == 'live':
                        items = collection.get('items', [])
                        if items:
                            current_program_title = items[0].get('title', '')
                            ch = items[0].get('channel', {})
                            if ch.get('si_id'):
                                broadcast_id = ch['si_id']
                        break
        except Exception as e:
            logger.error(f"   ⚠️ Mobile API failed: {e}")

        if not broadcast_id:
            try:
                data = self.api_client.get(f"{self.api_front}/standard/edito/directs")
                if data:
                    for live in data.get('result', []):
                        if live.get('channel') == channel_name:
                            collections = live.get('collection', [])
                            if collections and not current_program_title:
                                current_program_title = collections[0].get('title', '')
                            for m in (collections[0].get('content_has_medias', []) if collections else []):
                                if 'si_direct_id' in m.get('media', {}):
                                    broadcast_id = m['media']['si_direct_id']
                                    break
                            break
            except Exception as e:
                logger.error(f"   ⚠️ Front API failed: {e}")

        if not broadcast_id:
            broadcast_id = self.fallback_channels.get(channel_name, {}).get('id')

        return broadcast_id, current_program_title

    def get_live_stream_url(self, channel_id: str) -> Optional[Dict]:
        """Get live stream URL for a specific channel with robust error handling and fallbacks"""
        logger.debug(f"🔍 [FranceTV] Getting live stream for {channel_id}")
        try:
            channel_name = channel_id.split(":")[-1]
            broadcast_id, current_program_title = self._get_broadcast_id(channel_name)

            if not broadcast_id:
                logger.error(f"   ❌ No broadcast ID found for {channel_name}")
                return None
            
            # Get video info from API (same as reference)
            # Try with proxy first for geo-blocking bypass, fallback to direct if needed
            video_url = f"https://k7.ftven.fr/videos/{broadcast_id}"
            params = {
                'country_code': 'FR',
                'os': 'androidtv',
                'diffusion_mode': 'tunnel_first',
                'offline': 'false',
            }
            
            logger.debug(f"   Video API URL: {video_url}")
            video_data = self.api_client.get(video_url, params=params, max_retries=2)

            if video_data and 'video' in video_data:
                video_info = video_data['video']
                logger.debug(f"   Video info keys: {list(video_info.keys())}")
                
                # Handle token field like reference implementation
                token_field = video_info.get('token', {})
                if isinstance(token_field, dict):
                    if 'akamai' in token_field:
                        url_token = token_field['akamai']
                    else:
                        url_token = "https://hdfauth.ftven.fr/esi/TA"
                else:
                    # older style string token
                    url_token = token_field or "https://hdfauth.ftven.fr/esi/TA"
                
                logger.debug(f"   Using token URL: {url_token}")
                
                # Get the actual stream URL
                token_params = {
                    'format': 'json',
                    'url': video_info.get('url', '')
                }
                
                logger.debug(f"   Token API params: {token_params}")
                token_data = self.api_client.get(url_token, params=token_params, max_retries=2)
                
                if token_data and 'url' in token_data:
                    final_url = token_data['url']
                    
                    if final_url:
                        # Determine manifest type
                        manifest_type = 'hls' if 'hls' in video_info.get('format', []) else 'mpd'
                        format_label = 'HLS' if manifest_type == 'hls' else 'MPD'

                        # Build enhanced title: [FORMAT] Current Program Name
                        # Falls back to channel name if no EPG data available
                        if current_program_title:
                            stream_title = f"[{format_label}] {current_program_title}"
                        else:
                            stream_title = f"[{format_label}] {channel_name.upper()}"

                        result = {
                            "url": final_url,
                            "manifest_type": manifest_type,
                            "title": stream_title
                        }
                        logger.debug(f"   ✅ Returning result: {result}")
                        return result
                    else:
                        logger.error(f"   ❌ No final URL in token response")
                else:
                    logger.error(f"   ❌ Token API failed or no URL found")
            else:
                logger.error(f"   ❌ No 'video' key in response or API failed")
            
            logger.error(f"   ❌ Returning None")
            return None
            
        except Exception as e:
            logger.error(f"❌ Error getting live stream for {channel_id}: {e}")
            traceback.print_exc()
            return None
    
    def get_channel_stream_url(self, channel_id: str) -> Optional[Dict]:
        """Get channel stream URL - wrapper for get_live_stream_url"""
        return self.get_live_stream_url(channel_id)
    
    def get_episodes(self, show_id: str) -> List[Dict]:
        """Get episodes for a specific show with enhanced metadata and fallbacks"""
        # Extract the actual show ID from our format
        actual_show_id = show_id.split(":")[-1]
        
        if actual_show_id not in self.shows:
            return []
        
        try:
            # Get the api_id for API calls (e.g., france-2_cash-investigation)
            show_info = self.shows[actual_show_id]
            api_show_id = show_info.get('api_id') or show_info.get('id', actual_show_id)
            
            # Use the same API endpoint as the source addon with error handling
            # URL example: http://api-front.yatta.francetv.fr/standard/publish/taxonomies/france-2_cash-investigation/contents/?size=20&page=0&sort=begin_date:desc&filter=with-no-vod,only-visible
            api_url = f"{self.api_front}/standard/publish/taxonomies/{api_show_id}/contents/"
            params = {
                'size': 20,
                'page': 0,
                'filter': "with-no-vod,only-visible",
                'sort': "begin_date:desc"
            }
            
            data = self.api_client.get(api_url, params=params)
            
            if data and 'result' in data:
                episodes = []
                
                # Parse the response to get episodes (same logic as source addon)
                for video in data['result']:
                    if video['type'] in ['integrale', 'extrait']:
                        # This is a video/episode - pass raw data first, episode number assigned later
                        episode_info = self._parse_episode(video, 0)
                        if episode_info:
                            episodes.append(episode_info)
                
                if episodes:
                    # Sort episodes chronologically by released date (oldest first, newest last)
                    # Use 'released' for full timestamp, fallback to 'air_date' if not available
                    episodes.sort(key=lambda x: x.get('released', '') or x.get('air_date', '') or '')
                    
                    # Assign episode numbers based on chronological order (1 = oldest, highest = newest)
                    for i, ep in enumerate(episodes, start=1):
                        ep['episode'] = i
                        ep['episode_number'] = i
                    
                    logger.debug(f"✅ [FranceTV] Found {len(episodes)} episodes for {actual_show_id} (sorted chronologically)")
                    return episodes
                else:
                    logger.warning(f"⚠️ [FranceTV] No episodes found in API response for {actual_show_id}")
            else:
                logger.error(f"❌ [FranceTV] API failed or no result for {actual_show_id}")
            
            # Fallback: return a placeholder episode
            logger.warning(f"⚠️ [FranceTV] Using fallback episode for {actual_show_id}")
            return [self._create_fallback_episode(actual_show_id)]
                
        except Exception as e:
            logger.error(f"❌ [FranceTV] Error getting show episodes: {e}")
            # Fallback: return a placeholder episode
            return [self._create_fallback_episode(actual_show_id)]
    
    def _create_fallback_episode(self, show_id: str) -> Dict:
        """Create a fallback episode when API fails"""
        show_info = self.shows.get(show_id, {})
        return {
            "id": f"cutam:fr:francetv:episode:{show_id}_fallback",
            "type": "episode",
            "title": f"Latest {show_info.get('name', show_id.replace('-', ' ').title())}",
            "description": f"Latest episode of {show_info.get('name', show_id.replace('-', ' ').title())}",
            "poster": show_info.get('logo', get_logo_url("fr", "france2", self.request)),
            "fanart": show_info.get('logo', get_logo_url("fr", "france2", self.request)),
            "episode": 1,
            "season": 1,
            "note": "Fallback episode - API unavailable"
        }
    
    def _parse_episode(self, episode_data: Dict, episode_number: int) -> Optional[Dict]:
        """Parse episode data from France TV API response with enhanced metadata"""
        try:
            # Extract episode information
            episode_id = episode_data.get('id')
            title = episode_data.get('title', episode_data.get('label', 'Unknown Title'))
            raw_description = episode_data.get('text', episode_data.get('description', ''))
            # Decode HTML entities like &nbsp; in the description
            description = html.unescape(raw_description) if raw_description else ''
            
            # Get images from the correct API structure
            poster = None
            fanart = None
            
            # Check for images in content_has_medias (this is where France TV stores episode images)
            if 'content_has_medias' in episode_data:
                for media_item in episode_data['content_has_medias']:
                    if media_item.get('type') == 'image' and 'media' in media_item:
                        media = media_item['media']
                        if 'patterns' in media:
                            for pattern in media['patterns']:
                                if 'type' in pattern and 'urls' in pattern:
                                    image_type = pattern['type']
                                    urls = pattern['urls']
                                    
                                    if 'vignette_16x9' in image_type:
                                        relative_poster = urls.get('w:1024')
                                        relative_fanart = urls.get('w:2500')  # Higher resolution for fanart
                                        # Convert to absolute URLs
                                        if relative_poster and relative_poster.startswith('/'):
                                            poster = f"https://www.france.tv{relative_poster}"
                                        if relative_fanart and relative_fanart.startswith('/'):
                                            fanart = f"https://www.france.tv{relative_fanart}"
                                    elif 'carre' in image_type:
                                        relative_poster = urls.get('w:400')
                                        if relative_poster and relative_poster.startswith('/'):
                                            poster = f"https://www.france.tv{relative_poster}"
                                    elif 'background_16x9' in image_type:
                                        relative_fanart = urls.get('w:2500')
                                        if relative_fanart and relative_fanart.startswith('/'):
                                            fanart = f"https://www.france.tv{relative_fanart}"
                                    
                                    # If we found both poster and fanart, we can break
                                    if poster and fanart:
                                        break
            
            # Fallback to media_image patterns (older API structure)
            if not poster and 'media_image' in episode_data and episode_data['media_image']:
                for image in episode_data['media_image'].get('patterns', []):
                    if 'vignette_16x9' in image.get('type', ''):
                        poster = image.get('urls', {}).get('w:1024')
                        fanart = image.get('urls', {}).get('w:2500')  # Higher resolution for fanart
                        break
                    elif 'carre' in image.get('type', ''):
                        poster = image.get('urls', {}).get('w:400')
                        break
            
            # Get broadcast ID from content_has_medias (same logic as source addon)
            broadcast_id = None
            if 'content_has_medias' in episode_data:
                for medium in episode_data['content_has_medias']:
                    if medium.get('type') == 'main':
                        broadcast_id = medium.get('media', {}).get('si_id')
                        break
            
            # Fallback to episode ID if no broadcast ID found
            if not broadcast_id:
                broadcast_id = episode_data.get('id')
            
            if not broadcast_id:
                return None
            
            # Extract air_date from begin_date field (format: 2024-01-15T21:00:00+01:00)
            air_date = episode_data.get('begin_date', '')
            # Parse to extract just the date portion if full datetime
            if air_date and 'T' in air_date:
                air_date = air_date.split('T')[0]  # Get just YYYY-MM-DD
            
            # Extract first_publication_date for Stremio 'released' field
            # Format from API: "2025-11-27T11:33:09+01:00"
            # Format for Stremio: "2025-11-27T10:33:09.000Z" (UTC)
            released = ""
            first_pub_date = episode_data.get('first_publication_date', '')
            if first_pub_date:
                try:
                    # Parse the datetime with timezone
                    dt = datetime.fromisoformat(first_pub_date)
                    # Convert to UTC and format for Stremio
                    released = dt.strftime('%Y-%m-%dT%H:%M:%S.000Z')
                except Exception:
                    # Fallback: use the original format if parsing fails
                    released = first_pub_date
            
            # Create base episode metadata
            episode_meta = {
                "id": f"cutam:fr:francetv:episode:{broadcast_id}",
                "title": title,
                "description": description,
                "poster": poster,
                "fanart": fanart,
                "broadcast_id": broadcast_id,
                "type": "episode",
                "air_date": air_date,  # Used for chronological sorting
                "released": released,  # ISO 8601 date for Stremio
                "episode_number": episode_number,
                "season": 1,  # All episodes in season 1
                "episode": episode_number
            }
            
            # Enhance with additional metadata from the API response
            episode_meta = metadata_processor.enhance_metadata_with_api(episode_meta, episode_data)
            
            return episode_meta
            
        except Exception as e:
            logger.error(f"❌ [FranceTV] Error parsing episode: {e}")
            return None
    
    def get_episode_stream_url(self, episode_id: str) -> Optional[Dict]:
        """Get stream URL for a specific episode with error handling and fallbacks"""
        # Extract broadcast ID from episode ID
        if "episode:" in episode_id:
            broadcast_id = episode_id.split("episode:")[-1]
        else:
            broadcast_id = episode_id
        
        try:
            # Use the same approach as the source addon
            # Get video information from France TV API
            video_url = f"https://k7.ftven.fr/videos/{broadcast_id}"
            
            params = {
                'country_code': 'FR',
                'os': 'androidtv',
                'diffusion_mode': 'tunnel_first',
                'offline': 'false',
            }
            
            video_data = self.api_client.get(video_url, params=params, max_retries=2)
            
            if video_data and 'video' in video_data:
                video_info = video_data['video']
                
                video_url = video_info.get('url')
                if not video_url:
                    logger.error("❌ [FranceTV] No video URL found")
                    return None
                
                # Get the actual stream URL
                token_url = "https://hdfauth.ftven.fr/esi/TA"
                token_params = {
                    'format': 'json',
                    'url': video_url
                }
                
                token_data = self.api_client.get(token_url, params=token_params, max_retries=2)
                
                if token_data and 'url' in token_data:
                    final_url = token_data['url']
                    
                    if final_url:
                        return {
                            "url": final_url,
                            "manifest_type": "hls"
                        }
                
                logger.error("❌ [FranceTV] Failed to get stream URL")
                return None
            else:
                logger.error(f"❌ [FranceTV] Failed to get video info or API failed")
                return None
                
        except Exception as e:
            logger.error(f"❌ [FranceTV] Error getting episode stream: {e}")
            traceback.print_exc()
            return None
