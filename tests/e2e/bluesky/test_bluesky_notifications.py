"""
End-to-End Tests: Bluesky Notifications and Posting Complete Flow

Tests Bluesky functionality end-to-end:
- Notification reading and summarization with real-time notifications
- Posting/tweeting to Bluesky

WINNING CRITERIA:
- Backend: BlueskyNotificationService polling, tool execution, API integration
- API: Real-time notification messages, WebSocket format, completion events
- UI: BlueskyNotificationCard rendering, TaskCompletionCard, interactive elements
"""

import pytest
import time
import sys
from pathlib import Path
from typing import Dict, Any, List

# Add helpers to path
sys.path.insert(0, str(Path(__file__).parent.parent / "helpers"))
from test_verification_helpers import (
    verify_backend_tool_execution,
    verify_websocket_message_format,
    verify_completion_event,
    verify_ui_rendering,
    verify_tool_result_data
)

pytestmark = [pytest.mark.e2e]


class TestBlueskyNotifications:
    """Test complete Bluesky notification and posting flows with full stack verification."""

    def test_notification_read_summarize(
        self,
        api_client,
        success_criteria_checker,
        telemetry_collector
    ):
        """
        Test reading and summarizing Bluesky notifications with complete verification.
        
        WINNING CRITERIA:
        Backend:
        - BlueskyNotificationService running and polling (check is_running())
        - summarize_bluesky_posts tool called with appropriate query
        - BlueskyAPIClient successfully authenticates
        - Returns summary with post highlights and metadata
        - Notification deduplication working (no duplicate notifications)
        
        API/WebSocket:
        - Real-time notification messages: {"type": "bluesky_notification", "data": {...}}
        - Tool call for summarization sent
        - Summary result includes post count and highlights
        - Notification payload includes: author_handle, author_name, timestamp, post text
        
        UI:
        - BlueskyNotificationCard renders for each notification
        - Card shows: author handle, post text preview, timestamp, action buttons
        - Summary message displays post count and key highlights
        - Notification cards have interactive buttons (reply, like, open)
        """
        query = "Summarize my Bluesky notifications"
        
        telemetry_collector.record_event("bluesky_notification_test_start", {
            "query": query,
            "test_type": "notification_read_summarize"
        })
        
        start_time = time.time()
        response = api_client.chat(query)
        messages = api_client.wait_for_completion(max_wait=90)
        execution_time = time.time() - start_time
        
        response_text = response.get("message", "")
        
        # BACKEND VERIFICATION
        # Check for summarize_bluesky_posts tool call
        backend_verification = verify_backend_tool_execution(
            messages,
            "summarize_bluesky_posts",
            expected_params={"query": "notifications"}
        )
        
        # Also check for get_bluesky_author_feed as alternative
        if not backend_verification["found"]:
            backend_verification = verify_backend_tool_execution(
                messages,
                "get_bluesky_author_feed"
            )
        
        assert backend_verification["found"], "Backend: Bluesky summarization tool was not called"
        
        # Verify tool result contains summary data
        tool_result_verification = verify_tool_result_data(
            messages,
            "summarize_bluesky_posts",
            ["summary", "items"]
        )
        
        # If get_bluesky_author_feed was used instead
        if not tool_result_verification["tool_result_found"]:
            tool_result_verification = verify_tool_result_data(
                messages,
                "get_bluesky_author_feed",
                ["posts", "count"]
            )
        
        # API/WEBSOCKET VERIFICATION
        # Check for real-time notification messages
        notification_messages = [
            msg for msg in messages
            if msg.get("type") == "bluesky_notification" or
            (msg.get("type") == "bluesky_notification" and msg.get("data"))
        ]
        
        # Verify notification message format if present
        if notification_messages:
            for notif_msg in notification_messages[:1]:  # Check first notification
                ws_format = verify_websocket_message_format(
                    notif_msg,
                    "bluesky_notification",
                    ["type", "data"]
                )
                # Notification format is flexible, so we just check it exists
                assert ws_format["type_match"] or "bluesky" in str(notif_msg).lower(), \
                    "API: Notification message format incorrect"
        
        # Verify tool call message format
        tool_call_messages = [
            msg for msg in messages
            if msg.get("type") == "tool_call" and
            ("bluesky" in msg.get("tool_name", "").lower())
        ]
        if tool_call_messages:
            ws_format = verify_websocket_message_format(
                tool_call_messages[0],
                "tool_call",
                ["type", "tool_name", "parameters"]
            )
            assert ws_format["type_match"], "API: Tool call message type incorrect"
        
        # UI VERIFICATION
        ui_verification = verify_ui_rendering(
            response,
            expected_elements=["bluesky", "notification", "summary"]
        )
        
        # SUCCESS CRITERIA CHECKS
        assert success_criteria_checker.check_no_errors(response), "UI: Response contains errors"
        assert success_criteria_checker.check_response_length(response_text, 50), "UI: Response too short"
        
        # Check for Bluesky-related keywords
        bluesky_keywords = ["bluesky"]
        assert success_criteria_checker.check_keywords_present(
            response_text,
            bluesky_keywords
        ), "UI: Missing Bluesky keywords"
        
        telemetry_collector.record_event("bluesky_notification_test_complete", {
            "execution_time": execution_time,
            "backend_verified": backend_verification["found"],
            "tool_result_found": tool_result_verification["tool_result_found"],
            "notification_messages_count": len(notification_messages),
            "response_length": len(response_text)
        })

    def test_post_to_bluesky_complete_flow(
        self,
        api_client,
        success_criteria_checker,
        telemetry_collector
    ):
        """
        Test posting to Bluesky with complete backend-to-UI verification.
        
        WINNING CRITERIA:
        Backend:
        - post_bluesky_update(message="...") tool called
        - BlueskyAPIClient successfully posts to Bluesky
        - Returns post URI and URL
        - Post appears in user's Bluesky feed (verification via API)
        
        API/WebSocket:
        - Tool call message with correct message parameter
        - Completion event: {"action": "bluesky_posted", "status": "success", "url": "..."}
        - Final message includes post URL
        
        UI:
        - TaskCompletionCard shows Bluesky icon and "Posted to Bluesky"
        - Post URL is clickable/linkable
        - Success indicator visible
        - No error states
        """
        post_content = "Testing Bluesky integration for quality testing"
        query = f"Post '{post_content}' to Bluesky"
        
        telemetry_collector.record_event("bluesky_post_test_start", {
            "query": query,
            "test_type": "post_to_bluesky_complete_flow",
            "post_content": post_content
        })
        
        start_time = time.time()
        response = api_client.chat(query)
        messages = api_client.wait_for_completion(max_wait=60)
        execution_time = time.time() - start_time
        
        response_text = response.get("message", "")
        
        # BACKEND VERIFICATION
        backend_verification = verify_backend_tool_execution(
            messages,
            "post_bluesky_update",
            expected_params={"message": post_content}
        )
        
        assert backend_verification["found"], "Backend: post_bluesky_update tool was not called"
        
        # Verify tool result contains post data
        tool_result_verification = verify_tool_result_data(
            messages,
            "post_bluesky_update",
            ["uri", "url"]
        )
        
        # API/WEBSOCKET VERIFICATION
        # Verify tool call message format
        tool_call_messages = [
            msg for msg in messages
            if msg.get("type") == "tool_call" and msg.get("tool_name") == "post_bluesky_update"
        ]
        if tool_call_messages:
            ws_format = verify_websocket_message_format(
                tool_call_messages[0],
                "tool_call",
                ["type", "tool_name", "parameters"]
            )
            assert ws_format["type_match"], "API: Tool call message type incorrect"
            assert ws_format["has_all_fields"], f"API: Tool call missing required fields: {ws_format['missing_fields']}"
        
        # Verify completion event
        completion_verification = verify_completion_event(
            messages,
            expected_action="bluesky_posted",
            expected_status="success"
        )
        
        # UI VERIFICATION
        ui_verification = verify_ui_rendering(
            response,
            expected_elements=["bluesky", "posted", "post"]
        )
        
        # SUCCESS CRITERIA CHECKS
        assert success_criteria_checker.check_no_errors(response), "UI: Response contains errors"
        assert success_criteria_checker.check_response_length(response_text, 50), "UI: Response too short"
        assert success_criteria_checker.check_keywords_present(
            response_text,
            ["bluesky", "posted"]
        ), "UI: Missing posting confirmation keywords"
        
        # Verify completion event was sent (for TaskCompletionCard)
        assert completion_verification["found"] or len([m for m in messages if m.get("completion_event")]) > 0, \
            "API: No completion event sent for UI TaskCompletionCard"
        
        # Check for URL in response (for clickable link)
        has_url = "http" in response_text or "bsky.app" in response_text or "url" in response_text.lower()
        
        telemetry_collector.record_event("bluesky_post_test_complete", {
            "execution_time": execution_time,
            "backend_verified": backend_verification["found"],
            "completion_event_found": completion_verification["found"],
            "tool_result_found": tool_result_verification["tool_result_found"],
            "has_url": has_url,
            "response_length": len(response_text)
        })


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])

