"""DRM utilities package.

Consolidates all DRM processing behind a common :class:`DRMProcessor` interface:

* :class:`~app.utils.drm.nm3u8_drm_processor.SimpleDRMProcessor`
  — offloads downloads to a remote N_m3u8DL-RE API.
* :class:`~app.utils.drm.sixplay_mpd_processor.SixPlayMPDProcessor`
  — rewrites 6play MPD manifests for MediaFlow compatibility.
* :class:`~app.utils.drm.direct_mpd_processor.DirectMPDProcessor`
  — downloads + rewrites an MPD in one step.
"""

from app.utils.drm.base import DRMProcessor
from app.utils.drm.pssh_extractor import extract_pssh_from_mpd
from app.utils.drm.widevine_handler import extract_widevine_key
from app.utils.drm.clearkey_handler import build_mediaflow_clearkey_stream
from app.utils.drm.nm3u8_drm_processor import SimpleDRMProcessor, process_drm_simple
from app.utils.drm.sixplay_mpd_processor import (
    SixPlayMPDProcessor,
    create_mediaflow_compatible_mpd,
    extract_drm_info_from_mpd,
)
from app.utils.drm.direct_mpd_processor import DirectMPDProcessor, get_processed_mpd_content

__all__ = [
    # Abstract base
    'DRMProcessor',
    # PSSH / key extraction
    'extract_pssh_from_mpd',
    'extract_widevine_key',
    'build_mediaflow_clearkey_stream',
    # N_m3u8DL-RE remote processor
    'SimpleDRMProcessor',
    'process_drm_simple',
    # 6play MPD rewriter
    'SixPlayMPDProcessor',
    'create_mediaflow_compatible_mpd',
    'extract_drm_info_from_mpd',
    # Direct download + rewrite
    'DirectMPDProcessor',
    'get_processed_mpd_content',
]
