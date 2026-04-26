"""Backward-compatible re-export — implementation moved to app.providers.fr.metadata."""
from app.providers.fr.metadata import FranceTVMetadataProcessor, metadata_processor

__all__ = ['FranceTVMetadataProcessor', 'metadata_processor']
