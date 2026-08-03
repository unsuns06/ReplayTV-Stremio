"""Geo-proxy configuration.

Proxies live under the ``proxies`` key of the credentials document — loaded
through :func:`app.utils.credentials.load_credentials`, so both the
``credentials.json`` file *and* the ``CREDENTIALS_JSON`` environment variable
work (previously this module read the file directly and silently lost proxy
configuration in env-var-only deployments).

Each proxy is keyed by a short name (e.g. ``fr_default``, ``nm3u8_processor``)
and can be overridden per-proxy with a ``PROXY_<NAME_UPPER>`` environment
variable, making it easy to adjust containerised deployments without changing
the credentials document.
"""

import logging
import os
from typing import Dict, Optional

from app.utils.credentials import load_credentials

logger = logging.getLogger(__name__)


class ProxyConfig:
    """Read-through view over the ``proxies`` section of the credentials doc."""

    @property
    def proxies(self) -> Dict[str, str]:
        """Return the ``proxies`` dict from the credentials document.

        ``load_credentials`` caches the parsed document for the process
        lifetime, so this property is cheap to call repeatedly.
        """
        proxies = load_credentials().get("proxies", {})
        if not isinstance(proxies, dict):
            logger.error("proxy_config: 'proxies' section is not an object; got %s", type(proxies).__name__)
            return {}
        return proxies

    def get_proxy(self, name: str) -> Optional[str]:
        """Return a proxy URL by name.

        Checks the ``PROXY_<NAME_UPPER>`` environment variable first, then
        falls back to the value from the credentials document.

        Args:
            name: Proxy key, e.g. ``"fr_default"`` or ``"nm3u8_processor"``.

        Returns:
            URL string, or ``None`` if the proxy is not configured.
        """
        env_value = os.getenv(f"PROXY_{name.upper()}")
        if env_value:
            return env_value
        return self.proxies.get(name)


# Module-level instance — same pattern as app.utils.cache
_proxy_config = ProxyConfig()


def get_proxy_config() -> ProxyConfig:
    """Return the global :class:`ProxyConfig` instance."""
    return _proxy_config
