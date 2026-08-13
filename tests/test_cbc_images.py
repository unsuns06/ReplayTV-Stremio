"""CBC show artwork from the catalog API, with programs.json pins winning."""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.providers.ca.cbc import CBCProvider

QUERY = "?impolicy=ott&im=Resize=(_Size_)&quality=75"
API_LOGO = f"https://pp-images.gem.cbc.ca/v1/synps-cbc/show/perso/cbc_dragons_den_ott_logo_v06.png{QUERY}"
API_BACKGROUND = f"https://images.gem.cbc.ca/v1/synps-cbc/show/perso/cbc_dragons_den_ott_background_v12.jpg{QUERY}"
API_POSTER = f"https://images.gem.cbc.ca/v1/synps-cbc/show/perso/cbc_dragons_den_ott_program_v12.jpg{QUERY}"

PAYLOAD = {
    "images": {"logo": {"url": API_LOGO, "size": "Bigger"},
               "background": {"url": API_BACKGROUND, "size": "Normal"}},
    "htmlMeta": {"og:image": API_POSTER},
}


@pytest.fixture
def provider(monkeypatch):
    p = CBCProvider()
    monkeypatch.setattr(p.api_client, "get", lambda *a, **k: PAYLOAD)
    yield p
    p.close()


def test_logo_and_background_come_from_the_api(provider):
    extra = provider._get_show_api_metadata("dragons-den", {"name": "Dragon's Den"})
    assert extra["logo"] == API_LOGO
    assert extra["background"] == API_BACKGROUND
    assert extra["fanart"] == API_BACKGROUND


def test_poster_comes_from_og_image(provider):
    """The poster is not under images — it is htmlMeta's og:image."""
    assert provider._get_show_api_metadata("dragons-den", {})["poster"] == API_POSTER


def test_poster_omitted_when_og_image_is_absent(monkeypatch):
    p = CBCProvider()
    payload = {k: v for k, v in PAYLOAD.items() if k != "htmlMeta"}
    monkeypatch.setattr(p.api_client, "get", lambda *a, **k: payload)
    assert "poster" not in p._get_show_api_metadata("dragons-den", {})
    p.close()


def test_pinned_poster_overrides_og_image(provider):
    extra = provider._get_show_api_metadata("dragons-den", {"poster": "https://example.test/pin.jpg"})
    assert "poster" not in extra


def test_programs_json_pin_overrides_the_api(provider):
    pinned = "https://example.test/pinned-logo.png"
    extra = provider._get_show_api_metadata("dragons-den", {"logo": pinned})
    assert "logo" not in extra
    assert extra["background"] == API_BACKGROUND


def test_catalogue_entry_uses_the_api_images(provider):
    info = {"name": "Dragon's Den", "channel": "CBC"}
    show = provider._build_show_metadata("dragons-den", info,
                                         provider._get_show_api_metadata("dragons-den", info))
    assert show["logo"] == API_LOGO
    assert show["background"] == API_BACKGROUND


def test_detail_page_gets_the_api_artwork(provider, monkeypatch):
    monkeypatch.setattr(provider, "shows", {"dragons-den": {"name": "Dragon's Den"}})
    meta = provider.enhance_series_meta({"logo": "http://host/static/logos/ca/cbc.png"}, "dragons-den")
    assert meta["logo"] == API_LOGO


def test_empty_or_broken_payload_yields_nothing(monkeypatch):
    p = CBCProvider()
    monkeypatch.setattr(p.api_client, "get", lambda *a, **k: None)
    assert p._get_show_api_metadata("dragons-den", {}) == {}
    monkeypatch.setattr(p.api_client, "get", lambda *a, **k: {"images": {}})
    assert p._get_show_api_metadata("dragons-den", {}) == {}
    p.close()


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
