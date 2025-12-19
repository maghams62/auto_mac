"""
Knowledge Agent - Handles external knowledge source queries.

This agent provides access to external knowledge sources like Wikipedia
for factual information retrieval and quick reference.

INTEGRATION PATTERN:
- Agent calls knowledge providers (Wikipedia, etc.)
- Returns normalized structured data (title, summary, url, confidence)
- LLM can use this for factual verification or quick lookups
- Caches responses to reduce API calls and improve speed

Acts as a data provider for knowledge-aware workflows.
"""

from typing import Dict, Any, Optional
from langchain_core.tools import tool
import logging

logger = logging.getLogger(__name__)


@tool
def wiki_lookup(query: str) -> Dict[str, Any]:
    """
    Look up factual information on Wikipedia.

    This tool searches Wikipedia for the given query and returns a structured summary
    with title, description, source URL, and confidence score. Perfect for getting
    quick factual overviews before diving deeper with browser tools.

    KNOWLEDGE AGENT - LEVEL 1: Factual Data Retrieval
    Use this FIRST for factual overviews, background information, and quick references.

    Args:
        query: The topic, person, place, or concept to look up on Wikipedia
               (e.g., "Python programming language", "Albert Einstein", "World War II")

    Returns:
        Dictionary with structured Wikipedia information:
        {
            "title": str,           # Article title
            "summary": str,         # Brief summary/extract from the article
            "url": str,            # Full Wikipedia URL to the article
            "confidence": float,   # Confidence score (0.0-1.0, 1.0 = good match)
            "error": bool,         # Whether an error occurred
            "error_type": str,     # Error type if error=True ("NotFound", "Timeout", etc.)
            "error_message": str   # Error description if error=True
        }

    Examples:
        # Quick factual lookup
        wiki_lookup("machine learning")
        → {"title": "Machine learning", "summary": "Machine learning is...", "url": "...", "confidence": 1.0}

        # Person lookup
        wiki_lookup("Marie Curie")
        → {"title": "Marie Curie", "summary": "Marie Curie was...", "url": "...", "confidence": 1.0}

        # Concept verification
        wiki_lookup("photosynthesis")
        → {"title": "Photosynthesis", "summary": "Photosynthesis is...", "url": "...", "confidence": 1.0}

    CRITICAL: Use this BEFORE browser navigation for factual topics.
    - Returns cached results when available (fast!)
    - Handles 404s gracefully with structured errors
    - No web scraping or browser automation required

    When confidence < 1.0 or error=True, consider using browser tools for deeper research.
    """
    logger.info(f"[KNOWLEDGE AGENT] wiki_lookup(query='{query}')")

    try:
        from ..knowledge_providers.wiki import lookup_wikipedia
        from ..utils import load_config

        config = load_config()

        # Check if knowledge providers are enabled
        if not config.get("knowledge_providers", {}).get("enabled", True):
            logger.warning("[KNOWLEDGE AGENT] Knowledge providers disabled in config")
            return {
                "title": "",
                "summary": "",
                "url": "",
                "confidence": 0.0,
                "error": True,
                "error_type": "DisabledProvider",
                "error_message": "Knowledge providers are disabled in configuration"
            }

        # Call the knowledge provider
        result = lookup_wikipedia(query, config)

        if result.error:
            logger.warning(f"[KNOWLEDGE AGENT] ❌ Wiki lookup failed: {result.error_message}")
        else:
            logger.info(f"[KNOWLEDGE AGENT] ✅ Wiki lookup success: '{result.title}' (confidence: {result.confidence})")

        return result.to_dict()

    except Exception as e:
        logger.error(f"[KNOWLEDGE AGENT] Error in wiki_lookup: {e}")
        return {
            "title": "",
            "summary": "",
            "url": "",
            "confidence": 0.0,
            "error": True,
            "error_type": "AgentError",
            "error_message": str(e)
        }


# Knowledge Agent Tool Registry
KNOWLEDGE_AGENT_TOOLS = [
    wiki_lookup,
]


# Tool hierarchy documentation
KNOWLEDGE_AGENT_HIERARCHY = """
KNOWLEDGE AGENT TOOL HIERARCHY
============================

LEVEL 1: External Knowledge Retrieval
└─ wiki_lookup → Retrieve factual information from Wikipedia
   ├─ Returns structured data (title, summary, url, confidence)
   ├─ Uses REST API with caching for speed
   ├─ Handles 404s and timeouts gracefully
   └─ Perfect for quick factual verification

INTEGRATION PATTERN:
Knowledge Agent provides FAST FACTUAL DATA → LLM INTERPRETS → Browser Agent EXPLORES DEEPER

Example Flow:
1. wiki_lookup("quantum computing")
   → Returns: {"title": "Quantum computing", "summary": "...", "url": "...", "confidence": 1.0}

2. LLM evaluates if summary is sufficient, or needs deeper research
   → If sufficient: use summary for response
   → If insufficient: use browser tools for detailed exploration

3. navigate_to_url($step1.url) if user wants full article
   → Opens Wikipedia page in browser for reading

CRITICAL PRINCIPLES:
- Knowledge Agent is FAST (cached, API-based)
- Use BEFORE browser tools for factual topics
- Confidence score indicates result quality
- Error handling prevents workflow failures
- No hardcoded logic - LLM decides when to use
"""


class KnowledgeAgent:
    """
    Knowledge Agent - Provides access to external knowledge sources.

    Handles Wikipedia lookups and other factual information retrieval
    with caching and error handling.
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        logger.info("[KNOWLEDGE AGENT] Initialized")

    def get_tools(self):
        """Get all knowledge agent tools."""
        return KNOWLEDGE_AGENT_TOOLS

    def execute(self, tool_name: str, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a knowledge agent tool.

        Args:
            tool_name: Name of the tool to execute
            inputs: Tool input parameters

        Returns:
            Tool execution result
        """
        logger.info(f"[KNOWLEDGE AGENT] Executing tool: {tool_name}")

        tool_map = {
            "wiki_lookup": wiki_lookup,
        }

        if tool_name not in tool_map:
            return {
                "error": True,
                "error_type": "UnknownTool",
                "error_message": f"Unknown knowledge agent tool: {tool_name}",
                "retry_possible": False
            }

        try:
            tool = tool_map[tool_name]
            result = tool.invoke(inputs)
            return result
        except Exception as e:
            logger.error(f"[KNOWLEDGE AGENT] Execution error: {e}")
            return {
                "error": True,
                "error_type": "ExecutionError",
                "error_message": str(e),
                "retry_possible": False
            }

    def get_hierarchy(self) -> str:
        """Get tool hierarchy documentation."""
        return KNOWLEDGE_AGENT_HIERARCHY
