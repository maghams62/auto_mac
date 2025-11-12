"""
Unit tests for Calendar Agent.

Tests calendar event reading and meeting brief preparation with mocked dependencies.
"""

import sys
import json
import os
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import pytest

from src.agent.calendar_agent import (
    CalendarAgent,
    list_calendar_events,
    get_calendar_event_details,
    prepare_meeting_brief
)


@pytest.fixture
def mock_config():
    """Create a mock config for testing."""
    return {
        "openai": {
            "api_key": "test-key",
            "model": "gpt-4o",
            "embedding_model": "text-embedding-3-small",
            "temperature": 0.3
        },
        "documents": {
            "folders": ["tests/data/test_docs"],
            "supported_types": [".pdf", ".docx", ".txt"]
        },
        "search": {
            "top_k": 5,
            "similarity_threshold": 0.5
        }
    }


@pytest.fixture
def sample_event():
    """Sample calendar event for testing."""
    return {
        "title": "Q4 Review Meeting",
        "start_time": "2024-12-20T14:00:00",
        "end_time": "2024-12-20T15:00:00",
        "location": "Conference Room A",
        "notes": "Discuss revenue and marketing strategy",
        "attendees": ["John Doe", "Jane Smith"],
        "calendar_name": "Work",
        "event_id": "12345"
    }


@pytest.fixture
def sample_events(sample_event):
    """Sample list of calendar events."""
    return [sample_event]


def test_list_calendar_events(mock_config, sample_events):
    """Test list_calendar_events tool."""
    with patch('src.agent.calendar_agent._load_calendar_runtime') as mock_load:
        mock_calendar_automation = Mock()
        mock_calendar_automation.list_events.return_value = sample_events
        mock_load.return_value = (mock_config, mock_calendar_automation)

        result = list_calendar_events.invoke({"days_ahead": 7})

        assert result["count"] == 1
        assert len(result["events"]) == 1
        assert result["events"][0]["title"] == "Q4 Review Meeting"
        assert result["days_ahead"] == 7
        mock_calendar_automation.list_events.assert_called_once_with(days_ahead=7)


def test_list_calendar_events_limit_days(mock_config, sample_events):
    """Test that days_ahead is limited to 30."""
    with patch('src.agent.calendar_agent._load_calendar_runtime') as mock_load:
        mock_calendar_automation = Mock()
        mock_calendar_automation.list_events.return_value = sample_events
        mock_load.return_value = (mock_config, mock_calendar_automation)

        result = list_calendar_events.invoke({"days_ahead": 100})

        # Should be limited to 30
        mock_calendar_automation.list_events.assert_called_once_with(days_ahead=30)


def test_get_calendar_event_details(mock_config, sample_event):
    """Test get_calendar_event_details tool."""
    with patch('src.agent.calendar_agent._load_calendar_runtime') as mock_load:
        mock_calendar_automation = Mock()
        mock_calendar_automation.get_event_details.return_value = sample_event
        mock_load.return_value = (mock_config, mock_calendar_automation)

        result = get_calendar_event_details.invoke({
            "event_title": "Q4 Review"
        })

        assert result["found"] is True
        assert result["event"]["title"] == "Q4 Review Meeting"
        mock_calendar_automation.get_event_details.assert_called_once()


def test_get_calendar_event_details_not_found(mock_config):
    """Test get_calendar_event_details when event not found."""
    with patch('src.agent.calendar_agent._load_calendar_runtime') as mock_load:
        mock_calendar_automation = Mock()
        mock_calendar_automation.get_event_details.return_value = {}
        mock_load.return_value = (mock_config, mock_calendar_automation)

        result = get_calendar_event_details.invoke({
            "event_title": "Non-existent Meeting"
        })

        assert result["found"] is False
        assert result["event"] == {}


