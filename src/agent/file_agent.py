"""
File Agent - Handles all file and document operations.

This agent is responsible for:
- Document search and retrieval
- Content extraction
- File organization
- Document screenshots

Acts as a mini-orchestrator for file-related operations.
"""

from typing import List, Optional, Dict, Any
from langchain_core.tools import tool
from pathlib import Path
import logging
import re

from ..config import get_config_context
from ..utils import get_temperature_for_model

logger = logging.getLogger(__name__)


@tool
def search_documents(query: str, user_request: str = None, include_images: bool = True, top_k: Optional[int] = None) -> Dict[str, Any]:
    """
    Search for documents and optionally images using semantic search with LLM-determined parameters.

    FILE AGENT - LEVEL 1: Document Discovery
    Use this as the first step to find relevant documents and images.

    Args:
        query: Natural language search query
        user_request: Original user request for context (optional)
        include_images: Whether to also search for images (default: True)
        top_k: Optional explicit number of results to return. If provided, overrides LLM-determined value.

    Returns:
        Dictionary with results array containing both documents and images:
        {
            "results": [
                {
                    "doc_path": str,
                    "doc_title": str,
                    "relevance_score": float,
                    "content_preview": str,
                    "file_type": str,
                    "result_type": "document" | "image",
                    "thumbnail_url": str (for images),
                    "preview_url": str (for images),
                    "metadata": dict
                }
            ],
            "best_result": dict (top result for backward compatibility)
        }
    """
    logger.info(f"[FILE AGENT] Tool: search_documents(query='{query}', include_images={include_images}, top_k={top_k})")

    try:
        from src.documents import DocumentIndexer, SemanticSearch
        from src.utils import load_config

        config = load_config()
        documents_config = config.get("documents", {})
        allowed_doc_types = {
            ext.lower()
            for ext in documents_config.get("supported_types", [".pdf", ".docx", ".txt"])
            if isinstance(ext, str) and ext
        }
        indexer = DocumentIndexer(config)
        search_engine = SemanticSearch(indexer, config)

        # Determine top_k: use explicit value if provided, otherwise use LLM-determined value
        if top_k is not None:
            # Use explicit top_k, but still get other search params from LLM
            from .parameter_resolver import ParameterResolver
            resolver = ParameterResolver(config)
            search_params = resolver.resolve_search_parameters(
                query=query,
                context={'user_request': user_request or query, 'previous_steps': []}
            )
            # Override top_k with explicit value
            search_params['top_k'] = max(1, top_k)  # Ensure at least 1
            logger.info(f"[FILE AGENT] Using explicit top_k={top_k}, other params from LLM: {search_params}")
        else:
            # Use LLM to determine optimal search parameters (NO hardcoded top_k!)
            from .parameter_resolver import ParameterResolver
            resolver = ParameterResolver(config)
            search_params = resolver.resolve_search_parameters(
                query=query,
                context={'user_request': user_request or query, 'previous_steps': []}
            )
            logger.info(f"[FILE AGENT] LLM-determined search params: {search_params}")

        query_normalized = query.lower() if isinstance(query, str) else ""
        query_tokens = [token for token in re.split(r"\W+", query_normalized) if token]

        # Search documents
        doc_results = search_engine.search(query, top_k=search_params.get('top_k', 1))
        
        all_results = []
        
        # Add document results
        for result in doc_results:
            file_path = Path(result["file_path"])
            suffix = file_path.suffix.lower()

            # Filter to supported document types so we don't treat images as primary docs
            if allowed_doc_types and suffix and suffix not in allowed_doc_types:
                logger.debug(
                    "[FILE AGENT] Skipping non-document result in document search: %s (extension=%s)",
                    result["file_path"],
                    suffix,
                )
                continue

            boosted_score = result.get("score", 0.0)
            content_preview_raw = result.get("content_preview", "")
            title_normalized = file_path.stem.lower()

            if query_normalized and title_normalized:
                if query_normalized in title_normalized:
                    boosted_score = max(boosted_score, 1.5)
                elif query_tokens and all(token in title_normalized for token in query_tokens):
                    boosted_score = max(boosted_score, 1.0)

            if query_tokens and content_preview_raw:
                content_preview_lower = content_preview_raw.lower()
                if all(token in content_preview_lower for token in query_tokens):
                    boosted_score = max(boosted_score, 1.2)

            all_results.append({
                "doc_path": result["file_path"],
                "doc_title": result.get("title", file_path.name),
                "relevance_score": boosted_score,
                "content_preview": content_preview_raw[:500],
                "file_path": str(file_path),
                "result_type": "document",
                "metadata": {
                    "file_type": suffix[1:],
                    "chunk_count": result.get("chunk_count", 1),
                    "page_count": result.get("total_pages", 0)
                }
            })

        # Search images if enabled and requested
        if include_images and indexer.image_indexer:
            try:
                # Use same top_k for images as documents
                image_top_k = search_params.get('top_k', 1)
                logger.info(f"[FILE AGENT] Searching images with query: '{query}' (top_k={image_top_k})")
                image_results = indexer.image_indexer.search_images(query, top_k=image_top_k)
                
                logger.info(f"[FILE AGENT] Image search returned {len(image_results)} results")
                for i, img_result in enumerate(image_results):
                    file_path = img_result.get('file_path', '')
                    similarity_score = img_result.get('similarity_score', 0.0)
                    caption = img_result.get('caption', '')
                    logger.debug(
                        f"[FILE AGENT] Image result {i+1}: {img_result.get('file_name', 'unknown')} "
                        f"(similarity: {similarity_score:.4f}, caption: {caption[:50]}...)"
                    )
                    all_results.append({
                        "doc_path": file_path,
                        "doc_title": img_result.get('file_name', Path(file_path).name),
                        "relevance_score": similarity_score,
                        "content_preview": caption,
                        "file_path": file_path,
                        "result_type": "image",
                        "thumbnail_url": f"/api/files/thumbnail?path={file_path}&max_size=256",
                        "preview_url": f"/api/files/preview?path={file_path}",
                        "metadata": {
                            "file_type": Path(file_path).suffix[1:] if file_path else "image",
                            "width": img_result.get('width'),
                            "height": img_result.get('height'),
                            "breadcrumb": img_result.get('breadcrumb', '')
                        }
                    })
                    
                if image_results:
                    top_similarity = image_results[0].get('similarity_score', 0.0)
                    logger.info(
                        f"[FILE AGENT] Found {len(image_results)} image results "
                        f"(top similarity: {top_similarity:.4f})"
                    )
                else:
                    logger.info(f"[FILE AGENT] No image results found for query: '{query}'")
            except Exception as e:
                logger.error(f"[FILE AGENT] Image search failed: {e}", exc_info=True)

        # Sort all results by relevance score
        all_results.sort(key=lambda x: x.get("relevance_score", 0.0), reverse=True)

        if not all_results:
            return {
                "error": True,
                "error_type": "NotFoundError",
                "error_message": f"No documents or images found matching query: {query}",
                "retry_possible": True,
                "results": []
            }

        doc_count = sum(1 for r in all_results if r.get("result_type") == "document")
        image_count = len(all_results) - doc_count

        # Return results array and best result for backward compatibility
        best_result = next((r for r in all_results if r.get("result_type") == "document"), all_results[0])
        summary_blurb = []
        if doc_count:
            summary_blurb.append(f"{doc_count} document{'s' if doc_count != 1 else ''}")
        if image_count:
            summary_blurb.append(f"{image_count} image{'s' if image_count != 1 else ''}")
        summary_text = ""
        if summary_blurb:
            summary_text = f"Found {', '.join(summary_blurb)} matching '{query}'. Top match: {best_result.get('doc_title', 'unknown')}."

        return {
            "results": all_results,
            "best_result": best_result,
            "doc_path": best_result.get("doc_path"),
            "doc_title": best_result.get("doc_title"),
            "relevance_score": best_result.get("relevance_score", 0.0),
            "content_preview": best_result.get("content_preview", ""),
            "result_type": best_result.get("result_type", "document"),
            "thumbnail_url": best_result.get("thumbnail_url"),
            "preview_url": best_result.get("preview_url"),
            "metadata": best_result.get("metadata", {}),
            "summary_blurb": summary_text,
            "files": all_results  # consumers can render a file list if desired
        }

    except Exception as e:
        logger.error(f"[FILE AGENT] Error in search_documents: {e}")
        return {
            "error": True,
            "error_type": "SearchError",
            "error_message": str(e),
            "retry_possible": False,
            "results": []
        }


