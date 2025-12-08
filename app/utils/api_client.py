"""
Unified API client with robust error handling and retry logic.
Replaces duplicated _safe_api_call implementations across all providers.
"""

import time
import requests
import logging
from typing import Dict, Optional, Any, Union
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from app.utils.client_ip import merge_ip_headers
from app.utils.safe_print import safe_print
from app.utils.user_agent import get_random_windows_ua
from app.utils.http_utils import http_client  # Consolidated JSON parsing

logger = logging.getLogger(__name__)


class ProviderAPIClient:
    """
    Unified HTTP client for provider API calls.
    
    Features:
    - Automatic retry with exponential backoff
    - User-Agent rotation
    - IP header forwarding for geo-restricted content
    - Robust JSON parsing with multiple fallback strategies
    - Detailed logging for debugging
    """
    
    def __init__(
        self, 
        provider_name: str, 
        timeout: int = 15, 
        max_retries: int = 3
    ):
        self.provider_name = provider_name
        self.timeout = timeout
        self.max_retries = max_retries
        self.session = self._create_session()
    
    def _create_session(self) -> requests.Session:
        """Create a requests session with retry strategy"""
        session = requests.Session()
        
        # Configure retry strategy
        try:
            retry_strategy = Retry(
                total=self.max_retries,
                status_forcelist=[429, 500, 502, 503, 504],
                allowed_methods=["HEAD", "GET", "POST", "OPTIONS"],
                backoff_factor=1
            )
        except TypeError:
            # Fallback for older urllib3
            retry_strategy = Retry(
                total=self.max_retries,
                status_forcelist=[429, 500, 502, 503, 504],
                method_whitelist=["HEAD", "GET", "POST", "OPTIONS"],
                backoff_factor=1
            )
        
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        return session
    
    def _prepare_headers(
        self, 
        headers: Optional[Dict[str, str]] = None,
        rotate_ua: bool = True
    ) -> Dict[str, str]:
        """Prepare headers with User-Agent rotation and IP forwarding"""
        current_headers = headers.copy() if headers else {}
        
        # Rotate User-Agent
        if rotate_ua:
            current_headers['User-Agent'] = get_random_windows_ua()
        
        # Forward viewer IP to upstream
        current_headers = merge_ip_headers(current_headers)
        
        return current_headers
    
    def _parse_json_response(
        self, 
        response: requests.Response,
        context: str = ""
    ) -> Optional[Dict[str, Any]]:
        """
        Parse JSON response using consolidated RobustHTTPClient.
        Provides comprehensive error handling including JSONP, HTML detection,
        quote fixing, and detailed logging.
        """
        # Delegate to RobustHTTPClient for comprehensive JSON parsing
        return http_client.safe_json_parse(
            response, 
            context=f"[{self.provider_name}] {context}".strip()
        )
    
    def safe_request(
        self,
        method: str,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        data: Optional[Union[Dict[str, Any], str]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        timeout: Optional[int] = None,
        max_retries: Optional[int] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Make a safe API request with retry logic and error handling.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            url: Target URL
            params: Query parameters
            headers: Request headers
            data: Form data or raw data
            json_data: JSON body data
            timeout: Request timeout (defaults to instance timeout)
            max_retries: Max retry attempts (defaults to instance max_retries)
            
        Returns:
            Parsed JSON response or None on failure
        """
        retries = max_retries or self.max_retries
        req_timeout = timeout or self.timeout
        
        for attempt in range(retries):
            try:
                current_headers = self._prepare_headers(headers)
                
                safe_print(f"🔍 [{self.provider_name}] {method} attempt {attempt + 1}/{retries}: {url[:80]}...")
                
                if method.upper() == 'POST':
                    if json_data:
                        response = self.session.post(
                            url, params=params, headers=current_headers,
                            json=json_data, timeout=req_timeout
                        )
                    elif data:
                        # Check Content-Type for form vs json
                        if current_headers.get('Content-Type') == 'application/x-www-form-urlencoded':
                            response = self.session.post(
                                url, params=params, headers=current_headers,
                                data=data, timeout=req_timeout
                            )
                        else:
                            response = self.session.post(
                                url, params=params, headers=current_headers,
                                json=data, timeout=req_timeout
                            )
                    else:
                        response = self.session.post(
                            url, params=params, headers=current_headers,
                            timeout=req_timeout
                        )
                else:
                    response = self.session.get(
                        url, params=params, headers=current_headers,
                        timeout=req_timeout
                    )
                
                if response.status_code == 200:
                    result = self._parse_json_response(response)
                    if result is not None:
                        return result
                    
                    # JSON parse failed, retry
                    if attempt < retries - 1:
                        time.sleep(2 ** attempt)
                        continue
                        
                elif response.status_code in [403, 429, 500, 502, 503]:
                    safe_print(f"⚠️ [{self.provider_name}] HTTP {response.status_code}")
                    if attempt < retries - 1:
                        time.sleep(2 ** attempt)
                        continue
                else:
                    safe_print(f"⚠️ [{self.provider_name}] HTTP {response.status_code}: {response.text[:200]}")
                    
            except requests.exceptions.Timeout:
                safe_print(f"⏰ [{self.provider_name}] Timeout on attempt {attempt + 1}")
                if attempt < retries - 1:
                    time.sleep(2 ** attempt)
                    continue
                    
            except requests.exceptions.RequestException as e:
                safe_print(f"⚠️ [{self.provider_name}] Request error: {e}")
                if attempt < retries - 1:
                    time.sleep(2 ** attempt)
                    continue
                    
            except Exception as e:
                safe_print(f"❌ [{self.provider_name}] Unexpected error: {e}")
                if attempt < retries - 1:
                    time.sleep(2 ** attempt)
                    continue
        
        safe_print(f"❌ [{self.provider_name}] All {retries} attempts failed for {url[:60]}...")
        return None
    
    def get(self, url: str, **kwargs) -> Optional[Dict]:
        """Convenience method for GET requests"""
        return self.safe_request('GET', url, **kwargs)
    
    def post(self, url: str, **kwargs) -> Optional[Dict]:
        """Convenience method for POST requests"""
        return self.safe_request('POST', url, **kwargs)
    
    def raw_request(
        self,
        method: str,
        url: str,
        headers: Optional[Dict] = None,
        **kwargs
    ) -> Optional[requests.Response]:
        """
        Make a raw request and return the Response object.
        Useful when you need access to non-JSON responses.
        """
        try:
            current_headers = self._prepare_headers(headers)
            timeout = kwargs.pop('timeout', self.timeout)
            
            response = self.session.request(
                method=method,
                url=url,
                headers=current_headers,
                timeout=timeout,
                **kwargs
            )
            return response
        except Exception as e:
            safe_print(f"❌ [{self.provider_name}] Raw request error: {e}")
            return None
