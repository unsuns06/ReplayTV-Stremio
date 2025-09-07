"""
CBC Gem Stremio Addon - Main Application
Complete implementation with authentication and streaming
"""

from flask import Flask, Response, jsonify, request, render_template_string
from functools import wraps
import json
import re
import os
import logging
from typing import Dict, List, Optional, Any
from urllib.parse import unquote, quote
import time

# Import our CBC authentication module
from cbc_auth import CBCAuthenticator

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Addon configuration
ADDON_CONFIG = {
    'id': 'org.stremio.cbcgem',
    'version': '1.0.0',
    'name': 'CBC Gem',
    'description': 'Stream content from CBC Gem with authentication support',
    'logo': 'https://gem.cbc.ca/favicon.ico',
    'background': 'https://gem.cbc.ca/assets/images/gem-logo.png',
    'types': ['movie', 'series'],
    'catalogs': [
        {
            'type': 'series',
            'id': 'cbc-shows',
            'name': 'CBC Shows',
            'extra': [
                {'name': 'search', 'isRequired': False},
                {'name': 'skip', 'isRequired': False}
            ]
        },
        {
            'type': 'movie', 
            'id': 'cbc-movies',
            'name': 'CBC Movies',
            'extra': [
                {'name': 'search', 'isRequired': False},
                {'name': 'skip', 'isRequired': False}
            ]
        }
    ],
    'resources': [
        {
            'name': 'catalog',
            'types': ['movie', 'series'],
            'idPrefixes': ['cbc']
        },
        {
            'name': 'meta',
            'types': ['movie', 'series'], 
            'idPrefixes': ['cbc']
        },
        {
            'name': 'stream',
            'types': ['movie', 'series'],
            'idPrefixes': ['cbc']
        }
    ],
    'behaviorHints': {
        'configurable': True,
        'configurationRequired': True
    },
    'config': [
        {
            'key': 'email',
            'title': 'CBC Gem Email',
            'type': 'text',
            'required': True
        },
        {
            'key': 'password',
            'title': 'CBC Gem Password', 
            'type': 'password',
            'required': True
        }
    ]
}

# Simple in-memory cache
cache = {}

def respond_with(data):
    """Helper function to build CORS-enabled responses"""
    resp = jsonify(data)
    resp.headers['Access-Control-Allow-Origin'] = '*'
    resp.headers['Access-Control-Allow-Headers'] = '*'
    resp.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
    return resp

