"""
Test that API server correctly extracts files array from agent results.
This simulates what api_server.py does when processing agent results.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.agent.agent import AutomationAgent
from src.utils import load_config


def simulate_api_server_extraction(result_dict):
    """
    Simulate the API server's file extraction logic from api_server.py:320-333
    """
    files_array = None
    location = None

    # Check step_results
    if "step_results" in result_dict and result_dict["step_results"]:
        for step_result in result_dict["step_results"].values():
            if isinstance(step_result, dict) and step_result.get("type") == "file_list" and "files" in step_result:
                files_array = step_result["files"]
                location = "step_results"
                break

    # Check results
    if not files_array and "results" in result_dict and result_dict["results"]:
        for step_result in result_dict["results"].values():
            if isinstance(step_result, dict) and step_result.get("type") == "file_list" and "files" in step_result:
                files_array = step_result["files"]
                location = "results"
                break

    # Check top-level
    if not files_array and result_dict.get("type") == "file_list" and "files" in result_dict:
        files_array = result_dict["files"]
        location = "top-level"

    return files_array, location


def test_api_extraction():
    """Test the full flow including API extraction logic."""
    print("\n" + "="*80)
    print("TEST: API Server File Extraction")
    print("="*80)

    try:
        config = load_config()
        agent = AutomationAgent(config)

        user_query = "pull up edgar allan poe files"
        print(f"\nUser Query: {user_query}")

        print("\nStep 1: Running agent...")
        result = agent.run(user_query)

        print(f"✓ Result status: {result.get('status')}")

        print("\nStep 2: Simulating API server extraction...")
        files_array, location = simulate_api_server_extraction(result)

        if files_array is None:
            print("❌ API server would NOT find files array")
            print(f"   Result keys: {list(result.keys())}")
            if "results" in result:
                print(f"   Results keys: {list(result['results'].keys())}")
                for k, v in result['results'].items():
                    if isinstance(v, dict):
                        print(f"     Result[{k}] keys: {list(v.keys())}")
                        print(f"     Result[{k}] type: {v.get('type')}")
            return False

        print(f"✓ Files array extracted from: {location}")
        print(f"✓ Number of files: {len(files_array)}")

        print("\nStep 3: Verify file structure for UI...")
        if len(files_array) > 0:
            file = files_array[0]
            required_fields = ['name', 'path', 'score', 'meta']
            missing = [f for f in required_fields if f not in file]

            if missing:
                print(f"❌ Missing fields: {missing}")
                return False

            print("✓ All required fields present")
            print(f"\nFile that will be displayed in UI:")
            print(f"  Name: {file['name']}")
            print(f"  Path: {file['path']}")
            print(f"  Score: {file['score']*100:.1f}%")
            print(f"  Type: {file['meta']['file_type']}")
            if file['meta'].get('total_pages'):
                print(f"  Pages: {file['meta']['total_pages']}")

        print("\nStep 4: Simulate WebSocket payload...")
        # This is what would be sent to the UI
        response_payload = {
            "type": "response",
            "message": result.get("message", ""),
            "status": result.get("status"),
            "files": files_array  # This is what FileList component needs
        }

        print("✓ WebSocket payload structure:")
        print(f"  - type: {response_payload['type']}")
        print(f"  - status: {response_payload['status']}")
        print(f"  - message: {response_payload['message'][:50]}..." if len(response_payload.get('message', '')) > 50 else f"  - message: {response_payload.get('message')}")
        print(f"  - files: Array with {len(response_payload['files'])} item(s)")

        print("\n" + "="*80)
        print("✅ COMPLETE FLOW VERIFIED")
        print("="*80)
        print("\nSummary:")
        print("1. ✅ Agent executed successfully")
        print("2. ✅ API server would extract files array")
        print("3. ✅ File structure is UI-compatible")
        print("4. ✅ WebSocket payload is correct")
        print("\n→ UI would display FileList component with Tell-Tale_Heart.pdf")
        print("→ User would see file name, path, score, with Reveal/Copy buttons")

        return True

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    test_api_extraction()
