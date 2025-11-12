"""
Integration tests for Calendar Agent.

Tests end-to-end calendar workflows with fake data and sample documents.
"""

import sys
import json
import os
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import pytest

from src.agent.calendar_agent import CalendarAgent, prepare_meeting_brief
from src.automation.calendar_automation import CalendarAutomation


@pytest.fixture
def fake_calendar_data(tmp_path):
    """Create fake calendar data JSON file."""
    fake_data = [
        {
            "title": "Q4 Review Meeting",
            "start_time": "2024-12-20T14:00:00",
            "end_time": "2024-12-20T15:00:00",
            "location": "Conference Room A",
            "notes": "Discuss revenue and marketing strategy",
            "attendees": ["John Doe", "Jane Smith"],
            "calendar_name": "Work",
            "event_id": "12345"
        },
        {
            "title": "Team Standup",
            "start_time": "2024-12-21T09:00:00",
            "end_time": "2024-12-21T09:30:00",
            "location": "Zoom",
            "notes": "Daily sync on project progress",
            "attendees": ["Team"],
            "calendar_name": "Work",
            "event_id": "12346"
        }
    ]
    
    fake_file = tmp_path / "fake_calendar.json"
    with open(fake_file, 'w') as f:
        json.dump(fake_data, f)
    
    return str(fake_file)


@pytest.fixture
def test_config(tmp_path):
    """Create test config with test document folder."""
    test_docs_dir = tmp_path / "test_docs"
    test_docs_dir.mkdir()
    
    # Create a sample document
    sample_doc = test_docs_dir / "q4_report.txt"
    sample_doc.write_text("Q4 Revenue Report\n\nRevenue: $10M\nMarketing Strategy: Focus on digital channels")
    
    return {
        "openai": {
            "api_key": "test-key",
            "model": "gpt-4o",
            "embedding_model": "text-embedding-3-small",
            "temperature": 0.3
        },
        "documents": {
            "folders": [str(test_docs_dir)],
            "supported_types": [".txt", ".pdf", ".docx"]
        },
        "search": {
            "top_k": 5,
            "similarity_threshold": 0.5
        }
    }


def test_calendar_automation_fake_data(fake_calendar_data, test_config):
    """Test CalendarAutomation with fake data."""
    os.environ["CALENDAR_FAKE_DATA_PATH"] = fake_calendar_data
    
    automation = CalendarAutomation(test_config)
    events = automation.list_events(days_ahead=7)
    
    assert len(events) == 2
    assert events[0]["title"] == "Q4 Review Meeting"
    assert events[1]["title"] == "Team Standup"
    
    # Clean up
    del os.environ["CALENDAR_FAKE_DATA_PATH"]


def test_calendar_automation_get_event_details(fake_calendar_data, test_config):
    """Test CalendarAutomation.get_event_details with fake data."""
    os.environ["CALENDAR_FAKE_DATA_PATH"] = fake_calendar_data
    
    automation = CalendarAutomation(test_config)
    event = automation.get_event_details("Q4 Review")
    
    assert event["title"] == "Q4 Review Meeting"
    assert event["notes"] == "Discuss revenue and marketing strategy"
    assert len(event["attendees"]) == 2
    
    # Clean up
    del os.environ["CALENDAR_FAKE_DATA_PATH"]


def test_calendar_automation_export_event_context(test_config):
    """Test CalendarAutomation.export_event_context."""
    automation = CalendarAutomation(test_config)
    
    event = {
        "title": "Test Meeting",
        "start_time": "2024-12-20T14:00:00",
        "end_time": "2024-12-20T15:00:00",
        "location": "Room 1",
        "notes": "Test notes",
        "attendees": ["Alice", "Bob"],
        "calendar_name": "Work"
    }
    
    context = automation.export_event_context(event)
    
    assert context["title"] == "Test Meeting"
    assert context["notes"] == "Test notes"
    assert "summary" in context
    assert "Event: Test Meeting" in context["summary"]


@patch('src.agent.calendar_agent.OpenAI')
@patch('src.agent.calendar_agent.DocumentIndexer')
@patch('src.agent.calendar_agent.SemanticSearch')
def test_prepare_meeting_brief_integration(mock_semantic_search, mock_indexer, mock_openai, 
                                           fake_calendar_data, test_config):
    """Test prepare_meeting_brief end-to-end with fake calendar data."""
    os.environ["CALENDAR_FAKE_DATA_PATH"] = fake_calendar_data
    
    # Mock OpenAI for query generation
    mock_client = Mock()
    mock_openai.return_value = mock_client
    mock_client.chat.completions.create.return_value = Mock(
        choices=[Mock(message=Mock(content='["Q4 revenue report", "marketing strategy"]'))]
    )
    
    # Mock DocumentIndexer
    mock_indexer_instance = Mock()
    mock_indexer_instance.index = Mock(ntotal=10)
    mock_indexer_instance.documents = [{"content": "test"}]
    mock_indexer.return_value = mock_indexer_instance
    
    # Mock SemanticSearch
    mock_search_instance = Mock()
    mock_search_instance.search.return_value = [
        {
            "file_path": "/path/to/q4_report.txt",
            "file_name": "q4_report.txt",
            "similarity": 0.85,
            "content_preview": "Q4 revenue was strong..."
        }
    ]
    mock_semantic_search.return_value = mock_search_instance
    
    # Mock Writing Agent
    with patch('src.agent.calendar_agent.synthesize_content') as mock_synthesize:
        mock_synthesize.invoke.return_value = {
            "synthesized_content": "Meeting Brief: Q4 Review\n\nKey points about revenue and marketing."
        }
        
        agent = CalendarAgent(test_config)
        result = agent.execute("prepare_meeting_brief", {
            "event_title": "Q4 Review",
            "save_to_note": False
        })
        
        assert "brief" in result
        assert result["event"]["title"] == "Q4 Review Meeting"
        assert len(result["relevant_docs"]) > 0
        assert len(result["search_queries"]) > 0
        assert "Q4 revenue report" in result["search_queries"]
    
    # Clean up
    del os.environ["CALENDAR_FAKE_DATA_PATH"]


def test_calendar_slash_command_routing():
    """Test calendar slash command routing."""
    from src.ui.slash_commands import SlashCommandHandler
    
    config = {"documents": {"folders": []}}
    
    class MockRegistry:
        def execute_tool(self, tool_name, params, session_id=None):
            return {"tool": tool_name, "params": params}
    
    handler = SlashCommandHandler(MockRegistry(), config=config)
    
    # Test prep command
    tool, params, msg = handler._route_calendar_command("prep for Q4 Review meeting")
    assert tool == "prepare_meeting_brief"
    assert params["event_title"] == "Q4 Review"
    
    # Test list command
    tool, params, msg = handler._route_calendar_command("list upcoming events")
    assert tool == "list_calendar_events"
    assert params["days_ahead"] == 7
    
    # Test details command
    tool, params, msg = handler._route_calendar_command('details for "Project Kickoff"')
    assert tool == "get_calendar_event_details"
    assert "Project Kickoff" in params["event_title"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

