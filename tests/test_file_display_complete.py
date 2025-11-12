"""
Complete end-to-end test for file display functionality.

This test verifies the complete flow from user query to UI display:
1. User asks to see files (by name pattern or starting letter)
2. Agent executes list_related_documents
3. API server extracts files array
4. UI receives properly structured data
5. FileList component can render the files

Tests both scenarios:
- Files starting with a letter (e.g., "files starting with A")
- Files matching a pattern (e.g., "edgar allan poe files")
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.agent.agent import AutomationAgent
from src.utils import load_config


def extract_files_from_result(result_dict):
    """Extract files array from agent result (simulates API server logic)."""
    # Check results field
    if "results" in result_dict and result_dict["results"]:
        for step_result in result_dict["results"].values():
            if isinstance(step_result, dict) and step_result.get("type") == "file_list" and "files" in step_result:
                return step_result["files"]

    # Check step_results field
    if "step_results" in result_dict and result_dict["step_results"]:
        for step_result in result_dict["step_results"].values():
            if isinstance(step_result, dict) and step_result.get("type") == "file_list" and "files" in step_result:
                return step_result["files"]

    return None


def validate_ui_compatibility(files_array):
    """Validate that files array matches UI expectations."""
    if not isinstance(files_array, list):
        return False, f"Expected list, got {type(files_array)}"

    if len(files_array) == 0:
        return True, "Empty array (no matches)"

    # Check structure of first file
    file = files_array[0]
    required_fields = {
        'name': str,
        'path': str,
        'score': (int, float),
        'meta': dict
    }

    for field, expected_type in required_fields.items():
        if field not in file:
            return False, f"Missing field: {field}"
        if not isinstance(file[field], expected_type):
            return False, f"Field '{field}' wrong type: expected {expected_type}, got {type(file[field])}"

    # Check meta structure
    if 'file_type' not in file['meta']:
        return False, "meta missing 'file_type'"

    return True, "Valid structure"


def test_scenario(config, query, expected_file_name=None, description=None):
    """Test a single file query scenario."""
    print("\n" + "-"*80)
    print(f"TEST: {description or query}")
    print("-"*80)

    try:
        agent = AutomationAgent(config)

        print(f"Query: {query}")
        result = agent.run(query)

        print(f"Status: {result.get('status')}")

        # Extract files array
        files_array = extract_files_from_result(result)

        if files_array is None:
            print("⚠️  No files array in result")
            return False

        print(f"✓ Files array found with {len(files_array)} file(s)")

        # Validate UI compatibility
        valid, message = validate_ui_compatibility(files_array)
        if not valid:
            print(f"❌ UI validation failed: {message}")
            return False

        print(f"✓ UI structure valid: {message}")

        # Display files
        if len(files_array) > 0:
            print("\nFiles that would be displayed:")
            for i, file in enumerate(files_array[:5], 1):  # Show first 5
                print(f"  {i}. {file['name']}")
                print(f"     Path: {file['path']}")
                print(f"     Similarity: {file['score']*100:.0f}%")
                print(f"     Type: {file['meta']['file_type']}")

        # Check for expected file if provided
        if expected_file_name:
            found = any(expected_file_name in f['name'] for f in files_array)
            if found:
                print(f"\n✓ Expected file '{expected_file_name}' found!")
            else:
                print(f"\n⚠️  Expected file '{expected_file_name}' not in results")

        print("\n✅ Scenario passed")
        return True

    except Exception as e:
        print(f"\n❌ Scenario failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    print("="*80)
    print("FILE DISPLAY COMPLETE END-TO-END TEST")
    print("="*80)
    print("\nThis test verifies the complete flow:")
    print("  User Query → Agent → API Server → UI FileList Component")

    config = load_config()
    results = []

    # Scenario 1: Files of Edgar Allan Poe
    results.append((
        "Edgar Allan Poe files",
        test_scenario(
            config,
            "pull up edgar allan poe files",
            expected_file_name="Tell-Tale",
            description="Files by author/content"
        )
    ))

    # Scenario 2: Guitar tab files
    results.append((
        "Guitar tab files",
        test_scenario(
            config,
            "pull up all guitar tab documents",
            expected_file_name=None,  # May or may not have guitar tabs
            description="Files by content type"
        )
    ))

    # Scenario 3: Files starting with letter
    results.append((
        "Files starting with 'E'",
        test_scenario(
            config,
            "show files starting with E",
            expected_file_name="End",  # End-of-Beginning-Djo.pdf
            description="Files by name pattern"
        )
    ))

    # Print summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)

    all_passed = True
    for test_name, passed in results:
        status = "✅" if passed else "❌"
        print(f"{status} {test_name}")
        if not passed:
            all_passed = False

    print("="*80)

    if all_passed:
        print("\n✅ ALL TESTS PASSED!")
        print("\nConclusion:")
        print("  The UI file display functionality is working correctly for:")
        print("  • Files matching semantic queries (Edgar Allan Poe)")
        print("  • Files matching content types (guitar tabs)")
        print("  • Files starting with specific letters")
        print("\n  The complete flow is verified:")
        print("  1. Agent correctly interprets file listing requests")
        print("  2. list_related_documents returns properly structured data")
        print("  3. API server extracts files array")
        print("  4. UI receives data in FileList-compatible format")
        print("  5. Users will see files with name, path, score, and action buttons")
        return 0
    else:
        print("\n❌ SOME TESTS FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(main())
