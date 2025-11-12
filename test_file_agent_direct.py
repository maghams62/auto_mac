"""
Test the file agent directly to see what it returns for Edgar Allan Poe query.
"""

import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.agent.file_agent import list_related_documents
from src.utils import load_config
import json


def test_direct_file_query():
    """Test the list_related_documents tool directly."""
    print("\n" + "="*80)
    print("TEST: Direct File Agent Query")
    print("="*80)

    try:
        # Test the tool directly
        query = "Edgar Allan Poe"
        print(f"\nQuery: {query}")
        print("Calling list_related_documents tool directly...\n")

        result = list_related_documents.invoke({
            "query": query,
            "max_results": 10
        })

        print("Result received!")
        print(f"Type: {result.get('type')}")
        print(f"Message: {result.get('message')}")
        print(f"Total count: {result.get('total_count')}")

        files = result.get('files', [])
        print(f"\nNumber of files: {len(files)}")

        if len(files) > 0:
            print("\n" + "-"*80)
            print("FILES RETURNED:")
            print("-"*80)
            for i, file_obj in enumerate(files):
                print(f"\nFile {i+1}:")
                print(f"  Name: {file_obj.get('name')}")
                print(f"  Path: {file_obj.get('path')}")
                print(f"  Score: {file_obj.get('score')}")
                print(f"  Meta: {file_obj.get('meta')}")

            # Check for Tell-Tale Heart
            found_tell_tale = any(
                'Tell-Tale' in file_obj.get('name', '')
                for file_obj in files
            )

            print("\n" + "-"*80)
            if found_tell_tale:
                print("✅ Tell-Tale_Heart.pdf found!")

                # Print the exact structure that will be sent to UI
                tell_tale_file = next(f for f in files if 'Tell-Tale' in f.get('name', ''))
                print("\nExact file object that UI will receive:")
                print(json.dumps(tell_tale_file, indent=2))
            else:
                print("❌ Tell-Tale_Heart.pdf NOT found")

        else:
            print("⚠️  No files returned")

        return True

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    test_direct_file_query()
