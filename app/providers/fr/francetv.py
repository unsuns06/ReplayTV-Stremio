#!/usr/bin/env python3
"""
France TV provider implementation
Hybrid approach with robust error handling, fallbacks, and retry logic
"""

import json
import requests
import re
import os
import time
import random
import sys
from typing import Dict, List, Optional
from fastapi import Request
from app.utils.credentials import get_provider_credentials
from app.utils.metadata import metadata_processor
from app.utils.safe_print import safe_print
from app.utils.client_ip import merge_ip_headers
from app.utils.base_url import get_base_url, get_logo_url

def get_random_windows_ua():
    """Generates a random Windows User-Agent string."""
    user_agents = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/109.0.1518.78',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Firefox/109.0',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/109.0'
    ]
    return random.choice(user_agents)

class FranceTVProvider:
    """France TV provider implementation with robust error handling and fallbacks"""
    
    def __init__(self, request: Optional[Request] = None):
        self.credentials = get_provider_credentials('francetv')
        self.base_url = "https://www.france.tv"
        self.api_mobile = "https://api-mobile.yatta.francetv.fr"
        self.api_front = "http://api-front.yatta.francetv.fr"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': get_random_windows_ua()
        })
        
        # Store request for base URL determination
        self.request = request
        # Get base URL for static assets
        self.static_base = get_base_url(request)
        
        # Enhanced show information with rich metadata
        self.shows = {
            "envoye-special": {
                "id": "france-2_envoye-special",
                "name": "Envoyé spécial",
                "description": "Magazine d'information de France 2",
                "channel": "France 2",
                "logo": get_logo_url("fr", "france2", self.request),
                "genres": ["News", "Documentary", "Investigation"],
                "year": 2024,
                "rating": "Tous publics"
            },
            "cash-investigation": {
                "id": "france-2_cash-investigation", 
                "name": "Cash Investigation",
                "description": "Magazine d'investigation économique de France 2",
                "channel": "France 2",
                "logo": get_logo_url("fr", "france2", self.request),
                "genres": ["News", "Documentary", "Investigation", "Economics"],
                "year": 2024,
                "rating": "Tous publics"
            },
            "complement-enquete": {
                "id": "france-2_complement-d-enquete",
                "name": "Complément d'enquête",
                "description": "Magazine d'investigation de France 2",
                "channel": "France 2",
                "logo": get_logo_url("fr", "france2", self.request),
                "genres": ["News", "Documentary", "Investigation"],
                "year": 2024,
                "rating": "Tous publics"
            }
        }
        
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
        """Make a safe API call with retry logic and error handling"""
        for attempt in range(max_retries):
            try:
                # Rotate User-Agent for each attempt
                current_headers = headers or {}
                current_headers['User-Agent'] = get_random_windows_ua()
                # Forward viewer IP to upstream
                current_headers = merge_ip_headers(current_headers)
                
                safe_print(f"[FranceTV] API call attempt {attempt + 1}/{max_retries}: {url}")
                if params:
                    safe_print(f"[FranceTV] Request params: {params}")
                if headers:
                    safe_print(f"[FranceTV] Request headers (pre-merge): {headers}")
                try:
                    safe_print(f"[FranceTV] Request headers (effective): {current_headers}")
                except Exception:
                    pass
                
                response = self.session.get(url, params=params, headers=current_headers, timeout=15)
                
                if response.status_code == 200:
                    # Log response details for debugging
                    safe_print(f"[FranceTV] Response headers: {dict(response.headers)}")
                    safe_print(f"[FranceTV] Content-Type: {response.headers.get('content-type', 'Not set')}")
                    
                    # Try to parse JSON with multiple strategies
                    try:
                        return response.json()
                    except json.JSONDecodeError as e:
                        safe_print(f"[FranceTV] JSON parse error on attempt {attempt + 1}: {e}")
                        safe_print(f"[FranceTV] Error position: line {e.lineno}, column {e.colno}, char {e.pos}")
                        
                        # Log the raw response for debugging
                        text = response.text
                        safe_print(f"[FranceTV] Raw response length: {len(text)} characters")
                        safe_print(f"[FranceTV] Raw response (first 500 chars): {text[:500]}")
                        
                        # Log the problematic area around the error
                        if e.pos > 0:
                            start = max(0, e.pos - 50)
                            end = min(len(text), e.pos + 50)
                            safe_print(f"[FranceTV] Context around error (chars {start}-{end}): {text[start:end]}")
                        
                        # Strategy 1: Try to fix common JSON issues
                        if "'" in text and '"' not in text:
                            # Replace single quotes with double quotes
                            text = text.replace("'", '"')
                            try:
                                return json.loads(text)
                            except:
                                pass
                        
                        # Strategy 2: Try to fix unquoted property names
                        try:
                            # This regex looks for property names that aren't properly quoted
                            import re
                            fixed_text = re.sub(r'([{,])\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*:', r'\1"\2":', text)
                            if fixed_text != text:
                                safe_print(f"[FranceTV] Attempting to fix unquoted property names...")
                                return json.loads(fixed_text)
                        except:
                            pass
                        
                        # Strategy 3: Try to extract JSON from larger response
                        if '<html' in text.lower():
                            safe_print(f"[FranceTV] Received HTML instead of JSON on attempt {attempt + 1}")
                        else:
                            safe_print(f"[FranceTV] Malformed response on attempt {attempt + 1}: {text[:200]}...")
                        
                        # Wait before retry
                        if attempt < max_retries - 1:
                            time.sleep(2 ** attempt)  # Exponential backoff
                            continue
                        
                elif response.status_code in [403, 429, 500]:
                    safe_print(f"[FranceTV] HTTP {response.status_code} on attempt {attempt + 1}")
                    safe_print(f"[FranceTV] Response headers: {dict(response.headers)}")
                    safe_print(f"[FranceTV] Response content: {response.text[:500]}...")
                    if attempt < max_retries - 1:
                        time.sleep(2 ** attempt)
                        continue
                else:
                    safe_print(f"[FranceTV] HTTP {response.status_code} on attempt {attempt + 1}")
                    safe_print(f"[FranceTV] Response headers: {dict(response.headers)}")
                    safe_print(f"[FranceTV] Response content: {response.text[:500]}...")
                    
            except Exception as e:
                safe_print(f"[FranceTV] Request error on attempt {attempt + 1}: {e}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                    continue
        
        safe_print(f"[FranceTV] All {max_retries} attempts failed for {url}")
        return None
    
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
            try:
                api_metadata = self._get_show_api_metadata(show_info['id'])
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
            
            # First try to get broadcast ID from mobile API
            broadcast_id = None
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
                            if items and items[0].get('channel') and items[0]['channel'].get('si_id'):
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
                                medias = live.get('collection', [{}])[0].get('content_has_medias', [])
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
            video_url = f"https://k7.ftven.fr/videos/{broadcast_id}"
            params = {
                'country_code': 'FR',
                'os': 'androidtv',
                'diffusion_mode': 'tunnel_first',
                'offline': 'false',
            }
            
            safe_print(f"   Video API URL: {video_url}")
            video_data = self._safe_api_call(video_url, params=params)
            
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
                token_data = self._safe_api_call(url_token, params=token_params)
                
                if token_data and 'url' in token_data:
                    final_url = token_data['url']
                    
                    if final_url:
                        manifest_type = 'hls' if 'hls' in video_info.get('format', []) else 'mpd'
                        result = {
                            "url": final_url,
                            "manifest_type": manifest_type,
                            "title": f"Live {channel_name.upper()}"
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
            # Use the same API endpoint as the source addon with error handling
            # URL example: http://api-front.yatta.francetv.fr/standard/publish/taxonomies/france-2_cash-investigation/contents/?size=20&page=0&sort=begin_date:desc&filter=with-no-vod,only-visible
            api_url = f"{self.api_front}/standard/publish/taxonomies/{self.shows[actual_show_id]['id']}/contents/"
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
                for i, video in enumerate(data['result']):
                    if video['type'] in ['integrale', 'extrait']:
                        # This is a video/episode
                        episode_info = self._parse_episode(video, i + 1)
                        if episode_info:
                            episodes.append(episode_info)
                
                if episodes:
                    safe_print(f"[FranceTV] Found {len(episodes)} episodes for {actual_show_id}")
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
            description = episode_data.get('text', episode_data.get('description', ''))
            
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
            
            # Create base episode metadata
            episode_meta = {
                "id": f"cutam:fr:francetv:episode:{broadcast_id}",
                "title": title,
                "description": description,
                "poster": poster,
                "fanart": fanart,
                "broadcast_id": broadcast_id,
                "type": "episode",
                "episode_number": episode_number,
                "season": 1,  # All episodes in season 1 for now
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
            
            video_data = self._safe_api_call(video_url, params=params)
            
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
                
                token_data = self._safe_api_call(token_url, params=token_params)
                
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
