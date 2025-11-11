"""
Convert HTML report to PDF using reportlab (Mac-native Python).
"""

from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from bs4 import BeautifulSoup
import re
from pathlib import Path
import logging
import base64
import tempfile

logger = logging.getLogger(__name__)


def html_to_pdf(html_path: str, pdf_path: str) -> bool:
    """
    Convert HTML report to PDF using reportlab.

    Args:
        html_path: Path to HTML file
        pdf_path: Path for PDF output

    Returns:
        True if successful
    """
    try:
        # Read HTML
        with open(html_path, 'r', encoding='utf-8') as f:
            html_content = f.read()

        # Parse HTML
        soup = BeautifulSoup(html_content, 'html.parser')

        # Create PDF
        doc = SimpleDocTemplate(
            pdf_path,
            pagesize=letter,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=18,
        )

        # Styles
        styles = getSampleStyleSheet()

        # Custom styles
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            textColor='#1a1a1a',
            spaceAfter=30,
            alignment=TA_CENTER
        )

        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontSize=16,
            textColor='#333',
            spaceAfter=12,
            spaceBefore=20
        )

        body_style = ParagraphStyle(
            'CustomBody',
            parent=styles['BodyText'],
            fontSize=11,
            leading=16,
            alignment=TA_LEFT
        )

        # Build document content
        story = []
        temp_files = []  # Keep track of temp files to clean up later

        # Extract title
        title_tag = soup.find('h1')
        if title_tag:
            title = title_tag.get_text()
            story.append(Paragraph(title, title_style))
            story.append(Spacer(1, 0.2*inch))

        # Extract sections
        sections = soup.find_all('div', class_='section')

        for section in sections:
            # Get heading
            h2 = section.find('h2')
            if h2:
                heading_text = h2.get_text()
                story.append(Paragraph(heading_text, heading_style))
                story.append(Spacer(1, 0.1*inch))

            # Get content (paragraphs)
            paragraphs = section.find_all('p')
            for p in paragraphs:
                # Get text and convert <br> to newlines
                text = p.decode_contents()
                text = text.replace('<br>', '<br/>')
                text = text.replace('<br/>', '\n')

                # Remove any remaining HTML tags
                text = re.sub(r'<[^>]+>', '', text)

                if text.strip():
                    story.append(Paragraph(text, body_style))
                    story.append(Spacer(1, 0.1*inch))

            # Check for images
            images = section.find_all('img')
            for img in images:
                src = img.get('src', '')

                # Handle base64 images
                if src.startswith('data:image'):
                    try:
                        # Extract base64 data
                        match = re.search(r'data:image/(\w+);base64,(.+)', src)
                        if match:
                            img_type = match.group(1)
                            img_data = match.group(2)

                            # Decode base64
                            decoded_data = base64.b64decode(img_data)

                            # Save to temp file
                            tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=f'.{img_type}')
                            tmp_file.write(decoded_data)
                            tmp_file.close()
                            tmp_path = tmp_file.name
                            temp_files.append(tmp_path)  # Store for cleanup later

                            # Add image to PDF
                            try:
                                img_obj = Image(tmp_path, width=6*inch, height=4*inch, kind='proportional')
                                story.append(Spacer(1, 0.2*inch))
                                story.append(img_obj)
                                story.append(Spacer(1, 0.2*inch))
                            except Exception as e:
                                logger.warning(f"Could not add image to PDF: {e}")
                    except Exception as e:
                        logger.warning(f"Could not process base64 image: {e}")

        # Add timestamp
        timestamp_div = soup.find('div', class_='timestamp')
        if timestamp_div:
            timestamp_text = timestamp_div.get_text()
            story.append(Spacer(1, 0.5*inch))
            story.append(Paragraph(timestamp_text, styles['Italic']))

        # Build PDF
        doc.build(story)
        logger.info(f"[HTML2PDF] PDF created: {pdf_path}")

        # Clean up temp files
        for tmp_path in temp_files:
            try:
                Path(tmp_path).unlink()
            except:
                pass

        return True

    except Exception as e:
        logger.error(f"[HTML2PDF] Error converting HTML to PDF: {e}")
        return False


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 3:
        print("Usage: python html_to_pdf.py <input.html> <output.pdf>")
        sys.exit(1)

    html_path = sys.argv[1]
    pdf_path = sys.argv[2]

    logging.basicConfig(level=logging.INFO)

    success = html_to_pdf(html_path, pdf_path)

    if success:
        print(f"✅ PDF created: {pdf_path}")
        sys.exit(0)
    else:
        print(f"❌ Failed to create PDF")
        sys.exit(1)
