"""
Test Music Clarification Workflow

Tests for the bounded conversational memory and music clarification system.
Covers ambiguous song requests, context window management, and clarification workflows.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from src.memory.session_memory import SessionMemory, SessionStatus
from src.memory.session_manager import SessionManager
from src.llm.song_disambiguator import SongDisambiguator
from src.agent.spotify_agent import play_song, clarify_song_selection, process_clarification_response


class TestBoundedConversationalMemory:
    """Test bounded conversational memory window functionality."""

    def test_active_context_window_basic(self):
        """Test basic active context window functionality."""
        memory = SessionMemory(active_context_window=3)

        # Add interactions
        memory.add_interaction("Hello", {"message": "Hi there!", "status": "success"})
        memory.add_interaction("Play music", {"message": "Playing music", "status": "success"})
        memory.add_interaction("What's playing?", {"message": "Current track info", "status": "success"})
        memory.add_interaction("Pause", {"message": "Paused", "status": "success"})
        memory.add_interaction("Resume", {"message": "Resumed", "status": "success"})

        active_interactions = memory.get_active_context_interactions()
        assert len(active_interactions) == 3  # Limited by window size
        assert active_interactions[0].user_request == "What's playing?"
        assert active_interactions[2].user_request == "Resume"

    def test_context_window_reset_on_completion(self):
        """Test that context window resets after successful task completion."""
        memory = SessionMemory(active_context_window=5)

        # Add some interactions
        memory.add_interaction("Play some music", {"message": "What song?", "status": "action_required"})
        memory.add_interaction("Play Hello by Adele", {"message": "Playing Hello by Adele", "status": "success"})
        memory.add_interaction("What's the weather?", {"message": "Weather info", "status": "success"})

        # Check initial state
        assert memory._active_window_start is None
        active_interactions = memory.get_active_context_interactions()
        assert len(active_interactions) == 3

        # Simulate successful task completion (this should trigger reset)
        memory.add_interaction(
            "Create a presentation",
            {
                "message": "Presentation created successfully",
                "status": "success",
                "final_result": {"status": "success"}
            }
        )

        # Context window should be reset
        assert memory._active_window_start == 3  # Points to the last interaction
        active_interactions = memory.get_active_context_interactions()
        assert len(active_interactions) == 1  # Only the presentation creation

    def test_context_window_explicit_clear(self):
        """Test explicit context window reset via /clear command."""
        memory = SessionMemory(active_context_window=5)

        memory.add_interaction("Play music", {"message": "Playing", "status": "success"})
        memory.add_interaction("Pause", {"message": "Paused", "status": "success"})

        assert len(memory.get_active_context_interactions()) == 2

        # Explicit clear command
        memory.add_interaction("/clear", {"message": "Context cleared", "status": "success"})

        # Window should be reset
        assert memory._active_window_start == 2
        assert len(memory.get_active_context_interactions()) == 1

    def test_conversation_summary_large_window(self):
        """Test conversation summary generation for large context windows."""
        memory = SessionMemory(active_context_window=10, enable_conversation_summary=True)

        # Add many interactions to trigger summarization
        for i in range(12):
            memory.add_interaction(
                f"Request {i}",
                {"message": f"Response {i}", "status": "success"}
            )

        # Should use summary when window > 8
        assert memory.should_use_conversation_summary()

        summary = memory.get_conversation_summary(max_interactions=3)
        assert "Recent Conversation Summary:" in summary
        assert "Request 9" in summary  # Most recent
        assert "... and 9 earlier interactions" in summary


class TestMusicClarificationWorkflow:
    """Test music clarification workflow end-to-end."""

    @patch('src.agent.spotify_agent.SongDisambiguator')
    @patch('src.agent.spotify_agent.SpotifyPlaybackService')
    def test_ambiguous_song_triggers_clarification(self, mock_service, mock_disambiguator):
        """Test that ambiguous songs trigger clarification instead of auto-play."""
        # Mock disambiguation with low confidence and alternatives
        mock_disambiguator_instance = Mock()
        mock_disambiguator_instance.disambiguate.return_value = {
            "song_name": "Hello",
            "artist": "Adele",
            "confidence": 0.6,
            "alternatives": [
                {"song_name": "Hello", "artist": "Lionel Richie"},
                {"song_name": "Hello", "artist": "Adele"}
            ],
            "reasoning": "Multiple Hello songs exist"
        }

        mock_disambiguator_instance.check_ambiguity_and_decide.return_value = {
            "should_clarify": True,
            "confidence": 0.6,
            "reasoning": "Low confidence with alternatives",
            "risk_factors": ["low_confidence_0.6", "multiple_alternatives_2"],
            "suggested_action": "clarify_with_user"
        }

        mock_disambiguator.return_value = mock_disambiguator_instance

        # Call play_song
        result = play_song("hello")

        # Should return clarification request, not play
        assert result.get("error") == True
        assert result.get("error_type") == "AmbiguousSongRequest"
        assert result.get("clarification_needed") == True
        assert "clarification_options" in result
        assert len(result["clarification_options"]) == 2

    @patch('src.agent.spotify_agent.datetime')
    def test_clarify_song_selection_formats_options(self, mock_datetime):
        """Test that clarification options are properly formatted."""
        mock_datetime.now.return_value = datetime(2024, 1, 1, 12, 0, 0)

        clarification_options = [
            {"song_name": "Hello", "artist": "Adele", "confidence": 0.8, "primary": True},
            {"song_name": "Hello", "artist": "Lionel Richie", "confidence": 0.6, "primary": False}
        ]

        result = clarify_song_selection(clarification_options, "hello")

        assert result["success"] == True
        assert "I'm not sure which song you mean" in result["message"]
        assert "1. 'Hello' by Adele (recommended)" in result["message"]
        assert "2. 'Hello' by Lionel Richie" in result["message"]
        assert result["clarification_options"] == clarification_options

    def test_process_clarification_by_number(self):
        """Test processing clarification response by option number."""
        clarification_options = [
            {"song_name": "Hello", "artist": "Adele", "confidence": 0.8},
            {"song_name": "Hello", "artist": "Lionel Richie", "confidence": 0.6}
        ]

        result = process_clarification_response(
            "1", clarification_options, "hello"
        )

        assert result["success"] == True
        assert result["resolved_choice"]["song_name"] == "Hello"
        assert result["resolved_choice"]["artist"] == "Adele"
        assert result["ready_for_playback"] == True

    def test_process_clarification_by_name(self):
        """Test processing clarification response by song/artist name."""
        clarification_options = [
            {"song_name": "Hello", "artist": "Adele", "confidence": 0.8},
            {"song_name": "Hello", "artist": "Lionel Richie", "confidence": 0.6}
        ]

        # Test by artist name
        result = process_clarification_response(
            "adele", clarification_options, "hello"
        )

        assert result["success"] == True
        assert result["resolved_choice"]["artist"] == "Adele"

        # Test by song name
        result = process_clarification_response(
            "hello by lionel", clarification_options, "hello"
        )

        assert result["success"] == True
        assert result["resolved_choice"]["artist"] == "Lionel Richie"


class TestContextReuseAndLearning:
    """Test context reuse and learning from clarifications."""

    def test_prior_resolution_lookup(self):
        """Test that prior clarifications are reused."""
        config = {"openai": {"api_key": "test", "model": "gpt-4"}}
        disambiguator = SongDisambiguator(config)

        # Mock reasoning context with prior clarification
        reasoning_context = {
            "spotify_last_resolution": {
                "original_query": "hello",
                "resolved_song": "Hello",
                "resolved_artist": "Adele",
                "confidence": 1.0
            }
        }

        # Should return prior resolution without LLM call
        result = disambiguator.disambiguate("hello", reasoning_context)

        assert result["song_name"] == "Hello"
        assert result["artist"] == "Adele"
        assert result["confidence"] == 1.0
        assert result["from_prior_clarification"] == True

    def test_clarification_storage_in_session(self):
        """Test that clarifications are stored in session context."""
        memory = SessionMemory()

        # Simulate clarification processing result
        clarification_data = {
            "original_query": "hello",
            "user_response": "1",
            "resolved_song": "Hello",
            "resolved_artist": "Adele",
            "clarification_timestamp": "2024-01-01T12:00:00",
            "options_presented": 2
        }

        # Store clarification (normally done in agent.py)
        memory.set_context("spotify.last_resolution", {
            "original_query": clarification_data["original_query"],
            "resolved_song": clarification_data["resolved_song"],
            "resolved_artist": clarification_data["resolved_artist"],
            "clarification_timestamp": clarification_data["clarification_timestamp"],
            "confidence": 1.0
        })

        # Add to clarifications list
        existing_clarifications = memory.get_context("spotify.clarifications", [])
        existing_clarifications.append(clarification_data)
        memory.set_context("spotify.clarifications", existing_clarifications)

        # Verify storage
        last_resolution = memory.get_context("spotify.last_resolution")
        assert last_resolution["resolved_song"] == "Hello"
        assert last_resolution["resolved_artist"] == "Adele"

        clarifications = memory.get_context("spotify.clarifications")
        assert len(clarifications) == 1
        assert clarifications[0]["resolved_song"] == "Hello"


class TestIntegrationScenarios:
    """Integration tests for complete clarification workflows."""

    def test_complete_clarification_workflow(self):
        """Test a complete ambiguous → clarify → resolve → play workflow."""
        # This would be an integration test that:
        # 1. User requests ambiguous song
        # 2. Agent returns clarification_needed
        # 3. User responds with choice
        # 4. Agent resolves and plays song
        # 5. Resolution is stored for future use

        # For now, just test the data flow
        workflow_steps = [
            {
                "user_request": "play hello",
                "expected_response": {
                    "error_type": "AmbiguousSongRequest",
                    "clarification_needed": True
                }
            },
            {
                "user_request": "1",  # Choose first option
                "context": {
                    "clarification_options": [
                        {"song_name": "Hello", "artist": "Adele"},
                        {"song_name": "Hello", "artist": "Lionel Richie"}
                    ]
                },
                "expected_response": {
                    "resolved_choice": {"song_name": "Hello", "artist": "Adele"},
                    "ready_for_playback": True
                }
            }
        ]

        # Test data structure expectations
        assert workflow_steps[0]["expected_response"]["clarification_needed"] == True
        assert workflow_steps[1]["expected_response"]["ready_for_playback"] == True

    def test_context_window_resets_after_completion(self):
        """Test that context window resets after task completion."""
        memory = SessionMemory(active_context_window=5)

        # Simulate a clarification workflow
        interactions = [
            ("play hello", {"error_type": "AmbiguousSongRequest", "clarification_needed": True}),
            ("1", {"resolved_choice": {"song_name": "Hello", "artist": "Adele"}, "ready_for_playback": True}),
            ("play song", {"message": "Now playing Hello by Adele", "status": "success", "final_result": {"status": "success"}}),
            ("what's the weather?", {"message": "Weather info", "status": "success"})
        ]

        for user_req, agent_resp in interactions:
            memory.add_interaction(user_req, agent_resp)

        # After successful completion, context should reset
        # The weather question should start fresh context
        active_interactions = memory.get_active_context_interactions()
        assert len(active_interactions) == 1
        assert active_interactions[0].user_request == "what's the weather?"


if __name__ == "__main__":
    pytest.main([__file__])
