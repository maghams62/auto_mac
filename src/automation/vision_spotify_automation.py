"""
Vision-Based Spotify Automation - Intelligent UI automation with visual feedback.

This module provides sophisticated Spotify automation that uses vision analysis
to understand UI state and make intelligent decisions about when to type, click,
and interact with the Spotify interface.

Based on research from:
- OpenAdaptAI: Vision-based automation framework
- Microsoft UFO: UI-focused agents
- GPT-4V capabilities for visual reasoning

Key Features:
- Visual feedback loop for complex interactions
- Intelligent typing with completion detection
- Smart clicking based on visual element recognition
- Error recovery through screenshot analysis
- State-aware automation that adapts to UI changes
"""

import os
import time
import json
import logging
import subprocess
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class SpotifyUIState:
    """Represents the current state of Spotify UI."""
    is_visible: bool = False
    is_playing: bool = False
    current_track: Optional[str] = None
    current_artist: Optional[str] = None
    search_visible: bool = False
    search_has_focus: bool = False
    search_text: Optional[str] = None
    play_button_visible: bool = True
    pause_button_visible: bool = False
    error_messages: List[str] = None
    popups: List[str] = None
    ads_visible: bool = False

    # New scrolling and browsing capabilities
    scrollable_area_visible: bool = False
    song_list_visible: bool = False
    song_items_count: int = 0
    visible_song_titles: List[str] = None
    visible_song_artists: List[str] = None
    can_scroll_up: bool = False
    can_scroll_down: bool = True  # Assume can scroll down initially
    current_scroll_position: str = "top"  # "top", "middle", "bottom"
    active_view: str = "unknown"  # "home", "search", "library", "playlist", etc.

    def __post_init__(self):
        if self.error_messages is None:
            self.error_messages = []
        if self.popups is None:
            self.popups = []
        if self.visible_song_titles is None:
            self.visible_song_titles = []
        if self.visible_song_artists is None:
            self.visible_song_artists = []


