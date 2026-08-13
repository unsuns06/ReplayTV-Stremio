"""6play show artwork: roles pulled from the program API, programs.json overrides them."""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.providers.fr.sixplay import SixPlayProvider, IMAGE_URL

# _IMAGE_ROLES prefers the plain "logo" role, with "fullColorLogo" as the fallback.
LOGO_KEY, FULL_COLOR_LOGO_KEY = "4865292", "4666282"
COVER_KEY, JUMBO_KEY = "4865287", "4348895"

# Trimmed shape of a real /programs/{id} payload — role + external_key only.
PROGRAM = {"images": [
    {"role": "carousel", "external_key": "941176"},
    {"role": "backdropWide", "external_key": "4666280"},
    {"role": "fullColorLogo", "external_key": FULL_COLOR_LOGO_KEY},
    {"role": "singleColorLogo", "external_key": "4666283"},
    {"role": "jumbotron", "external_key": JUMBO_KEY},
    {"role": "cover", "external_key": COVER_KEY},
    {"role": "portrait", "external_key": "4865289"},
    {"role": "logo", "external_key": LOGO_KEY},
]}

URL_LOGO = IMAGE_URL.format(LOGO_KEY)
URL_FULL_COLOR_LOGO = IMAGE_URL.format(FULL_COLOR_LOGO_KEY)
URL_COVER = IMAGE_URL.format(COVER_KEY)
URL_JUMBO = IMAGE_URL.format(JUMBO_KEY)


@pytest.fixture
def provider():
    p = SixPlayProvider()
    yield p
    p.close()


def test_roles_map_to_artwork_fields(provider):
    images = provider._images_from_program(PROGRAM, {})
    assert images["logo"] == URL_LOGO
    assert images["poster"] == URL_COVER
    assert images["background"] == URL_JUMBO
    assert images["fanart"] == URL_JUMBO


def test_plain_logo_role_wins_when_both_logo_roles_exist(provider):
    """PROGRAM carries both roles — the plain 'logo' is the preferred one."""
    assert provider._images_from_program(PROGRAM, {})["logo"] == URL_LOGO


def test_full_color_logo_used_when_plain_logo_is_absent(provider):
    program = {"images": [img for img in PROGRAM["images"] if img["role"] != "logo"]}
    assert provider._images_from_program(program, {})["logo"] == URL_FULL_COLOR_LOGO


def test_logo_omitted_when_neither_logo_role_exists(provider):
    program = {"images": [{"role": "cover", "external_key": COVER_KEY}]}
    assert "logo" not in provider._images_from_program(program, {})


def test_programs_json_url_overrides_the_api(provider):
    pinned = "https://example.test/my-logo.png"
    images = provider._images_from_program(PROGRAM, {"logo": pinned})
    assert "logo" not in images, "a pinned logo must not be overwritten by the API"
    assert images["poster"] == URL_COVER and images["background"] == URL_JUMBO


def test_each_field_overrides_independently(provider):
    show_info = {"logo": "https://example.test/l.png", "background": "https://example.test/b.jpg"}
    assert provider._images_from_program(PROGRAM, show_info) == {
        "poster": URL_COVER, "fanart": URL_JUMBO,
    }


def test_missing_roles_are_omitted_not_faked(provider):
    only_cover = {"images": [{"role": "cover", "external_key": COVER_KEY}]}
    assert provider._images_from_program(only_cover, {}) == {"poster": URL_COVER}


@pytest.mark.parametrize("payload", [
    {}, {"images": None}, {"images": []},
    {"images": [{"role": "cover"}, {"external_key": "1"}, {"role": None, "external_key": None}]},
])
def test_malformed_payloads_do_not_raise(provider, payload):
    assert provider._images_from_program(payload, {}) == {}


def test_empty_string_in_programs_json_is_not_treated_as_an_override(provider):
    assert provider._images_from_program(PROGRAM, {"poster": ""})["poster"] == URL_COVER


def test_catalogue_entry_uses_the_api_images(provider, monkeypatch):
    monkeypatch.setattr(provider, "_get_show_api_metadata",
                        lambda sid, info: provider._images_from_program(PROGRAM, info))
    info = {"name": "66 minutes", "channel": "M6"}
    show = provider._build_show_metadata("66-minutes", info,
                                         provider._get_show_api_metadata("66-minutes", info))
    assert show["logo"] == URL_LOGO
    assert show["poster"] == URL_COVER
    assert show["background"] == URL_JUMBO


def test_series_detail_page_uses_the_show_logo_not_the_channel_logo(provider, monkeypatch):
    """The /meta route builds from programs.json; without enhancement the logo
    falls back to /static/logos/fr/m6.png."""
    monkeypatch.setattr(provider, "shows", {"66-minutes": {"name": "66 minutes"}})
    monkeypatch.setattr(provider, "_get_show_api_metadata",
                        lambda sid, info: provider._images_from_program(PROGRAM, info))
    series_meta = {"name": "66 minutes", "logo": "http://host/static/logos/fr/m6.png",
                   "poster": "http://host/static/logos/fr/m6.png", "background": ""}
    enhanced = provider.enhance_series_meta(series_meta, "66-minutes")
    assert "/static/logos/" not in enhanced["logo"]
    assert enhanced["logo"] == URL_LOGO
    assert enhanced["poster"] == URL_COVER
    assert enhanced["background"] == URL_JUMBO


def test_series_detail_page_keeps_programs_json_overrides(provider, monkeypatch):
    pinned = "https://example.test/pinned-logo.png"
    monkeypatch.setattr(provider, "shows", {"66-minutes": {"name": "66 minutes", "logo": pinned}})
    monkeypatch.setattr(provider, "_get_show_api_metadata",
                        lambda sid, info: provider._images_from_program(PROGRAM, info))
    enhanced = provider.enhance_series_meta({"logo": pinned}, "66-minutes")
    assert enhanced["logo"] == pinned


def test_series_detail_page_survives_an_unknown_show(provider, monkeypatch):
    monkeypatch.setattr(provider, "shows", {})
    monkeypatch.setattr(provider, "_get_show_api_metadata", lambda sid, info: {})
    assert provider.enhance_series_meta({"logo": "keep"}, "nope")["logo"] == "keep"


def test_program_id_lookup_is_cached(provider, monkeypatch):
    from app.utils.cache import cache
    calls = []
    cache.delete("provider:6play:program_id:cache-probe")
    monkeypatch.setattr(provider, "_resolve_program_id",
                        lambda sid: (calls.append(sid), "4242")[1])
    assert provider._find_program_id("cache-probe") == "4242"
    assert provider._find_program_id("cache-probe") == "4242"
    assert len(calls) == 1, "second lookup should come from the cache"


@pytest.mark.integration
def test_live_program_endpoint_serves_all_three_roles(provider):
    """66 minutes (program 825) against the real API — no programs.json overrides."""
    images = provider._get_show_api_metadata("66-minutes", {"name": "66 minutes", "api_id": "825"})
    assert set(images) == {"logo", "poster", "background", "fanart"}
    assert len({images["logo"], images["poster"], images["background"]}) == 3


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
