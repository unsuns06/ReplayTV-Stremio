"""Offline checks for the 6play live path (no network)."""

import os
import sys
from urllib.parse import urlparse, parse_qs

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.providers.fr.sixplay import SixPlayProvider
from app.providers.base_provider import LiveProviderMixin
from app.utils.drm import extract_pssh

# PlayReady box listed first, as 6play's live manifests do — a Widevine CDM
# rejects it, so extraction must pick the second one by system ID.
PLAYREADY_PSSH = "AAAAKHBzc2gAAAAAmgTweZhAQoarkuZb4IhflQAAAAA="
WIDEVINE_PSSH = "AAAAKHBzc2gAAAAA7e+LqXnWSs6jyCfc1R0h7QAAAAA="
MPD_XML = f"""<?xml version="1.0"?>
<MPD xmlns="urn:mpeg:dash:schema:mpd:2011" xmlns:cenc="urn:mpeg:cenc:2013">
  <Period><AdaptationSet>
    <ContentProtection schemeIdUri="urn:mpeg:dash:mp4protection:2011" value="cenc"
                       cenc:default_KID="433ffba6-7096-3e70-8578-59a9dff4be04"/>
    <ContentProtection schemeIdUri="urn:uuid:9a04f079-9840-4286-ab92-e65be0885f95">
      <cenc:pssh>{PLAYREADY_PSSH}</cenc:pssh></ContentProtection>
    <ContentProtection schemeIdUri="urn:uuid:edef8ba9-79d6-4ace-a3c8-27dcd51d21ed">
      <cenc:pssh>{WIDEVINE_PSSH}</cenc:pssh></ContentProtection>
  </AdaptationSet></Period>
</MPD>""".encode()

LIVE_ASSETS = [
    {"type": "subtitle_vtt", "full_physical_path": "https://x/sub.vtt"},
    {"type": "delta_dashcenc_h264", "video_quality": "sd", "full_physical_path": "https://x/sd.mpd"},
    {"type": "delta_dashcenc_h264", "video_quality": "hd", "full_physical_path": "https://x/hd.mpd"},
]


def test_live_supported():
    assert issubclass(SixPlayProvider, LiveProviderMixin)
    assert SixPlayProvider.supports_live


def test_channel_list():
    p = SixPlayProvider()
    ids = [c["id"] for c in p.get_live_channels()]
    assert ids == ["cutam:fr:6play:m6", "cutam:fr:6play:w9",
                   "cutam:fr:6play:6ter", "cutam:fr:6play:gulli"]


def test_live_asset_selection_prefers_hd_dashcenc():
    p = SixPlayProvider()
    assert p._select_best_asset(LIVE_ASSETS, is_live=True) == ("https://x/hd.mpd", "mpd")


def test_live_stream_info_carries_license(monkeypatch):
    p = SixPlayProvider()
    p.account_id, p.login_token = "uid", "jwt"
    monkeypatch.setattr(p, "_fetch_live_drm_token", lambda key: f"tok-{key}")
    stream = p._build_live_stream_info("https://x/hd.mpd", "mpd", "6T", {"title": "Le 19:45"}, "6ter")
    assert stream["manifest_type"] == "mpd"
    assert stream["title"] == "[MPD] Le 19:45"
    assert stream["licenseHeaders"]["x-dt-auth-token"] == "tok-6T"
    assert "lic.drmtoday.com" in stream["licenseUrl"]


def test_unknown_channel_returns_none():
    assert SixPlayProvider().get_channel_stream_url("cutam:fr:6play:nope") is None


def test_widevine_pssh_preferred_over_playready(monkeypatch):
    monkeypatch.setattr(extract_pssh, "fetch_mpd", lambda url: MPD_XML)
    record = extract_pssh.extract_first_pssh("https://x/live.mpd")
    assert record.base64_text == WIDEVINE_PSSH
    assert record.system_id == extract_pssh.WIDEVINE_SYSTEM_ID


def test_drm_info_parses_lowercase_scheme_uuids():
    from app.utils.drm.sixplay_mpd_processor import extract_drm_info_from_mpd
    info = extract_drm_info_from_mpd(MPD_XML.decode())
    assert info["key_id"] == "433ffba6-7096-3e70-8578-59a9dff4be04"
    assert info["widevine_pssh"] == WIDEVINE_PSSH


def test_live_key_cached_by_kid(monkeypatch):
    p, calls = SixPlayProvider(), []
    monkeypatch.setattr(p, "_acquire_decryption_key",
                        lambda *a: (calls.append(1), "dd" * 16)[1])
    assert p._cached_decryption_key(object(), "cc" * 16, "tok") == "dd" * 16
    assert p._cached_decryption_key(object(), "cc" * 16, "tok") == "dd" * 16
    assert len(calls) == 1, "second call should hit the per-KID cache"
    # A rotated KID must miss the cache and re-license.
    p._cached_decryption_key(object(), "ee" * 16, "tok")
    assert len(calls) == 2


def test_live_stream_passes_key_to_mediaflow(monkeypatch):
    p = SixPlayProvider()
    p.account_id, p.login_token = "uid", "jwt"
    p.mediaflow_url, p.mediaflow_password = "https://mf.test", "pw"
    monkeypatch.setattr(p, "_fetch_live_drm_token", lambda k: "tok")
    monkeypatch.setattr(p, "_extract_mpd_drm_info", lambda url: (object(), "ab" * 16, {}))
    monkeypatch.setattr(p, "_acquire_decryption_key", lambda *a: "ba" * 16)
    stream = p._build_live_stream_info("https://x/hd.mpd", "mpd", "M6", {}, "M6")
    q = parse_qs(urlparse(stream["url"]).query)
    assert q["key_id"] == ["ab" * 16] and q["key"] == ["ba" * 16]
    assert q["d"] == ["https://x/hd.mpd"]


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q"]))
