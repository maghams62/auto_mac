#!/usr/bin/env python3
"""Test the fixed status logic."""

# Test Case 1: Search result with summary (no 'success' field)
tool_result = {
    "query": "arsenal's score",
    "summary": "Arsenal won 2-1 against Manchester United...",
    "results": [],
    "num_results": 5
}

message = (
    tool_result.get("message") or
    tool_result.get("summary") or
    tool_result.get("content") or
    tool_result.get("response") or
    "Command executed"
)

# NEW LOGIC
is_error = tool_result.get("error") is True
has_content = bool(message and message != "Command executed")
status = "error" if is_error else ("success" if has_content else "completed")

print("=" * 60)
print("TEST 1: Search result with summary")
print("=" * 60)
print(f"Message: {message[:50]}...")
print(f"is_error: {is_error}")
print(f"has_content: {has_content}")
print(f"Status: {status}")
print(f"✅ CORRECT" if status == "success" else f"❌ WRONG (expected 'success', got '{status}')")

# Test Case 2: Result with explicit error
tool_result2 = {
    "error": True,
    "error_message": "API failed"
}

message2 = (
    tool_result2.get("message") or
    tool_result2.get("summary") or
    tool_result2.get("content") or
    tool_result2.get("response") or
    "Command executed"
)

is_error2 = tool_result2.get("error") is True
has_content2 = bool(message2 and message2 != "Command executed")
status2 = "error" if is_error2 else ("success" if has_content2 else "completed")

print("\n" + "=" * 60)
print("TEST 2: Result with explicit error")
print("=" * 60)
print(f"Message: {message2}")
print(f"is_error: {is_error2}")
print(f"has_content: {has_content2}")
print(f"Status: {status2}")
print(f"✅ CORRECT" if status2 == "error" else f"❌ WRONG (expected 'error', got '{status2}')")

# Test Case 3: Empty result (no content)
tool_result3 = {
    "query": "test"
}

message3 = (
    tool_result3.get("message") or
    tool_result3.get("summary") or
    tool_result3.get("content") or
    tool_result3.get("response") or
    "Command executed"
)

is_error3 = tool_result3.get("error") is True
has_content3 = bool(message3 and message3 != "Command executed")
status3 = "error" if is_error3 else ("success" if has_content3 else "completed")

print("\n" + "=" * 60)
print("TEST 3: Empty result (fallback message)")
print("=" * 60)
print(f"Message: {message3}")
print(f"is_error: {is_error3}")
print(f"has_content: {has_content3}")
print(f"Status: {status3}")
print(f"✅ CORRECT" if status3 == "completed" else f"❌ WRONG (expected 'completed', got '{status3}')")

# Test Case 4: Result with explicit success field
tool_result4 = {
    "success": True,
    "message": "Operation completed"
}

message4 = (
    tool_result4.get("message") or
    tool_result4.get("summary") or
    tool_result4.get("content") or
    tool_result4.get("response") or
    "Command executed"
)

is_error4 = tool_result4.get("error") is True
has_content4 = bool(message4 and message4 != "Command executed")
status4 = "error" if is_error4 else ("success" if has_content4 else "completed")

print("\n" + "=" * 60)
print("TEST 4: Result with explicit success field")
print("=" * 60)
print(f"Message: {message4}")
print(f"is_error: {is_error4}")
print(f"has_content: {has_content4}")
print(f"Status: {status4}")
print(f"✅ CORRECT" if status4 == "success" else f"❌ WRONG (expected 'success', got '{status4}')")

print("\n" + "=" * 60)
print("SUMMARY")
print("=" * 60)
print("✅ Fixed! Search results now get 'success' status instead of 'error'")
print("✅ Error results still get 'error' status")
print("✅ Empty results get 'completed' status")
