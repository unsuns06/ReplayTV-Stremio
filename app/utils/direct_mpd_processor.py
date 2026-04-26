"""Backward-compatible re-export — implementation moved to app.utils.drm."""
from app.utils.drm.direct_mpd_processor import DirectMPDProcessor, get_processed_mpd_content

__all__ = ['DirectMPDProcessor', 'get_processed_mpd_content']
