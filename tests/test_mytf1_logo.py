"""TF1 catalogue artwork: the API must not overwrite the show logo with its poster."""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.providers.fr.mytf1 import MyTF1Provider

JSON_LOGO = "https://photos.tf1.fr/450/225/logo-programme-quotidien.png"
API_POSTER = "https://photos.tf1.fr/700/933/flux-program-card-portrait-quotidien.jpg"
API_BACKGROUND = "https://photos.tf1.fr/1920/1080/background-ott-quotidien.jpg"

SHOW_INFO = {"name": "Quotidien", "channel": "TMC", "logo": JSON_LOGO,
             "poster": "https://photos.tf1.fr/700/933/json-poster.jpg"}

GRAPHQL_PROGRAM = {
    "name": "Quotidien",
    "decoration": {
        "image": {"sources": [{"url": API_POSTER}]},
        "background": {"sources": [{"url": API_BACKGROUND}]},
    },
}


def _provider(monkeypatch):
    p = MyTF1Provider()
    monkeypatch.setattr(p, "_get_graphql_programs_list", lambda h, f=None: [GRAPHQL_PROGRAM])
    return p


def test_api_metadata_does_not_claim_the_poster_is_a_logo(monkeypatch):
    extra = _provider(monkeypatch)._get_show_api_metadata("quotidien", SHOW_INFO)
    assert extra["poster"] == API_POSTER
    assert extra.get("logo") != API_POSTER, "poster must not be published as the logo"


def test_catalogue_entry_keeps_the_logo_from_programs_json(monkeypatch):
    p = _provider(monkeypatch)
    extra = p._get_show_api_metadata("quotidien", SHOW_INFO)
    show = p._build_show_metadata("quotidien", SHOW_INFO, extra)
    assert show["logo"] == JSON_LOGO
    assert show["poster"] == API_POSTER
    assert show["logo"] != show["poster"]


def test_logo_falls_back_to_channel_logo_when_programs_json_has_none(monkeypatch):
    p = _provider(monkeypatch)
    info = {k: v for k, v in SHOW_INFO.items() if k != "logo"}
    show = p._build_show_metadata("quotidien", info, p._get_show_api_metadata("quotidien", info))
    assert show["logo"] and show["logo"].endswith("/static/logos/fr/tf1.png")


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q"]))
