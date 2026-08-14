"""The one artwork precedence rule shared by every self-fetching provider."""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.providers.base_provider import BaseProvider
from app.providers.registry import PROVIDER_CLASSES


class _Dummy(BaseProvider):
    provider_name = "dummy"
    country = "fr"
    default_channel = "m6"
    id_prefix = "cutam:fr:dummy"

    def get_episode_stream_url(self, episode_id):
        return None


@pytest.fixture
def provider():
    p = _Dummy()
    yield p
    p.close()


def test_first_non_empty_candidate_wins(provider):
    picked = provider._pick_fields({"logo": [None, "", "second.png", "third.png"]}, {})
    assert picked["logo"] == "second.png"


def test_pinned_field_is_skipped_entirely(provider):
    picked = provider._pick_fields({"logo": ["api.png"], "poster": ["p.jpg"]},
                                    {"logo": "pinned.png"})
    assert picked == {"poster": "p.jpg"}


def test_field_with_no_candidates_is_omitted(provider):
    """Omitted, not blanked — build_show_dict's own fallback must still apply."""
    assert provider._pick_fields({"logo": [None, ""]}, {}) == {}


def test_empty_pin_does_not_count_as_pinned(provider):
    assert provider._pick_fields({"logo": ["api.png"]}, {"logo": ""}) == {"logo": "api.png"}


def test_enhance_series_meta_only_writes_known_show_fields(provider, monkeypatch):
    """Extras carry provider-internal keys (FranceTV's raw image patterns); only
    the documented show fields may land in the meta."""
    provider.shows = {"show": {}}
    monkeypatch.setattr(provider, "_get_show_api_metadata", lambda sid, info: {
        "logo": "l.png", "genres": ["Magazine"], "year": 1999,
        "images": [1, 2], "description": None,
    })
    meta = provider.enhance_series_meta({"logo": "old.png"}, "show")
    assert meta["logo"] == "l.png"
    assert meta["genres"] == ["Magazine"]
    assert meta["year"] == 1999
    assert "images" not in meta


def test_enhance_series_meta_is_a_noop_without_api_metadata(provider):
    assert provider.enhance_series_meta({"logo": "keep"}, "unknown") == {"logo": "keep"}


@pytest.mark.parametrize("key", ["6play", "mytf1", "cbc"])
def test_self_fetching_providers_share_the_rule(key):
    """Each unified provider drives its artwork through _pick_fields."""
    cls = PROVIDER_CLASSES[key]
    assert cls._get_show_api_metadata is not BaseProvider._get_show_api_metadata
    assert cls.enhance_series_meta is BaseProvider.enhance_series_meta


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
