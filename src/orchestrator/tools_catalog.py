"""
Tool catalog generation from existing tools.
"""

from typing import List, Dict, Any
import logging
from ..agent import ALL_AGENT_TOOLS
from .state import ToolSpec

logger = logging.getLogger(__name__)


def _build_parameter_metadata(tool) -> List[Dict[str, Any]]:
    """
    Build structured parameter metadata for a LangChain tool.

    Args:
        tool: LangChain tool instance

    Returns:
        List of parameter dictionaries with name/type/required/description/default
    """
    metadata: List[Dict[str, Any]] = []
    args_schema = getattr(tool, "args_schema", None)

    if not args_schema:
        return metadata

    try:
        schema_dict = args_schema.schema()
    except Exception:
        return metadata

    required_fields = set(schema_dict.get("required", []))
    properties = schema_dict.get("properties", {}) or {}

    for name, prop in properties.items():
        metadata.append({
            "name": name,
            "type": prop.get("type", "any"),
            "required": name in required_fields,
            "description": prop.get("description", "") or "",
            "default": prop.get("default"),
        })

    return metadata


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
        "reply_to_user": ToolSpec(
            name="reply_to_user",
            kind="tool",
            io={
                "in": ["message: str", "details: Optional[str]", "artifacts: Optional[List[str]]", "status: str"],
                "out": ["message", "details", "artifacts", "status"]
            },
            strengths=[
                "Produces consistent, human-friendly responses",
                "Allows agents to highlight key artifacts and context",
                "Encodes status metadata for the UI"
            ],
            limits=[
                "Must be supplied with meaningful content from prior steps",
                "Does not execute actions—purely communication oriented"
            ],
            description="Compose the final user-facing reply with optional details and artifacts."
        ),
        "search_bluesky_posts": ToolSpec(
            name="search_bluesky_posts",
            kind="tool",
            io={
                "in": ["query: str", "max_posts: int"],
                "out": ["query", "count", "posts"]
            },
            strengths=[
                "Quickly discovers public Bluesky posts for a keyword or phrase",
                "Returns metadata including author, engagement, and direct URLs",
                "Supports configurable limits for lightweight investigations"
            ],
            limits=[
                "Requires Bluesky credentials (identifier + app password)",
                "Search is limited to public posts and current API constraints"
            ],
            description="Search Bluesky for recent posts matching a query."
        ),
        "get_bluesky_author_feed": ToolSpec(
            name="get_bluesky_author_feed",
            kind="tool",
            io={
                "in": ["actor: Optional[str]", "max_posts: int"],
                "out": ["actor", "count", "posts"]
            },
            strengths=[
                "Gets posts from a specific Bluesky user or authenticated user",
                "Useful for queries like 'last 3 tweets' or 'my tweets'",
                "Returns posts in chronological order (most recent first)"
            ],
            limits=[
                "Requires Bluesky credentials (identifier + app password)",
                "Limited to public posts from the specified user"
            ],
            description="Get posts from a specific Bluesky author/handle. If actor is None, gets posts from authenticated user."
        ),
        "summarize_bluesky_posts": ToolSpec(
            name="summarize_bluesky_posts",
            kind="tool",
            io={
                "in": ["query: str", "lookback_hours: Optional[int]", "max_items: Optional[int]", "actor: Optional[str]"],
                "out": ["summary", "items", "query", "time_window"]
            },
            strengths=[
                "Combines Bluesky search results or author feed with LLM summarization",
                "Automatically detects queries like 'last N tweets' and fetches from user's feed",
                "Ranks posts by engagement (for search) or chronologically (for author feed)",
                "Supports time filtering for fresh updates"
            ],
            limits=[
                "Dependent on Bluesky search quality and rate limits",
                "Summaries rely on configured LLM (OpenAI)"
            ],
            description="Gather and summarize top Bluesky posts for a query or from a specific author within an optional time window. Handles queries like 'last 3 tweets' or 'my tweets'."
        ),
        "post_bluesky_update": ToolSpec(
            name="post_bluesky_update",
            kind="tool",
            io={
                "in": ["message: str"],
                "out": ["uri", "cid", "url", "message"]
            },
            strengths=[
                "Publishes posts directly via AT Protocol",
                "Returns canonical URI and web URL for sharing",
                "Validates content length for Bluesky limits"
            ],
            limits=[
                "Requires Bluesky credentials",
                "Posts limited to 300 characters (no media attachments via this tool)"
            ],
            description="Publish a status update to Bluesky using the configured account."
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
        "create_zip_archive": ToolSpec(
            name="create_zip_archive",
            kind="tool",
            io={
                "in": [
                    "source_path: Optional[str]",
                    "zip_name: Optional[str]",
                    "include_pattern: Optional[str]",
                    "include_extensions: Optional[List[str]]",
                    "exclude_extensions: Optional[List[str]]"
                ],
                "out": [
                    "zip_path",
                    "file_count",
                    "total_size",
                    "compressed_size",
                    "compression_ratio",
                    "source_path",
                    "message"
                ]
            },
            strengths=[
                "Flexible filtering with glob patterns and extension allow/deny lists",
                "Defaults to primary document directory when source_path is omitted",
                "Returns archive statistics (file count, size, compression ratio)"
            ],
            limits=[
                "Operates within the configured document directory",
                "Does not bundle sub-folder creation (combine with organize_files if needed)"
            ],
            description="Create ZIP archives with optional filename pattern and extension filters."
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
                "PRIMARY web search tool (DuckDuckGo HTML endpoint) - use this first for finding information online",
                "Returns structured results with titles, links, and snippets",
                "Fast and reliable, no API keys required",
                "Good for finding documentation, websites, and general information"
            ],
            limits=[
                "Requires internet connection",
                "Limited to search results (doesn't extract page content)",
                "DuckDuckGo HTML payload occasionally omits snippets for certain pages"
            ],
            description="Perform DuckDuckGo web searches and extract structured results. LEVEL 1 tool in browser hierarchy—use this first when you need to find information on the web."
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
        ),
        "plan_trip_with_stops": ToolSpec(
            name="plan_trip_with_stops",
            kind="maps_tool",
            io={
                "in": ["origin: str", "destination: str", "num_fuel_stops: int", "num_food_stops: int", "departure_time: Optional[str]", "use_google_maps: bool", "open_maps: bool"],
                "out": ["origin", "destination", "stops", "departure_time", "maps_url", "maps_service", "num_fuel_stops", "num_food_stops", "total_stops", "maps_opened", "message"]
            },
            strengths=[
                "LLM-driven stop location suggestions (NO hardcoded routes)",
                "Handles multiple fuel and food stops",
                "Supports departure time for traffic-aware routing",
                "ALWAYS returns Maps URL in https://maps.apple.com/ format (browser/UI compatible)",
                "URL format automatically converted from maps:// to https://maps.apple.com/ if needed",
                "Returns simple, clean message: 'Here's your trip, enjoy: [URL]' (no verbose reasoning chain)",
                "Optional automatic Maps opening (open_maps parameter)",
                "Apple Maps URL is default (opens in macOS Maps app, supports waypoints)",
                "Uses AppleScript automation (MapsAutomation) for native macOS integration",
                "Falls back to URL method if AppleScript fails",
                "Google Maps URL available as alternative (opens in browser)",
                "Automatic route optimization using LLM geographic knowledge",
                "Orchestrator extracts Maps URL to top level for easy access"
            ],
            limits=[
                "Maximum ~20 total stops (fuel + food combined) - reasonable limit, but LLM can suggest optimal number",
                "Stop locations determined by LLM (may vary based on route knowledge)",
                "Requires valid origin and destination locations",
                "Works for routes worldwide - no geographic limitations"
            ],
            description="Plan a road trip with fuel and food stops. ALL parameters must be extracted from user's natural language query using LLM reasoning. Handles variations like 'LA' → 'Los Angeles, CA', '2 gas stops' → num_fuel_stops=2, 'lunch and dinner' → num_food_stops=2. Returns simple response with Maps URL - no verbose reasoning chain shown to user."
        ),
        "open_maps_with_route": ToolSpec(
            name="open_maps_with_route",
            kind="maps_tool",
            io={
                "in": ["origin: str", "destination: str", "stops: Optional[List[str]]"],
                "out": ["status", "maps_url", "message"]
            },
            strengths=[
                "Opens Apple Maps app directly on macOS using AppleScript",
                "Uses MapsAutomation class for native macOS integration",
                "Supports routes with multiple waypoints",
                "Can optionally start navigation automatically",
                "Falls back to URL method if AppleScript fails",
                "Direct integration with macOS Maps application"
            ],
            limits=[
                "macOS only",
                "Requires Maps app to be installed",
                "Waypoints limited by Maps app capabilities"
            ],
            description="Open Apple Maps application with a specific route. Use after plan_trip_with_stops to display the route in Maps app."
        )
    }

    # Add all mapped tools from all agents
    for tool in ALL_AGENT_TOOLS:
        tool_name = tool.name
        if tool_name in tool_mappings:
            spec = tool_mappings[tool_name]
            spec.parameters = _build_parameter_metadata(tool)
            catalog.append(spec)
            logger.debug(f"Added tool to catalog: {tool_name}")
        else:
            logger.debug(f"Tool '{tool_name}' not in catalog mapping; skipping")

    # Always add the LlamaIndex worker
    if "llamaindex_worker" not in [t.name for t in catalog]:
        spec = tool_mappings["llamaindex_worker"]
        spec.parameters = _build_parameter_metadata(
            next((tool for tool in ALL_AGENT_TOOLS if tool.name == "llamaindex_worker"), None)
        )
        catalog.append(spec)

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


def build_tool_parameter_index() -> Dict[str, Dict[str, Any]]:
    """
    Build parameter metadata for all registered tools.

    Returns:
        Mapping of tool_name -> {"parameters": [...], "required": [...], "optional": [...]}
    """
    index: Dict[str, Dict[str, Any]] = {}

    for tool in ALL_AGENT_TOOLS:
        params = _build_parameter_metadata(tool)
        index[tool.name] = {
            "parameters": params,
            "required": [p["name"] for p in params if p.get("required")],
            "optional": [p["name"] for p in params if not p.get("required")],
        }

    return index


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

        if tool.parameters:
            lines.append("**Parameters:**")
            for param in tool.parameters:
                requirement = "REQUIRED" if param.get("required") else "optional"
                param_type = param.get("type") or "any"
                desc = param.get("description") or ""
                lines.append(f"  - {param['name']} ({requirement}, {param_type}): {desc}")
            lines.append("")

        lines.append("**Strengths:**")
        for strength in tool.strengths:
            lines.append(f"  - {strength}")

        lines.append("\n**Limits:**")
        for limit in tool.limits:
            lines.append(f"  - {limit}")

        lines.append("\n---\n")

    return "\n".join(lines)
