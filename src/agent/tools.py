"""
LangGraph tool definitions wrapping existing automation components.
"""

from typing import List, Optional, Dict, Any
from langchain_core.tools import tool
from pathlib import Path
import logging

# Import existing components
from src.documents import DocumentIndexer, DocumentParser, SemanticSearch
from src.automation import MailComposer, KeynoteComposer, PagesComposer
from src.utils import load_config

logger = logging.getLogger(__name__)
config = load_config()

# Initialize components
indexer = DocumentIndexer(config)
search_engine = SemanticSearch(indexer, config)
parser = DocumentParser(config)
mail_composer = MailComposer(config)
keynote_composer = KeynoteComposer(config)
pages_composer = PagesComposer(config)


@tool
def search_documents(query: str) -> Dict[str, Any]:
    """
    Search for documents using semantic search.

    Args:
        query: Natural language search query

    Returns:
        Dictionary with doc_path, doc_title, relevance_score, and metadata
    """
    logger.info(f"Tool: search_documents(query='{query}')")

    try:
        results = search_engine.search(query, top_k=1)

        if not results:
            return {
                "error": True,
                "error_type": "NotFoundError",
                "error_message": f"No documents found matching query: {query}",
                "retry_possible": True
            }

        # Return top result
        result = results[0]
        return {
            "doc_path": result["file_path"],
            "doc_title": result.get("title", Path(result["file_path"]).name),
            "relevance_score": result.get("score", 0.0),
            "metadata": {
                "file_type": Path(result["file_path"]).suffix[1:],
                "chunk_count": result.get("chunk_count", 1)
            }
        }

    except Exception as e:
        logger.error(f"Error in search_documents: {e}")
        return {
            "error": True,
            "error_type": "SearchError",
            "error_message": str(e),
            "retry_possible": False
        }


