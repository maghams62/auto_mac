"""
LLM-based section interpretation for extracting document sections.

This module uses LLM reasoning to interpret user intent for section extraction,
avoiding hardcoded pattern matching.
"""

import logging
from typing import Dict, Any, List, Optional
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
import json
import re

from ..utils import get_temperature_for_model


logger = logging.getLogger(__name__)


class SectionInterpreter:
    """
    Interprets user's section requests using LLM reasoning.

    Instead of hardcoded patterns, uses LLM to understand:
    - "last page" → specific page index
    - "first 3 pages" → range [1, 2, 3]
    - "chorus" → semantic search
    - "pages containing X" → filtered search
    """

    def __init__(self, config: dict):
        """
        Initialize the section interpreter.

        Args:
            config: Configuration dictionary
        """
        self.config = config
        openai_config = config.get("openai", {})
        self.llm = ChatOpenAI(
            model=openai_config.get("model", "gpt-4o"),
            temperature=get_temperature_for_model(config, default_temperature=0.0),
            api_key=openai_config.get("api_key")
        )

    def interpret_section_request(
        self,
        section_query: str,
        document_info: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Interpret what the user wants to extract from the document.

        Args:
            section_query: User's section request (e.g., "last page", "chorus", "first 3 pages")
            document_info: Information about the document (page_count, title, etc.)

        Returns:
            Dictionary with interpretation:
            {
                "strategy": "exact_pages" | "page_range" | "semantic_search" | "keyword_search",
                "pages": [1, 2, 3],  # for exact_pages or page_range
                "search_query": "chorus",  # for semantic/keyword search
                "reasoning": "explanation of interpretation"
            }
        """
        logger.info(f"Interpreting section request: '{section_query}'")

        prompt = self._build_interpretation_prompt(section_query, document_info)

        try:
            messages = [
                SystemMessage(content="""You are a document section interpreter. Your job is to understand what the user wants to extract from a document and decide the best strategy.

Available strategies:
1. "exact_pages" - User wants specific page numbers (e.g., "page 5", "last page", "first page")
2. "page_range" - User wants a range of pages (e.g., "first 3 pages", "pages 2-5")
3. "semantic_search" - User wants content matching a concept (e.g., "chorus", "introduction", "summary")
4. "keyword_search" - User wants pages containing specific text (e.g., "pages with 'API'")

CRITICAL: Respond with ONLY a valid JSON object.
Format:
{
  "strategy": "exact_pages",
  "pages": [6],
  "search_query": null,
  "reasoning": "User asked for 'last page' which is page 6 of 6"
}"""),
                HumanMessage(content=prompt)
            ]

            response = self.llm.invoke(messages)

            # Parse JSON response
            content = response.content.strip()
            json_match = re.search(r'\{[\s\S]*\}', content)
            if json_match:
                content = json_match.group()

            result = json.loads(content)
            logger.info(f"Interpretation: strategy={result.get('strategy')}, pages={result.get('pages')}")

            return result

        except Exception as e:
            logger.error(f"Error interpreting section request: {e}")
            # Fallback to semantic search
            return {
                "strategy": "semantic_search",
                "pages": None,
                "search_query": section_query,
                "reasoning": f"Fallback to semantic search due to interpretation error: {e}"
            }

    def _build_interpretation_prompt(
        self,
        section_query: str,
        document_info: Dict[str, Any]
    ) -> str:
        """Build prompt for section interpretation."""

        page_count = document_info.get('page_count', 'unknown')
        doc_title = document_info.get('title', 'unknown')

        prompt = f"""DOCUMENT INFORMATION:
- Title: {doc_title}
- Total Pages: {page_count}

USER REQUEST: "{section_query}"

TASK: Determine the best strategy to extract what the user wants.

EXAMPLES:

Request: "last page" (doc has 6 pages)
Response: {{"strategy": "exact_pages", "pages": [6], "search_query": null, "reasoning": "Last page is page 6"}}

Request: "first page"
Response: {{"strategy": "exact_pages", "pages": [1], "search_query": null, "reasoning": "First page is page 1"}}

Request: "first 3 pages"
Response: {{"strategy": "page_range", "pages": [1, 2, 3], "search_query": null, "reasoning": "Pages 1 through 3"}}

Request: "page 5"
Response: {{"strategy": "exact_pages", "pages": [5], "search_query": null, "reasoning": "Explicit page 5"}}

Request: "pages 2-4"
Response: {{"strategy": "page_range", "pages": [2, 3, 4], "search_query": null, "reasoning": "Range from 2 to 4"}}

Request: "chorus"
Response: {{"strategy": "semantic_search", "pages": null, "search_query": "chorus", "reasoning": "Need to semantically search for chorus section"}}

Request: "pages containing API"
Response: {{"strategy": "keyword_search", "pages": null, "search_query": "API", "reasoning": "Search for keyword 'API'"}}

Request: "all pages"
Response: {{"strategy": "page_range", "pages": [1, 2, 3, 4, 5, 6], "search_query": null, "reasoning": "All pages means 1 through {page_count}"}}

Now interpret the user's request and respond with JSON."""

        return prompt

    def apply_interpretation(
        self,
        interpretation: Dict[str, Any],
        document_pages: List[str],
        search_engine: Any = None
    ) -> Dict[str, Any]:
        """
        Apply the interpretation to extract the actual pages.

        Args:
            interpretation: Result from interpret_section_request
            document_pages: List of page texts (0-indexed)
            search_engine: Optional search engine for semantic/keyword search

        Returns:
            Dictionary with extracted_text and page_numbers
        """
        strategy = interpretation.get('strategy')

        if strategy == 'exact_pages':
            pages = interpretation.get('pages', [])
            extracted_pages = []
            for page_num in pages:
                if 0 < page_num <= len(document_pages):
                    extracted_pages.append((page_num, document_pages[page_num - 1]))

            if extracted_pages:
                extracted_text = '\n\n'.join([text for _, text in extracted_pages])
                page_numbers = [num for num, _ in extracted_pages]
                return {
                    "extracted_text": extracted_text,
                    "page_numbers": page_numbers,
                    "word_count": len(extracted_text.split())
                }
            else:
                return {
                    "error": True,
                    "error_type": "ValidationError",
                    "error_message": f"Pages {pages} not found in document",
                    "retry_possible": False
                }

        elif strategy == 'page_range':
            pages = interpretation.get('pages', [])
            extracted_pages = []
            for page_num in pages:
                if 0 < page_num <= len(document_pages):
                    extracted_pages.append((page_num, document_pages[page_num - 1]))

            if extracted_pages:
                extracted_text = '\n\n'.join([text for _, text in extracted_pages])
                page_numbers = [num for num, _ in extracted_pages]
                return {
                    "extracted_text": extracted_text,
                    "page_numbers": page_numbers,
                    "word_count": len(extracted_text.split())
                }
            else:
                return {
                    "error": True,
                    "error_type": "ValidationError",
                    "error_message": f"Page range {pages} not valid",
                    "retry_possible": False
                }

        elif strategy == 'semantic_search':
            if not search_engine:
                # Fallback to keyword search
                query = interpretation.get('search_query', '')
                matching_pages = [
                    (i + 1, page) for i, page in enumerate(document_pages)
                    if query.lower() in page.lower()
                ]
                if matching_pages:
                    extracted_text = '\n\n'.join([text for _, text in matching_pages])
                    page_numbers = [num for num, _ in matching_pages]
                    return {
                        "extracted_text": extracted_text,
                        "page_numbers": page_numbers,
                        "word_count": len(extracted_text.split())
                    }
                else:
                    # Return all pages as fallback
                    return {
                        "extracted_text": '\n\n'.join(document_pages),
                        "page_numbers": list(range(1, len(document_pages) + 1)),
                        "word_count": sum(len(page.split()) for page in document_pages)
                    }

            # Use search engine for semantic search
            return {
                "use_semantic_search": True,
                "search_query": interpretation.get('search_query')
            }

        elif strategy == 'keyword_search':
            query = interpretation.get('search_query', '')
            matching_pages = [
                (i + 1, page) for i, page in enumerate(document_pages)
                if query.lower() in page.lower()
            ]

            if matching_pages:
                extracted_text = '\n\n'.join([text for _, text in matching_pages])
                page_numbers = [num for num, _ in matching_pages]
                return {
                    "extracted_text": extracted_text,
                    "page_numbers": page_numbers,
                    "word_count": len(extracted_text.split())
                }
            else:
                return {
                    "error": True,
                    "error_type": "ValidationError",
                    "error_message": f"No pages contain '{query}'",
                    "retry_possible": False
                }

        else:
            return {
                "error": True,
                "error_type": "InterpretationError",
                "error_message": f"Unknown strategy: {strategy}",
                "retry_possible": False
            }
