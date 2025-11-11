#!/usr/bin/env python3
"""
Comprehensive test: Verify ALL parsing scenarios work correctly.
Tests:
1. Bluesky tweet reading and summarization
2. Folder summarization
3. Search (already tested)
"""

import sys
from pathlib import Path
project_root = Path(__file__).resolve().parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv()

from src.agent.agent import AutomationAgent
from src.agent.agent_registry import AgentRegistry
from src.ui.slash_commands import SlashCommandHandler
from src.utils import load_config
from src.memory import SessionManager

print("=" * 80)
print("COMPREHENSIVE PARSING TEST - ALL SCENARIOS")
print("=" * 80)

# Initialize components
config = load_config()
session_manager = SessionManager(storage_dir="data/sessions")
agent = AutomationAgent(config, session_manager=session_manager)
registry = AgentRegistry(config, session_manager=session_manager)
handler = SlashCommandHandler(registry, config)

test_results = []

# ============================================================================
# TEST 1: Bluesky Slash Command - Summarize Last 3 Tweets
# ============================================================================
print("\n" + "=" * 80)
print("TEST 1: Bluesky - /bluesky last 3 tweets")
print("=" * 80)

try:
    is_command, result = handler.handle("/bluesky last 3 tweets", session_id="test-bluesky")

    if isinstance(result, dict) and result.get("type") == "result":
        tool_result = result.get("result", {})

        # Extract message using the fix
        message = (
            tool_result.get("message") or
            tool_result.get("summary") or
            tool_result.get("content") or
            tool_result.get("response") or
            "Command executed"
        )

        print(f"✓ Command recognized: {is_command}")
        print(f"✓ Result type: {result.get('type')}")
        print(f"✓ Tool result keys: {list(tool_result.keys())}")
        print(f"✓ Message length: {len(message)}")

        if message != "Command executed" and len(message) > 100:
            print(f"✅ PASS - Bluesky summary extracted ({len(message)} chars)")
            print(f"Preview: {message[:150]}...")
            test_results.append(("Bluesky /bluesky", True))
        else:
            print(f"❌ FAIL - Message too short or generic: {message[:100]}")
            test_results.append(("Bluesky /bluesky", False))
    else:
        print(f"❌ FAIL - Unexpected result structure")
        test_results.append(("Bluesky /bluesky", False))
except Exception as e:
    print(f"❌ ERROR: {e}")
    test_results.append(("Bluesky /bluesky", False))

# ============================================================================
# TEST 2: Bluesky Natural Language - Summarize Last 3 Tweets
# ============================================================================
print("\n" + "=" * 80)
print("TEST 2: Bluesky - natural language 'summarize my last 3 tweets on bluesky'")
print("=" * 80)

try:
    result = agent.run("summarize my last 3 tweets on bluesky", session_id="test-bluesky-nl")

    if isinstance(result, dict):
        message = result.get("message", "")
        final_result = result.get("final_result", {})

        # Check final_result too
        fr_message = final_result.get("message", "") if isinstance(final_result, dict) else ""
        display_message = message or fr_message

        print(f"✓ Result status: {result.get('status')}")
        print(f"✓ Message length: {len(display_message)}")

        if display_message and len(display_message) > 100:
            print(f"✅ PASS - Bluesky NL summary extracted ({len(display_message)} chars)")
            print(f"Preview: {display_message[:150]}...")
            test_results.append(("Bluesky natural language", True))
        else:
            print(f"❌ FAIL - Message too short: {display_message[:100]}")
            test_results.append(("Bluesky natural language", False))
    else:
        print(f"❌ FAIL - Result not a dict")
        test_results.append(("Bluesky natural language", False))
except Exception as e:
    print(f"❌ ERROR: {e}")
    import traceback
    traceback.print_exc()
    test_results.append(("Bluesky natural language", False))

# ============================================================================
# TEST 3: Folder - Slash Command
# ============================================================================
print("\n" + "=" * 80)
print("TEST 3: Folder - /folder summarize test_docs")
print("=" * 80)

try:
    is_command, result = handler.handle("/folder summarize test_docs", session_id="test-folder")

    if isinstance(result, dict) and result.get("type") == "result":
        tool_result = result.get("result", {})

        # Extract message using the fix
        message = (
            tool_result.get("message") or
            tool_result.get("summary") or
            tool_result.get("content") or
            tool_result.get("response") or
            "Command executed"
        )

        print(f"✓ Command recognized: {is_command}")
        print(f"✓ Result type: {result.get('type')}")
        print(f"✓ Tool result keys: {list(tool_result.keys())}")
        print(f"✓ Message length: {len(message)}")

        if message != "Command executed" and len(message) > 50:
            print(f"✅ PASS - Folder summary extracted ({len(message)} chars)")
            print(f"Preview: {message[:150]}...")
            test_results.append(("Folder /folder", True))
        else:
            print(f"❌ FAIL - Message too short or generic: {message[:100]}")
            test_results.append(("Folder /folder", False))
    else:
        print(f"❌ FAIL - Unexpected result structure")
        print(f"Result: {result}")
        test_results.append(("Folder /folder", False))
except Exception as e:
    print(f"❌ ERROR: {e}")
    import traceback
    traceback.print_exc()
    test_results.append(("Folder /folder", False))

# ============================================================================
# TEST 4: Search - Natural Language (we already tested this)
# ============================================================================
print("\n" + "=" * 80)
print("TEST 4: Search - natural language 'search python programming'")
print("=" * 80)

try:
    result = agent.run("search python programming", session_id="test-search-nl")

    if isinstance(result, dict):
        message = result.get("message", "")
        final_result = result.get("final_result", {})
        fr_message = final_result.get("message", "") if isinstance(final_result, dict) else ""
        display_message = message or fr_message

        print(f"✓ Result status: {result.get('status')}")
        print(f"✓ Message length: {len(display_message)}")

        if display_message and len(display_message) > 100:
            print(f"✅ PASS - Search summary extracted ({len(display_message)} chars)")
            print(f"Preview: {display_message[:150]}...")
            test_results.append(("Search natural language", True))
        else:
            print(f"❌ FAIL - Message too short: {display_message[:100]}")
            test_results.append(("Search natural language", False))
    else:
        print(f"❌ FAIL - Result not a dict")
        test_results.append(("Search natural language", False))
except Exception as e:
    print(f"❌ ERROR: {e}")
    import traceback
    traceback.print_exc()
    test_results.append(("Search natural language", False))

# ============================================================================
# SUMMARY
# ============================================================================
print("\n" + "=" * 80)
print("TEST SUMMARY")
print("=" * 80)

passed = sum(1 for _, result in test_results if result)
total = len(test_results)

for test_name, result in test_results:
    status = "✅ PASS" if result else "❌ FAIL"
    print(f"{status}: {test_name}")

print(f"\nTotal: {passed}/{total} tests passed")

if passed == total:
    print("\n🎉 ALL PARSING SCENARIOS WORK!")
    print("✅ Bluesky slash command")
    print("✅ Bluesky natural language")
    print("✅ Folder slash command")
    print("✅ Search natural language")
    print("\n⚠️  REMEMBER: Restart api_server.py to apply these fixes in the UI!")
    sys.exit(0)
else:
    print(f"\n⚠️  {total - passed} test(s) failed")
    sys.exit(1)
