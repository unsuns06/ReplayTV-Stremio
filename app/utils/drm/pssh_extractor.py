"""
PSSH extraction utilities for DRM content.
Extracted from sixplay.py for shared use.
"""

import base64
from typing import Dict, Optional, Tuple, Any

from app.utils.safe_print import safe_print
from app.providers.fr.extract_pssh import extract_first_pssh, PsshRecord
from app.utils.sixplay_mpd_processor import extract_drm_info_from_mpd


def extract_pssh_from_mpd(
    mpd_url: str,
    provider_name: str = "DRM"
) -> Tuple[Optional[PsshRecord], Optional[str], Dict]:
    """
    Extract PSSH data and DRM metadata from an MPD manifest.
    
    Args:
        mpd_url: URL to the MPD manifest
        provider_name: Provider name for logging
        
    Returns:
        Tuple containing:
        - PSSH record (if found)
        - Raw MPD text
        - Extracted DRM info dict
    """
    mpd_text: Optional[str] = None
    drm_info: Dict = {}
    
    try:
        result = extract_first_pssh(mpd_url, include_mpd=True)
        pssh_record: Optional[PsshRecord]
        mpd_bytes: Optional[bytes]
        
        if isinstance(result, tuple):
            pssh_record, mpd_bytes = result
        else:
            pssh_record, mpd_bytes = result, None
        
        # Decode MPD text
        if mpd_bytes:
            try:
                mpd_text = mpd_bytes.decode('utf-8')
            except Exception:
                mpd_text = mpd_bytes.decode('utf-8', errors='ignore')
        
        # Extract DRM info from MPD
        if mpd_text:
            try:
                drm_info = extract_drm_info_from_mpd(mpd_text) or {}
            except Exception as drm_error:
                drm_info = {}
                safe_print(f"⚠️ [{provider_name}] Failed to parse DRM info: {drm_error}")
        
        # Fallback: create PSSH record from DRM info if not found
        if not pssh_record and drm_info.get('widevine_pssh'):
            try:
                raw = base64.b64decode(drm_info['widevine_pssh'])
                pssh_record = PsshRecord(
                    source='drm_info',
                    parent='ContentProtection',
                    base64_text=drm_info['widevine_pssh'],
                    raw_length=len(raw),
                    system_id='edef8ba9-79d6-4ace-a3c8-27dcd51d21ed'
                )
            except Exception:
                pass
        
        if pssh_record:
            safe_print(f"✅ [{provider_name}] PSSH extracted successfully")
            safe_print(f"📋   Base64 PSSH: {pssh_record.base64_text[:50]}...")
        else:
            safe_print(f"⚠️ [{provider_name}] No PSSH found in MPD manifest")
        
        return pssh_record, mpd_text, drm_info
        
    except Exception as e:
        safe_print(f"❌ [{provider_name}] Error extracting PSSH from MPD: {e}")
        return None, None, {}
