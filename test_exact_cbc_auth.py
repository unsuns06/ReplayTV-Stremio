#!/usr/bin/env python3
"""
Test script for the exact CBC authentication implementation
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.auth.cbc_auth import CBCAuth, load_tokens, save_tokens
from app.providers.ca.cbc import CBCProvider

def test_exact_auth():
    """Test the exact CBC authentication implementation"""
    print("🔍 Testing Exact CBC Authentication Implementation")
    print("=" * 60)
    
    # Test 1: Test the exact authentication module
    print("\n1. Testing CBC Authentication Module")
    print("-" * 40)
    
    try:
        auth = CBCAuth()
        print("✅ CBC authentication module initialized")
        
        # Test token loading
        access_token, claims_token = load_tokens()
        if access_token and claims_token:
            print("✅ Found existing tokens")
            print(f"   Access token: {access_token[:50]}...")
            print(f"   Claims token: {claims_token[:50]}...")
        else:
            print("ℹ️ No existing tokens found")
        
    except Exception as e:
        print(f"❌ Error testing authentication module: {e}")
        return False
    
    # Test 2: Test CBC provider with exact implementation
    print("\n2. Testing CBC Provider with Exact Implementation")
    print("-" * 40)
    
    try:
        provider = CBCProvider()
        print("✅ CBC provider initialized")
        print(f"   Is authenticated: {provider.is_authenticated}")
        
        if provider.is_authenticated:
            print(f"   Auth token: {provider.auth_token[:50] if provider.auth_token else 'None'}...")
            print(f"   Claims token: {provider.claims_token[:50] if provider.claims_token else 'None'}...")
        
    except Exception as e:
        print(f"❌ Error testing CBC provider: {e}")
        return False
    
    # Test 3: Test program listing
    print("\n3. Testing Program Listing")
    print("-" * 40)
    
    try:
        programs = provider.get_programs()
        print(f"✅ Found {len(programs)} programs")
        for program in programs[:3]:  # Show first 3
            print(f"   - {program.get('name', 'Unknown')}")
    except Exception as e:
        print(f"❌ Error getting programs: {e}")
    
    # Test 4: Test episode listing
    print("\n4. Testing Episode Listing")
    print("-" * 40)
    
    try:
        episodes = provider.get_episodes("cutam:ca:cbc:dragons-den")
        print(f"✅ Found {len(episodes)} episodes")
        for episode in episodes[:3]:  # Show first 3
            print(f"   - {episode.get('title', 'Unknown')}")
    except Exception as e:
        print(f"❌ Error getting episodes: {e}")
    
    # Test 5: Test stream URL generation
    print("\n5. Testing Stream URL Generation")
    print("-" * 40)
    
    try:
        if episodes:
            stream_info = provider.get_stream_url(episodes[0]['id'])
            if stream_info:
                print(f"✅ Generated stream URL: {stream_info['url'][:50]}...")
                print(f"   Manifest type: {stream_info.get('manifest_type', 'Unknown')}")
            else:
                print("❌ No stream URL generated")
    except Exception as e:
        print(f"❌ Error generating stream URL: {e}")
    
    print("\n✅ Exact CBC authentication implementation test completed!")
    return True

if __name__ == "__main__":
    print("Exact CBC Authentication Implementation Test")
    print("=" * 60)
    
    # Test basic functionality
    test_exact_auth()
    
    print("\n🎉 All tests completed!")