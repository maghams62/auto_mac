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

from ..config import get_config_context
from ..utils import get_temperature_for_model

logger = logging.getLogger(__name__)


@tool
def search_documents(query: str, user_request: str = None) -> Dict[str, Any]:
    """
    Search for documents using semantic search with LLM-determined parameters.

    FILE AGENT - LEVEL 1: Document Discovery
    Use this as the first step to find relevant documents.

    Args:
        query: Natural language search query
        user_request: Original user request for context (optional)

    Returns:
        Dictionary with doc_path, doc_title, relevance_score, and metadata
    """
    logger.info(f"[FILE AGENT] Tool: search_documents(query='{query}')")

    try:
        from src.documents import DocumentIndexer, SemanticSearch
        from src.utils import load_config

        config = load_config()
        indexer = DocumentIndexer(config)
        search_engine = SemanticSearch(indexer, config)

        # Use LLM to determine optimal search parameters (NO hardcoded top_k!)
        from .parameter_resolver import ParameterResolver

        resolver = ParameterResolver(config)
        search_params = resolver.resolve_search_parameters(
            query=query,
            context={'user_request': user_request or query, 'previous_steps': []}
        )

        logger.info(f"[FILE AGENT] LLM-determined search params: {search_params}")

        results = search_engine.search(query, top_k=search_params.get('top_k', 1))

        if not results:
            return {
                "error": True,
                "error_type": "NotFoundError",
                "error_message": f"No documents found matching query: {query}",
                "retry_possible": True
            }

        # Return top result with enhanced metadata for RAG
        result = results[0]
        return {
            "doc_path": result["file_path"],
            "doc_title": result.get("title", Path(result["file_path"]).name),
            "relevance_score": result.get("score", 0.0),
            "content_preview": result.get("content_preview", "")[:500],  # First 500 chars for context
            "metadata": {
                "file_type": Path(result["file_path"]).suffix[1:],
                "chunk_count": result.get("chunk_count", 1),
                "page_count": result.get("total_pages", 0)
            }
        }

    except Exception as e:
        logger.error(f"[FILE AGENT] Error in search_documents: {e}")
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
                logger.info(f"[FILE AGENT] Screenshot saved: {temp_file.name}")
            else:
                logger.warning(f"[FILE AGENT] Page {page_num} out of range (total: {len(doc)})")

        doc.close()

        return {
            "screenshot_paths": screenshot_paths,
            "pages_captured": pages_captured
        }

    except Exception as e:
        logger.error(f"[FILE AGENT] Error in take_screenshot: {e}")
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

        # Use search_and_group to get grouped results
        grouped_results = search_engine.search_and_group(query)

        if not grouped_results:
            logger.info(f"[FILE LIST] No documents found for query: {query}")
            return {
                "type": "file_list",
                "message": f"No documents found matching '{query}'",
                "files": [],
                "total_count": 0,
                "summary_blurb": ""
            }

        # Limit to max_results
        limited_results = grouped_results[:max_results]
        top_filenames = [r['file_name'] for r in limited_results[:5]]

        logger.info(f"[FILE LIST] Query: '{query}', Hit count: {len(grouped_results)}, Returning top {len(limited_results)}")
        logger.info(f"[FILE LIST] Top filenames: {', '.join(top_filenames)}")

        # Transform results to the expected format
        files = []
        for result in limited_results:
            file_path = result['file_path']
            file_name = result['file_name']
            similarity = result.get('max_similarity', 0.0)
            file_type = result.get('file_type', Path(file_path).suffix[1:] if Path(file_path).suffix else '')
            total_pages = result.get('total_pages', 0)

            files.append({
                "name": file_name,
                "path": file_path,
                "score": round(float(similarity), 4),
                "meta": {
                    "file_type": file_type,
                    "total_pages": total_pages if total_pages > 0 else None
                }
            })

        # Create summary message
        count = len(files)
        message = f"Found {count} document{'s' if count != 1 else ''} matching '{query}'"

        return {
            "type": "file_list",
            "message": message,
            "files": files,
            "total_count": len(grouped_results),  # Total found, not just returned
            "summary_blurb": ""  # Empty initially, LLM can populate later
        }

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
