"""
Regression tests for template string resolution.

These tests ensure that both executors (PlanExecutor and AutomationAgent)
resolve template strings correctly and consistently.

Critical bug this prevents:
- UI showing "Found {2} groups" instead of "Found 2 groups"
- Braces being left in output after partial resolution
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.utils.template_resolver import (
    resolve_template_string,
    resolve_direct_reference,
    resolve_parameters
)


def test_template_syntax_with_braces():
    """Test that {$stepN.field} syntax resolves correctly (removes braces)."""
    step_results = {1: {"count": 5, "total": 10}}

    # Single placeholder
    result = resolve_template_string("Found {$step1.count} items", step_results)
    assert result == "Found 5 items", f"Expected 'Found 5 items', got '{result}'"
    assert "{" not in result, f"Result contains braces: {result}"
    assert "}" not in result, f"Result contains braces: {result}"

    # Multiple placeholders
    result = resolve_template_string(
        "Found {$step1.count} items out of {$step1.total}",
        step_results
    )
    assert result == "Found 5 items out of 10", f"Expected 'Found 5 items out of 10', got '{result}'"
    assert "{" not in result, f"Result contains braces: {result}"
    assert "}" not in result, f"Result contains braces: {result}"

    print("✅ Template syntax with braces resolves correctly")


def test_direct_reference_syntax():
    """Test that $stepN.field syntax resolves correctly (no braces)."""
    step_results = {1: {"count": 5, "price": 225.50}}

    # Direct reference
    result = resolve_template_string("Price is $step1.price", step_results)
    # Python converts 225.50 to 225.5 when converting to string
    assert result == "Price is 225.5", f"Expected 'Price is 225.5', got '{result}'"
    assert "$step" not in result, f"Result contains unresolved reference: {result}"

    print("✅ Direct reference syntax resolves correctly")


def test_mixed_syntax():
    """Test that both syntaxes can be used in the same string."""
    step_results = {1: {"count": 5}, 2: {"price": 10.50}}

    result = resolve_template_string(
        "Found {$step1.count} items at $step2.price each",
        step_results
    )
    assert result == "Found 5 items at 10.5 each", f"Expected 'Found 5 items at 10.5 each', got '{result}'"
    assert "{" not in result, f"Result contains braces: {result}"
    assert "$step" not in result, f"Result contains unresolved reference: {result}"

    print("✅ Mixed syntax resolves correctly")


def test_nested_field_paths():
    """Test that nested field paths resolve correctly."""
    step_results = {
        1: {
            "metadata": {
                "file_size": 1024,
                "file_name": "test.pdf"
            }
        }
    }

    # Test direct reference with nested path
    result = resolve_direct_reference("$step1.metadata.file_size", step_results)
    assert result == 1024, f"Expected 1024, got {result}"

    result = resolve_direct_reference("$step1.metadata.file_name", step_results)
    assert result == "test.pdf", f"Expected 'test.pdf', got {result}"

    # Test template string with nested path
    result = resolve_template_string("File size is {$step1.metadata.file_size} bytes", step_results)
    assert result == "File size is 1024 bytes", f"Expected 'File size is 1024 bytes', got '{result}'"

    # Test direct reference in string with nested path
    result = resolve_template_string("File name: $step1.metadata.file_name", step_results)
    assert result == "File name: test.pdf", f"Expected 'File name: test.pdf', got '{result}'"

    print("✅ Nested field paths resolve correctly")


def test_array_access():
    """Test that array indices work correctly."""
    step_results = {
        1: {
            "files": [
                {"name": "file1.pdf"},
                {"name": "file2.pdf"}
            ]
        }
    }

    result = resolve_direct_reference("$step1.files.0.name", step_results)
    assert result == "file1.pdf", f"Expected 'file1.pdf', got {result}"

    print("✅ Array access resolves correctly")


def test_resolve_parameters_dict():
    """Test full parameter dictionary resolution."""
    step_results = {
        1: {
            "total_duplicate_groups": 2,
            "total_duplicate_files": 4,
            "wasted_space_mb": 0.38,
            "duplicates": [
                {"name": "file1.pdf"},
                {"name": "file2.pdf"}
            ]
        }
    }

    params = {
        "message": "Found {$step1.total_duplicate_groups} group(s) of duplicate files, wasting {$step1.wasted_space_mb} MB.",
        "details": "$step1.duplicates",
        "status": "success"
    }

    resolved = resolve_parameters(params, step_results)

    # Check message resolved correctly (NO BRACES!)
    expected_message = "Found 2 group(s) of duplicate files, wasting 0.38 MB."
    assert resolved["message"] == expected_message, \
        f"Expected '{expected_message}', got '{resolved['message']}'"
    assert "{" not in resolved["message"], \
        f"Message contains braces: {resolved['message']}"
    assert "}" not in resolved["message"], \
        f"Message contains braces: {resolved['message']}"

    # Check details resolved to array
    assert resolved["details"] == step_results[1]["duplicates"], \
        f"Expected array, got {resolved['details']}"

    # Check status passed through unchanged
    assert resolved["status"] == "success"

    print("✅ Full parameter dictionary resolves correctly")


def test_no_orphaned_braces():
    """CRITICAL: Ensure no orphaned braces like {2} remain after resolution."""
    step_results = {1: {"count": 2, "space": 0.38}}

    # This is the exact bug we're preventing
    result = resolve_template_string(
        "Found {$step1.count} groups, wasting {$step1.space} MB",
        step_results
    )

    # Check no orphaned braces
    assert "{2}" not in result, f"Found orphaned {{2}} in: {result}"
    assert "{0.38}" not in result, f"Found orphaned {{0.38}} in: {result}"
    assert result == "Found 2 groups, wasting 0.38 MB", \
        f"Expected 'Found 2 groups, wasting 0.38 MB', got '{result}'"

    print("✅ CRITICAL: No orphaned braces in output")


def test_missing_step_graceful_fallback():
    """Test that missing steps don't crash, keep placeholder."""
    step_results = {1: {"count": 5}}

    # Reference non-existent step
    result = resolve_template_string("Found {$step2.count} items", step_results)
    assert "{$step2.count}" in result, \
        f"Missing step should keep placeholder, got: {result}"

    print("✅ Missing step handled gracefully")


