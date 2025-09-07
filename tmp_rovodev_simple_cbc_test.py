#!/usr/bin/env python3
"""
Simple CBC test script
"""

import sys
import os
import logging

# Add the app directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_basic_imports():
    """Test basic imports"""
    try:
        logger.info("Testing imports...")
        from auth.cbc_auth import CBCAuthenticator
        from providers.ca.cbc import CBCProvider
        logger.info("✅ Imports successful")
        return True
    except Exception as e:
        logger.error(f"❌ Import failed: {e}")
        return False

def test_cbc_auth_init():
    """Test CBC authenticator initialization"""
    try:
        logger.info("Testing CBC authenticator initialization...")
        from auth.cbc_auth import CBCAuthenticator
        auth = CBCAuthenticator()
        logger.info("✅ CBC authenticator initialized")
        return True
    except Exception as e:
        logger.error(f"❌ CBC authenticator init failed: {e}")
        return False

def test_cbc_provider_init():
    """Test CBC provider initialization"""
    try:
        logger.info("Testing CBC provider initialization...")
        from providers.ca.cbc import CBCProvider
        provider = CBCProvider()
        logger.info("✅ CBC provider initialized")
        return True
    except Exception as e:
        logger.error(f"❌ CBC provider init failed: {e}")
        return False

if __name__ == "__main__":
    logger.info("🚀 Starting simple CBC tests...")
    
    success = True
    success &= test_basic_imports()
    success &= test_cbc_auth_init()
    success &= test_cbc_provider_init()
    
    if success:
        logger.info("🎉 All basic tests passed!")
    else:
        logger.error("❌ Some tests failed")
    
    sys.exit(0 if success else 1)