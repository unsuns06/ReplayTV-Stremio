"""Composite Stremio ID parsing.

All IDs in this addon follow the grammar documented in
:mod:`app.schemas.type_defs`::

    cutam:{country}:{provider}:{rest}

where ``rest`` is a show slug, a channel slug, or
``{slug}:episode:{broadcast_id}`` / ``episode:{broadcast_id}`` for episodes.

This module is the single place that splits those strings.  Routers and
providers should use :func:`parse_stremio_id` instead of ad-hoc
``id.split(":")`` / substring matching, which silently mis-routes malformed
IDs (e.g. a provider key appearing anywhere inside an unrelated ID).
"""

from dataclasses import dataclass
from typing import Optional

NAMESPACE = "cutam"


@dataclass(frozen=True)
class StremioId:
    """Parsed composite ID. ``rest`` holds everything after the provider key."""

    country: str
    provider: str
    rest: str
    raw: str

    @property
    def slug(self) -> str:
        """Trailing slug — the last colon-separated segment of ``rest``."""
        return self.rest.split(":")[-1] if self.rest else ""

    def after_marker(self, marker: str) -> Optional[str]:
        """Return the portion of ``rest`` after *marker* (e.g. ``"episode:"``).

        Returns ``None`` when the marker is absent.
        """
        if marker and marker in self.rest:
            return self.rest.split(marker, 1)[1]
        return None


def parse_stremio_id(raw: str) -> Optional[StremioId]:
    """Parse *raw* into a :class:`StremioId`, or ``None`` if malformed.

    A valid ID has at least four colon-separated parts and starts with the
    ``cutam`` namespace: ``cutam:{country}:{provider}:{rest...}``.
    """
    if not raw:
        return None
    parts = raw.split(":")
    if len(parts) < 4 or parts[0] != NAMESPACE or not parts[1] or not parts[2]:
        return None
    return StremioId(
        country=parts[1],
        provider=parts[2],
        rest=":".join(parts[3:]),
        raw=raw,
    )
