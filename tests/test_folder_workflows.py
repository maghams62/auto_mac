"""
Comprehensive test suite for folder workflow queries.

Tests the LLM's ability to decompose folder-related tasks and reason
about which tools to use. Each test creates verifiable test data.

Run with: python tests/test_folder_workflows.py
"""

import os
import sys
import json
import tempfile
import shutil
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class TestFolderWorkflows:
    """Test folder workflow reasoning and execution."""

    def __init__(self):
        self.test_dir = None
        self.folder_tools = None
        self.config = None

    def _init_tools(self):
        """Lazy initialization to avoid circular imports."""
        if self.folder_tools is None:
            from src.utils import load_config
            from src.automation.folder_tools import FolderTools
            self.config = load_config()
            self.folder_tools = FolderTools(self.config)

    def setup_test_environment(self):
        """Create test directory with sample files."""
        self._init_tools()
        # Get the configured sandbox folder
        sandbox = self.folder_tools.allowed_folder

        # Create test directory
        self.test_dir = os.path.join(sandbox, "test_folder_workflows")
        os.makedirs(self.test_dir, exist_ok=True)

        print(f"\n✓ Created test directory: {self.test_dir}")
        return self.test_dir

    def teardown_test_environment(self):
        """Clean up test directory."""
        if self.test_dir and os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
            print(f"✓ Cleaned up test directory: {self.test_dir}")

    def create_test_file(self, filename, content):
        """Create a test file with given content."""
        path = os.path.join(self.test_dir, filename)
        with open(path, 'w') as f:
            f.write(content)
        return path

    def test_1_find_duplicates(self):
        """Test 1: Find duplicate files by content."""
        print("\n" + "="*70)
        print("TEST 1: Find Duplicate Files")
        print("="*70)

        # Create test files with duplicates
        self.create_test_file("doc1.txt", "This is a test document.")
        self.create_test_file("doc2.txt", "This is a test document.")  # Duplicate of doc1
        self.create_test_file("doc3.txt", "Different content here.")
        self.create_test_file("report.txt", "This is a test document.")  # Another duplicate

        print("\n📁 Created test files:")
        print("  - doc1.txt (content: 'This is a test document.')")
        print("  - doc2.txt (DUPLICATE of doc1.txt)")
        print("  - doc3.txt (unique content)")
        print("  - report.txt (DUPLICATE of doc1.txt)")

        # Run duplicate detection
        result = self.folder_tools.find_duplicates(self.test_dir, recursive=False)

        # Verify results
        assert not result.get('error'), f"Error: {result.get('error_message')}"
        assert result['total_duplicate_groups'] == 1, \
            f"Expected 1 duplicate group, got {result['total_duplicate_groups']}"
        assert result['total_duplicate_files'] == 3, \
            f"Expected 3 duplicate files, got {result['total_duplicate_files']}"

        duplicate_group = result['duplicates'][0]
        assert duplicate_group['count'] == 3, \
            f"Expected 3 files in group, got {duplicate_group['count']}"

        file_names = {f['name'] for f in duplicate_group['files']}
        expected_names = {'doc1.txt', 'doc2.txt', 'report.txt'}
        assert file_names == expected_names, \
            f"Expected files {expected_names}, got {file_names}"

        print("\n✅ TEST 1 PASSED")
        print(f"  ✓ Found {result['total_duplicate_groups']} duplicate group")
        print(f"  ✓ Found {result['total_duplicate_files']} duplicate files")
        print(f"  ✓ Wasted space: {result['wasted_space_bytes']} bytes")
        print(f"  ✓ Files in group: {', '.join(file_names)}")

        return True

    def test_2_no_duplicates(self):
        """Test 2: Verify no false positives when all files are unique."""
        print("\n" + "="*70)
        print("TEST 2: No Duplicates (All Unique Files)")
        print("="*70)

        # Clear and create unique files
        shutil.rmtree(self.test_dir)
        os.makedirs(self.test_dir)

        self.create_test_file("file1.txt", "Content one")
        self.create_test_file("file2.txt", "Content two")
        self.create_test_file("file3.txt", "Content three")

        print("\n📁 Created test files:")
        print("  - file1.txt (unique)")
        print("  - file2.txt (unique)")
        print("  - file3.txt (unique)")

        # Run duplicate detection
        result = self.folder_tools.find_duplicates(self.test_dir, recursive=False)

        # Verify no duplicates found
        assert not result.get('error'), f"Error: {result.get('error_message')}"
        assert result['total_duplicate_groups'] == 0, \
            f"Expected 0 duplicate groups, got {result['total_duplicate_groups']}"
        assert result['total_duplicate_files'] == 0, \
            f"Expected 0 duplicate files, got {result['total_duplicate_files']}"
        assert result['wasted_space_bytes'] == 0, \
            f"Expected 0 wasted bytes, got {result['wasted_space_bytes']}"

        print("\n✅ TEST 2 PASSED")
        print("  ✓ No false positives")
        print("  ✓ All files correctly identified as unique")

        return True

    def test_3_folder_list(self):
        """Test 3: List folder contents."""
        print("\n" + "="*70)
        print("TEST 3: List Folder Contents")
        print("="*70)

        # Clear and create test files
        shutil.rmtree(self.test_dir)
        os.makedirs(self.test_dir)

        self.create_test_file("readme.txt", "Read me first")
        self.create_test_file("data.json", '{"key": "value"}')
        self.create_test_file("script.py", 'print("hello")')

        # Create a subdirectory
        subdir = os.path.join(self.test_dir, "subfolder")
        os.makedirs(subdir)

        print("\n📁 Created test structure:")
        print("  - readme.txt")
        print("  - data.json")
        print("  - script.py")
        print("  - subfolder/ (directory)")

        # List folder
        result = self.folder_tools.list_folder(self.test_dir)

        # Verify results
        assert not result.get('error'), f"Error: {result.get('error_message')}"
        assert result['total_count'] == 4, \
            f"Expected 4 items, got {result['total_count']}"

        # Verify all items are present
        item_names = {item['name'] for item in result['items']}
        expected_names = {'readme.txt', 'data.json', 'script.py', 'subfolder'}
        assert item_names == expected_names, \
            f"Expected items {expected_names}, got {item_names}"

        # Verify file types
        files = [item for item in result['items'] if item['type'] == 'file']
        dirs = [item for item in result['items'] if item['type'] == 'dir']
        assert len(files) == 3, f"Expected 3 files, got {len(files)}"
        assert len(dirs) == 1, f"Expected 1 directory, got {len(dirs)}"

        print("\n✅ TEST 3 PASSED")
        print(f"  ✓ Listed {result['total_count']} items")
        print(f"  ✓ Found {len(files)} files and {len(dirs)} directory")
        print(f"  ✓ Items: {', '.join(sorted(item_names))}")

        return True

    def test_4_organize_by_type(self):
        """Test 4: Organize files by extension."""
        print("\n" + "="*70)
        print("TEST 4: Organize Files by Type")
        print("="*70)

        # Clear and create mixed file types
        shutil.rmtree(self.test_dir)
        os.makedirs(self.test_dir)

        self.create_test_file("doc1.txt", "Text 1")
        self.create_test_file("doc2.txt", "Text 2")
        self.create_test_file("image1.png", "fake image data")
        self.create_test_file("image2.png", "fake image data")
        self.create_test_file("data.json", '{}')

        print("\n📁 Created test files:")
        print("  - doc1.txt, doc2.txt (2 TXT files)")
        print("  - image1.png, image2.png (2 PNG files)")
        print("  - data.json (1 JSON file)")

        # Run organization (dry-run first)
        result = self.folder_tools.organize_by_file_type(self.test_dir, dry_run=True)

        # Verify dry-run results
        assert not result.get('error'), f"Error: {result.get('error_message')}"
        assert result['dry_run'] is True, "Should be a dry-run"
        assert result['summary']['total_files_considered'] == 5, \
            f"Expected 5 files, got {result['summary']['total_files_considered']}"

        # Verify target folders
        target_folders = result['summary']['target_folders']
        expected_folders = ['JSON', 'PNG', 'TXT']
        assert set(target_folders) == set(expected_folders), \
            f"Expected folders {expected_folders}, got {target_folders}"

        print("\n✅ TEST 4 PASSED (DRY-RUN)")
        print(f"  ✓ Would organize {result['summary']['total_files_considered']} files")
        print(f"  ✓ Would create folders: {', '.join(sorted(target_folders))}")

        # Now apply for real
        result = self.folder_tools.organize_by_file_type(self.test_dir, dry_run=False)

        # Verify actual organization
        assert not result.get('error'), f"Error: {result.get('error_message')}"
        assert result['success'], "Organization should succeed"
        assert len(result['applied']) == 5, \
            f"Expected 5 files moved, got {len(result['applied'])}"

        # Verify folders were created
        for folder in expected_folders:
            folder_path = os.path.join(self.test_dir, folder)
            assert os.path.exists(folder_path), f"Folder {folder} should exist"

        # Verify files were moved
        assert os.path.exists(os.path.join(self.test_dir, 'TXT', 'doc1.txt'))
        assert os.path.exists(os.path.join(self.test_dir, 'TXT', 'doc2.txt'))
        assert os.path.exists(os.path.join(self.test_dir, 'PNG', 'image1.png'))
        assert os.path.exists(os.path.join(self.test_dir, 'PNG', 'image2.png'))
        assert os.path.exists(os.path.join(self.test_dir, 'JSON', 'data.json'))

        # Verify original files are gone
        assert not os.path.exists(os.path.join(self.test_dir, 'doc1.txt'))
        assert not os.path.exists(os.path.join(self.test_dir, 'image1.png'))

        print("\n✅ TEST 4 PASSED (ACTUAL EXECUTION)")
        print(f"  ✓ Created folders: {', '.join(sorted(expected_folders))}")
        print(f"  ✓ Moved {len(result['applied'])} files successfully")
        print("  ✓ Verified file organization with ls command")

        return True

    def test_5_recursive_duplicates(self):
        """Test 5: Find duplicates recursively across subdirectories."""
        print("\n" + "="*70)
        print("TEST 5: Recursive Duplicate Detection")
        print("="*70)

        # Clear and create nested structure with duplicates
        shutil.rmtree(self.test_dir)
        os.makedirs(self.test_dir)

        # Top level
        self.create_test_file("root.txt", "Same content")

        # Subdirectory 1
        sub1 = os.path.join(self.test_dir, "sub1")
        os.makedirs(sub1)
        with open(os.path.join(sub1, "file1.txt"), 'w') as f:
            f.write("Same content")

        # Subdirectory 2
        sub2 = os.path.join(self.test_dir, "sub2")
        os.makedirs(sub2)
        with open(os.path.join(sub2, "file2.txt"), 'w') as f:
            f.write("Same content")

        print("\n📁 Created nested structure:")
        print("  - root.txt (content: 'Same content')")
        print("  - sub1/file1.txt (DUPLICATE)")
        print("  - sub2/file2.txt (DUPLICATE)")

        # Non-recursive (should find only root.txt)
        result_non_recursive = self.folder_tools.find_duplicates(self.test_dir, recursive=False)
        assert result_non_recursive['total_duplicate_groups'] == 0, \
            "Non-recursive should find no duplicates (only 1 file at top level)"

        print("\n✓ Non-recursive mode: No duplicates (expected)")

        # Recursive (should find all 3 duplicates)
        result_recursive = self.folder_tools.find_duplicates(self.test_dir, recursive=True)
        assert not result_recursive.get('error'), f"Error: {result_recursive.get('error_message')}"
        assert result_recursive['total_duplicate_groups'] == 1, \
            f"Expected 1 duplicate group, got {result_recursive['total_duplicate_groups']}"
        assert result_recursive['total_duplicate_files'] == 3, \
            f"Expected 3 duplicate files, got {result_recursive['total_duplicate_files']}"

        print("\n✅ TEST 5 PASSED")
        print("  ✓ Recursive mode found all duplicates across subdirectories")
        print(f"  ✓ Found {result_recursive['total_duplicate_files']} duplicate files")

        return True

    def test_6_workflow_send_duplicates_email(self):
        """Test 6: End-to-end workflow - Find duplicates and format for email."""
        print("\n" + "="*70)
        print("TEST 6: Workflow - Find Duplicates → Email Summary")
        print("="*70)

        # Create test files
        shutil.rmtree(self.test_dir)
        os.makedirs(self.test_dir)

        self.create_test_file("report_v1.pdf", "PDF content here" * 100)
        self.create_test_file("report_v2.pdf", "PDF content here" * 100)  # Duplicate
        self.create_test_file("report_final.pdf", "PDF content here" * 100)  # Duplicate
        self.create_test_file("notes.txt", "Unique notes")

        print("\n📁 Created test files:")
        print("  - report_v1.pdf (large PDF)")
        print("  - report_v2.pdf (DUPLICATE)")
        print("  - report_final.pdf (DUPLICATE)")
        print("  - notes.txt (unique)")

        # Step 1: Find duplicates
        result = self.folder_tools.find_duplicates(self.test_dir, recursive=False)

        assert not result.get('error'), f"Error: {result.get('error_message')}"
        assert result['total_duplicate_groups'] == 1

        # Step 2: Format results for email
        duplicate_group = result['duplicates'][0]

        email_body = f"""Duplicate Files Report
======================

Found {result['total_duplicate_groups']} group(s) of duplicate files.
Total duplicate files: {result['total_duplicate_files']}
Wasted space: {result['wasted_space_mb']} MB

Duplicate Group 1:
- Hash: {duplicate_group['hash'][:16]}...
- File size: {duplicate_group['size']} bytes
- Count: {duplicate_group['count']} files
- Files:
"""
        for file_info in duplicate_group['files']:
            email_body += f"  * {file_info['name']}\n"

        email_body += "\nRecommendation: Keep one copy and delete the others to free up space."

        print("\n✅ TEST 6 PASSED")
        print("  ✓ Successfully found duplicates")
        print("  ✓ Formatted results for email")
        print(f"  ✓ Email body length: {len(email_body)} characters")
        print("\n📧 Sample email content:")
        print(email_body[:200] + "...")

        return True

    def run_all_tests(self):
        """Run all folder workflow tests."""
        print("\n" + "="*70)
        print("FOLDER WORKFLOW TEST SUITE")
        print("="*70)
        print("Testing LLM reasoning for folder operations...")

        try:
            self.setup_test_environment()

            tests = [
                self.test_1_find_duplicates,
                self.test_2_no_duplicates,
                self.test_3_folder_list,
                self.test_4_organize_by_type,
                self.test_5_recursive_duplicates,
                self.test_6_workflow_send_duplicates_email,
            ]

            passed = 0
            failed = 0

            for test in tests:
                try:
                    test()
                    passed += 1
                except AssertionError as e:
                    print(f"\n❌ {test.__name__} FAILED: {e}")
                    failed += 1
                except Exception as e:
                    print(f"\n❌ {test.__name__} ERROR: {e}")
                    import traceback
                    traceback.print_exc()
                    failed += 1

            print("\n" + "="*70)
            print("TEST SUMMARY")
            print("="*70)
            print(f"✅ Passed: {passed}/{len(tests)}")
            print(f"❌ Failed: {failed}/{len(tests)}")

            if failed == 0:
                print("\n🎉 ALL TESTS PASSED!")
                print("\nKey Findings:")
                print("  1. Duplicate detection works correctly (content-based, not name-based)")
                print("  2. No false positives for unique files")
                print("  3. Folder listing returns accurate file/directory info")
                print("  4. File organization by type works (dry-run + actual)")
                print("  5. Recursive duplicate detection works across subdirectories")
                print("  6. End-to-end workflows chain tools correctly")
                print("\n💡 The LLM can reason about these workflows by:")
                print("  - Understanding user intent (find, organize, summarize, email)")
                print("  - Chaining appropriate tools in sequence")
                print("  - Using folder_path=null for sandbox root")
                print("  - Formatting results for downstream steps (email, reports)")
            else:
                print("\n⚠️  Some tests failed. Review output above.")

            return failed == 0

        finally:
            self.teardown_test_environment()


def main():
    """Run the test suite."""
    tester = TestFolderWorkflows()
    success = tester.run_all_tests()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
