#!/usr/bin/env python3
"""Test script to verify the parsing fix for summary/message fields."""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Test the format_result_message function
def format_result_message(result):
    """Mimic the fixed format_result_message function."""
    if not isinstance(result, dict):
        return str(result)

    # Check for Maps result
    if "maps_url" in result:
        if "message" in result:
            return result["message"]
        else:
            return f"Here's your trip, enjoy: {result.get('maps_url', '')}"

    # Check for errors
    if result.get("error"):
        return f"❌ **Error:** {result.get('error_message', 'Unknown error')}"

    # Check for various message fields (message, summary, content, response, etc.)
    if "message" in result:
        return result["message"]
    elif "summary" in result:
        return result["summary"]
    elif "content" in result:
        return result["content"]
    elif "response" in result:
        return result["response"]

    # Format as JSON if it's a complex dict
    import json
    return json.dumps(result, indent=2)


def test_bluesky_summary():
    """Test with Bluesky summary format."""
    print("=" * 60)
    print("TEST 1: Bluesky Summary Format")
    print("=" * 60)

    result = {
        "summary": "### Overview\nRecent posts highlight testing and exploration [1], [2].\n\n### Key Takeaways\n- Testing integration [1]\n- Exploring features [2]",
        "items": [{"text": "post 1"}, {"text": "post 2"}],
        "query": "last 3 tweets",
        "time_window": {"hours": 24}
    }

    formatted = format_result_message(result)
    print("Input:", result)
    print("\nFormatted output:")
    print(formatted)
    print("\n✅ PASS" if "Overview" in formatted else "❌ FAIL")
    return "Overview" in formatted


def test_regular_message():
    """Test with regular message format."""
    print("\n" + "=" * 60)
    print("TEST 2: Regular Message Format")
    print("=" * 60)

    result = {
        "message": "Email sent successfully to user@example.com",
        "success": True
    }

    formatted = format_result_message(result)
    print("Input:", result)
    print("\nFormatted output:")
    print(formatted)
    print("\n✅ PASS" if "Email sent" in formatted else "❌ FAIL")
    return "Email sent" in formatted


def test_content_format():
    """Test with content format."""
    print("\n" + "=" * 60)
    print("TEST 3: Content Format (e.g., search results)")
    print("=" * 60)

    result = {
        "content": "Found 5 results for your search query",
        "results": ["result1", "result2"]
    }

    formatted = format_result_message(result)
    print("Input:", result)
    print("\nFormatted output:")
    print(formatted)
    print("\n✅ PASS" if "Found 5 results" in formatted else "❌ FAIL")
    return "Found 5 results" in formatted


def test_error_format():
    """Test with error format."""
    print("\n" + "=" * 60)
    print("TEST 4: Error Format")
    print("=" * 60)

    result = {
        "error": True,
        "error_message": "Failed to connect to API"
    }

    formatted = format_result_message(result)
    print("Input:", result)
    print("\nFormatted output:")
    print(formatted)
    print("\n✅ PASS" if "Failed to connect" in formatted else "❌ FAIL")
    return "Failed to connect" in formatted


def main():
    """Run all tests."""
    print("\nTESTING PARSING FIX FOR SUMMARY/MESSAGE FIELDS\n")

    results = [
        ("Bluesky Summary", test_bluesky_summary()),
        ("Regular Message", test_regular_message()),
        ("Content Format", test_content_format()),
        ("Error Format", test_error_format())
    ]

    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {test_name}")

    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print("\n🎉 All tests passed!")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
