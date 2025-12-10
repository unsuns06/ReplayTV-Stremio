#!/usr/bin/env python3
"""
France TV provider implementation
Hybrid approach with robust error handling, fallbacks, and retry logic
"""

import html
import json
import os
import time
from typing import Dict, List, Optional
from urllib.parse import urlencode, quote
from fastapi import Request
from app.utils.credentials import get_provider_credentials
from app.utils.metadata import metadata_processor
from app.utils.safe_print import safe_print
from app.utils.client_ip import merge_ip_headers
from app.utils.base_url import get_base_url, get_logo_url

from app.utils.user_agent import get_random_windows_ua
from app.utils.api_client import ProviderAPIClient
from app.utils.programs_loader import get_programs_for_provider
from app.providers.fr.base_fr_provider import BaseFrenchProvider

class FranceTVProvider(BaseFrenchProvider):
    """France TV provider implementation with robust error handling and fallbacks"""
    
    # Class attributes for BaseProvider
    provider_name = "francetv"
    base_url = "https://www.france.tv"
    
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
    
    def _safe_api_call(self, url: str, params: Dict = None, headers: Dict = None, max_retries: int = 3) -> Optional[Dict]:
        """Delegate to shared ProviderAPIClient."""
        return self.api_client.get(url, params=params, headers=headers, max_retries=max_retries)
    
    def get_programs(self) -> List[Dict]:
        """Get list of replay shows with enhanced metadata"""
        shows = []
        
        for show_id, show_info in self.shows.items():
            # Get base metadata from our enhanced show info
            show_metadata = metadata_processor.get_show_metadata(
                f"cutam:fr:francetv:{show_id}", 
                show_info
            )
            
            # Try to get additional metadata from France TV API with fallback
            # Use api_id if available (for composite IDs like france-2_envoye-special), otherwise fall back to id
            api_show_id = show_info.get('api_id') or show_info.get('id', show_id)
            try:
                api_metadata = self._get_show_api_metadata(api_show_id)
                if api_metadata:
                    show_metadata = metadata_processor.enhance_metadata_with_api(
                        show_metadata, api_metadata
                    )
            except Exception as e:
                safe_print(f"[FranceTV] Warning: Could not fetch API metadata for {show_id}: {e}")
                # Continue with static metadata
            
            shows.append(show_metadata)
        
        return shows
    
    def _get_show_api_metadata(self, show_api_id: str) -> Optional[Dict]:
        """Get additional metadata for a show from France TV API with error handling"""
        try:
            # Get show information from the front API
            api_url = f"{self.api_front}/standard/publish/taxonomies/{show_api_id}"
            params = {'platform': 'apps'}
            
            data = self._safe_api_call(api_url, params=params)
            if not data:
                return None
            
            # Extract show metadata
            images = data.get('media_image', {}).get('patterns', []) if 'media_image' in data else []
            description = data.get('description', '')
            text = data.get('seo', '')  # SEO field often contains rich text
            
            # Get additional metadata
            metadata = {
                'images': images,
                'description': description,
                'text': text,
            }
            
            return metadata
            
        except Exception as e:
            safe_print(f"[FranceTV] Error getting show API metadata: {e}")
            return None
    
    def get_live_channels(self) -> List[Dict]:
        """Get list of live TV channels from France TV"""
        channels = []
        
        # France TV live channels (based on source addon)
        france_channels = [
            {
                "id": "cutam:fr:francetv:france-2",
                "type": "channel",
                "name": "France 2",
                "poster": get_logo_url("fr", "france2", self.request),
                "logo": get_logo_url("fr", "france2", self.request),
                "description": "Chaîne de télévision française de service public"
            },
            {
                "id": "cutam:fr:francetv:france-3",
                "type": "channel",
                "name": "France 3",
                "poster": get_logo_url("fr", "france3", self.request),
                "logo": get_logo_url("fr", "france3", self.request),
                "description": "Chaîne de télévision française de service public"
            },
            {
                "id": "cutam:fr:francetv:france-4",
                "type": "channel",
                "name": "France 4", 
                "poster": get_logo_url("fr", "france4", self.request),
                "logo": get_logo_url("fr", "france4", self.request),
                "description": "Chaîne de télévision française de service public"
            },
            {
                "id": "cutam:fr:francetv:france-5",
                "type": "channel",
                "name": "France 5", 
                "poster": get_logo_url("fr", "france5", self.request),
                "logo": get_logo_url("fr", "france5", self.request),
                "description": "Chaîne de télévision française de service public"
            },
            {
                "id": "cutam:fr:francetv:franceinfo",
                "type": "channel",
                "name": "franceinfo:",
                "poster": get_logo_url("fr", "franceinfo", self.request),
                "logo": get_logo_url("fr", "franceinfo", self.request),
                "description": "Chaîne d'information continue française de service public"
            }
        ]
        
        channels.extend(france_channels)
        return channels
    
    def get_live_stream_url(self, channel_id: str) -> Optional[Dict]:
        """Get live stream URL for a specific channel with robust error handling and fallbacks"""
        safe_print(f"🔍 France TV: Getting live stream for {channel_id}")
        try:
            # Extract channel name from ID (e.g., "france-2" from "cutam:fr:francetv:france-2")
            channel_name = channel_id.split(":")[-1]
            safe_print(f"   Channel name: {channel_name}")
            
            # First try to get broadcast ID and current program info from mobile API
            broadcast_id = None
            current_program_title = None
            try:
                params = {'platform': 'apps'}
                api_url = f"{self.api_mobile}/apps/channels/{channel_name}"
                safe_print(f"   Mobile API URL: {api_url}")
                
                data = self._safe_api_call(api_url, params=params)
                if data:
                    # Look for live collection
                    for collection in data.get('collections', []):
                        if collection.get('type') == 'live':
                            items = collection.get('items', [])
                            if items:
                                # Get current program title
                                current_program_title = items[0].get('title', '')
                                safe_print(f"   Current program: {current_program_title}")
                                
                                # Get broadcast ID
                                if items[0].get('channel') and items[0]['channel'].get('si_id'):
                                    broadcast_id = items[0]['channel']['si_id']
                                    safe_print(f"   Found broadcast ID from mobile API: {broadcast_id}")
                            break
            except Exception as e:
                safe_print(f"   Mobile API failed: {e}")
            
            # If mobile API failed, try front API
            if not broadcast_id:
                try:
                    live_json_url = f"{self.api_front}/standard/edito/directs"
                    safe_print(f"   Front API URL: {live_json_url}")
                    
                    data = self._safe_api_call(live_json_url)
                    if data:
                        for live in data.get('result', []):
                            if live.get('channel') == channel_name:
                                # Try to get program title from collection
                                collections = live.get('collection', [])
                                if collections and not current_program_title:
                                    current_program_title = collections[0].get('title', '')
                                
                                medias = collections[0].get('content_has_medias', []) if collections else []
                                for m in medias:
                                    media = m.get('media', {})
                                    if 'si_direct_id' in media:
                                        broadcast_id = media['si_direct_id']
                                        safe_print(f"   Found broadcast ID from front API: {broadcast_id}")
                                        break
                                break
                except Exception as e:
                    safe_print(f"   Front API failed: {e}")
            
            # Final fallback to constants
            if not broadcast_id:
                broadcast_id = self.fallback_channels.get(channel_name, {}).get('id')
                safe_print(f"   Using fallback ID: {broadcast_id}")
            
            if not broadcast_id:
                safe_print(f"   No broadcast ID found for {channel_name}")
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
            
            safe_print(f"   Video API URL: {video_url}")
            video_data = self._safe_api_call(video_url, params=params, max_retries=2)
            
            if video_data and 'video' in video_data:
                video_info = video_data['video']
                safe_print(f"   Video info keys: {list(video_info.keys())}")
                
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
                
                safe_print(f"   Using token URL: {url_token}")
                
                # Get the actual stream URL
                token_params = {
                    'format': 'json',
                    'url': video_info.get('url', '')
                }
                
                safe_print(f"   Token API params: {token_params}")
                token_data = self._safe_api_call(url_token, params=token_params, max_retries=2)
                
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
                        safe_print(f"   ✅ Returning result: {result}")
                        return result
                    else:
                        safe_print(f"   ❌ No final URL in token response")
                else:
                    safe_print(f"   ❌ Token API failed or no URL found")
            else:
                safe_print(f"   ❌ No 'video' key in response or API failed")
            
            safe_print(f"   ❌ Returning None")
            return None
            
        except Exception as e:
            safe_print(f"❌ Error getting live stream for {channel_id}: {e}")
            import traceback
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
            
            data = self._safe_api_call(api_url, params=params)
            
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
                    
                    safe_print(f"[FranceTV] Found {len(episodes)} episodes for {actual_show_id} (sorted chronologically)")
                    return episodes
                else:
                    safe_print(f"[FranceTV] No episodes found in API response for {actual_show_id}")
            else:
                safe_print(f"[FranceTV] API failed or no result for {actual_show_id}")
            
            # Fallback: return a placeholder episode
            safe_print(f"[FranceTV] Using fallback episode for {actual_show_id}")
            return [self._create_fallback_episode(actual_show_id)]
                
        except Exception as e:
            safe_print(f"[FranceTV] Error getting show episodes: {e}")
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
                    from datetime import datetime
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
            safe_print(f"Error parsing episode: {e}")
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
            
            video_data = self._safe_api_call(video_url, params=params, max_retries=2)
            
            if video_data and 'video' in video_data:
                video_info = video_data['video']
                
                video_url = video_info.get('url')
                if not video_url:
                    safe_print("No video URL found")
                    return None
                
                # Get the actual stream URL
                token_url = "https://hdfauth.ftven.fr/esi/TA"
                token_params = {
                    'format': 'json',
                    'url': video_url
                }
                
                token_data = self._safe_api_call(token_url, params=token_params, max_retries=2)
                
                if token_data and 'url' in token_data:
                    final_url = token_data['url']
                    
                    if final_url:
                        return {
                            "url": final_url,
                            "manifest_type": "hls"
                        }
                
                safe_print("Failed to get stream URL")
                return None
            else:
                safe_print(f"Failed to get video info or API failed")
                return None
                
        except Exception as e:
            safe_print(f"Error getting episode stream: {e}")
            import traceback
            traceback.print_exc()
            return None

    def resolve_stream(self, stream_id: str) -> Optional[Dict]:
        """Resolve stream URL for a given stream ID"""
        # This method needs to be implemented based on the specific stream ID format
        # For now, return None as a placeholder
        safe_print(f"FranceTVProvider: resolve_stream not implemented for {stream_id}")
        return None

