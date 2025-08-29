import pytest
from app.manifest import get_manifest

def test_manifest():
    """Test that the manifest is correctly structured"""
    manifest = get_manifest()
    
    # Check required fields
    assert "id" in manifest
    assert "version" in manifest
    assert "name" in manifest
    assert "description" in manifest
    assert "resources" in manifest
    assert "types" in manifest
    assert "catalogs" in manifest
    
    # Check manifest values
    assert manifest["id"] == "org.catchuptvandmore.stremio"
    assert manifest["types"] == ["channel", "series"]
    
    # Check catalogs
    catalogs = manifest["catalogs"]
    assert len(catalogs) >= 4  # fr-live, francetv-replay, mytf1-replay, 6play-replay
    
    # Check that we have the expected catalogs
    catalog_ids = [cat["id"] for cat in catalogs]
    assert "fr-live" in catalog_ids
    assert "fr-francetv-replay" in catalog_ids
    assert "fr-mytf1-replay" in catalog_ids
    assert "fr-6play-replay" in catalog_ids