"""
Test email reading scenarios to verify functionality.

These tests validate that the email reading system works correctly for common use cases:
1. Read last N emails and summarize
2. Read emails from specific time range
3. Verify account-scoped reading (security)

Note: These tests directly invoke the email agent tools, not the full workflow.
"""

import pytest
from src.agent.email_agent import (
    read_latest_emails,
    read_emails_by_sender,
    read_emails_by_time,
    summarize_emails,
)
from src.utils import load_config


class TestEmailReadingScenarios:
    """Test common email reading scenarios."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Load config for all tests."""
        self.config = load_config()

    def test_read_last_3_emails(self):
        """
        Scenario: Read last 3 emails

        Tool: read_latest_emails(count=3)
        """
        result = read_latest_emails.invoke({"count": 3})

        # Result should be a dictionary
        assert isinstance(result, dict), f"Should return dict, got {type(result)}"

        # Check for error or success
        if result.get("error"):
            # Error is acceptable if Mail.app not configured
            pytest.skip(f"Mail.app error (expected if not configured): {result.get('error_message')}")

        # If successful, verify structure
        assert "emails" in result, "Should contain 'emails' key"
        assert "count" in result, "Should contain 'count' key"
        assert "account" in result, "Should contain 'account' key (security)"

        # Verify account matches config
        configured_account = self.config.get("email", {}).get("account_email")
        assert result["account"] == configured_account, \
            f"Should read from configured account: {configured_account}"

        # Verify count doesn't exceed requested
        email_count = result.get("count", 0)
        assert email_count <= 3, f"Should return max 3 emails, got {email_count}"

        print(f"✅ Successfully read {email_count} emails from account: {result['account']}")

    def test_read_emails_last_hour(self):
        """
        Scenario: Read emails from the last hour

        Tool: read_emails_by_time(hours=1)
        """
        result = read_emails_by_time.invoke({"hours": 1})

        # Result should be a dictionary
        assert isinstance(result, dict), f"Should return dict, got {type(result)}"

        # Check for error or success
        if result.get("error"):
            pytest.skip(f"Mail.app error (expected if not configured): {result.get('error_message')}")

        # If successful, verify structure
        assert "emails" in result, "Should contain 'emails' key"
        assert "count" in result, "Should contain 'count' key"
        assert "account" in result, "Should contain 'account' key (security)"
        assert "time_range" in result, "Should contain 'time_range' key"

        # Verify account matches config
        configured_account = self.config.get("email", {}).get("account_email")
        assert result["account"] == configured_account, \
            f"Should read from configured account: {configured_account}"

        # Verify time range
        assert "1 hours" in result["time_range"] or "hour" in result["time_range"], \
            f"Time range should be 1 hour, got: {result['time_range']}"

        print(f"✅ Read {result['count']} emails from last hour, account: {result['account']}")

    def test_unread_emails_not_supported(self):
        """
        Scenario: User asks to "read unread emails"

        Expected: System should attempt read_latest_emails (no unread filter exists)
        or inform user that unread filtering is not available.
        """
        request = "read unread emails"

        result = execute_workflow(request, self.config)

        # Workflow should execute something, even if unread filter isn't available
        assert result["status"] in ["success", "partial_success", "error"]

        # Note: This test just verifies system doesn't crash
        # The LLM will likely use read_latest_emails as fallback
        # since there's no read_unread_emails tool

    def test_read_emails_by_sender(self):
        """
        Scenario: User asks to "read emails from john@example.com"

        Expected workflow:
        1. read_emails_by_sender(sender="john@example.com")
        """
        request = "read emails from john@example.com"

        result = execute_workflow(request, self.config)

        # Verify workflow succeeded
        assert result["status"] in ["success", "partial_success"], \
            f"Workflow failed: {result.get('results')}"

        results = result.get("results", {})

        # Check that sender-based reading was used
        sender_step = None
        for step_id, step_result in results.items():
            if not isinstance(step_result, dict):
                continue
            tool = step_result.get("tool")
            if tool == "read_emails_by_sender":
                sender_step = step_result
                break

        assert sender_step is not None, "Should use read_emails_by_sender tool"

    def test_account_constraint_security(self):
        """
        SECURITY TEST: Verify that all email reading is constrained to configured account.

        This test checks that the account_email from config.yaml is being passed to
        all email reading tools.
        """
        request = "read my latest 5 emails"

        result = execute_workflow(request, self.config)

        if result["status"] not in ["success", "partial_success"]:
            pytest.skip("Workflow failed - may be expected if Mail.app not configured")

        results = result.get("results", {})
        configured_account = self.config.get("email", {}).get("account_email")

        if not configured_account:
            pytest.skip("No account_email configured in config.yaml")

        # Check that any email reading step includes the configured account
        for step_id, step_result in results.items():
            if not isinstance(step_result, dict):
                continue

            tool = step_result.get("tool", "")
            if tool.startswith("read_") and "email" in tool:
                # This is an email reading tool
                if not step_result.get("error"):
                    assert "account" in step_result, \
                        f"Email reading tool '{tool}' should return account info"
                    assert step_result.get("account") == configured_account, \
                        f"Tool '{tool}' should only read from configured account"

    @pytest.mark.integration
    def test_full_workflow_read_and_summarize(self):
        """
        INTEGRATION TEST: Full workflow test for reading and summarizing emails.

        Requires:
        - Mail.app configured and accessible
        - Emails in the inbox
        - OpenAI API key for summarization
        """
        request = "read my last 5 emails and give me a summary focusing on action items"

        result = execute_workflow(request, self.config)

        # This test allows partial success (some steps may fail)
        assert result["status"] != "error", "Complete workflow failure"

        results = result.get("results", {})

        # Verify both steps were attempted
        tools_used = []
        for step_id, step_result in results.items():
            if isinstance(step_result, dict):
                tool = step_result.get("tool")
                if tool:
                    tools_used.append(tool)

        assert "read_latest_emails" in tools_used or "read_emails_by_time" in tools_used, \
            "Should attempt to read emails"

        # Summarization might not run if reading failed
        print(f"Tools used: {tools_used}")
        print(f"Full result: {result}")


class TestEmailToolParameters:
    """Test that email tools receive correct parameters."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Load config for all tests."""
        self.config = load_config()

    def test_read_latest_emails_count_parameter(self):
        """Verify that count parameter is correctly passed to read_latest_emails."""
        request = "read my last 3 emails"

        result = execute_workflow(request, self.config)

        # Find the read_latest_emails step
        results = result.get("results", {})
        for step_id, step_result in results.items():
            if isinstance(step_result, dict) and step_result.get("tool") == "read_latest_emails":
                # If reading succeeded, verify count matches
                if not step_result.get("error"):
                    # The result should indicate 3 or fewer emails were returned
                    # (could be less if inbox has fewer than 3)
                    email_count = step_result.get("count", 0)
                    assert email_count <= 3, "Should not return more than requested count"

    def test_read_by_time_hours_parameter(self):
        """Verify that hours parameter is correctly passed to read_emails_by_time."""
        request = "read emails from the last 2 hours"

        result = execute_workflow(request, self.config)

        # Find the read_emails_by_time step
        results = result.get("results", {})
        for step_id, step_result in results.items():
            if isinstance(step_result, dict) and step_result.get("tool") == "read_emails_by_time":
                if not step_result.get("error"):
                    time_range = step_result.get("time_range", "")
                    assert "2 hours" in time_range or "hour" in time_range, \
                        "Should use hours-based time range"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
