#!/usr/bin/env python3
"""
Proxy configuration utility for managing JSON proxy settings
"""

import os
import logging
from typing import Dict, Optional
from app.utils.credentials import load_credentials

logger = logging.getLogger(__name__)

class ProxyConfig:
    """Configuration manager for JSON proxy settings"""
    
    def __init__(self):
        self.credentials = load_credentials()
        self.proxy_config = self.credentials.get('json_proxy', {})
        
        # Proxy settings
        self.proxy_url = self.proxy_config.get('url', 'https://f87h6xkw96.execute-api.ca-central-1.amazonaws.com/api/router?url=')
        self.proxy_timeout = self.proxy_config.get('timeout', 15)
        self.proxy_enabled = self.proxy_config.get('enabled', True)
        
        # Environment variable override
        if os.getenv('JSON_PROXY_ENABLED'):
            self.proxy_enabled = os.getenv('JSON_PROXY_ENABLED').lower() in ('true', '1', 'yes')
        
        if os.getenv('JSON_PROXY_URL'):
            self.proxy_url = os.getenv('JSON_PROXY_URL')
        
        if os.getenv('JSON_PROXY_TIMEOUT'):
            try:
                self.proxy_timeout = int(os.getenv('JSON_PROXY_TIMEOUT'))
            except ValueError:
                logger.warning(f"Invalid JSON_PROXY_TIMEOUT value: {os.getenv('JSON_PROXY_TIMEOUT')}")
    
    def is_enabled(self) -> bool:
        """Check if JSON proxy is enabled"""
        return self.proxy_enabled
    
    def get_proxy_url(self) -> str:
        """Get the configured proxy URL"""
        return self.proxy_url
    
    def get_timeout(self) -> int:
        """Get the configured timeout"""
        return self.proxy_timeout
    
    def get_config(self) -> Dict:
        """Get the complete proxy configuration"""
        return {
            'enabled': self.proxy_enabled,
            'url': self.proxy_url,
            'timeout': self.proxy_timeout
        }
    
    def print_config(self):
        """Print the current proxy configuration"""
        print("🔧 JSON Proxy Configuration:")
        print(f"   Enabled: {self.proxy_enabled}")
        print(f"   URL: {self.proxy_url}")
        print(f"   Timeout: {self.proxy_timeout}s")
        
        if not self.proxy_enabled:
            print("   ⚠️  Proxy is disabled - requests will use direct connections")
        else:
            print("   ✅ Proxy is enabled - requests will be routed through proxy")
    
    def validate_config(self) -> bool:
        """Validate the proxy configuration"""
        if not self.proxy_enabled:
            logger.info("JSON proxy is disabled")
            return True
        
        if not self.proxy_url:
            logger.error("JSON proxy URL is not configured")
            return False
        
        if not self.proxy_url.startswith(('http://', 'https://')):
            logger.error(f"Invalid JSON proxy URL: {self.proxy_url}")
            return False
        
        if self.proxy_timeout <= 0:
            logger.error(f"Invalid JSON proxy timeout: {self.proxy_timeout}")
            return False
        
        logger.info(f"JSON proxy configuration validated: {self.proxy_url}")
        return True

# Global proxy configuration instance
proxy_config = ProxyConfig()

def get_proxy_config() -> ProxyConfig:
    """Get the global proxy configuration instance"""
    return proxy_config

def is_proxy_enabled() -> bool:
    """Check if JSON proxy is enabled"""
    return proxy_config.is_enabled()

def get_proxy_url() -> str:
    """Get the configured proxy URL"""
    return proxy_config.get_proxy_url()

def get_proxy_timeout() -> int:
    """Get the configured proxy timeout"""
    return proxy_config.get_timeout()
