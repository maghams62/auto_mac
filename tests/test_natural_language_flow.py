#!/usr/bin/env python3
"""
Test the natural language flow (without slash command).
This simulates: "search whats arsenal's score"
"""

import sys
from pathlib import Path
project_root = Path(__file__).resolve().parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv()

from src.agent.agent import AutomationAgent
from src.utils import load_config
from src.memory import SessionManager

print("=" * 80)
print("NATURAL LANGUAGE FLOW TEST: search whats arsenal's score")
print("=" * 80)

# Initialize agent
config = load_config()
session_manager = SessionManager(storage_dir="data/sessions")
agent = AutomationAgent(config, session_manager=session_manager)

# Test natural language query (no slash)
user_input = "search whats arsenal's score"
print(f"\n📥 USER INPUT: {user_input}")
print("(No slash - goes through full LangGraph workflow)")

print("\n" + "=" * 80)
print("Running agent.run() with natural language query...")
print("=" * 80)

try:
    result = agent.run(user_input, session_id="test-nl-session")

    print("\n✓ Agent completed")
    print(f"✓ Result keys: {list(result.keys()) if isinstance(result, dict) else 'not a dict'}")

    if isinstance(result, dict):
        # Check what we got back
        status = result.get("status")
        message = result.get("message")
        final_result = result.get("final_result", {})

        print(f"\n📊 RESULT STRUCTURE:")
        print(f"  Status: {status}")
        print(f"  Has 'message' field: {bool(message)}")
        print(f"  Message length: {len(message) if message else 0}")

        if final_result and isinstance(final_result, dict):
            print(f"\n📊 FINAL_RESULT STRUCTURE:")
            print(f"  Keys: {list(final_result.keys())}")
            print(f"  Has 'message' field: {'message' in final_result}")

            fr_message = final_result.get("message")
            if fr_message:
                print(f"  final_result['message'] length: {len(fr_message)}")
                print(f"  Message preview: {fr_message[:150]}...")

        print("\n" + "=" * 80)
        print("VALIDATION")
        print("=" * 80)

        checks = []

        # Check 1: Has a message field
        if message:
            print(f"✅ CHECK 1: Result has 'message' field ({len(message)} chars)")
            checks.append(True)
        else:
            print("❌ CHECK 1: FAILED - No 'message' field in result")
            checks.append(False)

        # Check 2: Message is meaningful
        if message and len(message) > 50 and message != "Command executed":
            print("✅ CHECK 2: Message contains meaningful content (>50 chars)")
            print(f"\n📤 MESSAGE PREVIEW:")
            print("-" * 80)
            print(message[:500])
            if len(message) > 500:
                print(f"... ({len(message) - 500} more characters)")
            print("-" * 80)
            checks.append(True)
        else:
            print(f"❌ CHECK 2: FAILED - Message is too short or generic: '{message[:100] if message else 'None'}'")
            checks.append(False)

        # Check 3: Status is success
        if status in ["success", "completed", "partial_success"]:
            print(f"✅ CHECK 3: Status is '{status}' (good)")
            checks.append(True)
        else:
            print(f"❌ CHECK 3: FAILED - Status is '{status}'")
            checks.append(False)

        print("\n" + "=" * 80)
        if all(checks):
            print("🎉 ALL CHECKS PASSED - NATURAL LANGUAGE FIX WORKS!")
            print("✅ Natural language 'search' queries will display results correctly")
            sys.exit(0)
        else:
            print("❌ SOME CHECKS FAILED")
            print(f"Passed: {sum(checks)}/{len(checks)}")
            sys.exit(1)
    else:
        print(f"❌ ERROR: Result is not a dict: {type(result)}")
        sys.exit(1)

except Exception as e:
    print(f"\n❌ ERROR: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