@tool
def extract_section(doc_path: str, section: str) -> Dict[str, Any]:
    """
    Extract specific content from a document.

    Args:
        doc_path: Path to document
        section: Section identifier (e.g., 'summary', 'page 5', 'all')

    Returns:
        Dictionary with extracted_text, page_numbers, and word_count
    """
    logger.info(f"Tool: extract_section(doc_path='{doc_path}', section='{section}')")

    try:
        # Parse document
        parsed_doc = parser.parse_document(doc_path)
        if not parsed_doc:
            return {
                "error": True,
                "error_type": "ParseError",
                "error_message": f"Failed to parse document: {doc_path}",
                "retry_possible": False
            }

        text = parsed_doc.get('content', '')

        if section.lower() == "all":
            extracted_text = text
            page_numbers = list(range(1, len(text.split('\f')) + 1))
        elif section.lower().startswith("page "):
            # Extract specific page
            page_num = int(section.split()[1])
            pages = text.split('\f')
            if 0 < page_num <= len(pages):
                extracted_text = pages[page_num - 1]
                page_numbers = [page_num]
            else:
                return {
                    "error": True,
                    "error_type": "ValidationError",
                    "error_message": f"Page {page_num} not found in document",
                    "retry_possible": False
                }
        elif section.lower().startswith("pages "):
            # Extract page range or pages containing keyword
            rest_of_section = section[6:].strip()  # Remove "pages "

            # Check if it's a page range (e.g., "pages 1-5")
            if '-' in rest_of_section and rest_of_section.replace('-', '').isdigit():
                start, end = map(int, rest_of_section.split('-'))
                pages = text.split('\f')
                extracted_text = '\f'.join(pages[start-1:end])
                page_numbers = list(range(start, end + 1))
            # Check if it's "pages containing 'keyword'"
            elif rest_of_section.startswith("containing"):
                # Extract keyword from quotes or after "containing"
                keyword = rest_of_section.replace("containing", "").strip()
                keyword = keyword.strip("'\"")  # Remove quotes

                pages = text.split('\f')
                matching_pages = [
                    (i + 1, page) for i, page in enumerate(pages)
                    if keyword.lower() in page.lower()
                ]

                if matching_pages:
                    extracted_text = '\n\n'.join([page for _, page in matching_pages])
                    page_numbers = [page_num for page_num, _ in matching_pages]
                else:
                    # No matches found
                    extracted_text = text
                    page_numbers = list(range(1, len(pages) + 1))
            else:
                return {
                    "error": True,
                    "error_type": "ValidationError",
                    "error_message": f"Invalid page specification: {rest_of_section}",
                    "retry_possible": False
                }
        else:
            # Use semantic search to find most relevant pages
            logger.info(f"Using semantic search for section: {section}")

            try:
                # Search for pages semantically matching the section query
                page_results = search_engine.search_pages_in_document(
                    query=section,
                    doc_path=doc_path,
                    top_k=3  # Get top 3 most relevant pages
                )

                if page_results:
                    # Use the most relevant page(s)
                    page_numbers = [result['page_number'] for result in page_results]
                    similarities = [f"{r['similarity']:.3f}" for r in page_results]
                    logger.info(f"Semantic search found pages: {page_numbers}")
                    logger.info(f"Similarities: {similarities}")

                    # Extract text from found pages
                    pages = text.split('\f')
                    extracted_text = '\n\n'.join([
                        pages[page_num - 1] for page_num in page_numbers
                        if 0 < page_num <= len(pages)
                    ])
                else:
                    # Fallback to keyword search
                    logger.info("Semantic search found no results, falling back to keyword search")
                    keyword = section.lower()
                    pages = text.split('\f')
                    matching_pages = [
                        (i + 1, page) for i, page in enumerate(pages)
                        if keyword in page.lower()
                    ]

                    if matching_pages:
                        extracted_text = '\n\n'.join([page for _, page in matching_pages])
                        page_numbers = [page_num for page_num, _ in matching_pages]
                    else:
                        # Last resort: return full text
                        extracted_text = text
                        page_numbers = list(range(1, len(pages) + 1))

            except Exception as e:
                logger.error(f"Error in semantic page search: {e}")
                # Fallback to keyword search on error
                keyword = section.lower()
                pages = text.split('\f')
                matching_pages = [
                    (i + 1, page) for i, page in enumerate(pages)
                    if keyword in page.lower()
                ]

                if matching_pages:
                    extracted_text = '\n\n'.join([page for _, page in matching_pages])
                    page_numbers = [page_num for page_num, _ in matching_pages]
                else:
                    extracted_text = text
                    page_numbers = list(range(1, len(pages) + 1))

        return {
            "extracted_text": extracted_text,
            "page_numbers": page_numbers,
            "word_count": len(extracted_text.split())
        }

    except Exception as e:
        logger.error(f"Error in extract_section: {e}")
        return {
            "error": True,
            "error_type": "ExtractionError",
            "error_message": str(e),
            "retry_possible": False
        }


@tool
def take_screenshot(doc_path: str, pages: List[int]) -> Dict[str, Any]:
    """
    Capture page images from a document.

    Args:
        doc_path: Path to document
        pages: List of page numbers to capture

    Returns:
        Dictionary with screenshot_paths and pages_captured
    """
    logger.info(f"Tool: take_screenshot(doc_path='{doc_path}', pages={pages})")

    try:
        import fitz  # PyMuPDF
        import tempfile

        doc = fitz.open(doc_path)
        screenshot_paths = []
        pages_captured = []

        for page_num in pages:
            if 0 < page_num <= len(doc):
                page = doc[page_num - 1]
                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))  # 2x zoom

                # Save to temp file
                temp_file = tempfile.NamedTemporaryFile(
                    delete=False, suffix='.png', prefix=f'page{page_num}_'
                )
                pix.save(temp_file.name)
                screenshot_paths.append(temp_file.name)
                pages_captured.append(page_num)
                logger.info(f"Screenshot saved: {temp_file.name}")
            else:
                logger.warning(f"Page {page_num} out of range (total: {len(doc)})")

        doc.close()

        return {
            "screenshot_paths": screenshot_paths,
            "pages_captured": pages_captured
        }

    except Exception as e:
        logger.error(f"Error in take_screenshot: {e}")
        return {
            "error": True,
            "error_type": "ScreenshotError",
            "error_message": str(e),
            "retry_possible": False
        }


