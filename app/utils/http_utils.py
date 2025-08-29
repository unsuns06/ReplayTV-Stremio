"""
HTTP utilities for robust API calls with comprehensive error handling
"""

import json
import requests
import time
import logging
from typing import Dict, List, Optional, Any, Union
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

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
        """
        Safely parse JSON response with comprehensive error handling
        
        Args:
            response: The HTTP response object
            context: Context information for logging (e.g., "France TV API", "TF1 login")
            
        Returns:
            Parsed JSON data or None if parsing fails
        """
        try:
            # Check if response is successful
            if response.status_code != 200:
                logger.warning(f"{context} - HTTP {response.status_code}: {response.reason}")
                return None
            
            # Check content type
            content_type = response.headers.get('content-type', '').lower()
            
            # Handle empty responses
            if not response.text.strip():
                logger.warning(f"{context} - Empty response received")
                return None
            
            # Handle HTML error pages (common in cloud environments)
            if 'text/html' in content_type:
                logger.warning(f"{context} - Received HTML instead of JSON (likely error page)")
                logger.debug(f"{context} - HTML content preview: {response.text[:200]}...")
                return None
            
            # Handle JSONP responses (for 6play)
            text_content = response.text.strip()
            if text_content.startswith('jsonp_') and text_content.endswith(');'):
                # Extract JSON from JSONP
                start_idx = text_content.find('(') + 1
                end_idx = text_content.rfind(');')
                text_content = text_content[start_idx:end_idx]
                logger.debug(f"{context} - Extracted JSON from JSONP wrapper")
            
            # Attempt JSON parsing with fallback strategies
            try:
                data = json.loads(text_content)
                logger.debug(f"{context} - Successfully parsed JSON response")
                return data
                
            except json.JSONDecodeError as json_error:
                # Print detailed JSON error information to console (for immediate debugging)
                print(f"\n🚨 JSON DECODE ERROR - {context}")
                print(f"   Error: {json_error}")
                print(f"   Line: {json_error.lineno}, Column: {json_error.colno}")
                print(f"   Response Status: {response.status_code}")
                print(f"   Content-Type: {content_type}")
                print(f"   URL: {response.url}")
                
                # Show more of the problematic content for debugging
                error_preview = text_content[:1000] if len(text_content) > 1000 else text_content
                print(f"   Response Content: {error_preview}")
                
                # Try to identify common issues
                if '<html' in text_content.lower():
                    print(f"   ⚠️  Response appears to be HTML (error page)")
                elif 'cloudflare' in text_content.lower():
                    print(f"   ⚠️  Cloudflare protection detected")
                elif 'access denied' in text_content.lower():
                    print(f"   ⚠️  Access denied response")
                elif 'rate limit' in text_content.lower():
                    print(f"   ⚠️  Rate limiting detected")
                elif 'forbidden' in text_content.lower():
                    print(f"   ⚠️  Forbidden access")
                elif 'unauthorized' in text_content.lower():
                    print(f"   ⚠️  Unauthorized access")
                
                print(f"   📝 Full response headers: {dict(response.headers)}")
                
                # Try lenient parsing strategies
                print(f"   🔧 Attempting lenient parsing strategies...")
                
                # Strategy 1: Try to fix common JSON issues
                try:
                    # Fix single quotes to double quotes (common issue)
                    fixed_content = text_content.replace("'", '"')
                    # Fix unquoted keys (basic attempt)
                    import re
                    fixed_content = re.sub(r'(\w+):', r'"\1":', fixed_content)
                    data = json.loads(fixed_content)
                    print(f"   ✅ Successfully parsed with quote fixing")
                    logger.info(f"{context} - JSON parsed successfully with quote fixing")
                    return data
                except:
                    pass
                
                # Strategy 2: Try to extract JSON from a larger response
                try:
                    # Look for JSON-like patterns in the response
                    import re
                    json_match = re.search(r'\{.*\}', text_content, re.DOTALL)
                    if json_match:
                        potential_json = json_match.group(0)
                        data = json.loads(potential_json)
                        print(f"   ✅ Successfully extracted and parsed JSON from response")
                        logger.info(f"{context} - JSON extracted and parsed successfully")
                        return data
                except:
                    pass
                
                # Strategy 3: Try to handle JSONP-like responses
                try:
                    # Remove potential JSONP wrapper
                    if '(' in text_content and ')' in text_content:
                        start = text_content.find('{')
                        end = text_content.rfind('}') + 1
                        if start != -1 and end > start:
                            potential_json = text_content[start:end]
                            data = json.loads(potential_json)
                            print(f"   ✅ Successfully parsed JSON after removing wrapper")
                            logger.info(f"{context} - JSON parsed successfully after removing wrapper")
                            return data
                except:
                    pass
                
                print(f"   ❌ All lenient parsing strategies failed")
                print("🚨 END JSON DECODE ERROR\n")
                
                # Also log to logger for file logging
                logger.error(f"{context} - JSON Decode Error: {json_error}")
                logger.error(f"{context} - Full response: {text_content}")
                
                return None
                
        except Exception as e:
            logger.error(f"{context} - Unexpected error in JSON parsing: {e}")
            return None
    
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
            print(f"\n⏰ TIMEOUT ERROR - {context}")
            print(f"   URL: {url}")
            print(f"   Timeout: {timeout}s")
            print("⏰ END TIMEOUT ERROR\n")
            logger.error(f"{context} - Request timeout ({timeout}s) for {url}")
            return None
            
        except requests.exceptions.ConnectionError as e:
            print(f"\n🔌 CONNECTION ERROR - {context}")
            print(f"   URL: {url}")
            print(f"   Error: {str(e)}")
            print("🔌 END CONNECTION ERROR\n")
            logger.error(f"{context} - Connection error for {url}: {e}")
            return None
            
        except requests.exceptions.HTTPError as e:
            print(f"\n🌐 HTTP ERROR - {context}")
            print(f"   URL: {url}")
            print(f"   Error: {str(e)}")
            print("🌐 END HTTP ERROR\n")
            logger.error(f"{context} - HTTP error for {url}: {e}")
            return None
            
        except Exception as e:
            print(f"\n❌ UNEXPECTED HTTP ERROR - {context}")
            print(f"   URL: {url}")
            print(f"   Error Type: {type(e).__name__}")
            print(f"   Error: {str(e)}")
            import traceback
            print(f"   Traceback:")
            traceback.print_exc()
            print("❌ END UNEXPECTED HTTP ERROR\n")
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
        print(f"\n💥 API CALL ERROR - {context}")
        print(f"   Error Type: {type(e).__name__}")
        print(f"   Error Message: {str(e)}")
        
        # Print traceback for more detailed debugging
        import traceback
        print(f"   Traceback:")
        traceback.print_exc()
        print("💥 END API CALL ERROR\n")
        
        # Also log to logger
        logger.error(f"{context} - API call failed: {e}")
        logger.error(f"{context} - Traceback: {traceback.format_exc()}")
        
        return default_return
