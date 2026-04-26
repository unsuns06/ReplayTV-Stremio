"""Abstract base class for all DRM content processors."""

from abc import ABC, abstractmethod
from typing import Any


class DRMProcessor(ABC):
    """Common interface for DRM content processors.

    Concrete processors handle different DRM delivery mechanisms
    (remote API offloading, MPD manifest rewriting, direct download+rewrite).
    """

    @abstractmethod
    def process(self, url: str, **kwargs) -> Any:
        """Process DRM-protected content.

        Args:
            url: URL of the DRM-protected content or manifest
            **kwargs: Processor-specific arguments

        Returns:
            For remote processors: dict with at least a ``success`` key.
            For manifest processors: the rewritten manifest string.
        """
