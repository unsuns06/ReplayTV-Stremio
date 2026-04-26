"""Canonical cache key definitions for the global InMemoryCache.

All modules that read or write the shared cache must use these helpers so
that key-naming is consistent and refactoring a key only requires one edit.
"""


class CacheKeys:
    """Static factory methods for every cache key used in this addon."""

    @staticmethod
    def channels(provider: str) -> str:
        """Live-channel list for a provider. TTL: ~5 min."""
        return f"channels:{provider}"

    @staticmethod
    def programs(provider: str) -> str:
        """Replay-show catalogue for a provider. TTL: ~10 min."""
        return f"programs:{provider}"

    @staticmethod
    def episodes(series_id: str) -> str:
        """Episode list for a series. TTL: ~10 min."""
        return f"episodes:{series_id}"

    @staticmethod
    def stream(episode_id: str) -> str:
        """Resolved stream URL for an episode. TTL: ~30 min."""
        return f"stream:{episode_id}"

    @staticmethod
    def programs_file() -> str:
        """Parsed programs.json file contents. TTL: 1 hour."""
        return "programs_data"
