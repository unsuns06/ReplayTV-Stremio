"""TF1 show artwork: real logo from the decoration, never the poster; pins win."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.providers.fr.mytf1 import MyTF1Provider

JSON_LOGO = "https://photos.tf1.fr/450/225/logo-programme-quotidien.png"
API_LOGO = "https://photos.tf1.fr/450/225/api-logo-quotidien.png"
API_POSTER = "https://photos.tf1.fr/700/933/flux-program-card-portrait-quotidien.jpg"
API_THUMBNAIL = "https://photos.tf1.fr/1200/720/flux-program-card-landscape-quotidien.jpg"
API_BACKGROUND = "https://photos.tf1.fr/1920/1080/background-ott-quotidien.jpg"

SHOW_INFO = {"name": "Quotidien"}

DECORATION = {
    "logo": {"sources": [{"url": API_LOGO}, {"url": "small.png"}]},
    "image": {"sources": [{"url": API_POSTER}]},
    "thumbnail": {"sources": [{"url": API_THUMBNAIL}]},
    "background": {"sources": [{"url": API_BACKGROUND}]},
}


def _provider(monkeypatch, decoration=None):
    p = MyTF1Provider()
    program = {"name": "Quotidien", "slug": "quotidien",
               "decoration": DECORATION if decoration is None else decoration}
    monkeypatch.setattr(p, "_find_program", lambda slug, headers=None: program)
    return p


def test_logo_comes_from_the_decoration_logo_not_the_poster(monkeypatch):
    extra = _provider(monkeypatch)._get_show_api_metadata("quotidien", SHOW_INFO)
    assert extra["logo"] == API_LOGO
    assert extra["poster"] == API_POSTER
    assert extra["logo"] != extra["poster"], "poster must never be published as the logo"


def test_largest_source_is_used(monkeypatch):
    """Sources come back largest-first; take the first, not the last."""
    assert _provider(monkeypatch)._get_show_api_metadata("quotidien", SHOW_INFO)["logo"] == API_LOGO


def test_background_feeds_both_background_and_fanart(monkeypatch):
    extra = _provider(monkeypatch)._get_show_api_metadata("quotidien", SHOW_INFO)
    assert extra["background"] == API_BACKGROUND
    assert extra["fanart"] == API_BACKGROUND


def test_poster_is_the_portrait_image_never_the_landscape_thumbnail(monkeypatch):
    """decoration.image is PORTRAIT in all 500 programs; thumbnail is the
    landscape card and is deliberately not used."""
    extra = _provider(monkeypatch)._get_show_api_metadata("quotidien", SHOW_INFO)
    assert extra["poster"] == API_POSTER
    assert API_THUMBNAIL not in extra.values()


def test_poster_omitted_when_the_portrait_image_is_absent(monkeypatch):
    decoration = {k: v for k, v in DECORATION.items() if k != "image"}
    extra = _provider(monkeypatch, decoration)._get_show_api_metadata("quotidien", SHOW_INFO)
    assert "poster" not in extra


def test_programs_json_pin_overrides_the_api(monkeypatch):
    info = {**SHOW_INFO, "logo": JSON_LOGO}
    p = _provider(monkeypatch)
    extra = p._get_show_api_metadata("quotidien", info)
    assert "logo" not in extra
    show = p._build_show_metadata("quotidien", info, extra)
    assert show["logo"] == JSON_LOGO
    assert show["poster"] == API_POSTER
    assert show["logo"] != show["poster"]


def test_catalogue_entry_uses_the_api_logo_when_nothing_is_pinned(monkeypatch):
    p = _provider(monkeypatch)
    show = p._build_show_metadata("quotidien", SHOW_INFO,
                                  p._get_show_api_metadata("quotidien", SHOW_INFO))
    assert show["logo"] == API_LOGO
    assert show["poster"] == API_POSTER
    assert show["background"] == API_BACKGROUND


def test_logo_falls_back_to_channel_logo_when_api_has_none(monkeypatch):
    decoration = {k: v for k, v in DECORATION.items() if k != "logo"}
    p = _provider(monkeypatch, decoration)
    show = p._build_show_metadata("quotidien", SHOW_INFO,
                                  p._get_show_api_metadata("quotidien", SHOW_INFO))
    assert show["logo"].endswith("/static/logos/fr/tf1.png")


def test_detail_page_gets_the_api_artwork(monkeypatch):
    p = _provider(monkeypatch)
    monkeypatch.setattr(p, "shows", {"quotidien": SHOW_INFO})
    meta = p.enhance_series_meta({"logo": "http://host/static/logos/fr/tf1.png"}, "quotidien")
    assert meta["logo"] == API_LOGO


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q"]))
