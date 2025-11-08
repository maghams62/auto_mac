"""
Report Generator - Create reports and convert to PDF using macOS native tools.

Uses TextEdit for document creation and macOS PDF printing for conversion.
"""

import subprocess
import logging
import time
from pathlib import Path
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)


class ReportGenerator:
    """
    Generate reports using TextEdit and convert to PDF.

    This uses macOS native tools:
    - TextEdit for RTF document creation
    - macOS PDF printing for conversion
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize report generator.

        Args:
            config: Configuration dictionary
        """
        self.config = config
        self.reports_dir = Path("data/reports")
        self.reports_dir.mkdir(parents=True, exist_ok=True)

    def create_report(
        self,
        title: str,
        content: str,
        sections: Optional[List[Dict[str, str]]] = None,
        image_paths: Optional[List[str]] = None,
        export_pdf: bool = True,
        output_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a report and optionally export to PDF with embedded images.

        Args:
            title: Report title
            content: Main content (if sections not provided)
            sections: Optional list of sections with 'heading' and 'content' keys
            image_paths: Optional list of image file paths to embed in report
            export_pdf: Whether to export as PDF (default: True)
            output_name: Custom output filename (without extension)

        Returns:
            Dictionary with rtf_path, pdf_path (if exported), and success status

        Examples:
            # Simple report
            create_report(
                title="Stock Analysis Report",
                content="Microsoft stock is trading at $495..."
            )

            # Report with sections and images
            create_report(
                title="Stock Analysis",
                content="",
                sections=[
                    {"heading": "Executive Summary", "content": "..."},
                    {"heading": "Chart", "content": "[See image below]"}
                ],
                image_paths=["data/screenshots/msft_chart.png"]
            )
        """
        logger.info(f"[REPORT GENERATOR] Creating report: {title}")

        try:
            # Generate filename
            if not output_name:
                timestamp = time.strftime("%Y%m%d_%H%M%S")
                safe_title = "".join(c if c.isalnum() or c in (' ', '_') else '_' for c in title)
                safe_title = safe_title.replace(' ', '_')[:50]
                output_name = f"{safe_title}_{timestamp}"

            rtf_path = self.reports_dir / f"{output_name}.rtf"
            html_path = self.reports_dir / f"{output_name}.html"

            # If images are provided, use HTML-based report for better image support
            if image_paths:
                success = self._create_html_document(
                    title=title,
                    content=content,
                    sections=sections,
                    image_paths=image_paths,
                    output_path=str(html_path)
                )

                if not success:
                    return {
                        "error": True,
                        "error_type": "ReportCreationError",
                        "error_message": "Failed to create HTML report",
                        "retry_possible": True
                    }

                result = {
                    "success": True,
                    "html_path": str(html_path),
                    "title": title,
                    "message": f"Report created: {html_path.name}"
                }

                # Export to PDF
                if export_pdf:
                    pdf_path = self.reports_dir / f"{output_name}.pdf"
                    pdf_success = self._convert_html_to_pdf(str(html_path), str(pdf_path))

                    if pdf_success:
                        result["pdf_path"] = str(pdf_path)
                        result["message"] = f"Report created: {pdf_path.name}"
                        logger.info(f"[REPORT GENERATOR] PDF exported: {pdf_path}")
                    else:
                        result["pdf_warning"] = "PDF conversion failed, HTML available"
                        logger.warning("[REPORT GENERATOR] PDF conversion failed")

            else:
                # Use RTF for text-only reports
                success = self._create_rtf_document(
                    title=title,
                    content=content,
                    sections=sections,
                    output_path=str(rtf_path)
                )

                if not success:
                    return {
                        "error": True,
                        "error_type": "ReportCreationError",
                        "error_message": "Failed to create RTF report",
                        "retry_possible": True
                    }

                result = {
                    "success": True,
                    "rtf_path": str(rtf_path),
                    "title": title,
                    "message": f"Report created: {rtf_path.name}"
                }

                # Export to PDF if requested
                if export_pdf:
                    pdf_path = self.reports_dir / f"{output_name}.pdf"
                    pdf_success = self._convert_to_pdf(str(rtf_path), str(pdf_path))

                    if pdf_success:
                        result["pdf_path"] = str(pdf_path)
                        result["message"] = f"Report created: {rtf_path.name} and {pdf_path.name}"
                        logger.info(f"[REPORT GENERATOR] PDF exported: {pdf_path}")
                    else:
                        result["pdf_warning"] = "PDF conversion failed, RTF available"
                        logger.warning("[REPORT GENERATOR] PDF conversion failed")

            return result

        except Exception as e:
            logger.error(f"[REPORT GENERATOR] Error creating report: {e}")
            return {
                "error": True,
                "error_type": "ReportGenerationError",
                "error_message": str(e),
                "retry_possible": False
            }

    def _create_rtf_document(
        self,
        title: str,
        content: str,
        sections: Optional[List[Dict[str, str]]],
        output_path: str
    ) -> bool:
        """
        Create RTF document using TextEdit via AppleScript.

        Args:
            title: Document title
            content: Main content
            sections: Optional sections
            output_path: Where to save the RTF

        Returns:
            True if successful
        """
        try:
            # Build document content
            doc_content = self._build_document_content(title, content, sections)

            # Create RTF using AppleScript + TextEdit
            applescript = f'''
            set documentContent to "{self._escape_applescript(doc_content)}"
            set outputPath to "{output_path}"

            tell application "TextEdit"
                activate

                -- Create new document
                make new document

                -- Set content
                set text of document 1 to documentContent

                -- Format as RTF and save
                tell document 1
                    -- Wait a moment for document to be ready
                    delay 0.5

                    -- Save as RTF
                    save in POSIX file outputPath
                end tell

                -- Close the document
                close document 1 saving no

            end tell
            '''

            result = subprocess.run(
                ["osascript", "-e", applescript],
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode == 0:
                logger.info(f"[REPORT GENERATOR] RTF created: {output_path}")
                return True
            else:
                logger.error(f"[REPORT GENERATOR] AppleScript error: {result.stderr}")
                return False

        except Exception as e:
            logger.error(f"[REPORT GENERATOR] Error creating RTF: {e}")
            return False

    def _build_document_content(
        self,
        title: str,
        content: str,
        sections: Optional[List[Dict[str, str]]]
    ) -> str:
        """
        Build the document content with formatting.

        Args:
            title: Document title
            content: Main content
            sections: Optional sections

        Returns:
            Formatted document content
        """
        doc = []

        # Add title
        doc.append(title.upper())
        doc.append("=" * len(title))
        doc.append("")

        # Add sections or content
        if sections:
            for section in sections:
                heading = section.get("heading") or section.get("title") or ""
                section_content = section.get("content") or section.get("text") or ""

                if heading:
                    doc.append("")
                    doc.append(heading)
                    doc.append("-" * len(heading))
                    doc.append("")

                if section_content:
                    doc.append(section_content)
                    doc.append("")
        else:
            doc.append(content)

        # Add timestamp
        doc.append("")
        doc.append("---")
        doc.append(f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}")

        return "\\n".join(doc)

    def _escape_applescript(self, text: str) -> str:
        """
        Escape text for AppleScript.

        Args:
            text: Text to escape

        Returns:
            Escaped text
        """
        # Replace backslash first
        text = text.replace('\\', '\\\\')
        # Replace quotes
        text = text.replace('"', '\\"')
        # Newlines are already \\n from build_document_content
        return text

    def _create_html_document(
        self,
        title: str,
        content: str,
        sections: Optional[List[Dict[str, str]]],
        image_paths: List[str],
        output_path: str
    ) -> bool:
        """
        Create HTML document with embedded images.

        Args:
            title: Document title
            content: Main content
            sections: Optional sections
            image_paths: List of image file paths to embed
            output_path: Where to save the HTML

        Returns:
            True if successful
        """
        try:
            import base64
            from pathlib import Path

            # Build HTML content
            html_parts = []
            html_parts.append('<!DOCTYPE html>')
            html_parts.append('<html>')
            html_parts.append('<head>')
            html_parts.append('<meta charset="UTF-8">')
            html_parts.append(f'<title>{title}</title>')
            html_parts.append('<style>')
            html_parts.append('''
                body {
                    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
                    max-width: 900px;
                    margin: 40px auto;
                    padding: 20px;
                    line-height: 1.6;
                    color: #333;
                }
                h1 {
                    color: #1a1a1a;
                    border-bottom: 3px solid #007aff;
                    padding-bottom: 10px;
                    margin-bottom: 30px;
                }
                h2 {
                    color: #333;
                    margin-top: 30px;
                    margin-bottom: 15px;
                    border-bottom: 1px solid #ddd;
                    padding-bottom: 5px;
                }
                p {
                    margin: 10px 0;
                }
                img {
                    max-width: 100%;
                    height: auto;
                    margin: 20px 0;
                    border: 1px solid #ddd;
                    border-radius: 4px;
                    display: block;
                }
                .timestamp {
                    color: #888;
                    font-size: 0.9em;
                    margin-top: 40px;
                    padding-top: 20px;
                    border-top: 1px solid #ddd;
                }
                .section {
                    margin-bottom: 30px;
                }
            ''')
            html_parts.append('</style>')
            html_parts.append('</head>')
            html_parts.append('<body>')

            # Add title
            html_parts.append(f'<h1>{title}</h1>')

            # Add sections or content
            if sections:
                for section in sections:
                    heading = section.get("heading") or section.get("title") or ""
                    section_content = section.get("content") or section.get("text") or ""

                    html_parts.append('<div class="section">')
                    if heading:
                        html_parts.append(f'<h2>{heading}</h2>')
                    if section_content:
                        # Convert newlines to <br> tags
                        formatted_content = section_content.replace('\n', '<br>')
                        html_parts.append(f'<p>{formatted_content}</p>')
                    html_parts.append('</div>')
            elif content:
                formatted_content = content.replace('\n', '<br>')
                html_parts.append(f'<p>{formatted_content}</p>')

            # Add images with base64 encoding
            if image_paths:
                html_parts.append('<div class="section">')
                html_parts.append('<h2>Charts & Visualizations</h2>')
                for img_path in image_paths:
                    img_file = Path(img_path)
                    if img_file.exists():
                        try:
                            with open(img_file, 'rb') as f:
                                img_data = base64.b64encode(f.read()).decode('utf-8')
                            # Determine image type
                            ext = img_file.suffix.lower()
                            mime_type = 'image/png' if ext == '.png' else 'image/jpeg'
                            html_parts.append(f'<img src="data:{mime_type};base64,{img_data}" alt="Stock Chart"/>')
                        except Exception as e:
                            logger.warning(f"Failed to embed image {img_path}: {e}")
                            html_parts.append(f'<p><em>Image not found: {img_file.name}</em></p>')
                    else:
                        html_parts.append(f'<p><em>Image not found: {img_file.name}</em></p>')
                html_parts.append('</div>')

            # Add timestamp
            html_parts.append('<div class="timestamp">')
            html_parts.append(f'Generated: {time.strftime("%Y-%m-%d %H:%M:%S")}')
            html_parts.append('</div>')

            html_parts.append('</body>')
            html_parts.append('</html>')

            # Write HTML file
            html_content = '\n'.join(html_parts)
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(html_content)

            logger.info(f"[REPORT GENERATOR] HTML created: {output_path}")
            return True

        except Exception as e:
            logger.error(f"[REPORT GENERATOR] Error creating HTML: {e}")
            return False

    def _convert_html_to_pdf(self, html_path: str, pdf_path: str) -> bool:
        """
        Convert HTML to PDF using macOS cupsfilter.

        Args:
            html_path: Path to HTML file
            pdf_path: Path for PDF output

        Returns:
            True if successful
        """
        try:
            # Convert HTML to PDF using cupsfilter
            result = subprocess.run(
                ["cupsfilter", html_path],
                capture_output=True,
                timeout=30
            )

            if result.returncode == 0:
                # Write PDF output
                with open(pdf_path, 'wb') as f:
                    f.write(result.stdout)
                logger.info(f"[REPORT GENERATOR] PDF created from HTML: {pdf_path}")
                return True
            else:
                logger.error(f"cupsfilter failed: {result.stderr}")
                return False

        except Exception as e:
            logger.error(f"[REPORT GENERATOR] HTML to PDF conversion error: {e}")
            return False

    def _convert_to_pdf(self, rtf_path: str, pdf_path: str) -> bool:
        """
        Convert RTF to PDF using macOS's textutil and cupsfilter.

        Args:
            rtf_path: Path to RTF file
            pdf_path: Path for PDF output

        Returns:
            True if successful
        """
        try:
            # Method 1: Use textutil to convert RTF to HTML, then use cupsfilter for PDF
            # This is more reliable than trying to use TextEdit's PDF export

            # First, convert RTF to plain text (easier to convert to PDF)
            import tempfile
            temp_html = tempfile.NamedTemporaryFile(suffix='.html', delete=False)
            temp_html_path = temp_html.name
            temp_html.close()

            try:
                # Convert RTF to HTML using textutil
                result = subprocess.run(
                    ["textutil", "-convert", "html", rtf_path, "-output", temp_html_path],
                    capture_output=True,
                    text=True,
                    timeout=10
                )

                if result.returncode != 0:
                    logger.error(f"textutil conversion failed: {result.stderr}")
                    return False

                # Convert HTML to PDF using cupsfilter
                result = subprocess.run(
                    ["cupsfilter", temp_html_path],
                    capture_output=True,
                    timeout=10
                )

                if result.returncode == 0:
                    # Write PDF output
                    with open(pdf_path, 'wb') as f:
                        f.write(result.stdout)
                    logger.info(f"[REPORT GENERATOR] PDF created: {pdf_path}")
                    return True
                else:
                    logger.error(f"cupsfilter failed: {result.stderr}")
                    return False

            finally:
                # Clean up temp file
                import os
                try:
                    os.unlink(temp_html_path)
                except:
                    pass

        except Exception as e:
            logger.error(f"[REPORT GENERATOR] PDF conversion error: {e}")
            return False


def test_report_generator():
    """Test the report generator."""
    from ..utils import load_config

    config = load_config()
    generator = ReportGenerator(config)

    print("=" * 80)
    print("Testing Report Generator")
    print("=" * 80)

    # Test 1: Simple report
    print("\nTest 1: Simple report with PDF export")
    result = generator.create_report(
        title="Test Report - Stock Analysis",
        content="""This is a test report for stock analysis.

Microsoft Corporation (MSFT) is currently trading at $495.00, down 0.45% today.

Key Findings:
- Stock price is within normal range
- Volume is typical for this time of day
- No major news events affecting price

Recommendation: Hold current position.""",
        export_pdf=True
    )

    if result.get("error"):
        print(f"❌ Error: {result['error_message']}")
        return False

    print(f"✅ Report created!")
    print(f"   RTF: {result['rtf_path']}")
    if result.get("pdf_path"):
        print(f"   PDF: {result['pdf_path']}")

    # Test 2: Report with sections
    print("\nTest 2: Report with sections")
    result = generator.create_report(
        title="Q4 Stock Performance Report",
        content="",
        sections=[
            {
                "heading": "Executive Summary",
                "content": "Stock performance was strong in Q4 with gains across all sectors."
            },
            {
                "heading": "Key Metrics",
                "content": "- Revenue: $50B\n- Profit Margin: 25%\n- Market Cap: $2.5T"
            },
            {
                "heading": "Outlook",
                "content": "Positive outlook for Q1 2025 with continued growth expected."
            }
        ],
        export_pdf=True
    )

    if result.get("error"):
        print(f"❌ Error: {result['error_message']}")
        return False

    print(f"✅ Sectioned report created!")
    print(f"   RTF: {result['rtf_path']}")
    if result.get("pdf_path"):
        print(f"   PDF: {result['pdf_path']}")

    return True


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))

    success = test_report_generator()
    sys.exit(0 if success else 1)
