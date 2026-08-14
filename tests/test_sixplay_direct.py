"""Offline checks for the 6play direct-source (MediaFlow) replay path."""

import os
import sys
from urllib.parse import urlparse, parse_qs

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.providers.fr.sixplay import SixPlayProvider

PROCESSED = [{"url": "https://tb/x.mp4", "manifest_type": "video", "title": "✅ [TorBox] DRM-Free Video"}]


def _provider(monkeypatch, processed=None, key="ba" * 16):
    p = SixPlayProvider()
    p.mediaflow_url, p.mediaflow_password = "https://mf.test", "pw"
    p.account_id, p.login_token, p._authenticated = "uid", "jwt", True
    monkeypatch.setattr(p, "_check_processed_file", lambda eid: processed)
    monkeypatch.setattr(p, "_fetch_video_assets", lambda eid: [
        {"type": "usp_dashcenc_h264", "video_quality": "hd", "full_physical_path": "https://x/hd.mpd"}])
    monkeypatch.setattr(p, "_select_best_asset", lambda assets, is_live=False: ("https://x/hd.mpd", "mpd"))
    monkeypatch.setattr(p, "_extract_mpd_drm_info", lambda url: (object(), "ab" * 16, {"url": url, "manifest_type": "mpd"}))
    monkeypatch.setattr(p, "_fetch_drm_token", lambda eid: "tok")
    # bypass the KID cache so each test licenses fresh
    monkeypatch.setattr(p, "_cached_decryption_key", lambda *a: key)
    return p


def test_direct_stream_passes_key_to_mediaflow(monkeypatch):
    p = _provider(monkeypatch)
    monkeypatch.setattr(p, "_start_drm_processing", lambda *a, **k: {"url": "placeholder"})
    streams = p.get_episode_stream_url("cutam:fr:6play:episode:123")
    direct = streams[0]
    q = parse_qs(urlparse(direct["url"]).query)
    assert q["d"] == ["https://x/hd.mpd"]
    assert q["key_id"] == ["ab" * 16] and q["key"] == ["ba" * 16]
    assert "license_url" not in q, "key extracted locally — MediaFlow must not need DRMtoday"


def test_direct_stream_is_additional_not_replacement(monkeypatch):
    """Processed file stays first; direct source is appended; no re-download."""
    started = []
    p = _provider(monkeypatch, processed=list(PROCESSED))
    monkeypatch.setattr(p, "_start_drm_processing", lambda *a, **k: started.append(1))
    streams = p.get_episode_stream_url("cutam:fr:6play:episode:123")
    assert streams[0] == PROCESSED[0]
    assert "mf.test" in streams[1]["url"]
    assert not started, "already-processed episode must not be queued again"


def test_processing_still_starts_without_processed_file(monkeypatch):
    started = []
    p = _provider(monkeypatch)
    monkeypatch.setattr(p, "_start_drm_processing",
                        lambda *a, **k: (started.append(1), {"url": "placeholder"})[1])
    streams = p.get_episode_stream_url("cutam:fr:6play:episode:123")
    assert started, "background DRM processing must still run for new episodes"
    assert [s["url"] for s in streams][-1] == "placeholder"


def test_falls_back_to_license_url_without_key(monkeypatch):
    p = _provider(monkeypatch, key=None)
    streams = p.get_episode_stream_url("cutam:fr:6play:episode:123")
    q = parse_qs(urlparse(streams[0]["url"]).query)
    assert "lic.drmtoday.com" in q["license_url"][0]
    assert q["license_h_x-dt-auth-token"] == ["tok"]
    assert "key" not in q


def test_processed_file_survives_auth_failure(monkeypatch):
    p = _provider(monkeypatch, processed=list(PROCESSED))
    p._authenticated = False
    monkeypatch.setattr(p, "_authenticate", lambda: False)
    assert p.get_episode_stream_url("cutam:fr:6play:episode:123") == PROCESSED


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q"]))
