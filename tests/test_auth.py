import pytest
from app.auth.francetv_auth import FranceTVAuth
from app.auth.mytf1_auth import MyTF1Auth
from app.auth.sixplay_auth import SixPlayAuth

def test_francetv_auth():
    """Test FranceTV authentication functionality"""
    # Test initialization
    auth = FranceTVAuth("testuser", "testpass")
    assert auth.username == "testuser"
    assert auth.password == "testpass"
    assert auth.session_token is None
    
    # Test login
    result = auth.login()
    assert result is True
    assert auth.session_token is not None
    
    # Test is_authenticated
    assert auth.is_authenticated() is True
    
    # Test refresh_session
    old_token = auth.session_token
    result = auth.refresh_session()
    assert result is True
    assert auth.session_token is not None
    assert auth.session_token != old_token

def test_mytf1_auth():
    """Test MyTF1 authentication functionality"""
    # Test initialization
    auth = MyTF1Auth("testuser", "testpass")
    assert auth.username == "testuser"
    assert auth.password == "testpass"
    assert auth.session_token is None
    
    # Test login
    result = auth.login()
    assert result is True
    assert auth.session_token is not None
    
    # Test is_authenticated
    assert auth.is_authenticated() is True
    
    # Test refresh_session
    old_token = auth.session_token
    result = auth.refresh_session()
    assert result is True
    assert auth.session_token is not None
    assert auth.session_token != old_token

def test_sixplay_auth():
    """Test 6play authentication functionality"""
    # Test initialization
    auth = SixPlayAuth("testuser", "testpass")
    assert auth.username == "testuser"
    assert auth.password == "testpass"
    assert auth.session_token is None
    
    # Test login
    result = auth.login()
    assert result is True
    assert auth.session_token is not None
    
    # Test is_authenticated
    assert auth.is_authenticated() is True
    
    # Test refresh_session
    old_token = auth.session_token
    result = auth.refresh_session()
    assert result is True
    assert auth.session_token is not None
    assert auth.session_token != old_token