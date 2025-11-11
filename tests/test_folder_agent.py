"""
Comprehensive test suite for Folder Agent.

Tests:
1. Tool functionality (list, plan, apply, check_sandbox)
2. Security constraints (sandbox enforcement)
3. LLM-driven routing and orchestration
4. Confirmation discipline
5. Error handling and recovery
"""

import os
import sys
import tempfile
import shutil
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.automation.folder_tools import FolderTools, FolderSecurityError
from src.agent.folder_agent import FolderAgent, FOLDER_AGENT_TOOLS
from src.utils import load_config
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def build_test_config(folder_path: str) -> dict:
    """Build minimal config with required sections for FolderTools."""
    from pathlib import Path as _Path
    resolved = str(_Path(folder_path).resolve())
    return {
        'openai': {
            'api_key': 'test-key',
            'model': 'gpt-4o'
        },
        'documents': {
            'folders': [resolved]
        },
        'search': {
            'top_k': 5
        }
    }


class TestFolderTools:
    """Test suite for FolderTools (deterministic layer)."""

    def setup_test_folder(self):
        """Create a temporary test folder with sample files."""
        test_dir = tempfile.mkdtemp(prefix="folder_test_")

        # Create test files with various naming patterns
        test_files = [
            "Music Notes.txt",
            "Work Document 2023.pdf",
            "photo IMG_1234.jpg",
            "random-file-name.txt",
            "UPPERCASE FILE.pdf",
            "already_normalized.txt",
            "multiple   spaces.txt",
            "special!@#chars.txt"
        ]

        for filename in test_files:
            with open(os.path.join(test_dir, filename), 'w') as f:
                f.write(f"Test content for {filename}")

        # Create a subfolder
        subfolder = os.path.join(test_dir, "Test Subfolder")
        os.makedirs(subfolder)
        with open(os.path.join(subfolder, "nested file.txt"), 'w') as f:
            f.write("Nested content")

        return test_dir

    def build_config(self, folder_path: str) -> dict:
        """Build minimal config with required sections for FolderTools."""
        return build_test_config(folder_path)

    def test_check_sandbox(self):
        """Test sandbox validation."""
        print("\n" + "="*80)
        print("TEST: Sandbox Validation")
        print("="*80)

        test_dir = self.setup_test_folder()

        try:
            # Create config with test directory as sandbox
            config = self.build_config(test_dir)
            tools = FolderTools(config)

            # Test 1: Valid path within sandbox
            result = tools.check_sandbox(test_dir)
            assert result['is_safe'] is True, "Direct sandbox path should be safe"
            print(f"✓ Valid path test passed: {result['message']}")

            # Test 2: Valid subpath
            subpath = os.path.join(test_dir, "Test Subfolder")
            result = tools.check_sandbox(subpath)
            assert result['is_safe'] is True, "Subpath should be safe"
            print(f"✓ Subpath test passed: {result['message']}")

            # Test 3: Parent directory traversal
            parent_path = os.path.join(test_dir, "..")
            result = tools.check_sandbox(parent_path)
            assert result['is_safe'] is False, "Parent directory should be rejected"
            print(f"✓ Parent traversal blocked: {result['message']}")

            # Test 4: Absolute path outside sandbox
            result = tools.check_sandbox("/tmp")
            assert result['is_safe'] is False, "Outside path should be rejected"
            print(f"✓ Outside path blocked: {result['message']}")

            print("\n✅ All sandbox validation tests passed")
            return True

        finally:
            shutil.rmtree(test_dir)

    def test_folder_list(self):
        """Test folder listing."""
        print("\n" + "="*80)
        print("TEST: Folder Listing")
        print("="*80)

        test_dir = self.setup_test_folder()

        try:
            config = self.build_config(test_dir)
            tools = FolderTools(config)

            # Test listing
            result = tools.list_folder(test_dir)

            assert not result.get('error'), f"List should succeed: {result.get('error_message')}"
            assert 'items' in result, "Result should contain items"
            assert result['total_count'] > 0, "Should find files"

            print(f"✓ Found {result['total_count']} items")

            # Check alphabetical sorting
            items = result['items']
            names = [item['name'] for item in items]
            assert names == sorted(names), "Items should be alphabetically sorted"
            print(f"✓ Items sorted alphabetically")

            # Check item structure
            for item in items:
                assert 'name' in item, "Item should have name"
                assert 'type' in item, "Item should have type"
                assert item['type'] in ['file', 'dir'], f"Invalid type: {item['type']}"
                print(f"  - {item['name']} ({item['type']})")

            print("\n✅ Folder listing tests passed")
            return True

        finally:
            shutil.rmtree(test_dir)

    def test_plan_alpha(self):
        """Test alphabetical normalization planning."""
        print("\n" + "="*80)
        print("TEST: Alphabetical Normalization Planning")
        print("="*80)

        test_dir = self.setup_test_folder()

        try:
            config = self.build_config(test_dir)
            tools = FolderTools(config)

            # Generate plan
            result = tools.plan_folder_organization_alpha(test_dir)

            assert not result.get('error'), f"Plan should succeed: {result.get('error_message')}"
            assert 'plan' in result, "Result should contain plan"
            assert 'needs_changes' in result, "Result should indicate if changes needed"

            plan = result['plan']
            changes_count = result['changes_count']

            print(f"✓ Generated plan for {len(plan)} items")
            print(f"✓ {changes_count} items need changes")

            # Check plan structure
            for item in plan:
                assert 'current_name' in item
                assert 'proposed_name' in item
                assert 'needs_change' in item
                assert 'reason' in item

                if item['needs_change']:
                    # Verify normalization rules
                    proposed = item['proposed_name']
                    # Should be lowercase (except extension)
                    name_part = proposed.rsplit('.', 1)[0] if '.' in proposed else proposed
                    assert name_part.islower() or name_part == name_part.lower(), \
                        f"Name part should be lowercase: {proposed}"
                    # Should not have multiple consecutive underscores
                    assert '__' not in proposed, f"Should not have multiple underscores: {proposed}"

                    print(f"  {item['current_name']} → {item['proposed_name']}")

            print("\n✅ Planning tests passed")
            return True

        finally:
            shutil.rmtree(test_dir)

    def test_organize_by_file_type_dry_run(self):
        """Ensure organize_by_file_type produces a dry-run plan."""
        print("\n" + "="*80)
        print("TEST: Organize by File Type (Dry Run)")
        print("="*80)

        test_dir = self.setup_test_folder()

        try:
            config = self.build_config(test_dir)
            tools = FolderTools(config)

            result = tools.organize_by_file_type(test_dir, dry_run=True)

            assert not result.get('error'), f"Dry-run should succeed: {result.get('error_message')}"
            assert result['dry_run'] is True
            assert len(result['plan']) > 0, "Plan should include files to move"

            target_folders = {item['target_folder'] for item in result['plan']}
            assert "TXT" in target_folders, "TXT folder expected in plan"
            assert "PDF" in target_folders, "PDF folder expected in plan"

            print(f"✓ Dry-run generated for {len(result['plan'])} files")
            print(f"✓ Target folders: {sorted(target_folders)}")

        finally:
            shutil.rmtree(test_dir)

    def test_organize_by_file_type_apply(self):
        """Ensure organize_by_file_type moves files when dry_run=False."""
        print("\n" + "="*80)
        print("TEST: Organize by File Type (Apply)")
        print("="*80)

        test_dir = self.setup_test_folder()

        try:
            config = self.build_config(test_dir)
            tools = FolderTools(config)

            result = tools.organize_by_file_type(test_dir, dry_run=False)

            assert not result.get('error'), f"Execution should succeed: {result.get('error_message')}"
            assert result['dry_run'] is False
            assert result['success'] is True

            txt_folder = os.path.join(test_dir, "TXT")
            pdf_folder = os.path.join(test_dir, "PDF")

            assert os.path.isdir(txt_folder), "TXT folder should be created"
            assert os.path.isdir(pdf_folder), "PDF folder should be created"

            moved_files = {item['file'] for item in result['applied']}
            assert "Music Notes.txt" in moved_files
            assert "Work Document 2023.pdf" in moved_files

            assert os.path.exists(os.path.join(txt_folder, "Music Notes.txt"))
            assert os.path.exists(os.path.join(pdf_folder, "Work Document 2023.pdf"))

            print(f"✓ Moved {len(result['applied'])} files by extension")

        finally:
            shutil.rmtree(test_dir)

    def test_apply_dry_run(self):
        """Test dry-run application (no actual changes)."""
        print("\n" + "="*80)
        print("TEST: Dry-Run Application")
        print("="*80)

        test_dir = self.setup_test_folder()

        try:
            config = self.build_config(test_dir)
            tools = FolderTools(config)

            # Get original file list
            original_files = set(os.listdir(test_dir))

            # Generate plan
            plan_result = tools.plan_folder_organization_alpha(test_dir)
            plan = plan_result['plan']

            # Apply with dry_run=True
            result = tools.apply_folder_plan(plan, test_dir, dry_run=True)

            assert not result.get('error'), f"Dry-run should succeed: {result.get('error_message')}"
            assert result['dry_run'] == True, "Should be marked as dry run"

            # Verify no changes were made
            current_files = set(os.listdir(test_dir))
            assert original_files == current_files, "Dry-run should not modify files"

            print(f"✓ Dry-run completed")
            print(f"✓ Would apply {len(result['applied'])} changes")
            print(f"✓ Would skip {len(result['skipped'])} items")
            print(f"✓ No actual files modified")

            print("\n✅ Dry-run tests passed")
            return True

        finally:
            shutil.rmtree(test_dir)

    def test_apply_actual(self):
        """Test actual file renaming."""
        print("\n" + "="*80)
        print("TEST: Actual File Renaming")
        print("="*80)

        test_dir = self.setup_test_folder()

        try:
            config = self.build_config(test_dir)
            tools = FolderTools(config)

            # Generate plan
            plan_result = tools.plan_folder_organization_alpha(test_dir)
            plan = plan_result['plan']
            changes_count = plan_result['changes_count']

            # Apply with dry_run=False
            result = tools.apply_folder_plan(plan, test_dir, dry_run=False)

            assert not result.get('error'), f"Apply should succeed: {result.get('error_message')}"
            assert result['dry_run'] == False, "Should be actual execution"
            assert len(result['applied']) == changes_count, "Should apply all changes"

            print(f"✓ Applied {len(result['applied'])} changes")

            # Verify files were actually renamed
            current_files = os.listdir(test_dir)
            for item in result['applied']:
                proposed_name = item['proposed_name']
                assert proposed_name in current_files, f"File should exist: {proposed_name}"
                print(f"  ✓ {item['current_name']} → {item['proposed_name']}")

            print("\n✅ Actual renaming tests passed")
            return True

        finally:
            shutil.rmtree(test_dir)

    def test_conflict_handling(self):
        """Test handling of naming conflicts."""
        print("\n" + "="*80)
        print("TEST: Conflict Handling")
        print("="*80)

        test_dir = tempfile.mkdtemp(prefix="folder_test_")

        try:
            # Create files that will conflict
            with open(os.path.join(test_dir, "File One.txt"), 'w') as f:
                f.write("Content 1")
            with open(os.path.join(test_dir, "file_one.txt"), 'w') as f:
                f.write("Content 2")

            config = self.build_config(test_dir)
            tools = FolderTools(config)

            # Generate plan
            plan_result = tools.plan_folder_organization_alpha(test_dir)
            plan = plan_result['plan']

            # Apply (should detect conflict)
            result = tools.apply_folder_plan(plan, test_dir, dry_run=False)

            # Should have errors due to conflict
            assert len(result['errors']) > 0, "Should detect conflicts"

            for error in result['errors']:
                assert 'conflict' in error['error'].lower() or 'exists' in error['error'].lower()
                print(f"✓ Conflict detected: {error['current_name']} → {error['proposed_name']}")

            print("\n✅ Conflict handling tests passed")
            return True

        finally:
            shutil.rmtree(test_dir)


