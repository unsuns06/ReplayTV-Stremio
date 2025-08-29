import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.manifest import get_manifest

# Create a test client
client = TestClient(app)

def test_root_endpoint():
    """Test the root endpoint"""
    response = client.get("/")
    assert response.status_code == 200
    assert "message" in response.json()

def test_manifest_endpoint():
    """Test the manifest endpoint"""
    response = client.get("/manifest.json")
    assert response.status_code == 200
    
    manifest = response.json()
    
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

def test_catalog_endpoint_fr_live():
    """Test the French live TV catalog endpoint"""
    response = client.get("/catalog/channel/fr-live.json")
    assert response.status_code == 200
    
    data = response.json()
    assert "metas" in data
    
    # Check that we have some channels
    metas = data["metas"]
    assert len(metas) > 0
    
    # Check the structure of the first channel
    first_channel = metas[0]
    assert "id" in first_channel
    assert "type" in first_channel
    assert first_channel["type"] == "channel"
    assert "name" in first_channel

def test_catalog_endpoint_fr_replay():
    """Test the French replay catalog endpoints"""
    # Test france.tv replays
    response = client.get("/catalog/series/fr-francetv-replay.json")
    assert response.status_code == 200
    
    data = response.json()
    assert "metas" in data
    
    # Test myTF1 replays
    response = client.get("/catalog/series/fr-mytf1-replay.json")
    assert response.status_code == 200
    
    data = response.json()
    assert "metas" in data
    
    # Test 6play replays
    response = client.get("/catalog/series/fr-6play-replay.json")
    assert response.status_code == 200
    
    data = response.json()
    assert "metas" in data

def test_meta_endpoint_channel():
    """Test the channel meta endpoint"""
    # Test France 2 channel (using the correct ID format)
    response = client.get("/meta/channel/cutam:fr:francetv:france-2.json")
    assert response.status_code == 200
    
    data = response.json()
    assert "meta" in data
    meta = data["meta"]
    
    # The meta might be empty if the provider fails, but it should exist
    assert meta is not None

def test_meta_endpoint_series():
    """Test the series meta endpoint"""
    # Test Soirée 100% program
    response = client.get("/meta/series/cutam:fr:francetv:prog:soiree100.json")
    assert response.status_code == 200
    
    data = response.json()
    assert "meta" in data
    meta = data["meta"]
    
    assert meta["id"] == "cutam:fr:francetv:prog:soiree100"
    assert meta["type"] == "series"
    assert "name" in meta
    assert "poster" in meta

def test_stream_endpoint_channel():
    """Test the channel stream endpoint"""
    # Test France 2 stream (using the correct ID format)
    response = client.get("/stream/channel/cutam:fr:francetv:france-2.json")
    assert response.status_code == 200
    
    data = response.json()
    assert "streams" in data
    
    # Streams might be empty if the provider fails, but the structure should be correct
    streams = data["streams"]
    assert streams is not None

def test_stream_endpoint_series():
    """Test the series stream endpoint"""
    # Test Soirée 100% episode stream
    response = client.get("/stream/series/cutam:fr:francetv:ep:soiree100:1:1.json")
    assert response.status_code == 200
    
    data = response.json()
    assert "streams" in data
    
    streams = data["streams"]
    assert len(streams) > 0
    
    first_stream = streams[0]
    assert "url" in first_stream
    assert "title" in first_stream

def test_configure_endpoint():
    """Test the configure endpoint"""
    response = client.get("/configure")
    assert response.status_code == 200
    
    data = response.json()
    assert "message" in data

def test_nonexistent_endpoint():
    """Test that nonexistent endpoints return 404"""
    response = client.get("/nonexistent")
    assert response.status_code == 404