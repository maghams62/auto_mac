"""
Test document listing service functionality.

Tests cover:
- Listing documents when index exists
- Filtering by name
- Filtering by folder
- Empty index handling
- Error handling
"""

import sys
import os
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.services.document_listing import DocumentListingService


def test_list_documents_no_index():
    """Test listing when no documents are indexed."""
    config = {"openai": {"api_key": "test"}}
    service = DocumentListingService(config)

    # Mock indexer with no documents
    with patch('src.documents.DocumentIndexer') as mock_indexer_class:
        mock_indexer = Mock()
        mock_indexer.documents = []
        mock_indexer_class.return_value = mock_indexer

        result = service.list_documents()

        assert result["type"] == "document_list"
        assert "No documents indexed yet" in result["message"]
        assert result["documents"] == []
        assert result["total_count"] == 0
        assert result["has_more"] == False


def test_list_documents_with_data():
    """Test listing documents with mock indexed data."""
    config = {"openai": {"api_key": "test"}}
    service = DocumentListingService(config)

    # Mock document chunks
    mock_chunks = [
        {
            "file_path": "/docs/test1.pdf",
            "file_name": "test1.pdf",
            "file_type": "pdf",
            "total_pages": 5,
            "content": "Document: test1.pdf\n\nThis is test content."
        },
        {
            "file_path": "/docs/test2.docx",
            "file_name": "test2.docx",
            "file_type": "docx",
            "total_pages": 3,
            "content": "Document: test2.docx\n\nMore test content."
        }
    ]

    with patch('src.documents.DocumentIndexer') as mock_indexer_class, \
         patch.object(service, '_enrich_document_metadata') as mock_enrich:

        mock_indexer = Mock()
        mock_indexer.documents = mock_chunks
        mock_indexer_class.return_value = mock_indexer

        # Mock enrichment
        mock_enrich.side_effect = lambda doc: doc.update({
            'size': 1024,
            'modified': '2024-01-01T10:00:00',
            'size_human': '1 KB',
            'preview': 'This is test content.'
        })

        result = service.list_documents()

        assert result["type"] == "document_list"
        assert result["total_count"] == 2
        assert len(result["documents"]) == 2
        assert result["has_more"] == False

        # Check document structure
        doc1 = result["documents"][0]
        assert doc1["name"] == "test1.pdf"
        assert doc1["path"] == "/docs/test1.pdf"
        assert doc1["type"] == "pdf"
        assert doc1["total_pages"] == 5


def test_list_documents_with_filter():
    """Test filtering documents by name."""
    config = {"openai": {"api_key": "test"}}
    service = DocumentListingService(config)

    mock_chunks = [
        {
            "file_path": "/docs/guitar_tabs.pdf",
            "file_name": "guitar_tabs.pdf",
            "file_type": "pdf",
            "content": "Document: guitar_tabs.pdf\n\nGuitar tabs content."
        },
        {
            "file_path": "/docs/finance_report.pdf",
            "file_name": "finance_report.pdf",
            "file_type": "pdf",
            "content": "Document: finance_report.pdf\n\nFinance content."
        }
    ]

    with patch('src.documents.DocumentIndexer') as mock_indexer_class, \
         patch.object(service, '_enrich_document_metadata') as mock_enrich:

        mock_indexer = Mock()
        mock_indexer.documents = mock_chunks
        mock_indexer_class.return_value = mock_indexer
        mock_enrich.side_effect = lambda doc: doc.update({
            'size': 1024,
            'modified': '2024-01-01T10:00:00',
            'size_human': '1 KB',
            'preview': ''
        })

        result = service.list_documents(filter_text="guitar")

        assert result["total_count"] == 1
        assert len(result["documents"]) == 1
        assert result["documents"][0]["name"] == "guitar_tabs.pdf"


