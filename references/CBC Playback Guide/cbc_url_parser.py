#!/usr/bin/env python3
"""
CBC Gem URL Parser and Converter
Utility to convert CBC Gem URLs to Stremio-compatible IDs
"""

import re
from typing import Optional, Dict, Any
from urllib.parse import urlparse, unquote

class CBCURLParser:
    """
    Parse and convert CBC Gem URLs to internal IDs
    """
    
    @staticmethod
    def parse_cbc_url(url: str) -> Optional[Dict[str, Any]]:
        """
        Parse CBC Gem URL and extract show/episode information
        
        Supported formats:
        - https://gem.cbc.ca/media/schitts-creek/s06e01
        - https://gem.cbc.ca/schitts-creek/s06e01
        - https://gem.cbc.ca/media/show-name
        - https://gem.cbc.ca/show-name
        
        Returns:
            Dict with parsed information or None if invalid
        """
        if not url or 'gem.cbc.ca' not in url:
            return None
            
        try:
            parsed = urlparse(url)
            path = parsed.path.strip('/')
            
            # Remove 'media/' prefix if present
            if path.startswith('media/'):
                path = path[6:]
            
            # Split path components
            parts = path.split('/')
            if not parts or not parts[0]:
                return None
            
            show_name = parts[0]
            
            result = {
                'show_name': show_name,
                'show_id': show_name,
                'full_id': path,
                'type': 'series',  # Default to series
                'season': None,
                'episode': None
            }
            
            # Parse season/episode if present
            if len(parts) > 1:
                season_episode = parts[1]
                
                # Pattern: s01e01, s01, s1e1, etc.
                season_match = re.search(r's(\d+)', season_episode, re.IGNORECASE)
                episode_match = re.search(r'e(\d+)', season_episode, re.IGNORECASE)
                
                if season_match:
                    result['season'] = int(season_match.group(1))
                
                if episode_match:
                    result['episode'] = int(episode_match.group(1))
                    result['type'] = 'episode'
                elif season_match and not episode_match:
                    result['type'] = 'season'
            
            return result
            
        except Exception as e:
            print(f"Error parsing CBC URL {url}: {e}")
            return None
    
    @staticmethod
    def create_stremio_id(show_info: Dict[str, Any]) -> str:
        """
        Create Stremio-compatible ID from parsed show info
        """
        return f"cbc:{show_info['full_id']}"
    
    @staticmethod
    def parse_stremio_id(stremio_id: str) -> Optional[str]:
        """
        Extract CBC show ID from Stremio ID
        """
        if not stremio_id.startswith('cbc:'):
            return None
        return stremio_id[4:]  # Remove 'cbc:' prefix
    
    @staticmethod
    def normalize_show_name(show_name: str) -> str:
        """
        Normalize show name for display
        """
        return show_name.replace('-', ' ').replace('_', ' ').title()


def test_url_parser():
    """Test the URL parser with various formats"""
    test_urls = [
        'https://gem.cbc.ca/media/schitts-creek/s06e01',
        'https://gem.cbc.ca/schitts-creek/s06e01', 
        'https://gem.cbc.ca/media/heartland/s15e10',
        'https://gem.cbc.ca/coroner/s04',
        'https://gem.cbc.ca/media/marketplace',
        'https://gem.cbc.ca/the-national',
        'invalid-url',
    ]
    
    parser = CBCURLParser()
    
    for url in test_urls:
        print(f"\nTesting: {url}")
        result = parser.parse_cbc_url(url)
        if result:
            print(f"  Show: {parser.normalize_show_name(result['show_name'])}")
            print(f"  ID: {result['full_id']}")
            print(f"  Type: {result['type']}")
            if result['season']:
                print(f"  Season: {result['season']}")
            if result['episode']:
                print(f"  Episode: {result['episode']}")
            print(f"  Stremio ID: {parser.create_stremio_id(result)}")
        else:
            print("  Invalid or unsupported URL")


if __name__ == '__main__':
    test_url_parser()