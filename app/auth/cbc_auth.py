#!/usr/bin/env python3
"""
CBC Gem Authentication Module
Based on the yt-dlp CBC extractor implementation
"""

import time
import logging
from typing import Optional, Dict, Any
try:
    import jwt
except ImportError:
    try:
        import PyJWT as jwt
    except ImportError:
        # Fallback implementation without JWT validation
        class jwt:
            @staticmethod
            def decode(token, options=None):
                import json
                import base64
                # Simple JWT decode without verification
                parts = token.split('.')
                if len(parts) >= 2:
                    payload = parts[1]
                    # Add padding if needed
                    payload += '=' * (4 - len(payload) % 4)
                    decoded_bytes = base64.urlsafe_b64decode(payload)
                    return json.loads(decoded_bytes)
                return {}
import requests

logger = logging.getLogger(__name__)

class CBCAuthenticator:
    """
    CBC Gem OAuth 2.0 authenticator using ROPC flow
    """
    
    CLIENT_ID = 'fc05b0ee-3865-4400-a3cc-3da82c330c23'
    
    def __init__(self, cache_handler=None):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        
        # Token storage
        self.refresh_token = None
        self.access_token = None
        self.claims_token = None
        
        # Cache handler for token persistence
        self.cache_handler = cache_handler or {}
        
        # ROPC settings cache
        self._ropc_settings = None
    
    def get_ropc_settings(self) -> Dict[str, Any]:
        """
        Get ROPC settings from CBC API
        """
        if not self._ropc_settings:
            try:
                response = self.session.get(
                    'https://services.radio-canada.ca/ott/catalog/v1/gem/settings',
                    params={'device': 'web'},
                    timeout=30
                )
                response.raise_for_status()
                data = response.json()
                self._ropc_settings = data['identityManagement']['ropc']
                logger.info("Retrieved ROPC settings")
            except Exception as e:
                logger.error(f"Failed to get ROPC settings: {e}")
                raise Exception(f"Failed to get ROPC settings: {e}")
        
        return self._ropc_settings
    
    def _is_jwt_expired(self, token: str) -> bool:
        """
        Check if JWT token is expired (with 5 minute buffer)
        """
        if not token:
            return True
        
        try:
            # Decode without verification to check expiry
            decoded = jwt.decode(token, options={"verify_signature": False})
            exp_time = decoded.get('exp', 0)
            current_time = time.time()
            
            # Add 5 minute buffer
            return exp_time - current_time < 300
        except Exception:
            return True
    
    def _call_oauth_api(self, oauth_data: Dict[str, Any], note: str = 'OAuth API call') -> Dict[str, Any]:
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
            
        except Exception as e: # requests.exceptions.RequestException
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
                }, 'Refresh token')
                return self.access_token
            except Exception as e:
                logger.error(f"Token refresh failed: {e}")
                # Clear invalid tokens
                self.refresh_token = None
                self.access_token = None
                return None
        
        logger.warning("No valid access token available")
        return None
    
    def get_claims_token(self) -> Optional[str]:
        """
        Get valid claims token for content access
        """
        # Check if current claims token is valid
        if self.claims_token and not self._is_jwt_expired(self.claims_token):
            return self.claims_token
        
        # Get fresh access token
        access_token = self.get_access_token()
        if not access_token:
            logger.error("No access token available for claims token")
            return None
        
        try:
            logger.info("Fetching claims token")
            response = self.session.get(
                'https://services.radio-canada.ca/ott/subscription/v2/gem/Subscriber/profile',
                params={'device': 'web'},
                headers={'Authorization': f'Bearer {access_token}'},
                timeout=30
            )
            logger.info(f"Claims token API response: {response.status_code}")
            
            if response.status_code == 401:
                logger.error("Access token expired or invalid when fetching claims token")
                # Clear tokens and force re-auth path
                self.access_token = None
                self.refresh_token = None
                return None
            
            response.raise_for_status()
            
            data = response.json()
            self.claims_token = data.get('claimsToken')
            
            if not self.claims_token:
                logger.error("No claims token in response payload")
                logger.error(str(data)[:500])
                return None
            
            # Cache claims token
            if self.cache_handler and hasattr(self.cache_handler, 'set'):
                self.cache_handler.set('cbc_claims_token', self.claims_token)
            elif isinstance(self.cache_handler, dict):
                self.cache_handler['cbc_claims_token'] = self.claims_token
            
            logger.info("Successfully fetched claims token")
            logger.info(f"Claims token (truncated): {self.claims_token[:20]}...")
            return self.claims_token
            
        except Exception as e:
            logger.error(f"Failed to get claims token: {e}")
            return None
    
    def get_authenticated_headers(self) -> Dict[str, str]:
        """
        Get headers with authentication tokens for API requests
        """
        headers = {
            'User-Agent': self.session.headers['User-Agent'],
            'Referer': 'https://gem.cbc.ca/',
            'Origin': 'https://gem.cbc.ca'
        }
        
        # Add claims token if available
        claims_token = self.get_claims_token()
        if claims_token:
            headers['x-claims-token'] = claims_token
        
        return headers
    
    def is_authenticated(self) -> bool:
        """
        Check if user is properly authenticated
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