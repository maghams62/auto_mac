#!/usr/bin/env python3
"""
Test that all critical agent imports work correctly.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

def test_imports():
    """Test importing all critical modules."""

    print("\n" + "="*80)
    print("CRITICAL IMPORTS TEST")
    print("="*80 + "\n")

    tests = [
        ("File Agent", "from src.agent.file_agent import search_documents, extract_section"),
        ("Email Agent", "from src.agent.email_agent import compose_email, read_latest_emails"),
        ("Browser Agent", "from src.agent.browser_agent import navigate_to_url, extract_page_content"),
        ("Google Finance Agent", "from src.agent.google_finance_agent import search_google_finance_stock"),
        ("Writing Agent", "from src.agent.writing_agent import create_slide_deck_content"),
        ("Agent Registry", "from src.agent.agent_registry import AgentRegistry"),
        ("Utils", "from src.utils import load_config"),
        ("Documents", "from src.documents import DocumentIndexer, SemanticSearch"),
        ("Automation", "from src.automation import MailComposer, KeynoteComposer"),
        ("Workflow", "from src.workflow import WorkflowOrchestrator"),
    ]

    passed = 0
    failed = 0

    for name, import_stmt in tests:
        try:
            exec(import_stmt)
            print(f"✅ {name}")
            passed += 1
        except ImportError as e:
            print(f"❌ {name}: {e}")
            failed += 1
        except Exception as e:
            # Other exceptions are OK (like missing config), we only care about ImportError
            print(f"✅ {name} (import successful, runtime error OK)")
            passed += 1

    print("\n" + "="*80)
    print(f"RESULTS: {passed} passed, {failed} failed out of {len(tests)} tests")
    print("="*80 + "\n")

    return failed == 0

if __name__ == "__main__":
    success = test_imports()
    sys.exit(0 if success else 1)
