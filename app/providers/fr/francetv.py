#!/usr/bin/env python3
"""
France TV provider implementation
Based on the source addon code for France TV
"""

import json
import requests
import re
import os
from typing import Dict, List, Optional
from app.utils.credentials import get_provider_credentials
from app.utils.metadata import metadata_processor
from app.utils.json_utils import parse_lenient_json

class FranceTVProvider:
    """France TV provider implementation based on source addon"""
    
    def __init__(self):
        self.credentials = get_provider_credentials('francetv')
        self.base_url = "https://www.france.tv"
        self.api_mobile = "https://api-mobile.yatta.francetv.fr"
        self.api_front = "http://api-front.yatta.francetv.fr"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        
        # Get base URL for static assets
        self.static_base = os.getenv('ADDON_BASE_URL', 'http://localhost:8000')
        
        # Enhanced show information with rich metadata
        self.shows = {
            "envoye-special": {
                "id": "france-2_envoye-special",
                "name": "Envoyé spécial",
                "description": "Magazine d'information de France 2",
                "channel": "France 2",
                "logo": f"{self.static_base}/static/logos/fr/france2.png",
                "genres": ["News", "Documentary", "Investigation"],
                "year": 2024,
                "rating": "Tous publics"
            },
            "cash-investigation": {
                "id": "france-2_cash-investigation", 
                "name": "Cash Investigation",
                "description": "Magazine d'investigation économique de France 2",
                "channel": "France 2",
                "logo": f"{self.static_base}/static/logos/fr/france2.png",
                "genres": ["News", "Documentary", "Investigation", "Economics"],
                "year": 2024,
                "rating": "Tous publics"
            },
            "complement-enquete": {
                "id": "france-2_complement-d-enquete",
                "name": "Complément d'enquête",
                "description": "Magazine d'investigation de France 2",
                "channel": "France 2",
                "logo": f"{self.static_base}/static/logos/fr/france2.png",
                "genres": ["News", "Documentary", "Investigation"],
                "year": 2024,
                "rating": "Tous publics"
            }
        }
    
    def get_programs(self) -> List[Dict]:
        """Get list of replay shows with enhanced metadata"""
        shows = []
        
        for show_id, show_info in self.shows.items():
            # Get base metadata from our enhanced show info
            show_metadata = metadata_processor.get_show_metadata(
                f"cutam:fr:francetv:{show_id}", 
                show_info
            )
            
            # Try to get additional metadata from France TV API
            try:
                api_metadata = self._get_show_api_metadata(show_info['id'])
                if api_metadata:
                    show_metadata = metadata_processor.enhance_metadata_with_api(
                        show_metadata, api_metadata
                    )
            except Exception as e:
                print(f"Warning: Could not fetch API metadata for {show_id}: {e}")
            
            shows.append(show_metadata)
        
        return shows
    
    def _get_show_api_metadata(self, show_api_id: str) -> Optional[Dict]:
        """Get additional metadata for a show from France TV API"""
        try:
            # Get show information from the front API
            api_url = f"{self.api_front}/standard/publish/taxonomies/{show_api_id}"
            params = {'platform': 'apps'}
            
            response = self.session.get(api_url, params=params, timeout=10)
            
            if response.status_code == 200:
                data = parse_lenient_json(response.text)
                
                # The API response structure is different - it's directly the show data
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
            
            return None
            
        except Exception as e:
            print(f"Error getting show API metadata: {e}")
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
                "poster": f"{self.static_base}/static/logos/fr/france2.png",
                "logo": f"{self.static_base}/static/logos/fr/france2.png",
                "description": "Chaîne de télévision française de service public"
            },
            {
                "id": "cutam:fr:francetv:france-3",
                "type": "channel",
                "name": "France 3",
                "poster": f"{self.static_base}/static/logos/fr/france3.png",
                "logo": f"{self.static_base}/static/logos/fr/france3.png",
                "description": "Chaîne de télévision française de service public"
            },
            {
                "id": "cutam:fr:francetv:france-4",
                "type": "channel",
                "name": "France 4", 
                "poster": f"{self.static_base}/static/logos/fr/france4.png",
                "logo": f"{self.static_base}/static/logos/fr/france4.png",
                "description": "Chaîne de télévision française de service public"
            },
            {
                "id": "cutam:fr:francetv:france-5",
                "type": "channel",
                "name": "France 5", 
                "poster": f"{self.static_base}/static/logos/fr/france5.png",
                "logo": f"{self.static_base}/static/logos/fr/france5.png",
                "description": "Chaîne de télévision française de service public"
            },
            {
                "id": "cutam:fr:francetv:franceinfo",
                "type": "channel",
                "name": "franceinfo:",
                "poster": f"{self.static_base}/static/logos/fr/franceinfo.png",
                "logo": f"{self.static_base}/static/logos/fr/franceinfo.png",
                "description": "Chaîne d'information continue française de service public"
            }
        ]
        
        channels.extend(france_channels)
        return channels
    
    def get_live_stream_url(self, channel_id: str) -> Optional[Dict]:
        """Get live stream URL for a specific channel - based on reference implementation"""
        print(f"🔍 France TV: Getting live stream for {channel_id}")
        try:
            # Extract channel name from ID (e.g., "france-2" from "cutam:fr:francetv:france-2")
            channel_name = channel_id.split(":")[-1]
            print(f"   Channel name: {channel_name}")
            
            # Use the same approach as the reference implementation
            fallback_id = {
                "france-2": "006194ea-117d-4bcf-94a9-153d999c59ae",
                "france-3": "29bdf749-7082-4426-a4f3-595cc436aa0d",
                "france-4": "9a6a7670-dde9-4264-adbc-55b89558594b",
                "france-5": "45007886-f3ff-4b3e-9706-1ef1014c5a60",
                "franceinfo": "35be22fb-1569-43ff-857c-99bf81defa2e",
            }
            
            # First try to get broadcast ID from mobile API
            broadcast_id = None
            try:
                params = {'platform': 'apps'}
                api_url = f"{self.api_mobile}/apps/channels/{channel_name}"
                print(f"   Mobile API URL: {api_url}")
                
                response = self.session.get(api_url, params=params, timeout=10)
                print(f"   Mobile API response: {response.status_code}")
                
                if response.status_code == 200:
                    json_data = parse_lenient_json(response.text)
                    
                    # Look for live collection
                    for collection in json_data.get('collections', []):
                        if collection.get('type') == 'live':
                            items = collection.get('items', [])
                            if items and items[0].get('channel') and items[0]['channel'].get('si_id'):
                                broadcast_id = items[0]['channel']['si_id']
                                print(f"   Found broadcast ID from mobile API: {broadcast_id}")
                                break
            except Exception as e:
                print(f"   Mobile API failed: {e}")
            
            # If mobile API failed, try front API
            if not broadcast_id:
                try:
                    live_json_url = f"{self.api_front}/standard/edito/directs"
                    print(f"   Front API URL: {live_json_url}")
                    
                    response = self.session.get(live_json_url, timeout=10)
                    print(f"   Front API response: {response.status_code}")
                    
                    if response.status_code == 200:
                        json_data = parse_lenient_json(response.text)
                        
                        for live in json_data.get('result', []):
                            if live.get('channel') == channel_name:
                                medias = live.get('collection', [{}])[0].get('content_has_medias', [])
                                for m in medias:
                                    media = m.get('media', {})
                                    if 'si_direct_id' in media:
                                        broadcast_id = media['si_direct_id']
                                        print(f"   Found broadcast ID from front API: {broadcast_id}")
                                        break
                                break
                except Exception as e:
                    print(f"   Front API failed: {e}")
            
            # Final fallback to constants
            if not broadcast_id:
                broadcast_id = fallback_id.get(channel_name)
                print(f"   Using fallback ID: {broadcast_id}")
            
            if not broadcast_id:
                print(f"   No broadcast ID found for {channel_name}")
                return None
            
            # Get video info from API (same as reference)
            video_url = f"https://k7.ftven.fr/videos/{broadcast_id}"
            params = {
                'country_code': 'FR',
                'os': 'androidtv',
                'diffusion_mode': 'tunnel_first',
                'offline': 'false',
            }
            
            print(f"   Video API URL: {video_url}")
            video_response = self.session.get(video_url, params=params, timeout=10)
            print(f"   Video API response: {video_response.status_code}")
            
            if video_response.status_code == 200:
                video_data = parse_lenient_json(video_response.text)
                print(f"   Video data keys: {list(video_data.keys())}")
                
                if 'video' in video_data:
                    video_info = video_data['video']
                    print(f"   Video info keys: {list(video_info.keys())}")
                    
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
                    
                    print(f"   Using token URL: {url_token}")
                    
                    # Get the actual stream URL
                    token_params = {
                        'format': 'json',
                        'url': video_info.get('url', '')
                    }
                    
                    print(f"   Token API params: {token_params}")
                    token_response = self.session.get(url_token, params=token_params, timeout=10)
                    print(f"   Token API response: {token_response.status_code}")
                    
                    if token_response.status_code == 200:
                        token_data = parse_lenient_json(token_response.text)
                        final_url = token_data.get('url')
                        
                        if final_url:
                            manifest_type = 'hls' if 'hls' in video_info.get('format', []) else 'mpd'
                            result = {
                                "url": final_url,
                                "manifest_type": manifest_type,
                                "title": f"Live {channel_name.upper()}"
                            }
                            print(f"   Returning result: {result}")
                            return result
                        else:
                            print(f"   No final URL in token response")
                    else:
                        print(f"   Token API error: {token_response.text}")
                else:
                    print(f"   No 'video' key in response")
            else:
                print(f"   Video API error: {video_response.text}")
            
            print(f"   Returning None")
            return None
            
        except Exception as e:
            print(f"❌ Error getting live stream for {channel_id}: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def get_channel_stream_url(self, channel_id: str) -> Optional[Dict]:
        """Get channel stream URL - wrapper for get_live_stream_url"""
        return self.get_live_stream_url(channel_id)

    def resolve_stream(self, stream_id: str) -> Optional[Dict]:
        """Resolve stream URL for a given stream ID"""
        # This method needs to be implemented based on the specific stream ID format
        # For now, return None as a placeholder
        print(f"FranceTVProvider: resolve_stream not implemented for {stream_id}")
        return None
    
    def get_episodes(self, show_id: str) -> List[Dict]:
        """Get episodes for a specific show with enhanced metadata"""
        # Extract the actual show ID from our format
        actual_show_id = show_id.split(":")[-1]
        
        if actual_show_id not in self.shows:
            return []
        
        try:
            # Use the same API endpoint as the source addon
            # URL example: http://api-front.yatta.francetv.fr/standard/publish/taxonomies/france-2_cash-investigation/contents/?size=20&page=0&sort=begin_date:desc&filter=with-no-vod,only-visible
            api_url = f"{self.api_front}/standard/publish/taxonomies/{self.shows[actual_show_id]['id']}/contents/"
            params = {
                'size': 20,
                'page': 0,
                'filter': "with-no-vod,only-visible",
                'sort': "begin_date:desc"
            }
            
            response = self.session.get(api_url, params=params, timeout=10)
            
            if response.status_code == 200:
                data = parse_lenient_json(response.text)
                episodes = []
                
                # Parse the response to get episodes (same logic as source addon)
                if 'result' in data:
                    for i, video in enumerate(data['result']):
                        if video['type'] in ['integrale', 'extrait']:
                            # This is a video/episode
                            episode_info = self._parse_episode(video, i + 1)
                            if episode_info:
                                episodes.append(episode_info)
                
                return episodes
            else:
                print(f"Failed to get show episodes: {response.status_code}")
                return []
                
        except Exception as e:
            print(f"Error getting show episodes: {e}")
            return []
    
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
            print(f"Error parsing episode: {e}")
            return None
    
    def get_episode_stream_url(self, episode_id: str) -> Optional[Dict]:
        """Get stream URL for a specific episode"""
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
            
            response = self.session.get(video_url, params=params, timeout=10)
            
            if response.status_code == 200:
                video_data = parse_lenient_json(response.text)
                
                if 'video' not in video_data:
                    print("No video data found")
                    return None
                
                video_info = video_data['video']
                
                video_url = video_info.get('url')
                if not video_url:
                    print("No video URL found")
                    return None
                
                # Get the actual stream URL
                token_url = "https://hdfauth.ftven.fr/esi/TA"
                token_params = {
                    'format': 'json',
                    'url': video_url
                }
                
                token_response = self.session.get(token_url, params=token_params, timeout=10)
                
                if token_response.status_code == 200:
                    token_data = parse_lenient_json(token_response.text)
                    final_url = token_data.get('url')
                    
                    if final_url:
                        return {
                            "url": final_url,
                            "manifest_type": "hls"
                        }
                
                print("Failed to get stream URL")
                return None
            else:
                print(f"Failed to get video info: {response.status_code}")
                return None
                
        except Exception as e:
            print(f"Error getting episode stream: {e}")
            import traceback
            traceback.print_exc()
            return None

def test_francetv_provider():
    """Test the France TV provider"""
    print("🔍 Testing France TV provider...")
    
    provider = FranceTVProvider()
    
    # Test getting replay shows
    print("\n1️⃣ Testing replay shows...")
    shows = provider.get_programs()
    
    if shows:
        print(f"✅ Found {len(shows)} shows:")
        for show in shows:
            print(f"   - {show['name']}: {show['id']}")
            print(f"     Poster: {show.get('poster', 'N/A')}")
            print(f"     Fanart: {show.get('fanart', 'N/A')}")
            print(f"     Genres: {show.get('genres', [])}")
        
        # Test getting episodes for the first show
        if shows:
            first_show = shows[0]
            print(f"\n2️⃣ Testing episodes for {first_show['name']}...")
            
            episodes = provider.get_episodes(first_show['id'])
            
            if episodes:
                print(f"✅ Found {len(episodes)} episodes:")
                for episode in episodes[:3]:  # Show first 3 episodes
                    print(f"   - {episode['title']}: {episode['id']}")
                    print(f"     Poster: {episode.get('poster', 'N/A')}")
                    print(f"     Fanart: {episode.get('fanart', 'N/A')}")
                    print(f"     Description: {episode.get('description', 'N/A')[:100]}...")
                
                # Test getting stream URL for the first episode
                if episodes:
                    first_episode = episodes[0]
                    print(f"\n3️⃣ Testing stream URL for episode: {first_episode['title']}...")
                    
                    stream_info = provider.get_episode_stream_url(first_episode['id'])
                    
                    if stream_info:
                        print(f"✅ Stream info retrieved:")
                        print(f"   URL: {stream_info['url'][:100] if stream_info['url'] else 'N/A'}...")
                        print(f"   Manifest Type: {stream_info.get('manifest_type', 'unknown')}")
                    else:
                        print("❌ Failed to get stream info")
            else:
                print("❌ No episodes found")
    else:
        print("❌ No shows found")
    
    print("\n🔍 Test complete!")

if __name__ == "__main__":
    test_francetv_provider()
