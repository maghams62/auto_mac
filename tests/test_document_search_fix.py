#!/usr/bin/env python3
"""
Test that document search import issues are fixed.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

def test_search_documents_import():
    """Test that search_documents can be imported and called without errors."""

    print("\n" + "="*80)
    print("DOCUMENT SEARCH IMPORT FIX TEST")
    print("="*80 + "\n")

    try:
        from src.agent.file_agent import search_documents
        print("✅ Successfully imported search_documents from src.agent.file_agent")

        # Try to call it (it may not find documents, but shouldn't have import errors)
        result = search_documents("test query")

        if result.get("error"):
            error_type = result.get("error_type")
            error_message = result.get("error_message")

            # Check if it's an import error
            if "No module named" in error_message or "ImportError" in str(error_type):
                print(f"❌ FAILED: Still has import error - {error_message}")
                return False
            else:
                # Other errors are OK (like NotFoundError)
                print(f"✅ No import errors! (Got expected error: {error_type})")
                return True
        else:
            print(f"✅ Function executed successfully!")
            print(f"   Result: {result}")
            return True

    except ImportError as e:
        print(f"❌ FAILED: Import error - {e}")
        return False
    except Exception as e:
        print(f"⚠️  Got exception: {e}")
        print(f"   This might be OK if it's not an import error")

        # Check if it's an import-related error
        if "No module named" in str(e):
            print(f"❌ FAILED: Still has import issues")
            return False
        else:
            print(f"✅ No import errors (got different error which is OK)")
            return True

    print("="*80 + "\n")

if __name__ == "__main__":
    success = test_search_documents_import()
    sys.exit(0 if success else 1)
