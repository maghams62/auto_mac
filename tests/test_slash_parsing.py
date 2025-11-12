#!/usr/bin/env python3
"""Test to understand the slash command result structure."""

# Simulate what slash command handler returns for search
slash_result = {
    "type": "result",
    "agent": "google",
    "command": "search",
    "result": {
        "query": "arsenal's score",
        "summary": "Arsenal won 2-1 against Manchester United...",
        "results": [...],
        "num_results": 5
    }
}

# Simulate what agent.py does with my fix
tool_result = slash_result.get("result", {})

# Extract message
message = (
    tool_result.get("message") or
    tool_result.get("summary") or
    tool_result.get("content") or
    tool_result.get("response") or
    "Command executed"
)

print("=" * 60)
print("SIMULATING SLASH COMMAND RESULT PARSING")
print("=" * 60)

print("\n1. Slash command returns:")
print(f"   Type: {slash_result['type']}")
print(f"   Agent: {slash_result['agent']}")
print(f"   Result keys: {list(slash_result['result'].keys())}")

print("\n2. After extraction (agent.py line 803):")
print(f"   tool_result: {tool_result}")

print("\n3. Message extraction (agent.py line 805-811):")
print(f"   Has 'message' field: {bool(tool_result.get('message'))}")
print(f"   Has 'summary' field: {bool(tool_result.get('summary'))}")
print(f"   Extracted message: {message[:100]}...")

print("\n4. Status check (agent.py line 813):")
print(f"   Has 'success' field: {bool(tool_result.get('success'))}")
print(f"   tool_result.get('success'): {tool_result.get('success')}")
print(f"   Status will be: {'success' if tool_result.get('success') else 'error'}")

print("\n5. Final return from agent.py:")
final_return = {
    "status": "success" if tool_result.get("success") else "error",
    "message": message,
    "final_result": tool_result,
    "results": {1: tool_result}
}
print(f"   Status: {final_return['status']}")
print(f"   Message length: {len(final_return['message'])}")
print(f"   Message preview: {final_return['message'][:100]}...")

print("\n" + "=" * 60)
print("DIAGNOSIS")
print("=" * 60)

if final_return['status'] == 'error':
    print("⚠️  ISSUE: Status is 'error' because search result has no 'success' field")
    print("   This might cause UI to ignore the message!")
else:
    print("✅ Status is 'success'")

if message and message != "Command executed":
    print("✅ Message extracted successfully from 'summary' field")
else:
    print("❌ Failed to extract message")
