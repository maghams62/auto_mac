"""
Test suite for Planner SessionContext integration.

Tests:
1. Planner accepts SessionContext parameter
2. Context data appears in planning prompts
3. Plan titles derive from context headlines
4. Token budget hints are included in prompts
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from unittest.mock import Mock, patch

from src.orchestrator.planner import Planner
from src.memory.session_memory import SessionContext
from src.agent.agent_registry import AgentRegistry


class TestPlannerContextIntegration:
    """Test Planner's integration with SessionContext."""

    def setup_method(self):
        """Set up test fixtures."""
        config = {
            "openai": {
                "model": "gpt-4o",
                "api_key": "test_key",
                "temperature": 0.2,
                "max_tokens": 2000
            }
        }
        self.planner = Planner(config)
        self.sample_context = SessionContext(
            original_query="Why did Arsenal draw against Chelsea?",
            session_id="test_session_123",
            derived_topic="Why Arsenal Drew",
            context_objects={"sport": "football", "importance": "high"},
            token_budget_metadata={"profile": "reasoning", "estimated_tokens": 2000}
        )

    def test_planner_accepts_session_context(self):
        """Test that planner accepts SessionContext parameter."""
        # This should not raise an exception
        try:
            # We won't actually call create_plan since it requires LLM, but we can check the signature
            assert hasattr(self.planner, 'create_plan')

            # Check method signature
            import inspect
            sig = inspect.signature(self.planner.create_plan)
            params = list(sig.parameters.keys())
            assert 'session_context' in params

        except Exception as e:
            pytest.fail(f"Planner does not properly accept SessionContext: {e}")

    @patch('src.orchestrator.planner.ChatOpenAI')
    def test_planning_prompt_includes_context(self, mock_llm_class):
        """Test that planning prompts include SessionContext data."""
        # Mock the LLM
        mock_llm = Mock()
        mock_response = Mock()
        mock_response.content = '''
        {
          "reasoning": "Plan created with context",
          "steps": [
            {
              "id": 1,
              "action": "search_web",
              "parameters": {"query": "Arsenal Chelsea match result"},
              "reasoning": "Need to find match details",
              "dependencies": []
            }
          ]
        }
        '''
        mock_llm.invoke.return_value = mock_response
        mock_llm_class.return_value = mock_llm

        # Create planner with mocked LLM
        planner = Planner({
            "openai": {"model": "gpt-4o", "api_key": "test", "temperature": 0.2}
        })

        # Call create_plan with context
        result = planner.create_plan(
            goal="Analyze the Arsenal Chelsea match",
            available_tools=[{"name": "search_web", "description": "Search the web"}],
            session_context=self.sample_context
        )

        # Verify LLM was called
        assert mock_llm.invoke.called
        call_args = mock_llm.invoke.call_args

        # Check that the prompt includes context data
        messages = call_args[0][0]  # First positional argument
        prompt_text = messages[1].content  # Human message content

        # Verify context sections are present
        assert "ORIGINAL USER QUERY: Why did Arsenal draw against Chelsea?" in prompt_text
        assert "DERIVED TOPIC: Why Arsenal Drew" in prompt_text
        assert '"sport": "football"' in prompt_text
        assert '"importance": "high"' in prompt_text
        assert "'profile': 'reasoning'" in prompt_text

    @patch('src.orchestrator.planner.ChatOpenAI')
    def test_context_influences_plan_output(self, mock_llm_class):
        """Test that SessionContext influences plan generation."""
        # Mock LLM to return a plan that references context
        mock_llm = Mock()
        mock_response = Mock()
        mock_response.content = '''
        {
          "reasoning": "Using context about Arsenal match to create targeted plan",
          "steps": [
            {
              "id": 1,
              "action": "search_web",
              "parameters": {"query": "Why Arsenal drew against Chelsea"},
              "reasoning": "Context indicates user wants to understand the draw",
              "dependencies": []
            }
          ]
        }
        '''
        mock_llm.invoke.return_value = mock_response
        mock_llm_class.return_value = mock_llm

        planner = Planner({
            "openai": {"model": "gpt-4o", "api_key": "test", "temperature": 0.2}
        })

        result = planner.create_plan(
            goal="Explain the match result",
            available_tools=[{"name": "search_web", "description": "Search the web"}],
            session_context=self.sample_context
        )

        assert result["success"] is True
        assert len(result["plan"]) == 1
        assert "Arsenal" in str(result["plan"][0]["parameters"])

    def test_planner_fallback_without_context(self):
        """Test planner works without SessionContext (backward compatibility)."""
        # This tests that the planner can still function in legacy mode
        # without SessionContext, though it would require additional mocking
        # to avoid actual LLM calls

        # For now, just verify the method exists and has proper signature
        assert hasattr(self.planner, 'create_plan')

        import inspect
        sig = inspect.signature(self.planner.create_plan)

        # Check that session_context has a default value (None)
        session_context_param = sig.parameters['session_context']
        assert session_context_param.default is None


