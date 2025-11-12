"""
Test the new HelpRegistry system.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.ui.help_registry import HelpRegistry
from src.ui.help_models import HelpEntry, AgentHelp, CategoryInfo
from src.utils import load_config
from src.agent.agent_registry import AgentRegistry


def test_basic_initialization():
    """Test that HelpRegistry initializes without agent registry."""
    print("\n" + "="*60)
    print("TEST 1: Basic Initialization (No Agent Registry)")
    print("="*60)

    help_registry = HelpRegistry()

    print(f"\nTotal Entries: {len(help_registry.entries)}")
    print(f"Total Categories: {len(help_registry.categories)}")

    # Check some expected commands
    assert "/files" in help_registry.entries
    assert "/email" in help_registry.entries
    assert "/help" in help_registry.entries

    print("\n✅ PASS: Basic initialization works")
    return True


def test_with_agent_registry():
    """Test HelpRegistry with full agent discovery."""
    print("\n" + "="*60)
    print("TEST 2: Initialization with Agent Registry")
    print("="*60)

    config = load_config()
    agent_registry = AgentRegistry(config)
    help_registry = HelpRegistry(agent_registry)

    print(f"\nTotal Entries: {len(help_registry.entries)}")
    print(f"Total Agents: {len(help_registry.agents)}")
    print(f"Total Categories: {len(help_registry.categories)}")

    # Check agents were discovered
    print(f"\nDiscovered Agents:")
    for agent_name, agent_help in help_registry.agents.items():
        print(f"  - {agent_help.icon} {agent_help.display_name}: {agent_help.tool_count} tools")

    assert len(help_registry.agents) > 0, "No agents discovered!"

    print("\n✅ PASS: Agent discovery works")
    return True


def test_search():
    """Test search functionality."""
    print("\n" + "="*60)
    print("TEST 3: Search Functionality")
    print("="*60)

    help_registry = HelpRegistry()

    # Test search
    results = help_registry.search("email")
    print(f"\nSearch 'email' found {len(results)} results:")
    for entry in results[:3]:
        print(f"  - {entry.icon} {entry.name}: {entry.description}")

    assert len(results) > 0, "Search returned no results!"

    # Test search for "file"
    results = help_registry.search("file")
    print(f"\nSearch 'file' found {len(results)} results:")
    for entry in results[:3]:
        print(f"  - {entry.icon} {entry.name}: {entry.description}")

    print("\n✅ PASS: Search works")
    return True


def test_categories():
    """Test category filtering."""
    print("\n" + "="*60)
    print("TEST 4: Category Filtering")
    print("="*60)

    help_registry = HelpRegistry()

    # Get all categories
    categories = help_registry.get_all_categories()
    print(f"\nAvailable Categories ({len(categories)}):")
    for cat in categories:
        print(f"  - {cat.icon} {cat.display_name}: {cat.command_count} commands")

    # Get entries by category
    file_entries = help_registry.get_by_category("files")
    print(f"\nFile Category has {len(file_entries)} entries:")
    for entry in file_entries:
        print(f"  - {entry.name}")

    assert len(file_entries) > 0, "No file entries found!"

    print("\n✅ PASS: Category filtering works")
    return True


def test_suggestions():
    """Test command suggestions for typos."""
    print("\n" + "="*60)
    print("TEST 5: Command Suggestions")
    print("="*60)

    help_registry = HelpRegistry()

    # Test typos
    test_cases = [
        ("/fil", "/files"),
        ("/emai", "/email"),
        ("/brows", "/browse"),
    ]

    for typo, expected in test_cases:
        suggestions = help_registry.get_suggestions(typo)
        print(f"\nTypo: '{typo}' → Suggestions: {suggestions}")

        if expected:
            assert expected in suggestions, f"Expected suggestion '{expected}' not found!"

    print("\n✅ PASS: Suggestions work")
    return True


def test_entry_details():
    """Test detailed entry information."""
    print("\n" + "="*60)
    print("TEST 6: Entry Details")
    print("="*60)

    help_registry = HelpRegistry()

    # Get email entry
    email_entry = help_registry.get_entry("/email")
    assert email_entry is not None, "/email entry not found!"

    print(f"\nEntry: {email_entry.name}")
    print(f"Icon: {email_entry.icon}")
    print(f"Type: {email_entry.type}")
    print(f"Category: {email_entry.category}")
    print(f"Description: {email_entry.description}")
    print(f"Examples ({len(email_entry.examples)}):")
    for example in email_entry.examples[:3]:
        print(f"  - {example}")
    print(f"Tags: {', '.join(email_entry.tags)}")

    print("\n✅ PASS: Entry details work")
    return True


def test_json_export():
    """Test JSON export functionality."""
    print("\n" + "="*60)
    print("TEST 7: JSON Export")
    print("="*60)

    config = load_config()
    agent_registry = AgentRegistry(config)
    help_registry = HelpRegistry(agent_registry)

    # Export to dict
    data = help_registry.to_dict()

    print(f"\nExported Data Structure:")
    print(f"  - Categories: {len(data['categories'])}")
    print(f"  - Commands: {len(data['commands'])}")
    print(f"  - Agents: {len(data['agents'])}")
    print(f"  - Total Entries: {data['total_entries']}")

    assert data['total_entries'] > 0, "No entries in export!"

    # Test serialization of one entry
    email_data = data['commands']['/email']
    print(f"\nSample Entry (/email):")
    print(f"  - Name: {email_data['name']}")
    print(f"  - Description: {email_data['description']}")
    print(f"  - Examples: {len(email_data['examples'])}")

    print("\n✅ PASS: JSON export works")
    return True


def main():
    """Run all tests."""
    print("\n" + "="*60)
    print("HELP REGISTRY TEST SUITE")
    print("="*60)

    tests = [
        test_basic_initialization,
        test_with_agent_registry,
        test_search,
        test_categories,
        test_suggestions,
        test_entry_details,
        test_json_export,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            if test():
                passed += 1
        except AssertionError as e:
            print(f"\n❌ FAIL: {e}")
            failed += 1
        except Exception as e:
            print(f"\n❌ ERROR: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    print(f"✅ Passed: {passed}/{len(tests)}")
    print(f"❌ Failed: {failed}/{len(tests)}")

    if failed == 0:
        print("\n🎉 ALL TESTS PASSED!")
        print("\nHelpRegistry is ready to use!")
        return 0
    else:
        print("\n⚠️  Some tests failed. Please review the errors above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
