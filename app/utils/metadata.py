#!/usr/bin/env python3
"""
Metadata utility module for FranceTV replays
Based on the reference plugin.video.catchuptvandmore implementation
"""

import re
import time
from typing import Dict, List, Any

class FranceTVMetadataProcessor:
    """Process and enhance metadata for FranceTV replays"""
    
    def __init__(self):
        # Base URLs for France TV APIs
        self.api_mobile = "https://api-mobile.yatta.francetv.fr"
        self.api_front = "http://api-front.yatta.francetv.fr"
        
        # Image type mappings based on reference plugin
        self.image_types = {
            'carre': 'w:400',           # Square thumbnail
            'vignette_16x9': 'w:1024',  # 16:9 poster
            'background_16x9': 'w:2500', # 16:9 fanart
            'vignette_3x4': 'w:1024',   # 3:4 poster
            'logo': 'w:400',             # Logo
            'banner': 'w:1200',          # Banner
            'clearart': 'w:800',         # Clear art
            'clearlogo': 'w:400'         # Clear logo
        }
    
    def populate_images(self, item_data: Dict[str, Any], images: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Populate image metadata based on France TV API response
        Based on the reference plugin's populate_images function
        """
        if not images:
            return item_data
        
        all_images = {}
        
        # Process all available images
        for image in images:
            if 'type' in image and 'urls' in image:
                image_type = image['type']
                urls = image['urls']
                
                # Map image types to our standard format
                if image_type in self.image_types:
                    size_key = self.image_types[image_type]
                    if size_key in urls:
                        # Convert relative URLs to absolute France TV URLs
                        relative_url = urls[size_key]
                        if relative_url.startswith('/'):
                            absolute_url = f"https://www.france.tv{relative_url}"
                        else:
                            absolute_url = relative_url
                        all_images[image_type] = absolute_url
        
        # Set poster/thumbnail (priority: vignette_3x4 > carre > vignette_16x9)
        if 'vignette_3x4' in all_images:
            item_data['poster'] = all_images['vignette_3x4']
            item_data['landscape'] = all_images['vignette_3x4']
        elif 'carre' in all_images:
            item_data['poster'] = all_images['carre']
            item_data['landscape'] = all_images['carre']
        elif 'vignette_16x9' in all_images:
            item_data['poster'] = all_images['vignette_16x9']
            item_data['landscape'] = all_images['vignette_16x9']
        
        # Set fanart/background (priority: background_16x9 > vignette_16x9)
        if 'background_16x9' in all_images:
            item_data['fanart'] = all_images['background_16x9']
            item_data['background'] = all_images['background_16x9']
        elif 'vignette_16x9' in all_images:
            item_data['fanart'] = all_images['vignette_16x9']
            item_data['background'] = all_images['vignette_16x9']
        
        # Set additional image types
        if 'logo' in all_images:
            item_data['logo'] = all_images['logo']
        if 'banner' in all_images:
            item_data['banner'] = all_images['banner']
        if 'clearart' in all_images:
            item_data['clearart'] = all_images['clearart']
        if 'clearlogo' in all_images:
            item_data['clearlogo'] = all_images['clearlogo']
        
        return item_data
    
    def populate_video_metadata(self, video_data: Dict[str, Any], video: Dict[str, Any]) -> Dict[str, Any]:
        """
        Populate video metadata based on France TV API response
        Based on the reference plugin's populate_video_item function
        """
        # Basic video information
        if 'episode_title' in video:
            video_data['title'] = video['episode_title']
        else:
            video_data['title'] = video.get('title', 'Unknown Title')
        
        # Description
        description = video.get('description') or video.get('text', '')
        if description:
            # Clean HTML tags like the reference plugin
            description = re.sub(r'<[^>]+>', '', description)
            video_data['description'] = description
        
        # Broadcast date
        if 'begin_date' in video:
            try:
                broadcast_date = time.strftime('%Y-%m-%d', time.localtime(video['begin_date']))
                video_data['broadcast_date'] = broadcast_date
                # Also set year for metadata
                video_data['year'] = int(broadcast_date[:4])
            except (ValueError, TypeError):
                pass
        
        # Program information
        if 'program' in video and video['program']:
            program_info = video['program']
            if 'label' in program_info:
                video_data['program'] = program_info['label']
                # Combine program and episode title
                if 'episode_title' in video:
                    video_data['title'] = f"{program_info['label']} - {video['episode_title']}"
        
        # Video type
        video_type = video.get('type', '')
        if video_type == 'extrait':
            video_data['title'] = f"[extrait] {video_data['title']}"
            video_data['type'] = 'extrait'
        elif video_type == 'integrale':
            video_data['type'] = 'integrale'
        
        # Rating (CSA code)
        rating = video.get('rating_csa_code', '')
        if rating and rating.isdigit():
            video_data['rating'] = f"-{rating}"
        
        # Duration
        if 'duration' in video:
            video_data['duration'] = video['duration']
        
        # Director
        if 'director' in video and video['director']:
            video_data['director'] = video['director']
        
        # Season and episode
        if 'saison' in video and video['saison']:
            video_data['season'] = video['saison']
        if 'episode' in video and video['episode']:
            video_data['episode'] = video['episode']
            video_data['mediatype'] = 'episode'
        
        # Cast and characters
        actors = []
        if 'casting' in video and video['casting']:
            actors = [actor.strip() for actor in video['casting'].split(",")]
        elif 'presenter' in video and video['presenter']:
            actors.append(video['presenter'])
        
        if actors:
            video_data['cast'] = actors
            
            # Handle cast and roles
            if 'characters' in video and video['characters']:
                characters = [role.strip() for role in video['characters'].split(",")]
                if len(actors) > 0 and len(characters) > 0:
                    # Create castandrole list like the reference plugin
                    castandrole = []
                    for i in range(max(len(actors), len(characters))):
                        actor = actors[i] if i < len(actors) else ""
                        character = characters[i] if i < len(characters) else ""
                        castandrole.append([actor, character])
                    video_data['castandrole'] = castandrole
        
        return video_data
    
    def get_show_metadata(self, show_id: str, show_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get enhanced metadata for a show/series
        """
        # Determine provider from show_id
        
        metadata = {
            'id': show_id,
            'type': 'series',
            'name': show_info.get('name', 'Unknown Show'),
            'description': show_info.get('description', ''),
            'channel': show_info.get('channel', 'France 2'),
            'genres': show_info.get('genres', ['Documentary', 'News', 'Investigation']),  # Use show's own genres
            'year': show_info.get('year', 2024),  # Use show's own year
            'rating': show_info.get('rating', 'Tous publics'),  # Use show's own rating
        }
        
        # Set default images if available
        if 'logo' in show_info:
            metadata['logo'] = show_info['logo']
            metadata['poster'] = show_info['logo']  # Use logo as poster for now
        
        # Copy all additional fields from show_info to preserve them
        for key, value in show_info.items():
            if key not in metadata and value is not None:
                metadata[key] = value
        
        return metadata
    
    def get_episode_metadata(self, episode_data: Dict[str, Any], show_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get enhanced metadata for an episode
        """
        episode_meta = {
            'id': episode_data.get('id', ''),
            'title': episode_data.get('title', 'Unknown Episode'),
            'description': episode_data.get('description', ''),
            'season': 1,  # Default season
            'episode': episode_data.get('episode_number', 1),
            'type': episode_data.get('type', 'episode'),
            'channel': show_info.get('channel', 'France 2'),
            'program': show_info.get('name', ''),
        }
        
        # Add images if available
        if 'poster' in episode_data:
            episode_meta['thumbnail'] = episode_data['poster']
            episode_meta['poster'] = episode_data['poster']
        
        # Add additional metadata
        if 'broadcast_id' in episode_data:
            episode_meta['broadcast_id'] = episode_data['broadcast_id']
        
        return episode_meta
    
    def enhance_metadata_with_api(self, metadata: Dict[str, Any], api_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Enhance metadata with additional API data
        """
        # Process images if available
        if 'images' in api_data:
            metadata = self.populate_images(metadata, api_data['images'])
        
        # Process video-specific metadata if available
        if 'type' in api_data and api_data['type'] in ['integrale', 'extrait']:
            metadata = self.populate_video_metadata(metadata, api_data)
        
        return metadata

# Global instance
metadata_processor = FranceTVMetadataProcessor()
