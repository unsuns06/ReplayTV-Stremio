"""Offline checks for the MyTF1 direct-source (MediaFlow) replay path."""

import os
import sys
from urllib.parse import urlparse, parse_qs

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from app.providers.fr.mytf1 import MyTF1Provider

PROCESSED = [{"url": "https://tb/x.mp4", "manifest_type": "video", "title": "✅ [TorBox] DRM-Free Video"}]
MPD_URL = "https://cdn.tf1.fr/vod/x.mpd"
LICENSE = "https://drm-wide.tf1.fr/proxy?id=42"
KID, KEY = "ab" * 16, "ba" * 16


def _provider(monkeypatch, processed=None, drm_keys=None, url=MPD_URL, license_url=LICENSE):
    p = MyTF1Provider()
    p.mediaflow_url, p.mediaflow_password = "https://mf.test", "pw"
    p.auth_token, p._authenticated = "jwt", True
    monkeypatch.setattr(p, "_check_processed_file", lambda eid: processed)
    monkeypatch.setattr(p, "_fetch_episode_delivery", lambda eid: {
        "delivery": {"code": 200, "url": url, "drms": [{"url": license_url, "h": [{"k": "x-tf1", "v": "tok"}]}]}})
    monkeypatch.setattr(p, "_extract_drm_keys",
                        lambda *a, **k: dict(drm_keys) if drm_keys is not None else {KID: KEY})
    return p


def _q(stream):
    return parse_qs(urlparse(stream["url"]).query)


def test_direct_stream_passes_key_to_mediaflow(monkeypatch):
    p = _provider(monkeypatch)
    monkeypatch.setattr(p, "_start_drm_processing", lambda *a, **k: {"url": "placeholder"})
    streams = p.get_episode_stream_url("cutam:fr:mytf1:episode:42")
    q = _q(streams[0])
    assert streams[0]["title"] == "🌐 [MPD] Direct source (MediaFlow)"
    assert q["d"] == [MPD_URL]
    assert q["key_id"] == [KID] and q["key"] == [KEY]
    assert "license_url" not in q, "key extracted locally — MediaFlow must not need the TF1 license"
    assert q["h_authorization"] == ["Bearer jwt"]


def test_dash_proxy_is_gone():
    assert not hasattr(MyTF1Provider, "_build_dash_proxy_stream")


def test_direct_stream_is_additional_not_replacement(monkeypatch):
    """Processed file stays first, direct source is appended, nothing is re-queued."""
    started = []
    p = _provider(monkeypatch, processed=list(PROCESSED))
    monkeypatch.setattr(p, "_start_drm_processing", lambda *a, **k: started.append(1))
    streams = p.get_episode_stream_url("cutam:fr:mytf1:episode:42")
    assert streams[0] == PROCESSED[0]
    assert len(streams) == 2 and "mf.test" in streams[1]["url"]
    assert not started, "already-processed episode must not be queued again"


def test_processing_still_starts_without_processed_file(monkeypatch):
    started = []
    p = _provider(monkeypatch)
    monkeypatch.setattr(p, "_start_drm_processing",
                        lambda *a, **k: (started.append(k.get("keys")), {"url": "placeholder"})[1])
    streams = p.get_episode_stream_url("cutam:fr:mytf1:episode:42")
    assert started == [[f"{KID}:{KEY}"]]
    assert streams[-1]["url"] == "placeholder"


def test_direct_stream_present_even_when_key_extraction_fails(monkeypatch):
    """No key: still a direct stream, licensed by MediaFlow, and no processing job."""
    started = []
    p = _provider(monkeypatch, drm_keys={})
    monkeypatch.setattr(p, "_start_drm_processing", lambda *a, **k: started.append(1))
    streams = p.get_episode_stream_url("cutam:fr:mytf1:episode:42")
    q = _q(streams[0])
    assert q["license_url"] == [LICENSE]
    assert q["license_h_x-tf1"] == ["tok"]
    assert "key" not in q
    assert streams[0]["licenseUrl"] == LICENSE
    assert not started, "nothing to process without keys"


def test_multi_key_license_picks_manifest_default_kid(monkeypatch):
    other = "cd" * 16
    p = _provider(monkeypatch, drm_keys={other: "11" * 16, KID: KEY})
    monkeypatch.setattr(p, "_start_drm_processing", lambda *a, **k: {"url": "placeholder"})
    monkeypatch.setattr("app.providers.fr.mytf1.extract_pssh_from_mpd",
                        lambda url, name: (None, None, {"key_id": KID}))
    assert _q(p.get_episode_stream_url("cutam:fr:mytf1:episode:42")[0])["key_id"] == [KID]


def test_single_key_skips_the_extra_manifest_fetch(monkeypatch):
    fetched = []
    p = _provider(monkeypatch)
    monkeypatch.setattr(p, "_start_drm_processing", lambda *a, **k: {"url": "placeholder"})
    monkeypatch.setattr("app.providers.fr.mytf1.extract_pssh_from_mpd",
                        lambda url, name: (fetched.append(url), (None, None, {}))[1])
    p.get_episode_stream_url("cutam:fr:mytf1:episode:42")
    assert not fetched, "one key — no reason to re-download the manifest"


def test_hls_episode_still_returns_mediaflow_stream(monkeypatch):
    p = _provider(monkeypatch, url="https://cdn.tf1.fr/vod/x.m3u8", license_url=None)
    streams = p.get_episode_stream_url("cutam:fr:mytf1:episode:42")
    assert len(streams) == 1
    assert streams[0]["manifest_type"] == "hls"
    assert _q(streams[0])["d"] == ["https://cdn.tf1.fr/vod/x.m3u8"]


def test_processed_file_survives_auth_failure(monkeypatch):
    p = _provider(monkeypatch, processed=list(PROCESSED))
    p._authenticated = False
    monkeypatch.setattr(p, "_authenticate", lambda: False)
    assert p.get_episode_stream_url("cutam:fr:mytf1:episode:42") == PROCESSED


def test_processed_file_survives_delivery_failure(monkeypatch):
    p = _provider(monkeypatch, processed=list(PROCESSED))
    monkeypatch.setattr(p, "_fetch_episode_delivery", lambda eid: {"delivery": {"code": 403}})
    assert p.get_episode_stream_url("cutam:fr:mytf1:episode:42") == PROCESSED


def test_nothing_at_all_returns_none(monkeypatch):
    p = _provider(monkeypatch)
    monkeypatch.setattr(p, "_fetch_episode_delivery", lambda eid: None)
    assert p.get_episode_stream_url("cutam:fr:mytf1:episode:42") is None


def test_direct_stream_falls_back_to_raw_url_without_mediaflow(monkeypatch):
    p = _provider(monkeypatch)
    p.mediaflow_url = p.mediaflow_password = None
    monkeypatch.setattr(p, "_start_drm_processing", lambda *a, **k: {"url": "placeholder"})
    assert p.get_episode_stream_url("cutam:fr:mytf1:episode:42")[0]["url"] == MPD_URL


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
