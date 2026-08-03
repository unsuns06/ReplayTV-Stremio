"""Viewer IP extraction, normalization and forwarding.

One resolution pipeline (:func:`resolve_viewer_ip`) replaces the two
overlapping extractors that previously lived here with different header
priorities (``extract_request_ip`` vs ``get_public_client_ip``).

Priority order (highest first):
1. ``x-ip-token``  — signed JWT-shaped token carrying the user's external IP
2. ``cf-connecting-ip`` / ``true-client-ip`` — CDN-provided single values
3. ``x-real-ip``  — reverse-proxy single value
4. ``x-forwarded-for`` — first (public, when filtering) hop in the chain
5. The raw connection address (``request.client.host``) / request context
"""

from typing import Dict, Optional
from contextvars import ContextVar
import ipaddress

# Context variable to track the current request's client IP
_client_ip_ctx: ContextVar[Optional[str]] = ContextVar("client_ip", default=None)

# Single-value forwarding headers, in trust order
_SINGLE_IP_HEADERS = ("cf-connecting-ip", "true-client-ip", "x-real-ip")


def _decode_ip_token(token: str) -> Optional[str]:
    """Decode the ``ip`` claim from an unsigned JWT-shaped token header.

    The token is NOT verified — it is trusted as far as the proxy chain is
    trusted (same assumption used throughout this addon for IP forwarding).
    """
    try:
        import json as _json
        import base64
        parts = token.split(".")
        if len(parts) != 3:
            return None
        pad = "=" * (-len(parts[1]) % 4)
        payload = _json.loads(base64.urlsafe_b64decode(parts[1] + pad).decode("utf-8", errors="ignore"))
        return payload.get("ip")
    except Exception:
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


def is_public_ip(ip_str: str) -> bool:
    """Check if an IP address is public (not private/local/loopback)."""
    try:
        ip = ipaddress.ip_address(ip_str)
        return ip.is_global
    except (ValueError, ipaddress.AddressValueError):
        return False


def extract_public_ip_from_xff(xff_header: str) -> Optional[str]:
    """Extract the first public IP from an X-Forwarded-For header chain."""
    if not xff_header:
        return None
    for ip in (part.strip() for part in xff_header.split(',')):
        normalized = normalize_ip(ip)
        if normalized and is_public_ip(normalized):
            return normalized
    return None


def resolve_viewer_ip(
    headers: Optional[Dict[str, str]] = None,
    client_host: Optional[str] = None,
    public_only: bool = False,
) -> Optional[str]:
    """Resolve the viewer's IP from request data — the single extraction pipeline.

    Args:
        headers: Mapping of header name → value (case-insensitive lookup attempted).
        client_host: The raw ``request.client.host`` value (may be a private IP).
        public_only: When True, only return globally-routable addresses
            (private/loopback candidates are skipped).

    Returns:
        Normalised IP string, or ``None`` if no usable IP is found.
    """
    headers = headers or {}

    def _h(name: str) -> Optional[str]:
        getter = getattr(headers, "get", None)
        if getter is None:
            return None
        return getter(name) or getter(name.lower()) or getter(name.upper()) \
            or getter(name.title()) or getter("-".join(p.capitalize() for p in name.split("-")))

    def _accept(candidate: Optional[str]) -> Optional[str]:
        ip = normalize_ip(candidate)
        if not ip:
            return None
        if public_only and not is_public_ip(ip):
            return None
        return ip

    # 1. Signed token (contains the user's real external IP)
    token = _h("x-ip-token")
    if token:
        ip = _accept(_decode_ip_token(token))
        if ip:
            return ip

    # 2./3. CDN / reverse-proxy single-value headers
    for header in _SINGLE_IP_HEADERS:
        ip = _accept(_h(header))
        if ip:
            return ip

    # 4. X-Forwarded-For chain
    xff = _h("x-forwarded-for")
    if xff:
        if public_only:
            ip = extract_public_ip_from_xff(xff)
        else:
            ip = normalize_ip(xff.split(",")[0].strip())
        if ip:
            return ip

    # 5. Direct connection IP (may be private/loopback in proxied setups)
    return _accept(client_host)


def extract_request_ip(headers, client_host: Optional[str] = None) -> Optional[str]:
    """Extract the viewer IP from an incoming HTTP request (any IP accepted)."""
    return resolve_viewer_ip(headers, client_host, public_only=False)


def get_public_client_ip(request_headers: Optional[Dict[str, str]] = None) -> Optional[str]:
    """Get the viewer's public IP, filtering out private/local addresses.

    Falls back to the request-context IP when headers yield nothing public.
    """
    ip = resolve_viewer_ip(request_headers, client_host=None, public_only=True)
    if ip:
        return ip
    context_ip = normalize_ip(get_client_ip())
    if context_ip and is_public_ip(context_ip):
        return context_ip
    return None


def set_client_ip(ip: Optional[str]) -> None:
    """Set the current viewer/client IP for this request context."""
    _client_ip_ctx.set(ip)


def get_client_ip(default: Optional[str] = None) -> Optional[str]:
    """Get the current viewer/client IP from context (if any)."""
    ip = _client_ip_ctx.get()
    return ip if ip else default


def set_ip_from_request(headers, client_host: Optional[str] = None) -> None:
    """Extract viewer IP from request data and set it in the context variable.

    Convenience wrapper used by the request middleware so the two-step
    extract → set dance lives in one place.
    """
    set_client_ip(resolve_viewer_ip(headers, client_host))


def make_ip_headers(ip: Optional[str] = None, request_headers: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    """Return a set of headers that forward the viewer's public IP to upstreams.

    These headers are commonly honored by various upstreams/CDNs.
    Note: Upstreams may or may not trust them, but we always forward.
    """
    real_ip = ip or get_public_client_ip(request_headers)
    if not real_ip:
        return {}

    return {
        "X-Forwarded-For": real_ip,
        "X-Real-IP": real_ip,
        "CF-Connecting-IP": real_ip,
        "True-Client-IP": real_ip,
        # Some stacks also use this legacy header
        "X-Client-IP": real_ip,
        # RFC 7239 Forwarded header (minimal form)
        "Forwarded": f"for={real_ip}",
    }


def merge_ip_headers(headers: Optional[Dict[str, str]] = None, ip: Optional[str] = None, request_headers: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    """Merge IP forwarding headers into an existing headers dict, overriding if present."""
    merged = dict(headers or {})
    merged.update(make_ip_headers(ip, request_headers))
    return merged
