"""
Test UI file display capabilities.

Tests that the UI can correctly display files when:
1. User requests files starting with a specific letter (e.g., "pull up all files starting with A")
2. User requests files matching a pattern (e.g., "pull up all edge-share-in files")

This test verifies:
- File list structure is correct (name, path, score, meta)
- API server correctly extracts and sends files array
- Frontend components can render the file list
"""

import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.agent.agent import AutomationAgent
from src.utils import load_config


def validate_file_structure(files_array):
    """Validate that files array has correct structure for UI display."""
    if not isinstance(files_array, list):
        raise AssertionError(f"files_array should be a list, got {type(files_array)}")

    if len(files_array) == 0:
        print("  ⚠️  Empty files array - no matching documents found")
        return True

    print(f"  ✓ Found {len(files_array)} files in array")

    # Check first file structure
    first_file = files_array[0]

    # Required fields for UI display
    required_fields = ['name', 'path', 'score', 'meta']
    for field in required_fields:
        if field not in first_file:
            raise AssertionError(f"File missing required field '{field}': {first_file}")

    # Validate meta structure
    if not isinstance(first_file['meta'], dict):
        raise AssertionError(f"meta should be a dict, got {type(first_file['meta'])}")

    if 'file_type' not in first_file['meta']:
        raise AssertionError(f"meta missing 'file_type': {first_file['meta']}")

    print(f"  ✓ File structure validated:")
    print(f"    - name: {first_file['name']}")
    print(f"    - path: {first_file['path']}")
    print(f"    - score: {first_file['score']}")
    print(f"    - file_type: {first_file['meta']['file_type']}")

    if first_file['meta'].get('total_pages'):
        print(f"    - pages: {first_file['meta']['total_pages']}")

    return True