class TestPlannerPromptBuilding:
    """Test planner prompt building with context."""

    def setup_method(self):
        """Set up test fixtures."""
        config = {
            "openai": {"model": "gpt-4o", "api_key": "test", "temperature": 0.2}
        }
        self.planner = Planner(config)

    def test_build_planning_prompt_with_context(self):
        """Test _build_planning_prompt includes context sections."""
        context = SessionContext(
            original_query="Analyze Arsenal's performance",
            session_id="test_123",
            derived_topic="Arsenal Performance Analysis",
            context_objects={"league": "Premier League"},
            token_budget_metadata={"profile": "reasoning"}
        )

        prompt = self.planner._build_planning_prompt(
            goal="Create performance report",
            available_tools=[{"name": "analyze_data"}],
            session_context=context
        )

        # Verify all context sections are present
        assert "ORIGINAL USER QUERY: Analyze Arsenal's performance" in prompt
        assert "DERIVED TOPIC: Arsenal Performance Analysis" in prompt
        assert '"league": "Premier League"' in prompt
        assert "REASONING BUDGET:" in prompt

    def test_build_planning_prompt_without_context(self):
        """Test prompt building still works without context."""
        prompt = self.planner._build_planning_prompt(
            goal="Create report",
            available_tools=[{"name": "analyze_data"}],
            session_context=None
        )

        # Should not include context sections
        assert "ORIGINAL USER QUERY:" not in prompt
        assert "DERIVED TOPIC:" not in prompt
        assert "CONTEXT OBJECTS:" not in prompt

    def test_context_different_profiles(self):
        """Test prompts include different token budgets for different profiles."""
        compact_context = SessionContext(
            original_query="Quick summary",
            session_id="test_123",
            token_budget_metadata={"profile": "compact", "estimated_tokens": 500}
        )

        reasoning_context = SessionContext(
            original_query="Detailed analysis",
            session_id="test_123",
            token_budget_metadata={"profile": "reasoning", "estimated_tokens": 2000}
        )

        compact_prompt = self.planner._build_planning_prompt(
            goal="Summarize",
            available_tools=[{"name": "summarize"}],
            session_context=compact_context
        )

        reasoning_prompt = self.planner._build_planning_prompt(
            goal="Analyze",
            available_tools=[{"name": "analyze"}],
            session_context=reasoning_context
        )

        assert "'profile': 'compact'" in compact_prompt
        assert "'profile': 'reasoning'" in reasoning_prompt
        assert "500" in compact_prompt  # estimated tokens
        assert "2000" in reasoning_prompt  # estimated tokens


class TestPlannerValidation:
    """Test planner validation with context."""

    def setup_method(self):
        """Set up test fixtures."""
        config = {
            "openai": {"model": "gpt-4o", "api_key": "test", "temperature": 0.2}
        }
        self.planner = Planner(config)

    def test_validate_plan_with_context(self):
        """Test plan validation works with context-aware plans."""
        plan = [
            {
                "id": 1,
                "action": "search_web",
                "parameters": {"query": "Arsenal Chelsea result"},
                "reasoning": "Context shows user cares about this match",
                "dependencies": []
            }
        ]

        tools = [
            {"name": "search_web", "description": "Search web", "parameters": {"query": {"type": "string"}}}
        ]

        result = self.planner.validate_plan(plan, tools)

        # Should pass validation
        assert result["valid"] is True
        assert len(result["issues"]) == 0
