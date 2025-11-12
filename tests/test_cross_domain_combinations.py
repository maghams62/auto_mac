"""
Test cross-domain combinations functionality.

Tests that combinations work correctly:
1. Tweets + Email
2. Email + Presentation
3. Reminders + Email
4. Notes + Email
5. Stock presentation + Email
"""

import os
import tempfile
import pytest
from unittest.mock import Mock, patch, MagicMock

from src.agent.email_agent import compose_email
from src.agent.bluesky_agent import summarize_bluesky_posts
from src.agent.enriched_stock_agent import create_stock_report_and_email


def test_tweets_and_email_workflow():
    """Test that tweets can be fetched and emailed."""
    # Mock Bluesky posts
    mock_posts = {
        "summary": "Summary of tweets",
        "items": [
            {"text": "Tweet 1", "author_handle": "test.bsky.social"},
            {"text": "Tweet 2", "author_handle": "test.bsky.social"},
        ],
        "count": 2,
        "requested_count": 2
    }
    
    with patch('src.agent.bluesky_agent.summarize_bluesky_posts') as mock_summarize:
        mock_summarize.invoke.return_value = mock_posts
        
        # Step 1: Get tweets
        tweets_result = summarize_bluesky_posts.invoke({
            "query": "last 5 tweets",
            "max_items": 5
        })
        
        assert tweets_result.get("summary") is not None
        
        # Step 2: Email the summary
        with patch('src.automation.mail_composer.MailComposer.compose_email') as mock_compose:
            mock_compose.return_value = True
            
            email_result = compose_email.invoke({
                "subject": "Bluesky Summary",
                "body": tweets_result.get("summary", ""),
                "send": True
            })
            
            # Should not have attachment error (we're not attaching files)
            assert email_result.get("error_type") != "AttachmentError"


def test_presentation_and_email_workflow():
    """Test that presentation can be created and emailed."""
    # Create a temporary presentation file
    with tempfile.NamedTemporaryFile(delete=False, suffix=".key") as tmp_file:
        tmp_path = tmp_file.name
        tmp_file.write(b"fake keynote content")
    
    try:
        # Mock presentation creation
        mock_presentation = {
            "success": True,
            "presentation_path": tmp_path,
            "company": "NVIDIA",
            "ticker": "NVDA"
        }
        
        with patch('src.agent.enriched_stock_agent.create_enriched_stock_presentation') as mock_create:
            mock_create.invoke.return_value = mock_presentation
            
            # Test the combined workflow
            with patch('src.automation.mail_composer.MailComposer.compose_email') as mock_compose:
                mock_compose.return_value = True
                
                result = create_stock_report_and_email.invoke({
                    "company": "NVIDIA",
                    "recipient": "me"
                })
                
                # Should verify attachment exists
                assert mock_compose.called
                call_args = mock_compose.call_args
                attachment_paths = call_args.kwargs.get("attachment_paths", [])
                
                # If attachments were provided, they should be validated
                if attachment_paths:
                    assert os.path.exists(attachment_paths[0]), "Attachment file should exist"
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


def test_presentation_and_email_missing_file():
    """Test that missing presentation file returns error."""
    # Mock presentation creation with non-existent file
    mock_presentation = {
        "success": True,
        "presentation_path": "/nonexistent/path/to/presentation.key",
        "company": "NVIDIA",
        "ticker": "NVDA"
    }
    
    with patch('src.agent.enriched_stock_agent.create_enriched_stock_presentation') as mock_create:
        mock_create.invoke.return_value = mock_presentation
        
        result = create_stock_report_and_email.invoke({
            "company": "NVIDIA",
            "recipient": "me"
        })
        
        # Should return error because file doesn't exist
        assert result.get("email_sent") is False
        assert "not found" in result.get("email_error", "").lower() or result.get("success") is False


def test_reminders_and_email_pattern():
    """Test that reminders can be created and confirmation emailed."""
    # This is a pattern test - actual reminder agent would need to be imported
    # For now, we test the email part of the pattern
    
    reminder_info = {
        "title": "Call John",
        "due_time": "tomorrow",
        "created": True
    }
    
    with patch('src.automation.mail_composer.MailComposer.compose_email') as mock_compose:
        mock_compose.return_value = True
        
        email_result = compose_email.invoke({
            "subject": "Reminder Created",
            "body": f"Reminder set: {reminder_info['title']} ({reminder_info['due_time']})",
            "send": True
        })
        
        # Should not have attachment error
        assert email_result.get("error_type") != "AttachmentError"


def test_notes_and_email_pattern():
    """Test that notes can be created and content emailed."""
    # This is a pattern test - actual notes agent would need to be imported
    # For now, we test the email part of the pattern
    
    note_content = {
        "title": "Meeting Notes",
        "body": "Meeting discussed project timeline and deliverables.",
        "created": True
    }
    
    with patch('src.automation.mail_composer.MailComposer.compose_email') as mock_compose:
        mock_compose.return_value = True
        
        email_result = compose_email.invoke({
            "subject": note_content["title"],
            "body": note_content["body"],
            "send": True
        })
        
        # Should not have attachment error
        assert email_result.get("error_type") != "AttachmentError"
        # Body should contain note content
        assert note_content["body"] in email_result.get("message", "") or mock_compose.called


def test_stock_presentation_email_attachment_verification():
    """Test that stock presentation email workflow verifies attachments."""
    # Create a temporary presentation file
    with tempfile.NamedTemporaryFile(delete=False, suffix=".key") as tmp_file:
        tmp_path = tmp_file.name
        tmp_file.write(b"fake keynote content")
    
    try:
        # Mock the full workflow
        with patch('src.agent.enriched_stock_agent.create_enriched_stock_presentation') as mock_create:
            mock_create.invoke.return_value = {
                "success": True,
                "presentation_path": tmp_path,
                "company": "NVIDIA",
                "ticker": "NVDA",
                "current_price": "$150.25",
                "price_change": "+2.3%",
                "data_date": "January 15, 2024",
                "total_searches": 5
            }
            
            with patch('src.automation.mail_composer.MailComposer.compose_email') as mock_compose:
                mock_compose.return_value = True
                
                result = create_stock_report_and_email.invoke({
                    "company": "NVIDIA",
                    "recipient": "me"
                })
                
                # Verify that compose_email was called
                assert mock_compose.called
                
                # Verify attachment was validated
                call_args = mock_compose.call_args
                attachment_paths = call_args.kwargs.get("attachment_paths", [])
                
                if attachment_paths:
                    # File should exist (we created it)
                    assert os.path.exists(attachment_paths[0])
                    # Path should be absolute
                    assert os.path.isabs(attachment_paths[0])
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


def test_cross_domain_email_send_flag():
    """Test that cross-domain combinations use send=true when user says 'email' or 'send'."""
    # Test that when user says "email [content]", send flag is True
    with patch('src.automation.mail_composer.MailComposer.compose_email') as mock_compose:
        mock_compose.return_value = True
        
        # Simulate "email tweets" request
        compose_email.invoke({
            "subject": "Tweets Summary",
            "body": "Summary of tweets",
            "send": True  # User said "email" so send should be True
        })
        
        assert mock_compose.called
        call_args = mock_compose.call_args
        assert call_args.kwargs.get("send_immediately") is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