def require_config(f):
    """Decorator to ensure configuration is present"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        config = getattr(request, 'addon_config', {})
        if not config.get('email') or not config.get('password'):
            return respond_with({'streams': []})
        return f(*args, **kwargs)
    return decorated_function

def extract_config_from_url():
    """Extract configuration from URL path"""
    # Stremio passes config in URL like /email=test@test.com&password=pass/manifest.json
    path = request.path
    config_match = re.search(r'/([^/]+)/(?:manifest\.json|catalog|meta|stream)', path)
    
    if config_match:
        config_str = unquote(config_match.group(1))
        config = {}
        for param in config_str.split('&'):
            if '=' in param:
                key, value = param.split('=', 1)
                config[key] = value
        return config
    return {}

@app.before_request
def parse_config():
    """Parse configuration from request"""
    config = extract_config_from_url()
    request.addon_config = config

class CBCGemExtractor:
    """CBC Gem content extractor"""
    
    def __init__(self, authenticator: CBCAuthenticator):
        self.auth = authenticator
    
    def extract_show_id_from_url(self, cbc_url: str) -> Optional[str]:
        """Extract show ID from CBC Gem URL"""
        # Pattern: https://gem.cbc.ca/media/show-name/s01e01
        patterns = [
            r'gem\.cbc\.ca/(?:media/)?([^/]+/s\d+e?\d+)',
            r'gem\.cbc\.ca/(?:media/)?([^/]+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, cbc_url)
            if match:
                return match.group(1)
        return None
    
    def parse_episode_info(self, show_id: str) -> Dict[str, Any]:
        """Parse show ID to extract episode information"""
        # Pattern: show-name/s01e01 or show-name/s01
        parts = show_id.split('/')
        show_name = parts[0]
        
        episode_info = {
            'show_name': show_name.replace('-', ' ').title(),
            'season': 1,
            'episode': 1
        }
        
        if len(parts) > 1:
            season_ep = parts[1]
            # Parse s01e01 format
            season_match = re.search(r's(\d+)', season_ep)
            episode_match = re.search(r'e(\d+)', season_ep)
            
            if season_match:
                episode_info['season'] = int(season_match.group(1))
            if episode_match:
                episode_info['episode'] = int(episode_match.group(1))
        
        return episode_info
    
    def get_show_metadata(self, show_id: str) -> Optional[Dict[str, Any]]:
        """Get metadata for a show"""
        try:
            # Extract show name for API call
            show_name = show_id.split('/')[0]
            show_info = self.auth.get_show_info(show_name)
            
            if not show_info:
                return None
                
            episode_info = self.parse_episode_info(show_id)
            
            # Find specific episode or season
            content_items = []
            for content in show_info.get('content', []):
                for lineup in content.get('lineups', []):
                    for item in lineup.get('items', []):
                        if item.get('url') == show_id:
                            content_items.append(item)
            
            if not content_items:
                # If specific episode not found, return show info
                return {
                    'id': f'cbc:{show_id}',
                    'type': 'series',
                    'name': episode_info['show_name'],
                    'description': show_info.get('description', ''),
                    'poster': self._extract_image_url(show_info),
                    'background': self._extract_image_url(show_info, image_type='background'),
                    'genres': show_info.get('genre', []),
                    'year': self._extract_year(show_info),
                }
            
            # Return specific episode info
            item = content_items[0]
            return {
                'id': f'cbc:{show_id}',
                'type': 'series',
                'name': item.get('title', episode_info['show_name']),
                'description': item.get('description', ''),
                'poster': self._extract_image_url(item),
                'background': self._extract_image_url(item, image_type='background'),
                'season': episode_info['season'],
                'episode': episode_info['episode'],
                'duration': item.get('metadata', {}).get('duration'),
                'genres': show_info.get('genre', []),
                'year': self._extract_year(item),
            }
            
        except Exception as e:
            logger.error(f"Error getting metadata for {show_id}: {e}")
            return None
    
    def _extract_image_url(self, item_data: Dict[str, Any], image_type: str = 'poster') -> Optional[str]:
        """Extract image URL from item data"""
        try:
            images = item_data.get('images', {})
            if image_type == 'background':
                return images.get('hero', {}).get('url') or images.get('card', {}).get('url')
            else:
                return images.get('card', {}).get('url') or images.get('poster', {}).get('url')
        except Exception:
            return None
    
    def _extract_year(self, item_data: Dict[str, Any]) -> Optional[int]:
        """Extract year from metadata"""
        try:
            metadata = item_data.get('metadata', {})
            air_date = metadata.get('airDate')
            if air_date:
                return int(air_date[:4])
        except Exception:
            return None
    
    def get_stream_url(self, show_id: str) -> Optional[str]:
        """Get stream URL for content"""
        try:
            # Get show info to find media ID
            show_name = show_id.split('/')[0]
            show_info = self.auth.get_show_info(show_name)
            
            if not show_info:
                logger.error(f"No show info found for {show_name}")
                return None
            
            # Find specific episode
            media_id = None
            for content in show_info.get('content', []):
                for lineup in content.get('lineups', []):
                    for item in lineup.get('items', []):
                        if item.get('url') == show_id:
                            media_id = item.get('idMedia')
                            break
            
            if not media_id:
                logger.error(f"No media ID found for {show_id}")
                return None
            
            # Get stream data
            stream_data = self.auth.get_stream_data(media_id, require_auth=True)
            
            if not stream_data:
                logger.error(f"No stream data for media ID {media_id}")
                return None
            
            return stream_data.get('url')
            
        except Exception as e:
            logger.error(f"Error getting stream URL for {show_id}: {e}")
            return None

# Global extractor instance
extractor = None

def get_authenticator(config: Dict[str, str]) -> CBCAuthenticator:
    """Get or create authenticator instance"""
    global cache
    
    email = config.get('email', '')
    cache_key = f"auth_{hash(email)}"
    
    if cache_key not in cache:
        auth = CBCAuthenticator(cache_handler=cache)
        cache[cache_key] = auth
    
    auth = cache[cache_key]
    
    # Try to login if not authenticated
    if not auth.is_authenticated():
        email = config.get('email', '')
        password = config.get('password', '')
        if email and password:
            success = auth.login(email, password)
            if not success:
                logger.error(f"Failed to authenticate user {email}")
    
    return auth

@app.route('/')
def index():
    """Addon homepage"""
    return """
    <html>
    <head><title>CBC Gem Stremio Addon</title></head>
    <body>
        <h1>CBC Gem Stremio Addon</h1>
        <p>This addon allows you to stream content from CBC Gem through Stremio.</p>
        <p>To use this addon, you need a CBC Gem account.</p>
        <p><strong>Install URL:</strong> <code>{}/manifest.json</code></p>
    </body>
    </html>
    """.format(request.host_url.rstrip('/'))

@app.route('/<path:config>/manifest.json')
@app.route('/manifest.json')
def manifest():
    """Return addon manifest"""
    return respond_with(ADDON_CONFIG)

@app.route('/configure')
def configure():
    """Configuration page"""
    return render_template_string("""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Configure CBC Gem Addon</title>
        <meta charset="utf-8">
        <style>
            body { font-family: Arial, sans-serif; max-width: 600px; margin: 50px auto; padding: 20px; }
            .form-group { margin-bottom: 20px; }
            label { display: block; margin-bottom: 5px; font-weight: bold; }
            input[type="email"], input[type="password"] { 
                width: 100%; padding: 10px; border: 1px solid #ccc; border-radius: 4px; 
            }
            .btn { 
                background: #007bff; color: white; padding: 10px 20px; 
                border: none; border-radius: 4px; cursor: pointer; 
            }
            .btn:hover { background: #0056b3; }
            .install-url { 
                background: #f8f9fa; padding: 15px; border-radius: 4px; 
                margin-top: 20px; word-break: break-all; 
            }
        </style>
    </head>
    <body>
        <h1>CBC Gem Addon Configuration</h1>
        <form id="configForm">
            <div class="form-group">
                <label for="email">CBC Gem Email:</label>
                <input type="email" id="email" name="email" required>
            </div>
            <div class="form-group">
                <label for="password">CBC Gem Password:</label>
                <input type="password" id="password" name="password" required>
            </div>
            <button type="submit" class="btn">Generate Install URL</button>
        </form>
        
        <div id="installUrl" class="install-url" style="display: none;">
            <strong>Install URL for Stremio:</strong><br>
            <span id="urlText"></span>
        </div>

        <script>
            document.getElementById('configForm').addEventListener('submit', function(e) {
                e.preventDefault();
                const email = document.getElementById('email').value;
                const password = document.getElementById('password').value;
                
                if (email && password) {
                    const config = encodeURIComponent(`email=${email}&password=${password}`);
                    const installUrl = `${window.location.origin}/${config}/manifest.json`;
                    
                    document.getElementById('urlText').textContent = installUrl;
                    document.getElementById('installUrl').style.display = 'block';
                }
            });
        </script>
    </body>
    </html>
    """)

@app.route('/<path:config>/catalog/<catalog_type>/<catalog_id>.json')
@require_config
def catalog(catalog_type, catalog_id):
    """Return catalog data"""
    try:
        config = request.addon_config
        auth = get_authenticator(config)
        
        if not auth.is_authenticated():
            return respond_with({'metas': []})
        
        # For now, return empty catalog
        # In a full implementation, you would fetch popular shows/movies from CBC
        return respond_with({'metas': []})
        
    except Exception as e:
        logger.error(f"Error in catalog: {e}")
        return respond_with({'metas': []})

@app.route('/<path:config>/meta/<meta_type>/<meta_id>.json')
@require_config  
def meta(meta_type, meta_id):
    """Return metadata for specific content"""
    try:
        config = request.addon_config
        auth = get_authenticator(config)
        
        if not auth.is_authenticated():
            return respond_with({'meta': {}})
        
        # Extract CBC ID
        if not meta_id.startswith('cbc:'):
            return respond_with({'meta': {}})
        
        show_id = meta_id[4:]  # Remove 'cbc:' prefix
        
        global extractor
        if not extractor:
            extractor = CBCGemExtractor(auth)
        
        metadata = extractor.get_show_metadata(show_id)
        
        if not metadata:
            return respond_with({'meta': {}})
            
        return respond_with({'meta': metadata})
        
    except Exception as e:
        logger.error(f"Error in meta: {e}")
        return respond_with({'meta': {}})

@app.route('/<path:config>/stream/<stream_type>/<stream_id>.json')
@require_config
def stream(stream_type, stream_id):
    """Return streams for content"""
    try:
        config = request.addon_config
        auth = get_authenticator(config)
        
        if not auth.is_authenticated():
            return respond_with({'streams': []})
        
        # Extract CBC ID
        if not stream_id.startswith('cbc:'):
            return respond_with({'streams': []})
        
        show_id = stream_id[4:]  # Remove 'cbc:' prefix
        
        global extractor
        if not extractor:
            extractor = CBCGemExtractor(auth)
        
        stream_url = extractor.get_stream_url(show_id)
        
        if not stream_url:
            return respond_with({'streams': []})
        
        streams = [{
            'url': stream_url,
            'title': 'CBC Gem',
            'behaviorHints': {
                'bingeGroup': 'cbc-gem',
                'countryWhitelist': ['CA']
            }
        }]
        
        return respond_with({'streams': streams})
        
    except Exception as e:
        logger.error(f"Error in stream: {e}")
        return respond_with({'streams': []})

@app.errorhandler(404)
def not_found(error):
    return respond_with({'error': 'Not found'}), 404

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 7000))
    app.run(host='0.0.0.0', port=port, debug=False)