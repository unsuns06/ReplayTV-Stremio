from urllib.parse import urlencode
from typing import Dict, Optional


def build_mediaflow_url(
    base_url: str,
    password: str,
    destination_url: str,
    endpoint: Optional[str] = None,
    request_headers: Optional[Dict[str, str]] = None,
    license_url: Optional[str] = None,
    license_headers: Optional[Dict[str, str]] = None,
    extra_params: Optional[Dict[str, str]] = None,
) -> str:
    """Build a MediaFlow proxy URL with h_ header params and optional DRM license support.

    Mirrors the simple pattern used in TVVoo: `${base}${path}?d=<dest>&api_password=<psw>&h_<k>=<v>`.
    Header keys are passed as lowercased names after the `h_` prefix, consistent with MediaFlow.
    
    Args:
        base_url: MediaFlow proxy base URL
        password: MediaFlow API password
        destination_url: Target stream URL to proxy
        endpoint: MediaFlow endpoint path (defaults to HLS proxy)
        request_headers: Headers to pass through to destination
        license_url: DRM license server URL (for Widevine/FairPlay)
        license_headers: Headers to pass to license server
        extra_params: Additional query parameters (e.g., DRM keys) to append
    """
    path = (endpoint or "/proxy/hls/manifest.m3u8").lstrip("/")
    base = base_url.rstrip("/")
    q = {
        "d": destination_url,
        "api_password": password,
    }
    
    # Add request headers with h_ prefix
    if request_headers:
        for k, v in request_headers.items():
            if v is None:
                continue
            key = k.lower()
            q[f"h_{key}"] = v
    
    # Add DRM license parameters if provided
    if license_url:
        q["license_url"] = license_url
    
    if extra_params:
        for k, v in extra_params.items():
            if v is None:
                continue
            q[str(k)] = v

    if license_headers:
        for k, v in license_headers.items():
            if v is None:
                continue
            key = k.lower()
            q[f"license_h_{key}"] = v
    
    return f"{base}/{path}?" + urlencode(q)

