#!/usr/bin/env python3
"""MPD assets must be handed downstream as the *final* CDN URL.

6cloud's signed URL (lbcdn.6cloud.fr) redirects to the bedrock edge and serves a
manifest whose SegmentTemplate paths are root-relative, so segments are fetched
from whatever host served the manifest.  Give MediaFlow the signed URL and every
segment 404s on lbcdn.  lbcdn is also geo-restricted, so from outside France the
redirect can only be resolved through the fr_router proxy.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.providers.fr.sixplay import SixPlayProvider

SIGNED = "https://lbcdn.6cloud.fr/resource/m6web/s/m6web/output/a/b/c/show.mpd?token=x"
FINAL = "https://th2-edge-02.cdn.bedrock.tech/m6web/output/a/b/c/show.mpd?st=y&e=1"
ROUTER = "https://router.example/api/router?url="
# fr_router answers with a meta-refresh page, so '&' arrives &amp;-escaped.
ROUTER_PAGE = (
    '<html><head><meta http-equiv="refresh" content="0;url=\''
    + FINAL.replace("&", "&amp;")
    + "'\" /></head></html>"
)


class FakeResponse:
    def __init__(self, status_code, url="", text=""):
        self.status_code = status_code
        self.url = url
        self.text = text
        self.headers = {}

    def close(self):
        pass


class FakeClient:
    """Answers the direct resolve and the fr_router resolve differently."""

    def __init__(self, direct, routed=None):
        self.direct = direct
        self.routed = routed
        self.calls = []

    def raw_request(self, method, url, **kwargs):
        self.calls.append(url)
        if url.startswith(ROUTER):
            return self.routed
        assert method == "GET" and kwargs.get("allow_redirects") is True
        return self.direct


class FakeProxyConfig:
    def __init__(self, router=ROUTER):
        self.router = router

    def get_proxy(self, name):
        return self.router if name == "fr_router" else None


def _provider(direct, routed=None, router=ROUTER):
    provider = SixPlayProvider.__new__(SixPlayProvider)
    provider.api_client = FakeClient(direct, routed)
    provider.proxy_config = FakeProxyConfig(router)
    return provider


def _assets():
    return [{"type": "usp_dashcenc_h264", "video_quality": "hd", "full_physical_path": SIGNED}]


def test_direct_redirect_is_followed():
    """When the host can reach lbcdn the redirect resolves without the proxy."""
    p = _provider(FakeResponse(200, FINAL))
    assert p._select_best_asset(_assets()) == (FINAL, "mpd")
    assert len(p.api_client.calls) == 1  # router not consulted


def test_geo_blocked_falls_back_to_router():
    """403 from lbcdn (non-FR host) must not leak the signed URL."""
    p = _provider(FakeResponse(403, SIGNED), FakeResponse(200, ROUTER, ROUTER_PAGE))
    url, fmt = p._select_best_asset(_assets())
    assert (url, fmt) == (FINAL, "mpd"), url
    assert "&amp;" not in url  # HTML entity must be unescaped


def test_no_resolution_keeps_signed_url():
    """Both resolvers down: fall back to the signed URL rather than nothing."""
    assert _provider(FakeResponse(403, SIGNED), FakeResponse(500, ROUTER))._select_best_asset(
        _assets())[0] == SIGNED
    assert _provider(None, None, router=None)._select_best_asset(_assets())[0] == SIGNED
    assert _provider(None, FakeResponse(200, ROUTER, "<html>no target</html>"))._select_best_asset(
        _assets())[0] == SIGNED


def test_hls_asset_is_not_resolved():
    p = _provider(FakeResponse(200, FINAL))
    assets = [{"type": "http_h264", "video_quality": "hd", "full_physical_path": "http://x/y.m3u8"}]
    assert p._select_best_asset(assets) == ("http://x/y.m3u8", "hls")
    assert p.api_client.calls == []


if __name__ == "__main__":
    test_direct_redirect_is_followed()
    test_geo_blocked_falls_back_to_router()
    test_no_resolution_keeps_signed_url()
    test_hls_asset_is_not_resolved()
    print("ok")
