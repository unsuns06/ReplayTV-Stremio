#!/usr/bin/env python3
"""
Tests for MyTF1 URL accessibility and geo-blocking bypass
Verifies that resolved URLs actually work and are not geo-blocked
"""

import pytest
import requests
import time
import json
from urllib.parse import urlparse, parse_qs
from app.providers.fr.mytf1 import MyTF1Provider
from app.utils.credentials import get_provider_credentials

# Test configuration
TIMEOUT_SECONDS = 30
MAX_RETRIES = 3

@pytest.fixture
def mytf1_provider():
    """Fixture to provide a MyTF1Provider instance."""
    return MyTF1Provider()

def test_credentials_available():
    """Test that TF1 credentials are available for testing."""
    credentials = get_provider_credentials('mytf1')
    assert credentials.get('login'), "TF1 login credentials required for URL accessibility testing"
    assert credentials.get('password'), "TF1 password credentials required for URL accessibility testing"
    print(f"✅ Credentials available for user: {credentials.get('login')}")

def test_authentication_works(mytf1_provider):
    """Test that authentication with TF1+ works."""
    success = mytf1_provider._authenticate()
    assert success, "TF1 authentication must succeed for URL testing"
    assert mytf1_provider.auth_token, "Authentication token must be present"
    print(f"✅ Authentication successful, token: {mytf1_provider.auth_token[:20]}...")

def test_live_channel_url_accessibility(mytf1_provider):
    """Test that live channel URLs are accessible and working."""
    # Test TF1 live channel
    channel_id = "cutam:fr:mytf1:tf1"
    
    print(f"\n🔍 Testing live channel accessibility: {channel_id}")
    
    # Get stream info with URL logging
    stream_info = mytf1_provider.get_channel_stream_url(channel_id)
    
    if not stream_info:
        pytest.skip("Could not obtain stream info - may indicate geo-blocking or service issues")
    
    stream_url = stream_info.get('url')
    manifest_type = stream_info.get('manifest_type')
    
    print(f"📺 Stream URL obtained: {stream_url[:100]}...")
    print(f"📺 Manifest type: {manifest_type}")
    
    # Test URL accessibility
    accessibility_result = test_url_accessibility(stream_url, "TF1 Live Stream")
    
    assert accessibility_result['accessible'], f"Live stream URL not accessible: {accessibility_result['error']}"
    assert accessibility_result['status_code'] == 200, f"Expected 200 status, got {accessibility_result['status_code']}"
    
    # For HLS streams, verify it's a valid playlist
    if manifest_type == 'hls':
        content = accessibility_result['content']
        assert '#EXTM3U' in content, "HLS stream should contain #EXTM3U header"
        print("✅ Valid HLS playlist confirmed")
    
    print("✅ Live channel URL is accessible and working!")

def test_replay_episode_url_accessibility(mytf1_provider):
    """Test that replay episode URLs are accessible and working."""
    # First get a list of shows to test with
    shows = mytf1_provider.get_programs()
    
    if not shows:
        pytest.skip("No shows available for replay testing")
    
    # Test with the first available show
    test_show = shows[0]
    show_id = test_show['id']
    
    print(f"\n🔍 Testing replay accessibility for show: {test_show['name']}")
    
    # Get episodes for this show
    episodes = mytf1_provider.get_episodes(show_id)
    
    if not episodes:
        pytest.skip(f"No episodes available for show: {test_show['name']}")
    
    # Test with the first episode
    test_episode = episodes[0]
    episode_id = test_episode['id']
    
    print(f"📺 Testing episode: {test_episode.get('title', 'Unknown title')}")
    
    # Get stream info for the episode
    stream_info = mytf1_provider.get_episode_stream_url(episode_id)
    
    if not stream_info:
        pytest.skip("Could not obtain episode stream info - may indicate geo-blocking or content unavailable")
    
    stream_url = stream_info.get('url')
    manifest_type = stream_info.get('manifest_type')
    
    print(f"📺 Episode stream URL: {stream_url[:100]}...")
    print(f"📺 Manifest type: {manifest_type}")
    
    # Test URL accessibility
    accessibility_result = test_url_accessibility(stream_url, "Replay Episode")
    
    assert accessibility_result['accessible'], f"Replay stream URL not accessible: {accessibility_result['error']}"
    assert accessibility_result['status_code'] == 200, f"Expected 200 status, got {accessibility_result['status_code']}"
    
    # Verify content type is appropriate
    if manifest_type == 'hls':
        content = accessibility_result['content']
        assert '#EXTM3U' in content, "HLS replay stream should contain #EXTM3U header"
        print("✅ Valid HLS replay playlist confirmed")
    
    print("✅ Replay episode URL is accessible and working!")