def test_missing_field_graceful_fallback():
    """Test that missing fields don't crash, keep placeholder."""
    step_results = {1: {"count": 5}}

    # Reference non-existent field
    result = resolve_template_string("Found {$step1.missing} items", step_results)
    assert "{$step1.missing}" in result, \
        f"Missing field should keep placeholder, got: {result}"

    print("✅ Missing field handled gracefully")


def test_empty_string_unchanged():
    """Test that empty strings pass through unchanged."""
    step_results = {1: {"count": 5}}

    result = resolve_template_string("", step_results)
    assert result == "", f"Expected empty string, got '{result}'"

    print("✅ Empty strings handled correctly")


def test_no_placeholders_unchanged():
    """Test that strings without placeholders pass through unchanged."""
    step_results = {1: {"count": 5}}

    result = resolve_template_string("No placeholders here!", step_results)
    assert result == "No placeholders here!", \
        f"Expected 'No placeholders here!', got '{result}'"

    print("✅ Strings without placeholders pass through unchanged")


def test_invalid_placeholder_patterns_not_resolved():
    """Test that invalid patterns like {file1.name} are NOT resolved."""
    step_results = {1: {"count": 2, "duplicates": ["file1.pdf", "file2.pdf"]}}

    # The OLD wrong prompt example used these invalid patterns
    bad_pattern = "Group 1:\n- {file1.name}\n- {file2.name}"

    # These should NOT be resolved because they're not valid template syntax
    result = resolve_template_string(bad_pattern, step_results)

    # The result should be unchanged (resolver doesn't recognize these patterns)
    assert result == bad_pattern, \
        f"Invalid patterns should remain unchanged, got: {result}"

    # Verify the patterns are still there (showing they're invalid)
    assert "{file1.name}" in result, "Invalid pattern {file1.name} should remain"
    assert "{file2.name}" in result, "Invalid pattern {file2.name} should remain"

    print("✅ CRITICAL: Invalid placeholder patterns NOT resolved (as expected)")


def run_all_tests():
    """Run all template resolution tests."""
    print("\n" + "=" * 60)
    print("TEMPLATE RESOLUTION REGRESSION TESTS")
    print("=" * 60 + "\n")

    tests = [
        test_template_syntax_with_braces,
        test_direct_reference_syntax,
        test_mixed_syntax,
        test_nested_field_paths,
        test_array_access,
        test_resolve_parameters_dict,
        test_no_orphaned_braces,  # CRITICAL TEST
        test_missing_step_graceful_fallback,
        test_missing_field_graceful_fallback,
        test_empty_string_unchanged,
        test_no_placeholders_unchanged,
        test_invalid_placeholder_patterns_not_resolved,  # CRITICAL TEST for prompt regression
    ]

    failed = []

    for test_func in tests:
        try:
            test_func()
        except AssertionError as e:
            print(f"❌ {test_func.__name__} FAILED: {e}")
            failed.append((test_func.__name__, str(e)))
        except Exception as e:
            print(f"❌ {test_func.__name__} ERROR: {e}")
            failed.append((test_func.__name__, str(e)))

    print("\n" + "=" * 60)
    if failed:
        print(f"❌ {len(failed)} TEST(S) FAILED:")
        for name, error in failed:
            print(f"  - {name}: {error}")
        print("=" * 60)
        return False
    else:
        print(f"✅ ALL {len(tests)} TESTS PASSED!")
        print("=" * 60)
        return True


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
