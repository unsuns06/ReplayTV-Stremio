#!/usr/bin/env python3
"""
JSON Proxy utility for routing requests through a proxy service
This helps bypass deployment issues with French TV providers
"""

import json
import requests
import logging
from typing import Dict, List, Optional, Any, Union
from urllib.parse import urlencode, quote
from app.utils.proxy_config import is_proxy_enabled, get_proxy_url, get_proxy_timeout

logger = logging.getLogger(__name__)

class JSONProxyClient:
    """HTTP client that routes requests through a JSON proxy service with fallback"""
    
    def __init__(self, timeout: int = None):
        self.timeout = timeout or get_proxy_timeout()
        self.session = requests.Session()
        
        # Set default headers that work well with proxy services
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-US,en;q=0.9,fr;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        })
    
    def _build_proxy_url(self, target_url: str, params: Optional[Dict] = None) -> str:
        """Build the proxy URL with the target URL encoded"""
        if not is_proxy_enabled():
            return target_url
        
        # Encode the target URL
        encoded_url = quote(target_url, safe='')
        
        # Build proxy URL
        proxy_url = f"{get_proxy_url()}{encoded_url}"
        
        # Add any additional proxy parameters
        if params:
            proxy_url += f"&{urlencode(params)}"
        
        return proxy_url
    
    def _make_request(self, method: str, url: str, use_proxy: bool = True, **kwargs) -> requests.Response:
        """Make a request with proxy or direct fallback"""
        if use_proxy and is_proxy_enabled():
            # Use proxy
            proxy_url = self._build_proxy_url(url, kwargs.get('params'))
            logger.debug(f"Proxying {method} request: {url} -> {proxy_url}")
            
            # Remove params from kwargs since they're now in the proxy URL
            kwargs.pop('params', None)
            
            response = self.session.request(
                method=method,
                url=proxy_url,
                timeout=self.timeout,
                **kwargs
            )
            
            logger.debug(f"Proxy response: {response.status_code} for {url}")
            return response
        else:
            # Use direct request
            logger.debug(f"Direct {method} request: {url}")
            
            response = self.session.request(
                method=method,
                url=url,
                timeout=self.timeout,
                **kwargs
            )
            
            logger.debug(f"Direct response: {response.status_code} for {url}")
            return response
    
    def get(self, url: str, params: Optional[Dict] = None, headers: Optional[Dict] = None, 
            use_proxy: bool = True, **kwargs) -> requests.Response:
        """Make a GET request with proxy or direct fallback"""
        try:
            # Merge headers
            request_headers = self.session.headers.copy()
            if headers:
                request_headers.update(headers)
            
            kwargs['headers'] = request_headers
            kwargs['params'] = params
            
            return self._make_request('GET', url, use_proxy, **kwargs)
            
        except Exception as e:
            logger.error(f"GET request failed for {url}: {e}")
            raise
    
    def post(self, url: str, data: Optional[Union[Dict, str]] = None, json_data: Optional[Dict] = None, 
             params: Optional[Dict] = None, headers: Optional[Dict] = None, use_proxy: bool = True, 
             **kwargs) -> requests.Response:
        """Make a POST request with proxy or direct fallback"""
        try:
            # Merge headers
            request_headers = self.session.headers.copy()
            if headers:
                request_headers.update(headers)
            
            kwargs['headers'] = request_headers
            kwargs['params'] = params
            kwargs['data'] = data
            kwargs['json'] = json_data
            
            return self._make_request('POST', url, use_proxy, **kwargs)
            
        except Exception as e:
            logger.error(f"POST request failed for {url}: {e}")
            raise
    
    def head(self, url: str, headers: Optional[Dict] = None, use_proxy: bool = True, **kwargs) -> requests.Response:
        """Make a HEAD request with proxy or direct fallback"""
        try:
            # Merge headers
            request_headers = self.session.headers.copy()
            if headers:
                request_headers.update(headers)
            
            kwargs['headers'] = request_headers
            
            return self._make_request('HEAD', url, use_proxy, **kwargs)
            
        except Exception as e:
            logger.error(f"HEAD request failed for {url}: {e}")
            raise
    
    def safe_json_parse(self, response: requests.Response, context: str = "") -> Optional[Dict[str, Any]]:
        """
        Safely parse JSON response with enhanced error handling
        
        Args:
            response: The HTTP response object
            context: Context information for logging
            
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
                # Log detailed JSON error information
                logger.error(f"{context} - JSON Decode Error: {json_error}")
                logger.error(f"{context} - Line: {json_error.lineno}, Column: {json_error.colno}")
                logger.error(f"{context} - Response Status: {response.status_code}")
                logger.error(f"{context} - Content-Type: {content_type}")
                logger.error(f"{context} - URL: {response.url}")
                
                # Show problematic content for debugging
                error_preview = text_content[:1000] if len(text_content) > 1000 else text_content
                logger.error(f"{context} - Response Content: {error_preview}")
                
                # Try lenient parsing strategies
                logger.info(f"{context} - Attempting lenient parsing strategies...")
                
                # Strategy 1: Try to fix common JSON issues
                try:
                    # Fix single quotes to double quotes
                    fixed_content = text_content.replace("'", '"')
                    # Fix unquoted keys (basic attempt)
                    import re
                    fixed_content = re.sub(r'(\w+):', r'"\1":', fixed_content)
                    data = json.loads(fixed_content)
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
                            logger.info(f"{context} - JSON parsed successfully after removing wrapper")
                            return data
                except:
                    pass
                
                logger.error(f"{context} - All lenient parsing strategies failed")
                return None
                
        except Exception as e:
            logger.error(f"{context} - Unexpected error in JSON parsing: {e}")
            return None
    
    def get_json(self, url: str, params: Optional[Dict] = None, headers: Optional[Dict] = None, 
                 context: str = "", use_proxy: bool = True, **kwargs) -> Optional[Dict[str, Any]]:
        """
        Convenience method for GET requests that return JSON
        
        Args:
            url: Request URL
            params: URL parameters
            headers: Request headers
            context: Context for logging
            use_proxy: Whether to use proxy (default: True)
            **kwargs: Additional requests arguments
            
        Returns:
            Parsed JSON data or None if request/parsing fails
        """
        try:
            response = self.get(url, params=params, headers=headers, use_proxy=use_proxy, **kwargs)
            return self.safe_json_parse(response, context)
        except Exception as e:
            logger.error(f"{context} - GET request failed: {e}")
            return None
    
    def post_json(self, url: str, data: Optional[Union[Dict, str]] = None, json_data: Optional[Dict] = None,
                  params: Optional[Dict] = None, headers: Optional[Dict] = None, context: str = "", 
                  use_proxy: bool = True, **kwargs) -> Optional[Dict[str, Any]]:
        """
        Convenience method for POST requests that return JSON
        
        Args:
            url: Request URL
            data: Form data
            json_data: JSON data
            params: URL parameters
            headers: Request headers
            context: Context for logging
            use_proxy: Whether to use proxy (default: True)
            **kwargs: Additional requests arguments
            
        Returns:
            Parsed JSON data or None if request/parsing fails
        """
        try:
            response = self.post(url, data=data, json=json_data, params=params, headers=headers, use_proxy=use_proxy, **kwargs)
            return self.safe_json_parse(response, context)
        except Exception as e:
            logger.error(f"{context} - POST request failed: {e}")
            return None

def get_proxy_client() -> JSONProxyClient:
    """Get a configured proxy client instance"""
    return JSONProxyClient()

# Create a global instance for convenience
proxy_client = get_proxy_client()
