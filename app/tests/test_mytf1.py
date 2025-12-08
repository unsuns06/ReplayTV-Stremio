#!/usr/bin/env python3
"""
MyTF1 Provider Tests - Baseline
Run these BEFORE refactoring to establish working baseline.
Run again AFTER refactoring to verify no regressions.
"""

import sys
import os
import json
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.providers.fr.mytf1 import MyTF1Provider

# Test results storage
RESULTS = {
    "timestamp": None,
    "provider": "mytf1",
    "tests": {}
}

def log(msg):
    """Print with timestamp"""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

def test_get_live_channels():
    """Test: Get list of live channels"""
    log("🧪 Testing get_live_channels()...")
    try:
        provider = MyTF1Provider()
        channels = provider.get_live_channels()
        
        assert channels is not None, "channels should not be None"
        assert isinstance(channels, list), "channels should be a list"
        assert len(channels) > 0, "channels should have at least one channel"
        
        # Check first channel has required fields
        first = channels[0]
        assert 'id' in first, "channel should have id"
        assert 'name' in first, "channel should have name"
        
        log(f"✅ get_live_channels: Found {len(channels)} channels")
        for c in channels:
            log(f"   - {c.get('name', 'Unknown')} ({c.get('id', 'no-id')})")
        
        RESULTS["tests"]["get_live_channels"] = {
            "status": "PASS",
            "count": len(channels),
            "channels": [{"id": c.get("id"), "name": c.get("name")} for c in channels]
        }
        return True, channels
    except Exception as e:
        log(f"❌ get_live_channels FAILED: {e}")
        RESULTS["tests"]["get_live_channels"] = {"status": "FAIL", "error": str(e)}
        return False, None

def test_get_programs():
    """Test: Get list of programs/shows"""
    log("🧪 Testing get_programs()...")
    try:
        provider = MyTF1Provider()
        programs = provider.get_programs()
        
        assert programs is not None, "programs should not be None"
        assert isinstance(programs, list), "programs should be a list"
        assert len(programs) > 0, "programs should have at least one show"
        
        # Check first program has required fields
        first = programs[0]
        assert 'id' in first, "program should have id"
        assert 'name' in first, "program should have name"
        
        log(f"✅ get_programs: Found {len(programs)} programs")
        for p in programs:
            log(f"   - {p.get('name', 'Unknown')} ({p.get('id', 'no-id')})")
        
        RESULTS["tests"]["get_programs"] = {
            "status": "PASS",
            "count": len(programs),
            "programs": [{"id": p.get("id"), "name": p.get("name")} for p in programs]
        }
        return True, programs
    except Exception as e:
        log(f"❌ get_programs FAILED: {e}")
        RESULTS["tests"]["get_programs"] = {"status": "FAIL", "error": str(e)}
        return False, None

def test_get_episodes(show_id: str = None):
    """Test: Get episodes for a specific show"""
    if not show_id:
        # Use first show - "sept-a-huit"
        show_id = "cutam:fr:mytf1:sept-a-huit"
    
    log(f"🧪 Testing get_episodes('{show_id}')...")
    try:
        provider = MyTF1Provider()
        episodes = provider.get_episodes(show_id)
        
        assert episodes is not None, "episodes should not be None"
        assert isinstance(episodes, list), "episodes should be a list"
        
        log(f"✅ get_episodes: Found {len(episodes)} episodes")
        
        # Log first 3 episodes
        for ep in episodes[:3]:
            log(f"   - {ep.get('title', ep.get('name', 'Unknown'))} (ID: {ep.get('id', 'no-id')})")
        
        RESULTS["tests"]["get_episodes"] = {
            "status": "PASS",
            "show_id": show_id,
            "count": len(episodes),
            "sample_episodes": [{"id": e.get("id"), "title": e.get("title", e.get("name"))} for e in episodes[:5]]
        }
        return True, episodes
    except Exception as e:
        log(f"❌ get_episodes FAILED: {e}")
        RESULTS["tests"]["get_episodes"] = {"status": "FAIL", "show_id": show_id, "error": str(e)}
        return False, None

def test_get_channel_stream_url(channel_id: str = None):
    """Test: Get stream URL for a live channel"""
    if not channel_id:
        # Use TF1 channel
        channel_id = "cutam:fr:mytf1:tf1"
    
    log(f"🧪 Testing get_channel_stream_url('{channel_id}')...")
    try:
        provider = MyTF1Provider()
        stream = provider.get_channel_stream_url(channel_id)
        
        if stream is None:
            log("⚠️ Stream returned None (may need auth or geo-block)")
            RESULTS["tests"]["get_channel_stream_url"] = {
                "status": "WARN",
                "channel_id": channel_id,
                "note": "Stream returned None"
            }
            return True, None
        
        has_url = 'url' in stream
        log(f"✅ get_channel_stream_url: Got stream response")
        log(f"   - URL: {stream.get('url', 'N/A')[:80]}...")
        log(f"   - Type: {stream.get('manifest_type', 'unknown')}")
        
        RESULTS["tests"]["get_channel_stream_url"] = {
            "status": "PASS" if has_url else "WARN",
            "channel_id": channel_id,
            "has_url": has_url,
            "manifest_type": stream.get('manifest_type', 'unknown')
        }
        return True, stream
    except Exception as e:
        log(f"❌ get_channel_stream_url FAILED: {e}")
        RESULTS["tests"]["get_channel_stream_url"] = {"status": "FAIL", "channel_id": channel_id, "error": str(e)}
        return False, None

def run_all_tests():
    """Run all mytf1 tests and save results"""
    log("=" * 60)
    log("🚀 MyTF1 Provider Baseline Tests")
    log("=" * 60)
    
    RESULTS["timestamp"] = datetime.now().isoformat()
    
    # Test 1: Get Live Channels
    channels_ok, channels = test_get_live_channels()
    log("")
    
    # Test 2: Get Programs
    programs_ok, programs = test_get_programs()
    log("")
    
    # Test 3: Get Episodes
    episodes_ok, episodes = test_get_episodes()
    log("")
    
    # Test 4: Get Channel Stream URL
    stream_ok, stream = test_get_channel_stream_url()
    log("")
    
    # Summary
    log("=" * 60)
    log("📊 Test Summary")
    log("=" * 60)
    
    passed = sum(1 for t in RESULTS["tests"].values() if t["status"] == "PASS")
    warned = sum(1 for t in RESULTS["tests"].values() if t["status"] == "WARN")
    failed = sum(1 for t in RESULTS["tests"].values() if t["status"] == "FAIL")
    
    log(f"   ✅ Passed: {passed}")
    log(f"   ⚠️ Warnings: {warned}")
    log(f"   ❌ Failed: {failed}")
    
    # Save results
    results_path = os.path.join(os.path.dirname(__file__), "mytf1_baseline.json")
    with open(results_path, "w") as f:
        json.dump(RESULTS, f, indent=2)
    log(f"\n📄 Results saved to: {results_path}")
    
    return failed == 0

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
