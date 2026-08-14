"""Daily-segment CBC shows (About That): LiveToVod items and medianet streams.

These shows have no season 1 in the catalog, publish LiveToVod/Quickturn items
instead of Episode ones, carry no episodeNumber, and their media only resolves
under appCode=medianet — four ways the normal CBC path does not fit them.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.providers.ca.cbc import CBCProvider
from app.utils.cache import cache

SLUG = "about-that-with-andrew-chang"
ITEM = {
    "idMedia": 10735091,
    "title": "Can Count Binface defeat Nigel Farage? | About That",
    "url": f"{SLUG}/s01e10735091",
    "mediaType": "LiveToVod",
    "type": "Quickturn",
    "metadata": {"airDate": "2026-08-12", "duration": 220},
}
ITEM2 = {**ITEM, "idMedia": 10735092, "url": f"{SLUG}/s01e10735092",
         "title": "A later segment | About That"}
PAYLOAD = {"content": [{"lineups": [{"seasonNumber": 1, "items": [ITEM, ITEM2]}]}]}


@pytest.fixture
def provider(monkeypatch):
    cache.delete(f"episodes:cbc:{SLUG}")
    p = CBCProvider()
    yield p
    p.close()


def test_livetovod_items_are_numbered_1_up_but_keep_the_media_id_in_their_id(provider, monkeypatch):
    """Stremio prints the episode number before the title, so it stays small;
    the id keeps Gem's media id, which is what streams resolve against."""
    monkeypatch.setattr(provider.api_client, "get", lambda *a, **k: PAYLOAD)
    episodes = provider._get_show_episodes(SLUG, "About That")
    assert [(e["season"], e["episode"], e["cbc_media_id"]) for e in episodes] == [
        (1, 1, "10735091"), (1, 2, "10735092")
    ]
    assert episodes[0]["id"].endswith(":episode:1:10735091")
    assert "livetovod" not in episodes[0]


def test_media_id_still_resolves_after_renumbering(provider, monkeypatch):
    monkeypatch.setattr(provider.api_client, "get", lambda *a, **k: PAYLOAD)
    episode_id = f"cutam:ca:cbc:{SLUG}:episode:1:10735091"
    assert provider._extract_media_id_from_episode_id(episode_id) == "10735091"


def test_stream_falls_back_to_medianet_when_gem_has_no_such_media(provider, monkeypatch):
    """errorCode 6 from gem is not a failure — the media lives under medianet."""
    monkeypatch.setattr(provider.authenticator, "is_authenticated", lambda: True)
    monkeypatch.setattr(provider.authenticator, "get_authenticated_headers",
                        lambda: {"x-claims-token": "token"})
    tried = []

    def fake_get(url, params=None, headers=None, **kwargs):
        tried.append(params["appCode"])
        if params["appCode"] == "gem":
            return {"errorCode": 6, "message": "Media not found"}
        return {"errorCode": 0, "url": "https://cbchls.akamaized.net/x/master.m3u8"}

    monkeypatch.setattr(provider.api_client, "get", fake_get)
    streams = provider._get_stream_from_cbc_api("10735091")
    assert tried == ["gem", "medianet"]
    assert streams and streams[0]["url"].endswith("master.m3u8")
