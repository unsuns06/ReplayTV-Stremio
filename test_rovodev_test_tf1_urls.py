#!/usr/bin/env python3
"""
Simple tests for TF1 URL resolving - Live feeds and Replays
"""

import sys
import os
sys.path.append('.')

from app.providers.fr.mytf1 import MyTF1Provider
from app.utils.safe_print import safe_print

def test_tf1_live_stream_url():
    """Test TF1 live stream URL resolution"""
    print("=" * 60)
    print("Testing TF1 Live Stream URL Resolution")
    print("=" * 60)
    
    provider = MyTF1Provider()
    
    # Test TF1 main channel
    channel_id = "cutam:fr:mytf1:tf1"
    safe_print(f"Testing live stream for: {channel_id}")
    
    try:
        stream_info = provider.get_channel_stream_url(channel_id)
        
        if stream_info:
            safe_print("✅ SUCCESS: Got stream info")
            safe_print(f"   URL: {stream_info.get('url', 'N/A')[:100]}...")
            safe_print(f"   Manifest Type: {stream_info.get('manifest_type', 'N/A')}")
            safe_print(f"   Has Headers: {bool(stream_info.get('headers'))}")
            safe_print(f"   Has License URL: {bool(stream_info.get('licenseUrl'))}")
            return True
        else:
            safe_print("❌ FAIL: No stream info returned")
            return False
            
    except Exception as e:
        safe_print(f"❌ ERROR: {e}")
        return False

def test_tf1_replay_stream_url():
    """Test TF1 replay stream URL resolution"""
    print("\n" + "=" * 60)
    print("Testing TF1 Replay Stream URL Resolution")
    print("=" * 60)
    
    provider = MyTF1Provider()
    
    # First, get a valid episode ID from the provider
    programs = provider.get_programs()
    if not programs:
        safe_print("❌ FAIL: Could not retrieve any programs to test.")
        return False
        
    # Use the first program to find episodes
    show_id = programs[0]['id']
    safe_print(f"Testing with show: {programs[0]['name']} ({show_id})")
    
    episodes = provider.get_episodes(show_id)
    if not episodes:
        safe_print(f"❌ FAIL: Could not retrieve episodes for show: {show_id}")
        return False
        
    # Use the first episode for the test
    episode_id = episodes[0]['id']
    safe_print(f"Testing replay stream for episode: {episodes[0]['title']} ({episode_id})")
    
    try:
        stream_info = provider.get_episode_stream_url(episode_id)
        
        if stream_info:
            safe_print("✅ SUCCESS: Got stream info")
            safe_print(f"   URL: {stream_info.get('url', 'N/A')[:100]}...")
            safe_print(f"   Manifest Type: {stream_info.get('manifest_type', 'N/A')}")
            safe_print(f"   Has Headers: {bool(stream_info.get('headers'))}")
            safe_print(f"   Has License URL: {bool(stream_info.get('licenseUrl'))}")
            return True
        else:
            safe_print("❌ FAIL: No stream info returned")
            return False
            
    except Exception as e:
        safe_print(f"❌ ERROR: {e}")
        return False

def test_tf1_authentication():
    """Test TF1 authentication"""
    print("\n" + "=" * 60)
    print("Testing TF1 Authentication")
    print("=" * 60)
    
    provider = MyTF1Provider()
    
    try:
        # Try to authenticate
        auth_success = provider._authenticate()
        
        if auth_success:
            safe_print("✅ SUCCESS: Authentication successful")
            safe_print(f"   Auth token exists: {bool(provider.auth_token)}")
            safe_print(f"   Is authenticated: {provider._authenticated}")
            return True
        else:
            safe_print("❌ FAIL: Authentication failed")
            safe_print("   This might be expected if no credentials are configured")
            return False
            
    except Exception as e:
        safe_print(f"❌ ERROR: {e}")
        return False

def test_tf1_show_data():
    """Test TF1 show data retrieval"""
    print("\n" + "=" * 60)
    print("Testing TF1 Show Data Retrieval")
    print("=" * 60)
    
    provider = MyTF1Provider()
    
    try:
        # Test getting live channels
        channels = provider.get_live_channels()
        safe_print(f"✅ Live channels retrieved: {len(channels)} channels")
        for channel in channels[:3]:  # Show first 3
            safe_print(f"   - {channel.get('name', 'N/A')}: {channel.get('id', 'N/A')}")
        
        # Test getting programs
        programs = provider.get_programs()
        safe_print(f"✅ Programs retrieved: {len(programs)} programs")
        for program in programs[:3]:  # Show first 3
            safe_print(f"   - {program.get('name', 'N/A')}: {program.get('id', 'N/A')}")
        
        return True
        
    except Exception as e:
        safe_print(f"❌ ERROR: {e}")
        return False

def main():
    """Run all tests"""
    print("TF1 URL Resolution Tests")
    print("========================")
    
    results = []
    
    # Test authentication first
    results.append(("Authentication", test_tf1_authentication()))
    
    # Test show data
    results.append(("Show Data", test_tf1_show_data()))
    
    # Test live streams
    results.append(("Live Stream URL", test_tf1_live_stream_url()))
    
    # Test replay streams
    results.append(("Replay Stream URL", test_tf1_replay_stream_url()))
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    passed = 0
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        safe_print(f"{test_name}: {status}")
        if result:
            passed += 1
    
    print(f"\nTotal: {passed}/{len(results)} tests passed")
    
    if passed == len(results):
        safe_print("🎉 All tests passed!")
        return 0
    else:
        safe_print("⚠️ Some tests failed")
        return 1

if __name__ == "__main__":
    exit(main())