@patch('src.agent.calendar_agent.OpenAI')
@patch('src.agent.calendar_agent.DocumentIndexer')
@patch('src.agent.calendar_agent.SemanticSearch')
def test_prepare_meeting_brief(mock_semantic_search, mock_indexer, mock_openai, mock_config, sample_event):
    """Test prepare_meeting_brief tool with mocked dependencies."""
    with patch('src.agent.calendar_agent._load_calendar_runtime') as mock_load:
        # Setup mocks
        mock_calendar_automation = Mock()
        mock_calendar_automation.get_event_details.return_value = sample_event
        mock_calendar_automation.export_event_context.return_value = {
            "title": sample_event["title"],
            "notes": sample_event["notes"],
            "attendees": sample_event["attendees"],
            "location": sample_event["location"],
            "start_time": sample_event["start_time"]
        }
        mock_load.return_value = (mock_config, mock_calendar_automation)

        # Mock OpenAI client
        mock_client_instance = Mock()
        mock_openai.return_value = mock_client_instance
        mock_client_instance.chat.completions.create.return_value = Mock(
            choices=[Mock(message=Mock(content='["Q4 revenue report", "marketing strategy 2024"]'))]
        )

        # Mock DocumentIndexer
        mock_indexer_instance = Mock()
        mock_indexer_instance.index = Mock(ntotal=100)
        mock_indexer_instance.documents = [{"content": "test"}]
        mock_indexer.return_value = mock_indexer_instance

        # Mock SemanticSearch
        mock_search_instance = Mock()
        mock_search_instance.search.return_value = [
            {
                "file_path": "/path/to/q4_report.pdf",
                "file_name": "Q4_Report.pdf",
                "similarity": 0.85,
                "content_preview": "Q4 revenue was strong..."
            }
        ]
        mock_semantic_search.return_value = mock_search_instance

        # Mock Writing Agent synthesize_content
        with patch('src.agent.calendar_agent.synthesize_content') as mock_synthesize:
            mock_synthesize.invoke.return_value = {
                "synthesized_content": "Meeting Brief: Q4 Review\n\nKey points..."
            }

            result = prepare_meeting_brief.invoke({
                "event_title": "Q4 Review",
                "save_to_note": False
            })

            assert "brief" in result
            assert result["event"]["title"] == "Q4 Review Meeting"
            assert len(result["relevant_docs"]) > 0
            assert "search_queries" in result
            assert result["note_saved"] is False


@patch('src.agent.calendar_agent.OpenAI')
def test_prepare_meeting_brief_event_not_found(mock_openai, mock_config):
    """Test prepare_meeting_brief when event is not found."""
    with patch('src.agent.calendar_agent._load_calendar_runtime') as mock_load:
        mock_calendar_automation = Mock()
        mock_calendar_automation.get_event_details.return_value = {}
        mock_load.return_value = (mock_config, mock_calendar_automation)

        result = prepare_meeting_brief.invoke({
            "event_title": "Non-existent Meeting"
        })

        assert result["error"] is True
        assert result["error_type"] == "EventNotFound"


def test_calendar_agent_execute(mock_config, sample_events):
    """Test CalendarAgent.execute method."""
    with patch('src.agent.calendar_agent._load_calendar_runtime') as mock_load:
        mock_calendar_automation = Mock()
        mock_calendar_automation.list_events.return_value = sample_events
        mock_load.return_value = (mock_config, mock_calendar_automation)

        agent = CalendarAgent(mock_config)
        result = agent.execute("list_calendar_events", {"days_ahead": 7})

        assert result["count"] == 1
        assert len(result["events"]) == 1


def test_calendar_agent_execute_unknown_tool(mock_config):
    """Test CalendarAgent.execute with unknown tool."""
    agent = CalendarAgent(mock_config)
    result = agent.execute("unknown_tool", {})

    assert result["error"] is True
    assert result["error_type"] == "ToolNotFound"


def test_calendar_agent_get_tools(mock_config):
    """Test CalendarAgent.get_tools method."""
    agent = CalendarAgent(mock_config)
    tools = agent.get_tools()

    assert len(tools) == 3
    assert any(tool.name == "list_calendar_events" for tool in tools)
    assert any(tool.name == "get_calendar_event_details" for tool in tools)
    assert any(tool.name == "prepare_meeting_brief" for tool in tools)


def test_calendar_agent_get_hierarchy(mock_config):
    """Test CalendarAgent.get_hierarchy method."""
    agent = CalendarAgent(mock_config)
    hierarchy = agent.get_hierarchy()

    assert "Calendar Agent Hierarchy" in hierarchy
    assert "LEVEL 1" in hierarchy
    assert "LEVEL 2" in hierarchy
    assert "list_calendar_events" in hierarchy
    assert "prepare_meeting_brief" in hierarchy


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

