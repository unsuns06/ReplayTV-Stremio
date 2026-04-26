"""Singleton loader for geo-proxy configuration.

Proxies are stored in ``credentials.json`` under the ``proxies`` key and can
be overridden per-proxy with ``PROXY_<NAME_UPPER>`` environment variables.
"""

import json
import os
from threading import Lock

from .safe_print import safe_print


class ProxyConfig:
    """Thread-safe singleton that loads proxy URLs from credentials.json.

    Each proxy is keyed by a short name (e.g. ``fr_default``, ``nm3u8_processor``).
    An environment variable ``PROXY_<NAME_UPPER>`` always takes precedence over
    the value in the config file, making it easy to override in containerised
    deployments without changing the file.
    """

    _instance = None
    _lock = Lock()

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            with cls._lock:
                if not cls._instance:
                    cls._instance = super(ProxyConfig, cls).__new__(cls)
        return cls._instance

    def __init__(self, config_file=None):
        if not hasattr(self, 'initialized'):
            self.config_file = config_file or os.getenv('CREDENTIALS_FILE', 'credentials.json')
            self.proxies = {}
            self.load_proxies()
            self.initialized = True

    def load_proxies(self):
        """Load the ``proxies`` dict from the config file.

        Silently falls back to an empty dict when the file is missing or
        contains invalid JSON so the server can still start without proxy
        configuration.
        """
        try:
            with open(self.config_file, 'r') as f:
                data = json.load(f)
                self.proxies = data.get('proxies', {})
        except FileNotFoundError:
            safe_print(f"Warning: Proxy config file not found at {self.config_file}", level="warning")
            self.proxies = {}
        except json.JSONDecodeError:
            safe_print(f"Error: Could not decode proxy config file {self.config_file}", level="error")
            self.proxies = {}

    def get_proxy(self, name):
        """Return a proxy URL by name.

        Checks the ``PROXY_<NAME_UPPER>`` environment variable first, then
        falls back to the value loaded from the config file.

        Args:
            name: Proxy key, e.g. ``"fr_default"`` or ``"nm3u8_processor"``.

        Returns:
            URL string, or ``None`` if the proxy is not configured.
        """
        env_var_name = f"PROXY_{name.upper()}"
        proxy_url = os.getenv(env_var_name)
        if proxy_url:
            return proxy_url
        return self.proxies.get(name)

    @classmethod
    def get_instance(cls, *args, **kwargs):
        """Return the singleton instance, creating it on first call."""
        if not cls._instance:
            cls._instance = cls(*args, **kwargs)
        return cls._instance


def get_proxy_config():
    """Return the global :class:`ProxyConfig` singleton."""
    return ProxyConfig.get_instance()
