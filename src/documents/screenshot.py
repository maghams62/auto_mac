"""
Document screenshot module for rendering pages to images.
"""

import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
import fitz  # PyMuPDF
from PIL import Image
import io


logger = logging.getLogger(__name__)


class DocumentScreenshot:
    """
    Captures screenshots of document pages.
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the screenshot module.

        Args:
            config: Configuration dictionary
        """
        self.config = config
        self.dpi = 150  # Resolution for screenshots

    def screenshot_pages(
        self,
        file_path: str,
        page_numbers: Optional[List[int]] = None,
        search_text: Optional[str] = None,
        output_dir: str = "data/screenshots"
    ) -> List[str]:
        """
        Take screenshots of document pages.

        Args:
            file_path: Path to the document
            page_numbers: Specific page numbers to screenshot (1-indexed)
            search_text: Text to search for; screenshots pages containing this text
            output_dir: Directory to save screenshots

        Returns:
            List of paths to saved screenshot images
        """
        file_path = Path(file_path)

        if not file_path.exists():
            logger.error(f"File not found: {file_path}")
            return []

        file_ext = file_path.suffix.lower()

        try:
            if file_ext == '.pdf':
                return self._screenshot_pdf(
                    file_path, page_numbers, search_text, output_dir
                )
            elif file_ext == '.docx':
                # For DOCX, we'd need to convert to PDF first or use other methods
                logger.warning("DOCX screenshot not yet implemented")
                return []
            else:
                logger.warning(f"Unsupported file type for screenshots: {file_ext}")
                return []

        except Exception as e:
            logger.error(f"Error taking screenshots: {e}")
            return []

    def _screenshot_pdf(
        self,
        file_path: Path,
        page_numbers: Optional[List[int]],
        search_text: Optional[str],
        output_dir: str
    ) -> List[str]:
        """
        Screenshot PDF pages using PyMuPDF.

        Args:
            file_path: Path to PDF
            page_numbers: Page numbers to screenshot (1-indexed)
            search_text: Text to search for in pages
            output_dir: Output directory

        Returns:
            List of screenshot file paths
        """
        screenshots = []
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        # Open PDF
        doc = fitz.open(str(file_path))

        try:
            # Determine which pages to screenshot
            if page_numbers:
                # Convert 1-indexed to 0-indexed
                pages_to_capture = [p - 1 for p in page_numbers if 0 < p <= len(doc)]
            elif search_text:
                # Search for text in all pages
                pages_to_capture = []
                search_lower = search_text.lower()

                for page_num in range(len(doc)):
                    page = doc[page_num]
                    text = page.get_text().lower()

                    if search_lower in text:
                        pages_to_capture.append(page_num)
                        logger.info(f"Found '{search_text}' on page {page_num + 1}")
            else:
                # Screenshot all pages (use with caution!)
                pages_to_capture = list(range(len(doc)))

            logger.info(f"Capturing {len(pages_to_capture)} pages")

            # Capture each page
            for page_idx in pages_to_capture:
                page = doc[page_idx]

                # Render page to pixmap (image)
                mat = fitz.Matrix(self.dpi / 72, self.dpi / 72)  # Scale for DPI
                pix = page.get_pixmap(matrix=mat)

                # Convert to PIL Image
                img_data = pix.tobytes("png")
                img = Image.open(io.BytesIO(img_data))

                # Save screenshot
                filename = f"{file_path.stem}_page_{page_idx + 1}.png"
                output_file = output_path / filename
                img.save(output_file, "PNG")

                screenshots.append(str(output_file))
                logger.info(f"Saved screenshot: {output_file}")

        finally:
            doc.close()

        return screenshots

    def screenshot_single_page(
        self,
        file_path: str,
        page_number: int,
        output_path: Optional[str] = None
    ) -> Optional[str]:
        """
        Take a screenshot of a single page.

        Args:
            file_path: Path to document
            page_number: Page number (1-indexed)
            output_path: Custom output path (optional)

        Returns:
            Path to screenshot or None
        """
        screenshots = self.screenshot_pages(
            file_path=file_path,
            page_numbers=[page_number],
            search_text=None
        )

        if screenshots and output_path:
            # Move to custom path
            import shutil
            shutil.move(screenshots[0], output_path)
            return output_path

        return screenshots[0] if screenshots else None

    def get_page_count(self, file_path: str) -> int:
        """
        Get the total number of pages in a document.

        Args:
            file_path: Path to document

        Returns:
            Number of pages
        """
        file_path = Path(file_path)
        file_ext = file_path.suffix.lower()

        try:
            if file_ext == '.pdf':
                doc = fitz.open(str(file_path))
                count = len(doc)
                doc.close()
                return count
            else:
                return 0
        except:
            return 0
