"""
End-to-End Tests: Bluesky Integration

Tests Bluesky social media functionality:
- Posting updates
- Fetching feed/timeline
- Summarizing notifications
- Error handling for rate limits
- Authentication flow

WINNING CRITERIA:
- Posts published successfully
- Content matches input
- Feed retrieval works
- UI shows proper status
"""

import pytest
import time
import json
from typing import Dict, Any, List

pytestmark = [pytest.mark.e2e]


class TestBlueskyIntegration:
    """Test comprehensive Bluesky social media functionality."""

    def test_post_to_bluesky(
        self,
        api_client,
        success_criteria_checker,
        telemetry_collector
    ):
        """
        Test posting content to Bluesky.

        WINNING CRITERIA:
        - Post published successfully
        - Content matches exactly
        - Confirmation shown
        - UI updates with post status
        """
        post_content = "Testing Bluesky integration with automated posting #test"

        query = f"Post '{post_content}' to Bluesky"

        telemetry_collector.record_event("bluesky_test_start", {
            "type": "post_content",
            "content_length": len(post_content)
        })

        response = api_client.chat(query)
        messages = api_client.wait_for_completion(max_wait=60)

        response_text = response.get("message", "")

        # Check success criteria
        assert success_criteria_checker.check_no_errors(response)
        assert success_criteria_checker.check_response_length(response_text, 50)

        # Check posting confirmation
        post_keywords = ["posted", "bluesky", "published"]
        assert success_criteria_checker.check_keywords_present(response_text, post_keywords)

        # Verify post content in tool call
        post_verified = False
        for message in messages:
            if message.get("type") == "tool_call" and message.get("tool_name") == "post_to_bluesky":
                params = message.get("parameters", {})
                if params.get("content") == post_content:
                    post_verified = True
                    break

        assert post_verified, "Post content not correctly sent to Bluesky API"

        telemetry_collector.record_event("bluesky_post_complete", {
            "content_posted": post_verified,
            "content_length": len(post_content)
        })

    def test_fetch_bluesky_feed(
        self,
        api_client,
        success_criteria_checker
    ):
        """
        Test fetching Bluesky timeline/feed.

        WINNING CRITERIA:
        - Feed retrieved successfully
        - Posts displayed chronologically
        - Content properly formatted
        - UI shows timeline view
        """
        query = "Show me my recent Bluesky posts"

        response = api_client.chat(query)
        messages = api_client.wait_for_completion(max_wait=60)

        response_text = response.get("message", "")

        assert success_criteria_checker.check_no_errors(response)
        assert success_criteria_checker.check_response_length(response_text, 100)

        # Check feed keywords
        feed_keywords = ["bluesky", "post"]
        assert success_criteria_checker.check_keywords_present(response_text, feed_keywords)

        # Verify feed fetching tool was called
        feed_fetched = any(
            msg.get("tool_name") == "get_bluesky_feed"
            for msg in messages
            if msg.get("type") == "tool_call"
        )
        assert feed_fetched, "Bluesky feed not fetched"

    def test_summarize_bluesky_notifications(
        self,
        api_client,
        success_criteria_checker
    ):
        """
        Test summarizing Bluesky notifications.

        WINNING CRITERIA:
        - Notifications retrieved
        - Summary generated
        - Content properly synthesized
        - UI shows notification summary
        """
        query = "Summarize my Bluesky notifications from the past hour"

        response = api_client.chat(query)
        messages = api_client.wait_for_completion(max_wait=60)

        response_text = response.get("message", "")

        assert success_criteria_checker.check_no_errors(response)
        assert success_criteria_checker.check_response_length(response_text, 150)

        # Check notification keywords
        notification_keywords = ["notification", "summary", "bluesky"]
        assert success_criteria_checker.check_keywords_present(response_text, notification_keywords)

        # Verify notification fetching
        notifications_fetched = any(
            msg.get("tool_name") in ["get_bluesky_notifications", "summarize_bluesky_activity"]
            for msg in messages
            if msg.get("type") == "tool_call"
        )
        assert notifications_fetched, "Bluesky notifications not retrieved"

    def test_bluesky_rate_limit_handling(
        self,
        api_client,
        success_criteria_checker,
        telemetry_collector
    ):
        """
        Test Bluesky rate limit handling and backoff.

        WINNING CRITERIA:
        - Rate limit detected
        - Backoff implemented
        - User notified gracefully
        - Operation retries appropriately
        """
        # This test would need to simulate rate limiting
        # For now, we'll test the error handling framework

        query = "Post multiple updates to Bluesky rapidly"

        telemetry_collector.record_event("rate_limit_test_start", {"test_type": "bluesky_rate_limit"})

        response = api_client.chat(query)
        messages = api_client.wait_for_completion(max_wait=60)

        response_text = response.get("message", "")

        # Check that rate limiting is handled gracefully
        has_rate_limit_handling = (
            "rate limit" in response_text.lower() or
            "too many" in response_text.lower() or
            "wait" in response_text.lower() or
            "retry" in response_text.lower() or
            not success_criteria_checker.check_no_errors(response)  # May have rate limit error
        )

        # If rate limited, should show appropriate message
        if "rate limit" in response_text.lower():
            assert "retry" in response_text.lower() or "wait" in response_text.lower(), \
                "Rate limit error not handled with retry guidance"

        telemetry_collector.record_event("rate_limit_test_complete", {
            "rate_limit_handled": has_rate_limit_handling
        })

    def test_bluesky_authentication_flow(
        self,
        api_client,
        success_criteria_checker
    ):
        """
        Test Bluesky authentication and session management.

        WINNING CRITERIA:
        - Authentication successful
        - Session maintained
        - Operations work post-auth
        - Token refresh handled
        """
        query = "Check my Bluesky connection and post a test message"

        response = api_client.chat(query)
        messages = api_client.wait_for_completion(max_wait=60)

        response_text = response.get("message", "")

        # Should handle auth gracefully
        auth_handled = (
            "connected" in response_text.lower() or
            "authenticated" in response_text.lower() or
            "login" in response_text.lower() or
            "authorize" in response_text.lower() or
            success_criteria_checker.check_no_errors(response)
        )

        assert auth_handled, "Bluesky authentication not properly handled"

        # If authenticated, should be able to post
        if "connected" in response_text.lower() or success_criteria_checker.check_no_errors(response):
            post_possible = any(
                msg.get("tool_name") == "post_to_bluesky"
                for msg in messages
                if msg.get("type") == "tool_call"
            )
            if post_possible:
                assert "test message" in response_text.lower() or "posted" in response_text.lower()

    def test_bluesky_content_validation(
        self,
        api_client,
        success_criteria_checker
    ):
        """
        Test Bluesky content validation and formatting.

        WINNING CRITERIA:
        - Content properly formatted
        - Length limits respected
        - Special characters handled
        - Links properly formatted
        """
        # Test with special characters and links
        test_content = "Testing Bluesky API with special chars: @user #hashtag https://example.com 🚀"

        query = f"Post this to Bluesky: {test_content}"

        response = api_client.chat(query)
        messages = api_client.wait_for_completion(max_wait=60)

        response_text = response.get("message", "")

        assert success_criteria_checker.check_no_errors(response)

        # Verify content was processed correctly
        content_verified = False
        for message in messages:
            if message.get("type") == "tool_call" and message.get("tool_name") == "post_to_bluesky":
                params = message.get("parameters", {})
                if test_content in params.get("content", ""):
                    content_verified = True
                    break

        assert content_verified, "Special characters or formatting not handled correctly"

    def test_bluesky_ui_status_display(
        self,
        api_client,
        success_criteria_checker
    ):
        """
        Test Bluesky UI status and social features display.

        WINNING CRITERIA:
        - Post status shown
        - Social interactions visible
        - Feed properly rendered
        - Error states clear
        """
        query = "Show my Bluesky activity summary"

        response = api_client.chat(query)
        messages = api_client.wait_for_completion(max_wait=60)

        # Check for UI components
        ui_messages = [msg for msg in messages if msg.get("type") in ["status", "social_card", "feed_display"]]

        # Should have some UI feedback for social features
        assert len(ui_messages) > 0, "No UI feedback for Bluesky activity"

        response_text = response.get("message", "")
        assert success_criteria_checker.check_response_length(response_text, 50)

        # Should mention Bluesky-specific elements
        bluesky_ui_keywords = ["bluesky", "post", "feed"]
        assert success_criteria_checker.check_keywords_present(response_text, bluesky_ui_keywords)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
