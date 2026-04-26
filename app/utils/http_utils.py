"""
HTTP utilities for robust API calls with comprehensive error handling
"""

import requests
import logging
from typing import Dict, Optional, Any, Union
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from app.utils.client_ip import merge_ip_headers
from app.utils.safe_print import safe_print
from app.utils.json_parser import safe_json_parse  # noqa: F401 — re-exported for callers

logger = logging.getLogger(__name__)

class RobustHTTPClient:
    """HTTP client with robust error handling and JSON parsing"""
    
    def __init__(self, timeout: int = 10, max_retries: int = 3):
        self.timeout = timeout
        self.max_retries = max_retries
        self.session = self._create_session()
    
    def _create_session(self) -> requests.Session:
        """Create a requests session with retry strategy"""
        session = requests.Session()
        
        # Configure retry strategy (compatible with newer urllib3 versions)
        try:
            # Try newer urllib3 version parameter name
            retry_strategy = Retry(
                total=self.max_retries,
                status_forcelist=[429, 500, 502, 503, 504],
                allowed_methods=["HEAD", "GET", "OPTIONS"],
                backoff_factor=1
            )
        except TypeError:
            # Fallback to older urllib3 version parameter name
            retry_strategy = Retry(
                total=self.max_retries,
                status_forcelist=[429, 500, 502, 503, 504],
                method_whitelist=["HEAD", "GET", "OPTIONS"],
                backoff_factor=1
            )
        
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        return session
    
    def safe_json_parse(self, response: requests.Response, context: str = "") -> Optional[Dict[str, Any]]:
        """Safely parse JSON response. Delegates to :func:`app.utils.json_parser.safe_json_parse`."""
        return safe_json_parse(response, context)
    
    def safe_request(
        self, 
        method: str, 
        url: str, 
        context: str = "",
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Union[Dict[str, Any], str]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Optional[requests.Response]:
        """
        Make a safe HTTP request with comprehensive error handling
        
        Args:
            method: HTTP method (GET, POST, etc.)
            url: Request URL
            context: Context for logging
            headers: Request headers
            params: URL parameters
            data: Request data
            json_data: JSON data for POST requests
            **kwargs: Additional requests arguments
            
        Returns:
            Response object or None if request fails
        """
        try:
            # Set default headers
            default_headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            if headers:
                default_headers.update(headers)
            # Ensure viewer IP is forwarded to upstreams
            default_headers = merge_ip_headers(default_headers)
            
            # Set timeout
            timeout = kwargs.pop('timeout', self.timeout)
            
            logger.debug(f"{context} - Making {method} request to {url}")
            
            response = self.session.request(
                method=method,
                url=url,
                headers=default_headers,
                params=params,
                data=data,
                json=json_data,
                timeout=timeout,
                **kwargs
            )
            
            logger.debug(f"{context} - Received response: {response.status_code} {response.reason}")
            return response
            
        except requests.exceptions.Timeout:
            safe_print(f"\n⏰ TIMEOUT ERROR - {context}")
            safe_print(f"   URL: {url}")
            safe_print(f"   Timeout: {timeout}s")
            safe_print("⏰ END TIMEOUT ERROR\n")
            logger.error(f"{context} - Request timeout ({timeout}s) for {url}")
            return None
            
        except requests.exceptions.ConnectionError as e:
            safe_print(f"\n🔌 CONNECTION ERROR - {context}")
            safe_print(f"   URL: {url}")
            safe_print(f"   Error: {str(e)}")
            safe_print("🔌 END CONNECTION ERROR\n")
            logger.error(f"{context} - Connection error for {url}: {e}")
            return None
            
        except requests.exceptions.HTTPError as e:
            safe_print(f"\n🌐 HTTP ERROR - {context}")
            safe_print(f"   URL: {url}")
            safe_print(f"   Error: {str(e)}")
            safe_print("🌐 END HTTP ERROR\n")
            logger.error(f"{context} - HTTP error for {url}: {e}")
            return None
            
        except Exception as e:
            safe_print(f"\n❌ UNEXPECTED HTTP ERROR - {context}")
            safe_print(f"   URL: {url}")
            safe_print(f"   Error Type: {type(e).__name__}")
            safe_print(f"   Error: {str(e)}")
            import traceback
            safe_print("   Traceback:")
            traceback.print_exc()
            safe_print("❌ END UNEXPECTED HTTP ERROR\n")
            logger.error(f"{context} - Unexpected error for {url}: {e}")
            return None
    
    def get_json(
        self, 
        url: str, 
        context: str = "",
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Optional[Dict[str, Any]]:
        """
        Convenience method for GET requests that return JSON
        
        Args:
            url: Request URL
            context: Context for logging
            headers: Request headers
            params: URL parameters
            **kwargs: Additional requests arguments
            
        Returns:
            Parsed JSON data or None if request/parsing fails
        """
        response = self.safe_request(
            method="GET",
            url=url,
            context=context,
            headers=headers,
            params=params,
            **kwargs
        )
        
        if response is None:
            return None
            
        return self.safe_json_parse(response, context)
    
    def post_json(
        self, 
        url: str, 
        context: str = "",
        headers: Optional[Dict[str, str]] = None,
        data: Optional[Union[Dict[str, Any], str]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Optional[Dict[str, Any]]:
        """
        Convenience method for POST requests that return JSON
        
        Args:
            url: Request URL
            context: Context for logging
            headers: Request headers
            data: Form data
            json_data: JSON data
            **kwargs: Additional requests arguments
            
        Returns:
            Parsed JSON data or None if request/parsing fails
        """
        response = self.safe_request(
            method="POST",
            url=url,
            context=context,
            headers=headers,
            data=data,
            json_data=json_data,
            **kwargs
        )
        
        if response is None:
            return None
            
        return self.safe_json_parse(response, context)


# Create a global instance for convenience
http_client = RobustHTTPClient()


def safe_api_call(func, context: str = "", default_return=None):
    """
    Decorator/wrapper for API calls to ensure they don't crash the application
    
    Args:
        func: Function to execute
        context: Context for logging
        default_return: Value to return if function fails
        
    Returns:
        Function result or default_return if function fails
    """
    try:
        return func()
    except Exception as e:
        # Print detailed error information to console for debugging
        safe_print(f"\n💥 API CALL ERROR - {context}")
        safe_print(f"   Error Type: {type(e).__name__}")
        safe_print(f"   Error Message: {str(e)}")
        
        # Print traceback for more detailed debugging
        import traceback
        safe_print("   Traceback:")
        traceback.print_exc()
        safe_print("💥 END API CALL ERROR\n")
        
        # Also log to logger
        logger.error(f"{context} - API call failed: {e}")
        logger.error(f"{context} - Traceback: {traceback.format_exc()}")
        
        return default_return
