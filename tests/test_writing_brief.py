"""
Test suite for WritingBrief SessionContext integration.

Tests:
1. WritingBrief accepts SessionContext parameter
2. Context data auto-populates brief fields
3. prepare_writing_brief uses SessionContext
4. synthesize_content derives topics from context
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from unittest.mock import Mock, patch

from src.agent.writing_agent import WritingBrief, prepare_writing_brief, synthesize_content
from src.memory.session_memory import SessionContext


class TestWritingBriefContextIntegration:
    """Test WritingBrief's integration with SessionContext."""

    def test_writing_brief_accepts_session_context(self):
        """Test WritingBrief constructor accepts SessionContext."""
        context = SessionContext(
            original_query="Write a report on AI trends",
            session_id="test_123",
            context_objects={
                "user_context": {"audience_hint": "technical", "tone_hint": "professional"}
            }
        )

        brief = WritingBrief(session_context=context)

        # Should auto-populate from context
        assert brief.audience == "technical"
        assert brief.tone == "professional"
        assert brief.focus_areas == ["Write a report on AI trends"]  # Derived topic

    def test_writing_brief_context_override(self):
        """Test explicit parameters override context defaults."""
        context = SessionContext(
            original_query="Write about AI",
            session_id="test_123",
            context_objects={
                "user_context": {"audience_hint": "technical", "tone_hint": "formal"}
            }
        )

        brief = WritingBrief(
            audience="executive",  # Override context
            tone="casual",         # Override context
            session_context=context
        )

        # Explicit parameters should take precedence
        assert brief.audience == "executive"
        assert brief.tone == "casual"

    def test_writing_brief_token_budget_from_context(self):
        """Test token budget metadata flows to brief constraints."""
        context = SessionContext(
            original_query="Summarize the report",
            session_id="test_123",
            token_budget_metadata={"profile": "compact", "max_tokens": 1000}
        )

        brief = WritingBrief(session_context=context)

        assert brief.constraints == {"max_tokens": 1000, "profile": "compact"}

    def test_writing_brief_topic_derivation(self):
        """Test topic derivation from context headlines."""
        context = SessionContext(
            original_query="Why did sales drop last quarter?",
            session_id="test_123"
        )

        brief = WritingBrief(session_context=context)

        assert brief.focus_areas == ["Why sales dropped last quarter"]

    def test_writing_brief_serialization_with_context(self):
        """Test brief serialization preserves context-influenced fields."""
        context = SessionContext(
            original_query="Analyze market trends",
            session_id="test_123",
            context_objects={
                "user_context": {"audience_hint": "business"}
            }
        )

        brief = WritingBrief(session_context=context)
        data = brief.to_dict()

        assert data["audience"] == "business"
        assert data["focus_areas"] == ["Analysis: market trends"]


class TestPrepareWritingBrief:
    """Test prepare_writing_brief with SessionContext."""

    @patch('src.agent.writing_agent.ChatOpenAI')
    def test_prepare_brief_with_context(self, mock_llm_class):
        """Test prepare_writing_brief enhances brief with SessionContext."""
        # Mock LLM response
        mock_llm = Mock()
        mock_response = Mock()
        mock_response.content = '''
        {
          "writing_brief": {
            "deliverable_type": "report",
            "tone": "professional",
            "audience": "executive",
            "length_guideline": "comprehensive",
            "must_include_facts": ["Revenue increased 15%"],
            "focus_areas": ["Financial performance"]
          },
          "analysis": "Created comprehensive brief",
          "confidence_score": 0.9
        }
        '''
        mock_llm.invoke.return_value = mock_response
        mock_llm_class.return_value = mock_llm

        context = SessionContext(
            original_query="Write a financial report",
            session_id="test_123",
            context_objects={
                "user_context": {"audience_hint": "technical", "tone_hint": "formal"}
            },
            token_budget_metadata={"profile": "reasoning"}
        )

        result = prepare_writing_brief(
            user_request="Create financial report",
            deliverable_type="report",
            session_context=context
        )

        # Should have session_context_used flag
        assert result.get("session_context_used") is True

        # Brief should be enhanced
        brief_data = result["writing_brief"]
        assert brief_data["audience"] == "executive"  # From LLM response
        assert brief_data["tone"] == "professional"   # From LLM response

    @patch('src.agent.writing_agent.ChatOpenAI')
    def test_prepare_brief_without_context(self, mock_llm_class):
        """Test prepare_writing_brief works without SessionContext."""
        # Mock LLM response
        mock_llm = Mock()
        mock_response = Mock()
        mock_response.content = '''
        {
          "writing_brief": {
            "deliverable_type": "summary",
            "tone": "neutral",
            "audience": "general"
          },
          "analysis": "Basic brief created",
          "confidence_score": 0.8
        }
        '''
        mock_llm.invoke.return_value = mock_response
        mock_llm_class.return_value = mock_llm

        result = prepare_writing_brief(
            user_request="Summarize the article",
            deliverable_type="summary"
        )

        assert result["writing_brief"]["deliverable_type"] == "summary"
        assert "session_context_used" not in result


