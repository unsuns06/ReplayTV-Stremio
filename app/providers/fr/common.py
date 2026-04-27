"""
Shared helpers for French (and other) content providers.

Import this module from mytf1, sixplay, francetv, cbc, etc.
It must NOT import from any individual provider module to avoid
circular imports.
"""

import logging
import requests

from typing import Dict, Optional

from app.utils.credentials import load_credentials
from app.utils.proxy_config import get_proxy_config
from app.utils.user_agent import get_random_windows_ua

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# DRM / processed-file helpers
# ---------------------------------------------------------------------------

def check_processed_file(episode_id: str, provider_tag: str = "Provider") -> Optional[Dict]:
    """Check whether a DRM-free processed file already exists.

    Inspection order:
    1. Real-Debrid shared folder (``realdebridfolder`` credential).
    2. nm3u8_processor ``/stream/`` endpoint.

    Args:
        episode_id:   Raw episode identifier used as the filename stem
                      (e.g. ``"1234567"``).
        provider_tag: Short label prepended to log messages (e.g. ``"MyTF1"``).

    Returns:
        A stream-info dict with ``url``, ``manifest_type``, ``title`` and
        ``filename`` keys when the file is found, otherwise ``None``.
    """
    proxy_config = get_proxy_config()
    processor_url = proxy_config.get_proxy("nm3u8_processor")
    if not processor_url:
        logger.error(
            "❌ [%s] nm3u8_processor not configured in credentials.json",
            provider_tag,
        )
        return None

    processed_filename = f"{episode_id}.mp4"
    logger.debug("✅ [%s] Looking for processed file: %s", provider_tag, processed_filename)

    # ------------------------------------------------------------------
    # 1. Real-Debrid folder
    # ------------------------------------------------------------------
    try:
        all_creds = load_credentials()
        rd_folder = all_creds.get("realdebridfolder")

        if rd_folder:
            logger.debug(
                "🔍 [%s] Checking RD folder for '%s'…", provider_tag, processed_filename
            )
            rd_headers = {
                "User-Agent": get_random_windows_ua(),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9,fr;q=0.8",
                "Accept-Encoding": "gzip, deflate, br",
                "DNT": "1",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
                "Cache-Control": "max-age=0",
            }
            try:
                folder_resp = requests.get(rd_folder, headers=rd_headers, timeout=10)
                if folder_resp.status_code == 200 and processed_filename in folder_resp.text:
                    rd_file_url = rd_folder.rstrip("/") + "/" + processed_filename
                    logger.debug(
                        "✅ [%s] File '%s' found in RD folder.", provider_tag, processed_filename
                    )
                    return {
                        "url": rd_file_url,
                        "manifest_type": "video",
                        "title": "✅ [RD] DRM-Free Video",
                        "filename": processed_filename,
                    }
                logger.warning(
                    "⚠️ [%s] '%s' not in RD folder, checking processor…",
                    provider_tag, processed_filename,
                )
            except requests.exceptions.Timeout:
                logger.warning("⚠️ [%s] RD folder request timed out.", provider_tag)
            except requests.exceptions.RequestException as exc:
                logger.error("❌ [%s] RD folder request error: %s", provider_tag, exc)
        else:
            logger.warning("⚠️ [%s] Real-Debrid folder not configured.", provider_tag)
    except Exception as exc:
        logger.error("❌ [%s] Error checking Real-Debrid: %s", provider_tag, exc)

    # ------------------------------------------------------------------
    # 2. nm3u8_processor /stream/ endpoint
    # ------------------------------------------------------------------
    processed_url = f"{processor_url}/stream/{processed_filename}"
    logger.debug(
        "🔍 [%s] Checking processor URL: %s", provider_tag, processed_url
    )
    try:
        check_resp = requests.head(processed_url, timeout=5)
        if check_resp.status_code == 200:
            logger.debug(
                "✅ [%s] Processed file exists at processor URL.", provider_tag
            )
            return {
                "url": processed_url,
                "manifest_type": "video",
                "title": "✅ DRM-Free Video",
                "filename": processed_filename,
            }
        logger.warning(
            "⚠️ [%s] Processor file not found (HTTP %s).",
            provider_tag, check_resp.status_code,
        )
    except Exception as exc:
        logger.error("❌ [%s] Error checking processor URL: %s", provider_tag, exc)

    return None