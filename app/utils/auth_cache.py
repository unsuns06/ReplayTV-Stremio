"""Cross-request persistence for provider auth tokens.

Provider instances are created per request (see ``ProviderFactory``), so any
token stored on the instance is discarded when the request ends.  Without
this module, MyTF1 and 6play performed a full multi-round-trip login on
*every* stream request.  CBC already solved this with the shared cache
(``CBCAuthenticator``); this module generalises that pattern.

Usage::

    state = load_auth_state("mytf1")
    if state:
        self.auth_token = state["auth_token"]
    ...
    store_auth_state("mytf1", {"auth_token": token}, token_for_ttl=token)

The TTL is derived from the JWT ``exp`` claim when possible (minus a safety
buffer), falling back to a conservative default.
"""

import logging
import time
from typing import Any, Dict, Optional

import jwt

from app.utils.cache import cache
from app.utils.cache_keys import CacheKeys

logger = logging.getLogger(__name__)

DEFAULT_TOKEN_TTL = 4 * 3600   # 4 hours when the token carries no usable exp
EXPIRY_BUFFER = 300            # refresh 5 minutes before actual expiry


def ttl_from_jwt(token: Optional[str], default: int = DEFAULT_TOKEN_TTL) -> int:
    """Return seconds until *token* expires (minus a buffer), or *default*.

    The token is decoded without signature verification — we only need the
    ``exp`` claim to pick a cache TTL, not to trust the token.
    """
    if not token:
        return default
    try:
        decoded = jwt.decode(token, options={"verify_signature": False})
        exp = decoded.get("exp")
        if exp:
            return max(int(exp - time.time()) - EXPIRY_BUFFER, 0)
    except Exception as e:
        logger.debug("auth_cache: could not decode JWT for TTL: %s", e)
    return default


def store_auth_state(
    provider: str,
    state: Dict[str, Any],
    token_for_ttl: Optional[str] = None,
    ttl: Optional[int] = None,
) -> None:
    """Persist *state* (a dict of tokens/IDs) for *provider*.

    Args:
        provider: Provider key, e.g. ``"mytf1"``.
        state: Arbitrary JSON-ish dict the provider needs to resume a session.
        token_for_ttl: A JWT whose ``exp`` claim determines the cache TTL.
        ttl: Explicit TTL override in seconds (wins over *token_for_ttl*).
    """
    effective_ttl = ttl if ttl is not None else ttl_from_jwt(token_for_ttl)
    if effective_ttl <= 0:
        logger.debug("auth_cache: %s token already expired — not caching", provider)
        return
    cache.set(CacheKeys.auth_state(provider), state, ttl=effective_ttl)
    logger.debug("auth_cache: stored %s auth state (ttl=%ds)", provider, effective_ttl)


def load_auth_state(provider: str) -> Optional[Dict[str, Any]]:
    """Return the cached auth state for *provider*, or ``None``."""
    state = cache.get(CacheKeys.auth_state(provider))
    if state is not None and not isinstance(state, dict):
        return None
    return state


def clear_auth_state(provider: str) -> None:
    """Drop the cached auth state for *provider* (e.g. after a 401)."""
    cache.delete(CacheKeys.auth_state(provider))
