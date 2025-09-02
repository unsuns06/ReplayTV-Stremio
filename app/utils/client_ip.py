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


def normalize_ip(raw: Optional[str]) -> Optional[str]:
    """Normalize IP strings from headers: strip ports, brackets, IPv6-mapped IPv4.

    Examples:
    - "203.0.113.5:1234" -> "203.0.113.5"
    - "[2001:db8::1]:443" -> "2001:db8::1"
    - "::ffff:192.0.2.10" -> "192.0.2.10"
    """
    if not raw:
        return None
    s = str(raw).strip()
    try:
        # Strip IPv6 brackets with optional port
        if s.startswith("[") and "]" in s:
            inside = s[1 : s.index("]")]
            return inside
        # Strip trailing :port for IPv4
        if s.count(":") == 1 and "." in s and s.rsplit(":", 1)[1].isdigit():
            s = s.rsplit(":", 1)[0]
        # Map IPv6-mapped IPv4
        if s.lower().startswith("::ffff:") and s.count(".") == 3:
            tail = s.split(":")[-1]
            return tail
        return s
    except Exception:
        return s


def make_ip_headers(ip: Optional[str] = None) -> Dict[str, str]:
    """Return a set of headers that forward the viewer's IP to upstreams.

    These headers are commonly honored by various upstreams/CDNs.
    Note: Upstreams may or may not trust them, but we always forward.
    """
    real_ip = normalize_ip(ip if ip else get_client_ip())
    if not real_ip:
        return {}
    # Base headers many vendors look at
    headers = {
        "X-Forwarded-For": real_ip,
        "X-Real-IP": real_ip,
        "CF-Connecting-IP": real_ip,
        "True-Client-IP": real_ip,
        # Some stacks also use this legacy header
        "X-Client-IP": real_ip,
    }
    # RFC 7239 Forwarded header (minimal form). Upstreams may ignore without proto/host, but safe to include.
    try:
        headers["Forwarded"] = f"for={real_ip}"
    except Exception:
        pass
    return headers


def merge_ip_headers(headers: Optional[Dict[str, str]] = None, ip: Optional[str] = None) -> Dict[str, str]:
    """Merge IP forwarding headers into an existing headers dict, overriding if present."""
    merged = dict(headers or {})
    for k, v in make_ip_headers(ip).items():
        merged[k] = v
    return merged

