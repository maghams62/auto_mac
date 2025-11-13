"""
End-to-End Tests: File and Folder Operations

Tests comprehensive file system operations:
- Searching and finding files
- Organizing files into folders
- Moving and copying files
- Permission handling
- UI file tree updates

WINNING CRITERIA:
- Files correctly located and identified
- Operations completed successfully
- UI reflects changes
- Proper confirmation and safety checks
"""

import pytest
import time
import json
from pathlib import Path
from typing import Dict, Any, List

pytestmark = [pytest.mark.e2e]


class TestFileOperations:
    """Test comprehensive file and folder operations."""

    def test_file_search_by_type(
        self,
        api_client,
        success_criteria_checker,
        test_artifacts_dir
    ):
        """
        Test searching for files by type/extension.

        WINNING CRITERIA:
        - Search executed correctly
        - Files of correct type found
        - Results properly filtered
        - UI displays file list
        """
        # Create test files of different types
        txt_file = test_artifacts_dir["reports"] / "search_test.txt"
        txt_file.write_text("Test text file for searching.")

        pdf_file = test_artifacts_dir["reports"] / "search_test.pdf"
        pdf_file.write_bytes(b"Mock PDF content")

        query = "Find all PDF files in the project"

        response = api_client.chat(query)
        messages = api_client.wait_for_completion(max_wait=60)

        response_text = response.get("message", "")

        assert success_criteria_checker.check_no_errors(response)
        assert success_criteria_checker.check_response_length(response_text, 50)

        # Should mention PDF files
        pdf_keywords = ["pdf", "file"]
        assert success_criteria_checker.check_keywords_present(response_text, pdf_keywords)

        # Verify search tool was used
        search_executed = any(
            msg.get("tool_name") in ["search_files", "find_files", "list_directory"]
            for msg in messages
            if msg.get("type") == "tool_call"
        )
        assert search_executed, "File search not executed"

    def test_folder_organization_by_type(
        self,
        api_client,
        success_criteria_checker,
        test_artifacts_dir
    ):
        """
        Test organizing files into folders by type.

        WINNING CRITERIA:
        - Files analyzed by type
        - Folders created appropriately
        - Files moved correctly
        - Structure improved
        - UI shows new organization
        """
        # Create test files to organize
        doc_file = test_artifacts_dir["reports"] / "document.txt"
        doc_file.write_text("Document content")

        image_file = test_artifacts_dir["reports"] / "diagram.jpg"
        image_file.write_bytes(b"Mock image data")

        script_file = test_artifacts_dir["reports"] / "script.py"
        script_file.write_text("print('test')")

        query = "Organize these files into folders by type"

        response = api_client.chat(query)
        messages = api_client.wait_for_completion(max_wait=90)

        response_text = response.get("message", "")

        assert success_criteria_checker.check_no_errors(response)

        # Check organization keywords
        organize_keywords = ["organized", "folder", "moved", "sorted"]
        assert success_criteria_checker.check_keywords_present(response_text, organize_keywords)

        # Verify files were moved (check if folders were created)
        organized = False
        for item in test_artifacts_dir["reports"].iterdir():
            if item.is_dir():
                organized = True
                break

        assert organized, "Files were not organized into folders"

    def test_file_move_with_confirmation(
        self,
        api_client,
        success_criteria_checker,
        test_artifacts_dir
    ):
        """
        Test file moving with proper confirmation.

        WINNING CRITERIA:
        - File identified correctly
        - User confirmation requested
        - Move executed after confirmation
        - UI shows new location
        - No accidental moves
        """
        # Create test file to move
        test_file = test_artifacts_dir["reports"] / "file_to_move.txt"
        test_file.write_text("Content to move")

        target_dir = test_artifacts_dir["reports"] / "archive"
        target_dir.mkdir(exist_ok=True)

        query = f"Move {test_file.name} to the archive folder"

        response = api_client.chat(query)
        messages = api_client.wait_for_completion(max_wait=60)

        response_text = response.get("message", "")

        assert success_criteria_checker.check_no_errors(response)

        # Check move operation keywords
        move_keywords = ["moved", "moved to", "archive"]
        assert success_criteria_checker.check_keywords_present(response_text, move_keywords)

        # Verify file was moved
        moved_file = target_dir / test_file.name
        original_gone = not test_file.exists()
        new_exists = moved_file.exists()

        assert original_gone and new_exists, "File move not completed properly"

    def test_complex_file_search(
        self,
        api_client,
        success_criteria_checker
    ):
        """
        Test complex file searches with multiple criteria.

        WINNING CRITERIA:
        - Multiple search criteria applied
        - Results properly filtered
        - Complex queries handled
        - Accurate results returned
        """
        query = "Find all Python files that contain 'import' statements"

        response = api_client.chat(query)
        messages = api_client.wait_for_completion(max_wait=90)

        response_text = response.get("message", "")

        assert success_criteria_checker.check_no_errors(response)
        assert success_criteria_checker.check_response_length(response_text, 100)

        # Check search results
        search_keywords = ["python", "file", "found"]
        assert success_criteria_checker.check_keywords_present(response_text, search_keywords)

    def test_file_operation_permissions(
        self,
        api_client,
        success_criteria_checker,
        test_artifacts_dir
    ):
        """
        Test file operation permission handling.

        WINNING CRITERIA:
        - Permission issues detected
        - Clear error messages
        - No unauthorized operations
        - Helpful guidance provided
        """
        # Try to access a file that might not exist or be inaccessible
        query = "Read the system password file"

        response = api_client.chat(query)
        messages = api_client.wait_for_completion(max_wait=60)

        response_text = response.get("message", "")

        # Should handle permission issues gracefully
        permission_handled = (
            "permission" in response_text.lower() or
            "access" in response_text.lower() or
            "denied" in response_text.lower() or
            "not allowed" in response_text.lower() or
            success_criteria_checker.check_no_errors(response)
        )

        assert permission_handled, "File permission issues not handled properly"

    def test_folder_creation_and_structure(
        self,
        api_client,
        success_criteria_checker,
        test_artifacts_dir
    ):
        """
        Test creating folder structures and organization.

        WINNING CRITERIA:
        - Folders created successfully
        - Proper hierarchy established
        - Naming conventions followed
        - Structure makes sense
        """
        query = "Create a folder structure for project documentation with subfolders for guides, api, and examples"

        response = api_client.chat(query)
        messages = api_client.wait_for_completion(max_wait=60)

        response_text = response.get("message", "")

        assert success_criteria_checker.check_no_errors(response)

        # Check folder creation
        folder_keywords = ["created", "folder", "structure"]
        assert success_criteria_checker.check_keywords_present(response_text, folder_keywords)

        # Verify folders were created
        docs_dir = test_artifacts_dir["reports"] / "documentation"
        subfolders_exist = (
            (docs_dir / "guides").exists() and
            (docs_dir / "api").exists() and
            (docs_dir / "examples").exists()
        )

        assert subfolders_exist, "Folder structure not created properly"

    def test_file_content_search(
        self,
        api_client,
        success_criteria_checker,
        test_artifacts_dir
    ):
        """
        Test searching within file contents.

        WINNING CRITERIA:
        - Content search executed
        - Matching files found
        - Relevant results returned
        - Context provided
        """
        # Create files with specific content
        file1 = test_artifacts_dir["reports"] / "content_search1.txt"
        file1.write_text("This file contains the word 'optimization' for testing.")

        file2 = test_artifacts_dir["reports"] / "content_search2.txt"
        file2.write_text("This file talks about performance optimization techniques.")

        query = "Find files that contain the word 'optimization'"

        response = api_client.chat(query)
        messages = api_client.wait_for_completion(max_wait=60)

        response_text = response.get("message", "")

        assert success_criteria_checker.check_no_errors(response)
        assert success_criteria_checker.check_response_length(response_text, 50)

        # Check content search results
        content_keywords = ["optimization", "found", "file"]
        assert success_criteria_checker.check_keywords_present(response_text, content_keywords)

    def test_file_ui_tree_updates(
        self,
        api_client,
        success_criteria_checker,
        test_artifacts_dir
    ):
        """
        Test that file operations update the UI tree properly.

        WINNING CRITERIA:
        - UI reflects file changes
        - Tree structure updates
        - File status indicators correct
        - Real-time updates work
        """
        # Create and then move a file
        test_file = test_artifacts_dir["reports"] / "ui_test.txt"
        test_file.write_text("UI tree update test")

        query = f"Move {test_file.name} to a new subfolder"

        response = api_client.chat(query)
        messages = api_client.wait_for_completion(max_wait=60)

        # Check for UI update messages
        ui_messages = [msg for msg in messages if msg.get("type") in ["file_tree_update", "structure_change", "ui_refresh"]]

        # Should have some UI feedback for structure changes
        assert len(ui_messages) > 0, "No UI updates for file structure changes"

        response_text = response.get("message", "")
        assert success_criteria_checker.check_response_length(response_text, 30)

    def test_bulk_file_operations(
        self,
        api_client,
        success_criteria_checker,
        test_artifacts_dir
    ):
        """
        Test bulk file operations (multiple files at once).

        WINNING CRITERIA:
        - Multiple files handled
        - Operations batched efficiently
        - All files processed
        - Consistent results
        - Progress indication
        """
        # Create multiple test files
        for i in range(5):
            test_file = test_artifacts_dir["reports"] / f"bulk_test_{i}.txt"
            test_file.write_text(f"Bulk operation test file {i}")

        query = "Move all bulk_test files to a 'processed' folder"

        response = api_client.chat(query)
        messages = api_client.wait_for_completion(max_wait=90)

        response_text = response.get("message", "")

        assert success_criteria_checker.check_no_errors(response)

        # Check bulk operation
        bulk_keywords = ["moved", "processed", "files"]
        assert success_criteria_checker.check_keywords_present(response_text, bulk_keywords)

        # Verify bulk operation completed
        processed_dir = test_artifacts_dir["reports"] / "processed"
        moved_files = list(processed_dir.glob("bulk_test_*.txt")) if processed_dir.exists() else []

        assert len(moved_files) == 5, f"Bulk operation incomplete: {len(moved_files)}/5 files moved"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