class TestFolderAgent:
    """Test suite for FolderAgent (LangChain integration layer)."""

    def test_agent_initialization(self):
        """Test agent initialization and tool registration."""
        print("\n" + "="*80)
        print("TEST: Agent Initialization")
        print("="*80)

        config = load_config()
        agent = FolderAgent(config)

        # Check tools are registered
        tools = agent.get_tools()
        assert len(tools) == 5, f"Should have 5 tools, got {len(tools)}"

        tool_names = [tool.name for tool in tools]
        expected_tools = [
            'folder_check_sandbox',
            'folder_list',
            'folder_plan_alpha',
            'folder_apply',
            'folder_organize_by_type'
        ]

        for expected in expected_tools:
            assert expected in tool_names, f"Missing tool: {expected}"
            print(f"✓ Tool registered: {expected}")

        # Check hierarchy documentation
        hierarchy = agent.get_hierarchy()
        assert "LEVEL 0" in hierarchy
        assert "LEVEL 1" in hierarchy
        assert "LEVEL 2" in hierarchy
        assert "LEVEL 3" in hierarchy
        print(f"✓ Hierarchy documentation present")

        print("\n✅ Agent initialization tests passed")
        return True

    def test_tool_execution(self):
        """Test executing tools through agent."""
        print("\n" + "="*80)
        print("TEST: Tool Execution Through Agent")
        print("="*80)

        test_dir = tempfile.mkdtemp(prefix="folder_test_")

        try:
            # Create test file
            with open(os.path.join(test_dir, "test file.txt"), 'w') as f:
                f.write("Test")

            # Use test directory in config
            config = build_test_config(test_dir)
            agent = FolderAgent(config)

            # Test folder_list through agent
            result = agent.execute('folder_list', {'folder_path': test_dir})

            assert not result.get('error'), f"Execution should succeed: {result.get('error_message')}"
            assert 'items' in result
            print(f"✓ folder_list execution: {result['total_count']} items")

            # Test folder_check_sandbox through agent
            result = agent.execute('folder_check_sandbox', {'path': test_dir})

            assert not result.get('error'), f"Execution should succeed: {result.get('error_message')}"
            assert result['is_safe'] == True
            print(f"✓ folder_check_sandbox execution: {result['message']}")

            print("\n✅ Tool execution tests passed")
            return True

        finally:
            shutil.rmtree(test_dir)


