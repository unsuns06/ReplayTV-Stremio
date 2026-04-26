"""Downloads a 6play MPD and rewrites it for MediaFlow compatibility."""

import requests
from typing import Any, Optional

from app.utils.drm.base import DRMProcessor
from app.utils.drm.sixplay_mpd_processor import create_mediaflow_compatible_mpd
from app.utils.safe_print import safe_print


class DirectMPDProcessor(DRMProcessor):
    """Downloads an MPD and rewrites it in one step.

    Wraps :class:`~app.utils.drm.sixplay_mpd_processor.SixPlayMPDProcessor`
    with an HTTP fetch so callers don't need two separate calls.
    """

    def process(self, url: str, **kwargs) -> Any:
        """Download and rewrite the MPD at *url*.

        Args:
            url: URL of the original MPD manifest.
            **kwargs:
                auth_token (str | None): Bearer token for the download request.

        Returns:
            The rewritten MPD string, or ``None`` on failure.
        """
        return get_processed_mpd_content(url, auth_token=kwargs.get('auth_token'))


def get_processed_mpd_content(original_mpd_url: str,
                               auth_token: Optional[str] = None) -> Optional[str]:
    """Download and rewrite a 6play MPD for MediaFlow compatibility."""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36',
            'Origin': 'https://www.6play.fr',
            'Referer': 'https://www.6play.fr/',
        }
        if auth_token:
            headers['Authorization'] = f'Bearer {auth_token}'

        safe_print(f"[DirectMPDProcessor] Downloading MPD: {original_mpd_url[:50]}...")
        response = requests.get(original_mpd_url, headers=headers, timeout=15)

        if response.status_code != 200:
            safe_print(f"[DirectMPDProcessor] Failed to download MPD: {response.status_code}")
            return None

        processed_mpd = create_mediaflow_compatible_mpd(response.text, original_mpd_url)
        safe_print(f"[DirectMPDProcessor] MPD processed successfully ({len(processed_mpd)} chars)")

        mspr_count = processed_mpd.count('<mspr:')
        if mspr_count == 0:
            safe_print("[DirectMPDProcessor] ✅ PlayReady elements successfully removed")

        return processed_mpd
    except Exception as e:
        safe_print(f"[DirectMPDProcessor] Error processing MPD: {e}")
        return None