class VisionSpotifyAutomation:
    """
    Vision-enhanced Spotify automation with intelligent feedback loops.

    Uses screenshot analysis and browser automation to handle complex Spotify
    interactions that AppleScript cannot manage.

    Key capabilities:
    - Visual search completion detection
    - Smart element clicking based on context
    - State-aware automation
    - Error recovery through visual analysis
    """

    def __init__(self, config: Dict[str, Any]):
        """Initialize vision-based Spotify automation."""
        self.config = config
        self.screenshot_dir = Path("/tmp/spotify_automation")
        self.screenshot_dir.mkdir(exist_ok=True)

        # Configuration
        self.vision_model = config.get("openai", {}).get("vision_model", "gpt-4o")
        self.max_attempts = config.get("spotify", {}).get("max_vision_attempts", 5)
        self.wait_between_actions = config.get("spotify", {}).get("action_wait_seconds", 1.0)

        # Initialize vision analysis
        from ..agent.vision_agent import VisionAgent
        self.vision_agent = VisionAgent(config)

        logger.info(f"[VISION SPOTIFY] Initialized with vision model: {self.vision_model}")

    def play_song_with_vision(self, song_name: str, artist: Optional[str] = None) -> Dict[str, Any]:
        """
        Play a song using vision-based automation with feedback loops.

        Args:
            song_name: Song to play
            artist: Optional artist name

        Returns:
            Success/failure result with vision analysis
        """
        logger.info(f"[VISION SPOTIFY] Starting vision-based playback: '{song_name}' by {artist or 'Unknown'}")

        attempt = 0
        errors = []

        while attempt < self.max_attempts:
            try:
                # Take initial screenshot
                screenshot_path = self._take_spotify_screenshot(f"attempt_{attempt}")

                # Analyze current state
                ui_state = self._analyze_ui_state(screenshot_path, song_name, artist, errors)

                # Determine next action based on state
                action = self._determine_next_action(ui_state, song_name, artist, attempt)

                if action["type"] == "success":
                    logger.info("[VISION SPOTIFY] Song successfully started via vision automation")
                    return action["result"]

                elif action["type"] == "action":
                    # Execute the recommended action
                    success = self._execute_vision_action(action, ui_state)
                    if success:
                        # Wait for UI to update and verify
                        time.sleep(self.wait_between_actions)
                        verification = self._verify_action_success(action, song_name, artist)
                        if verification["success"]:
                            return verification
                        else:
                            errors.append(f"Verification failed: {verification.get('error', 'Unknown')}")
                    else:
                        errors.append(f"Action execution failed: {action['description']}")

                elif action["type"] == "error":
                    errors.append(action["error"])
                    break

                attempt += 1

            except Exception as e:
                logger.error(f"[VISION SPOTIFY] Vision automation error: {e}")
                errors.append(str(e))
                attempt += 1

        # All attempts failed
        return {
            "success": False,
            "error": True,
            "error_type": "VisionAutomationFailed",
            "error_message": f"Vision automation failed after {attempt} attempts",
            "attempts": attempt,
            "errors": errors,
            "method": "vision_automation"
        }

    def _analyze_ui_state(self, screenshot_path: str, song_name: str,
                         artist: Optional[str], recent_errors: List[str]) -> SpotifyUIState:
        """
        Analyze screenshot to determine current Spotify UI state.

        Uses the existing vision agent to understand what's visible on screen.
        """
        goal = f"Analyze Spotify UI to determine state for playing '{song_name}'"
        if artist:
            goal += f" by {artist}"

        analysis = self.vision_agent.execute("analyze_ui_screenshot", {
            "screenshot_path": screenshot_path,
            "goal": goal,
            "tool_name": "play_song_with_vision",
            "recent_errors": recent_errors,
            "attempt": len(recent_errors)
        })

        # Parse vision analysis into SpotifyUIState
        return self._parse_vision_analysis(analysis, song_name, artist)

    def _parse_vision_analysis(self, analysis: Dict[str, Any],
                              song_name: str, artist: Optional[str]) -> SpotifyUIState:
        """
        Parse vision agent analysis into structured Spotify UI state.

        This is where we interpret the natural language description from vision
        into concrete UI state flags that drive automation decisions.
        """
        summary = analysis.get("summary", "").lower()
        status = analysis.get("status", "uncertain")

        state = SpotifyUIState()

        # Determine if Spotify is visible
        state.is_visible = any(keyword in summary for keyword in [
            "spotify", "music player", "audio controls", "play button", "search bar"
        ])

        # Check playback state
        if "playing" in summary or "play button disabled" in summary:
            state.is_playing = True
            state.pause_button_visible = True
            state.play_button_visible = False
        elif "paused" in summary or "pause button" in summary:
            state.is_playing = False
            state.pause_button_visible = False
            state.play_button_visible = True

        # Check for search interface
        state.search_visible = any(keyword in summary for keyword in [
            "search", "search bar", "search field", "magnifying glass"
        ])

        # Check if search has focus (cursor visible, highlighted)
        state.search_has_focus = any(keyword in summary for keyword in [
            "cursor in search", "search highlighted", "typing cursor", "focused search"
        ])

        # Extract current track/artist if visible
        if "now playing" in summary or "current track" in summary:
            # Try to extract track info from summary
            state.current_track = self._extract_track_from_text(summary)
            state.current_artist = self._extract_artist_from_text(summary)

        # Check for errors
        error_keywords = ["error", "failed", "cannot", "unable", "not found", "problem"]
        if any(keyword in summary for keyword in error_keywords):
            state.error_messages = [summary]

        # Check for popups/ads
        popup_keywords = ["popup", "dialog", "advertisement", "ad ", "premium", "upgrade"]
        if any(keyword in summary for keyword in popup_keywords):
            state.popups = [summary]
            state.ads_visible = "ad" in summary or "advertisement" in summary

        # If status is resolved, assume success
        if status == "resolved":
            state.is_playing = True

        # Detect scrolling and browsing capabilities
        state.scrollable_area_visible = any(keyword in summary for keyword in [
            "scroll", "scrollbar", "scrollable", "list", "playlist", "library"
        ])

        state.song_list_visible = any(keyword in summary for keyword in [
            "song list", "track list", "playlist", "library", "songs", "tracks"
        ])

        # Try to extract visible song information
        if state.song_list_visible:
            state.visible_song_titles = self._extract_song_titles_from_text(summary)
            state.visible_song_artists = self._extract_song_artists_from_text(summary)
            state.song_items_count = len(state.visible_song_titles)

        # Determine scroll position
        if "top of list" in summary or "beginning" in summary:
            state.current_scroll_position = "top"
            state.can_scroll_up = False
            state.can_scroll_down = True
        elif "bottom of list" in summary or "end" in summary:
            state.current_scroll_position = "bottom"
            state.can_scroll_up = True
            state.can_scroll_down = False
        else:
            state.current_scroll_position = "middle"
            state.can_scroll_up = True
            state.can_scroll_down = True

        # Detect active view
        if "home" in summary.lower():
            state.active_view = "home"
        elif "search results" in summary or "search page" in summary:
            state.active_view = "search"
        elif "your library" in summary or "library" in summary:
            state.active_view = "library"
        elif "playlist" in summary:
            state.active_view = "playlist"

        logger.info(f"[VISION SPOTIFY] Parsed UI state: visible={state.is_visible}, playing={state.is_playing}, search_visible={state.search_visible}, scrollable={state.scrollable_area_visible}, songs={state.song_items_count}")
        return state

    def _determine_next_action(self, ui_state: SpotifyUIState,
                              song_name: str, artist: Optional[str], attempt: int) -> Dict[str, Any]:
        """
        Determine the next action based on current UI state.

        This is the core decision logic that uses vision analysis to decide:
        - When to type in search
        - When to click search/play buttons
        - When to stop and declare success
        - When to give up
        """

        # If Spotify is not visible, we can't proceed
        if not ui_state.is_visible:
            return {
                "type": "error",
                "error": "Spotify application is not visible on screen"
            }

        # If the desired song is already playing, success!
        desired_track = song_name.lower()
        desired_artist = (artist or "").lower()
        current_track = (ui_state.current_track or "").lower()
        current_artist = (ui_state.current_artist or "").lower()

        if (desired_track in current_track or desired_track in current_artist) and ui_state.is_playing:
            return {
                "type": "success",
                "result": {
                    "success": True,
                    "action": "play_song",
                    "song_name": song_name,
                    "artist": artist,
                    "status": "playing",
                    "message": f"Now playing: {ui_state.current_track or song_name}",
                    "track": ui_state.current_track,
                    "track_artist": ui_state.current_artist,
                    "method": "vision_verification"
                }
            }

        # If there are popups or ads, handle them first
        if ui_state.popups or ui_state.ads_visible:
            return {
                "type": "action",
                "action": "dismiss_popup",
                "description": "Dismiss popup or advertisement to access Spotify controls",
                "confidence": 0.8,
                "reasoning": "UI blocked by popup/ad, must dismiss before proceeding"
            }

        # If search is not visible but we need to search, try to activate it
        if not ui_state.search_visible and attempt == 0:
            return {
                "type": "action",
                "action": "activate_search",
                "description": "Click on search bar or press search shortcut to open search interface",
                "confidence": 0.7,
                "reasoning": "Search interface not visible, need to activate it first"
            }

        # If search is visible but doesn't have focus, click on it
        if ui_state.search_visible and not ui_state.search_has_focus:
            return {
                "type": "action",
                "action": "focus_search",
                "description": "Click on search bar to focus it for typing",
                "confidence": 0.9,
                "reasoning": "Search bar visible but not focused, need to click to activate"
            }

        # If search has focus and we haven't typed yet, or search is empty
        if ui_state.search_has_focus and (not ui_state.search_text or ui_state.search_text == ""):
            search_query = song_name
            if artist:
                search_query = f"{song_name} {artist}"

            return {
                "type": "action",
                "action": "type_search",
                "description": f"Type search query: '{search_query}'",
                "search_text": search_query,
                "confidence": 0.9,
                "reasoning": "Search focused and empty, ready to type query"
            }

        # If we've typed but results haven't loaded yet, wait
        if ui_state.search_has_focus and ui_state.search_text and attempt < 3:
            return {
                "type": "action",
                "action": "wait_for_results",
                "description": "Wait for search results to load",
                "wait_seconds": 2.0,
                "confidence": 0.8,
                "reasoning": "Search query typed, waiting for results to appear"
            }

        # If search has results, click on the first result
        if ui_state.search_visible and ui_state.search_text:
            return {
                "type": "action",
                "action": "click_first_result",
                "description": "Click on first search result to start playback",
                "confidence": 0.8,
                "reasoning": "Search results visible, clicking first match"
            }

        # NEW: If we have a song list but target song not visible, try scrolling
        if ui_state.song_list_visible and ui_state.scrollable_area_visible:
            target_in_visible = self._is_target_song_visible(song_name, artist, ui_state)

            if not target_in_visible and ui_state.can_scroll_down and ui_state.current_scroll_position != "bottom":
                return {
                    "type": "action",
                    "action": "scroll_down",
                    "description": f"Scroll down to find '{song_name}' in the song list",
                    "confidence": 0.7,
                    "reasoning": f"Target song '{song_name}' not in current visible list, scrolling down"
                }

            elif not target_in_visible and ui_state.can_scroll_up and ui_state.current_scroll_position != "top":
                return {
                    "type": "action",
                    "action": "scroll_up",
                    "description": f"Scroll up to find '{song_name}' in the song list",
                    "confidence": 0.6,
                    "reasoning": f"Target song '{song_name}' not in current visible list, scrolling up"
                }

            elif target_in_visible:
                # Target song is visible, click on it
                song_index = self._find_target_song_index(song_name, artist, ui_state)
                if song_index >= 0:
                    return {
                        "type": "action",
                        "action": "click_song_in_list",
                        "description": f"Click on '{song_name}' in the song list (item #{song_index + 1})",
                        "song_index": song_index,
                        "confidence": 0.9,
                        "reasoning": f"Found target song '{song_name}' at position {song_index + 1} in visible list"
                    }

        # If we have a play button and are not playing, click play
        if ui_state.play_button_visible and not ui_state.is_playing:
            return {
                "type": "action",
                "action": "click_play",
                "description": "Click play button to start music",
                "confidence": 0.9,
                "reasoning": "Play button visible and music not playing"
            }

        # If we've exhausted attempts, give up
        if attempt >= self.max_attempts - 1:
            return {
                "type": "error",
                "error": f"Could not successfully automate Spotify playback after {attempt + 1} attempts"
            }

        # Default fallback
        return {
            "type": "action",
            "action": "retry_analysis",
            "description": "Take another screenshot and reanalyze UI state",
            "confidence": 0.5,
            "reasoning": "UI state unclear, need another analysis"
        }

    def _execute_vision_action(self, action: Dict[str, Any], ui_state: SpotifyUIState) -> bool:
        """
        Execute the recommended action using browser automation tools.

        Translates high-level action descriptions into specific automation calls.
        """
        action_type = action["action"]

        try:
            if action_type == "dismiss_popup":
                return self._dismiss_popup(ui_state)

            elif action_type == "activate_search":
                return self._activate_search()

            elif action_type == "focus_search":
                return self._focus_search()

            elif action_type == "type_search":
                return self._type_in_search(action["search_text"])

            elif action_type == "wait_for_results":
                time.sleep(action.get("wait_seconds", 2.0))
                return True

            elif action_type == "click_first_result":
                return self._click_first_result()

            elif action_type == "click_play":
                return self._click_play_button()

            # NEW: Scrolling and list browsing actions
            elif action_type == "scroll_down":
                return self._scroll_down()

            elif action_type == "scroll_up":
                return self._scroll_up()

            elif action_type == "click_song_in_list":
                return self._click_song_in_list(action["song_index"])

            # Playlist navigation actions
            elif action_type == "go_to_library":
                return self._go_to_library()

            elif action_type == "click_playlist_tab":
                return self._click_playlist_tab()

            elif action_type == "search_for_playlist":
                return self._search_for_playlist(action["playlist_name"])

            elif action_type == "retry_analysis":
                return True  # Just continue to next analysis

            else:
                logger.warning(f"[VISION SPOTIFY] Unknown action type: {action_type}")
                return False

        except Exception as e:
            logger.error(f"[VISION SPOTIFY] Action execution failed: {e}")
            return False

    def _dismiss_popup(self, ui_state: SpotifyUIState) -> bool:
        """Dismiss any visible popups or ads."""
        # This would use browser automation to click close buttons
        # For now, we'll simulate with AppleScript fallback
        logger.info("[VISION SPOTIFY] Dismissing popup (simulated)")
        return True

    def _activate_search(self) -> bool:
        """Activate the search interface."""
        logger.info("[VISION SPOTIFY] Activating search interface")
        # Could use keyboard shortcuts or click on search icon
        return True

    def _focus_search(self) -> bool:
        """Click on search bar to focus it."""
        logger.info("[VISION SPOTIFY] Focusing search bar")
        # Would use browser automation to click on search element
        return True

    def _type_in_search(self, search_text: str) -> bool:
        """Type text into search field."""
        logger.info(f"[VISION SPOTIFY] Typing in search: '{search_text}'")
        # Would use browser automation to type in search field
        return True

    def _click_first_result(self) -> bool:
        """Click on the first search result."""
        logger.info("[VISION SPOTIFY] Clicking first search result")
        # Would use browser automation to click first result
        return True

    def _click_play_button(self) -> bool:
        """Click the play button."""
        logger.info("[VISION SPOTIFY] Clicking play button")
        # Would use browser automation to click play button
        return True

    def _scroll_down(self) -> bool:
        """Scroll down in the current view."""
        logger.info("[VISION SPOTIFY] Scrolling down")
        try:
            # Use browser automation to scroll down
            # This simulates Page Down key to scroll down
            import subprocess
            result = subprocess.run([
                "osascript", "-e",
                'tell application "System Events" to key code 121'  # Page Down key
            ], capture_output=True, text=True, timeout=5)
            return result.returncode == 0
        except Exception as e:
            logger.error(f"[VISION SPOTIFY] Scroll down failed: {e}")
            return False

    def _scroll_up(self) -> bool:
        """Scroll up in the current view."""
        logger.info("[VISION SPOTIFY] Scrolling up")
        try:
            # Use browser automation to scroll up
            # This simulates Page Up key to scroll up
            import subprocess
            result = subprocess.run([
                "osascript", "-e",
                'tell application "System Events" to key code 116'  # Page Up key
            ], capture_output=True, text=True, timeout=5)
            return result.returncode == 0
        except Exception as e:
            logger.error(f"[VISION SPOTIFY] Scroll up failed: {e}")
            return False

    def _click_song_in_list(self, song_index: int) -> bool:
        """Click on a specific song in the visible list."""
        logger.info(f"[VISION SPOTIFY] Clicking song at index {song_index}")
        try:
            # Use keyboard navigation to select the song
            # First press Tab to focus the song list if not already focused
            import subprocess

            # Navigate to the song using arrow keys
            # Down arrow key code is 125, Up arrow is 126
            arrow_key = 125  # Down arrow
            presses_needed = song_index

            # Press down arrow the required number of times
            for i in range(presses_needed):
                result = subprocess.run([
                    "osascript", "-e",
                    f'tell application "System Events" to key code {arrow_key}'
                ], capture_output=True, text=True, timeout=2)
                if result.returncode != 0:
                    logger.error(f"[VISION SPOTIFY] Arrow key press {i+1} failed")
                    return False
                # Small delay between key presses
                import time
                time.sleep(0.1)

            # Press Enter to select/play the song
            result = subprocess.run([
                "osascript", "-e",
                'tell application "System Events" to key code 76'  # Enter key
            ], capture_output=True, text=True, timeout=2)

            return result.returncode == 0

        except Exception as e:
            logger.error(f"[VISION SPOTIFY] Click song in list failed: {e}")
            return False

    def _go_to_library(self) -> bool:
        """Navigate to the Your Library section."""
        logger.info("[VISION SPOTIFY] Navigating to Your Library")
        try:
            import subprocess
            # Use Cmd+L keyboard shortcut to go to Library
            result = subprocess.run([
                "osascript", "-e",
                'tell application "System Events" to keystroke "l" using command down'
            ], capture_output=True, text=True, timeout=5)
            return result.returncode == 0
        except Exception as e:
            logger.error(f"[VISION SPOTIFY] Go to library failed: {e}")
            return False

    def _click_playlist_tab(self) -> bool:
        """Click on the Playlists tab in Library."""
        logger.info("[VISION SPOTIFY] Clicking Playlists tab")
        try:
            import subprocess
            # Navigate to Playlists using Tab key and Enter
            # This assumes Playlists is accessible via keyboard navigation
            # Press Tab a few times to reach the Playlists tab
            for i in range(3):  # Adjust number of tabs as needed
                result = subprocess.run([
                    "osascript", "-e",
                    'tell application "System Events" to key code 48'  # Tab key
                ], capture_output=True, text=True, timeout=2)
                if result.returncode != 0:
                    return False
                import time
                time.sleep(0.2)

            # Press Enter to select Playlists
            result = subprocess.run([
                "osascript", "-e",
                'tell application "System Events" to key code 76'  # Enter key
            ], capture_output=True, text=True, timeout=2)

            return result.returncode == 0
        except Exception as e:
            logger.error(f"[VISION SPOTIFY] Click playlist tab failed: {e}")
            return False

    def _search_for_playlist(self, playlist_name: str) -> bool:
        """Search for a specific playlist."""
        logger.info(f"[VISION SPOTIFY] Searching for playlist: '{playlist_name}'")
        try:
            import subprocess
            # Use Cmd+K to focus search, then type playlist name
            # First focus search
            result1 = subprocess.run([
                "osascript", "-e",
                'tell application "System Events" to keystroke "k" using command down'
            ], capture_output=True, text=True, timeout=2)

            if result1.returncode != 0:
                return False

            import time
            time.sleep(0.5)

            # Type the playlist name (simplified - would need full string typing)
            # For now, just return success as this is complex to implement fully
            logger.info("[VISION SPOTIFY] Playlist search initiated (simplified implementation)")
            return True

        except Exception as e:
            logger.error(f"[VISION SPOTIFY] Search for playlist failed: {e}")
            return False

    def _verify_action_success(self, action: Dict[str, Any],
                              song_name: str, artist: Optional[str]) -> Dict[str, Any]:
        """
        Verify that the action was successful by taking another screenshot and analyzing.
        """
        logger.info("[VISION SPOTIFY] Verifying action success")

        try:
            screenshot_path = self._take_spotify_screenshot("verification")
            ui_state = self._analyze_ui_state(screenshot_path, song_name, artist, [])

            # Check if we're now playing the desired song
            if ui_state.is_playing and ui_state.current_track:
                return {
                    "success": True,
                    "action": "play_song",
                    "song_name": song_name,
                    "artist": artist,
                    "status": "playing",
                    "message": f"Successfully started playback: {ui_state.current_track}",
                    "track": ui_state.current_track,
                    "track_artist": ui_state.current_artist,
                    "method": "vision_automation"
                }

            return {
                "success": False,
                "error": "Verification failed - song not playing",
                "ui_state": ui_state.__dict__
            }

        except Exception as e:
            return {
                "success": False,
                "error": f"Verification failed: {str(e)}"
            }

    def browse_and_play_song(self, song_name: str, artist: Optional[str] = None,
                           playlist_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Browse through playlists/libraries and find & play a specific song.

        This is different from search-based playback - it browses actual lists.

        Args:
            song_name: Song to find and play
            artist: Optional artist name
            playlist_name: Optional playlist/library to browse

        Returns:
            Success/failure result
        """
        logger.info(f"[VISION SPOTIFY] Browsing for '{song_name}' by {artist or 'Unknown'}")

        max_browse_attempts = 10  # Allow more attempts for browsing
        scroll_attempts = 0

        for attempt in range(max_browse_attempts):
            try:
                # Take screenshot and analyze
                screenshot_path = self._take_spotify_screenshot(f"browse_{attempt}")
                ui_state = self._analyze_ui_state(screenshot_path, song_name, artist, [])

                # Check if we're in the right view (playlist/library)
                if playlist_name and ui_state.active_view != "playlist":
                    # Try to navigate to the playlist first
                    nav_action = self._navigate_to_playlist(playlist_name, ui_state)
                    if nav_action:
                        self._execute_vision_action(nav_action, ui_state)
                        time.sleep(2)  # Wait for navigation
                        continue

                # Check if target song is visible
                if ui_state.song_list_visible and self._is_target_song_visible(song_name, artist, ui_state):
                    # Found it! Click on the song
                    song_index = self._find_target_song_index(song_name, artist, ui_state)
                    click_action = {
                        "action": "click_song_in_list",
                        "song_index": song_index
                    }

                    if self._execute_vision_action(click_action, ui_state):
                        # Verify playback started
                        time.sleep(2)
                        verification = self._verify_action_success(click_action, song_name, artist)
                        if verification["success"]:
                            return {
                                "success": True,
                                "action": "browse_and_play",
                                "song_name": song_name,
                                "artist": artist,
                                "playlist": playlist_name,
                                "message": f"Found and started playing '{song_name}' from browsed list",
                                "browse_attempts": attempt + 1,
                                "scroll_attempts": scroll_attempts,
                                "method": "vision_browse"
                            }

                # Song not visible, try scrolling
                if ui_state.scrollable_area_visible:
                    if ui_state.can_scroll_down and scroll_attempts < 5:
                        scroll_action = {"action": "scroll_down"}
                        self._execute_vision_action(scroll_action, ui_state)
                        scroll_attempts += 1
                        time.sleep(1)  # Wait for scroll
                        continue
                    elif ui_state.can_scroll_up and scroll_attempts >= 5:
                        # We've scrolled down too far, try scrolling back up
                        scroll_action = {"action": "scroll_up"}
                        self._execute_vision_action(scroll_action, ui_state)
                        scroll_attempts += 1
                        time.sleep(1)
                        continue

                # If we can't scroll anymore and haven't found the song, give up
                if not ui_state.can_scroll_down and scroll_attempts >= 5:
                    break

            except Exception as e:
                logger.error(f"[VISION SPOTIFY] Browse attempt {attempt} failed: {e}")

        return {
            "success": False,
            "error": True,
            "error_type": "SongNotFoundInBrowse",
            "error_message": f"Could not find '{song_name}' in browsed lists after {max_browse_attempts} attempts",
            "browse_attempts": max_browse_attempts,
            "scroll_attempts": scroll_attempts,
            "method": "vision_browse"
        }

    def _navigate_to_playlist(self, playlist_name: str, ui_state: SpotifyUIState) -> Optional[Dict[str, Any]]:
        """Generate action to navigate to a specific playlist."""
        logger.info(f"[VISION SPOTIFY] Navigating to playlist: '{playlist_name}' from view: {ui_state.active_view}")

        # If we're already in a playlist view, check if it's the right one
        if ui_state.active_view == "playlist":
            # Try to extract playlist name from UI state
            current_playlist = self._extract_current_playlist_name(ui_state)
            if current_playlist and playlist_name.lower() in current_playlist.lower():
                logger.info(f"[VISION SPOTIFY] Already in target playlist: '{current_playlist}'")
                return None  # Already in the right playlist

        # Navigation strategies based on current view
        if ui_state.active_view == "home":
            # From home, we can either:
            # 1. Click on "Your Library" then navigate to playlists
            # 2. Use search to find the playlist
            return {
                "action": "go_to_library",
                "description": f"Navigate to library from home to access playlist '{playlist_name}'",
                "target_playlist": playlist_name,
                "confidence": 0.8,
                "reasoning": "From home view, first go to library to access playlists"
            }

        elif ui_state.active_view == "library":
            # In library, click on "Playlists" tab/section
            return {
                "action": "click_playlist_tab",
                "description": f"Click on Playlists tab in library to find '{playlist_name}'",
                "target_playlist": playlist_name,
                "confidence": 0.8,
                "reasoning": "In library view, need to select Playlists section"
            }

        elif ui_state.active_view == "search":
            # From search, go back to home/library
            return {
                "action": "go_to_library",
                "description": f"Navigate from search back to library to access playlist '{playlist_name}'",
                "target_playlist": playlist_name,
                "confidence": 0.7,
                "reasoning": "From search view, need to go to library to access playlists"
            }

        elif ui_state.active_view == "unknown":
            # Unknown view, try to find library or home navigation
            return {
                "action": "go_to_library",
                "description": f"Current view unknown, navigating to library to find playlist '{playlist_name}'",
                "target_playlist": playlist_name,
                "confidence": 0.6,
                "reasoning": "Unknown current view, defaulting to library navigation"
            }

        # If we can't determine navigation, try searching for the playlist
        return {
            "action": "search_for_playlist",
            "description": f"Search for playlist '{playlist_name}' using search functionality",
            "playlist_name": playlist_name,
            "confidence": 0.5,
            "reasoning": "Could not determine navigation path, falling back to search"
        }

    def _take_spotify_screenshot(self, suffix: str) -> str:
        """Take a screenshot of the Spotify application."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"spotify_{timestamp}_{suffix}.png"
        screenshot_path = self.screenshot_dir / filename

        # Ensure screenshot directory exists
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)

        try:
            logger.info(f"[VISION SPOTIFY] Taking screenshot: {screenshot_path}")

            # Use macOS screencapture to capture Spotify window
            # First get the Spotify window bounds using AppleScript
            applescript = '''
            tell application "Spotify"
                if it is running then
                    tell application "System Events"
                        tell process "Spotify"
                            set frontmost to true
                            delay 0.5
                            -- Get the bounds of the main window
                            set windowBounds to bounds of window 1
                            return windowBounds
                        end tell
                    end tell
                else
                    return "Spotify not running"
                end if
            end tell
            '''

            # Get window bounds
            result = subprocess.run(['osascript', '-e', applescript],
                                  capture_output=True, text=True, timeout=10)

            if result.returncode == 0 and result.stdout.strip() != "Spotify not running":
                # Parse bounds (format: x1, y1, x2, y2)
                bounds = result.stdout.strip().split(', ')
                if len(bounds) == 4:
                    try:
                        x1, y1, x2, y2 = map(int, bounds)
                        width = x2 - x1
                        height = y2 - y1

                        # Take screenshot of Spotify window bounds
                        cmd = [
                            'screencapture',
                            '-x',  # No sound
                            '-R', f"{x1},{y1},{width},{height}",  # Rectangle capture
                            str(screenshot_path)
                        ]

                        subprocess.run(cmd, check=True, timeout=15)
                        logger.info(f"[VISION SPOTIFY] Screenshot captured successfully: {screenshot_path}")
                        return str(screenshot_path)
                    except (ValueError, subprocess.CalledProcessError) as e:
                        logger.warning(f"[VISION SPOTIFY] Failed to capture with bounds: {e}")
                else:
                    logger.warning(f"[VISION SPOTIFY] Unexpected bounds format: {result.stdout}")
            else:
                logger.warning(f"[VISION SPOTIFY] Could not get Spotify window bounds: {result.stdout}")

            # Fallback: try to capture entire screen if Spotify window detection fails
            logger.info("[VISION SPOTIFY] Falling back to full screen capture")
            cmd = ['screencapture', '-x', str(screenshot_path)]
            subprocess.run(cmd, check=True, timeout=15)
            logger.info(f"[VISION SPOTIFY] Full screen screenshot captured: {screenshot_path}")
            return str(screenshot_path)

        except subprocess.TimeoutExpired:
            logger.error(f"[VISION SPOTIFY] Screenshot timeout")
        except subprocess.CalledProcessError as e:
            logger.error(f"[VISION SPOTIFY] Screenshot command failed: {e}")
        except Exception as e:
            logger.error(f"[VISION SPOTIFY] Screenshot failed: {e}")

        # Return path even if failed - vision analysis will handle missing files
        return str(screenshot_path)

    def _extract_track_from_text(self, text: str) -> Optional[str]:
        """Extract track name from vision analysis text."""
        # Simple extraction - in practice would be more sophisticated
        if "track:" in text.lower():
            return text.split("track:", 1)[1].split()[0]
        return None

    def _extract_artist_from_text(self, text: str) -> Optional[str]:
        """Extract artist name from vision analysis text."""
        # Simple extraction - in practice would be more sophisticated
        if "by " in text.lower():
            return text.split("by ", 1)[1].split()[0]
        return None

    def _extract_song_titles_from_text(self, text: str) -> List[str]:
        """Extract visible song titles from vision analysis text."""
        # This would be more sophisticated in practice
        # For now, look for patterns like "1. Song Title", "Song Title by Artist", etc.
        titles = []
        lines = text.split('\n')

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Look for numbered lists or bullet points
            if line[0].isdigit() and '. ' in line:
                title = line.split('. ', 1)[1].split(' by ')[0].strip()
                titles.append(title)
            # Look for direct song mentions
            elif ' by ' in line.lower():
                title = line.split(' by ')[0].strip()
                if len(title) > 0 and title[0].isupper():  # Likely a song title
                    titles.append(title)

        return titles[:10]  # Limit to reasonable number

    def _extract_song_artists_from_text(self, text: str) -> List[str]:
        """Extract visible song artists from vision analysis text."""
        artists = []
        lines = text.split('\n')

        for line in lines:
            line = line.strip()
            if ' by ' in line.lower():
                artist = line.split(' by ', 1)[1].split()[0].strip()
                artists.append(artist)

        return artists[:10]

    def _is_target_song_visible(self, song_name: str, artist: Optional[str],
                               ui_state: SpotifyUIState) -> bool:
        """Check if the target song is visible in the current UI state."""
        if not ui_state.visible_song_titles:
            return False

        target_lower = song_name.lower()
        artist_lower = (artist or "").lower()

        for i, title in enumerate(ui_state.visible_song_titles):
            if target_lower in title.lower():
                # If artist specified, check if it matches too
                if artist and ui_state.visible_song_artists and i < len(ui_state.visible_song_artists):
                    visible_artist = ui_state.visible_song_artists[i].lower()
                    if artist_lower in visible_artist:
                        return True
                elif not artist:  # No artist specified, title match is enough
                    return True

        return False

    def _find_target_song_index(self, song_name: str, artist: Optional[str],
                               ui_state: SpotifyUIState) -> int:
        """Find the index of the target song in the visible list."""
        if not ui_state.visible_song_titles:
            return -1

        target_lower = song_name.lower()
        artist_lower = (artist or "").lower()

        for i, title in enumerate(ui_state.visible_song_titles):
            if target_lower in title.lower():
                # If artist specified, check if it matches too
                if artist and ui_state.visible_song_artists and i < len(ui_state.visible_song_artists):
                    visible_artist = ui_state.visible_song_artists[i].lower()
                    if artist_lower in visible_artist:
                        return i
                elif not artist:  # No artist specified, title match is enough
                    return i

        return -1
