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
        from documents import DocumentIndexer, SemanticSearch
        from utils import load_config

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
        from documents import DocumentParser, SemanticSearch, DocumentIndexer
        from utils import load_config

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
        from automation.file_organizer import FileOrganizer
        from utils import load_config
        from documents.search import SemanticSearch
        from documents import DocumentIndexer

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
            logger.warning(f"[FILE AGENT] Search engine not available: {e}")

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
        logger.error(f"[FILE AGENT] Error in organize_files: {e}")
        return {
            "error": True,
            "error_type": "OrganizationError",
            "error_message": str(e),
            "retry_possible": False
        }


@tool
def create_zip_archive(
    source_path: str,
    zip_name: str,
    include_pattern: str = "*"
) -> Dict[str, Any]:
    """
    Create a ZIP archive from files or folders.

    FILE AGENT - LEVEL 5: Compression
    Use this to compress files/folders into a ZIP archive.

    Args:
        source_path: Path to file or folder to compress (can be relative to document_directory)
        zip_name: Name of the output ZIP file (with or without .zip extension)
        include_pattern: Optional glob pattern to filter files (default: "*" = all files)

    Returns:
        Dictionary with zip_path, file_count, and total_size

    Examples:
        - Zip entire folder: create_zip_archive("test_data", "backup.zip")
        - Zip only PDFs: create_zip_archive("test_data", "pdfs.zip", "*.pdf")
        - Zip specific folder: create_zip_archive("test_data/misc_folder", "misc_archive.zip")
    """
    logger.info(f"[FILE AGENT] Tool: create_zip_archive(source='{source_path}', zip='{zip_name}')")

    try:
        import zipfile
        import os
        from pathlib import Path
        import fnmatch
        from utils import load_config

        config = load_config()

        # Ensure .zip extension
        if not zip_name.endswith('.zip'):
            zip_name += '.zip'

        # Resolve source path
        doc_dir = config.get('document_directory', './test_data')

        # Make path absolute
        if os.path.isabs(source_path):
            source_path = os.path.abspath(source_path)
        else:
            # Check if it's relative to current dir first
            if os.path.exists(source_path):
                source_path = os.path.abspath(source_path)
            else:
                # Try relative to document directory
                source_path = os.path.abspath(os.path.join(doc_dir, source_path))

        if not os.path.exists(source_path):
            return {
                "error": True,
                "error_type": "NotFoundError",
                "error_message": f"Source path not found: {source_path}",
                "retry_possible": False
            }

        # Determine output location (same directory as source or document directory)
        if os.path.isdir(source_path):
            output_dir = os.path.dirname(source_path)
        else:
            output_dir = os.path.dirname(source_path)

        zip_path = os.path.join(output_dir, zip_name)

        # Create ZIP archive
        file_count = 0
        total_size = 0

        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            if os.path.isfile(source_path):
                # Single file
                if fnmatch.fnmatch(os.path.basename(source_path), include_pattern):
                    zipf.write(source_path, os.path.basename(source_path))
                    file_count = 1
                    total_size = os.path.getsize(source_path)
                    logger.info(f"[FILE AGENT] Added file: {source_path}")
            else:
                # Directory - walk and add files
                for root, dirs, files in os.walk(source_path):
                    for file in files:
                        if fnmatch.fnmatch(file, include_pattern):
                            file_path = os.path.join(root, file)
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


# File Agent Tool Registry
FILE_AGENT_TOOLS = [
    search_documents,
    extract_section,
    take_screenshot,
    organize_files,
    create_zip_archive,
]


# File Agent Hierarchy
FILE_AGENT_HIERARCHY = """
File Agent Hierarchy:
====================

LEVEL 1: Document Discovery
└─ search_documents → Find relevant documents using semantic search

LEVEL 2: Content Extraction
└─ extract_section → Extract specific sections from documents

LEVEL 3: Visual Capture
└─ take_screenshot → Capture page images from documents

LEVEL 4: File Organization
└─ organize_files → Organize files into folders (COMPLETE standalone tool)

LEVEL 5: Compression
└─ create_zip_archive → Create ZIP archives from files/folders

Typical Workflow:
1. search_documents(query) → Find document
2. extract_section(doc_path, section) → Extract content
3. [Optional] take_screenshot(doc_path, pages) → Capture images
4. [Optional] organize_files(category, folder) → Organize files
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
