from typing import Dict, Optional
from contextvars import ContextVar

# Context variable to track the current request's client IP
_client_ip_ctx: ContextVar[Optional[str]] = ContextVar("client_ip", default=None)


def set_client_ip(ip: Optional[str]) -> None:
    """Set the current viewer/client IP for this request context."""
    _client_ip_ctx.set(ip)


def get_client_ip(default: Optional[str] = None) -> Optional[str]:
    """Get the current viewer/client IP from context (if any)."""
    ip = _client_ip_ctx.get()
    return ip if ip else default


def make_ip_headers(ip: Optional[str] = None) -> Dict[str, str]:
    """Return a set of headers that forward the viewer's IP to upstreams.

    These headers are commonly honored by various upstreams/CDNs.
    Note: Upstreams may or may not trust them, but we always forward.
    """
    real_ip = ip if ip else get_client_ip()
    if not real_ip:
        return {}
    return {
        # Widely used/understood headers
        "X-Forwarded-For": real_ip,
        "X-Real-IP": real_ip,
        # Some CDNs/vendors look at these
        "CF-Connecting-IP": real_ip,
        "True-Client-IP": real_ip,
    }


def merge_ip_headers(headers: Optional[Dict[str, str]] = None, ip: Optional[str] = None) -> Dict[str, str]:
    """Merge IP forwarding headers into an existing headers dict, overriding if present."""
    merged = dict(headers or {})
    for k, v in make_ip_headers(ip).items():
        merged[k] = v
    return merged

