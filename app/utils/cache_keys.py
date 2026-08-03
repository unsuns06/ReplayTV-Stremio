"""Canonical cache key and TTL definitions for the global InMemoryCache.

All modules that read or write the shared cache must use these helpers so
that key-naming is consistent and refactoring a key only requires one edit.
TTLs live next to their keys (``CacheTTL``) so a key's lifetime is defined
exactly once instead of being re-declared per router.
"""


class CacheTTL:
    """Seconds-to-live for each cache key family."""

    CHANNELS = 300        # 5 min  — live-channel lists
    PROGRAMS = 600        # 10 min — replay-show catalogues
    EPISODES = 600        # 10 min — episode lists
    STREAM = 1800         # 30 min — resolved stream URLs (signed, limited life)
    PROGRAMS_FILE = 3600  # 1 hour — parsed programs.json contents


class CacheKeys:
    """Static factory methods for every cache key used in this addon."""

    @staticmethod
    def channels(provider: str) -> str:
        """Live-channel list for a provider. TTL: CacheTTL.CHANNELS."""
        return f"channels:{provider}"

    @staticmethod
    def programs(provider: str) -> str:
        """Replay-show catalogue for a provider. TTL: CacheTTL.PROGRAMS."""
        return f"programs:{provider}"

    @staticmethod
    def episodes(series_id: str) -> str:
        """Episode list for a series. TTL: CacheTTL.EPISODES."""
        return f"episodes:{series_id}"

    @staticmethod
    def stream(episode_id: str) -> str:
        """Resolved stream URL for an episode. TTL: CacheTTL.STREAM."""
        return f"stream:{episode_id}"

    @staticmethod
    def programs_file() -> str:
        """Parsed programs.json file contents. TTL: CacheTTL.PROGRAMS_FILE."""
        return "programs_data"

    @staticmethod
    def auth_state(provider: str) -> str:
        """Persisted auth tokens for a provider. TTL: derived from JWT expiry."""
        return f"auth:{provider}"

    @staticmethod
    def provider_resource(provider: str, resource: str) -> str:
        """Provider-internal API resource (e.g. a GraphQL program list)."""
        return f"provider:{provider}:{resource}"
