"""
Unified API client with robust error handling and retry logic.

Owns its own requests.Session with retry adapters, User-Agent rotation,
and IP header forwarding.  Used directly by all providers via BaseProvider.
"""

import time
import requests
import logging
from typing import Dict, Optional, Any, Union
from requests.adapters import HTTPAdapter

from app.utils.client_ip import merge_ip_headers
from app.utils.user_agent import get_random_windows_ua
from app.utils.json_parser import safe_json_parse

logger = logging.getLogger(__name__)


class ProviderAPIClient:
    """
    Provider-specific HTTP client with retry logic and error handling.

    Features:
    - Session management with retry strategy and connection pooling
    - User-Agent rotation per request
    - IP header forwarding for geo-restricted content
    - Provider-prefixed logging
    """

    def __init__(
        self,
        provider_name: str,
        timeout: int = 15,
        max_retries: int = 3,
    ):
        self.provider_name = provider_name
        self.timeout = timeout
        self.max_retries = max_retries
        self.session = self._create_session()

    def _create_session(self) -> requests.Session:
        """Create a requests session with connection pooling.

        Retries are handled exclusively by the manual loop in
        :meth:`safe_request` (which can also retry on JSON-parse failures);
        the transport adapter deliberately performs none, so a "3-retry"
        request makes at most 3 attempts rather than 3 × 3.
        """
        session = requests.Session()
        adapter = HTTPAdapter(pool_connections=10, pool_maxsize=10, max_retries=0)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        return session

    def safe_json_parse(
        self, response: requests.Response, context: str = ""
    ) -> Optional[Dict[str, Any]]:
        """Parse JSON response with provider-prefixed context."""
        return safe_json_parse(
            response, context=f"[{self.provider_name}] {context}".strip()
        )

    def _prepare_headers(
        self,
        headers: Optional[Dict[str, str]] = None,
        rotate_ua: bool = True,
    ) -> Dict[str, str]:
        """Prepare headers with User-Agent rotation and IP forwarding."""
        current_headers = headers.copy() if headers else {}
        if rotate_ua:
            current_headers["User-Agent"] = get_random_windows_ua()
        current_headers = merge_ip_headers(current_headers)
        return current_headers

    def _parse_json_response(
        self, response: requests.Response, context: str = ""
    ) -> Optional[Dict[str, Any]]:
        return self.safe_json_parse(response, context)

    def safe_request(
        self,
        method: str,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        data: Optional[Union[Dict[str, Any], str]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        timeout: Optional[int] = None,
        max_retries: Optional[int] = None,
    ) -> Optional[Dict[str, Any]]:
        """Make a safe API request with retry logic and error handling."""
        retries = max_retries or self.max_retries
        req_timeout = timeout or self.timeout

        for attempt in range(retries):
            try:
                current_headers = self._prepare_headers(headers)
                logger.debug(
                    "🔍 [%s] %s attempt %d/%d: %s", self.provider_name, method, attempt + 1, retries, url
                )

                if method.upper() == "POST":
                    if json_data:
                        response = self.session.post(
                            url, params=params, headers=current_headers,
                            json=json_data, timeout=req_timeout,
                        )
                    elif data:
                        if current_headers.get("Content-Type") == "application/x-www-form-urlencoded":
                            response = self.session.post(
                                url, params=params, headers=current_headers,
                                data=data, timeout=req_timeout,
                            )
                        else:
                            response = self.session.post(
                                url, params=params, headers=current_headers,
                                json=data, timeout=req_timeout,
                            )
                    else:
                        response = self.session.post(
                            url, params=params, headers=current_headers,
                            timeout=req_timeout,
                        )
                else:
                    response = self.session.get(
                        url, params=params, headers=current_headers,
                        timeout=req_timeout,
                    )

                if response.status_code == 200:
                    result = self._parse_json_response(response)
                    if result is not None:
                        return result
                    if attempt < retries - 1:
                        time.sleep(2 ** attempt)
                        continue
                elif response.status_code in [403, 429, 500, 502, 503]:
                    logger.warning("⚠️ [%s] HTTP %s", self.provider_name, response.status_code)
                    if attempt < retries - 1:
                        time.sleep(2 ** attempt)
                        continue
                else:
                    logger.warning(
                        "⚠️ [%s] HTTP %s: %s", self.provider_name, response.status_code, response.text[:200]
                    )
                    # 404 and friends answer the same way every time — retrying
                    # only multiplies the wait (CBC season probing hits these).
                    return None

            except requests.exceptions.Timeout:
                logger.warning("⏰ [%s] Timeout on attempt %d", self.provider_name, attempt + 1)
                if attempt < retries - 1:
                    time.sleep(2 ** attempt)
                    continue
            except requests.exceptions.RequestException as e:
                logger.warning("⚠️ [%s] Request error: %s", self.provider_name, e)
                if attempt < retries - 1:
                    time.sleep(2 ** attempt)
                    continue
            except Exception as e:
                logger.error("❌ [%s] Unexpected error: %s", self.provider_name, e)
                if attempt < retries - 1:
                    time.sleep(2 ** attempt)
                    continue

        logger.error("❌ [%s] All %d attempts failed for %s...", self.provider_name, retries, url[:60])
        return None

    def get(self, url: str, **kwargs) -> Optional[Dict]:
        """Convenience method for GET requests."""
        return self.safe_request("GET", url, **kwargs)

    def post(self, url: str, **kwargs) -> Optional[Dict]:
        """Convenience method for POST requests."""
        return self.safe_request("POST", url, **kwargs)

    def close(self) -> None:
        """Close the underlying requests session and release connections."""
        self.session.close()

    def raw_request(
        self,
        method: str,
        url: str,
        headers: Optional[Dict] = None,
        **kwargs,
    ) -> Optional[requests.Response]:
        """Make a raw request and return the Response object (non-JSON callers)."""
        try:
            current_headers = self._prepare_headers(headers)
            timeout = kwargs.pop("timeout", self.timeout)
            response = self.session.request(
                method=method,
                url=url,
                headers=current_headers,
                timeout=timeout,
                **kwargs,
            )
            return response
        except Exception as e:
            logger.error("❌ [%s] Raw request error: %s", self.provider_name, e)
            return None
