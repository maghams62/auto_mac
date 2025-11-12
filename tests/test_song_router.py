"""
Test Song Router - Comprehensive testing for IntentRouter functionality.

Tests routing decisions, confidence scoring, and ReasoningTrace integration.
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import json
from src.agent.song_router import IntentRouter, RouteDecision, ROUTING_PROMPT, ROUTING_SYSTEM_PROMPT


class TestSongRouter(unittest.TestCase):
    """Test cases for IntentRouter."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_config = {
            "openai": {
                "api_key": "test-key",
                "model": "gpt-4o"
            }
        }

        self.mock_reasoning_trace = Mock()

    def test_route_decision_enum(self):
        """Test RouteDecision enum values."""
        self.assertEqual(RouteDecision.RESOLVE.value, "resolve")
        self.assertEqual(RouteDecision.SEARCH.value, "search")
        self.assertEqual(RouteDecision.ASK_USER.value, "ask_user")

    def test_router_initialization(self):
        """Test IntentRouter initialization."""
        router = IntentRouter(self.mock_config, self.mock_reasoning_trace)
        self.assertEqual(router.config, self.mock_config)
        self.assertEqual(router.reasoning_trace, self.mock_reasoning_trace)
        self.assertEqual(router.model, "gpt-4o")
        self.assertEqual(router.temperature, 0.2)

    @patch('src.agent.song_router.OpenAI')
    def test_route_famous_song_resolve(self, mock_openai):
        """Test routing a famous song query to RESOLVE."""
        # Mock LLM response for "moonwalk song"
        mock_message = Mock()
        mock_message.content = json.dumps({
            "route": "resolve",
            "confidence": 0.95,
            "reasoning": "Famous iconic query - 'moonwalk' + 'Michael Jackson' is a well-known reference",
            "fallback_route": "search"
        })

        mock_choice = Mock()
        mock_choice.message = mock_message

        mock_response = Mock()
        mock_response.choices = [mock_choice]

        mock_client = Mock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai.return_value = mock_client

        router = IntentRouter(self.mock_config)
        result = router.route("moonwalk song")

        self.assertEqual(result["route"], RouteDecision.RESOLVE)
        self.assertEqual(result["confidence"], 0.95)
        self.assertIn("moonwalk", result["reasoning"])

        # Verify LLM was called with correct parameters
        mock_client.chat.completions.create.assert_called_once()
        call_args = mock_client.chat.completions.create.call_args[1]
        self.assertEqual(call_args["model"], "gpt-4o")
        self.assertEqual(call_args["temperature"], 0.2)

    @patch('src.agent.song_router.OpenAI')
    def test_route_exact_title_search(self, mock_openai):
        """Test routing an exact song title to SEARCH."""
        mock_message = Mock()
        mock_message.content = json.dumps({
            "route": "search",
            "confidence": 0.90,
            "reasoning": "Exact song title provided. Direct catalog search is more efficient",
            "fallback_route": "resolve"
        })

        mock_choice = Mock()
        mock_choice.message = mock_message

        mock_response = Mock()
        mock_response.choices = [mock_choice]

        mock_client = Mock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai.return_value = mock_client

        router = IntentRouter(self.mock_config)
        result = router.route("Breaking the Habit")

        self.assertEqual(result["route"], RouteDecision.SEARCH)
        self.assertEqual(result["confidence"], 0.90)
        self.assertIn("exact", result["reasoning"].lower())

    @patch('src.agent.song_router.OpenAI')
    def test_route_vague_query_ask_user(self, mock_openai):
        """Test routing a vague query to ASK_USER."""
        mock_message = Mock()
        mock_message.content = json.dumps({
            "route": "ask_user",
            "confidence": 0.95,
            "reasoning": "Extremely vague with no context. Cannot confidently route",
            "fallback_route": "search"
        })

        mock_choice = Mock()
        mock_choice.message = mock_message

        mock_response = Mock()
        mock_response.choices = [mock_choice]

        mock_client = Mock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai.return_value = mock_client

        router = IntentRouter(self.mock_config)
        result = router.route("that song")

        self.assertEqual(result["route"], RouteDecision.ASK_USER)
        self.assertEqual(result["confidence"], 0.95)
        self.assertIn("vague", result["reasoning"].lower())

    @patch('src.agent.song_router.OpenAI')
    def test_route_with_reasoning_trace(self, mock_openai):
        """Test routing with ReasoningTrace integration."""
        mock_message = Mock()
        mock_message.content = json.dumps({
            "route": "resolve",
            "confidence": 0.85,
            "reasoning": "Famous reference to Space Song",
            "fallback_route": "search"
        })

        mock_choice = Mock()
        mock_choice.message = mock_message

        mock_response = Mock()
        mock_response.choices = [mock_choice]

        mock_client = Mock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai.return_value = mock_client

        router = IntentRouter(self.mock_config, self.mock_reasoning_trace)
        result = router.route("the space song")

        # Verify reasoning trace was called
        self.mock_reasoning_trace.add_entry.assert_called_once()
        call_args = self.mock_reasoning_trace.add_entry.call_args[1]
        self.assertIn("ReasoningStage.PLANNING", call_args["stage"])  # Check stage string
        self.assertIn("Routing song query", call_args["thought"])
        self.assertEqual(call_args["action"], "route_song_query")

    @patch('src.agent.song_router.OpenAI')
    def test_route_with_context_history(self, mock_openai):
        """Test routing with past failure context."""
        mock_message = Mock()
        mock_message.content = json.dumps({
            "route": "search",
            "confidence": 0.80,
            "reasoning": "Recent failures suggest using catalog search",
            "fallback_route": "resolve"
        })

        mock_choice = Mock()
        mock_choice.message = mock_message

        mock_response = Mock()
        mock_response.choices = [mock_choice]

        mock_client = Mock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai.return_value = mock_client

        router = IntentRouter(self.mock_config)
        context = {
            "past_failures": [
                {"query": "moonwalk song", "route": "resolve", "reason": "Wrong song"}
            ],
            "session_history": [
                {"query": "space song", "success": False}
            ]
        }

        result = router.route("another song", context)

        # Verify context was included in prompt
        call_args = mock_client.chat.completions.create.call_args[1]
        messages = call_args["messages"]
        user_message = messages[1]["content"]
        self.assertIn("PAST FAILURES", user_message)
        self.assertIn("moonwalk song", user_message)

    @patch('src.agent.song_router.OpenAI')
    def test_route_confidence_clamping(self, mock_openai):
        """Test confidence score clamping to [0, 1]."""
        mock_message = Mock()
        mock_message.content = json.dumps({
            "route": "resolve",
            "confidence": 1.5,  # Over 1.0
            "reasoning": "Test confidence clamping",
            "fallback_route": "search"
        })

        mock_choice = Mock()
        mock_choice.message = mock_message

        mock_response = Mock()
        mock_response.choices = [mock_choice]

        mock_client = Mock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai.return_value = mock_client

        router = IntentRouter(self.mock_config)
        result = router.route("test query")

        self.assertEqual(result["confidence"], 1.0)  # Should be clamped

    @patch('src.agent.song_router.OpenAI')
    def test_route_invalid_json_fallback(self, mock_openai):
        """Test fallback when LLM returns invalid JSON."""
        mock_message = Mock()
        mock_message.content = "Invalid JSON response"

        mock_choice = Mock()
        mock_choice.message = mock_message

        mock_response = Mock()
        mock_response.choices = [mock_choice]

        mock_client = Mock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai.return_value = mock_client

        router = IntentRouter(self.mock_config)
        result = router.route("test query")

        # Should fallback to SEARCH with low confidence
        self.assertEqual(result["route"], RouteDecision.SEARCH)
        self.assertEqual(result["confidence"], 0.3)
        self.assertIn("defaulting to catalog search", result["reasoning"])

    @patch('src.agent.song_router.OpenAI')
    def test_route_invalid_route_fallback(self, mock_openai):
        """Test fallback when LLM returns invalid route."""
        mock_message = Mock()
        mock_message.content = json.dumps({
            "route": "invalid_route",
            "confidence": 0.8,
            "reasoning": "Invalid route test",
            "fallback_route": "search"
        })

        mock_choice = Mock()
        mock_choice.message = mock_message

        mock_response = Mock()
        mock_response.choices = [mock_choice]

        mock_client = Mock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai.return_value = mock_client

        router = IntentRouter(self.mock_config)
        result = router.route("test query")

        # Should default to SEARCH
        self.assertEqual(result["route"], RouteDecision.SEARCH)
        self.assertEqual(result["confidence"], 0.8)

    @patch('src.agent.song_router.OpenAI')
    def test_route_llm_error_fallback(self, mock_openai):
        """Test fallback when LLM call fails."""
        mock_client = Mock()
        mock_client.chat.completions.create.side_effect = Exception("API Error")
        mock_openai.return_value = mock_client

        router = IntentRouter(self.mock_config)
        result = router.route("test query")

        # Should fallback to SEARCH with low confidence
        self.assertEqual(result["route"], RouteDecision.SEARCH)
        self.assertEqual(result["confidence"], 0.3)
        self.assertIn("defaulting to catalog search", result["reasoning"])
        self.assertIn("API Error", result["reasoning"])

    @patch('src.agent.song_router.OpenAI')
    def test_route_o1_model_parameters(self, mock_openai):
        """Test routing with o1 model (different parameters)."""
        config_o1 = self.mock_config.copy()
        config_o1["openai"]["model"] = "o1-preview"

        mock_message = Mock()
        mock_message.content = json.dumps({
            "route": "resolve",
            "confidence": 0.9,
            "reasoning": "o1 model test",
            "fallback_route": "search"
        })

        mock_choice = Mock()
        mock_choice.message = mock_message

        mock_response = Mock()
        mock_response.choices = [mock_choice]

        mock_client = Mock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai.return_value = mock_client

        router = IntentRouter(config_o1)
        result = router.route("test query")

        # Verify o1-specific parameters were used
        call_args = mock_client.chat.completions.create.call_args[1]
        self.assertEqual(call_args["model"], "o1-preview")
        self.assertIn("max_completion_tokens", call_args)
        self.assertNotIn("temperature", call_args)

    def test_should_use_fallback(self):
        """Test fallback decision logic."""
        router = IntentRouter(self.mock_config)

        # High confidence - no fallback
        decision_high = {"confidence": 0.9}
        self.assertFalse(router.should_use_fallback(decision_high))

        # Low confidence - use fallback
        decision_low = {"confidence": 0.7}
        self.assertTrue(router.should_use_fallback(decision_low))

        # Edge case
        decision_edge = {"confidence": 0.8}
        self.assertFalse(router.should_use_fallback(decision_edge))

    def test_build_history_context_empty(self):
        """Test building context with no history."""
        router = IntentRouter(self.mock_config)
        context = router._build_history_context(None)
        self.assertEqual(context, "")

    def test_build_history_context_with_failures(self):
        """Test building context with past failures."""
        router = IntentRouter(self.mock_config)

        context = {
            "past_failures": [
                {"query": "wrong song", "route": "resolve", "reason": "Not found"}
            ],
            "session_history": [
                {"query": "good song", "success": True}
            ]
        }

        context_str = router._build_history_context(context)
        self.assertIn("PAST FAILURES", context_str)
        self.assertIn("wrong song", context_str)
        self.assertIn("RECENT QUERIES", context_str)
        self.assertIn("good song", context_str)
        self.assertIn("SUCCESS", context_str)


if __name__ == '__main__':
    unittest.main()
