"""CBC show artwork from the catalog API, with programs.json pins winning."""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.providers.ca.cbc import CBCProvider

QUERY = "?impolicy=ott&im=Resize=(_Size_)&quality=75"
API_LOGO = f"https://pp-images.gem.cbc.ca/v1/synps-cbc/show/perso/cbc_dragons_den_ott_logo_v06.png{QUERY}"
API_BACKGROUND = f"https://images.gem.cbc.ca/v1/synps-cbc/show/perso/cbc_dragons_den_ott_background_v12.jpg{QUERY}"
OG_IMAGE = f"https://images.gem.cbc.ca/v1/synps-cbc/show/perso/cbc_dragons_den_ott_program_v12.jpg{QUERY}"
# Built from API_BACKGROUND + latest season (20) — the target from the spec.
DERIVED_POSTER = f"https://images.gem.cbc.ca/v1/synps-cbc/season/perso/cbc_dragons_den_s20_ott_poster_v01.jpg{QUERY}"

PAYLOAD = {
    "images": {"logo": {"url": API_LOGO, "size": "Bigger"},
               "background": {"url": API_BACKGROUND, "size": "Normal"}},
    "htmlMeta": {"og:image": OG_IMAGE},
    "content": [{"lineups": [{"seasonNumber": 19}, {"seasonNumber": 20}, {"seasonNumber": 10}]}],
}


SHOW_POSTER = f"https://images.gem.cbc.ca/v1/synps-cbc/show/perso/cbc_dragons_den_ott_poster_v01.jpg{QUERY}"


class _Response:
    def __init__(self, status_code):
        self.status_code = status_code


@pytest.fixture(autouse=True)
def _clear_url_cache():
    """_first_existing and the show payload are cached in the shared cache —
    each test swaps in a different fake, so drop both between tests."""
    from app.utils.cache import cache
    for url in (DERIVED_POSTER, SHOW_POSTER):
        cache.delete(f"provider:cbc:url_ok:{url}")
    cache.delete("provider:cbc:show:dragons-den")
    yield


def _cbc(monkeypatch, payload=None, serves=()):
    """Provider whose show request returns *payload* and whose CDN serves *serves*."""
    p = CBCProvider()
    monkeypatch.setattr(p.api_client, "get", lambda *a, **k: PAYLOAD if payload is None else payload)
    monkeypatch.setattr(p.session, "head",
                        lambda url, **k: _Response(200 if url in serves else 404))
    return p


@pytest.fixture
def provider(monkeypatch):
    p = _cbc(monkeypatch, serves=(DERIVED_POSTER,))
    yield p
    p.close()


def test_logo_and_background_come_from_the_api(provider):
    extra = provider._get_show_api_metadata("dragons-den", {"name": "Dragon's Den"})
    assert extra["logo"] == API_LOGO
    assert extra["background"] == API_BACKGROUND
    assert extra["fanart"] == API_BACKGROUND


def test_season_poster_is_derived_from_background_and_latest_season(provider):
    """The exact transform from the spec: show->season, background_v12 -> s20_poster_v01."""
    assert provider._get_show_api_metadata("dragons-den", {})["poster"] == DERIVED_POSTER


def test_candidates_match_the_spec_examples(provider):
    """Both observed shapes, season form first."""
    assert provider._poster_candidates(PAYLOAD) == [DERIVED_POSTER, SHOW_POSTER]


def test_show_form_used_when_the_season_form_is_absent(monkeypatch):
    """schitts-creek shape: show/perso/<stem>_ott_poster_v01.jpg."""
    p = _cbc(monkeypatch, serves=(SHOW_POSTER,))
    assert p._get_show_api_metadata("dragons-den", {})["poster"] == SHOW_POSTER
    p.close()


def test_og_image_used_when_neither_derived_form_exists(monkeypatch):
    """son-of-a-critch shape: the poster exists only at an unguessable version."""
    p = _cbc(monkeypatch, serves=())
    assert p._get_show_api_metadata("dragons-den", {})["poster"] == OG_IMAGE
    p.close()


def test_season_form_wins_over_show_form(monkeypatch):
    p = _cbc(monkeypatch, serves=(DERIVED_POSTER, SHOW_POSTER))
    assert p._get_show_api_metadata("dragons-den", {})["poster"] == DERIVED_POSTER
    p.close()


def test_latest_season_is_used_not_the_last_lineup(provider):
    """Lineups arrive unsorted (19, 20, 10) — the poster must use 20."""
    assert "_s20_ott_poster_" in provider._get_show_api_metadata("dragons-den", {})["poster"]


