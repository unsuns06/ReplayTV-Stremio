"""
CBC Gem Authentication Module for Stremio Addon
Based on yt-dlp CBC extractor implementation
"""

import json
import time
import base64
import hmac
import hashlib
import urllib.parse
import requests
from typing import Dict, Optional, Tuple, Any
import logging

logger = logging.getLogger(__name__)

class CBCAuthenticator:
    """
    CBC Gem authentication handler that replicates yt-dlp functionality
    """
    
    # Constants from yt-dlp CBC extractor
    CLIENT_ID = 'fc05b0ee-3865-4400-a3cc-3da82c330c23'
    SETTINGS_URL = 'https://services.radio-canada.ca/ott/catalog/v1/gem/settings'
    SHOW_API_URL = 'https://services.radio-canada.ca/ott/catalog/v2/gem/show/'
    VALIDATION_URL = 'https://services.radio-canada.ca/media/validation/v2/'
    CLAIMS_URL = 'https://services.radio-canada.ca/ott/subscription/v2/gem/Subscriber/profile'
    
    def __init__(self, cache_handler=None):
        """
        Initialize CBC authenticator
        
        Args:
            cache_handler: Optional cache handler for storing tokens
        """
        self.cache_handler = cache_handler or {}
        self.refresh_token = None
        self.access_token = None
        self.claims_token = None
        self._ropc_settings = None
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })
    
    def _jwt_decode_hs256(self, token: str) -> Dict[str, Any]:
        """
        Decode JWT token (simplified version)
        """
        try:
            # Split the token
            header, payload, signature = token.split('.')
            
            # Add padding if needed
            payload += '=' * (4 - len(payload) % 4)
            
            # Decode payload
            decoded = base64.b64decode(payload)
            return json.loads(decoded.decode('utf-8'))
        except Exception as e:
            logger.error(f"Failed to decode JWT: {e}")
            return {}
    
    def _is_jwt_expired(self, token: str) -> bool:
        """
        Check if JWT token is expired (with 5 min buffer)
        """
        if not token:
            return True
            
        try:
            payload = self._jwt_decode_hs256(token)
            exp_time = payload.get('exp', 0)
            return exp_time - time.time() < 300  # 5 minute buffer
        except Exception:
            return True
    
    def get_ropc_settings(self) -> Dict[str, Any]:
        """
        Get ROPC settings from CBC
        """
        if self._ropc_settings is None:
            try:
                response = self.session.get(
                    self.SETTINGS_URL,
                    params={'device': 'web'},
                    timeout=30
                )
                response.raise_for_status()
                settings = response.json()
                self._ropc_settings = settings['identityManagement']['ropc']
                logger.info("Successfully fetched ROPC settings")
            except Exception as e:
                logger.error(f"Failed to fetch ROPC settings: {e}")
                raise Exception(f"Failed to get CBC settings: {e}")
        
        return self._ropc_settings
    
    def _call_oauth_api(self, oauth_data: Dict[str, str], note: str = 'OAuth API call') -> Dict[str, Any]:
        """
        Call CBC OAuth API
        """
        ropc_settings = self.get_ropc_settings()
        
        data = {
            'client_id': self.CLIENT_ID,
            'scope': ropc_settings['scopes'],
            **oauth_data
        }
        
        try:
            response = self.session.post(
                ropc_settings['url'],
                data=data,
                timeout=30
            )
            
            logger.info(f"{note}: Status {response.status_code}")
            
            if response.status_code == 400:
                error_data = response.json() if response.content else {}
                error_msg = error_data.get('error_description', 'Invalid credentials')
                raise Exception(f"Authentication failed: {error_msg}")
            
            response.raise_for_status()
            token_data = response.json()
            
            # Store tokens
            self.refresh_token = token_data.get('refresh_token')
            self.access_token = token_data.get('access_token')
            
            # Cache tokens if handler available
            if self.cache_handler and hasattr(self.cache_handler, 'set'):
                self.cache_handler.set('cbc_refresh_token', self.refresh_token)
                self.cache_handler.set('cbc_access_token', self.access_token)
            elif isinstance(self.cache_handler, dict):
                self.cache_handler['cbc_refresh_token'] = self.refresh_token
                self.cache_handler['cbc_access_token'] = self.access_token
            
            logger.info(f"Successfully {note.lower()}")
            return token_data
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error during {note}: {e}")
            raise Exception(f"Network error: {e}")
    
    def login(self, username: str, password: str) -> bool:
        """
        Perform initial login with username/password
        """
        try:
            # Try to load cached tokens first
            self._load_cached_tokens()
            
            if self.refresh_token and self.access_token and not self._is_jwt_expired(self.access_token):
                logger.info("Using cached valid tokens")
                return True
            
            # Perform fresh login
            logger.info("Performing fresh login")
            self._call_oauth_api({
                'grant_type': 'password',
                'username': username,
                'password': password,
            }, 'Login')
            
            return True
            
        except Exception as e:
            logger.error(f"Login failed: {e}")
            return False
    
    def _load_cached_tokens(self):
        """
        Load cached tokens
        """
        try:
            if hasattr(self.cache_handler, 'get'):
                self.refresh_token = self.cache_handler.get('cbc_refresh_token')
                self.access_token = self.cache_handler.get('cbc_access_token')
                self.claims_token = self.cache_handler.get('cbc_claims_token')
            elif isinstance(self.cache_handler, dict):
                self.refresh_token = self.cache_handler.get('cbc_refresh_token')
                self.access_token = self.cache_handler.get('cbc_access_token')
                self.claims_token = self.cache_handler.get('cbc_claims_token')
        except Exception as e:
            logger.error(f"Failed to load cached tokens: {e}")
    
    def get_access_token(self) -> Optional[str]:
        """
        Get valid access token, refreshing if needed
        """
        # Check if current token is valid
        if self.access_token and not self._is_jwt_expired(self.access_token):
            return self.access_token
        
        # Try to refresh if we have refresh token
        if self.refresh_token and not self._is_jwt_expired(self.refresh_token):
            try:
                logger.info("Refreshing access token")
                self._call_oauth_api({
                    'grant_type': 'refresh_token',
                    'refresh_token': self.refresh_token,
                }, 'Token refresh')
                return self.access_token
            except Exception as e:
                logger.error(f"Token refresh failed: {e}")
                # Clear invalid tokens
                self.refresh_token = None
                self.access_token = None
                return None
        
        return None
    
    def get_claims_token(self) -> Optional[str]:
        """
        Get claims token for content access
        """
        # Check if current claims token is valid
        if self.claims_token and not self._is_jwt_expired(self.claims_token):
            return self.claims_token
        
        # Get fresh access token
        access_token = self.get_access_token()
        if not access_token:
            return None
        
        try:
            logger.info("Fetching claims token")
            response = self.session.get(
                self.CLAIMS_URL,
                params={'device': 'web'},
                headers={'Authorization': f'Bearer {access_token}'},
                timeout=30
            )
            response.raise_for_status()
            claims_data = response.json()
            
            self.claims_token = claims_data.get('claimsToken')
            
            # Cache claims token
            if self.cache_handler and hasattr(self.cache_handler, 'set'):
                self.cache_handler.set('cbc_claims_token', self.claims_token)
            elif isinstance(self.cache_handler, dict):
                self.cache_handler['cbc_claims_token'] = self.claims_token
            
            logger.info("Successfully fetched claims token")
            return self.claims_token
            
        except Exception as e:
            logger.error(f"Failed to get claims token: {e}")
            return None
    
    def get_show_info(self, show_id: str) -> Optional[Dict[str, Any]]:
        """
        Get show information from CBC API
        """
        try:
            url = f"{self.SHOW_API_URL}{show_id}"
            response = self.session.get(
                url,
                params={'device': 'web'},
                timeout=30
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to get show info for {show_id}: {e}")
            return None
    
    def get_stream_data(self, media_id: str, require_auth: bool = True) -> Optional[Dict[str, Any]]:
        """
        Get stream data for content
        """
        headers = {}
        
        # Add claims token if authentication required
        if require_auth:
            claims_token = self.get_claims_token()
            if claims_token:
                headers['x-claims-token'] = claims_token
            else:
                logger.warning("No claims token available for authenticated content")
        
        params = {
            'appCode': 'gem',
            'connectionType': 'hd',
            'deviceType': 'ipad',
            'multibitrate': 'true',
            'output': 'json',
            'tech': 'hls',
            'manifestVersion': '2',
            'manifestType': 'desktop',
            'idMedia': media_id,
        }
        
        try:
            response = self.session.get(
                self.VALIDATION_URL,
                params=params,
                headers=headers,
                timeout=30
            )
            response.raise_for_status()
            stream_data = response.json()
            
            # Check for errors in response
            error_code = stream_data.get('errorCode', 0)
            
            if error_code == 1:
                raise Exception("Content is geo-restricted to Canada")
            elif error_code == 35:
                raise Exception("Authentication required for this content")
            elif error_code != 0:
                error_msg = stream_data.get('message', f'Unknown error {error_code}')
                raise Exception(f"CBC API error: {error_msg}")
            
            return stream_data
            
        except Exception as e:
            logger.error(f"Failed to get stream data for {media_id}: {e}")
            return None
    
    def is_authenticated(self) -> bool:
        """
        Check if user is authenticated
        """
        return bool(self.get_access_token())
    
    def logout(self):
        """
        Clear all tokens and logout
        """
        self.refresh_token = None
        self.access_token = None
        self.claims_token = None
        
        # Clear from cache
        if self.cache_handler and hasattr(self.cache_handler, 'delete'):
            self.cache_handler.delete('cbc_refresh_token')
            self.cache_handler.delete('cbc_access_token')  
            self.cache_handler.delete('cbc_claims_token')
        elif isinstance(self.cache_handler, dict):
            self.cache_handler.pop('cbc_refresh_token', None)
            self.cache_handler.pop('cbc_access_token', None)
            self.cache_handler.pop('cbc_claims_token', None)
        
        logger.info("Logged out successfully")