def test_list_documents_no_matches():
    """Test filtering that results in no matches."""
    config = {"openai": {"api_key": "test"}}
    service = DocumentListingService(config)

    mock_chunks = [
        {
            "file_path": "/docs/test.pdf",
            "file_name": "test.pdf",
            "file_type": "pdf",
            "content": "Document: test.pdf\n\nContent."
        }
    ]

    with patch('src.documents.DocumentIndexer') as mock_indexer_class:
        mock_indexer = Mock()
        mock_indexer.documents = mock_chunks
        mock_indexer_class.return_value = mock_indexer

        result = service.list_documents(filter_text="nonexistent")

        assert result["total_count"] == 0
        assert len(result["documents"]) == 0
        assert "No documents found matching 'nonexistent'" == result["message"]


def test_list_documents_folder_filter():
    """Test filtering by folder name."""
    config = {"openai": {"api_key": "test"}}
    service = DocumentListingService(config)

    mock_chunks = [
        {
            "file_path": "/finance/budget.pdf",
            "file_name": "budget.pdf",
            "file_type": "pdf",
            "content": "Document: budget.pdf\n\nBudget content."
        },
        {
            "file_path": "/music/tabs.pdf",
            "file_name": "tabs.pdf",
            "file_type": "pdf",
            "content": "Document: tabs.pdf\n\nMusic content."
        }
    ]

    with patch('src.documents.DocumentIndexer') as mock_indexer_class, \
         patch.object(service, '_enrich_document_metadata') as mock_enrich:

        mock_indexer = Mock()
        mock_indexer.documents = mock_chunks
        mock_indexer_class.return_value = mock_indexer
        mock_enrich.side_effect = lambda doc: doc.update({
            'size': 1024,
            'modified': '2024-01-01T10:00:00',
            'size_human': '1 KB',
            'preview': ''
        })

        result = service.list_documents(filter_text="folder=finance")

        assert result["total_count"] == 1
        assert len(result["documents"]) == 1
        assert "finance" in result["documents"][0]["path"]


def test_list_documents_pagination():
    """Test pagination limits."""
    config = {"openai": {"api_key": "test"}}
    service = DocumentListingService(config)

    # Create 25 mock documents
    mock_chunks = [
        {
            "file_path": f"/docs/test{i}.pdf",
            "file_name": f"test{i}.pdf",
            "file_type": "pdf",
            "content": f"Document: test{i}.pdf\n\nContent {i}."
        } for i in range(25)
    ]

    with patch('src.documents.DocumentIndexer') as mock_indexer_class, \
         patch.object(service, '_enrich_document_metadata') as mock_enrich:

        mock_indexer = Mock()
        mock_indexer.documents = mock_chunks
        mock_indexer_class.return_value = mock_indexer
        mock_enrich.side_effect = lambda doc: doc.update({
            'size': 1024,
            'modified': '2024-01-01T10:00:00',
            'size_human': '1 KB',
            'preview': ''
        })

        result = service.list_documents(max_results=10)

        assert result["total_count"] == 25
        assert len(result["documents"]) == 10  # Limited to max_results
        assert result["has_more"] == True


def test_list_documents_error_handling():
    """Test error handling in document listing."""
    config = {"openai": {"api_key": "test"}}
    service = DocumentListingService(config)

    with patch('src.documents.DocumentIndexer') as mock_indexer_class:
        mock_indexer_class.side_effect = Exception("Test error")

        result = service.list_documents()

        assert result["type"] == "document_list"
        assert "Error listing documents" in result["message"]
        assert result["documents"] == []
        assert result["total_count"] == 0


def run_tests():
    """Run all document listing tests."""
    print("🧪 Running Document Listing Service Tests...")

    test_list_documents_no_index()
    print("✅ test_list_documents_no_index passed")

    test_list_documents_with_data()
    print("✅ test_list_documents_with_data passed")

    test_list_documents_with_filter()
    print("✅ test_list_documents_with_filter passed")

    test_list_documents_no_matches()
    print("✅ test_list_documents_no_matches passed")

    test_list_documents_folder_filter()
    print("✅ test_list_documents_folder_filter passed")

    test_list_documents_pagination()
    print("✅ test_list_documents_pagination passed")

    test_list_documents_error_handling()
    print("✅ test_list_documents_error_handling passed")

    print("🎉 All Document Listing Service tests passed!")


if __name__ == "__main__":
    run_tests()