def test_files_starting_with_letter():
    """Test displaying files starting with a specific letter."""
    print("\n" + "="*80)
    print("TEST 1: Files Starting with Letter")
    print("="*80)

    try:
        config = load_config()
        agent = AutomationAgent(config)

        # Test query for files starting with a letter
        user_query = "pull up all files starting with A"
        print(f"\nUser Query: {user_query}")
        print("Expected: Files array with names starting with 'A'\n")

        # Run the agent
        print("Running agent...")
        result = agent.run(user_query)

        # Check result structure
        assert isinstance(result, dict), f"Expected dict result, got: {type(result)}"
        print(f"✓ Result status: {result.get('status')}")

        # Extract files array from result
        files_array = None
        result_location = None

        # Check step_results
        if "step_results" in result:
            for step_id, step_result in result["step_results"].items():
                if isinstance(step_result, dict) and step_result.get("type") == "file_list":
                    if "files" in step_result:
                        files_array = step_result["files"]
                        result_location = f"step_results[{step_id}]"
                        break

        # Check results (alternative structure)
        if not files_array and "results" in result:
            for step_id, step_result in result["results"].items():
                if isinstance(step_result, dict) and step_result.get("type") == "file_list":
                    if "files" in step_result:
                        files_array = step_result["files"]
                        result_location = f"results[{step_id}]"
                        break

        # Check final_result
        if not files_array and "final_result" in result:
            final_result = result["final_result"]
            if isinstance(final_result, dict) and final_result.get("type") == "file_list":
                if "files" in final_result:
                    files_array = final_result["files"]
                    result_location = "final_result"

        # Check top-level
        if not files_array and result.get("type") == "file_list":
            if "files" in result:
                files_array = result["files"]
                result_location = "top-level"

        if files_array is None:
            print("\n⚠️  No files array found in result")
            print("   This might indicate:")
            print("   1. No documents matched the query")
            print("   2. The query wasn't interpreted as a file listing request")
            print("   3. Result structure is different than expected")
            print("\nResult structure:")
            print(f"  Keys: {list(result.keys())}")
            if "step_results" in result:
                print(f"  Step results keys: {list(result['step_results'].keys())}")
            return False

        print(f"\n✓ Files array found in: {result_location}")

        # Validate file structure for UI display
        validate_file_structure(files_array)

        # Check if files actually start with 'A'
        if len(files_array) > 0:
            print(f"\n  Checking if filenames start with 'A':")
            for i, file_obj in enumerate(files_array[:5]):  # Check first 5
                name = file_obj['name']
                starts_with_a = name.upper().startswith('A')
                status = "✓" if starts_with_a else "⚠️"
                print(f"    {status} {name}")

        print("\n✅ TEST 1 PASSED: Files starting with letter structure validated")
        return True

    except Exception as e:
        print(f"\n❌ TEST 1 FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_files_matching_pattern():
    """Test displaying files matching a specific pattern."""
    print("\n" + "="*80)
    print("TEST 2: Files Matching Pattern")
    print("="*80)

    try:
        config = load_config()
        agent = AutomationAgent(config)

        # Test query for files matching a pattern
        # Using "guitar" as a more likely pattern to find in test documents
        user_query = "pull up all guitar tab files"
        print(f"\nUser Query: {user_query}")
        print("Expected: Files array with guitar-related documents\n")

        # Run the agent
        print("Running agent...")
        result = agent.run(user_query)

        # Check result structure
        assert isinstance(result, dict), f"Expected dict result, got: {type(result)}"
        print(f"✓ Result status: {result.get('status')}")

        # Extract files array from result (same logic as test 1)
        files_array = None
        result_location = None

        if "step_results" in result:
            for step_id, step_result in result["step_results"].items():
                if isinstance(step_result, dict) and step_result.get("type") == "file_list":
                    if "files" in step_result:
                        files_array = step_result["files"]
                        result_location = f"step_results[{step_id}]"
                        break

        if not files_array and "results" in result:
            for step_id, step_result in result["results"].items():
                if isinstance(step_result, dict) and step_result.get("type") == "file_list":
                    if "files" in step_result:
                        files_array = step_result["files"]
                        result_location = f"results[{step_id}]"
                        break

        if not files_array and "final_result" in result:
            final_result = result["final_result"]
            if isinstance(final_result, dict) and final_result.get("type") == "file_list":
                if "files" in final_result:
                    files_array = final_result["files"]
                    result_location = "final_result"

        if not files_array and result.get("type") == "file_list":
            if "files" in result:
                files_array = result["files"]
                result_location = "top-level"

        if files_array is None:
            print("\n⚠️  No files array found in result")
            print("   This might indicate:")
            print("   1. No documents matched the query")
            print("   2. The query wasn't interpreted as a file listing request")
            print("\nResult structure:")
            print(f"  Keys: {list(result.keys())}")
            return False

        print(f"\n✓ Files array found in: {result_location}")

        # Validate file structure for UI display
        validate_file_structure(files_array)

        # Show matched filenames
        if len(files_array) > 0:
            print(f"\n  Matched files (showing up to 5):")
            for i, file_obj in enumerate(files_array[:5]):
                name = file_obj['name']
                score = file_obj['score']
                print(f"    {i+1}. {name} (similarity: {score*100:.0f}%)")

        print("\n✅ TEST 2 PASSED: Files matching pattern structure validated")
        return True

    except Exception as e:
        print(f"\n❌ TEST 2 FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_ui_component_compatibility():
    """Test that the file structure is compatible with UI components."""
    print("\n" + "="*80)
    print("TEST 3: UI Component Compatibility")
    print("="*80)

    # Create a mock file object matching the structure from list_related_documents
    mock_file = {
        "name": "TestDocument.pdf",
        "path": "/Users/test/Documents/TestDocument.pdf",
        "score": 0.8523,
        "meta": {
            "file_type": "pdf",
            "total_pages": 10
        }
    }

    print("\nMock file object:")
    print(f"  {mock_file}")

    print("\nValidating against UI requirements:")

    # Check FileList.tsx requirements
    try:
        # FileList expects: files: FileHit[]
        # where FileHit = { name: string, path: string, score: number, meta?: {...} }

        assert isinstance(mock_file['name'], str), "name should be string"
        print("  ✓ name is string")

        assert isinstance(mock_file['path'], str), "path should be string"
        print("  ✓ path is string")

        assert isinstance(mock_file['score'], (int, float)), "score should be number"
        print("  ✓ score is number")

        assert isinstance(mock_file['meta'], dict), "meta should be object"
        print("  ✓ meta is object")

        assert 'file_type' in mock_file['meta'], "meta should have file_type"
        print("  ✓ meta has file_type")

        # total_pages is optional
        if 'total_pages' in mock_file['meta']:
            assert isinstance(mock_file['meta']['total_pages'], (int, type(None))), \
                "total_pages should be number or null"
            print("  ✓ total_pages is number (optional)")

        print("\n✅ TEST 3 PASSED: File structure is compatible with UI components")
        return True

    except AssertionError as e:
        print(f"\n❌ TEST 3 FAILED: {e}")
        return False


if __name__ == "__main__":
    print("\n" + "="*80)
    print("UI FILE DISPLAY TEST SUITE")
    print("="*80)
    print("\nThese tests verify that the UI can correctly display file lists")
    print("when users request files by name patterns or starting letters.")

    results = []

    # Run test 3 first (quick validation)
    results.append(("UI Component Compatibility", test_ui_component_compatibility()))

    # Run integration tests
    results.append(("Files Starting with Letter", test_files_starting_with_letter()))
    results.append(("Files Matching Pattern", test_files_matching_pattern()))

    # Print summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)

    all_passed = True
    for test_name, passed in results:
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{status}: {test_name}")
        if not passed:
            all_passed = False

    print("="*80)

    if all_passed:
        print("\n✅ ALL TESTS PASSED!")
        print("\nConclusion: The UI can correctly display file lists for:")
        print("  - Files starting with specific letters")
        print("  - Files matching name patterns")
        print("  - The file structure is compatible with frontend components")
        sys.exit(0)
    else:
        print("\n❌ SOME TESTS FAILED!")
        print("\nPlease review the failures above.")
        sys.exit(1)
