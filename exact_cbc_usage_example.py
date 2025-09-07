#!/usr/bin/env python3
"""
Exact CBC Authentication Usage Example
Demonstrates how to use the exact CBC authentication implementation
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.auth.cbc_auth import CBCAuth, load_tokens
from app.providers.ca.cbc import CBCProvider

def example_usage():
    """Example of how to use the exact CBC authentication implementation"""
    
    print("Exact CBC Authentication Usage Example")
    print("=" * 50)
    
    # Method 1: Using the CBC provider (recommended for Stremio add-on)
    print("\n1. Using CBC Provider (Recommended)")
    print("-" * 30)
    
    # Initialize the provider
    provider = CBCProvider()
    
    # Check if already authenticated
    if provider.is_authenticated:
        print("✅ Already authenticated!")
    else:
        print("🔐 Not authenticated, need to login...")
        
        # You can authenticate using credentials from your config
        # provider.authenticate(username, password)
        
        # Or load from credentials file (already done in __init__)
        print("ℹ️ Check credentials-test.json for CBC credentials")
    
    # Get programs
    programs = provider.get_programs()
    print(f"📺 Found {len(programs)} programs")
    
    # Get episodes for a program
    if programs:
        episodes = provider.get_episodes(programs[0]['id'])
        print(f"📺 Found {len(episodes)} episodes")
        
        # Get stream URL for an episode
        if episodes:
            stream_info = provider.get_stream_url(episodes[0]['id'])
            if stream_info:
                print(f"🎬 Stream URL: {stream_info['url'][:50]}...")
            else:
                print("❌ No stream URL available")
    
    # Method 2: Using CBC authentication directly
    print("\n2. Using CBC Authentication Directly")
    print("-" * 30)
    
    auth = CBCAuth()
    
    # Check if already authenticated
    access_token, claims_token = load_tokens()
    if access_token and claims_token:
        print("✅ Already authenticated!")
        print(f"🔑 Access token: {access_token[:50]}...")
        print(f"🔑 Claims token: {claims_token[:50]}...")
    else:
        print("🔐 Not authenticated")
        print("   Use auth.authenticate(username, password) to login")
    
    # Method 3: Using tokens directly for API requests
    print("\n3. Using Tokens Directly for API Requests")
    print("-" * 30)
    
    if access_token and claims_token:
        print("✅ Tokens loaded successfully")
        
        # Use tokens for API requests
        headers = {
            'Authorization': f'Bearer {access_token}',
            'x-claims-token': claims_token
        }
        print(f"📡 Use these headers for CBC API requests: {headers}")
    else:
        print("❌ No tokens found")

def example_stream_request():
    """Example of making a stream request with authentication"""
    
    print("\n4. Making Authenticated Stream Request")
    print("-" * 30)
    
    import requests
    
    # Load tokens
    access_token, claims_token = load_tokens()
    
    if not access_token or not claims_token:
        print("❌ No authentication tokens available")
        return
    
    # Example: Get stream URL for a media ID
    media_id = "1234567"  # Replace with actual media ID
    stream_api_url = "https://services.radio-canada.ca/media/validation/v2/"
    
    params = {
        'appCode': 'toutv',
        'connectionType': 'hd',
        'deviceType': 'web',
        'idMedia': media_id,
        'multibitrate': 'true',
        'output': 'json',
        'tech': 'hls',
        'manifestType': 'desktop'
    }
    
    headers = {
        'Authorization': f'Bearer {access_token}',
        'x-claims-token': claims_token,
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Referer': 'https://gem.cbc.ca/',
        'Accept': 'application/json, text/plain, */*'
    }
    
    try:
        response = requests.get(stream_api_url, params=params, headers=headers)
        response.raise_for_status()
        
        data = response.json()
        if 'url' in data:
            print(f"✅ Stream URL: {data['url']}")
        else:
            print(f"❌ No stream URL in response: {data}")
            
    except Exception as e:
        print(f"❌ Error making stream request: {e}")

def example_manual_auth():
    """Example of manual authentication"""
    
    print("\n5. Manual Authentication Example")
    print("-" * 30)
    
    try:
        auth = CBCAuth()
        
        # Check if already authenticated
        access_token, claims_token = load_tokens()
        if access_token and claims_token:
            print("✅ Already authenticated!")
            return True
        
        # Ask for credentials
        print("Please provide CBC Gem credentials:")
        username = input("Email: ").strip()
        password = input("Password: ").strip()
        
        if not username or not password:
            print("❌ No credentials provided")
            return False
        
        # Attempt authentication using exact implementation
        print("🔐 Attempting authentication using exact implementation...")
        auth.authenticate(username, password)
        
        # Check if authentication was successful
        access_token, claims_token = load_tokens()
        if access_token and claims_token:
            print("✅ Authentication successful!")
            print(f"   Access token: {access_token[:50]}...")
            print(f"   Claims token: {claims_token[:50]}...")
            return True
        else:
            print("❌ Authentication failed - no tokens received")
            return False
            
    except Exception as e:
        print(f"❌ Error during manual authentication: {e}")
        return False

if __name__ == "__main__":
    example_usage()
    example_stream_request()
    
    print("\n" + "=" * 50)
    print("🎉 Usage example completed!")
    print("\nTo use in your Stremio add-on:")
    print("1. Add CBC credentials to credentials-test.json")
    print("2. Initialize CBCProvider()")
    print("3. Call provider.authenticate() if needed")
    print("4. Use provider.get_stream_url() for episodes")
    print("\nFor direct API access:")
    print("1. Use CBCAuth().authenticate(username, password)")
    print("2. Use load_tokens() to get access_token and claims_token")
    print("3. Use tokens in Authorization and x-claims-token headers")


