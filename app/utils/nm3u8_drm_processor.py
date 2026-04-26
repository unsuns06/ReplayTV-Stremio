"""Backward-compatible re-export — implementation moved to app.utils.drm."""
from app.utils.drm.nm3u8_drm_processor import SimpleDRMProcessor, process_drm_simple

__all__ = ['SimpleDRMProcessor', 'process_drm_simple']