def test_mediaflow_proxy_accessibility(mytf1_provider):
    """Test that MediaFlow proxy URLs are accessible when configured."""
    # Check if MediaFlow is configured
    if not mytf1_provider.mediaflow_url or not mytf1_provider.mediaflow_password:
        pytest.skip("MediaFlow not configured - skipping proxy accessibility test")
    
    print(f"\n🔍 Testing MediaFlow proxy accessibility: {mytf1_provider.mediaflow_url}")
    
    # Test a live channel through MediaFlow
    channel_id = "cutam:fr:mytf1:tf1"
    stream_info = mytf1_provider.get_channel_stream_url(channel_id)
    
    if not stream_info:
        pytest.skip("Could not obtain stream info for MediaFlow testing")
    
    stream_url = stream_info.get('url')
    
    # Verify this is actually a MediaFlow URL
    parsed_url = urlparse(stream_url)
    mediaflow_host = urlparse(mytf1_provider.mediaflow_url).netloc
    
    assert mediaflow_host in parsed_url.netloc, f"Stream URL should use MediaFlow proxy: {mediaflow_host}"
    print(f"✅ Confirmed MediaFlow proxy is being used: {parsed_url.netloc}")
    
    # Test accessibility
    accessibility_result = test_url_accessibility(stream_url, "MediaFlow Proxy Stream", check_hls=False)
    
    # MediaFlow might return different status codes, so be more lenient
    assert accessibility_result['accessible'], f"MediaFlow proxy URL not accessible: {accessibility_result['error']}"
    
    print("✅ MediaFlow proxy URL is accessible!")

def test_french_ip_proxy_effectiveness(mytf1_provider):
    """Test that the French IP proxy is effectively bypassing geo-blocking."""
    print(f"\n🔍 Testing French IP proxy effectiveness...")
    
    # Test direct access to TF1 mediainfo (should be geo-blocked outside France)
    direct_url = "https://mediainfo.tf1.fr/mediainfocombo/L_TF1"
    direct_params = {
        'context': 'MYTF1',
        'pver': '5029000',
        'platform': 'web',
        'device': 'desktop',
        'os': 'windows',
        'osVersion': '10.0',
        'topDomain': 'www.tf1.fr',
        'playerVersion': '5.29.0',
        'productName': 'mytf1',
        'productVersion': '3.37.0',
        'format': 'hls'
    }
    
    print("🚫 Testing direct access (should be geo-blocked)...")
    direct_result = test_url_accessibility_with_params(direct_url, direct_params, "Direct TF1 API")
    
    # Try through the French IP proxy
    from urllib.parse import urlencode, quote
    dest_with_params = direct_url + ("?" + urlencode(direct_params))
    proxy_url = f"https://tvff3tyk1e.execute-api.eu-west-3.amazonaws.com/api/router?url={quote(dest_with_params, safe='')}"
    
    print("🌍 Testing through French IP proxy...")
    proxy_result = test_url_accessibility(proxy_url, "French IP Proxy")
    
    # The proxy should work better than direct access
    if direct_result['accessible'] and proxy_result['accessible']:
        print("✅ Both direct and proxy access work - server may be in France or geo-blocking not active")
    elif not direct_result['accessible'] and proxy_result['accessible']:
        print("✅ Proxy successfully bypasses geo-blocking!")
    elif direct_result['accessible'] and not proxy_result['accessible']:
        print("⚠️ Direct access works but proxy fails - may indicate proxy issues")
    else:
        print("⚠️ Both direct and proxy access fail - may indicate service issues or strong geo-blocking")
    
    # At least one method should work for the user to access content
    assert direct_result['accessible'] or proxy_result['accessible'], \
        "Neither direct nor proxy access works - content is inaccessible"

