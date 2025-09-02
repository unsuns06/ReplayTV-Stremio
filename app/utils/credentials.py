import json
import os
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


def _lenient_parse(text: str, context: str) -> Optional[Dict[str, Any]]:
    """Attempt to parse non-strict JSON and log what was attempted."""
    try:
        # 1) Straight parse
        return json.loads(text)
    except json.JSONDecodeError as e:
        logger.error(
            f"{context} - JSONDecodeError: {e.msg} at line {e.lineno} column {e.colno} (char {e.pos})"
        )
        preview_start = max(0, e.pos - 80)
        preview_end = min(len(text), e.pos + 80)
        snippet = text[preview_start:preview_end]
        logger.error(f"{context} - Content snippet around error [{preview_start}:{preview_end}]: {snippet}")

    # 2) Replace single quotes with double quotes
    try:
        fixed = text.replace("'", '"')
        if fixed != text:
            logger.warning(f"{context} - Retrying after replacing single quotes with double quotes")
        return json.loads(fixed)
    except Exception:
        pass

    # 3) Quote unquoted property names (shallow heuristic)
    try:
        import re
        fixed = re.sub(r'([{,])\s*([A-Za-z_][A-Za-z0-9_]*)\s*:', r'\1"\2":', text)
        if fixed != text:
            logger.warning(f"{context} - Retrying after quoting unquoted property names")
            return json.loads(fixed)
    except Exception:
        pass

    logger.error(f"{context} - Lenient parsing attempts failed")
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
        logger.info(f"credentials: File not found: {path}")
        return None

    try:
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        logger.info(f"credentials: Loading credentials from {path} ({len(content)} bytes)")
        parsed = _lenient_parse(content, f"credentials.file:{path}")
        if parsed is None:
            logger.error(f"credentials: Failed to parse file {path}")
        return parsed
    except Exception as e:
        logger.error(f"credentials: Unexpected error reading {path}: {e}")
        return None


def load_credentials() -> Dict[str, Any]:
    """Load credentials from env or files, with robust diagnostics for deployment debugging."""
    # Try environment variable first (useful on cloud)
    creds = _load_from_env()
    if creds is not None:
        return creds

    # Resolve repository root based on this file location
    repo_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    primary_path = os.path.join(repo_root, 'credentials.json')
    fallback_path = os.path.join(repo_root, 'credentials-test.json')

    # Primary: credentials.json
    creds = _load_from_file(primary_path)
    if creds is not None:
        return creds

    # Fallback: credentials-test.json
    logger.warning("credentials: Falling back to credentials-test.json")
    creds = _load_from_file(fallback_path)
    if creds is not None:
        return creds

    logger.warning("credentials: No credentials could be loaded; using empty credentials")
    return {}


def get_provider_credentials(provider_name: str) -> Dict[str, Any]:
    """Get credentials for a specific provider with defensive defaults."""
    credentials = load_credentials()
    provider = credentials.get(provider_name, {})
    if not isinstance(provider, dict):
        logger.error(f"credentials: Provider '{provider_name}' section is not an object; got {type(provider).__name__}")
        return {}
    return provider