def test_francetv_provider():
    """Test the France TV provider"""
    safe_print("🔍 Testing France TV provider...")
    
    provider = FranceTVProvider()
    
    # Test getting replay shows
    safe_print("\n1️⃣ Testing replay shows...")
    shows = provider.get_programs()
    
    if shows:
        safe_print(f"✅ Found {len(shows)} shows:")
        for show in shows:
            safe_print(f"   - {show['name']}: {show['id']}")
            safe_print(f"     Poster: {show.get('poster', 'N/A')}")
            safe_print(f"     Fanart: {show.get('fanart', 'N/A')}")
            safe_print(f"     Genres: {show.get('genres', [])}")
        
        # Test getting episodes for the first show
        if shows:
            first_show = shows[0]
            safe_print(f"\n2️⃣ Testing episodes for {first_show['name']}...")
            
            episodes = provider.get_episodes(first_show['id'])
            
            if episodes:
                safe_print(f"✅ Found {len(episodes)} episodes:")
                for episode in episodes[:3]:  # Show first 3 episodes
                    safe_print(f"   - {episode['title']}: {episode['id']}")
                    safe_print(f"     Poster: {episode.get('poster', 'N/A')}")
                    safe_print(f"     Fanart: {episode.get('fanart', 'N/A')}")
                    safe_print(f"     Description: {episode.get('description', 'N/A')[:100]}...")
                
                # Test getting stream URL for the first episode
                if episodes:
                    first_episode = episodes[0]
                    safe_print(f"\n3️⃣ Testing stream URL for episode: {first_episode['title']}...")
                    
                    stream_info = provider.get_episode_stream_url(first_episode['id'])
                    
                    if stream_info:
                        safe_print(f"✅ Stream info retrieved:")
                        safe_print(f"   URL: {stream_info['url'][:100] if stream_info['url'] else 'N/A'}...")
                        safe_print(f"   Manifest Type: {stream_info.get('manifest_type', 'unknown')}")
                    else:
                        safe_print("❌ Failed to get stream info")
            else:
                safe_print("❌ No episodes found")
    else:
        safe_print("❌ No shows found")
    
    safe_print("\n🔍 Test complete!")

if __name__ == "__main__":
    test_francetv_provider()