@tool
def extract_section(doc_path: str, section: str) -> Dict[str, Any]:
    """
    Extract specific content from a document using LLM-based interpretation.

    FILE AGENT - LEVEL 2: Content Extraction
    Use this after search_documents to extract specific sections.

    Args:
        doc_path: Path to document
        section: Section identifier (e.g., 'last page', 'first 3 pages', 'chorus', 'all')

    Returns:
        Dictionary with extracted_text, page_numbers, and word_count
    """
    logger.info(f"[FILE AGENT] Tool: extract_section(doc_path='{doc_path}', section='{section}')")

    try:
        from src.documents import DocumentParser, SemanticSearch, DocumentIndexer
        from src.utils import load_config

        config = load_config()
        parser = DocumentParser(config)
        indexer = DocumentIndexer(config)
        search_engine = SemanticSearch(indexer, config)

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

        interpreter = SectionInterpreter(config)

        # Let LLM interpret what the user wants
        interpretation = interpreter.interpret_section_request(
            section_query=section,
            document_info=document_info
        )

        logger.info(f"[FILE AGENT] LLM interpretation: strategy={interpretation.get('strategy')}")

        # Apply the interpretation
        result = interpreter.apply_interpretation(
            interpretation=interpretation,
            document_pages=pages,
            search_engine=search_engine
        )

        # If result indicates we should use semantic search, do it
        if result.get('use_semantic_search'):
            search_query = result.get('search_query')
            logger.info(f"[FILE AGENT] Using semantic search for: {search_query}")

            try:
                from .parameter_resolver import ParameterResolver

                resolver = ParameterResolver(config)
                page_params = resolver.resolve_page_selection_parameters(
                    total_pages=len(pages),
                    user_intent=section,
                    context={'query': search_query}
                )

                logger.info(f"[FILE AGENT] LLM-determined page params: max={page_params.get('max_pages')}")

                page_results = search_engine.search_pages_in_document(
                    query=search_query,
                    doc_path=doc_path,
                    top_k=page_params.get('max_pages', 1)
                )

                if page_results:
                    page_numbers = [r['page_number'] for r in page_results]
                    logger.info(f"[FILE AGENT] Semantic search found pages: {page_numbers}")

                    extracted_text = '\n\n'.join([
                        pages[page_num - 1] for page_num in page_numbers
                        if 0 < page_num <= len(pages)
                    ])

                    return {
                        "extracted_text": extracted_text,
                        "page_numbers": page_numbers,
                        "word_count": len(extracted_text.split())
                    }

            except Exception as e:
                logger.error(f"[FILE AGENT] Semantic search error: {e}")

        # Return the result from interpretation
        return result

    except Exception as e:
        logger.error(f"[FILE AGENT] Error in extract_section: {e}")
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

    FILE AGENT - LEVEL 3: Visual Capture
    Use this when you need images of document pages.

    Args:
        doc_path: Path to document
        pages: List of page numbers to capture

    Returns:
        Dictionary with screenshot_paths and pages_captured
    """
    logger.info(f"[FILE AGENT] Tool: take_screenshot(doc_path='{doc_path}', pages={pages})")

    try:
        import fitz  # PyMuPDF
        from pathlib import Path
        from datetime import datetime
        from src.utils.screenshot import get_screenshot_dir
        from src.config.context import get_config_context

        # Get screenshot directory from config
        context = get_config_context()
        config = context.data
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
                logger.info(f"[FILE AGENT] Screenshot saved: {output_path} (page {page_num} of {doc_path_obj.name})")
            else:
                logger.warning(f"[FILE AGENT] Page {page_num} out of range (total: {len(doc)})")

        doc.close()

        if not screenshot_paths:
            logger.warning(f"[FILE AGENT] No screenshots were captured from {doc_path}")
            return {
                "error": True,
                "error_type": "ScreenshotError",
                "error_message": "No valid pages were captured",
                "retry_possible": False
            }

        logger.info(f"[FILE AGENT] Successfully captured {len(screenshot_paths)} screenshot(s) from {doc_path_obj.name}")
        return {
            "screenshot_paths": screenshot_paths,
            "pages_captured": pages_captured
        }

    except Exception as e:
        logger.error(f"[FILE AGENT] Error in take_screenshot: {e}", exc_info=True)
        return {
            "error": True,
            "error_type": "ScreenshotError",
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

    FILE AGENT - LEVEL 4: File Organization
    Use this to organize files into folders. This is a COMPLETE standalone operation.

    This tool does EVERYTHING needed for file organization:
    - Uses LLM to determine which files match the category
    - Creates the target folder automatically
    - Moves or copies matching files to the folder
    - Provides detailed reasoning for each file decision

    Args:
        category: Description of files to organize (e.g., "music notes", "work documents")
        target_folder: Name or path of target folder (will be created if it doesn't exist)
        move_files: If True, move files; if False, copy files (default: True)

    Returns:
        Dictionary with organized files information
    """
    logger.info(f"[FILE AGENT] Tool: organize_files(category='{category}', target='{target_folder}')")

    try:
        from src.automation.file_organizer import FileOrganizer
        from src.documents.search import SemanticSearch
        from src.documents import DocumentIndexer

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
            logger.warning(f"[FILE AGENT] Search engine not available: {e}")

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
        logger.error(f"[FILE AGENT] Error in organize_files: {e}")
        return {
            "error": True,
            "error_type": "OrganizationError",
            "error_message": str(e),
            "retry_possible": False
        }


