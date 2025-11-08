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
def search_documents(query: str, user_request: str = None) -> Dict[str, Any]:
    """
    Search for documents using semantic search with LLM-determined parameters.

    Args:
        query: Natural language search query
        user_request: Original user request for context (optional)

    Returns:
        Dictionary with doc_path, doc_title, relevance_score, and metadata
    """
    logger.info(f"Tool: search_documents(query='{query}')")

    try:
        # Use LLM to determine optimal search parameters (NO hardcoded top_k!)
        from .parameter_resolver import ParameterResolver
        from ..utils import load_config

        config = load_config()
        resolver = ParameterResolver(config)

        search_params = resolver.resolve_search_parameters(
            query=query,
            context={'user_request': user_request or query, 'previous_steps': []}
        )

        logger.info(f"LLM-determined search params: {search_params}")

        results = search_engine.search(query, top_k=search_params.get('top_k', 1))

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
    Extract specific content from a document using LLM-based interpretation.

    Args:
        doc_path: Path to document
        section: Section identifier (e.g., 'last page', 'first 3 pages', 'chorus', 'all')

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
        pages = text.split('\f')

        # Get document info for LLM interpretation
        import os
        document_info = {
            'page_count': len(pages),
            'title': os.path.basename(doc_path)
        }

        # Use LLM-based section interpreter (no hardcoded patterns!)
        from .section_interpreter import SectionInterpreter
        from ..utils import load_config

        config = load_config()
        interpreter = SectionInterpreter(config)

        # Let LLM interpret what the user wants
        interpretation = interpreter.interpret_section_request(
            section_query=section,
            document_info=document_info
        )

        logger.info(f"LLM interpretation: strategy={interpretation.get('strategy')}, reasoning={interpretation.get('reasoning')}")

        # Apply the interpretation
        result = interpreter.apply_interpretation(
            interpretation=interpretation,
            document_pages=pages,
            search_engine=search_engine
        )

        # If result indicates we should use semantic search, do it
        if result.get('use_semantic_search'):
            search_query = result.get('search_query')
            logger.info(f"Using semantic search for: {search_query}")

            try:
                # Use LLM to determine how many pages to return (NO hardcoded top_k!)
                from .parameter_resolver import ParameterResolver

                resolver = ParameterResolver(config)
                page_params = resolver.resolve_page_selection_parameters(
                    total_pages=len(pages),
                    user_intent=section,
                    context={'query': search_query}
                )

                logger.info(f"LLM-determined page params: max={page_params.get('max_pages')}")

                page_results = search_engine.search_pages_in_document(
                    query=search_query,
                    doc_path=doc_path,
                    top_k=page_params.get('max_pages', 1)
                )

                if page_results:
                    page_numbers = [r['page_number'] for r in page_results]
                    logger.info(f"Semantic search found pages: {page_numbers}")

                    extracted_text = '\n\n'.join([
                        pages[page_num - 1] for page_num in page_numbers
                        if 0 < page_num <= len(pages)
                    ])

                    return {
                        "extracted_text": extracted_text,
                        "page_numbers": page_numbers,
                        "word_count": len(extracted_text.split())
                    }
                else:
                    # Fallback
                    return {
                        "extracted_text": text,
                        "page_numbers": list(range(1, len(pages) + 1)),
                        "word_count": len(text.split())
                    }

            except Exception as e:
                logger.error(f"Semantic search error: {e}")
                return {
                    "extracted_text": text,
                    "page_numbers": list(range(1, len(pages) + 1)),
                    "word_count": len(text.split())
                }

        # Return the result from interpretation
        return result

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
        # Convert content string to slides format
        # If content is short, create a single slide
        slides = []

        # Split content into paragraphs or use as single slide
        if len(content) < 500:
            # Short content - single slide
            slides.append({
                "title": "Overview",
                "content": content
            })
        else:
            # Longer content - split into multiple slides
            # Simple split by double newlines or every ~300 chars
            paragraphs = content.split('\n\n')
            for i, para in enumerate(paragraphs[:10], 1):  # Max 10 slides
                if para.strip():
                    slides.append({
                        "title": f"Slide {i}",
                        "content": para.strip()
                    })

        # Call the actual keynote composer with slides
        success = keynote_composer.create_presentation(
            title=title,
            slides=slides,
            output_path=output_path
        )

        if success:
            # Construct the path if not provided
            if output_path:
                final_path = output_path
            else:
                import os
                final_path = os.path.expanduser(f"~/Documents/{title}.key")

            return {
                "keynote_path": final_path,
                "slide_count": len(slides) + 1,  # +1 for title slide
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
def create_keynote_with_images(
    title: str,
    image_paths: List[str],
    output_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Create a Keynote presentation with images (screenshots).

    Args:
        title: Presentation title
        image_paths: List of image file paths to add as slides
        output_path: Save location (None = default)

    Returns:
        Dictionary with keynote_path and slide_count
    """
    logger.info(f"Tool: create_keynote_with_images(title='{title}', images={len(image_paths)})")

    try:
        # Create slides with images
        slides = []
        for i, image_path in enumerate(image_paths, 1):
            slides.append({
                "title": f"Image {i}",
                "image_path": image_path
            })

        # Determine output path - generate default if not provided
        if not output_path:
            import os
            output_path = os.path.expanduser(f"~/Documents/{title}.key")

        # Call the actual keynote composer with slides
        success = keynote_composer.create_presentation(
            title=title,
            slides=slides,
            output_path=output_path
        )

        if success:
            # Verify the file actually exists
            import os
            if os.path.exists(output_path):
                return {
                    "keynote_path": output_path,
                    "slide_count": len(slides) + 1,  # +1 for title slide
                    "message": f"Keynote presentation created with {len(slides)} image slides"
                }
            else:
                logger.error(f"Keynote reported success but file not found: {output_path}")
                return {
                    "error": True,
                    "error_type": "KeynoteError",
                    "error_message": f"Keynote file not saved to {output_path}",
                    "retry_possible": False
                }
        else:
            return {
                "error": True,
                "error_type": "KeynoteError",
                "error_message": "Failed to create Keynote presentation with images",
                "retry_possible": True
            }

    except Exception as e:
        logger.error(f"Error in create_keynote_with_images: {e}")
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


@tool
def organize_files(
    category: str,
    target_folder: str,
    move_files: bool = True
) -> Dict[str, Any]:
    """
    Organize files into a folder based on category using LLM-driven file selection.

    This tool does EVERYTHING needed for file organization:
    - Uses LLM to determine which files match the category
    - Creates the target folder automatically (no need for separate folder creation)
    - Moves or copies matching files to the folder
    - Provides detailed reasoning for each file decision

    Args:
        category: Description of files to organize (e.g., "music notes", "work documents")
        target_folder: Name or path of target folder (will be created if it doesn't exist)
        move_files: If True, move files; if False, copy files (default: True)

    Returns:
        Dictionary with organized files information

    Example:
        organize_files(category="music notes", target_folder="music stuff")

    Note: This is a STANDALONE tool - it handles folder creation, file categorization,
    and file moving all in one step. No need to create folders separately!
    """
    try:
        from ..automation.file_organizer import FileOrganizer
        from ..utils import load_config
        from ..documents.search import SemanticSearch
        from ..documents import DocumentIndexer

        config = load_config()
        organizer = FileOrganizer(config)

        # Get source directory from config
        source_directory = config.get('document_directory', './test_data')

        # Initialize search engine for content analysis
        search_engine = None
        try:
            indexer = DocumentIndexer(config)
            search_engine = SemanticSearch(indexer, config)
        except Exception as e:
            logger.warning(f"Search engine not available for content analysis: {e}")

        logger.info(f"Organizing files - Category: '{category}', Target: '{target_folder}'")

        # Use LLM-driven file organization
        result = organizer.organize_files(
            category=category,
            target_folder=target_folder,
            source_directory=source_directory,
            search_engine=search_engine,
            move=move_files
        )

        if result['success']:
            return {
                "files_moved": result['files_moved'],
                "files_skipped": result['files_skipped'],
                "target_path": result['target_path'],
                "total_evaluated": result['total_evaluated'],
                "reasoning": result['reasoning'],
                "message": f"Organized {len(result['files_moved'])} files into '{target_folder}'"
            }
        else:
            return {
                "error": True,
                "error_type": "OrganizationError",
                "error_message": "File organization failed",
                "retry_possible": True
            }

    except Exception as e:
        logger.error(f"Error in organize_files: {e}")
        return {
            "error": True,
            "error_type": "OrganizationError",
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
    create_keynote_with_images,
    create_pages_doc,
    organize_files,
]
