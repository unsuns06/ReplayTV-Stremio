"""Standalone JSON parsing utilities with comprehensive error handling.

Extracted from :class:`~app.utils.http_utils.RobustHTTPClient` so that JSON
parsing can be imported and tested independently of the HTTP client.
"""

import json
import logging
import re
from typing import Any, Dict, Optional

import requests

logger = logging.getLogger(__name__)


def safe_json_parse(
    response: requests.Response,
    context: str = "",
) -> Optional[Dict[str, Any]]:
    """Safely parse a JSON response with multiple fallback strategies.

    Args:
        response: The HTTP response object.
        context: Caller context for log messages (e.g. ``"France TV API"``).

    Returns:
        Parsed JSON dict, or ``None`` when parsing cannot succeed.
    """
    try:
        if response.status_code != 200:
            logger.warning("%s — HTTP %s: %s", context, response.status_code, response.reason)
            return None

        content_type = response.headers.get("content-type", "").lower()

        if not response.text.strip():
            logger.warning("%s — empty response", context)
            return None

        # Allow "text/html, application/json" (FranceTV token endpoint quirk)
        if "text/html" in content_type and "application/json" not in content_type:
            logger.warning("%s — received HTML instead of JSON (likely error page)", context)
            return None

        text = response.text.strip()

        # Unwrap JSONP
        if text.startswith("jsonp_") and text.endswith(");"):
            text = text[text.find("(") + 1: text.rfind(");")]
            logger.debug("%s — extracted JSON from JSONP wrapper", context)

        # Strategy 1: standard parse
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            logger.debug("%s — initial JSON parse failed: %s", context, exc)

        # Strategy 2: single-quote → double-quote fix
        try:
            fixed = re.sub(r"(\w+):", r'"\1":', text.replace("'", '"'))
            return json.loads(fixed)
        except Exception:
            pass

        # Strategy 3: extract outermost {...} from a mixed response
        try:
            m = re.search(r"\{.*\}", text, re.DOTALL)
            if m:
                return json.loads(m.group(0))
        except Exception:
            pass

        # Strategy 4: strip JSONP/callback wrapper
        try:
            start = text.find("{")
            end = text.rfind("}") + 1
            if start != -1 and end > start:
                return json.loads(text[start:end])
        except Exception:
            pass

        logger.error("%s — all JSON parse strategies failed; response: %.500s", context, text)
        return None

    except Exception as exc:
        logger.error("%s — unexpected error in JSON parsing: %s", context, exc)
        return None