class TestIntegration:
    """Integration tests for complete workflows."""

    def test_complete_workflow(self):
        """Test complete workflow: list → plan → apply."""
        print("\n" + "="*80)
        print("TEST: Complete Workflow (List → Plan → Apply)")
        print("="*80)

        test_dir = tempfile.mkdtemp(prefix="folder_test_")

        try:
            # Setup test files
            test_files = ["File One.txt", "File Two.pdf", "Photo 123.jpg"]
            for filename in test_files:
                with open(os.path.join(test_dir, filename), 'w') as f:
                    f.write("Test")

            config = build_test_config(test_dir)
            agent = FolderAgent(config)

            # Step 1: List
            print("\nStep 1: List current contents")
            result = agent.execute('folder_list', {'folder_path': test_dir})
            assert not result.get('error')
            print(f"✓ Found {result['total_count']} items")

            # Step 2: Plan
            print("\nStep 2: Generate normalization plan")
            result = agent.execute('folder_plan_alpha', {'folder_path': test_dir})
            assert not result.get('error')
            plan = result['plan']
            print(f"✓ Generated plan with {result['changes_count']} changes")

            # Step 3: Dry-run
            print("\nStep 3: Validate with dry-run")
            result = agent.execute('folder_apply', {
                'plan': plan,
                'folder_path': test_dir,
                'dry_run': True
            })
            assert not result.get('error')
            assert result['dry_run'] == True
            print(f"✓ Dry-run validated {len(result['applied'])} changes")

            # Step 4: Apply
            print("\nStep 4: Apply changes")
            result = agent.execute('folder_apply', {
                'plan': plan,
                'folder_path': test_dir,
                'dry_run': False
            })
            assert not result.get('error')
            assert result['success'] == True
            print(f"✓ Applied {len(result['applied'])} changes")

            # Step 5: Verify
            print("\nStep 5: Verify final state")
            result = agent.execute('folder_list', {'folder_path': test_dir})
            assert not result.get('error')

            # Check all files are normalized
            for item in result['items']:
                name = item['name']
                # Should be lowercase with underscores
                if item['type'] == 'file':
                    name_part = name.rsplit('.', 1)[0]
                    assert name_part.islower(), f"Should be lowercase: {name}"
                    assert ' ' not in name, f"Should not have spaces: {name}"
                print(f"  ✓ {name}")

            print("\n✅ Complete workflow test passed")
            return True

        finally:
            shutil.rmtree(test_dir)


