"""
Widevine DRM key extraction utilities.
Extracted from sixplay.py for shared use.
"""

import requests
from typing import Optional

from app.utils.safe_print import safe_print


def extract_widevine_key(
    pssh_value: str,
    drm_token: str,
    license_url: str = "https://lic.drmtoday.com/license-proxy-widevine/cenc/?specConform=true",
    provider_name: str = "DRM"
) -> Optional[str]:
    """
    Extract Widevine decryption key using CDRM API.
    
    Args:
        pssh_value: Base64-encoded PSSH box
        drm_token: DRM authentication token
        license_url: Widevine license server URL
        provider_name: Provider name for logging
        
    Returns:
        Decryption key string or None if extraction fails
    """
    try:
        safe_print(f"🔑 [{provider_name}] Extracting Widevine decryption key...")
        
        # Prepare headers for CDRM API
        headers_data = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/59.0.3041.0 Safari/537.36',
            'x-dt-auth-token': drm_token
        }
        
        # Prepare request payload
        payload = {
            'pssh': pssh_value,
            'licurl': license_url,
            'headers': str(headers_data)
        }
        
        safe_print(f"📋 [{provider_name}] CDRM API request:")
        safe_print(f"📋   PSSH: {pssh_value[:50]}...")
        safe_print(f"📋   License URL: {license_url}")
        
        # Make request to CDRM API
        response = requests.post(
            url='https://cdrm-project.com/api/decrypt',
            headers={'Content-Type': 'application/json'},
            json=payload,
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            if 'message' in result:
                decryption_key = result['message']
                safe_print(f"✅ [{provider_name}] Widevine key extracted successfully")
                safe_print(f"🔑   Key: {decryption_key}")
                return decryption_key
            else:
                safe_print(f"❌ [{provider_name}] No key in CDRM response: {result}")
                return None
        else:
            safe_print(f"❌ [{provider_name}] CDRM API error: {response.status_code}")
            safe_print(f"📋   Response: {response.text[:300]}...")
            return None
            
    except Exception as e:
        safe_print(f"❌ [{provider_name}] Error extracting Widevine key: {e}")
        return None
