"""
Direct MPD processing for 6play that creates a processed MPD and serves it inline.
This bypasses the need for a separate server by processing the MPD content directly.
"""

import requests
from typing import Optional
from .sixplay_mpd_processor import create_mediaflow_compatible_mpd


def get_processed_mpd_content(original_mpd_url: str, auth_token: Optional[str] = None) -> Optional[str]:
    """
    Download and process a 6play MPD directly, returning the processed content.
    This can be used to create a simplified MPD that MediaFlow can handle.
    """
    try:
        # Download the original MPD with authentication
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36',
            'Origin': 'https://www.6play.fr',
            'Referer': 'https://www.6play.fr/'
        }
        
        if auth_token:
            headers['Authorization'] = f'Bearer {auth_token}'
        
        print(f"[DirectMPDProcessor] Downloading MPD: {original_mpd_url[:50]}...")
        response = requests.get(original_mpd_url, headers=headers, timeout=15)
        
        if response.status_code != 200:
            print(f"[DirectMPDProcessor] Failed to download MPD: {response.status_code}")
            return None
        
        # Process the MPD to make it MediaFlow compatible
        original_mpd = response.text
        processed_mpd = create_mediaflow_compatible_mpd(original_mpd, original_mpd_url)
        
        print(f"[DirectMPDProcessor] MPD processed successfully ({len(processed_mpd)} chars)")
        
        # Check the processing result
        cp_count = processed_mpd.count('ContentProtection')
        mspr_count = processed_mpd.count('<mspr:')
        
        print(f"[DirectMPDProcessor] ContentProtection elements: {cp_count}")
        print(f"[DirectMPDProcessor] MSPR nested elements: {mspr_count}")
        
        if mspr_count == 0:
            print(f"[DirectMPDProcessor] ✅ PlayReady elements successfully removed")
        
        return processed_mpd
        
    except Exception as e:
        print(f"[DirectMPDProcessor] Error processing MPD: {e}")
        return None


def test_mpd_processing_only():
    """Test the MPD processing without MediaFlow to verify it works"""
    # This is a standalone test function
    pass