def test_no_head_requests_when_the_poster_is_pinned(monkeypatch):
    p = CBCProvider()
    calls = []
    monkeypatch.setattr(p.api_client, "get", lambda *a, **k: PAYLOAD)
    monkeypatch.setattr(p.session, "head", lambda url, **k: calls.append(url) or _Response(200))
    extra = p._get_show_api_metadata("dragons-den", {"poster": "https://example.test/pin.jpg"})
    assert "poster" not in extra and calls == []
    p.close()


def test_existence_check_is_cached(monkeypatch):
    from app.utils.cache import cache
    p, calls = CBCProvider(), []
    url = "https://images.gem.cbc.ca/v1/synps-cbc/show/perso/probe_ott_poster_v01.jpg"
    cache.delete(f"provider:cbc:url_ok:{url}")
    monkeypatch.setattr(p.session, "head", lambda u, **k: calls.append(u) or _Response(200))
    assert p._first_existing([url]) == url
    assert p._first_existing([url]) == url
    assert len(calls) == 1
    p.close()


def test_candidates_empty_without_a_background(provider):
    assert provider._poster_candidates({"images": {}}) == []


def test_season_numbers_are_sorted_and_deduped():
    data = {"content": [{"lineups": [{"seasonNumber": 3}, {"seasonNumber": 1},
                                     {"seasonNumber": 3}, {"seasonNumber": None}]}]}
    assert CBCProvider._season_numbers(data) == [1, 3]


@pytest.mark.parametrize("data", [{}, {"content": []}, {"content": [{}]},
                                  {"content": [{"lineups": []}]}])
def test_season_numbers_survive_empty_payloads(data):
    assert CBCProvider._season_numbers(data) == []


def test_show_form_still_tried_when_seasons_are_missing(monkeypatch):
    payload = {k: v for k, v in PAYLOAD.items() if k != "content"}
    p = _cbc(monkeypatch, payload=payload, serves=(SHOW_POSTER,))
    assert p._poster_candidates(payload) == [SHOW_POSTER]
    assert p._get_show_api_metadata("dragons-den", {})["poster"] == SHOW_POSTER
    p.close()


def test_poster_omitted_when_nothing_is_derivable(monkeypatch):
    p = _cbc(monkeypatch, payload={"images": {"logo": {"url": API_LOGO}}}, serves=())
    assert "poster" not in p._get_show_api_metadata("dragons-den", {})
    p.close()


def test_pinned_poster_overrides_the_derived_one(provider):
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


SYNOPSIS = "Entrepreneurs pitch their business concepts to a panel of moguls."


def test_scheduling_messages_are_appended_to_the_description():
    """Gem keeps "New season streaming September 17th" out of the synopsis."""
    assert CBCProvider._description({
        "description": SYNOPSIS,
        "messages": [{"type": "Info", "message": "New season streaming September 17th"}],
    }) == f"{SYNOPSIS}\n\nNew season streaming September 17th"


def test_every_message_gets_its_own_paragraph():
    assert CBCProvider._description({
        "description": SYNOPSIS,
        "messages": [{"message": "One"}, {"type": "Info"}, {"message": "Two"}],
    }) == f"{SYNOPSIS}\n\nOne\n\nTwo"


def test_description_is_untouched_without_messages():
    assert CBCProvider._description({"description": SYNOPSIS}) == SYNOPSIS
    assert CBCProvider._description({"description": SYNOPSIS, "messages": []}) == SYNOPSIS


def test_a_message_alone_still_becomes_the_description():
    assert CBCProvider._description({"messages": [{"message": "Coming soon"}]}) == "Coming soon"
    assert CBCProvider._description({}) is None
    assert CBCProvider._description(None) is None


def test_empty_or_broken_payload_yields_nothing(monkeypatch):
    p = CBCProvider()
    monkeypatch.setattr(p.api_client, "get", lambda *a, **k: None)
    assert p._get_show_api_metadata("dragons-den", {}) == {}
    monkeypatch.setattr(p.api_client, "get", lambda *a, **k: {"images": {}})
    assert p._get_show_api_metadata("dragons-den", {}) == {}
    p.close()


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))


def test_show_payload_skips_seasons_the_api_404s_on(monkeypatch):
    """A show whose season 1 is gone: probe forward until a season answers."""
    p = CBCProvider()
    tried = []

    def fake_get(url, **kwargs):
        tried.append(url)
        return PAYLOAD if "dragons-den/s03e01" in url else None

    monkeypatch.setattr(p.api_client, "get", fake_get)
    assert p._show_payload("dragons-den") is PAYLOAD
    assert [u.split("/")[-1].split("?")[0] for u in tried] == ["s01e01", "s02e01", "s03e01"]
    assert p._show_payload("gone") is None  # every season 404s
    p.close()