@tool
def compose_email(
    subject: str,
    body: str,
    recipient: Optional[str] = None,
    attachments: Optional[List[str]] = None,
    send: bool = False
) -> Dict[str, Any]:
    """
    Create and optionally send an email via Mail.app.

    Args:
        subject: Email subject
        body: Email body (supports markdown)
        recipient: Email address (None = draft only)
        attachments: List of file paths to attach
        send: If True, send immediately; if False, open draft

    Returns:
        Dictionary with status ('sent' or 'draft')
    """
    logger.info(f"Tool: compose_email(subject='{subject}', recipient='{recipient}', send={send})")

    try:
        success = mail_composer.compose_email(
            subject=subject,
            body=body,
            recipient=recipient,
            attachment_paths=attachments,
            send_immediately=send
        )

        if success:
            return {
                "status": "sent" if send else "draft",
                "message": f"Email {'sent' if send else 'drafted'} successfully"
            }
        else:
            return {
                "error": True,
                "error_type": "MailError",
                "error_message": "Failed to compose email",
                "retry_possible": True
            }

    except Exception as e:
        logger.error(f"Error in compose_email: {e}")
        return {
            "error": True,
            "error_type": "MailError",
            "error_message": str(e),
            "retry_possible": False
        }


@tool
def create_keynote(
    title: str,
    content: str,
    output_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Generate a Keynote presentation from content.

    Args:
        title: Presentation title
        content: Source content to transform into slides
        output_path: Save location (None = default)

    Returns:
        Dictionary with keynote_path and slide_count
    """
    logger.info(f"Tool: create_keynote(title='{title}')")

    try:
        result = keynote_composer.create_presentation(
            title=title,
            content=content,
            output_path=output_path
        )

        if result:
            return {
                "keynote_path": result.get("file_path", "Unknown"),
                "slide_count": result.get("slide_count", 0),
                "message": "Keynote presentation created successfully"
            }
        else:
            return {
                "error": True,
                "error_type": "KeynoteError",
                "error_message": "Failed to create Keynote presentation",
                "retry_possible": True
            }

    except Exception as e:
        logger.error(f"Error in create_keynote: {e}")
        return {
            "error": True,
            "error_type": "KeynoteError",
            "error_message": str(e),
            "retry_possible": False
        }


@tool
def create_pages_doc(
    title: str,
    content: str,
    output_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Generate a Pages document from content.

    Args:
        title: Document title
        content: Source content to format
        output_path: Save location (None = default)

    Returns:
        Dictionary with pages_path and page_count
    """
    logger.info(f"Tool: create_pages_doc(title='{title}')")

    try:
        result = pages_composer.create_document(
            title=title,
            content=content,
            output_path=output_path
        )

        if result:
            return {
                "pages_path": result.get("file_path", "Unknown"),
                "message": "Pages document created successfully"
            }
        else:
            return {
                "error": True,
                "error_type": "PagesError",
                "error_message": "Failed to create Pages document",
                "retry_possible": True
            }

    except Exception as e:
        logger.error(f"Error in create_pages_doc: {e}")
        return {
            "error": True,
            "error_type": "PagesError",
            "error_message": str(e),
            "retry_possible": False
        }


# Tool registry
ALL_TOOLS = [
    search_documents,
    extract_section,
    take_screenshot,
    compose_email,
    create_keynote,
    create_pages_doc,
]
