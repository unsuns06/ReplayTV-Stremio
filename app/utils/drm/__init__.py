"""DRM utilities package.

* :class:`~app.utils.drm.nm3u8_drm_processor.SimpleDRMProcessor`
  — offloads downloads to a remote N_m3u8DL-RE API.
* :class:`~app.utils.drm.sixplay_mpd_processor.SixPlayMPDProcessor`
  — rewrites 6play MPD manifests for MediaFlow compatibility.
* :func:`~app.utils.drm.pssh_extractor.extract_pssh_from_mpd`
  — PSSH / DRM-info extraction from MPD manifests.
"""

from app.utils.drm.pssh_extractor import extract_pssh_from_mpd
from app.utils.drm.nm3u8_drm_processor import SimpleDRMProcessor, process_drm_simple
from app.utils.drm.sixplay_mpd_processor import (
    SixPlayMPDProcessor,
    create_mediaflow_compatible_mpd,
    extract_drm_info_from_mpd,
)

__all__ = [
    # PSSH extraction
    "extract_pssh_from_mpd",
    # N_m3u8DL-RE remote processor
    "SimpleDRMProcessor",
    "process_drm_simple",
    # 6play MPD rewriter
    "SixPlayMPDProcessor",
    "create_mediaflow_compatible_mpd",
    "extract_drm_info_from_mpd",
]
