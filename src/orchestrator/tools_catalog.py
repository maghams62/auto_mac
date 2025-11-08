"""
Tool catalog generation from existing tools.
"""

from typing import List, Dict, Any
import logging
from ..agent import ALL_AGENT_TOOLS
from .state import ToolSpec

logger = logging.getLogger(__name__)


def generate_tool_catalog() -> List[ToolSpec]:
    """
    Generate tool catalog from existing LangChain tools.

    Returns:
        List of ToolSpec objects
    """
    catalog = []

    # Map existing tools to catalog specs
    tool_mappings = {
        "search_documents": ToolSpec(
            name="search_documents",
            kind="tool",
            io={
                "in": ["query: str"],
                "out": ["doc_path", "doc_title", "relevance_score", "metadata"]
            },
            strengths=[
                "Semantic search across indexed documents",
                "Returns most relevant document",
                "Includes file metadata"
            ],
            limits=[
                "Only searches indexed documents",
                "Returns single best match",
                "Requires documents to be pre-indexed"
            ],
            description="Search for documents using semantic similarity"
        ),
        "extract_section": ToolSpec(
            name="extract_section",
            kind="tool",
            io={
                "in": ["doc_path: str", "section: str"],
                "out": ["extracted_text", "page_numbers", "word_count"]
            },
            strengths=[
                "Supports multiple extraction methods (all, page N, pages containing keyword)",
                "Semantic search within document",
                "Returns page numbers for context"
            ],
            limits=[
                "Requires valid document path",
                "PDF and DOCX only",
                "May miss content if section query is ambiguous"
            ],
            description="Extract specific sections or pages from a document"
        ),
        "take_screenshot": ToolSpec(
            name="take_screenshot",
            kind="tool",
            io={
                "in": ["doc_path: str", "pages: List[int]"],
                "out": ["screenshot_paths", "pages_captured"]
            },
            strengths=[
                "High-quality page images",
                "Multiple pages at once",
                "Preserves visual formatting"
            ],
            limits=[
                "PDF documents only",
                "Creates temporary files",
                "Larger file sizes"
            ],
            description="Capture page images from PDF documents"
        ),
        "compose_email": ToolSpec(
            name="compose_email",
            kind="tool",
            io={
                "in": ["subject: str", "body: str", "recipient: Optional[str]", "attachments: Optional[List[str]]", "send: bool"],
                "out": ["status", "message"]
            },
            strengths=[
                "Direct Mail.app integration",
                "Supports attachments",
                "Can send immediately or create draft"
            ],
            limits=[
                "macOS Mail.app only",
                "Requires Mail.app to be configured",
                "May trigger user prompts"
            ],
            description="Compose and send emails via Mail.app"
        ),
        "create_keynote": ToolSpec(
            name="create_keynote",
            kind="tool",
            io={
                "in": ["title: str", "content: str", "output_path: Optional[str]"],
                "out": ["keynote_path", "slide_count", "message"]
            },
            strengths=[
                "Generates structured slides from text",
                "Automatic layout",
                "macOS Keynote integration"
            ],
            limits=[
                "macOS Keynote required",
                "Basic layouts only",
                "Text-based slides only (no images)"
            ],
            description="Create Keynote presentations from text content"
        ),
        "create_keynote_with_images": ToolSpec(
            name="create_keynote_with_images",
            kind="tool",
            io={
                "in": ["title: str", "image_paths: List[str]", "output_path: Optional[str]"],
                "out": ["keynote_path", "slide_count", "message"]
            },
            strengths=[
                "Creates slides with screenshots/images",
                "Each image becomes a full slide",
                "Perfect for displaying document pages",
                "macOS Keynote integration",
                "Accepts list of image paths from previous steps"
            ],
            limits=[
                "macOS Keynote required",
                "One image per slide",
                "No text overlays on images"
            ],
            description="Create Keynote presentations with images/screenshots as slides. Use this when user wants to display screenshots or images in a presentation."
        ),
        "create_pages_doc": ToolSpec(
            name="create_pages_doc",
            kind="tool",
            io={
                "in": ["title: str", "content: str", "output_path: Optional[str]"],
                "out": ["pages_path", "message"]
            },
            strengths=[
                "Formatted document creation",
                "macOS Pages integration",
                "Preserves text structure"
            ],
            limits=[
                "macOS Pages required",
                "Basic formatting only",
                "No advanced styling"
            ],
            description="Create Pages documents from content"
        ),
        "organize_files": ToolSpec(
            name="organize_files",
            kind="tool",
            io={
                "in": ["category: str", "target_folder: str", "move_files: bool"],
                "out": ["files_moved", "files_skipped", "target_path", "total_evaluated", "reasoning", "message"]
            },
            strengths=[
                "COMPLETE standalone tool - creates folder AND moves files in ONE step",
                "LLM-driven file categorization (NO hardcoded patterns)",
                "Semantic understanding of file relevance",
                "Detailed reasoning for each file decision",
                "Handles naming conflicts automatically",
                "Supports both moving and copying files"
            ],
            limits=[
                "Only works on files in configured document directory",
                "Categorization based on filenames (content analysis optional)",
                "Conservative approach - excludes ambiguous files"
            ],
            description="Organize files into folders using LLM-driven categorization. Creates target folder automatically and moves/copies matching files. NO separate folder creation needed!"
        ),
        # Browser Tools (Separate Hierarchy)
        "google_search": ToolSpec(
            name="google_search",
            kind="browser_tool",
            io={
                "in": ["query: str", "num_results: int"],
                "out": ["query", "results", "num_results", "message"]
            },
            strengths=[
                "PRIMARY web search tool - use this first for finding information online",
                "Returns structured results with titles, links, and snippets",
                "Fast and reliable Google search integration",
                "Good for finding documentation, websites, and general information"
            ],
            limits=[
                "Requires internet connection",
                "Limited to search results (doesn't extract page content)",
                "Subject to Google rate limiting"
            ],
            description="Search Google and extract results. LEVEL 1 tool in browser hierarchy - use this first when you need to find information on the web."
        ),
        "navigate_to_url": ToolSpec(
            name="navigate_to_url",
            kind="browser_tool",
            io={
                "in": ["url: str", "wait_until: str"],
                "out": ["url", "title", "status", "message"]
            },
            strengths=[
                "Navigate to specific URLs directly",
                "Waits for page load completion",
                "Returns page title and status",
                "Good for visiting known URLs from search results"
            ],
            limits=[
                "Requires valid URL with protocol (http/https)",
                "May timeout on slow-loading pages",
                "Doesn't extract content automatically"
            ],
            description="Navigate to a specific URL. LEVEL 2 tool - use after google_search to visit specific pages."
        ),
        "extract_page_content": ToolSpec(
            name="extract_page_content",
            kind="browser_tool",
            io={
                "in": ["url: Optional[str]"],
                "out": ["url", "title", "content", "word_count", "extraction_method", "message"]
            },
            strengths=[
                "INTELLIGENT content extraction using langextract",
                "Removes navigation, ads, headers, footers automatically",
                "Extracts clean, readable text perfect for LLM processing",
                "Can navigate to URL first or extract from current page",
                "Returns word count and metadata"
            ],
            limits=[
                "May miss content from JavaScript-heavy sites",
                "Extraction quality depends on page structure",
                "Text-only (no images or formatting)"
            ],
            description="Extract clean text content from webpages using langextract. LEVEL 2 tool - use for reading and analyzing webpage content. Perfect for sending to LLM for disambiguation."
        ),
        "take_web_screenshot": ToolSpec(
            name="take_web_screenshot",
            kind="browser_tool",
            io={
                "in": ["url: Optional[str]", "full_page: bool"],
                "out": ["screenshot_path", "url", "full_page", "message"]
            },
            strengths=[
                "Capture visual snapshots of webpages",
                "Supports full-page or viewport-only capture",
                "Preserves visual appearance and layout",
                "Can navigate to URL first or capture current page"
            ],
            limits=[
                "Creates image files (larger storage)",
                "No text extraction from screenshots",
                "May timeout on very long pages"
            ],
            description="Capture webpage screenshots. LEVEL 3 tool - use when you need visual proof or reference of webpage content."
        ),
        "close_browser": ToolSpec(
            name="close_browser",
            kind="browser_tool",
            io={
                "in": [],
                "out": ["message"]
            },
            strengths=[
                "Frees up system resources",
                "Closes browser windows",
                "Clean up temporary files"
            ],
            limits=[
                "Cannot reuse browser after closing - must reinitialize",
                "All open pages will be closed"
            ],
            description="Close browser and clean up resources. LEVEL 4 tool - use at the end of web browsing sessions."
        ),
        "llamaindex_worker": ToolSpec(
            name="llamaindex_worker",
            kind="worker",
            io={
                "in": ["task: str", "context: Dict"],
                "out": ["ok: bool", "artifacts: Any", "notes: List[str]", "usage: Dict"]
            },
            strengths=[
                "RAG-powered reasoning",
                "Iterative micro-planning",
                "Can break down complex atomic tasks",
                "Access to document index"
            ],
            limits=[
                "Higher token usage",
                "Longer execution time",
                "Best for analysis/reasoning tasks"
            ],
            description="LlamaIndex worker for complex atomic tasks and RAG"
        )
    }

    # Add all mapped tools from all agents
    for tool in ALL_AGENT_TOOLS:
        tool_name = tool.name
        if tool_name in tool_mappings:
            catalog.append(tool_mappings[tool_name])
            logger.debug(f"Added tool to catalog: {tool_name}")

    # Always add the LlamaIndex worker
    if "llamaindex_worker" not in [t.name for t in catalog]:
        catalog.append(tool_mappings["llamaindex_worker"])

    logger.info(f"Generated tool catalog with {len(catalog)} tools")
    return catalog


def get_tool_specs_as_dicts(catalog: List[ToolSpec]) -> List[Dict[str, Any]]:
    """
    Convert tool catalog to list of dictionaries.

    Args:
        catalog: List of ToolSpec objects

    Returns:
        List of tool specification dictionaries
    """
    return [tool.to_dict() for tool in catalog]


def format_tool_catalog_for_prompt(catalog: List[ToolSpec]) -> str:
    """
    Format tool catalog as a readable string for LLM prompts.

    Args:
        catalog: List of ToolSpec objects

    Returns:
        Formatted string representation
    """
    lines = ["# Available Tools\n"]

    for tool in catalog:
        lines.append(f"## {tool.name} ({tool.kind})")
        lines.append(f"**Description:** {tool.description}\n")

        lines.append(f"**Inputs:** {', '.join(tool.io['in'])}")
        lines.append(f"**Outputs:** {', '.join(tool.io['out'])}\n")

        lines.append("**Strengths:**")
        for strength in tool.strengths:
            lines.append(f"  - {strength}")

        lines.append("\n**Limits:**")
        for limit in tool.limits:
            lines.append(f"  - {limit}")

        lines.append("\n---\n")

    return "\n".join(lines)
