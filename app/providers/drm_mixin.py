"""Mixin for providers that offload DRM-protected content to external processors.

Only the DRM providers (MyTF1, 6play) need the Real-Debrid / nm3u8-processor
integration and the background-processing placeholder streams; keeping them in
a mixin means FranceTV and CBC don't carry the machinery (previously it lived
on ``BaseProvider`` itself).

Expects to be mixed into a :class:`~app.providers.base_provider.BaseProvider`
subclass — relies on ``self.session``, ``self.proxy_config`` and
``self.log_prefix``.
"""

import logging
from typing import Dict, List, Optional
from urllib.parse import quote

from app.utils.credentials import load_credentials
from app.utils.user_agent import get_random_windows_ua

logger = logging.getLogger(__name__)

# Sentinel URL Stremio shows while background DRM processing runs
PROCESSING_PLACEHOLDER_URL = "https://stream-not-available"


class DRMProcessedFileMixin:
    """Pre-processed-file lookup and background DRM processing for DRM providers."""

    def _check_torbox(self, processed_filename: str) -> Optional[List[Dict]]:
        """Check the TorBox WebDAV for a pre-processed file. Returns stream list or None.

        TorBox stores each download in a folder named after the file, so the path is
        ``{tb_webdav_url}/{filename}/{filename}``.
        """
        tb = load_credentials().get("torbox") or {}
        base = tb.get("tb_webdav_url")
        user = tb.get("tb_webdav_username")
        password = tb.get("tb_webdav_password")
        if not (base and user and password):
            return None

        name = quote(processed_filename)
        url = f"{base.rstrip('/')}/{name}/{name}"
        try:
            resp = self.session.head(url, auth=(user, password), timeout=10, allow_redirects=True)
            if resp.status_code != 200:
                return None
        except Exception as exc:
            logger.error("❌ %s TorBox WebDAV error: %s", self.log_prefix, exc)
            return None

        # ponytail: credentials inline in the URL — Stremio can't send per-stream auth
        # headers; switch to a local proxy endpoint if TorBox ever rejects userinfo URLs.
        scheme, rest = url.split("://", 1)
        auth_url = f"{scheme}://{quote(user, safe='')}:{quote(password, safe='')}@{rest}"
        logger.debug("✅ %s File '%s' found on TorBox.", self.log_prefix, processed_filename)
        return [{"url": auth_url, "manifest_type": "video", "title": "✅ [TorBox] DRM-Free Video", "filename": processed_filename}]

    def _check_rd_folder(self, processed_filename: str) -> Optional[List[Dict]]:
        """Check Real-Debrid folder for a pre-processed file. Returns stream list or None."""
        try:
            rd_folder = load_credentials().get("realdebridfolder")
            if not rd_folder:
                return None
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
            resp = self.session.get(rd_folder, headers=rd_headers, timeout=10)
            if resp.status_code == 200 and processed_filename in resp.text:
                url = rd_folder.rstrip("/") + "/" + processed_filename
                logger.debug("✅ %s File '%s' found in RD folder.", self.log_prefix, processed_filename)
                return [{"url": url, "manifest_type": "video", "title": "✅ [RD] DRM-Free Video", "filename": processed_filename}]
        except Exception as exc:
            logger.error("❌ %s RD folder error: %s", self.log_prefix, exc)
        return None

    def _check_processed_file(self, episode_id: str) -> Optional[List[Dict]]:
        """Check whether a DRM-free processed file already exists.

        Returns a single-element stream list so callers can forward it directly to
        the router without re-wrapping, consistent with the List[StreamInfo] contract.
        """
        processor_url = self.proxy_config.get_proxy("nm3u8_processor")
        if not processor_url:
            logger.error("❌ %s nm3u8_processor not configured", self.log_prefix)
            return None

        processed_filename = f"{episode_id}.mp4"
        logger.debug("✅ %s Looking for processed file: %s", self.log_prefix, processed_filename)

        # Order: TorBox → Real-Debrid → processor website
        for check in (self._check_torbox, self._check_rd_folder):
            result = check(processed_filename)
            if result:
                return result

        processed_url = f"{processor_url}/stream/{processed_filename}"
        try:
            check_resp = self.session.head(processed_url, timeout=5)
            if check_resp.status_code == 200:
                logger.debug("✅ %s Processed file exists at processor URL.", self.log_prefix)
                return [{"url": processed_url, "manifest_type": "video", "title": "✅ DRM-Free Video", "filename": processed_filename}]
        except Exception as exc:
            logger.error("❌ %s Error checking processor URL: %s", self.log_prefix, exc)

        return None

    def _make_processing_placeholder(self, started: bool) -> Dict:
        """Return the placeholder stream shown while background processing runs."""
        if started:
            return {
                "url": PROCESSING_PLACEHOLDER_URL,
                "manifest_type": "video",
                "title": "⏳ DRM-Free Video (Processing in background...)",
                "description": "Processing in progress. Please check back in a few minutes.",
            }
        return {
            "url": PROCESSING_PLACEHOLDER_URL,
            "manifest_type": "video",
            "title": "❌ DRM Processing Failed",
            "description": "DRM processing could not be started. Please try again later.",
        }

    def _start_drm_processing(
        self,
        video_url: str,
        save_name: str,
        key: Optional[str] = None,
        keys: Optional[List[str]] = None,
    ) -> Dict:
        """Kick off background DRM processing and return a placeholder stream."""
        from app.utils.drm.nm3u8_drm_processor import process_drm_simple

        result = process_drm_simple(
            url=video_url,
            save_name=save_name,
            key=key,
            keys=keys,
            quality="best",
            format="mkv",
        )
        started = bool(result.get("success"))
        if started:
            logger.debug("✅ %s Background DRM processing started", self.log_prefix)
        else:
            logger.error("⚠️ %s Background DRM processing failed to start: %s",
                         self.log_prefix, result.get("error"))
        return self._make_processing_placeholder(started)
