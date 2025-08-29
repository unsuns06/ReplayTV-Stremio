#!/usr/bin/env python3
"""
Test script to verify JSON proxy configuration
"""

import sys
import os

# Add the app directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app.utils.proxy_config import proxy_config
from app.utils.json_proxy import proxy_client

def test_proxy_config():
    """Test the proxy configuration"""
    print("🧪 Testing JSON Proxy Configuration")
    print("=" * 50)
    
    # Print current configuration
    proxy_config.print_config()
    
    # Validate configuration
    print(f"\n🔍 Validating configuration...")
    if proxy_config.validate_config():
        print("✅ Configuration is valid")
    else:
        print("❌ Configuration is invalid")
        return False
    
    return True

def test_proxy_client():
    """Test the proxy client"""
    print(f"\n🧪 Testing Proxy Client")
    print("=" * 50)
    
    # Test a simple request
    test_url = "https://httpbin.org/json"
    
    print(f"Testing GET request to: {test_url}")
    
    try:
        # Test with proxy enabled
        if proxy_config.is_enabled():
            print("🔧 Testing with proxy enabled...")
            response = proxy_client.get_json(
                url=test_url,
                context="Proxy Test - httpbin.org"
            )
            
            if response:
                print("✅ Proxy request successful")
                print(f"   Response keys: {list(response.keys())}")
            else:
                print("❌ Proxy request failed")
                return False
        else:
            print("⚠️  Proxy is disabled, testing direct request...")
            response = proxy_client.get_json(
                url=test_url,
                use_proxy=False,
                context="Direct Test - httpbin.org"
            )
            
            if response:
                print("✅ Direct request successful")
                print(f"   Response keys: {list(response.keys())}")
            else:
                print("❌ Direct request failed")
                return False
    
    except Exception as e:
        print(f"❌ Request failed with error: {e}")
        return False
    
    return True

def test_french_tv_endpoints():
    """Test French TV endpoints through proxy"""
    print(f"\n🧪 Testing French TV Endpoints")
    print("=" * 50)
    
    # Test France TV endpoint
    france_tv_url = "http://api-front.yatta.francetv.fr/standard/publish/taxonomies/france-2_envoye-special"
    france_tv_params = {"platform": "apps"}
    
    print(f"Testing France TV API: {france_tv_url}")
    
    try:
        response = proxy_client.get_json(
            url=france_tv_url,
            params=france_tv_params,
            context="France TV Test"
        )
        
        if response:
            print("✅ France TV API request successful")
            print(f"   Response type: {type(response)}")
            if isinstance(response, dict):
                print(f"   Response keys: {list(response.keys())}")
        else:
            print("❌ France TV API request failed")
            return False
    
    except Exception as e:
        print(f"❌ France TV API test failed: {e}")
        return False
    
    return True

def main():
    """Run all tests"""
    print("🚀 JSON Proxy Test Suite")
    print("=" * 50)
    
    # Test 1: Configuration
    if not test_proxy_config():
        print("\n❌ Configuration test failed")
        return False
    
    # Test 2: Proxy Client
    if not test_proxy_client():
        print("\n❌ Proxy client test failed")
        return False
    
    # Test 3: French TV Endpoints
    if not test_french_tv_endpoints():
        print("\n❌ French TV endpoints test failed")
        return False
    
    print("\n🎉 All tests passed!")
    print("\n💡 The JSON proxy is now configured and ready to use.")
    print("   All French TV provider requests will be routed through the proxy.")
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
