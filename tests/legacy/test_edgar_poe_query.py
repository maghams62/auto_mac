"""
Test query for Edgar Allan Poe files to debug the UI display issue.
"""

import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.agent.agent import AutomationAgent
from src.utils import load_config
import json


def test_edgar_poe_query():
    """Test the exact query the user tried."""
    print("\n" + "="*80)
    print("TEST: Edgar Allan Poe File Query")
    print("="*80)

    try:
        config = load_config()
        agent = AutomationAgent(config)

        user_query = "files pull up the files of edgar allan poe"
        print(f"\nUser Query: {user_query}")

        print("\nRunning agent...")
        result = agent.run(user_query)

        print(f"\nResult status: {result.get('status')}")
        print(f"Result keys: {list(result.keys())}")

        # Extract files array
        files_array = None
        result_location = None

        if "step_results" in result:
            print(f"\nStep results keys: {list(result['step_results'].keys())}")
            for step_id, step_result in result["step_results"].items():
                print(f"\nStep {step_id} type: {type(step_result)}")
                if isinstance(step_result, dict):
                    print(f"  Keys: {list(step_result.keys())}")
                    print(f"  Type field: {step_result.get('type')}")
                    if step_result.get("type") == "file_list":
                        files_array = step_result.get("files")
                        result_location = f"step_results[{step_id}]"
                        break

        if "results" in result and not files_array:
            print(f"\nResults keys: {list(result['results'].keys())}")
            for step_id, step_result in result["results"].items():
                if isinstance(step_result, dict) and step_result.get("type") == "file_list":
                    files_array = step_result.get("files")
                    result_location = f"results[{step_id}]"
                    break

        if files_array is None:
            print("\n❌ No files array found!")
            print("\nFull result:")
            print(json.dumps(result, indent=2, default=str))
            return False

        print(f"\n✓ Files array found in: {result_location}")
        print(f"✓ Number of files: {len(files_array)}")

        # Print all files found
        print("\n" + "-"*80)
        print("FILES RETURNED:")
        print("-"*80)
        for i, file_obj in enumerate(files_array):
            print(f"\nFile {i+1}:")
            print(f"  Name: {file_obj.get('name')}")
            print(f"  Path: {file_obj.get('path')}")
            print(f"  Score: {file_obj.get('score')}")
            if 'meta' in file_obj:
                print(f"  Meta: {file_obj.get('meta')}")

        # Check if Tell-Tale_Heart.pdf is in the results
        found_tell_tale = any(
            'Tell-Tale' in file_obj.get('name', '')
            for file_obj in files_array
        )

        print("\n" + "-"*80)
        if found_tell_tale:
            print("✅ Tell-Tale_Heart.pdf was found!")
        else:
            print("❌ Tell-Tale_Heart.pdf NOT found in results")
            print("   Expected file: Tell-Tale_Heart.pdf")
            print(f"   Actual files returned: {[f.get('name') for f in files_array]}")

        # Check if only one file was returned
        if len(files_array) == 1:
            print("✅ Only 1 file returned (as expected)")
        else:
            print(f"⚠️  {len(files_array)} files returned (expected 1)")

        return True

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    test_edgar_poe_query()
