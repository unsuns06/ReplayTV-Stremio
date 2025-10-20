
import json
import os
from threading import Lock

from .safe_print import safe_print

class ProxyConfig:
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
        """
        Gets a proxy URL by name.
        It first checks for an environment variable, then falls back to the config file.
        The environment variable is expected to be in the format 'PROXY_UPPERCASE_NAME'.
        For example, for a proxy named 'fr_default', the env var would be 'PROXY_FR_DEFAULT'.
        """
        env_var_name = f"PROXY_{name.upper()}"
        proxy_url = os.getenv(env_var_name)
        if proxy_url:
            return proxy_url
        return self.proxies.get(name)

    @classmethod
    def get_instance(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = cls(*args, **kwargs)
        return cls._instance

def get_proxy_config():
    return ProxyConfig.get_instance()
