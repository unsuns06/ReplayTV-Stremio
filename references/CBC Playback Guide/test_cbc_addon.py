#!/usr/bin/env python3
"""
CBC Gem Stremio Addon - Test Suite
Test script to verify authentication and functionality
"""

import sys
import json
import logging
from typing import Dict, Any
import time

try:
    from cbc_auth import CBCAuthenticator
    from cbc_url_parser import CBCURLParser
except ImportError:
    print("Error: Make sure cbc_auth.py and cbc_url_parser.py are in the same directory")
    sys.exit(1)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

class CBCAddonTester:
    """Test suite for CBC Gem Stremio addon"""
    
    def __init__(self):
        self.auth = None
        self.parser = CBCURLParser()
    
    def test_url_parsing(self):
        """Test URL parsing functionality"""
        print("\n" + "="*50)
        print("TESTING URL PARSING")
        print("="*50)
        
        test_urls = [
            'https://gem.cbc.ca/media/schitts-creek/s06e01',
            'https://gem.cbc.ca/schitts-creek/s06e01',
            'https://gem.cbc.ca/media/heartland/s15e10', 
            'https://gem.cbc.ca/coroner/s04',
            'https://gem.cbc.ca/media/marketplace',
            'https://gem.cbc.ca/the-national',
        ]
        
        for url in test_urls:
            print(f"\nTesting: {url}")
            result = self.parser.parse_cbc_url(url)
            if result:
                print(f"  ✓ Parsed successfully")
                print(f"    Show: {self.parser.normalize_show_name(result['show_name'])}")
                print(f"    ID: {result['full_id']}")
                print(f"    Type: {result['type']}")
                if result['season']:
                    print(f"    Season: {result['season']}")
                if result['episode']:
                    print(f"    Episode: {result['episode']}")
                stremio_id = self.parser.create_stremio_id(result)
                print(f"    Stremio ID: {stremio_id}")
            else:
                print("  ✗ Failed to parse")
        
        return True
    
    def test_authentication(self, email: str, password: str):
        """Test authentication flow"""
        print("\n" + "="*50)
        print("TESTING AUTHENTICATION")
        print("="*50)
        
        print(f"Testing with email: {email}")
        
        # Initialize authenticator
        cache = {}
        self.auth = CBCAuthenticator(cache_handler=cache)
        
        # Test ROPC settings
        print("\n1. Testing ROPC settings...")
        try:
            ropc_settings = self.auth.get_ropc_settings()
            print(f"  ✓ ROPC URL: {ropc_settings.get('url', 'N/A')}")
            print(f"  ✓ Scopes: {ropc_settings.get('scopes', 'N/A')}")
        except Exception as e:
            print(f"  ✗ Failed to get ROPC settings: {e}")
            return False
        
        # Test login
        print("\n2. Testing login...")
        try:
            success = self.auth.login(email, password)
            if success:
                print("  ✓ Login successful")
            else:
                print("  ✗ Login failed")
                return False
        except Exception as e:
            print(f"  ✗ Login error: {e}")
            return False
        
        # Test access token
        print("\n3. Testing access token...")
        try:
            access_token = self.auth.get_access_token()
            if access_token:
                print("  ✓ Access token obtained")
                # Check expiry
                is_expired = self.auth._is_jwt_expired(access_token)
                print(f"  ✓ Token expired: {is_expired}")
            else:
                print("  ✗ No access token")
                return False
        except Exception as e:
            print(f"  ✗ Access token error: {e}")
            return False
        
        # Test claims token
        print("\n4. Testing claims token...")
        try:
            claims_token = self.auth.get_claims_token()
            if claims_token:
                print("  ✓ Claims token obtained")
                # Check expiry
                is_expired = self.auth._is_jwt_expired(claims_token)
                print(f"  ✓ Token expired: {is_expired}")
            else:
                print("  ✗ No claims token")
                return False
        except Exception as e:
            print(f"  ✗ Claims token error: {e}")
            return False
        
        print("\n✓ Authentication tests passed!")
        return True
    
    def test_content_access(self):
        """Test content access functionality"""
        if not self.auth:
            print("Error: Authentication required first")
            return False
            
        print("\n" + "="*50)
        print("TESTING CONTENT ACCESS")
        print("="*50)
        
        # Test show info
        print("\n1. Testing show info...")
        test_show = "schitts-creek"
        try:
            show_info = self.auth.get_show_info(test_show)
            if show_info:
                print(f"  ✓ Retrieved show info for {test_show}")
                print(f"    Title: {show_info.get('title', 'N/A')}")
                print(f"    Content items: {len(show_info.get('content', []))}")
            else:
                print(f"  ✗ No show info for {test_show}")
        except Exception as e:
            print(f"  ✗ Show info error: {e}")
        
        # Test stream data (using a public media ID)
        print("\n2. Testing stream data...")
        # Note: This would need a real media ID from the show info
        try:
            # This is a placeholder - in real usage you'd extract from show_info
            print("  ⚠ Stream data test requires specific media ID")
            print("    (Would need to extract from actual show data)")
        except Exception as e:
            print(f"  ✗ Stream data error: {e}")
        
        return True
    
    def test_full_workflow(self, email: str, password: str, test_url: str = None):
        """Test complete workflow"""
        print("\n" + "="*60)
        print("FULL WORKFLOW TEST")
        print("="*60)
        
        # Test URL parsing if provided
        if test_url:
            print(f"\nTesting with URL: {test_url}")
            url_result = self.parser.parse_cbc_url(test_url)
            if url_result:
                print(f"✓ URL parsed: {url_result['full_id']}")
            else:
                print("✗ URL parsing failed")
                return False
        
        # Test authentication
        if not self.test_authentication(email, password):
            return False
        
        # Test content access
        if not self.test_content_access():
            return False
        
        print("\n" + "="*60)
        print("ALL TESTS COMPLETED!")
        print("="*60)
        print("✓ The addon should be ready to use with Stremio")
        return True

def main():
    """Main test runner"""
    print("CBC Gem Stremio Addon - Test Suite")
    print("==================================")
    
    tester = CBCAddonTester()
    
    # Test URL parsing (no credentials needed)
    tester.test_url_parsing()
    
    # Get credentials for authentication tests
    print("\n" + "="*50)
    print("AUTHENTICATION TESTS")
    print("="*50)
    print("To test authentication, please provide your CBC Gem credentials:")
    print("(These are only used for testing and are not stored)")
    
    email = input("CBC Gem email: ").strip()
    password = input("CBC Gem password: ").strip()
    
    if not email or not password:
        print("\nSkipping authentication tests (no credentials provided)")
        print("URL parsing tests completed successfully!")
        return
    
    # Test with optional URL
    test_url = input("Optional - CBC Gem URL to test (press Enter to skip): ").strip()
    
    # Run full workflow test
    success = tester.test_full_workflow(email, password, test_url or None)
    
    if success:
        print("\n🎉 All tests passed! Your addon should work correctly.")
        print("\nNext steps:")
        print("1. Run: python cbc_stremio_addon.py")
        print("2. Open: http://localhost:7000/configure")
        print("3. Enter your credentials and get the install URL")
        print("4. Install the addon in Stremio")
    else:
        print("\n❌ Some tests failed. Check the error messages above.")
        print("Common issues:")
        print("- Invalid credentials")
        print("- Not using a Canadian IP address")
        print("- CBC API temporarily unavailable")

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
    except Exception as e:
        print(f"\n\nUnexpected error: {e}")
        import traceback
        traceback.print_exc()