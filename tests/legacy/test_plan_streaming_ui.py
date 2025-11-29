#!/usr/bin/env python3
"""
UI Test Script for Plan Streaming
Run this while your frontend is running to test plan streaming functionality.
"""

import requests
import json
import time
import sys

def test_plan_streaming():
    """Test plan streaming by sending a request that creates a multi-step plan."""

    print("🎯 Testing Plan Streaming in UI")
    print("=" * 50)

    # Test request that should create a plan with multiple steps
    test_request = "Create a presentation about AI trends with 3 slides: introduction, current trends, and future predictions"

    print(f"📤 Sending test request: {test_request}")
    print()

    try:
        # Send the request to your API
        response = requests.post(
            "http://localhost:8000/api/chat",  # Adjust if your port is different
            json={"message": test_request},
            headers={"Content-Type": "application/json"}
        )

        if response.status_code == 200:
            print("✅ Request sent successfully")
            print("📋 Check your UI for:")
            print("  1. Initial plan display with goal and steps")
            print("  2. Step 1 marked as 'running' with pulsing animation")
            print("  3. Step transitions: running → completed/failed")
            print("  4. Visual status indicators (✓ ✗ ⊘)")
            print("  5. Color-coded borders (green=completed, red=failed)")
            print()
            print("💡 Expected behavior:")
            print("  - Plan should appear immediately with pending steps")
            print("  - Steps should transition through running/completed states")
            print("  - UI should update in real-time without refresh")
            print("  - Status indicators should be clearly visible")
            print()
            print("🔍 Troubleshooting:")
            print("  - If no plan appears: Check backend logs for plan creation")
            print("  - If steps don't update: Check WebSocket connection")
            print("  - If styling is wrong: Check TimelineStep component")
            print()
            print("✨ Test completed! Check your UI now.")
        else:
            print(f"❌ Request failed with status {response.status_code}")
            print(f"Response: {response.text}")

    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to API server")
        print("Make sure your backend is running on http://localhost:8000")
        print("Start it with: python -m uvicorn api_server:app --reload")

    except Exception as e:
        print(f"❌ Error: {e}")

def test_websocket_connection():
    """Test WebSocket connection."""
    print("\n🔌 Testing WebSocket Connection")
    print("-" * 30)

    try:
        import websocket
        ws = websocket.create_connection("ws://localhost:8000/ws/chat")
        print("✅ WebSocket connection successful")
        ws.close()
    except ImportError:
        print("⚠️  websocket-client not installed, skipping WebSocket test")
        print("Install with: pip install websocket-client")
    except Exception as e:
        print(f"❌ WebSocket connection failed: {e}")
        print("Make sure your backend WebSocket server is running")

if __name__ == "__main__":
    print("🚀 Plan Streaming UI Test Script")
    print("This script tests if plan streaming is working in your UI\n")

    # Test WebSocket first
    test_websocket_connection()

    print()

    # Test the actual functionality
    test_plan_streaming()

    print("\n" + "=" * 50)
    print("📝 Manual Verification Steps:")
    print("1. Start your frontend (npm run dev)")
    print("2. Start your backend API server")
    print("3. Run this script: python test_plan_streaming_ui.py")
    print("4. Check your UI for real-time plan updates")
    print("5. Verify step status changes are visible")
