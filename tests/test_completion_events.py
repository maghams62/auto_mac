"""
Tests for task completion event system.

Verifies that completion events are properly generated and serialized.
"""

import pytest
from src.agent.reply_tool import reply_to_user


def test_reply_to_user_without_completion_event():
    """Test that reply_to_user works without completion event parameters."""
    result = reply_to_user.invoke({
        "message": "Task completed",
        "status": "success"
    })
    
    assert result["type"] == "reply"
    assert result["message"] == "Task completed"
    assert result["status"] == "success"
    assert "completion_event" not in result


def test_reply_to_user_with_completion_event():
    """Test that reply_to_user generates completion_event when action_type is provided."""
    result = reply_to_user.invoke({
        "message": "Email sent successfully!",
        "action_type": "email_sent",
        "summary": "Your email has been delivered",
        "artifact_metadata": {
            "recipients": ["user@example.com"],
            "subject": "Test Email"
        },
        "artifacts": ["/path/to/file.pdf"],
        "status": "success"
    })
    
    assert result["type"] == "reply"
    assert "completion_event" in result
    
    event = result["completion_event"]
    assert event["action_type"] == "email_sent"
    assert event["summary"] == "Your email has been delivered"
    assert event["status"] == "success"
    assert event["artifact_metadata"]["recipients"] == ["user@example.com"]
    assert event["artifact_metadata"]["subject"] == "Test Email"
    assert event["artifacts"] == ["/path/to/file.pdf"]


def test_reply_to_user_completion_event_defaults():
    """Test that completion_event uses message as summary if summary not provided."""
    result = reply_to_user.invoke({
        "message": "Report created!",
        "action_type": "report_created",
        "status": "success"
    })
    
    assert "completion_event" in result
    assert result["completion_event"]["summary"] == "Report created!"
    assert result["completion_event"]["action_type"] == "report_created"


def test_reply_to_user_completion_event_empty_metadata():
    """Test that completion_event handles empty artifact_metadata gracefully."""
    result = reply_to_user.invoke({
        "message": "Task done",
        "action_type": "file_saved",
        "status": "success",
        "artifact_metadata": {}
    })
    
    assert "completion_event" in result
    assert result["completion_event"]["artifact_metadata"] == {}


def test_reply_to_user_completion_event_multiple_artifacts():
    """Test completion_event with multiple artifacts."""
    result = reply_to_user.invoke({
        "message": "Files saved",
        "action_type": "file_saved",
        "artifacts": ["/path/to/file1.pdf", "/path/to/file2.pdf"],
        "status": "success"
    })
    
    assert "completion_event" in result
    assert len(result["completion_event"]["artifacts"]) == 2
    assert "/path/to/file1.pdf" in result["completion_event"]["artifacts"]
    assert "/path/to/file2.pdf" in result["completion_event"]["artifacts"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