@tool
def create_zip_archive(
    source_path: Optional[str] = None,
    zip_name: str = "archive.zip",
    include_pattern: str = "*",
    include_extensions: Optional[List[str]] = None,
    exclude_extensions: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Create a ZIP archive from files or folders.

    FILE AGENT - LEVEL 5: Compression
    Use this to compress files/folders into a ZIP archive.

    Args:
        source_path: Path to file or folder to compress (can be relative to document_directory)
        zip_name: Name of the output ZIP file (with or without .zip extension)
        include_pattern: Optional glob pattern to filter files (default: "*" = all files)
        include_extensions: Optional list[str] of extensions (without dot) to include (e.g., ["pdf", "txt"])
        exclude_extensions: Optional list[str] of extensions to exclude (e.g., ["mp3", "wav"])

    Returns:
        Dictionary with zip_path, file_count, and total_size

    Examples:
        - Zip entire folder: create_zip_archive("backup.zip")  # Uses document directory
        - Zip only PDFs: create_zip_archive("pdfs.zip", include_extensions=["pdf"])
        - Zip everything except music: create_zip_archive("study_stuff.zip", exclude_extensions=["mp3", "wav", "flac"])
    """
    logger.info(f"[FILE AGENT] Tool: create_zip_archive(source='{source_path}', zip='{zip_name}')")

    try:
        import zipfile
        import os
        from pathlib import Path
        import fnmatch
        from src.config_validator import ConfigValidationError

        context = get_config_context()
        config = context.data
        accessor = context.accessor

        # Ensure .zip extension
        if not zip_name.endswith('.zip'):
            zip_name += '.zip'

        # Resolve source path
        # If source_path is provided and is absolute/exists, use it directly
        # Otherwise, try to use document directory, but fallback to current directory if not configured
        if source_path:
            # User provided a path - try to use it
            if os.path.isabs(source_path):
                source_path = os.path.abspath(source_path)
            elif os.path.exists(source_path):
                source_path = os.path.abspath(source_path)
            else:
                # Try relative to document directory if configured
                try:
                    doc_dir = accessor.get_primary_document_directory()
                    source_path = os.path.abspath(os.path.join(doc_dir, source_path))
                except ConfigValidationError:
                    # Fallback to current directory
                    source_path = os.path.abspath(source_path)
        else:
            # No source_path provided - try document directory, fallback to current directory
            try:
                doc_dir = accessor.get_primary_document_directory()
                source_path = doc_dir
            except ConfigValidationError:
                # Fallback to current working directory
                source_path = os.getcwd()
                logger.info(f"[FILE AGENT] No document directory configured, using current directory: {source_path}")

        if not os.path.exists(source_path):
            return {
                "error": True,
                "error_type": "NotFoundError",
                "error_message": f"Source path not found: {source_path}",
                "retry_possible": False
            }

        # Determine output location (same directory as source)
        if os.path.isdir(source_path):
            output_dir = source_path
        else:
            output_dir = os.path.dirname(source_path)

        zip_path = os.path.join(output_dir, zip_name)

        include_set = {ext.lower().lstrip('.') for ext in (include_extensions or []) if ext}
        exclude_set = {ext.lower().lstrip('.') for ext in (exclude_extensions or []) if ext}

        def should_include(file_name: str) -> bool:
            if not fnmatch.fnmatch(file_name, include_pattern):
                return False

            ext = os.path.splitext(file_name)[1].lower().lstrip('.')

            if include_set and ext not in include_set:
                return False

            if exclude_set and ext in exclude_set:
                return False

            return True

        # Create ZIP archive
        file_count = 0
        total_size = 0

        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            if os.path.isfile(source_path):
                # Single file
                if should_include(os.path.basename(source_path)):
                    zipf.write(source_path, os.path.basename(source_path))
                    file_count = 1
                    total_size = os.path.getsize(source_path)
                    logger.info(f"[FILE AGENT] Added file: {source_path}")
            else:
                # Directory - walk and add files
                for root, dirs, files in os.walk(source_path):
                    for file in files:
                        file_path = os.path.join(root, file)

                        # CRITICAL: Skip the output zip file itself to prevent self-inclusion
                        if os.path.abspath(file_path) == os.path.abspath(zip_path):
                            logger.info(f"[FILE AGENT] Skipping output zip file: {file}")
                            continue

                        if should_include(file):
                            # Archive name preserves directory structure
                            arcname = os.path.relpath(file_path, source_path)
                            zipf.write(file_path, arcname)
                            file_count += 1
                            total_size += os.path.getsize(file_path)
                            logger.info(f"[FILE AGENT] Added: {arcname}")

        if file_count == 0:
            # No files matched - remove empty ZIP
            os.remove(zip_path)
            return {
                "error": True,
                "error_type": "NoFilesError",
                "error_message": f"No files matched pattern '{include_pattern}' in {source_path}",
                "retry_possible": False
            }

        logger.info(f"[FILE AGENT] Created ZIP: {zip_path} ({file_count} files, {total_size} bytes)")

        return {
            "zip_path": zip_path,
            "file_count": file_count,
            "total_size": total_size,
            "compressed_size": os.path.getsize(zip_path),
            "compression_ratio": round((1 - os.path.getsize(zip_path) / total_size) * 100, 1) if total_size > 0 else 0,
            "include_pattern": include_pattern,
            "included_extensions": sorted(include_set) if include_set else None,
            "excluded_extensions": sorted(exclude_set) if exclude_set else None,
            "source_path": source_path,
            "message": f"Created ZIP archive with {file_count} files"
        }

    except Exception as e:
        logger.error(f"[FILE AGENT] Error in create_zip_archive: {e}")
        return {
            "error": True,
            "error_type": "ZipError",
            "error_message": str(e),
            "retry_possible": False
        }


@tool
def explain_folder(folder_path: Optional[str] = None) -> Dict[str, Any]:
    """
    List and explain all files in an authorized folder with brief descriptions.

    FILE AGENT - LEVEL 1: File Explanation
    Use this to get a high-level overview of files in a folder with 1-2 line explanations.

    Args:
        folder_path: Optional path to folder (must be in authorized folders from config).
                     If None, lists files from all authorized folders.

    Returns:
        Dictionary with:
        - files: List of file entries, each with file_path, file_name, file_type, explanation
        - folder_path: The folder that was queried (or "all authorized folders")
        - total_count: Number of files found

    Security:
        - Only operates on folders explicitly allowed in config.yaml (documents.folders)
        - Validates folder_path against authorized paths
    """
    logger.info(f"[FILE AGENT] Tool: explain_folder(folder_path='{folder_path}')")

    try:
        from ..documents import DocumentIndexer
        from ..utils import load_config
        from pathlib import Path
        import os

        config = load_config()
        indexer = DocumentIndexer(config)

        # Get authorized folders from config
        authorized_folders = config.get('documents', {}).get('folders', [])
        if not authorized_folders:
            return {
                "error": True,
                "error_type": "ConfigError",
                "error_message": "No authorized folders configured in config.yaml",
                "retry_possible": False
            }

        # Expand paths
        authorized_folders = [os.path.expanduser(f) for f in authorized_folders]

        # If folder_path provided, validate it's authorized
        target_folder = None
        if folder_path:
            folder_path = os.path.expanduser(folder_path)
            folder_path = os.path.abspath(folder_path)

            # Check if folder_path is within any authorized folder
            is_authorized = False
            for auth_folder in authorized_folders:
                auth_folder = os.path.abspath(auth_folder)
                try:
                    # Check if folder_path is within auth_folder
                    Path(folder_path).relative_to(auth_folder)
                    is_authorized = True
                    target_folder = folder_path
                    break
                except ValueError:
                    # Not a subpath, continue checking
                    continue

            if not is_authorized:
                return {
                    "error": True,
                    "error_type": "UnauthorizedPath",
                    "error_message": f"Folder '{folder_path}' is not in authorized folders. Authorized: {authorized_folders}",
                    "retry_possible": False
                }

        # Get all indexed files
        if not indexer.documents:
            return {
                "error": True,
                "error_type": "NoIndexError",
                "error_message": "No files indexed. Run indexing first.",
                "retry_possible": False
            }

        # Collect unique files (group by file_path)
        file_map = {}
        for doc_chunk in indexer.documents:
            file_path = doc_chunk['file_path']
            
            # Filter by folder if specified
            if target_folder:
                try:
                    Path(file_path).relative_to(target_folder)
                except ValueError:
                    continue  # Skip files not in target folder

            if file_path not in file_map:
                file_map[file_path] = {
                    'file_path': file_path,
                    'file_name': doc_chunk['file_name'],
                    'file_type': doc_chunk['file_type'],
                    'chunks': []
                }
            
            # Collect content previews from chunks
            file_map[file_path]['chunks'].append(doc_chunk.get('content', '')[:500])

        # Generate explanations using LLM
        from langchain_openai import ChatOpenAI
        from langchain_core.messages import SystemMessage, HumanMessage

        openai_config = config.get("openai", {})
        llm = ChatOpenAI(
            model=openai_config.get("model", "gpt-4o"),
            temperature=get_temperature_for_model(config, default_temperature=0.3),
            api_key=openai_config.get("api_key")
        )

        explained_files = []
        for file_path, file_info in sorted(file_map.items()):
            # Combine chunk previews for context
            content_preview = '\n\n'.join(file_info['chunks'])[:2000]  # Limit to avoid token limits
            
            # Generate explanation
            prompt = f"""Provide a brief 1-2 sentence explanation of what this file is about.

File: {file_info['file_name']}
Type: {file_info['file_type']}
Content preview: {content_preview[:1000]}

Respond with ONLY the explanation, no additional text."""

            try:
                messages = [
                    SystemMessage(content="You provide concise file descriptions. Respond with 1-2 sentences only."),
                    HumanMessage(content=prompt)
                ]
                response = llm.invoke(messages)
                explanation = response.content.strip()
            except Exception as e:
                logger.warning(f"[FILE AGENT] Error generating explanation for {file_info['file_name']}: {e}")
                explanation = f"{file_info['file_type'].upper()} file"

            explained_files.append({
                'file_path': file_path,
                'file_name': file_info['file_name'],
                'file_type': file_info['file_type'],
                'explanation': explanation
            })

        return {
            "files": explained_files,
            "folder_path": target_folder or "all authorized folders",
            "total_count": len(explained_files)
        }

    except Exception as e:
        logger.error(f"[FILE AGENT] Error in explain_folder: {e}")
        return {
            "error": True,
            "error_type": "ExplanationError",
            "error_message": str(e),
            "retry_possible": False
        }


@tool
def explain_files() -> Dict[str, Any]:
    """
    List and explain all indexed/authorized files with brief descriptions.

    FILE AGENT - LEVEL 1: File Explanation
    Use this to get a high-level overview of all files you have access to with 1-2 line explanations.

    Returns:
        Dictionary with:
        - files: List of file entries, each with file_path, file_name, file_type, explanation
        - total_count: Number of files found

    Security:
        - Only returns files from folders explicitly allowed in config.yaml (documents.folders)
    """
    logger.info(f"[FILE AGENT] Tool: explain_files()")

    # Reuse explain_folder with no folder_path to get all files
    return explain_folder.invoke({"folder_path": None})


@tool
def list_related_documents(query: str, max_results: int = 10) -> Dict[str, Any]:
    """
    List multiple related documents matching a semantic query.

    FILE AGENT - LEVEL 1: Document Discovery
    Use this when the user wants to see multiple matching files (e.g., "show all guitar tab files").
    This tool groups search results by document and returns structured metadata.

    Args:
        query: Natural language search query describing the documents to find
        max_results: Maximum number of documents to return (default: 10, cap: 25)

    Returns:
        Dictionary with:
        - type: "file_list"
        - message: Summary message with count
        - files: List of document entries, each with:
          - name: Basename of file
          - path: Full absolute path
          - score: Similarity score (0-1)
          - meta: Dictionary with file_type and optional total_pages
        - summary_blurb: Optional contextual summary (empty initially, LLM can populate)
        - total_count: Number of documents found
    """
    logger.info(f"[FILE LIST] Tool: list_related_documents(query='{query}', max_results={max_results})")

    try:
        import re
        from src.documents import DocumentIndexer, SemanticSearch
        from src.utils import load_config
        from pathlib import Path

        config = load_config()
        indexer = DocumentIndexer(config)
        search_engine = SemanticSearch(indexer, config)

        # Cap max_results at 25
        max_results = min(max_results, 25)
        if max_results < 1:
            max_results = 10

        # Extract high-signal keywords from query for filtering
        # Remove common stop words and extract meaningful tokens
        stop_words = {"the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "of", "with", "by", "my", "all", "files", "file", "documents", "document", "docs", "doc"}
        query_lower = query.lower()
        # Extract words (alphanumeric sequences)
        query_words = re.findall(r'\b\w+\b', query_lower)
        # Filter out stop words and short words (< 3 chars), keep meaningful tokens
        keywords = [w for w in query_words if w not in stop_words and len(w) >= 3]
        
        logger.info(f"[FILE LIST] Extracted keywords from query: {keywords}")

        # Use search_and_group to get grouped results
        grouped_results = search_engine.search_and_group(query)

        # Also search for images if image indexer is available
        image_results = []
        if indexer.image_indexer:
            try:
                logger.info(f"[FILE LIST] Searching images with query: '{query}' (max_results={max_results})")
                # Search for images with same query
                image_results = indexer.image_indexer.search_images(query, top_k=max_results)
                if image_results:
                    top_similarity = image_results[0].get('similarity_score', 0.0)
                    logger.info(
                        f"[FILE LIST] Found {len(image_results)} image results "
                        f"(top similarity: {top_similarity:.4f})"
                    )
                    # Log top results
                    for i, img_result in enumerate(image_results[:3]):  # Log top 3
                        logger.debug(
                            f"[FILE LIST] Image result {i+1}: {img_result.get('file_name', 'unknown')} "
                            f"(similarity: {img_result.get('similarity_score', 0.0):.4f})"
                        )
                else:
                    logger.info(f"[FILE LIST] No image results found for query: '{query}'")
            except Exception as e:
                logger.error(f"[FILE LIST] Image search failed: {e}", exc_info=True)

        # Combine document and image results
        all_results = []
        filtered_out_count = 0
        
        # Helper function to check if file matches keywords
        def matches_keywords(file_path: str, file_name: str, breadcrumb: str = "") -> bool:
            """Check if file path/name/breadcrumb contains at least one keyword."""
            if not keywords:
                return True  # No keywords to filter on
            
            search_text = f"{file_path} {file_name} {breadcrumb}".lower()
            return any(keyword in search_text for keyword in keywords)
        
        # Get breadcrumb helper from search results
        def get_breadcrumb(file_path: str) -> str:
            """Generate breadcrumb path for display."""
            try:
                folders = config.get('documents', {}).get('folders', [])
                file_path_obj = Path(file_path)
                
                for folder in folders:
                    try:
                        folder_path = Path(folder)
                        if file_path_obj.is_relative_to(folder_path):
                            relative_path = file_path_obj.relative_to(folder_path)
                            return str(relative_path.parent) if relative_path.parent != Path('.') else str(relative_path)
                    except (ValueError, OSError):
                        continue
                
                # Fallback: return parent directory name
                return str(file_path_obj.parent.name) if file_path_obj.parent != file_path_obj else ""
            except Exception:
                return ""
        
        # Add document results with keyword filtering
        for result in grouped_results:
            file_path = result['file_path']
            file_name = result['file_name']
            similarity = result.get('max_similarity', 0.0)
            file_type = result.get('file_type', Path(file_path).suffix[1:] if Path(file_path).suffix else '')
            total_pages = result.get('total_pages', 0)
            breadcrumb = result.get('breadcrumb', get_breadcrumb(file_path))

            # Apply keyword filtering if keywords were extracted
            if keywords and not matches_keywords(file_path, file_name, breadcrumb):
                filtered_out_count += 1
                logger.debug(
                    f"[FILE LIST] Filtered out document (no keyword match): {file_name} "
                    f"(similarity: {similarity:.4f}, keywords: {keywords})"
                )
                continue

            # Generate display path (human-friendly breadcrumb)
            display_path = breadcrumb if breadcrumb else get_breadcrumb(file_path)

            all_results.append({
                "name": file_name,
                "path": file_path,
                "display_path": display_path,
                "score": round(float(similarity), 4),
                "result_type": "document",
                "meta": {
                    "file_type": file_type,
                    "total_pages": total_pages if total_pages > 0 else None
                }
            })

        # Add image results with keyword filtering
        for img_result in image_results:
            file_path = img_result.get('file_path', '')
            file_name = img_result.get('file_name', Path(file_path).name if file_path else '')
            similarity = img_result.get('similarity_score', 0.0)
            file_type = Path(file_path).suffix[1:] if file_path and Path(file_path).suffix else 'image'
            breadcrumb = img_result.get('breadcrumb', get_breadcrumb(file_path))

            # Apply keyword filtering if keywords were extracted
            if keywords and not matches_keywords(file_path, file_name, breadcrumb):
                filtered_out_count += 1
                logger.debug(
                    f"[FILE LIST] Filtered out image (no keyword match): {file_name} "
                    f"(similarity: {similarity:.4f}, keywords: {keywords})"
                )
                continue

            # Generate display path
            display_path = breadcrumb if breadcrumb else get_breadcrumb(file_path)

            all_results.append({
                "name": file_name,
                "path": file_path,
                "display_path": display_path,
                "score": round(float(similarity), 4),
                "result_type": "image",
                "thumbnail_url": f"/api/files/thumbnail?path={file_path}&max_size=256",
                "preview_url": f"/api/files/preview?path={file_path}",
                "meta": {
                    "file_type": file_type,
                    "width": img_result.get('width'),
                    "height": img_result.get('height')
                }
            })

        # Sort all results by score (descending)
        all_results.sort(key=lambda x: x.get('score', 0.0), reverse=True)

        if not all_results:
            logger.info(f"[FILE LIST] No documents or images found for query: '{query}' (keywords: {keywords}, filtered: {filtered_out_count})")
            return {
                "type": "file_list",
                "message": f"No documents or images found matching '{query}'",
                "files": [],
                "total_count": 0,
                "summary_blurb": ""
            }

        # Limit to max_results
        limited_results = all_results[:max_results]
        top_filenames = [r['name'] for r in limited_results[:5]]

        logger.info(
            f"[FILE LIST] Query: '{query}', Keywords: {keywords}, "
            f"Total results before filtering: {len(grouped_results) + len(image_results)}, "
            f"Filtered out: {filtered_out_count}, "
            f"Final results: {len(all_results)}, "
            f"Returning top {len(limited_results)}"
        )
        logger.info(f"[FILE LIST] Top filenames: {', '.join(top_filenames)}")
        
        # Log similarity scores for top results
        for i, result in enumerate(limited_results[:5]):
            logger.debug(
                f"[FILE LIST] Result {i+1}: {result['name']} "
                f"(score: {result['score']:.4f}, type: {result['result_type']})"
            )

        # Create summary message
        doc_count = sum(1 for r in limited_results if r.get('result_type') == 'document')
        img_count = sum(1 for r in limited_results if r.get('result_type') == 'image')
        count = len(limited_results)
        
        if doc_count > 0 and img_count > 0:
            message = f"Found {count} result{'s' if count != 1 else ''} matching '{query}' ({doc_count} document{'s' if doc_count != 1 else ''}, {img_count} image{'s' if img_count != 1 else ''})"
        elif img_count > 0:
            message = f"Found {count} image{'s' if count != 1 else ''} matching '{query}'"
        else:
            message = f"Found {count} document{'s' if count != 1 else ''} matching '{query}'"
        
        files = limited_results

        result = {
            "type": "file_list",
            "message": message,
            "files": files,
            "total_count": len(all_results),  # Total found, not just returned
            "summary_blurb": ""  # Empty initially, LLM can populate later
        }
        
        # CRITICAL: Log the exact result structure for debugging
        logger.info(f"[FILE LIST] Returning result with type='{result.get('type')}', files count={len(result.get('files', []))}")
        logger.info(f"[FILE LIST] Result keys: {list(result.keys())}")
        if result.get("files"):
            logger.info(f"[FILE LIST] First file structure: {list(result['files'][0].keys()) if result['files'] else 'empty'}")
            logger.info(f"[FILE LIST] Sample file: name='{result['files'][0].get('name')}', path='{result['files'][0].get('path')}', result_type='{result['files'][0].get('result_type')}'")
        
        return result

    except Exception as e:
        logger.error(f"[FILE LIST] Error in list_related_documents: {e}")
        return {
            "error": True,
            "error_type": "ListError",
            "error_message": str(e),
            "retry_possible": False
        }


@tool
def list_documents(filter: Optional[str] = None, folder_path: Optional[str] = None,
                  max_results: int = 20) -> Dict[str, Any]:
    """
    List indexed documents with optional filtering.

    FILE AGENT - LEVEL 1: Document Discovery
    Use this when the user wants to browse or list their indexed documents.
    Shows a directory-style listing of all indexed documents with metadata.

    Args:
        filter: Text to filter documents by (name, folder, or semantic query)
        folder_path: Specific folder path to list documents from
        max_results: Maximum number of documents to return (default: 20)

    Returns:
        Dictionary with:
        - type: "document_list"
        - message: Summary message
        - documents: List of document entries with name, path, size, modified, preview
        - total_count: Total number of documents found
        - has_more: Boolean indicating if there are more results
    """
    logger.info(f"[DOCUMENT LIST] Tool: list_documents(filter='{filter}', folder_path='{folder_path}', max_results={max_results})")

    try:
        from src.services.document_listing import DocumentListingService
        from src.utils import load_config

        config = load_config()
        service = DocumentListingService(config)

        return service.list_documents(filter, folder_path, max_results)

    except Exception as e:
        logger.error(f"[DOCUMENT LIST] Error in list_documents: {e}")
        return {
            "error": True,
            "error_type": "ListError",
            "error_message": str(e),
            "retry_possible": False
        }


# File Agent Tool Registry
FILE_AGENT_TOOLS = [
    search_documents,
    list_related_documents,
    list_documents,
    extract_section,
    take_screenshot,
    organize_files,
    create_zip_archive,
    explain_folder,
    explain_files,
]


# File Agent Hierarchy
FILE_AGENT_HIERARCHY = """
File Agent Hierarchy:
====================

LEVEL 1: Document Discovery & Explanation
└─ search_documents → Find relevant documents using semantic search
└─ list_related_documents → List multiple related documents matching a query (e.g., "show all guitar tabs")
└─ explain_folder → List and explain files in a folder (1-2 line descriptions)
└─ explain_files → List and explain all indexed files (1-2 line descriptions)

LEVEL 2: Content Extraction
└─ extract_section → Extract specific sections from documents

LEVEL 3: Visual Capture
└─ take_screenshot → Capture page images from documents

LEVEL 4: File Organization
└─ organize_files → Organize files into folders (COMPLETE standalone tool)

LEVEL 5: Compression
└─ create_zip_archive → Create ZIP archives from files/folders

Typical Workflow:
1. explain_files() or explain_folder(path) → Get overview of available files
2. search_documents(query) → Find specific document
   OR list_related_documents(query) → List multiple matching documents
3. extract_section(doc_path, section) → Extract content
4. [Optional] take_screenshot(doc_path, pages) → Capture images
5. [Optional] organize_files(category, folder) → Organize files
"""


class FileAgent:
    """
    File Agent - Mini-orchestrator for file operations.

    Responsibilities:
    - Document search and retrieval
    - Content extraction with LLM interpretation
    - File organization with semantic understanding
    - Document screenshots

    This agent acts as a sub-orchestrator that handles all file-related tasks.
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.tools = {tool.name: tool for tool in FILE_AGENT_TOOLS}
        logger.info(f"[FILE AGENT] Initialized with {len(self.tools)} tools")

    def get_tools(self) -> List:
        """Get all file agent tools."""
        return FILE_AGENT_TOOLS

    def get_hierarchy(self) -> str:
        """Get file agent hierarchy documentation."""
        return FILE_AGENT_HIERARCHY

    def execute(self, tool_name: str, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a file agent tool."""
        if tool_name not in self.tools:
            return {
                "error": True,
                "error_type": "ToolNotFound",
                "error_message": f"File agent tool '{tool_name}' not found",
                "available_tools": list(self.tools.keys())
            }

        tool = self.tools[tool_name]
        logger.info(f"[FILE AGENT] Executing: {tool_name}")

        try:
            result = tool.invoke(inputs)
            return result
        except Exception as e:
            logger.error(f"[FILE AGENT] Execution error: {e}")
            return {
                "error": True,
                "error_type": "ExecutionError",
                "error_message": str(e),
                "retry_possible": False
            }
