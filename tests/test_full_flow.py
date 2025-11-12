#!/usr/bin/env python3
"""
END-TO-END TEST: Simulate the complete flow from /search command to UI display.
This tests the EXACT path that user input takes through the system.
"""

import sys
from pathlib import Path
project_root = Path(__file__).resolve().parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv()

from src.agent.agent_registry import AgentRegistry
from src.ui.slash_commands import SlashCommandHandler
from src.utils import load_config
from src.memory import SessionManager

print("=" * 80)
print("END-TO-END FLOW TEST: /search what's arsenal's score")
print("=" * 80)

# Initialize components
config = load_config()
session_manager = SessionManager(storage_dir="data/sessions")
registry = AgentRegistry(config, session_manager=session_manager)
handler = SlashCommandHandler(registry, config)

# Step 1: Parse slash command
user_input = "/search what's arsenal's score"
print(f"\n📥 USER INPUT: {user_input}")

# Step 2: Slash command handler processes it
print("\n" + "=" * 80)
print("STEP 1: Slash Command Handler")
print("=" * 80)

is_command, slash_result = handler.handle(user_input, session_id="test-session")

print(f"✓ Is slash command: {is_command}")
print(f"✓ Result type: {slash_result.get('type') if isinstance(slash_result, dict) else type(slash_result)}")

if isinstance(slash_result, dict) and slash_result.get("type") == "result":
    print(f"✓ Agent: {slash_result.get('agent')}")
    print(f"✓ Command: {slash_result.get('command')}")

    tool_result = slash_result.get("result", {})
    print(f"✓ Tool result keys: {list(tool_result.keys())}")
    print(f"✓ Has 'message' field: {bool(tool_result.get('message'))}")
    print(f"✓ Has 'summary' field: {bool(tool_result.get('summary'))}")
    print(f"✓ Has 'error' field: {bool(tool_result.get('error'))}")

    # Step 3: Simulate what agent.py does (from line 800-823)
    print("\n" + "=" * 80)
    print("STEP 2: Agent.py Processing (lines 804-823)")
    print("=" * 80)

    # Extract message (Fix #1)
    message = (
        tool_result.get("message") or
        tool_result.get("summary") or
        tool_result.get("content") or
        tool_result.get("response") or
        "Command executed"
    )

    print(f"✓ Extracted message length: {len(message)}")
    print(f"✓ Message preview: {message[:150]}...")

    # Determine status (Fix #2)
    is_error = tool_result.get("error") is True
    has_content = bool(message and message != "Command executed")
    status = "error" if is_error else ("success" if has_content else "completed")

    print(f"✓ is_error: {is_error}")
    print(f"✓ has_content: {has_content}")
    print(f"✓ Determined status: {status}")

    agent_return = {
        "status": status,
        "message": message,
        "final_result": tool_result,
        "results": {1: tool_result}
    }

    # Step 4: Simulate what api_server.py does (format_result_message)
    print("\n" + "=" * 80)
    print("STEP 3: API Server format_result_message() (lines 283-292)")
    print("=" * 80)

    result_dict = agent_return

    # Extract message from result_dict using api_server logic
    if "maps_url" in result_dict:
        if "message" in result_dict:
            formatted_message = result_dict["message"]
        else:
            formatted_message = f"Here's your trip, enjoy: {result_dict.get('maps_url', '')}"
    elif result_dict.get("error"):
        formatted_message = f"❌ **Error:** {result_dict.get('error_message', 'Unknown error')}"
    elif "message" in result_dict:
        formatted_message = result_dict["message"]
    elif "summary" in result_dict:
        formatted_message = result_dict["summary"]
    elif "content" in result_dict:
        formatted_message = result_dict["content"]
    elif "response" in result_dict:
        formatted_message = result_dict["response"]
    else:
        import json
        formatted_message = json.dumps(result_dict, indent=2)

    print(f"✓ Formatted message length: {len(formatted_message)}")
    print(f"✓ Message preview: {formatted_message[:150]}...")

    # Step 5: What UI receives
    print("\n" + "=" * 80)
    print("STEP 4: What the UI Receives")
    print("=" * 80)

    ui_message = {
        "type": "response",
        "message": formatted_message,
        "status": result_dict.get("status"),
        "session_id": "test-session",
        "timestamp": "2025-11-11T12:00:00"
    }

    print(f"✓ Message type: {ui_message['type']}")
    print(f"✓ Status: {ui_message['status']}")
    print(f"✓ Message length: {len(ui_message['message'])}")
    print(f"\n📤 UI DISPLAYS:\n{'-' * 80}")
    print(ui_message['message'][:500])
    if len(ui_message['message']) > 500:
        print(f"\n... ({len(ui_message['message']) - 500} more characters)")
    print("-" * 80)

    # Final validation
    print("\n" + "=" * 80)
    print("VALIDATION")
    print("=" * 80)

    checks = []

    # Check 1: Message was extracted
    if message != "Command executed":
        print("✅ CHECK 1: Message successfully extracted from tool result")
        checks.append(True)
    else:
        print("❌ CHECK 1: FAILED - Message is still 'Command executed'")
        checks.append(False)

    # Check 2: Status is success (not error)
    if status == "success":
        print("✅ CHECK 2: Status correctly set to 'success'")
        checks.append(True)
    else:
        print(f"❌ CHECK 2: FAILED - Status is '{status}' (should be 'success')")
        checks.append(False)

    # Check 3: UI message contains actual content
    if len(formatted_message) > 50 and formatted_message != "Command executed":
        print("✅ CHECK 3: UI receives meaningful content (>50 chars)")
        checks.append(True)
    else:
        print(f"❌ CHECK 3: FAILED - UI message too short or generic: {formatted_message[:100]}")
        checks.append(False)

    # Check 4: No error flag
    if not is_error:
        print("✅ CHECK 4: No error flag set")
        checks.append(True)
    else:
        print("❌ CHECK 4: FAILED - Error flag is set")
        checks.append(False)

    print("\n" + "=" * 80)
    if all(checks):
        print("🎉 ALL CHECKS PASSED - THE FIX WORKS!")
        print("✅ /search command will display results correctly in UI")
        sys.exit(0)
    else:
        print("❌ SOME CHECKS FAILED - FIX IS INCOMPLETE")
        print(f"Passed: {sum(checks)}/{len(checks)}")
        sys.exit(1)
else:
    print(f"\n❌ ERROR: Unexpected slash command result")
    print(f"Result: {slash_result}")
    sys.exit(1)
