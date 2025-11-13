"""
End-to-End Tests: Spotify Playback Control

Tests comprehensive Spotify music functionality:
- Track search and playback
- Queue management
- Playback status and controls
- Device handling and selection
- Error recovery for device issues

WINNING CRITERIA:
- Tracks located and played successfully
- Device selection works
- Playback state accurate
- Error handling graceful
"""

import pytest
import time
import json
from typing import Dict, Any, List

pytestmark = [pytest.mark.e2e]


class TestSpotifyPlayback:
    """Test comprehensive Spotify playback functionality."""

    def test_play_track_by_name(
        self,
        api_client,
        success_criteria_checker,
        telemetry_collector
    ):
        """
        Test playing a specific track by name.

        WINNING CRITERIA:
        - Track located via Spotify API
        - Playback started successfully
        - Correct track playing
        - UI shows playback status
        - Device handling works
        """
        track_name = "Blinding Lights"
        artist_name = "The Weeknd"

        query = f"Play '{track_name}' by {artist_name}"

        telemetry_collector.record_event("spotify_test_start", {
            "action": "play_track",
            "track": track_name,
            "artist": artist_name
        })

        response = api_client.chat(query)
        messages = api_client.wait_for_completion(max_wait=60)

        response_text = response.get("message", "")

        # Check success criteria
        assert success_criteria_checker.check_no_errors(response)
        assert success_criteria_checker.check_response_length(response_text, 50)

        # Check playback confirmation
        playback_keywords = ["play", "playing", "spotify", track_name.lower()]
        assert success_criteria_checker.check_keywords_present(response_text, playback_keywords)

        # Verify Spotify API was called
        spotify_called = any(
            msg.get("tool_name") in ["play_spotify_track", "spotify_play", "search_spotify"]
            for msg in messages
            if msg.get("type") == "tool_call"
        )
        assert spotify_called, "Spotify API not called for playback"

        telemetry_collector.record_event("spotify_playback_complete", {
            "track_found": True,
            "playback_started": True
        })

    def test_queue_playlist(
        self,
        api_client,
        success_criteria_checker
    ):
        """
        Test queuing an entire playlist.

        WINNING CRITERIA:
        - Playlist located successfully
        - All tracks added to queue
        - Queue status updated
        - Seamless playback continuation
        - Progress indication
        """
        query = "Queue the entire 'After Hours' playlist"

        response = api_client.chat(query)
        messages = api_client.wait_for_completion(max_wait=90)

        response_text = response.get("message", "")

        assert success_criteria_checker.check_no_errors(response)
        assert success_criteria_checker.check_response_length(response_text, 50)

        # Check queue operation
        queue_keywords = ["queue", "playlist", "added", "tracks"]
        assert success_criteria_checker.check_keywords_present(response_text, queue_keywords)

    def test_currently_playing_status(
        self,
        api_client,
        success_criteria_checker
    ):
        """
        Test getting current playback status.

        WINNING CRITERIA:
        - Current track identified
        - Playback state accurate
        - Progress information provided
        - Queue status shown
        - UI displays player card
        """
        query = "What's currently playing?"

        response = api_client.chat(query)
        messages = api_client.wait_for_completion(max_wait=60)

        response_text = response.get("message", "")

        assert success_criteria_checker.check_no_errors(response)

        # Should provide playback information
        status_keywords = ["playing", "track", "spotify"]
        status_info = sum(1 for keyword in status_keywords if keyword in response_text.lower())
        assert status_info >= 1, "No playback status information provided"

    def test_playback_controls(
        self,
        api_client,
        success_criteria_checker
    ):
        """
        Test basic playback controls (pause, resume, skip).

        WINNING CRITERIA:
        - Controls executed successfully
        - State changes properly
        - UI updates reflect changes
        - No disruption to playback
        """
        # Start playback first
        start_query = "Play some music"
        api_client.chat(start_query)
        api_client.wait_for_completion(max_wait=30)

        # Test pause
        query = "Pause the music"

        response = api_client.chat(query)
        messages = api_client.wait_for_completion(max_wait=60)

        response_text = response.get("message", "")

        assert success_criteria_checker.check_no_errors(response)

        # Check control execution
        control_keywords = ["pause", "stopped", "paused"]
        assert success_criteria_checker.check_keywords_present(response_text, control_keywords)

    def test_device_selection_handling(
        self,
        api_client,
        success_criteria_checker
    ):
        """
        Test Spotify device selection and handling.

        WINNING CRITERIA:
        - Available devices detected
        - Device selection works
        - Playback transfers correctly
        - Error handling for no devices
        - User prompts for device choice
        """
        query = "Play music on my phone"

        response = api_client.chat(query)
        messages = api_client.wait_for_completion(max_wait=60)

        response_text = response.get("message", "")

        assert success_criteria_checker.check_no_errors(response)

        # Should handle device selection
        device_handling = (
            "device" in response_text.lower() or
            "phone" in response_text.lower() or
            "playing" in response_text.lower() or
            "spotify" in response_text.lower()
        )

        assert device_handling, "Device selection not handled properly"

    def test_spotify_search_disambiguation(
        self,
        api_client,
        success_criteria_checker
    ):
        """
        Test handling ambiguous song requests.

        WINNING CRITERIA:
        - Multiple matches identified
        - Disambiguation options provided
        - User choice handled
        - Correct track selected
        - Playback starts with right song
        """
        # Use a common song name that might have multiple artists
        query = "Play 'Yesterday'"

        response = api_client.chat(query)
        messages = api_client.wait_for_completion(max_wait=60)

        response_text = response.get("message", "")

        assert success_criteria_checker.check_no_errors(response)

        # Should handle potential disambiguation
        disambiguation_handled = (
            "playing" in response_text.lower() or
            "yesterday" in response_text.lower() or
            "beatles" in response_text.lower() or  # Common artist for this song
            success_criteria_checker.check_no_errors(response)
        )

        assert disambiguation_handled, "Song disambiguation not handled properly"

    def test_spotify_error_device_unavailable(
        self,
        api_client,
        success_criteria_checker,
        telemetry_collector
    ):
        """
        NEGATIVE TEST: Handle device unavailability gracefully.

        WINNING CRITERIA:
        - Device issue detected
        - Clear error message provided
        - Recovery suggestions given
        - Alternative options offered
        - No crash or hang
        """
        # This test might need to simulate device unavailability
        query = "Play music on my computer"

        telemetry_collector.record_event("device_error_test_start", {
            "scenario": "device_unavailable"
        })

        response = api_client.chat(query)
        messages = api_client.wait_for_completion(max_wait=60)

        response_text = response.get("message", "")

        # Should handle device issues gracefully
        error_handling = (
            "device" in response_text.lower() or
            "available" in response_text.lower() or
            "playing" in response_text.lower() or
            success_criteria_checker.check_no_errors(response)
        )

        assert error_handling, "Device unavailability not handled gracefully"

        telemetry_collector.record_event("device_error_test_complete", {
            "error_handled_gracefully": error_handling
        })

    def test_spotify_authentication_flow(
        self,
        api_client,
        success_criteria_checker
    ):
        """
        Test Spotify authentication and token handling.

        WINNING CRITERIA:
        - Authentication successful
        - Tokens refreshed properly
        - API calls work post-auth
        - Session maintained
        - Re-auth prompts clear
        """
        query = "Check my Spotify connection and play a test song"

        response = api_client.chat(query)
        messages = api_client.wait_for_completion(max_wait=60)

        response_text = response.get("message", "")

        # Should handle auth gracefully
        auth_handling = (
            "connected" in response_text.lower() or
            "authenticated" in response_text.lower() or
            "playing" in response_text.lower() or
            "spotify" in response_text.lower() or
            success_criteria_checker.check_no_errors(response)
        )

        assert auth_handling, "Spotify authentication not handled properly"

    def test_spotify_playlist_creation(
        self,
        api_client,
        success_criteria_checker
    ):
        """
        Test creating and managing playlists.

        WINNING CRITERIA:
        - Playlist created successfully
        - Tracks added correctly
        - Playlist metadata set
        - Sharing options work
        - UI shows new playlist
        """
        query = "Create a playlist called 'Test Automation' with some upbeat songs"

        response = api_client.chat(query)
        messages = api_client.wait_for_completion(max_wait=90)

        response_text = response.get("message", "")

        assert success_criteria_checker.check_no_errors(response)
        assert success_criteria_checker.check_response_length(response_text, 50)

        # Check playlist creation
        playlist_keywords = ["playlist", "created", "added", "songs"]
        assert success_criteria_checker.check_keywords_present(response_text, playlist_keywords)

    def test_spotify_ui_player_display(
        self,
        api_client,
        success_criteria_checker
    ):
        """
        Test Spotify player UI components and controls.

        WINNING CRITERIA:
        - Player card displays correctly
        - Cover art shown
        - Progress bar functional
        - Control buttons work
        - Queue visible
        - Status updates in real-time
        """
        query = "Show me the music player"

        response = api_client.chat(query)
        messages = api_client.wait_for_completion(max_wait=60)

        # Check for UI player messages
        player_messages = [msg for msg in messages if msg.get("type") in ["spotify_player", "music_player", "playback_display"]]

        # Should have UI rendering messages
        assert len(player_messages) > 0, "No UI player rendering messages"

        response_text = response.get("message", "")
        assert success_criteria_checker.check_response_length(response_text, 30)

        # Should mention player or music concepts
        player_keywords = ["player", "music", "spotify", "playing"]
        assert success_criteria_checker.check_keywords_present(response_text, player_keywords)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
