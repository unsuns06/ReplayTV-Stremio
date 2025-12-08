"""
Local MPD server to serve processed 6play MPD files to MediaFlow.
This bypasses the MediaFlow parsing issue by pre-processing the MPD.
"""

import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import requests
from typing import Optional
from .sixplay_mpd_processor import create_mediaflow_compatible_mpd
from app.utils.safe_print import safe_print


class MPDHandler(BaseHTTPRequestHandler):
    """HTTP handler for serving processed MPD files"""
    
    def do_GET(self):
        """Handle GET requests for MPD files"""
        try:
            # Parse the request
            parsed_url = urlparse(self.path)
            query_params = parse_qs(parsed_url.query)
            
            # Extract parameters
            original_mpd_url = query_params.get('url', [None])[0]
            auth_token = query_params.get('token', [None])[0]
            
            if not original_mpd_url:
                self.send_error(400, "Missing URL parameter")
                return
            
            # Download the original MPD with authentication
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36',
                'Origin': 'https://www.6play.fr',
                'Referer': 'https://www.6play.fr/'
            }
            
            if auth_token:
                headers['Authorization'] = f'Bearer {auth_token}'
            
            response = requests.get(original_mpd_url, headers=headers, timeout=10)
            
            if response.status_code != 200:
                self.send_error(response.status_code, f"Failed to fetch MPD: {response.text}")
                return
            
            # Process the MPD to make it MediaFlow compatible
            original_mpd = response.text
            processed_mpd = create_mediaflow_compatible_mpd(original_mpd, original_mpd_url)
            
            # Send the processed MPD
            self.send_response(200)
            self.send_header('Content-Type', 'application/dash+xml')
            self.send_header('Content-Length', str(len(processed_mpd.encode('utf-8'))))
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Access-Control-Allow-Headers', '*')
            self.end_headers()
            
            self.wfile.write(processed_mpd.encode('utf-8'))
            
        except Exception as e:
            safe_print(f"[MPDServer] Error processing request: {e}")
            self.send_error(500, f"Internal server error: {str(e)}")
    
    def log_message(self, format, *args):
        """Override to reduce log noise"""
        pass


class MPDServer:
    """Local server for serving processed MPD files"""
    
    def __init__(self, port: int = 7861):
        self.port = port
        self.server = None
        self.thread = None
        self.running = False
    
    def start(self):
        """Start the MPD server in a background thread"""
        if self.running:
            return
        
        try:
            self.server = HTTPServer(('localhost', self.port), MPDHandler)
            self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
            self.thread.start()
            self.running = True
            safe_print(f"[MPDServer] Started on http://localhost:{self.port}")
        except Exception as e:
            safe_print(f"[MPDServer] Failed to start: {e}")
            raise
    
    def stop(self):
        """Stop the MPD server"""
        if self.server:
            self.server.shutdown()
            self.server.server_close()
            self.running = False
            safe_print("[MPDServer] Stopped")
    
    def get_processed_mpd_url(self, original_mpd_url: str, auth_token: Optional[str] = None) -> str:
        """Get URL for processed MPD that MediaFlow can handle"""
        if not self.running:
            self.start()
        
        # Build URL for our local server
        params = f"url={original_mpd_url}"
        if auth_token:
            params += f"&token={auth_token}"
        
        return f"http://localhost:{self.port}/mpd?{params}"


# Global MPD server instance
_mpd_server = None


def get_mpd_server() -> MPDServer:
    """Get the global MPD server instance"""
    global _mpd_server
    if _mpd_server is None:
        _mpd_server = MPDServer()
    return _mpd_server


def get_processed_mpd_url_for_mediaflow(original_mpd_url: str, auth_token: Optional[str] = None) -> str:
    """
    Get a URL that serves a MediaFlow-compatible version of the 6play MPD.
    This is the main function to use from the provider.
    """
    server = get_mpd_server()
    return server.get_processed_mpd_url(original_mpd_url, auth_token)
