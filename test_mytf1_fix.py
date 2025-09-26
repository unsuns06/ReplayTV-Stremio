#!/usr/bin/env python3
"""
Test MyTF1 Provider Fix
Test that the MyTF1 provider now works correctly with the proxy fix
"""

import sys
import os
sys.path.append('.')

from app.providers.fr.mytf1 import MyTF1Provider
from app.utils.safe_print import safe_print

def test_mytf1_provider():
    """Test the fixed MyTF1 provider"""
    safe_print("🚀 Testing MyTF1 Provider Fix...")

    try:
        # Create provider instance
        provider = MyTF1Provider()
        safe_print("✅ MyTF1Provider created successfully")

        # Test authentication
        if provider._authenticate():
            safe_print("✅ Authentication successful")
        else:
            safe_print("❌ Authentication failed - this might be expected in test environment")
            return

        # Test live stream (should work with fix)
        safe_print("\n" + "="*50)
        safe_print("TESTING LIVE STREAM")
        safe_print("="*50)

        live_result = provider.get_channel_stream_url("cutam:fr:mytf1:tf1")
        if live_result:
            safe_print("✅ Live stream URL obtained successfully!")
            safe_print(f"   URL: {live_result['url'][:50]}...")
            safe_print(f"   Type: {live_result['manifest_type']}")
        else:
            safe_print("❌ Failed to get live stream URL")

        # Test replay stream (should work with fix)
        safe_print("\n" + "="*50)
        safe_print("TESTING REPLAY STREAM")
        safe_print("="*50)

        # Get episodes first
        episodes = provider.get_episodes("cutam:fr:mytf1:quotidien")
        if episodes and len(episodes) > 0:
            episode_id = episodes[0]['id']
            safe_print(f"✅ Got episodes, testing with: {episode_id}")

            replay_result = provider.get_episode_stream_url(episode_id)
            if replay_result:
                safe_print("✅ Replay stream URL obtained successfully!")
                safe_print(f"   URL: {replay_result['url'][:50]}...")
                safe_print(f"   Type: {replay_result['manifest_type']}")
            else:
                safe_print("❌ Failed to get replay stream URL")
        else:
            safe_print("❌ No episodes found to test")

        safe_print("\n" + "="*50)
        safe_print("TEST COMPLETE")
        safe_print("="*50)

    except Exception as e:
        safe_print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_mytf1_provider()
