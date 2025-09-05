import json
import requests
import uuid
import re
from typing import Optional, Tuple

class SixPlayAuth:
    """Real 6play authentication implementation based on Gigya API"""
    
    def __init__(self, username=None, password=None):
        self.username = username
        self.password = password
        self.session_token = None
        self.account_id = None
        self.device_id = '_luid_' + str(uuid.UUID(int=uuid.getnode()))
        
        # API endpoints
        self.login_url = 'https://login.6play.fr/accounts.login'
        self.token_url = 'https://front-auth.6cloud.fr/v2/platforms/m6group_web/getJwt'
        self.api_key_url = 'https://www.6play.fr/connexion'
        self.js_bundle_url = 'https://www.6play.fr/main-%s.bundle.js'
        
        # Default API key (fallback)
        self.default_api_key = "3_hH5KBv25qZTd_sURpixbQW6a4OsiIzIEF2Ei_2H7TXTGLJb_1Hr4THKZianCQhWK"
        
        # Patterns for extracting API key and JS ID
        self.pattern_api_key = re.compile(r'"eu1.gigya.com",key:"(.*?)"')
        self.pattern_js_id = re.compile(r'main-(.*?)\.bundle\.js')
    
    def _get_api_key(self) -> str:
        """Get the current API key from 6play website"""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            # Get JS ID from connection page
            response = requests.get(self.api_key_url, headers=headers, timeout=10)
            js_id_matches = self.pattern_js_id.findall(response.text)
            
            if not js_id_matches:
                print("[SixPlayAuth] Could not find JS ID, using default API key")
                return self.default_api_key
            
            js_id = js_id_matches[0]
            
            # Get actual API key from JS bundle
            bundle_response = requests.get(self.js_bundle_url % js_id, headers=headers, timeout=10)
            bundle_response.encoding = 'utf-8'
            
            api_key_matches = self.pattern_api_key.findall(bundle_response.text)
            
            if not api_key_matches:
                print("[SixPlayAuth] Could not extract API key from bundle, using default")
                return self.default_api_key
            
            api_key = api_key_matches[0]
            print(f"[SixPlayAuth] Successfully extracted API key: {api_key[:20]}...")
            return api_key
            
        except Exception as e:
            print(f"[SixPlayAuth] Error getting API key: {e}")
            return self.default_api_key
    
    def login(self) -> bool:
        """Authenticate with 6play using Gigya API"""
        try:
            if not self.username or not self.password:
                print("[SixPlayAuth] No credentials provided")
                return False
            
            # Get current API key
            api_key = self._get_api_key()
            
            # Build login payload
            payload = {
                "loginID": self.username,
                "password": self.password,
                "apiKey": api_key,
                "format": "jsonp",
                "callback": "jsonp_3bbusffr388pem4"
            }
            
            # Login headers
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Referer': 'https://www.6play.fr/connexion'
            }
            
            print(f"[SixPlayAuth] Attempting login for user: {self.username}")
            
            # Make login request
            response = requests.post(self.login_url, data=payload, headers=headers, timeout=10)
            
            # Parse JSONP response
            json_text = response.text.replace('jsonp_3bbusffr388pem4(', '').replace(');', '')
            json_data = json.loads(json_text)
            
            if "UID" not in json_data:
                print(f"[SixPlayAuth] Login failed: {json_data.get('errorMessage', 'Unknown error')}")
                return False
            
            # Extract authentication data
            self.account_id = json_data["UID"]
            account_timestamp = json_data["signatureTimestamp"]
            account_signature = json_data["UIDSignature"]
            
            print(f"[SixPlayAuth] Gigya login successful, account ID: {self.account_id}")
            
            # Get JWT token from 6cloud
            uuid_headers = {
                'x-auth-gigya-signature': account_signature,
                'x-auth-gigya-signature-timestamp': account_timestamp,
                'x-auth-gigya-uid': self.account_id,
                'x-auth-device-id': self.device_id,
                'x-customer-name': 'm6web'
            }
            
            token_response = requests.get(self.token_url, headers=uuid_headers, timeout=10)
            token_data = token_response.json()
            
            self.session_token = token_data["token"]
            
            print(f"[SixPlayAuth] JWT token obtained: {self.session_token[:20]}...")
            return True
            
        except Exception as e:
            print(f"[SixPlayAuth] Login error: {e}")
            return False
    
    def is_authenticated(self) -> bool:
        """Check if we have a valid session"""
        return self.session_token is not None and self.account_id is not None
    
    def get_auth_data(self) -> Optional[Tuple[str, str]]:
        """Get authentication data for API calls"""
        if self.is_authenticated():
            return self.account_id, self.session_token
        return None
    
    def refresh_session(self) -> bool:
        """Refresh the authentication session"""
        # For now, just try to login again
        return self.login()