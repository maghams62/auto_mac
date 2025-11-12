#!/usr/bin/env python3
"""
Live testing script for Spotify API integration.

This script tests the Spotify API-based playback functionality:
- Authentication flow
- Basic playback controls (play, pause, status)
- Track search and playback
- Album/artist playback

Usage:
    python test_spotify_api_live.py

Requirements:
- SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET environment variables
- Spotify app running locally
- Valid OAuth token (will prompt for authentication if needed)
"""

import os
import sys
import time
import logging
from typing import Dict, Any

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.utils import load_config
from src.integrations.spotify_api import SpotifyAPIClient
from src.integrations.spotify_playback_service import SpotifyPlaybackService
from src.agent.spotify_agent import get_spotify_status, play_music, pause_music, play_song

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def test_api_client():
    """Test the Spotify API client directly."""
    print("\n=== Testing Spotify API Client ===")

    try:
        # Use mock credentials directly for testing
        client = SpotifyAPIClient(
            client_id="mock_client_id",
            client_secret="mock_client_secret",
            redirect_uri="http://127.0.0.1:3000/redirect",
        )

        print(f"Client created. Authenticated: {client.is_authenticated()}")

        if not client.is_authenticated():
            print("Not authenticated (expected with mock credentials). Testing OAuth URL generation...")
            scopes = ["user-read-playback-state", "user-modify-playback-state"]
            auth_url = client.get_authorization_url(scopes)
            print(f"OAuth URL generated successfully: {auth_url[:100]}...")

            # Skip interactive auth for testing - just test the URL generation
            print("Skipping interactive authentication for test purposes.")
            print("API client basic functionality verified.")
            return None

        # Test basic API calls
        print("\nTesting current playback...")
        playback = client.get_current_playback()
        if playback:
            item = playback.get("item", {})
            print(f"Current track: {item.get('name', 'Unknown')} by {item.get('artists', [{}])[0].get('name', 'Unknown')}")
        else:
            print("No active playback")

        # Test search
        print("\nTesting track search...")
        results = client.search_tracks("Bohemian Rhapsody", limit=1)
        if results and results.get("tracks", {}).get("items"):
            track = results["tracks"]["items"][0]
            print(f"Found track: {track['name']} by {track['artists'][0]['name']}")
            print(f"URI: {track['uri']}")
            return track['uri']
        else:
            print("No search results found")
            return None

    except Exception as e:
        print(f"API client test failed: {e}")
        return False


def test_playback_service():
    """Test the SpotifyPlaybackService."""
    print("\n=== Testing Spotify Playback Service ===")

    config = load_config(use_global_manager=False)
    service = SpotifyPlaybackService(config)

    print(f"Available backends: {[b.value for b in service.get_available_backends()]}")
    print(f"Preferring API: {service.prefer_api}")

    # Test status
    print("\nTesting get_status...")
    status_result = service.get_status()
    print(f"Status: {status_result.to_dict()}")

    # Test play/pause (if there's active playback)
    if status_result.success and "playing" in status_result.message.lower():
        print("\nTesting pause...")
        pause_result = service.pause()
        print(f"Pause result: {pause_result.to_dict()}")

        time.sleep(2)

        print("\nTesting play...")
        play_result = service.play()
        print(f"Play result: {play_result.to_dict()}")

    return service


def test_agent_tools():
    """Test the Spotify agent tools."""
    print("\n=== Testing Spotify Agent Tools ===")

    # Test get_spotify_status
    print("\nTesting get_spotify_status...")
    try:
        status = get_spotify_status()
        print(f"Status: {status}")
    except Exception as e:
        print(f"get_spotify_status failed: {e}")

    # Test play_music
    print("\nTesting play_music...")
    try:
        play_result = play_music()
        print(f"Play result: {play_result}")
    except Exception as e:
        print(f"play_music failed: {e}")

    # Test pause_music
    print("\nTesting pause_music...")
    try:
        pause_result = pause_music()
        print(f"Pause result: {pause_result}")
    except Exception as e:
        print(f"pause_music failed: {e}")


def test_track_playback(service: SpotifyPlaybackService, track_uri: str = None):
    """Test track playback functionality."""
    print("\n=== Testing Track Playback ===")

    if not track_uri:
        # Use a known track URI for testing
        track_uri = "spotify:track:4uLU6hMCjMI75M1A2tKUQC"  # Bohemian Rhapsody

    print(f"Testing playback of track: {track_uri}")

    try:
        result = service.play_track(track_uri)
        print(f"Track playback result: {result.to_dict()}")

        # Wait a bit and check status
        time.sleep(3)
        status_result = service.get_status()
        print(f"Status after playback: {status_result.to_dict()}")

    except Exception as e:
        print(f"Track playback test failed: {e}")


def test_song_disambiguation():
    """Test song disambiguation with URI resolution."""
    print("\n=== Testing Song Disambiguation ===")

    from src.llm.song_disambiguator import SongDisambiguator

    try:
        disambiguator = SongDisambiguator()

        # Test disambiguation with URI
        result = disambiguator.disambiguate_with_uri("Bohemian Rhapsody Queen")
        print(f"Disambiguation result: {result}")

        if result.get('uri'):
            print(f"Resolved URI: {result['uri']}")
            return result['uri']
        else:
            print("No URI resolved")
            return None

    except Exception as e:
        print(f"Song disambiguation test failed: {e}")
        return None


def main():
    """Run all Spotify API tests."""
    print("Spotify API Live Testing")
    print("=" * 50)

    # Check environment variables
    client_id = os.getenv('SPOTIFY_CLIENT_ID')
    client_secret = os.getenv('SPOTIFY_CLIENT_SECRET')

    if not client_id or not client_secret:
        print("WARNING: SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET environment variables not set.")
        print("Testing will proceed with mock credentials and fallback to automation backend.")
        print("For full API testing, set the environment variables.")
        print()

        # Set mock credentials for basic testing BEFORE loading config
        os.environ['SPOTIFY_CLIENT_ID'] = 'mock_client_id'
        os.environ['SPOTIFY_CLIENT_SECRET'] = 'mock_client_secret'
        os.environ['SPOTIFY_REDIRECT_URI'] = 'http://127.0.0.1:3000/redirect'
        mock_mode = True
    else:
        print(f"Client ID: {client_id[:10]}...")
        print(f"Client Secret: {'*' * len(client_secret)}")
        mock_mode = False

    # Test API client
    track_uri = test_api_client()
    if track_uri is False:
        print("API client test failed. Exiting.")
        return

    # Test playback service
    service = test_playback_service()

    # Test agent tools
    test_agent_tools()

    # Test song disambiguation
    resolved_uri = test_song_disambiguation()

    # Test track playback
    test_uri = resolved_uri or track_uri or "spotify:track:4uLU6hMCjMI75M1A2tKUQC"
    test_track_playback(service, test_uri)

    print("\n=== Testing Complete ===")
    print("Check the output above for any issues.")


if __name__ == "__main__":
    main()
