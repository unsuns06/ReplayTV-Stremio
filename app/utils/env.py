import os

def is_offline() -> bool:
    """Return True if running in offline/test mode to avoid external network calls.
    Triggers when:
    - ADDON_OFFLINE is set to a truthy value (1, true, yes, on)
    - PYTEST_CURRENT_TEST environment variable is present (pytest running)
    """
    if os.getenv("PYTEST_CURRENT_TEST") is not None:
        return True
    val = os.getenv("ADDON_OFFLINE", "").strip().lower()
    return val in {"1", "true", "yes", "on"}
