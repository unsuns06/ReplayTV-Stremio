"""
Integration tests for the FranceTV provider.

These tests make real network requests and require a configured environment.
Mark them to skip in CI without credentials via:
    pytest -m "not integration"
"""
import pytest
from app.providers.fr.francetv import FranceTVProvider


@pytest.mark.integration
def test_francetv_get_programs_returns_shows():
    """FranceTVProvider.get_programs() should return a non-empty list of shows."""
    provider = FranceTVProvider()
    shows = provider.get_programs()
    assert isinstance(shows, list), "get_programs() must return a list"
    assert len(shows) > 0, "Expected at least one show"

    first = shows[0]
    assert "id" in first, "Show must have an 'id' field"
    assert "name" in first, "Show must have a 'name' field"


@pytest.mark.integration
def test_francetv_get_episodes_returns_episodes():
    """FranceTVProvider.get_episodes() should return episodes for the first show."""
    provider = FranceTVProvider()
    shows = provider.get_programs()
    assert shows, "Need at least one show to fetch episodes"

    first_show = shows[0]
    episodes = provider.get_episodes(first_show["id"])
    assert isinstance(episodes, list), "get_episodes() must return a list"
    assert len(episodes) > 0, "Expected at least one episode"

    ep = episodes[0]
    assert "id" in ep, "Episode must have an 'id' field"
    assert "title" in ep, "Episode must have a 'title' field"


@pytest.mark.integration
def test_francetv_episode_has_broadcast_id():
    """Each episode returned should contain a broadcast_id used for streaming."""
    provider = FranceTVProvider()
    shows = provider.get_programs()
    assert shows

    episodes = provider.get_episodes(shows[0]["id"])
    assert episodes

    for ep in episodes[:3]:
        assert ep.get("broadcast_id"), f"Episode {ep.get('id')} is missing broadcast_id"