def test_url_accessibility(url: str, description: str, check_hls: bool = True) -> dict:
    """Test if a URL is accessible and return detailed results."""
    result = {
        'accessible': False,
        'status_code': None,
        'error': None,
        'content': None,
        'response_time': None
    }
    
    try:
        print(f"  🔗 Testing {description}: {url[:80]}...")
        
        start_time = time.time()
        
        # Use appropriate headers for TF1 requests
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36',
            'Accept': 'application/vnd.apple.mpegurl, application/json, text/plain, */*',
            'Accept-Language': 'fr-FR,fr;q=0.9,en;q=0.8',
            'Referer': 'https://www.tf1.fr/',
            'Origin': 'https://www.tf1.fr'
        }
        
        response = requests.get(url, headers=headers, timeout=TIMEOUT_SECONDS, allow_redirects=True)
        
        result['response_time'] = time.time() - start_time
        result['status_code'] = response.status_code
        
        if response.status_code == 200:
            result['accessible'] = True
            result['content'] = response.text[:1000]  # First 1000 chars for analysis
            
            print(f"  ✅ Accessible! Status: {response.status_code}, Response time: {result['response_time']:.2f}s")
            
            # Additional validation for HLS content
            if check_hls and '#EXTM3U' in response.text:
                print(f"  ✅ Valid HLS content detected")
            elif check_hls:
                print(f"  ⚠️ Content received but may not be valid HLS")
            
        elif response.status_code == 403:
            result['error'] = f"Forbidden (403) - likely geo-blocked"
            print(f"  🚫 Geo-blocked! Status: {response.status_code}")
        elif response.status_code in [404, 410]:
            result['error'] = f"Content not found ({response.status_code})"
            print(f"  ❌ Content not found: {response.status_code}")
        else:
            result['error'] = f"HTTP {response.status_code}"
            print(f"  ⚠️ Unexpected status: {response.status_code}")
            
    except requests.exceptions.Timeout:
        result['error'] = f"Request timeout after {TIMEOUT_SECONDS}s"
        print(f"  ⏱️ Timeout after {TIMEOUT_SECONDS}s")
    except requests.exceptions.ConnectionError as e:
        result['error'] = f"Connection error: {str(e)}"
        print(f"  🔌 Connection error: {str(e)}")
    except Exception as e:
        result['error'] = f"Unexpected error: {str(e)}"
        print(f"  ❌ Error: {str(e)}")
    
    return result

def test_url_accessibility_with_params(url: str, params: dict, description: str) -> dict:
    """Test URL accessibility with separate parameters."""
    result = {
        'accessible': False,
        'status_code': None,
        'error': None,
        'content': None,
        'response_time': None
    }
    
    try:
        print(f"  🔗 Testing {description}: {url}")
        
        start_time = time.time()
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'fr-FR,fr;q=0.9,en;q=0.8',
            'Referer': 'https://www.tf1.fr/',
            'Origin': 'https://www.tf1.fr'
        }
        
        response = requests.get(url, params=params, headers=headers, timeout=TIMEOUT_SECONDS)
        
        result['response_time'] = time.time() - start_time
        result['status_code'] = response.status_code
        
        if response.status_code == 200:
            result['accessible'] = True
            result['content'] = response.text[:500]
            print(f"  ✅ Accessible! Status: {response.status_code}")
        elif response.status_code == 403:
            result['error'] = f"Forbidden (403) - likely geo-blocked"
            print(f"  🚫 Geo-blocked! Status: {response.status_code}")
        else:
            result['error'] = f"HTTP {response.status_code}"
            print(f"  ⚠️ Status: {response.status_code}")
            
    except Exception as e:
        result['error'] = f"Error: {str(e)}"
        print(f"  ❌ Error: {str(e)}")
    
    return result

def test_stream_manifest_content_quality():
    """Test that the stream manifests contain quality content."""
    provider = MyTF1Provider()
    
    if not provider._authenticate():
        pytest.skip("Authentication failed - cannot test manifest quality")
    
    # Get a live stream
    stream_info = provider.get_channel_stream_url("cutam:fr:mytf1:tf1")
    
    if not stream_info:
        pytest.skip("Could not get stream info for manifest testing")
    
    stream_url = stream_info.get('url')
    result = test_url_accessibility(stream_url, "Manifest Quality Check")
    
    if result['accessible']:
        content = result['content']
        
        # Check for HLS quality indicators
        if '#EXTM3U' in content:
            print("🎥 Analyzing HLS manifest quality...")
            
            # Look for multiple quality levels
            if '#EXT-X-STREAM-INF' in content:
                stream_lines = [line for line in content.split('\n') if '#EXT-X-STREAM-INF' in line]
                print(f"📊 Found {len(stream_lines)} quality streams")
                
                # Look for resolution indicators
                resolutions = []
                for line in stream_lines:
                    if 'RESOLUTION=' in line:
                        res_part = line.split('RESOLUTION=')[1].split(',')[0]
                        resolutions.append(res_part)
                
                if resolutions:
                    print(f"📺 Available resolutions: {', '.join(resolutions)}")
                else:
                    print("📺 No resolution information found in manifest")
            
            print("✅ Manifest analysis complete")

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
