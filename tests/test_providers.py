import pytest
import time
from app.providers.fr.common import ProviderFactory
from app.providers.fr.francetv import FranceTVProvider
from app.providers.fr.mytf1 import MyTF1Provider
from app.providers.fr.sixplay import SixPlayProvider

def test_provider_factory():
    """Test provider factory creation"""
    # Test FranceTV provider creation
    provider = ProviderFactory.create_provider("francetv")
    assert isinstance(provider, FranceTVProvider)
    
    # Test TF1 provider creation
    provider = ProviderFactory.create_provider("mytf1")
    assert isinstance(provider, MyTF1Provider)
    
    # Test 6play provider creation
    provider = ProviderFactory.create_provider("6play")
    assert isinstance(provider, SixPlayProvider)
    
    # Test invalid provider
    with pytest.raises(ValueError):
        ProviderFactory.create_provider("invalid")

def test_francetv_provider():
    """Test FranceTV provider functionality"""
    provider = FranceTVProvider()
    
    # Test live channels
    channels = provider.get_live_channels()
    assert isinstance(channels, list)
    assert len(channels) > 0
    
    # Check that we have the expected channels
    channel_ids = [channel["id"] for channel in channels]
    assert "cutam:fr:francetv:france-2" in channel_ids
    assert "cutam:fr:francetv:france-3" in channel_ids

def test_mytf1_provider_initialization():
    """Test TF1 provider initialization"""
    provider = MyTF1Provider()
    # We can't test authentication without valid credentials in test environment
    assert isinstance(provider, MyTF1Provider)

def test_sixplay_provider_initialization():
    """Test 6play provider initialization"""
    provider = SixPlayProvider()
    # We can't test authentication without valid credentials in test environment
    assert isinstance(provider, SixPlayProvider)

def test_francetv_stream_resolution():
    """Test FranceTV stream resolution"""
    provider = FranceTVProvider()
    
    # Test getting stream for France 2
    stream_info = provider.get_channel_stream_url("cutam:fr:francetv:france-2")
    # Stream info might be None if API is not accessible, but shouldn't crash
    assert stream_info is None or isinstance(stream_info, dict)
    
    # Test getting stream for France 3
    stream_info = provider.get_channel_stream_url("cutam:fr:francetv:france-3")
    # Stream info might be None if API is not accessible, but shouldn't crash
    assert stream_info is None or isinstance(stream_info, dict)