"""Tests for the composite Stremio ID parser and provider routing."""

from app.utils.ids import parse_stremio_id


class TestParseStremioId:
    def test_series_id(self):
        parsed = parse_stremio_id("cutam:fr:francetv:cash-investigation")
        assert parsed is not None
        assert parsed.country == "fr"
        assert parsed.provider == "francetv"
        assert parsed.rest == "cash-investigation"
        assert parsed.slug == "cash-investigation"

    def test_episode_id(self):
        parsed = parse_stremio_id("cutam:fr:mytf1:episode:V_123456789")
        assert parsed.provider == "mytf1"
        assert parsed.after_marker("episode:") == "V_123456789"

    def test_cbc_episode_id_with_show_slug(self):
        parsed = parse_stremio_id("cutam:ca:cbc:dragons-den:episode:3:7")
        assert parsed.country == "ca"
        assert parsed.provider == "cbc"
        assert parsed.after_marker("episode:") == "3:7"

    def test_channel_id(self):
        parsed = parse_stremio_id("cutam:fr:francetv:france-2")
        assert parsed.provider == "francetv"
        assert parsed.slug == "france-2"

    def test_6play_provider_key(self):
        parsed = parse_stremio_id("cutam:fr:6play:episode:clip_12345")
        assert parsed.provider == "6play"

    def test_missing_marker_returns_none(self):
        parsed = parse_stremio_id("cutam:fr:francetv:some-show")
        assert parsed.after_marker("episode:") is None

    def test_rejects_wrong_namespace(self):
        assert parse_stremio_id("tt0111161") is None
        assert parse_stremio_id("other:fr:francetv:slug") is None

    def test_rejects_too_few_segments(self):
        assert parse_stremio_id("cutam:fr:francetv") is None
        assert parse_stremio_id("cutam:fr") is None
        assert parse_stremio_id("") is None
        assert parse_stremio_id(None) is None

    def test_rejects_empty_segments(self):
        assert parse_stremio_id("cutam::francetv:slug") is None
        assert parse_stremio_id("cutam:fr::slug") is None


class TestProviderRouting:
    """get_provider_by_id_prefix routes via the parsed provider segment."""

    def test_known_providers(self):
        from app.config.provider_config import get_provider_by_id_prefix
        assert get_provider_by_id_prefix("cutam:fr:francetv:show") == "francetv"
        assert get_provider_by_id_prefix("cutam:fr:mytf1:episode:V_1") == "mytf1"
        assert get_provider_by_id_prefix("cutam:fr:6play:episode:clip_1") == "6play"
        assert get_provider_by_id_prefix("cutam:ca:cbc:dragons-den") == "cbc"

    def test_unknown_provider_returns_none(self):
        from app.config.provider_config import get_provider_by_id_prefix
        assert get_provider_by_id_prefix("cutam:fr:notaprovider:show") is None

    def test_malformed_id_returns_none(self):
        from app.config.provider_config import get_provider_by_id_prefix
        assert get_provider_by_id_prefix("tt0111161") is None
        assert get_provider_by_id_prefix("") is None

    def test_provider_key_embedded_elsewhere_does_not_misroute(self):
        """A provider key appearing inside a slug must not select that provider."""
        from app.config.provider_config import get_provider_by_id_prefix
        assert get_provider_by_id_prefix("cutam:fr:francetv:all-about-mytf1") == "francetv"
