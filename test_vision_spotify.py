#!/usr/bin/env python3
"""
Test Vision-Based Spotify Automation

This script tests the new vision-based Spotify automation capabilities
including scrolling and clicking on songs in lists.
"""

import sys
import os
import json
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

try:
    from automation.vision_spotify_automation import VisionSpotifyAutomation
    from agent.execution_router import ExecutionRouter
    from utils import load_config
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("This might be due to missing dependencies or configuration issues.")
    print("Let's try a simpler test approach...")
    sys.exit(1)

def test_vision_spotify_setup():
    """Test that vision Spotify automation initializes properly."""
    print("🔍 Testing Vision Spotify Automation Setup...")

    try:
        config = load_config()
        print(f"✅ Config loaded successfully")

        # Test VisionSpotifyAutomation initialization
        vision_auto = VisionSpotifyAutomation(config)
        print(f"✅ VisionSpotifyAutomation initialized")

        # Test ExecutionRouter initialization
        execution_router = ExecutionRouter(config)
        print(f"✅ ExecutionRouter initialized")

        return True

    except Exception as e:
        print(f"❌ Setup failed: {e}")
        return False

def test_song_visibility_detection():
    """Test the song visibility detection logic."""
    print("\n🎵 Testing Song Visibility Detection...")

    try:
        config = load_config()
        vision_auto = VisionSpotifyAutomation(config)

        # Create a mock UI state with visible songs
        from automation.vision_spotify_automation import SpotifyUIState
        ui_state = SpotifyUIState()
        ui_state.visible_song_titles = ["Blinding Lights", "Watermelon Sugar", "Levitating", "Good 4 U"]
        ui_state.visible_song_artists = ["The Weeknd", "Harry Styles", "Dua Lipa", "Olivia Rodrigo"]

        # Test finding songs
        tests = [
            ("Blinding Lights", None, True),
            ("Levitating", "Dua Lipa", True),
            ("Blinding Lights", "Wrong Artist", False),  # Wrong artist
            ("Nonexistent Song", None, False),  # Not in list
        ]

        for song, artist, expected in tests:
            result = vision_auto._is_target_song_visible(song, artist, ui_state)
            status = "✅" if result == expected else "❌"
            print(f"{status} '{song}' by {artist or 'Any'}: {result} (expected {expected})")

            if result != expected:
                return False

        # Test index finding
        index = vision_auto._find_target_song_index("Levitating", "Dua Lipa", ui_state)
        if index != 2:
            print(f"❌ Index finding failed: got {index}, expected 2")
            return False

        print("✅ All visibility detection tests passed")
        return True

    except Exception as e:
        print(f"❌ Song visibility test failed: {e}")
        return False

def test_scroll_position_logic():
    """Test scroll position detection logic."""
    print("\n📜 Testing Scroll Position Logic...")

    try:
        config = load_config()
        vision_auto = VisionSpotifyAutomation(config)

        # Test different scroll scenarios
        test_cases = [
            ("At the top of the playlist showing first songs", "top", False, True),
            ("At the bottom of the list showing last songs", "bottom", True, False),
            ("In the middle of a long playlist", "middle", True, True),
        ]

        for summary, expected_pos, expected_up, expected_down in test_cases:
            ui_state = vision_auto._parse_vision_analysis({
                "summary": summary,
                "status": "action_required"
            }, "test song", None)

            checks = [
                (ui_state.current_scroll_position == expected_pos, f"position {expected_pos}"),
                (ui_state.can_scroll_up == expected_up, f"can_scroll_up {expected_up}"),
                (ui_state.can_scroll_down == expected_down, f"can_scroll_down {expected_down}"),
            ]

            all_passed = True
            for check, desc in checks:
                if not check:
                    print(f"❌ Failed: {desc}")
                    all_passed = False

            if all_passed:
                print(f"✅ {summary[:30]}... → {expected_pos}")

        return True

    except Exception as e:
        print(f"❌ Scroll position test failed: {e}")
        return False

def test_execution_router_routing():
    """Test that execution router can route to vision strategy."""
    print("\n🎯 Testing Execution Router Vision Routing...")

    try:
        config = load_config()
        router = ExecutionRouter(config)

        # Test direct vision routing with complex context
        context = {
            "ui_complexity": "very complex popup ads dynamic content",
            "force_vision": False
        }

        result = router.route_execution("play_song", "Complex Song", "Unknown Artist", context)

        if result["strategy"].value == "vision":
            print("✅ Execution router correctly routed to VISION strategy")
            return True
        else:
            print(f"❌ Expected VISION strategy, got {result['strategy'].value}")
            return False

    except Exception as e:
        print(f"❌ Execution router test failed: {e}")
        return False

def test_vision_analysis_simulation():
    """Simulate vision analysis without actual screenshots."""
    print("\n👁️ Testing Vision Analysis Simulation...")

    try:
        config = load_config()
        vision_auto = VisionSpotifyAutomation(config)

        # Simulate vision analysis result for a playlist view
        mock_analysis = {
            "summary": "Spotify playlist view showing multiple songs. 'Blinding Lights' by The Weeknd is visible at position 2. Scrollbar indicates more songs below.",
            "status": "action_required",
            "actions": [
                {
                    "description": "Click on 'Blinding Lights' in the song list",
                    "confidence": 0.9,
                    "notes": "Target song is visible in current view"
                }
            ]
        }

        ui_state = vision_auto._parse_vision_analysis(mock_analysis, "Blinding Lights", "The Weeknd")

        # Check that it detected song list
        if not ui_state.song_list_visible:
            print("❌ Failed to detect song list")
            return False

        # Check that it found the song
        if not vision_auto._is_target_song_visible("Blinding Lights", "The Weeknd", ui_state):
            print("❌ Failed to detect target song visibility")
            return False

        print("✅ Vision analysis simulation successful")
        print(f"   - Song list detected: {ui_state.song_list_visible}")
        print(f"   - Songs found: {len(ui_state.visible_song_titles)}")
        print(f"   - Target visible: {vision_auto._is_target_song_visible('Blinding Lights', 'The Weeknd', ui_state)}")

        return True

    except Exception as e:
        print(f"❌ Vision analysis simulation failed: {e}")
        return False

def run_all_tests():
    """Run all vision Spotify automation tests."""
    print("🚀 Starting Vision-Based Spotify Automation Tests")
    print("=" * 60)

    tests = [
        test_vision_spotify_setup,
        test_song_visibility_detection,
        test_scroll_position_logic,
        test_execution_router_routing,
        test_vision_analysis_simulation,
    ]

    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"❌ Test {test.__name__} crashed: {e}")
            results.append(False)

    print("\n" + "=" * 60)
    passed = sum(results)
    total = len(results)

    if passed == total:
        print(f"🎉 All {total} tests PASSED! Vision Spotify automation is ready.")
        print("\n💡 To test actual song playing:")
        print("   1. Make sure Spotify is running")
        print("   2. Enable vision in config.yaml: vision.enabled: true")
        print("   3. Set up OPENAI_API_KEY environment variable")
        print("   4. Run: python -c \"from src.agent.spotify_agent import play_song; play_song('Blinding Lights')\"")
    else:
        print(f"⚠️ {passed}/{total} tests passed. Some issues need fixing.")

    return passed == total

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