def run_all_tests():
    """Run all test suites."""
    print("\n" + "="*80)
    print("FOLDER AGENT TEST SUITE")
    print("="*80)

    test_results = []

    # Test FolderTools
    tools_tests = TestFolderTools()
    test_results.append(("Sandbox Validation", tools_tests.test_check_sandbox()))
    test_results.append(("Folder Listing", tools_tests.test_folder_list()))
    test_results.append(("Plan Alpha", tools_tests.test_plan_alpha()))
    test_results.append(("Apply Dry-Run", tools_tests.test_apply_dry_run()))
    test_results.append(("Apply Actual", tools_tests.test_apply_actual()))
    test_results.append(("Conflict Handling", tools_tests.test_conflict_handling()))

    # Test FolderAgent
    agent_tests = TestFolderAgent()
    test_results.append(("Agent Initialization", agent_tests.test_agent_initialization()))
    test_results.append(("Tool Execution", agent_tests.test_tool_execution()))

    # Integration tests
    integration_tests = TestIntegration()
    test_results.append(("Complete Workflow", integration_tests.test_complete_workflow()))

    # Print summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)

    passed = 0
    failed = 0

    for name, result in test_results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {name}")
        if result:
            passed += 1
        else:
            failed += 1

    print("\n" + "="*80)
    print(f"Total: {passed + failed} tests")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    print("="*80)

    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
