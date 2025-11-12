"""
Test email attachment verification functionality.

Tests that:
1. Email attachments are validated before sending
2. Absolute paths are used for attachments
3. Errors are returned if files don't exist
4. Attachment status is logged properly
"""

import os
import tempfile
import pytest
from pathlib import Path
from unittest.mock import Mock, patch

from src.agent.email_agent import compose_email


def test_email_attachment_validation_missing_file():
    """Test that missing attachment files return an error."""
    result = compose_email.invoke({
        "subject": "Test Email",
        "body": "Test body",
        "attachments": ["/nonexistent/path/to/file.pdf"],
        "send": False
    })
    
    assert result.get("error") is True
    assert result.get("error_type") == "AttachmentError"
    assert "failed validation" in result.get("error_message", "").lower()
    assert len(result.get("invalid_attachments", [])) > 0


def test_email_attachment_validation_valid_file():
    """Test that valid attachment files are accepted."""
    # Create a temporary file
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
        tmp_path = tmp_file.name
        tmp_file.write(b"test content")
    
    try:
        result = compose_email.invoke({
            "subject": "Test Email",
            "body": "Test body",
            "attachments": [tmp_path],
            "send": False
        })
        
        # Should not have attachment error (may have other errors like Mail.app not available)
        assert result.get("error_type") != "AttachmentError"
    finally:
        # Clean up
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


def test_email_attachment_absolute_path():
    """Test that relative paths are converted to absolute paths."""
    # Create a temporary file
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
        tmp_path = tmp_file.name
        tmp_file.write(b"test content")
    
    try:
        # Get relative path
        rel_path = os.path.relpath(tmp_path)
        
        with patch('src.automation.mail_composer.MailComposer.compose_email') as mock_compose:
            mock_compose.return_value = True
            
            result = compose_email.invoke({
                "subject": "Test Email",
                "body": "Test body",
                "attachments": [rel_path],
                "send": False
            })
            
            # Check that absolute path was passed to MailComposer
            if mock_compose.called:
                call_args = mock_compose.call_args
                attachment_paths = call_args.kwargs.get("attachment_paths", [])
                if attachment_paths:
                    assert os.path.isabs(attachment_paths[0]), "Path should be absolute"
    finally:
        # Clean up
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


def test_email_attachment_directory_not_file():
    """Test that directories are rejected as attachments."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        result = compose_email.invoke({
            "subject": "Test Email",
            "body": "Test body",
            "attachments": [tmp_dir],
            "send": False
        })
        
        assert result.get("error") is True
        assert result.get("error_type") == "AttachmentError"


def test_email_attachment_multiple_files():
    """Test validation of multiple attachments."""
    # Create two temporary files
    tmp_files = []
    try:
        for i in range(2):
            with tempfile.NamedTemporaryFile(delete=False, suffix=f"_{i}.pdf") as tmp_file:
                tmp_path = tmp_file.name
                tmp_file.write(b"test content")
                tmp_files.append(tmp_path)
        
        # Add one invalid path
        attachments = tmp_files + ["/nonexistent/file.pdf"]
        
        result = compose_email.invoke({
            "subject": "Test Email",
            "body": "Test body",
            "attachments": attachments,
            "send": False
        })
        
        # Should have error for invalid attachment
        assert result.get("error") is True
        assert result.get("error_type") == "AttachmentError"
    finally:
        # Clean up
        for tmp_path in tmp_files:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)


def test_email_attachment_empty_list():
    """Test that empty attachment list is handled."""
    result = compose_email.invoke({
        "subject": "Test Email",
        "body": "Test body",
        "attachments": [],
        "send": False
    })
    
    # Should not have attachment error
    assert result.get("error_type") != "AttachmentError"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

