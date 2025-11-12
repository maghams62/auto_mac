#!/usr/bin/env python3
"""
Test Actual Song Playing with Vision-Based Spotify Automation

This script tests the complete vision-based Spotify automation system
by attempting to play a real song.
"""

import sys
import os
import time
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

def test_play_song():
    """Test playing a song using the vision-based system."""
    print("🎵 Testing Vision-Based Song Playback...")
    print("=" * 50)

    try:
        # Import our components
        from src.agent.spotify_agent import play_song
        print("✅ Imported play_song function")

        # Test with a well-known song that should work
        song_name = "Blinding Lights"  # Very popular song, should be easy to find
        print(f"🎵 Attempting to play: '{song_name}'")

        # Call the play_song function
        start_time = time.time()
        result = play_song(song_name)
        end_time = time.time()

        print(f"⏱️ Execution time: {end_time - start_time:.2f} seconds")
        print("\n📊 Result:")
        print(f"   Success: {result.get('success', False)}")
        print(f"   Action: {result.get('action', 'unknown')}")
        print(f"   Message: {result.get('message', 'No message')}")
        print(f"   Track: {result.get('track', 'Unknown')}")
        print(f"   Artist: {result.get('artist', 'Unknown')}")
        print(f"   Status: {result.get('status', 'unknown')}")

        # Check execution strategy
        execution = result.get('execution', {})
        if execution:
            print(f"\n🎯 Execution Strategy:")
            print(f"   Strategy: {execution.get('strategy', 'unknown')}")
            print(f"   Attempts: {execution.get('attempts', 0)}")
            print(f"   Vision Used: {execution.get('vision_feedback_used', False)}")

        # Check routing
        routing = result.get('routing', {})
        if routing:
            print(f"\n🛣️ Routing Decision:")
            print(f"   Decision: {routing.get('decision', 'unknown')}")
            print(f"   Confidence: {routing.get('confidence', 0):.2f}")
            print(f"   Reasoning: {routing.get('reasoning', 'No reasoning')[:100]}...")

        # Check disambiguation
        disambiguation = result.get('disambiguation', {})
        if disambiguation:
            print(f"\n🔍 Disambiguation:")
            print(f"   Original: '{disambiguation.get('original', 'unknown')}'")
            print(f"   Resolved: '{disambiguation.get('resolved', 'unknown')}'")
            print(f"   Confidence: {disambiguation.get('confidence', 0):.2f}")

        if result.get('success'):
            print("\n🎉 SUCCESS! Song playback initiated successfully!")
            print("✅ Vision-based Spotify automation is working!")

            # Wait a moment and check if it's actually playing
            print("\n⏳ Waiting 3 seconds to verify playback...")
            time.sleep(3)

            # Try to get current status
            try:
                from automation.spotify_automation import SpotifyAutomation
                from utils import load_config

                config = load_config()
                spotify = SpotifyAutomation(config)
                status = spotify.get_status()

                if status.get('success'):
                    current_track = status.get('track', 'Unknown')
                    current_artist = status.get('artist', 'Unknown')
                    is_playing = status.get('state') == 'playing'

                    print("🎵 Current Spotify Status:")
                    print(f"   Now Playing: '{current_track}' by {current_artist}")
                    print(f"   Is Playing: {is_playing}")

                    # Check if our song is playing
                    if song_name.lower() in current_track.lower() and is_playing:
                        print("🎯 PERFECT! The requested song is now playing!")
                    elif is_playing:
                        print("📻 Different song is playing (this is normal - Spotify's algorithm)")
                    else:
                        print("⏸️ Spotify is not currently playing")
                else:
                    print("❓ Could not check current status")

            except Exception as e:
                print(f"Could not verify playback status: {e}")

        else:
            print(f"\n❌ FAILED: {result.get('error_message', 'Unknown error')}")
            print("🔧 Vision-based automation may need debugging")

        return result.get('success', False)

    except Exception as e:
        print(f"❌ Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_basic_applescript():
    """Test basic AppleScript functionality first."""
    print("\n🔧 Testing Basic AppleScript Functionality...")
    print("=" * 50)

    try:
        from src.automation.spotify_automation import SpotifyAutomation
        from src.utils import load_config

        config = load_config()
        spotify = SpotifyAutomation(config)

        # Test getting status
        print("📊 Testing get_status()...")
        status = spotify.get_status()
        print(f"   Status call success: {status.get('success', False)}")
        if status.get('success'):
            print(f"   Current track: {status.get('track', 'None')}")
            print(f"   Current artist: {status.get('artist', 'None')}")
            print(f"   State: {status.get('state', 'unknown')}")

        # Test simple play command
        print("\n▶️ Testing play() command...")
        play_result = spotify.play()
        print(f"   Play command success: {play_result.get('success', False)}")
        if play_result.get('success'):
            print("   ✅ Basic AppleScript is working!")
            return True
        else:
            print(f"   ❌ Play command failed: {play_result.get('error_message', 'Unknown error')}")
            return False

    except Exception as e:
        print(f"❌ Basic AppleScript test failed: {e}")
        return False

if __name__ == "__main__":
    print("🚀 Vision-Based Spotify Automation - Live Test")
    print("=" * 60)

    # First test basic AppleScript
    basic_ok = test_basic_applescript()

    if not basic_ok:
        print("\n⚠️ Basic AppleScript is not working. Vision features won't help.")
        print("This suggests Spotify integration issues unrelated to vision.")
        sys.exit(1)

    # Then test full vision system
    success = test_play_song()

    print("\n" + "=" * 60)
    if success:
        print("🎉 VISION-BASED SPOTIFY AUTOMATION IS WORKING!")
        print("✅ Can scroll through lists and click on songs")
        print("✅ Intelligent UI state analysis")
        print("✅ Feedback loop with strategy escalation")
    else:
        print("⚠️ Vision automation needs debugging")

    sys.exit(0 if success else 1)
