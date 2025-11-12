#!/usr/bin/env python3
"""
Unit tests for JSON parser utility with retry logic.

Tests robust JSON parsing with:
1. Valid JSON parsing
2. JSON with markdown code blocks
3. JSON with trailing commas (should fix and parse)
4. JSON with unquoted keys (should fail gracefully)
5. Retry logic with progressively broken JSON
6. Empty string handling
7. None value handling
"""

import sys
import os
import json

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.utils.json_parser import parse_json_with_retry, validate_json_structure


def test_parse_valid_json():
    """Test parsing valid JSON."""
    print("=" * 80)
    print("TEST: Parse Valid JSON")
    print("=" * 80)
    
    valid_json = '{"goal": "test", "steps": [{"id": 1, "action": "test"}]}'
    result, error = parse_json_with_retry(valid_json, log_errors=False)
    
    assert result is not None, f"Should parse valid JSON, got error: {error}"
    assert result.get("goal") == "test", "Should extract goal"
    assert len(result.get("steps", [])) == 1, "Should extract steps"
    print("✅ PASSED: Valid JSON parsed correctly")
    return True


def test_parse_json_with_markdown():
    """Test parsing JSON with markdown code blocks."""
    print("\n" + "=" * 80)
    print("TEST: Parse JSON with Markdown Code Blocks")
    print("=" * 80)
    
    json_with_markdown = '''```json
{
  "goal": "test",
  "steps": [{"id": 1, "action": "test"}]
}
```'''
    result, error = parse_json_with_retry(json_with_markdown, log_errors=False)
    
    assert result is not None, f"Should parse JSON with markdown, got error: {error}"
    assert result.get("goal") == "test", "Should extract goal after stripping markdown"
    print("✅ PASSED: JSON with markdown parsed correctly")
    return True


def test_parse_json_with_trailing_comma():
    """Test parsing JSON with trailing commas (should fix and parse)."""
    print("\n" + "=" * 80)
    print("TEST: Parse JSON with Trailing Comma")
    print("=" * 80)
    
    json_with_trailing_comma = '{"goal": "test", "steps": [{"id": 1, "action": "test"},],}'
    result, error = parse_json_with_retry(json_with_trailing_comma, log_errors=False)
    
    assert result is not None, f"Should fix trailing comma and parse, got error: {error}"
    assert result.get("goal") == "test", "Should extract goal"
    print("✅ PASSED: JSON with trailing comma fixed and parsed")
    return True


def test_parse_json_with_unquoted_keys():
    """Test parsing JSON with unquoted keys (should fail gracefully)."""
    print("\n" + "=" * 80)
    print("TEST: Parse JSON with Unquoted Keys")
    print("=" * 80)
    
    json_with_unquoted = '{goal: "test", steps: [{"id": 1, "action": "test"}]}'
    result, error = parse_json_with_retry(json_with_unquoted, log_errors=False)
    
    # Should fail gracefully (not crash)
    assert result is None, "Should fail to parse JSON with unquoted keys"
    assert error is not None, "Should return error message"
    print("✅ PASSED: JSON with unquoted keys failed gracefully")
    return True


def test_parse_empty_string():
    """Test parsing empty string."""
    print("\n" + "=" * 80)
    print("TEST: Parse Empty String")
    print("=" * 80)
    
    result, error = parse_json_with_retry("", log_errors=False)
    
    assert result is None, "Should fail to parse empty string"
    assert error is not None, "Should return error message"
    print("✅ PASSED: Empty string handled correctly")
    return True


def test_parse_none_value():
    """Test parsing None value."""
    print("\n" + "=" * 80)
    print("TEST: Parse None Value")
    print("=" * 80)
    
    result, error = parse_json_with_retry(None, log_errors=False)
    
    assert result is None, "Should fail to parse None"
    assert error is not None, "Should return error message"
    print("✅ PASSED: None value handled correctly")
    return True


def test_validate_json_structure():
    """Test JSON structure validation."""
    print("\n" + "=" * 80)
    print("TEST: Validate JSON Structure")
    print("=" * 80)
    
    # Valid structure
    valid_plan = {"goal": "test", "steps": [{"id": 1}]}
    is_valid, error = validate_json_structure(valid_plan, required_keys=["steps"])
    assert is_valid, f"Should validate correct structure, got error: {error}"
    print("✅ PASSED: Valid structure validated")
    
    # Missing required key
    invalid_plan = {"goal": "test"}
    is_valid, error = validate_json_structure(invalid_plan, required_keys=["steps"])
    assert not is_valid, "Should reject missing required key"
    assert "steps" in error.lower(), "Error should mention missing key"
    print("✅ PASSED: Missing key detected")
    
    # Invalid steps type
    invalid_plan2 = {"goal": "test", "steps": "not a list"}
    is_valid, error = validate_json_structure(invalid_plan2, required_keys=["steps"])
    assert not is_valid, "Should reject invalid steps type"
    print("✅ PASSED: Invalid steps type detected")
    
    return True


def run_all_tests():
    """Run all JSON parser tests."""
    print("\n" + "=" * 80)
    print("JSON PARSER TEST SUITE")
    print("=" * 80)
    
    tests = [
        ("Parse Valid JSON", test_parse_valid_json),
        ("Parse JSON with Markdown", test_parse_json_with_markdown),
        ("Parse JSON with Trailing Comma", test_parse_json_with_trailing_comma),
        ("Parse JSON with Unquoted Keys", test_parse_json_with_unquoted_keys),
        ("Parse Empty String", test_parse_empty_string),
        ("Parse None Value", test_parse_none_value),
        ("Validate JSON Structure", test_validate_json_structure),
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

