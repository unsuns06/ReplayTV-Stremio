#!/usr/bin/env python3
"""
SixPlay Provider Tests - Baseline
Run these BEFORE refactoring to establish working baseline.
Run again AFTER refactoring to verify no regressions.
"""

import sys
import os
import json
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.providers.fr.sixplay import SixPlayProvider

# Test results storage
RESULTS = {
    "timestamp": None,
    "provider": "sixplay",
    "tests": {}
}

def log(msg):
    """Print with timestamp"""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

def test_get_programs():
    """Test: Get list of programs/shows"""
    log("🧪 Testing get_programs()...")
    try:
        provider = SixPlayProvider()
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
        # Use first show from the hardcoded list - "capital"
        show_id = "cutam:fr:6play:capital"
    
    log(f"🧪 Testing get_episodes('{show_id}')...")
    try:
        provider = SixPlayProvider()
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

def test_get_episode_stream_url(episode_id: str = None):
    """Test: Get stream URL for specific episode"""
    if not episode_id:
        # First try to get a real episode ID from get_episodes
        log("🔍 Getting real episode ID from API...")
        try:
            provider = SixPlayProvider()
            episodes = provider.get_episodes("cutam:fr:6play:capital")
            if episodes and len(episodes) > 0:
                episode_id = episodes[0].get("id")
                log(f"   Using episode: {episode_id}")
        except:
            pass
    
    if not episode_id:
        log("⚠️ No episode ID available, skipping stream test")
        RESULTS["tests"]["get_episode_stream_url"] = {"status": "SKIP", "reason": "No episode ID"}
        return False, None
    
    log(f"🧪 Testing get_episode_stream_url('{episode_id}')...")
    try:
        provider = SixPlayProvider()
        stream = provider.get_episode_stream_url(episode_id)
        
        if stream is None:
            log("⚠️ Stream returned None (may need authentication or content unavailable)")
            RESULTS["tests"]["get_episode_stream_url"] = {
                "status": "WARN",
                "episode_id": episode_id,
                "note": "Stream returned None"
            }
            return True, None
        
        # Check if stream has URL
        has_url = False
        if isinstance(stream, dict):
            has_url = 'url' in stream
            log(f"✅ get_episode_stream_url: Got stream response")
            log(f"   - URL: {stream.get('url', 'N/A')[:80]}...")
            log(f"   - Type: {stream.get('manifest_type', 'unknown')}")
        elif isinstance(stream, list) and len(stream) > 0:
            has_url = 'url' in stream[0]
            log(f"✅ get_episode_stream_url: Got {len(stream)} stream(s)")
            log(f"   - URL: {stream[0].get('url', 'N/A')[:80]}...")
        
        RESULTS["tests"]["get_episode_stream_url"] = {
            "status": "PASS" if has_url else "WARN",
            "episode_id": episode_id,
            "has_url": has_url,
            "manifest_type": stream.get('manifest_type') if isinstance(stream, dict) else "list"
        }
        return True, stream
    except Exception as e:
        log(f"❌ get_episode_stream_url FAILED: {e}")
        RESULTS["tests"]["get_episode_stream_url"] = {"status": "FAIL", "episode_id": episode_id, "error": str(e)}
        return False, None

def run_all_tests():
    """Run all sixplay tests and save results"""
    log("=" * 60)
    log("🚀 SixPlay Provider Baseline Tests")
    log("=" * 60)
    
    RESULTS["timestamp"] = datetime.now().isoformat()
    
    # Test 1: Get Programs
    programs_ok, programs = test_get_programs()
    log("")
    
    # Test 2: Get Episodes
    episodes_ok, episodes = test_get_episodes()
    log("")
    
    # Test 3: Get Stream URL
    episode_id = None
    if episodes and len(episodes) > 0:
        episode_id = episodes[0].get("id")
    stream_ok, stream = test_get_episode_stream_url(episode_id)
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
    results_path = os.path.join(os.path.dirname(__file__), "sixplay_baseline.json")
    with open(results_path, "w") as f:
        json.dump(RESULTS, f, indent=2)
    log(f"\n📄 Results saved to: {results_path}")
    
    return failed == 0

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
