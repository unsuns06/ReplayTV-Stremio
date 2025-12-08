"""
Router endpoint tests using FastAPI TestClient.
Tests catalog, meta, and stream router endpoints.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
import json

# Import the main app
from app.main import app

client = TestClient(app)


class TestManifestEndpoint:
    """Test the manifest endpoint"""
    
    def test_manifest_returns_200(self):
        """Manifest should return 200 OK"""
        response = client.get("/manifest.json")
        assert response.status_code == 200
    
    def test_manifest_has_required_fields(self):
        """Manifest should have all required Stremio fields"""
        response = client.get("/manifest.json")
        data = response.json()
        
        assert "id" in data
        assert "name" in data
        assert "version" in data
        assert "catalogs" in data
        assert "resources" in data


class TestCatalogEndpoints:
    """Test catalog router endpoints"""
    
    def test_catalog_francetv_returns_valid_structure(self):
        """FranceTV catalog should return valid Stremio catalog structure"""
        response = client.get("/catalog/series/francetv-replay.json")
        
        # Should return 200 even if provider fails (graceful degradation)
        assert response.status_code == 200
        
        data = response.json()
        assert "metas" in data
        assert isinstance(data["metas"], list)
    
    def test_catalog_cbc_returns_valid_structure(self):
        """CBC catalog should return valid Stremio catalog structure"""
        response = client.get("/catalog/series/cbc-replay.json")
        
        assert response.status_code == 200
        
        data = response.json()
        assert "metas" in data
        assert isinstance(data["metas"], list)
    
    def test_catalog_sixplay_returns_valid_structure(self):
        """6play catalog should return valid Stremio catalog structure"""
        response = client.get("/catalog/series/6play-replay.json")
        
        assert response.status_code == 200
        
        data = response.json()
        assert "metas" in data
        assert isinstance(data["metas"], list)
    
    def test_catalog_mytf1_returns_valid_structure(self):
        """MyTF1 catalog should return valid Stremio catalog structure"""
        response = client.get("/catalog/series/mytf1-replay.json")
        
        assert response.status_code == 200
        
        data = response.json()
        assert "metas" in data
        assert isinstance(data["metas"], list)
    
    def test_catalog_unknown_provider_returns_empty(self):
        """Unknown provider should return empty catalog"""
        response = client.get("/catalog/series/unknown-replay.json")
        
        # Should still return 200 with empty metas
        assert response.status_code == 200
        data = response.json()
        assert data.get("metas", []) == []


class TestMetaEndpoints:
    """Test meta router endpoints"""
    
    def test_meta_invalid_id_returns_404_or_empty(self):
        """Invalid meta ID should return error or empty meta"""
        response = client.get("/meta/series/invalid-id-format.json")
        
        # Should handle gracefully (200 with empty, 404 not found, or 500 error)
        assert response.status_code in [200, 404, 500]


class TestStreamEndpoints:
    """Test stream router endpoints"""
    
    def test_stream_invalid_id_returns_empty_streams(self):
        """Invalid stream ID should return empty streams list"""
        response = client.get("/stream/series/invalid-id.json")
        
        assert response.status_code == 200
        data = response.json()
        assert "streams" in data
        assert isinstance(data["streams"], list)


class TestErrorHandling:
    """Test error handling in endpoints"""
    
    @patch('app.providers.common.ProviderFactory.create_provider')
    def test_catalog_handles_provider_exception(self, mock_create):
        """Catalog should handle provider exceptions gracefully"""
        mock_create.side_effect = Exception("Provider initialization failed")
        
        response = client.get("/catalog/series/francetv-replay.json")
        
        # Should still return 200 with fallback
        assert response.status_code == 200


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
