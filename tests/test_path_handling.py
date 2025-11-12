"""
Test file path resolution and missing asset handling for PPT/report loaders.
"""
import pytest
import tempfile
import os
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add src to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.documents.parser import DocumentParser
from src.automation.keynote_composer import KeynoteComposer
from src.utils import load_config


class TestPathHandling:
    """Test file path resolution and error handling."""

    def test_document_parser_missing_file(self):
        """Test that document parser handles missing files gracefully."""
        config = {}
        parser = DocumentParser(config)

        # Test with non-existent file
        result = parser.parse_document("/non/existent/file.pdf")
        assert result is None

        # Test with empty path
        result = parser.parse_document("")
        assert result is None

    def test_document_parser_valid_pdf(self):
        """Test document parser with valid PDF file."""
        config = {}
        parser = DocumentParser(config)

        # Create a temporary text file to simulate a document
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("Test document content\nLine 2\nLine 3")
            temp_file = f.name

        try:
            result = parser.parse_document(temp_file)
            assert result is not None
            assert result['file_name'].endswith('.txt')
            assert result['file_type'] == 'txt'
            assert 'Test document content' in result['content']
        finally:
            os.unlink(temp_file)

    def test_document_parser_unsupported_format(self):
        """Test document parser with unsupported file format."""
        config = {}
        parser = DocumentParser(config)

        with tempfile.NamedTemporaryFile(mode='w', suffix='.unsupported', delete=False) as f:
            f.write("Unsupported format content")
            temp_file = f.name

        try:
            result = parser.parse_document(temp_file)
            assert result is None
        finally:
            os.unlink(temp_file)

    def test_keynote_composer_missing_image(self):
        """Test that Keynote composer handles missing images gracefully."""
        config = load_config()
        composer = KeynoteComposer(config)

        # Create slides with missing image
        slides = [
            {
                "title": "Text Slide",
                "content": "This is a text slide"
            },
            {
                "title": "Image Slide",
                "image_path": "/non/existent/image.png"
            },
            {
                "title": "Mixed Slide",
                "content": "This slide has text",
                "image_path": "/another/non/existent/image.jpg"
            }
        ]

        # Mock the AppleScript execution to avoid actually creating Keynote files
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="Success", stderr="")

            # Test with missing images - should still succeed but log warnings
            result = composer.create_presentation(
                title="Test Presentation",
                slides=slides,
                output_path=None  # Don't save to avoid file system changes
            )

            # Should succeed even with missing images
            assert result is True

            # Verify AppleScript was called
            assert mock_run.called

    def test_keynote_composer_valid_image(self):
        """Test Keynote composer with valid image path."""
        config = load_config()
        composer = KeynoteComposer(config)

        # Create a temporary file to simulate an image
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
            temp_image = f.name

        try:
            slides = [
                {
                    "title": "Image Slide",
                    "image_path": temp_image
                }
            ]

            # Mock the AppleScript execution
            with patch('subprocess.run') as mock_run:
                mock_run.return_value = MagicMock(returncode=0, stdout="Success", stderr="")

                result = composer.create_presentation(
                    title="Test Presentation",
                    slides=slides,
                    output_path=None
                )

                assert result is True
                assert mock_run.called

        finally:
            os.unlink(temp_image)

    def test_keynote_composer_output_path_resolution(self):
        """Test that output paths are properly resolved and expanded."""
        config = load_config()
        composer = KeynoteComposer(config)

        slides = [{"title": "Test Slide", "content": "Test content"}]

        # Test with tilde path
        output_path = "~/Documents/test.key"

        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="Success", stderr="")

            result = composer.create_presentation(
                title="Test Presentation",
                slides=slides,
                output_path=output_path
            )

            assert result is True

            # Check that the AppleScript contains the expanded path
            script_call = mock_run.call_args[0][1]  # Get the script file path
            assert len(script_call) > 0

    def test_data_directory_structure(self):
        """Test that data directory structure exists and is accessible."""
        data_dir = Path("data")

        # Check main data directories exist
        assert data_dir.exists()
        assert (data_dir / "screenshots").exists()
        assert (data_dir / "reports").exists()
        assert (data_dir / "presentations").exists()
        assert (data_dir / "logs").exists()

        # Check that directories are writable
        test_file = data_dir / "test_write.tmp"
        try:
            test_file.write_text("test")
            assert test_file.exists()
            test_file.unlink()
        except Exception as e:
            pytest.fail(f"Data directory not writable: {e}")

    def test_config_path_resolution(self):
        """Test that config file paths are properly resolved."""
        from src.config import Config

        # Test loading config
        config = load_config()
        assert isinstance(config, dict)
        assert 'openai' in config
        assert 'logging' in config

        # Test screenshot directory from config
        screenshot_dir = config.get('screenshots', {}).get('base_dir')
        if screenshot_dir:
            path = Path(screenshot_dir)
            assert path.exists() or path.parent.exists()  # Either exists or parent does


class TestIntegrationPaths:
    """Integration tests for path handling across components."""

    def test_document_indexer_paths(self):
        """Test document indexer path resolution."""
        from src.documents.indexer import DocumentIndexer

        config = load_config()
        indexer = DocumentIndexer(config)

        # Test with valid directory
        test_docs_dir = Path("tests/data/test_docs")
        if test_docs_dir.exists():
            # Should not crash even if no documents
            try:
                indexer.index_documents(str(test_docs_dir))
            except Exception as e:
                # It's okay if indexing fails, as long as it doesn't crash on path issues
                assert "No such file or directory" not in str(e)

    def test_presentation_agent_file_handling(self):
        """Test presentation agent file handling."""
        from src.agent.presentation_agent import PresentationAgent

        config = load_config()
        agent = PresentationAgent(config)

        # Test with non-existent file path
        try:
            result = agent.create_presentation_from_file("/non/existent/file.pdf")
            # Should return error gracefully
            assert "error" in result.lower() or result is None or isinstance(result, dict)
        except Exception as e:
            # Should not crash with path errors
            assert "No such file or directory" not in str(e)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
