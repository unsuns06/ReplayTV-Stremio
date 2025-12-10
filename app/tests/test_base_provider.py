"""
Base Provider Inheritance Tests
Verifies all providers properly inherit from BaseProvider and have required attributes.
"""

import pytest
from typing import Type


class TestBaseProviderInheritance:
    """Verify all providers properly inherit from BaseProvider"""
    
    @pytest.fixture
    def base_provider_class(self):
        from app.providers.base_provider import BaseProvider
        return BaseProvider
    
    @pytest.fixture
    def sixplay_provider(self):
        from app.providers.fr.sixplay import SixPlayProvider
        return SixPlayProvider()
    
    @pytest.fixture
    def mytf1_provider(self):
        from app.providers.fr.mytf1 import MyTF1Provider
        return MyTF1Provider()
    
    @pytest.fixture
    def francetv_provider(self):
        from app.providers.fr.francetv import FranceTVProvider
        return FranceTVProvider()
    
    @pytest.fixture
    def cbc_provider(self):
        from app.providers.ca.cbc import CBCProvider
        return CBCProvider()
    
    def test_sixplay_inherits_base_provider(self, base_provider_class):
        """SixPlayProvider should inherit from BaseProvider"""
        from app.providers.fr.sixplay import SixPlayProvider
        assert issubclass(SixPlayProvider, base_provider_class)
    
    def test_mytf1_inherits_base_provider(self, base_provider_class):
        """MyTF1Provider should inherit from BaseProvider"""
        from app.providers.fr.mytf1 import MyTF1Provider
        assert issubclass(MyTF1Provider, base_provider_class)
    
    def test_francetv_inherits_base_provider(self, base_provider_class):
        """FranceTVProvider should inherit from BaseProvider"""
        from app.providers.fr.francetv import FranceTVProvider
        assert issubclass(FranceTVProvider, base_provider_class)
    
    def test_cbc_inherits_base_provider(self, base_provider_class):
        """CBCProvider should inherit from BaseProvider"""
        from app.providers.ca.cbc import CBCProvider
        assert issubclass(CBCProvider, base_provider_class)
    
    def test_sixplay_has_required_attributes(self, sixplay_provider):
        """SixPlayProvider should have required provider attributes"""
        assert hasattr(sixplay_provider, 'provider_name')
        assert sixplay_provider.provider_name == "6play"
        assert hasattr(sixplay_provider, 'session')
        assert hasattr(sixplay_provider, 'api_client')
        assert hasattr(sixplay_provider, 'credentials')
    
    def test_mytf1_has_required_attributes(self, mytf1_provider):
        """MyTF1Provider should have required provider attributes"""
        assert hasattr(mytf1_provider, 'provider_name')
        assert mytf1_provider.provider_name == "mytf1"
        assert hasattr(mytf1_provider, 'session')
        assert hasattr(mytf1_provider, 'api_client')
        assert hasattr(mytf1_provider, 'credentials')
    
    def test_francetv_has_required_attributes(self, francetv_provider):
        """FranceTVProvider should have required provider attributes"""
        assert hasattr(francetv_provider, 'provider_name')
        assert francetv_provider.provider_name == "francetv"
        assert hasattr(francetv_provider, 'session')
        assert hasattr(francetv_provider, 'api_client')
        assert hasattr(francetv_provider, 'credentials')
    
    def test_cbc_has_required_attributes(self, cbc_provider):
        """CBCProvider should have required provider attributes"""
        assert hasattr(cbc_provider, 'provider_name')
        assert cbc_provider.provider_name == "cbc"
        assert hasattr(cbc_provider, 'session')
        assert hasattr(cbc_provider, 'api_client')
        assert hasattr(cbc_provider, 'credentials')


class TestProviderAPIClientInheritance:
    """Verify ProviderAPIClient properly extends RobustHTTPClient"""
    
    def test_provider_api_client_inherits_robust_http_client(self):
        """ProviderAPIClient should inherit from RobustHTTPClient"""
        from app.utils.api_client import ProviderAPIClient
        from app.utils.http_utils import RobustHTTPClient
        
        assert issubclass(ProviderAPIClient, RobustHTTPClient)
    
    def test_provider_api_client_has_inherited_methods(self):
        """ProviderAPIClient should have inherited safe_json_parse method"""
        from app.utils.api_client import ProviderAPIClient
        
        client = ProviderAPIClient(provider_name="test")
        
        assert hasattr(client, 'safe_json_parse')
        assert hasattr(client, 'session')
        assert hasattr(client, 'timeout')
        assert hasattr(client, 'max_retries')
    
    def test_provider_api_client_has_provider_features(self):
        """ProviderAPIClient should have provider-specific features"""
        from app.utils.api_client import ProviderAPIClient
        
        client = ProviderAPIClient(provider_name="test_provider")
        
        assert client.provider_name == "test_provider"
        assert hasattr(client, '_prepare_headers')
        assert hasattr(client, 'safe_request')
        assert hasattr(client, 'get')
        assert hasattr(client, 'post')


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
