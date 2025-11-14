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
from src.config import get_config_context

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
    logger.info(f"[TOOLS] Tool: take_screenshot(doc_path='{doc_path}', pages={pages})")

    try:
        import fitz  # PyMuPDF
        from pathlib import Path
        from datetime import datetime
        from src.utils.screenshot import get_screenshot_dir
        from src.utils import load_config

        # Get screenshot directory from config
        config = load_config()
        screenshot_dir = get_screenshot_dir(config, ensure_exists=True)
        
        # Get document name for filename
        doc_path_obj = Path(doc_path)
        doc_stem = doc_path_obj.stem
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        doc = fitz.open(doc_path)
        screenshot_paths = []
        pages_captured = []

        for page_num in pages:
            if 0 < page_num <= len(doc):
                page = doc[page_num - 1]
                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))  # 2x zoom

                # Generate predictable filename
                filename = f"{doc_stem}_p{page_num}_{timestamp}.png"
                output_path = screenshot_dir / filename
                
                # Save to screenshot directory
                pix.save(str(output_path))
                
                # Return path relative to project root for security checks
                project_root = Path(__file__).resolve().parent.parent.parent
                try:
                    relative_path = output_path.resolve().relative_to(project_root)
                    screenshot_paths.append(str(relative_path))
                except ValueError:
                    # If not relative to project root, use absolute path
                    screenshot_paths.append(str(output_path.resolve()))
                
                pages_captured.append(page_num)
                logger.info(f"[TOOLS] Screenshot saved: {output_path} (page {page_num} of {doc_path_obj.name})")
            else:
                logger.warning(f"[TOOLS] Page {page_num} out of range (total: {len(doc)})")

        doc.close()

        if not screenshot_paths:
            logger.warning(f"[TOOLS] No screenshots were captured from {doc_path}")
            return {
                "error": True,
                "error_type": "ScreenshotError",
                "error_message": "No valid pages were captured",
                "retry_possible": False
            }

        logger.info(f"[TOOLS] Successfully captured {len(screenshot_paths)} screenshot(s) from {doc_path_obj.name}")
        return {
            "screenshot_paths": screenshot_paths,
            "pages_captured": pages_captured
        }

    except Exception as e:
        logger.error(f"[TOOLS] Error in take_screenshot: {e}", exc_info=True)
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

    # CRITICAL: Validate attachments are file paths, not content strings
    if attachments:
        import os
        for att_path in attachments:
            if att_path and isinstance(att_path, str):
                # Detect if someone is passing report/document CONTENT instead of a file path
                if len(att_path) > 500 or '\n\n' in att_path or att_path.count('\n') > 10:
                    logger.error(f"[COMPOSE_EMAIL] ⚠️  PLANNING ERROR: Attachment appears to be TEXT CONTENT, not a FILE PATH!")
                    logger.error(f"[COMPOSE_EMAIL] ⚠️  First 200 chars: {att_path[:200]}...")
                    return {
                        "error": True,
                        "error_type": "PlanningError",
                        "error_message": (
                            "Attachment validation failed: You provided TEXT CONTENT instead of a FILE PATH. "
                            "To email a report, you must first save it to a file using create_pages_doc. "
                            "Correct workflow: create_detailed_report → create_pages_doc → compose_email(attachments=['$stepN.pages_path'])"
                        ),
                        "retry_possible": True,
                        "hint": "Use create_pages_doc to save report_content to a file, then attach the pages_path"
                    }

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

        # Determine output path and ensure the parent directory exists
        import os
        final_path = output_path or f"~/Documents/{title}.key"
        final_path = os.path.expanduser(final_path)
        os.makedirs(os.path.dirname(final_path), exist_ok=True)

        # Call the actual keynote composer with slides
        success = keynote_composer.create_presentation(
            title=title,
            slides=slides,
            output_path=final_path
        )

        if success:
            # KeynoteComposer already verifies the file exists, but double-check here
            if os.path.exists(final_path) and os.path.isfile(final_path):
                logger.info(f"✅ Keynote file verified at: {final_path}")
                return {
                    "keynote_path": final_path,
                    "slide_count": len(slides) + 1,  # +1 for title slide
                    "message": "Keynote presentation created successfully"
                }
            else:
                logger.error(f"❌ Keynote reported success but file not found: {final_path}")
                return {
                    "error": True,
                    "error_type": "KeynoteError",
                    "error_message": f"Keynote file not saved to {final_path} - file not found after creation",
                    "retry_possible": True
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
        import os
        resolved_path = output_path or f"~/Documents/{title}.key"
        resolved_path = os.path.expanduser(resolved_path)
        os.makedirs(os.path.dirname(resolved_path), exist_ok=True)

        # Call the actual keynote composer with slides
        success = keynote_composer.create_presentation(
            title=title,
            slides=slides,
            output_path=resolved_path
        )

        if success:
            # KeynoteComposer already verifies the file exists, but double-check here
            if os.path.exists(resolved_path) and os.path.isfile(resolved_path):
                logger.info(f"✅ Keynote file with images verified at: {resolved_path}")
                return {
                    "keynote_path": resolved_path,
                    "slide_count": len(slides) + 1,  # +1 for title slide
                    "message": f"Keynote presentation created with {len(slides)} image slides"
                }

            logger.error(f"Keynote reported success but file not found after waiting: {resolved_path}")
            return {
                "error": True,
                "error_type": "KeynoteError",
                "error_message": f"Keynote file not saved to {resolved_path}",
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
    DISABLED: Pages document creation is unreliable and unsafe.
    Use create_keynote or create_local_document_report instead.

    Args:
        title: Document title
        content: Source content to format
        output_path: Save location (None = default)

    Returns:
        Error dictionary indicating Pages is disabled
    """
    logger.warning(f"Tool: create_pages_doc called but is disabled (title='{title}')")
    
    return {
        "error": True,
        "error_type": "PagesDisabled",
        "error_message": "Pages document creation is disabled due to reliability issues. Use create_keynote for presentations or create_local_document_report for PDF reports instead.",
        "retry_possible": False,
        "suggested_alternatives": [
            "create_keynote - for presentations",
            "create_local_document_report - for PDF reports"
        ]
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
        from ..documents.search import SemanticSearch
        from ..documents import DocumentIndexer

        context = get_config_context()
        config = context.data
        accessor = context.accessor
        organizer = FileOrganizer(config, accessor)

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
            search_engine=search_engine,
            move=move_files
        )

        if result.get('error'):
            return {
                "error": True,
                "error_type": result.get('error_type', 'OrganizationError'),
                "error_message": result.get('error_message', 'File organization failed'),
                "retry_possible": False
            }

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
