"""
Test Execution Router - Comprehensive testing for ExecutionRouter functionality.

Tests execution strategy routing, feedback loops, and vision-based escalation.
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import json
from src.agent.execution_router import ExecutionRouter, ExecutionStrategy


class TestExecutionRouter(unittest.TestCase):
    """Test cases for ExecutionRouter."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_config = {
            "openai": {
                "api_key": "test-key",
                "model": "gpt-4o",
                "vision_model": "gpt-4o"
            },
            "spotify": {
                "max_vision_attempts": 5
            }
        }

        self.mock_reasoning_trace = Mock()

    def test_execution_strategy_enum(self):
        """Test ExecutionStrategy enum values."""
        self.assertEqual(ExecutionStrategy.SIMPLE.value, "simple")
        self.assertEqual(ExecutionStrategy.ADVANCED.value, "advanced")
        self.assertEqual(ExecutionStrategy.VISION.value, "vision")

    def test_router_initialization(self):
        """Test ExecutionRouter initialization."""
        router = ExecutionRouter(self.mock_config, self.mock_reasoning_trace)
        self.assertEqual(router.config, self.mock_config)
        self.assertEqual(router.reasoning_trace, self.mock_reasoning_trace)
        self.assertEqual(router.model, "gpt-4o")
        self.assertEqual(router.vision_model, "gpt-4o")

    @patch('src.agent.execution_router.OpenAI')
    def test_route_simple_execution(self, mock_openai):
        """Test routing to SIMPLE execution strategy."""
        mock_message = Mock()
        mock_message.content = json.dumps({
            "strategy": "simple",
            "confidence": 0.95,
            "reasoning": "Standard playback operation - AppleScript can handle reliably",
            "escalation_trigger": "AppleScript fails",
            "fallback_strategy": "advanced"
        })

        mock_choice = Mock()
        mock_choice.message = mock_message

        mock_response = Mock()
        mock_response.choices = [mock_choice]

        mock_client = Mock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai.return_value = mock_client

        router = ExecutionRouter(self.mock_config)
        result = router.route_execution("play_song", "Viva la Vida", "Coldplay")

        self.assertEqual(result["strategy"], ExecutionStrategy.SIMPLE)
        self.assertEqual(result["confidence"], 0.95)
        self.assertIn("AppleScript", result["reasoning"])

    @patch('src.agent.execution_router.OpenAI')
    def test_route_vision_execution_for_complex_ui(self, mock_openai):
        """Test routing to VISION for complex UI scenarios."""
        mock_message = Mock()
        mock_message.content = json.dumps({
            "strategy": "vision",
            "confidence": 0.85,
            "reasoning": "Complex UI with unpredictable elements - need vision analysis",
            "escalation_trigger": "vision fails",
            "fallback_strategy": "advanced"
        })

        mock_choice = Mock()
        mock_choice.message = mock_message

        mock_response = Mock()
        mock_response.choices = [mock_choice]

        mock_client = Mock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai.return_value = mock_client

        router = ExecutionRouter(self.mock_config)
        context = {"ui_complexity": "complex unpredictable popup ads"}
        result = router.route_execution("play_song", "unknown song", context=context)

        # Should route to VISION due to complex UI
        self.assertEqual(result["strategy"], ExecutionStrategy.VISION)
        self.assertEqual(result["confidence"], 0.9)  # Direct vision routing confidence

    def test_should_use_vision_first_with_force_flag(self):
        """Test direct vision routing when force_vision is set."""
        router = ExecutionRouter(self.mock_config)
        context = {"force_vision": True}

        result = router.route_execution("play_song", "test song", context=context)

        self.assertEqual(result["strategy"], ExecutionStrategy.VISION)
        self.assertEqual(result["confidence"], 0.9)
        self.assertIn("Direct vision routing", result["reasoning"])

    def test_should_use_vision_first_with_multiple_failures(self):
        """Test routing to vision after multiple AppleScript failures."""
        router = ExecutionRouter(self.mock_config)
        context = {
            "previous_attempts": [
                {"strategy": "simple", "success": False},
                {"strategy": "simple", "success": False},
                {"strategy": "simple", "success": False}
            ]
        }

        result = router.route_execution("play_song", "test song", context=context)

        self.assertEqual(result["strategy"], ExecutionStrategy.VISION)
        self.assertIn("Direct vision routing", result["reasoning"])

    def test_execute_with_feedback_loop_simple_success(self):
        """Test feedback loop with simple strategy success."""
        router = ExecutionRouter(self.mock_config)

        # Mock the _execute_simple method directly
        mock_result = {
            "success": True,
            "track": "Viva la Vida",
            "artist": "Coldplay",
            "message": "Now playing Viva la Vida"
        }
        router._execute_simple = Mock(return_value=mock_result)

        result = router.execute_with_feedback_loop(
            operation="play_song",
            song_name="Viva la Vida",
            artist="Coldplay"
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["final_strategy"], "simple")
        self.assertEqual(result["execution_attempts"], 1)

    def test_execute_with_feedback_loop_escalation_to_vision(self):
        """Test feedback loop escalating from simple to vision."""
        router = ExecutionRouter(self.mock_config)

        # Mock failed simple execution
        router._execute_simple = Mock(return_value={
            "success": False,
            "error_type": "AppleScriptError",
            "error_message": "Script failed"
        })

        # Mock successful vision execution
        router._execute_vision = Mock(return_value={
            "success": True,
            "track": "Viva la Vida",
            "artist": "Coldplay",
            "final_strategy": "vision",
            "execution_attempts": 1
        })

        # Manually patch the route_execution method to simulate escalation
        call_count = 0

        def mock_route_execution(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return {
                    "strategy": ExecutionStrategy.SIMPLE,
                    "escalation_trigger": "AppleScript fails"
                }
            else:
                return {
                    "strategy": ExecutionStrategy.VISION,
                    "escalation_trigger": "vision fails"
                }

        router.route_execution = mock_route_execution
        router.should_escalate = lambda *args: True  # Force escalation

        result = router.execute_with_feedback_loop(
            operation="play_song",
            song_name="Viva la Vida",
            artist="Coldplay"
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["final_strategy"], "vision")
        self.assertGreaterEqual(result["execution_attempts"], 2)

    def test_should_escalate_logic(self):
        """Test escalation decision logic."""
        router = ExecutionRouter(self.mock_config)

        # Success should not escalate
        success_result = {"success": True}
        self.assertFalse(router.should_escalate(ExecutionStrategy.SIMPLE, success_result, "any error"))

        # AppleScript errors should escalate
        error_result = {
            "success": False,
            "error_type": "AppleScriptError"
        }
        self.assertTrue(router.should_escalate(ExecutionStrategy.SIMPLE, error_result, "AppleScript fails"))

        # Vision is final strategy, shouldn't escalate further
        self.assertFalse(router.should_escalate(ExecutionStrategy.VISION, error_result, "any error"))

    @patch('src.agent.execution_router.OpenAI')
    def test_analyze_screenshot_vision_success(self, mock_openai):
        """Test vision screenshot analysis."""
        mock_message = Mock()
        mock_message.content = json.dumps({
            "ui_state": "Spotify visible, search bar focused, no popups",
            "action_recommended": "type_search_query",
            "confidence": 0.9,
            "reasoning": "UI is ready for search input",
            "coordinates": None
        })

        mock_choice = Mock()
        mock_choice.message = mock_message

        mock_response = Mock()
        mock_response.choices = [mock_choice]

        mock_client = Mock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai.return_value = mock_client

        router = ExecutionRouter(self.mock_config)

        # Create a temporary screenshot file for testing
        import tempfile
        import os

        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
            f.write(b'fake png data')
            screenshot_path = f.name

        try:
            result = router.analyze_screenshot(
                screenshot_path=screenshot_path,
                operation="play_song",
                song_name="Test Song",
                artist="Test Artist"
            )

            self.assertEqual(result["ui_state"], "Spotify visible, search bar focused, no popups")
            self.assertEqual(result["action_recommended"], "type_search_query")
            self.assertEqual(result["confidence"], 0.9)

        finally:
            os.unlink(screenshot_path)

    def test_format_previous_attempts(self):
        """Test formatting of previous attempts for prompts."""
        router = ExecutionRouter(self.mock_config)

        attempts = [
            {"strategy": "simple", "error_type": "AppleScriptError"},
            {"strategy": "advanced", "error_type": "ElementNotFound"},
            {"strategy": "vision", "error_type": "AnalysisFailed"}
        ]

        formatted = router._format_previous_attempts(attempts)
        self.assertIn("1. simple → AppleScriptError", formatted)
        self.assertIn("2. advanced → ElementNotFound", formatted)
        self.assertIn("3. vision → AnalysisFailed", formatted)

    def test_build_context_string(self):
        """Test building context string from various inputs."""
        router = ExecutionRouter(self.mock_config)

        context = {
            "ui_complexity": "very complex",
            "spotify_running": False,
            "previous_failures": ["error1", "error2", "error3"]
        }

        context_str = router._build_context_string(context)
        self.assertIn("UI Complexity: very complex", context_str)
        self.assertIn("Spotify Status: Not Running", context_str)
        self.assertIn("Previous Failures: 3", context_str)

    def test_browse_and_play_song_found(self):
        """Test successful browsing and playing a song."""
        from src.agent.execution_router import ExecutionStrategy

        router = ExecutionRouter(self.mock_config)

        # Mock vision automation for successful browse
        mock_result = {
            "success": True,
            "action": "browse_and_play",
            "song_name": "Test Song",
            "artist": "Test Artist",
            "message": "Found and started playing 'Test Song' from browsed list",
            "browse_attempts": 2,
            "scroll_attempts": 1,
            "method": "vision_browse"
        }
        router._execute_vision = Mock(return_value=mock_result)

        # Mock the routing to return actual VISION enum
        router.route_execution = Mock(return_value={
            "strategy": ExecutionStrategy.VISION,
            "escalation_trigger": "vision fails"
        })

        result = router.execute_with_feedback_loop(
            operation="browse_and_play",
            song_name="Test Song",
            artist="Test Artist"
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["final_strategy"], "vision")
        self.assertEqual(result["action"], "browse_and_play")

    def test_scroll_down_action_execution(self):
        """Test scroll down action execution."""
        from src.automation.vision_spotify_automation import VisionSpotifyAutomation

        # Mock the vision agent initialization
        with patch('src.agent.vision_agent.VisionAgent') as mock_vision_agent:
            vision_auto = VisionSpotifyAutomation(self.mock_config)

            # Mock scroll down execution
            vision_auto._scroll_down = Mock(return_value=True)

            action = {"action": "scroll_down", "description": "Scroll down"}
            ui_state = Mock()

            result = vision_auto._execute_vision_action(action, ui_state)
            self.assertTrue(result)
            vision_auto._scroll_down.assert_called_once()

    def test_click_song_in_list_action(self):
        """Test clicking song in list action."""
        from src.automation.vision_spotify_automation import VisionSpotifyAutomation

        with patch('src.agent.vision_agent.VisionAgent') as mock_vision_agent:
            vision_auto = VisionSpotifyAutomation(self.mock_config)

            vision_auto._click_song_in_list = Mock(return_value=True)

            action = {
                "action": "click_song_in_list",
                "song_index": 2,
                "description": "Click on song at index 2"
            }
            ui_state = Mock()

            result = vision_auto._execute_vision_action(action, ui_state)
            self.assertTrue(result)
            vision_auto._click_song_in_list.assert_called_with(2)

    def test_song_visibility_detection(self):
        """Test detecting if target song is visible in list."""
        from src.automation.vision_spotify_automation import VisionSpotifyAutomation, SpotifyUIState

        vision_auto = VisionSpotifyAutomation(self.mock_config)

        # Create UI state with visible songs
        ui_state = SpotifyUIState()
        ui_state.visible_song_titles = ["Song One", "Target Song", "Song Three"]
        ui_state.visible_song_artists = ["Artist A", "Target Artist", "Artist C"]

        # Test song found without artist
        self.assertTrue(vision_auto._is_target_song_visible("Target Song", None, ui_state))

        # Test song found with matching artist
        self.assertTrue(vision_auto._is_target_song_visible("Target Song", "Target Artist", ui_state))

        # Test song not found
        self.assertFalse(vision_auto._is_target_song_visible("Missing Song", None, ui_state))

        # Test song found but artist doesn't match
        self.assertFalse(vision_auto._is_target_song_visible("Target Song", "Wrong Artist", ui_state))

    def test_find_target_song_index(self):
        """Test finding the index of target song in visible list."""
        from src.automation.vision_spotify_automation import VisionSpotifyAutomation, SpotifyUIState

        vision_auto = VisionSpotifyAutomation(self.mock_config)

        ui_state = SpotifyUIState()
        ui_state.visible_song_titles = ["Song One", "Target Song", "Song Three"]
        ui_state.visible_song_artists = ["Artist A", "Target Artist", "Artist C"]

        # Find song by title only
        index = vision_auto._find_target_song_index("Target Song", None, ui_state)
        self.assertEqual(index, 1)

        # Find song by title and artist
        index = vision_auto._find_target_song_index("Target Song", "Target Artist", ui_state)
        self.assertEqual(index, 1)

        # Song not found
        index = vision_auto._find_target_song_index("Missing Song", None, ui_state)
        self.assertEqual(index, -1)

    def test_extract_song_titles_from_text(self):
        """Test extracting song titles from vision analysis text."""
        from src.automation.vision_spotify_automation import VisionSpotifyAutomation

        vision_auto = VisionSpotifyAutomation(self.mock_config)

        text = """Visible songs in playlist:
1. Song Title One by Artist A
2. Another Song by Artist B
3. Third Song by Artist C"""

        titles = vision_auto._extract_song_titles_from_text(text)
        expected = ["Song Title One", "Another Song", "Third Song"]
        self.assertEqual(titles, expected)

    def test_scroll_position_detection(self):
        """Test detecting scroll position from vision analysis."""
        from src.automation.vision_spotify_automation import VisionSpotifyAutomation

        vision_auto = VisionSpotifyAutomation(self.mock_config)

        # Test basic scrolling detection - should default to allowing scroll down
        ui_state = vision_auto._parse_vision_analysis({
            "summary": "Showing a list of songs in playlist",
            "status": "action_required"
        }, "test song", None)

        # Basic test that scrolling flags are initialized properly
        self.assertTrue(ui_state.can_scroll_down)  # Should be able to scroll down initially
        self.assertEqual(ui_state.current_scroll_position, "middle")  # Default position

    def test_playlist_navigation_action(self):
        """Test generating navigation actions for playlists."""
        from src.automation.vision_spotify_automation import VisionSpotifyAutomation, SpotifyUIState

        vision_auto = VisionSpotifyAutomation(self.mock_config)

        # Test navigation from library view
        ui_state = SpotifyUIState()
        ui_state.active_view = "library"

        action = vision_auto._navigate_to_playlist("My Playlist", ui_state)
        self.assertEqual(action["action"], "click_playlist_tab")
        self.assertIn("My Playlist", action["description"])

        # Test navigation from home view
        ui_state.active_view = "home"
        action = vision_auto._navigate_to_playlist("Workout Mix", ui_state)
        self.assertEqual(action["action"], "go_to_library")
        self.assertIn("Workout Mix", action["description"])


if __name__ == '__main__':
    unittest.main()