class TestSynthesizeContent:
    """Test synthesize_content with SessionContext."""

    def test_synthesize_content_derives_topic(self):
        """Test synthesize_content derives topic from SessionContext."""
        context = SessionContext(
            original_query="Why did the stock market crash?",
            session_id="test_123"
        )

        # Mock the synthesize_content function to avoid actual LLM calls
        with patch('src.agent.writing_agent.ChatOpenAI') as mock_llm_class:
            mock_llm = Mock()
            mock_response = Mock()
            mock_response.content = '{"synthesized_content": "Market analysis..."}'
            mock_llm.invoke.return_value = mock_response
            mock_llm_class.return_value = mock_llm

            result = synthesize_content(
                source_contents=["Market data..."],
                session_context=context
            )

            # Verify topic was derived
            assert mock_llm.invoke.called
            call_args = mock_llm.invoke.call_args
            messages = call_args[0][0]
            prompt_text = messages[1].content

            # Should contain the derived topic
            assert "Why stock market crashed" in prompt_text

    def test_synthesize_content_explicit_topic_overrides(self):
        """Test explicit topic parameter overrides context-derived topic."""
        context = SessionContext(
            original_query="Why did sales drop?",
            session_id="test_123"
        )

        with patch('src.agent.writing_agent.ChatOpenAI') as mock_llm_class:
            mock_llm = Mock()
            mock_response = Mock()
            mock_response.content = '{"synthesized_content": "Analysis..."}'
            mock_llm.invoke.return_value = mock_response
            mock_llm_class.return_value = mock_llm

            result = synthesize_content(
                source_contents=["Sales data..."],
                topic="Quarterly Revenue Analysis",  # Explicit topic
                session_context=context
            )

            assert mock_llm.invoke.called
            call_args = mock_llm.invoke.call_args
            messages = call_args[0][0]
            prompt_text = messages[1].content

            # Should use explicit topic, not derived one
            assert "Quarterly Revenue Analysis" in prompt_text

    @patch('src.agent.writing_agent.ChatOpenAI')
    def test_synthesize_content_without_context(self, mock_llm_class):
        """Test synthesize_content works without SessionContext."""
        mock_llm = Mock()
        mock_response = Mock()
        mock_response.content = '{"synthesized_content": "Summary..."}'
        mock_llm.invoke.return_value = mock_response
        mock_llm_class.return_value = mock_llm

        result = synthesize_content(
            source_contents=["Content to summarize"],
            topic="Manual Topic"
        )

        assert mock_llm.invoke.called


class TestWritingBriefPromptGeneration:
    """Test WritingBrief prompt generation with context."""

    def test_to_prompt_section_with_context_data(self):
        """Test prompt section includes context-influenced fields."""
        context = SessionContext(
            original_query="Write a technical analysis",
            session_id="test_123",
            context_objects={
                "user_context": {"audience_hint": "expert"}
            },
            token_budget_metadata={"profile": "reasoning", "max_tokens": 3000}
        )

        brief = WritingBrief(
            deliverable_type="report",
            tone="technical",
            session_context=context
        )

        prompt = brief.to_prompt_section()

        assert "DELIVERABLE TYPE: report" in prompt
        assert "TONE: technical" in prompt
        assert "AUDIENCE: expert" in prompt  # From context
        assert "max_tokens" in prompt  # From token budget


class TestIntegration:
    """Integration tests for writing components with SessionContext."""

    def test_full_writing_workflow_with_context(self):
        """Test complete writing workflow using SessionContext."""
        context = SessionContext(
            original_query="Create a summary of the quarterly earnings",
            session_id="test_123",
            derived_topic="Quarterly Earnings Summary",
            context_objects={
                "user_context": {"audience_hint": "executive", "tone_hint": "professional"},
                "financial_data": {"revenue": "$10M", "growth": "15%"}
            }
        )

        # Create brief with context
        brief = WritingBrief(
            deliverable_type="summary",
            session_context=context
        )

        # Verify brief was populated correctly
        assert brief.audience == "executive"
        assert brief.tone == "professional"
        assert brief.focus_areas == ["Quarterly Earnings Summary"]

        # Test serialization round-trip
        data = brief.to_dict()
        reconstructed = WritingBrief.from_dict(data)

        assert reconstructed.audience == brief.audience
        assert reconstructed.tone == brief.tone
        assert reconstructed.focus_areas == brief.focus_areas
