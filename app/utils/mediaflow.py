from urllib.parse import urlencode
from typing import Dict, Optional


def build_mediaflow_url(
    base_url: str,
    password: str,
    destination_url: str,
    endpoint: Optional[str] = None,
    request_headers: Optional[Dict[str, str]] = None,
) -> str:
    """Build a MediaFlow proxy URL with h_ header params.

    Mirrors the simple pattern used in TVVoo: `${base}${path}?d=<dest>&api_password=<psw>&h_<k>=<v>`.
    Header keys are passed as lowercased names after the `h_` prefix, consistent with MediaFlow.
    """
    path = (endpoint or "/proxy/hls/manifest.m3u8").lstrip("/")
    base = base_url.rstrip("/")
    q = {
        "d": destination_url,
        "api_password": password,
    }
    if request_headers:
        for k, v in request_headers.items():
            if v is None:
                continue
            key = k.lower()
            q[f"h_{key}"] = v
    return f"{base}/{path}?" + urlencode(q)

