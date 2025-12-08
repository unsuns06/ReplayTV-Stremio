"""
ClearKey/MediaFlow stream building utilities.
Extracted from sixplay.py for shared use.
"""

from typing import Dict, Optional

from app.utils.safe_print import safe_print
from app.utils.encoding import hex_to_base64url
from app.utils.mediaflow import build_mediaflow_url
from app.utils.user_agent import get_random_windows_ua


def build_mediaflow_clearkey_stream(
    original_mpd_url: str,
    mediaflow_url: str,
    mediaflow_password: str,
    base_headers: Dict[str, str],
    key_id_hex: Optional[str],
    key_hex: Optional[str],
    base_url: str = "https://www.6play.fr",
    auth_token: Optional[str] = None,
    is_live: bool = False,
    provider_name: str = "DRM"
) -> Optional[Dict]:
    """
    Create a MediaFlow ClearKey MPD stream.
    
    Args:
        original_mpd_url: Original MPD manifest URL
        mediaflow_url: MediaFlow proxy base URL
        mediaflow_password: MediaFlow API password
        base_headers: Headers to pass through
        key_id_hex: Key ID in hex format
        key_hex: Decryption key in hex format
        base_url: Origin URL for headers
        auth_token: Optional auth token for authorization header
        is_live: Whether this is a live stream
        provider_name: Provider name for logging
        
    Returns:
        Stream dict with MediaFlow URL or None on failure
    """
    if not key_id_hex or not key_hex:
        safe_print(f"⚠️ [{provider_name}] Missing key_id or key for ClearKey")
        return None
    
    if not mediaflow_url or not mediaflow_password:
        safe_print(f"⚠️ [{provider_name}] MediaFlow not configured")
        return None
    
    try:
        # Build MediaFlow headers
        mediaflow_headers = {
            'user-agent': base_headers.get('User-Agent', get_random_windows_ua()),
            'origin': base_url,
            'referer': base_url,
        }
        
        if auth_token:
            mediaflow_headers['authorization'] = f'Bearer {auth_token}'
        
        # Convert keys to base64url format
        key_id_param = hex_to_base64url(key_id_hex) or key_id_hex
        key_param = hex_to_base64url(key_hex) or key_hex
        
        extra_params = {
            'key_id': key_id_param,
            'key': key_param,
        }
        
        # Build MediaFlow URL
        mediaflow_stream_url = build_mediaflow_url(
            base_url=mediaflow_url,
            password=mediaflow_password,
            destination_url=original_mpd_url,
            endpoint='/proxy/mpd/manifest.m3u8',
            request_headers=mediaflow_headers,
            extra_params=extra_params,
        )
        
        safe_print(f"✅ [{provider_name}] MediaFlow ClearKey URL prepared")
        
        return {
            'url': mediaflow_stream_url,
            'manifest_type': 'mpd',
            'externalUrl': original_mpd_url,
            'is_live': is_live,
        }
        
    except Exception as e:
        safe_print(f"❌ [{provider_name}] MediaFlow ClearKey setup failed: {e}")
        return None
