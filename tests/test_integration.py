import pytest
from fastapi.testclient import TestClient
from app.main import app

# Create a test client
client = TestClient(app)

def test_full_application_flow():
    """Test the full application flow from manifest to stream resolution"""
    
    # 1. Get the manifest
    response = client.get("/manifest.json")
    assert response.status_code == 200
    manifest = response.json()
    
    # Check that manifest has the expected structure
    assert "id" in manifest
    assert "version" in manifest
    assert "name" in manifest
    assert "description" in manifest
    assert "resources" in manifest
    assert "types" in manifest
    assert "catalogs" in manifest
    
    # 2. Get the French live TV catalog
    response = client.get("/catalog/channel/fr-live.json")
    assert response.status_code == 200
    catalog_data = response.json()
    assert "metas" in catalog_data
    
    # Check that we have TV channels
    metas = catalog_data["metas"]
    assert len(metas) > 0
    
    # Find France 2 in the catalog
    france2 = None
    for meta in metas:
        if meta["id"] == "cutam:fr:francetv:france-2":
            france2 = meta
            break
    
    assert france2 is not None
    assert france2["type"] == "channel"
    assert france2["name"] == "France 2"
    
    # 3. Get metadata for France 2
    response = client.get("/meta/channel/cutam:fr:francetv:france-2.json")
    assert response.status_code == 200
    meta_data = response.json()
    assert "meta" in meta_data
    
    meta = meta_data["meta"]
    assert meta["id"] == "cutam:fr:francetv:france-2"
    assert meta["type"] == "channel"
    assert meta["name"] == "France 2"
    assert "description" in meta
    
    # 4. Get stream for France 2
    response = client.get("/stream/channel/cutam:fr:francetv:france-2.json")
    assert response.status_code == 200
    stream_data = response.json()
    assert "streams" in stream_data
    
    streams = stream_data["streams"]
    assert len(streams) > 0
    
    first_stream = streams[0]
    assert "url" in first_stream
    assert "title" in first_stream
    
    # 5. Test a replay program
    # Get the France.tv replay catalog
    response = client.get("/catalog/series/fr-francetv-replay.json")
    assert response.status_code == 200
    replay_catalog = response.json()
    assert "metas" in replay_catalog
    
    # Find Soirée 100% in the catalog
    soiree100 = None
    metas = replay_catalog["metas"]
    for meta in metas:
        if meta["id"] == "cutam:fr:francetv:prog:soiree100":
            soiree100 = meta
            break
    
    assert soiree100 is not None
    assert soiree100["type"] == "series"
    assert soiree100["name"] == "Soirée 100%"
    
    # 6. Get metadata for Soirée 100%
    response = client.get("/meta/series/cutam:fr:francetv:prog:soiree100.json")
    assert response.status_code == 200
    meta_data = response.json()
    assert "meta" in meta_data
    
    meta = meta_data["meta"]
    assert meta["id"] == "cutam:fr:francetv:prog:soiree100"
    assert meta["type"] == "series"
    assert meta["name"] == "Soirée 100%"
    assert "description" in meta
    assert "videos" in meta
    
    # 7. Get stream for Soirée 100% episode
    response = client.get("/stream/series/cutam:fr:francetv:ep:soiree100:1:1.json")
    assert response.status_code == 200
    stream_data = response.json()
    assert "streams" in stream_data
    
    streams = stream_data["streams"]
    assert len(streams) > 0
    
    first_stream = streams[0]
    assert "url" in first_stream
    assert "title" in first_stream



def test_id_parsing():
    """Test ID parsing utilities"""
    from app.utils.ids import parse_channel_id, parse_program_id, parse_episode_id
    
    # Test channel ID parsing
    result = parse_channel_id("cutam:fr:francetv:france2")
    assert result == {"provider": "francetv", "channel_slug": "france2"}
    
    # Test program ID parsing
    result = parse_program_id("cutam:fr:francetv:prog:soiree100")
    assert result == {"provider": "francetv", "program_slug": "soiree100"}
    
    # Test episode ID parsing
    result = parse_episode_id("cutam:fr:francetv:ep:soiree100:1:1")
    assert result == {"provider": "francetv", "program_slug": "soiree100", "season": 1, "episode": 1}

def test_provider_factory():
    """Test provider factory"""
    from app.providers.fr.common import ProviderFactory
    
    # Test creating providers
    francetv = ProviderFactory.create_provider("francetv")
    mytf1 = ProviderFactory.create_provider("mytf1")
    sixplay = ProviderFactory.create_provider("6play")
    
    # Test that they have the expected methods
    assert hasattr(francetv, "get_live_channels")
    assert hasattr(francetv, "get_programs")
    assert hasattr(francetv, "get_episodes")
    assert hasattr(francetv, "resolve_stream")
    
    assert hasattr(mytf1, "get_live_channels")
    assert hasattr(mytf1, "get_programs")
    assert hasattr(mytf1, "get_episodes")
    assert hasattr(mytf1, "resolve_stream")
    
    assert hasattr(sixplay, "get_live_channels")
    assert hasattr(sixplay, "get_programs")
    assert hasattr(sixplay, "get_episodes")
    assert hasattr(sixplay, "resolve_stream")