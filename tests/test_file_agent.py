"""
Unit tests for File Agent tools, specifically list_related_documents.
"""

import sys
import os
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.agent.file_agent import list_related_documents


def test_list_related_documents_empty_results():
    """Test that list_related_documents handles empty results gracefully."""
    with patch('src.agent.file_agent.load_config') as mock_config, \
         patch('src.agent.file_agent.DocumentIndexer') as mock_indexer_class, \
         patch('src.agent.file_agent.SemanticSearch') as mock_search_class:
        
        # Setup mocks
        mock_config.return_value = {"search": {"top_k": 10, "similarity_threshold": 0.5}}
        mock_indexer = Mock()
        mock_indexer_class.return_value = mock_indexer
        mock_search = Mock()
        mock_search_class.return_value = mock_search
        
        # Mock empty results
        mock_search.search_and_group.return_value = []
        
        # Call the tool
        result = list_related_documents.invoke({"query": "nonexistent documents"})
        
        # Assertions
        assert result["type"] == "file_list", f"Expected type='file_list', got: {result.get('type')}"
        assert result["files"] == [], f"Expected empty files array, got: {result.get('files')}"
        assert result["total_count"] == 0, f"Expected total_count=0, got: {result.get('total_count')}"
        assert "No documents found" in result["message"], \
            f"Expected friendly message, got: {result.get('message')}"
        assert not result.get("error"), "Should not have error flag for empty results"
        
        print("✅ Empty results test passed")


def test_list_related_documents_returns_structured_results():
    """Test that list_related_documents returns properly structured results."""
    with patch('src.agent.file_agent.load_config') as mock_config, \
         patch('src.agent.file_agent.DocumentIndexer') as mock_indexer_class, \
         patch('src.agent.file_agent.SemanticSearch') as mock_search_class:
        
        # Setup mocks
        mock_config.return_value = {"search": {"top_k": 10, "similarity_threshold": 0.5}}
        mock_indexer = Mock()
        mock_indexer_class.return_value = mock_indexer
        mock_search = Mock()
        mock_search_class.return_value = mock_search
        
        # Mock grouped results
        mock_search.search_and_group.return_value = [
            {
                "file_path": "/test/path/file1.pdf",
                "file_name": "file1.pdf",
                "file_type": "pdf",
                "total_pages": 5,
                "max_similarity": 0.89,
                "avg_similarity": 0.85,
                "chunks": []
            },
            {
                "file_path": "/test/path/file2.pdf",
                "file_name": "file2.pdf",
                "file_type": "pdf",
                "total_pages": 3,
                "max_similarity": 0.75,
                "avg_similarity": 0.72,
                "chunks": []
            }
        ]
        
        # Call the tool
        result = list_related_documents.invoke({"query": "test documents", "max_results": 10})
        
        # Assertions
        assert result["type"] == "file_list", f"Expected type='file_list', got: {result.get('type')}"
        assert len(result["files"]) == 2, f"Expected 2 files, got: {len(result.get('files', []))}"
        assert result["total_count"] == 2, f"Expected total_count=2, got: {result.get('total_count')}"
        
        # Check first file structure
        file1 = result["files"][0]
        assert file1["name"] == "file1.pdf", f"Expected name='file1.pdf', got: {file1.get('name')}"
        assert file1["path"] == "/test/path/file1.pdf", f"Expected correct path, got: {file1.get('path')}"
        assert file1["score"] == 0.89, f"Expected score=0.89, got: {file1.get('score')}"
        assert file1["meta"]["file_type"] == "pdf", f"Expected file_type='pdf', got: {file1.get('meta', {}).get('file_type')}"
        assert file1["meta"]["total_pages"] == 5, f"Expected total_pages=5, got: {file1.get('meta', {}).get('total_pages')}"
        
        print("✅ Structured results test passed")


def test_list_related_documents_respects_max_results_cap():
    """Test that list_related_documents respects max_results cap of 25."""
    with patch('src.agent.file_agent.load_config') as mock_config, \
         patch('src.agent.file_agent.DocumentIndexer') as mock_indexer_class, \
         patch('src.agent.file_agent.SemanticSearch') as mock_search_class:
        
        # Setup mocks
        mock_config.return_value = {"search": {"top_k": 10, "similarity_threshold": 0.5}}
        mock_indexer = Mock()
        mock_indexer_class.return_value = mock_indexer
        mock_search = Mock()
        mock_search_class.return_value = mock_search
        
        # Mock many results
        mock_search.search_and_group.return_value = [
            {
                "file_path": f"/test/path/file{i}.pdf",
                "file_name": f"file{i}.pdf",
                "file_type": "pdf",
                "total_pages": 1,
                "max_similarity": 0.9 - (i * 0.01),
                "avg_similarity": 0.85,
                "chunks": []
            }
            for i in range(30)  # More than the cap
        ]
        
        # Call with max_results > 25 (should be capped)
        result = list_related_documents.invoke({"query": "test", "max_results": 30})
        
        # Should only return 25 files (the cap)
        assert len(result["files"]) == 25, \
            f"Expected 25 files (cap), got: {len(result.get('files', []))}"
        assert result["total_count"] == 30, \
            f"Expected total_count=30 (all found), got: {result.get('total_count')}"
        
        print("✅ Max results cap test passed")


def test_list_related_documents_defaults_to_10():
    """Test that list_related_documents defaults to 10 results."""
    with patch('src.agent.file_agent.load_config') as mock_config, \
         patch('src.agent.file_agent.DocumentIndexer') as mock_indexer_class, \
         patch('src.agent.file_agent.SemanticSearch') as mock_search_class:
        
        # Setup mocks
        mock_config.return_value = {"search": {"top_k": 10, "similarity_threshold": 0.5}}
        mock_indexer = Mock()
        mock_indexer_class.return_value = mock_indexer
        mock_search = Mock()
        mock_search_class.return_value = mock_search
        
        # Mock 15 results
        mock_search.search_and_group.return_value = [
            {
                "file_path": f"/test/path/file{i}.pdf",
                "file_name": f"file{i}.pdf",
                "file_type": "pdf",
                "total_pages": 1,
                "max_similarity": 0.9 - (i * 0.01),
                "avg_similarity": 0.85,
                "chunks": []
            }
            for i in range(15)
        ]
        
        # Call without max_results (should default to 10)
        result = list_related_documents.invoke({"query": "test"})
        
        # Should return 10 files (default)
        assert len(result["files"]) == 10, \
            f"Expected 10 files (default), got: {len(result.get('files', []))}"
        
        print("✅ Default max_results test passed")


if __name__ == "__main__":
    test_list_related_documents_empty_results()
    test_list_related_documents_returns_structured_results()
    test_list_related_documents_respects_max_results_cap()
    test_list_related_documents_defaults_to_10()
    print("\n✅ All file agent tests passed!")

