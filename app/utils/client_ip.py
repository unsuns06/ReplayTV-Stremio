from typing import Dict, Optional
from contextvars import ContextVar
import ipaddress

# Context variable to track the current request's client IP
_client_ip_ctx: ContextVar[Optional[str]] = ContextVar("client_ip", default=None)


def set_client_ip(ip: Optional[str]) -> None:
    """Set the current viewer/client IP for this request context."""
    _client_ip_ctx.set(ip)


def get_client_ip(default: Optional[str] = None) -> Optional[str]:
    """Get the current viewer/client IP from context (if any)."""
    ip = _client_ip_ctx.get()
    return ip if ip else default


def is_public_ip(ip_str: str) -> bool:
    """Check if an IP address is public (not private/local/loopback)."""
    try:
        ip = ipaddress.ip_address(ip_str)
        return ip.is_global
    except (ValueError, ipaddress.AddressValueError):
        return False


def extract_public_ip_from_xff(xff_header: str) -> Optional[str]:
    """Extract the first public IP from X-Forwarded-For header chain."""
    if not xff_header:
        return None
    
    # Split by comma and process each IP
    ips = [ip.strip() for ip in xff_header.split(',')]
    for ip in ips:
        normalized = normalize_ip(ip)
        if normalized and is_public_ip(normalized):
            return normalized
    return None


def get_public_client_ip(request_headers: Optional[Dict[str, str]] = None) -> Optional[str]:
    """Get the viewer's public IP, filtering out private/local addresses.
    
    Checks common forwarding headers in order of preference:
    1. CF-Connecting-IP (Cloudflare)
    2. True-Client-IP (Akamai)
    3. X-Real-IP (nginx)
    4. X-Forwarded-For (first public IP in chain)
    5. Context IP (if public)
    """
    headers = request_headers or {}
    
    # Check direct forwarding headers first
    for header in ['CF-Connecting-IP', 'True-Client-IP', 'X-Real-IP']:
        if header in headers:
            ip = normalize_ip(headers[header])
            if ip and is_public_ip(ip):
                return ip
    
    # Check X-Forwarded-For chain
    if 'X-Forwarded-For' in headers:
        public_ip = extract_public_ip_from_xff(headers['X-Forwarded-For'])
        if public_ip:
            return public_ip
    
    # Fall back to context IP if it's public
    context_ip = get_client_ip()
    if context_ip:
        normalized = normalize_ip(context_ip)
        if normalized and is_public_ip(normalized):
            return normalized
    
    return None


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


def make_ip_headers(ip: Optional[str] = None, request_headers: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    """Return a set of headers that forward the viewer's public IP to upstreams.

    These headers are commonly honored by various upstreams/CDNs.
    Note: Upstreams may or may not trust them, but we always forward.
    """
    # Use provided IP or try to get public IP from request headers or context
    real_ip = ip
    if not real_ip:
        real_ip = get_public_client_ip(request_headers)
    if not real_ip:
        # Last resort: use context IP only if it's public
        context_ip = normalize_ip(get_client_ip())
        if context_ip and is_public_ip(context_ip):
            real_ip = context_ip
    
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


def merge_ip_headers(headers: Optional[Dict[str, str]] = None, ip: Optional[str] = None, request_headers: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    """Merge IP forwarding headers into an existing headers dict, overriding if present."""
    merged = dict(headers or {})
    for k, v in make_ip_headers(ip, request_headers).items():
        merged[k] = v
    return merged
