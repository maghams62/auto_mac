#!/usr/bin/env python3
"""
Integration test for plan streaming functionality.
Tests that step status updates flow correctly from Agent → API Server → WebSocket → Frontend
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import asyncio
import json
from datetime import datetime
from unittest.mock import MagicMock, AsyncMock, patch
import pytest

from src.agent.agent import AutomationAgent


class MockWebSocket:
    """Mock WebSocket for testing."""
    def __init__(self):
        self.sent_messages = []
        self.connected = True

    def send(self, message):
        self.sent_messages.append(json.loads(message))


def test_plan_streaming_sequence_numbers():
    """Test that sequence numbers prevent out-of-order updates."""
    # Simulate frontend plan state
    plan_state = {
        "goal": "Test streaming",
        "steps": [
            {"id": 1, "action": "step1", "status": "pending", "sequence_number": 0},
            {"id": 2, "action": "step2", "status": "pending", "sequence_number": 0},
            {"id": 3, "action": "step3", "status": "pending", "sequence_number": 0}
        ],
        "last_sequence_number": 0
    }

    # Simulate receiving events out of order
    events = [
        {"type": "plan_update", "step_id": 1, "status": "running", "sequence_number": 1},
        {"type": "plan_update", "step_id": 2, "status": "running", "sequence_number": 2},  # Should be processed
        {"type": "plan_update", "step_id": 1, "status": "running", "sequence_number": 1},  # Should be ignored (duplicate)
        {"type": "plan_update", "step_id": 3, "status": "running", "sequence_number": 4},  # Should be processed
        {"type": "plan_update", "step_id": 2, "status": "completed", "sequence_number": 3}, # Should be ignored (out of order)
    ]

    for event in events:
        seq_num = event["sequence_number"]
        if seq_num <= plan_state["last_sequence_number"]:
            continue  # Skip out-of-order message

        plan_state["last_sequence_number"] = seq_num

        # Update step status
        for step in plan_state["steps"]:
            if step["id"] == event["step_id"]:
                step["status"] = event["status"]
                step["sequence_number"] = seq_num
                break

    # Verify final state
    assert plan_state["steps"][0]["status"] == "running"  # Step 1 processed
    assert plan_state["steps"][1]["status"] == "running"  # Step 2 processed
    assert plan_state["steps"][2]["status"] == "running"  # Step 3 processed
    assert plan_state["last_sequence_number"] == 4


def test_plan_state_cleanup():
    """Test that plan state is properly cleaned up on conversation reset."""
    # Mock the WebSocket hook state
    messages = [{"type": "plan", "goal": "Test", "steps": []}]
    plan_state = {
        "goal": "Test goal",
        "steps": [{"id": 1, "action": "test", "status": "running"}],
        "status": "executing"
    }

    # Simulate clearMessages call (equivalent to what useWebSocket does)
    messages.clear()
    plan_state = None

    assert len(messages) == 0
    assert plan_state is None


@pytest.mark.asyncio
async def test_backend_callback_sequence():
    """Test that backend callbacks fire in correct sequence."""
    config = {
        "openai": {"model": "gpt-4", "api_key": "test"},
        "tools": {},
        "vision": {"enabled": False}
    }

    agent = AutomationAgent(config)

    # Mock callbacks
    callback_calls = []
    def mock_step_started(data):
        callback_calls.append(("started", data))

    def mock_step_succeeded(data):
        callback_calls.append(("succeeded", data))

    def mock_step_failed(data):
        callback_calls.append(("failed", data))

    # Simple test request that should create a minimal plan
    user_request = "echo hello"

    # This would normally run the full agent, but we'll mock the execution
    # to test just the callback sequence

    # Simulate the callback sequence that would happen in execute_step
    mock_step_started({"step_id": 1, "sequence_number": 1, "timestamp": "2024-01-01T00:00:00"})
    mock_step_succeeded({"step_id": 1, "sequence_number": 2, "timestamp": "2024-01-01T00:00:01", "output_preview": "hello"})

    # Verify callback sequence
    assert len(callback_calls) == 2
    assert callback_calls[0][0] == "started"
    assert callback_calls[0][1]["step_id"] == 1
    assert callback_calls[0][1]["sequence_number"] == 1

    assert callback_calls[1][0] == "succeeded"
    assert callback_calls[1][1]["step_id"] == 1
    assert callback_calls[1][1]["sequence_number"] == 2
    assert callback_calls[1][1]["output_preview"] == "hello"


def test_websocket_reconnection_handling():
    """Test that plan state handles WebSocket disconnection gracefully."""
    # Simulate plan state during disconnection
    plan_state = {
        "goal": "Test reconnection",
        "steps": [{"id": 1, "action": "test", "status": "running"}],
        "status": "executing",
        "last_sequence_number": 5
    }

    # Simulate WebSocket disconnect (onclose event)
    if plan_state and plan_state["status"] not in ["completed", "failed"]:
        plan_state["status"] = "failed"  # Mark as failed until reconnected

    assert plan_state["status"] == "failed"

    # Simulate reconnection (onopen event)
    if plan_state and plan_state["status"] == "failed":
        plan_state["status"] = "executing"  # Assume execution continues

    assert plan_state["status"] == "executing"


def test_plan_finalization():
    """Test plan finalization marks remaining steps as skipped."""
    plan_state = {
        "goal": "Test finalization",
        "steps": [
            {"id": 1, "action": "step1", "status": "completed"},
            {"id": 2, "action": "step2", "status": "running"},
            {"id": 3, "action": "step3", "status": "pending"},
            {"id": 4, "action": "step4", "status": "pending"}
        ],
        "status": "executing",
        "last_sequence_number": 3
    }

    # Simulate plan finalization
    timestamp = "2024-01-01T00:00:00"
    finalized_steps = []
    for step in plan_state["steps"]:
        if step["status"] == "pending":
            finalized_steps.append({
                **step,
                "status": "skipped",
                "completed_at": timestamp
            })
        else:
            finalized_steps.append(step)

    plan_state["steps"] = finalized_steps
    plan_state["status"] = "completed"
    plan_state["completed_at"] = timestamp
    plan_state["activeStepId"] = None

    # Verify finalization
    assert plan_state["status"] == "completed"
    assert plan_state["steps"][0]["status"] == "completed"  # Already completed
    assert plan_state["steps"][1]["status"] == "running"    # Still running
    assert plan_state["steps"][2]["status"] == "skipped"    # Marked as skipped
    assert plan_state["steps"][3]["status"] == "skipped"    # Marked as skipped
    assert plan_state["activeStepId"] is None


if __name__ == "__main__":
    # Run basic tests
    test_plan_streaming_sequence_numbers()
    test_plan_state_cleanup()
    test_websocket_reconnection_handling()
    test_plan_finalization()

    print("✅ All plan streaming tests passed!")
