#!/usr/bin/env python3
"""
Integration tests for plan parsing robustness.

Tests that the agent can handle:
1. Plan creation with various query types
2. Plan parsing with malformed JSON (should retry and succeed)
3. Plan parsing with completely invalid JSON (should fail gracefully)
4. Plan structure validation
"""

import sys
import os
from unittest.mock import Mock, patch

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.utils.json_parser import parse_json_with_retry, validate_json_structure


def test_parse_plan_with_markdown():
    """Test parsing plan JSON with markdown code blocks."""
    print("=" * 80)
    print("TEST: Parse Plan with Markdown")
    print("=" * 80)
    
    plan_with_markdown = '''Here's the plan:

```json
{
  "goal": "Test goal",
  "steps": [
    {
      "id": 1,
      "action": "test_action",
      "parameters": {},
      "dependencies": []
    }
  ],
  "complexity": "simple"
}
```

That's the plan!'''
    
    result, error = parse_json_with_retry(plan_with_markdown, log_errors=False)
    
    assert result is not None, f"Should parse plan with markdown, got error: {error}"
    assert result.get("goal") == "Test goal", "Should extract goal"
    assert len(result.get("steps", [])) == 1, "Should extract steps"
    print("✅ PASSED: Plan with markdown parsed correctly")
    return True


def test_parse_plan_with_trailing_comma():
    """Test parsing plan with trailing commas."""
    print("\n" + "=" * 80)
    print("TEST: Parse Plan with Trailing Comma")
    print("=" * 80)
    
    plan_with_trailing = '''{
  "goal": "Test goal",
  "steps": [
    {
      "id": 1,
      "action": "test_action",
      "parameters": {},
      "dependencies": [],
    },
  ],
  "complexity": "simple",
}'''
    
    result, error = parse_json_with_retry(plan_with_trailing, log_errors=False)
    
    assert result is not None, f"Should fix trailing comma and parse, got error: {error}"
    assert result.get("goal") == "Test goal", "Should extract goal"
    print("✅ PASSED: Plan with trailing comma fixed and parsed")
    return True


def test_parse_invalid_plan():
    """Test parsing completely invalid plan (should fail gracefully)."""
    print("\n" + "=" * 80)
    print("TEST: Parse Invalid Plan")
    print("=" * 80)
    
    invalid_plan = "This is not JSON at all! Just some random text."
    result, error = parse_json_with_retry(invalid_plan, log_errors=False)
    
    assert result is None, "Should fail to parse invalid plan"
    assert error is not None, "Should return error message"
    print("✅ PASSED: Invalid plan failed gracefully")
    return True


def test_validate_plan_structure():
    """Test plan structure validation."""
    print("\n" + "=" * 80)
    print("TEST: Validate Plan Structure")
    print("=" * 80)
    
    # Valid plan structure
    valid_plan = {
        "goal": "Test goal",
        "steps": [
            {"id": 1, "action": "test_action", "parameters": {}, "dependencies": []}
        ],
        "complexity": "simple"
    }
    is_valid, error = validate_json_structure(valid_plan, required_keys=["steps"])
    assert is_valid, f"Should validate correct plan structure, got error: {error}"
    print("✅ PASSED: Valid plan structure validated")
    
    # Missing steps
    invalid_plan1 = {"goal": "Test goal"}
    is_valid, error = validate_json_structure(invalid_plan1, required_keys=["steps"])
    assert not is_valid, "Should reject plan missing steps"
    print("✅ PASSED: Missing steps detected")
    
    # Invalid steps type
    invalid_plan2 = {"goal": "Test goal", "steps": "not a list"}
    is_valid, error = validate_json_structure(invalid_plan2, required_keys=["steps"])
    assert not is_valid, "Should reject plan with invalid steps type"
    print("✅ PASSED: Invalid steps type detected")
    
    return True


def test_parse_plan_array_format():
    """Test parsing plan in array format (should wrap in dict)."""
    print("\n" + "=" * 80)
    print("TEST: Parse Plan Array Format")
    print("=" * 80)
    
    plan_array = '''[
  {
    "id": 1,
    "action": "test_action",
    "parameters": {},
    "dependencies": []
  }
]'''
    
    result, error = parse_json_with_retry(plan_array, log_errors=False)
    
    assert result is not None, f"Should parse array format, got error: {error}"
    assert "steps" in result, "Should wrap array in dict with 'steps' key"
    assert len(result.get("steps", [])) == 1, "Should extract steps from array"
    print("✅ PASSED: Plan array format parsed correctly")
    return True


def run_all_tests():
    """Run all plan parsing robustness tests."""
    print("\n" + "=" * 80)
    print("PLAN PARSING ROBUSTNESS TEST SUITE")
    print("=" * 80)
    
    tests = [
        ("Parse Plan with Markdown", test_parse_plan_with_markdown),
        ("Parse Plan with Trailing Comma", test_parse_plan_with_trailing_comma),
        ("Parse Invalid Plan", test_parse_invalid_plan),
        ("Validate Plan Structure", test_validate_plan_structure),
        ("Parse Plan Array Format", test_parse_plan_array_format),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result, None))
        except Exception as e:
            print(f"\n❌ Test '{test_name}' crashed: {e}")
            import traceback
            traceback.print_exc()
            results.append((test_name, False, str(e)))
    
    # Summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    
    passed = sum(1 for _, success, _ in results if success)
    total = len(results)
    
    for test_name, success, error in results:
        status = "✅ PASSED" if success else f"❌ FAILED: {error or 'Test failed'}"
        print(f"  {test_name}: {status}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    return passed == total


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)

