"""Backward-compatible re-export — implementation moved to app.utils.drm."""
from app.utils.drm.sixplay_mpd_processor import (
    SixPlayMPDProcessor,
    create_mediaflow_compatible_mpd,
    extract_drm_info_from_mpd,
)

__all__ = ['SixPlayMPDProcessor', 'create_mediaflow_compatible_mpd', 'extract_drm_info_from_mpd']
