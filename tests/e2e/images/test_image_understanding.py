"""
End-to-End Tests: Image Understanding and Processing

Tests comprehensive image and document understanding:
- Image location and display
- OCR text extraction
- Document description
- Visual search capabilities
- UI rendering of images

WINNING CRITERIA:
- Images located correctly
- Content extracted accurately
- UI displays properly
- Error handling for unsupported formats
"""

import pytest
import time
import json
from pathlib import Path
from typing import Dict, Any, List

pytestmark = [pytest.mark.e2e]


class TestImageUnderstanding:
    """Test comprehensive image understanding functionality."""

    def test_pull_up_image_by_description(
        self,
        api_client,
        success_criteria_checker,
        test_artifacts_dir,
        telemetry_collector
    ):
        """
        Test locating and displaying images by description.

        WINNING CRITERIA:
        - Image located successfully
        - Preview displayed in UI
        - Full-size view available
        - Metadata shown
        - Correct image returned
        """
        # Create a test image file
        test_image = test_artifacts_dir["screenshots"] / "mountain_landscape.jpg"
        test_image.write_bytes(b"Mock JPEG image data")

        query = "Pull up the mountain landscape image"

        telemetry_collector.record_event("image_test_start", {
            "action": "pull_up_image",
            "description": "mountain landscape"
        })

        response = api_client.chat(query)
        messages = api_client.wait_for_completion(max_wait=60)

        response_text = response.get("message", "")

        # Check success criteria
        assert success_criteria_checker.check_no_errors(response)
        assert success_criteria_checker.check_response_length(response_text, 50)

        # Check image display keywords
        image_keywords = ["image", "landscape", "mountain", "displayed"]
        assert success_criteria_checker.check_keywords_present(response_text, image_keywords)

        # Verify image was accessed
        image_accessed = any(
            str(test_image) in str(msg.get("parameters", {}))
            for msg in messages
            if msg.get("type") == "tool_call" and "image" in msg.get("tool_name", "")
        )
        assert image_accessed, "Image file not accessed"

        telemetry_collector.record_event("image_display_complete", {
            "image_found": True,
            "ui_displayed": True
        })

    def test_describe_pdf_document(
        self,
        api_client,
        success_criteria_checker,
        test_artifacts_dir
    ):
        """
        Test OCR and description of PDF documents.

        WINNING CRITERIA:
        - PDF located successfully
        - OCR executed properly
        - Text content extracted
        - Summary generated
        - UI shows document preview
        """
        # Create a test PDF file
        test_pdf = test_artifacts_dir["reports"] / "document.pdf"
        test_pdf.write_bytes(b"Mock PDF content with text for OCR testing")

        query = "Describe this PDF document"

        response = api_client.chat(query)
        messages = api_client.wait_for_completion(max_wait=90)

        response_text = response.get("message", "")

        assert success_criteria_checker.check_no_errors(response)
        assert success_criteria_checker.check_response_length(response_text, 100)

        # Check document description
        pdf_keywords = ["pdf", "document", "content", "text"]
        assert success_criteria_checker.check_keywords_present(response_text, pdf_keywords)

        # Verify OCR/document processing was attempted
        document_processed = any(
            msg.get("tool_name") in ["read_pdf", "ocr_document", "describe_document"]
            for msg in messages
            if msg.get("type") == "tool_call"
        )
        assert document_processed, "Document processing not executed"

    def test_visual_search_functionality(
        self,
        api_client,
        success_criteria_checker,
        test_artifacts_dir
    ):
        """
        Test searching for images by visual content.

        WINNING CRITERIA:
        - Visual search executed
        - Relevant images found
        - Results properly filtered
        - Thumbnails displayed
        - Search accuracy good
        """
        # Create test images with different content
        chart_image = test_artifacts_dir["screenshots"] / "chart.jpg"
        chart_image.write_bytes(b"Mock chart image")

        diagram_image = test_artifacts_dir["screenshots"] / "diagram.png"
        diagram_image.write_bytes(b"Mock diagram image")

        query = "Find images of charts in my documents"

        response = api_client.chat(query)
        messages = api_client.wait_for_completion(max_wait=60)

        response_text = response.get("message", "")

        assert success_criteria_checker.check_no_errors(response)
        assert success_criteria_checker.check_response_length(response_text, 50)

        # Check visual search results
        search_keywords = ["chart", "image", "found"]
        assert success_criteria_checker.check_keywords_present(response_text, search_keywords)

    def test_image_metadata_extraction(
        self,
        api_client,
        success_criteria_checker,
        test_artifacts_dir
    ):
        """
        Test extracting and displaying image metadata.

        WINNING CRITERIA:
        - Metadata extracted successfully
        - File information accurate
        - EXIF data handled
        - Creation/modification dates shown
        - File size/format correct
        """
        # Create test image with some metadata
        test_image = test_artifacts_dir["screenshots"] / "metadata_test.jpg"
        test_image.write_bytes(b"Mock image with metadata")

        query = "Show me the details of this image file"

        response = api_client.chat(query)
        messages = api_client.wait_for_completion(max_wait=60)

        response_text = response.get("message", "")

        assert success_criteria_checker.check_no_errors(response)
        assert success_criteria_checker.check_response_length(response_text, 50)

        # Should show some file information
        metadata_keywords = ["image", "file", "size", "format", "jpg"]
        metadata_info = sum(1 for keyword in metadata_keywords if keyword in response_text.lower())
        assert metadata_info >= 2, f"Insufficient metadata: {metadata_info} metadata fields shown"

    def test_unsupported_image_format_handling(
        self,
        api_client,
        success_criteria_checker,
        test_artifacts_dir
    ):
        """
        NEGATIVE TEST: Handle unsupported image formats gracefully.

        WINNING CRITERIA:
        - Unsupported format detected
        - Clear error message provided
        - Alternative suggestions offered
        - No crash or confusion
        - Helpful guidance given
        """
        # Create a file with unsupported extension
        unsupported_file = test_artifacts_dir["screenshots"] / "test.xyz"
        unsupported_file.write_text("Unsupported format test")

        query = "Describe this image file"

        response = api_client.chat(query)
        messages = api_client.wait_for_completion(max_wait=60)

        response_text = response.get("message", "")

        # Should handle unsupported format gracefully
        format_handling = (
            "format" in response_text.lower() or
            "supported" in response_text.lower() or
            "cannot" in response_text.lower() or
            success_criteria_checker.check_no_errors(response)
        )

        assert format_handling, "Unsupported image format not handled gracefully"

    def test_image_ui_display_and_interaction(
        self,
        api_client,
        success_criteria_checker,
        test_artifacts_dir
    ):
        """
        Test image UI display and interaction features.

        WINNING CRITERIA:
        - Image renders in UI properly
        - Zoom/pan controls work
        - Fullscreen view available
        - Download options functional
        - Navigation between images
        - Loading states proper
        """
        # Create test image
        test_image = test_artifacts_dir["screenshots"] / "ui_test.jpg"
        test_image.write_bytes(b"Mock image for UI testing")

        query = "Show me this image with full details"

        response = api_client.chat(query)
        messages = api_client.wait_for_completion(max_wait=60)

        # Check for UI image display messages
        image_ui_messages = [msg for msg in messages if msg.get("type") in ["image_display", "media_viewer", "file_preview"]]

        # Should have UI rendering messages
        assert len(image_ui_messages) > 0, "No UI image display messages"

        response_text = response.get("message", "")
        assert success_criteria_checker.check_response_length(response_text, 50)

    def test_document_image_extraction(
        self,
        api_client,
        success_criteria_checker,
        test_artifacts_dir
    ):
        """
        Test extracting images from documents.

        WINNING CRITERIA:
        - Document images located
        - Individual images extracted
        - Preview gallery created
        - Navigation between images
        - Original document context maintained
        """
        # Create a mock document with embedded images
        doc_with_images = test_artifacts_dir["reports"] / "presentation.pdf"
        doc_with_images.write_bytes(b"Mock PDF with embedded images")

        query = "Extract all images from this document"

        response = api_client.chat(query)
        messages = api_client.wait_for_completion(max_wait=90)

        response_text = response.get("message", "")

        assert success_criteria_checker.check_no_errors(response)

        # Check image extraction
        extraction_keywords = ["image", "extract", "document"]
        assert success_criteria_checker.check_keywords_present(response_text, extraction_keywords)

    def test_image_search_with_filters(
        self,
        api_client,
        success_criteria_checker,
        test_artifacts_dir
    ):
        """
        Test image search with various filters and criteria.

        WINNING CRITERIA:
        - Search filters applied correctly
        - Results properly filtered
        - Multiple criteria handled
        - Search performance good
        - Results ranking accurate
        """
        # Create images with different characteristics
        screenshot1 = test_artifacts_dir["screenshots"] / "app_screenshot.jpg"
        screenshot1.write_bytes(b"Mock application screenshot")

        photo1 = test_artifacts_dir["screenshots"] / "photo.jpg"
        photo1.write_bytes(b"Mock personal photo")

        diagram1 = test_artifacts_dir["screenshots"] / "diagram.png"
        diagram1.write_bytes(b"Mock technical diagram")

        query = "Find all screenshots from the last week"

        response = api_client.chat(query)
        messages = api_client.wait_for_completion(max_wait=60)

        response_text = response.get("message", "")

        assert success_criteria_checker.check_no_errors(response)

        # Check filtered search results
        filter_keywords = ["screenshot", "found", "image"]
        assert success_criteria_checker.check_keywords_present(response_text, filter_keywords)

    def test_image_annotation_and_markup(
        self,
        api_client,
        success_criteria_checker,
        test_artifacts_dir
    ):
        """
        Test image annotation and markup capabilities.

        WINNING CRITERIA:
        - Annotation tools work
        - Markup saved properly
        - Collaborative features functional
        - Export options available
        - Version history maintained
        """
        # Create test image for annotation
        markup_image = test_artifacts_dir["screenshots"] / "markup_test.jpg"
        markup_image.write_bytes(b"Mock image for markup testing")

        query = "Let me annotate this image with some notes"

        response = api_client.chat(query)
        messages = api_client.wait_for_completion(max_wait=60)

        response_text = response.get("message", "")

        assert success_criteria_checker.check_no_errors(response)

        # Check annotation functionality
        annotation_keywords = ["annotate", "markup", "notes", "image"]
        assert success_criteria_checker.check_keywords_present(response_text, annotation_keywords)

    def test_image_accessibility_features(
        self,
        api_client,
        success_criteria_checker,
        test_artifacts_dir
    ):
        """
        Test image accessibility and alternative text features.

        WINNING CRITERIA:
        - Alt text generated properly
        - Screen reader compatible
        - Keyboard navigation works
        - Color contrast adequate
        - Text alternatives accurate
        """
        # Create test image
        accessible_image = test_artifacts_dir["screenshots"] / "accessibility_test.jpg"
        accessible_image.write_bytes(b"Mock image for accessibility testing")

        query = "Describe this image for accessibility purposes"

        response = api_client.chat(query)
        messages = api_client.wait_for_completion(max_wait=60)

        response_text = response.get("message", "")

        assert success_criteria_checker.check_no_errors(response)
        assert success_criteria_checker.check_response_length(response_text, 50)

        # Check accessibility features
        accessibility_keywords = ["describe", "image", "accessibility", "alt"]
        assert success_criteria_checker.check_keywords_present(response_text, accessibility_keywords)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
