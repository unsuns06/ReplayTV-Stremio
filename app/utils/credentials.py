import json
import os
import logging
from typing import Dict, Any, Optional

from app.utils.json_parser import parse_json_text

logger = logging.getLogger(__name__)


def _lenient_parse(text: str, context: str) -> Optional[Dict[str, Any]]:
    """Attempt to parse non-strict JSON with diagnostic logging on first failure."""
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        preview = text[max(0, e.pos - 80): min(len(text), e.pos + 80)]
        logger.error(
            "%s - JSONDecodeError: %s at line %d column %d (char %d); snippet: %s",
            context, e.msg, e.lineno, e.colno, e.pos, preview,
        )

    result = parse_json_text(text, context)
    if result is not None:
        return result

    logger.error("%s - Lenient parsing attempts failed", context)
    return None


def _load_from_env() -> Optional[Dict[str, Any]]:
    """Load credentials from CREDENTIALS_JSON environment variable if set."""
    raw = os.getenv('CREDENTIALS_JSON')
    if not raw:
        return None
    logger.info("credentials: Using CREDENTIALS_JSON environment variable")
    parsed = _lenient_parse(raw, "credentials.env:CREDENTIALS_JSON")
    if parsed is None:
        logger.error("credentials: Failed to parse CREDENTIALS_JSON")
    return parsed


def _load_from_file(path: str) -> Optional[Dict[str, Any]]:
    """Load credentials from a specific file path with diagnostics."""
    if not os.path.exists(path):
        logger.info("credentials: File not found: %s", path)
        return None

    try:
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        logger.info("credentials: Loading credentials from %s (%d bytes)", path, len(content))
        parsed = _lenient_parse(content, f"credentials.file:{path}")
        if parsed is None:
            logger.error("credentials: Failed to parse file %s", path)
        return parsed
    except Exception as e:
        logger.error("credentials: Unexpected error reading %s: %s", path, e)
        return None


# Module-level credentials cache — loaded once per process, never re-read from disk.
# This eliminates 5-10 file reads per request cycle (every BaseProvider.__init__,
# get_provider_credentials call, ProxyConfig.load_proxies, etc.)
_cached_credentials: Optional[Dict[str, Any]] = None


def load_credentials() -> Dict[str, Any]:
    """Load credentials from env or files, with robust diagnostics for deployment debugging.

    Result is cached for the lifetime of the process.  Call :func:`reload_credentials`
    to force a re-read (useful for live credential rotation without a restart).
    """
    global _cached_credentials
    if _cached_credentials is not None:
        return _cached_credentials

    # Try environment variable first (useful on cloud)
    creds = _load_from_env()
    if creds is not None:
        _cached_credentials = creds
        return creds

    # Resolve repository root based on this file location
    repo_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    primary_path = os.path.join(repo_root, 'credentials.json')
    fallback_path = os.path.join(repo_root, 'credentials-test.json')

    # Primary: credentials.json
    creds = _load_from_file(primary_path)
    if creds is not None:
        _cached_credentials = creds
        return creds

    # Fallback: credentials-test.json
    logger.warning("credentials: Falling back to credentials-test.json")
    creds = _load_from_file(fallback_path)
    if creds is not None:
        _cached_credentials = creds
        return creds

    logger.warning("credentials: No credentials could be loaded; using empty credentials")
    _cached_credentials = {}
    return {}


def reload_credentials() -> Dict[str, Any]:
    """Clear the credentials cache and reload from source.

    Useful after updating credentials at runtime without restarting the server.
    Returns the freshly loaded credentials dict.
    """
    global _cached_credentials
    _cached_credentials = None
    logger.info("credentials: Cache cleared — reloading credentials from source")
    return load_credentials()


def get_provider_credentials(provider_name: str) -> Dict[str, Any]:
    """Get credentials for a specific provider with defensive defaults."""
    credentials = load_credentials()
    provider = credentials.get(provider_name, {})
    if not isinstance(provider, dict):
        logger.error("credentials: Provider '%s' section is not an object; got %s", provider_name, type(provider).__name__)
        return {}
    return provider