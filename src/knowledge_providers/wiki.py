"""
Wikipedia Knowledge Provider

Provides Wikipedia article summaries via REST API with caching and error handling.

Uses MediaWiki REST API: https://en.wikipedia.org/api/rest_v1/page/summary/{slug}
"""

import requests
import json
import os
import time
import logging
from typing import Dict, Any, Optional
from urllib.parse import quote
from pathlib import Path

from .models import KnowledgeResult

logger = logging.getLogger(__name__)

# Wikipedia REST API endpoint
WIKIPEDIA_API_BASE = "https://en.wikipedia.org/api/rest_v1/page/summary"

def _slugify_query(query: str) -> str:
    """Convert query to URL-safe slug for Wikipedia API."""
    return quote(query.replace(" ", "_"), safe="")

def _get_cache_path(cache_dir: str, query: str) -> str:
    """Get cache file path for a query."""
    # Create safe filename from query
    safe_name = "".join(c for c in query if c.isalnum() or c in "._- ").replace(" ", "_")
    return os.path.join(cache_dir, f"wiki_{safe_name}.json")

def _is_cache_valid(cache_path: str, ttl_hours: int) -> bool:
    """Check if cache file is still valid."""
    if not os.path.exists(cache_path):
        return False

    cache_age_hours = (time.time() - os.path.getmtime(cache_path)) / 3600
    return cache_age_hours < ttl_hours

def _load_from_cache(cache_path: str) -> Optional[Dict[str, Any]]:
    """Load cached result if available and valid."""
    try:
        with open(cache_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"Failed to load cache file {cache_path}: {e}")
        return None

def _save_to_cache(cache_path: str, data: Dict[str, Any]) -> None:
    """Save result to cache."""
    try:
        os.makedirs(os.path.dirname(cache_path), exist_ok=True)
        with open(cache_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.warning(f"Failed to save cache file {cache_path}: {e}")

def lookup_wikipedia(query: str, config: Optional[Dict[str, Any]] = None) -> KnowledgeResult:
    """
    Look up a topic on Wikipedia and return structured information.

    Args:
        query: The topic or article title to search for
        config: Configuration dictionary (optional, will load from config if not provided)

    Returns:
        KnowledgeResult with title, summary, url, and confidence score
    """
    if not config:
        from ..utils import load_config
        config = load_config()

    # Check if wiki_lookup is enabled
    wiki_config = config.get("knowledge_providers", {}).get("wiki_lookup", {})
    if not wiki_config.get("enabled", True):
        return KnowledgeResult(
            error=True,
            error_type="DisabledProvider",
            error_message="Wikipedia lookup is disabled in configuration"
        )

    cache_dir = wiki_config.get("cache_dir", "data/cache/knowledge")
    cache_ttl_hours = wiki_config.get("cache_ttl_hours", 24)
    timeout_seconds = wiki_config.get("timeout_seconds", 10)
    max_retries = wiki_config.get("max_retries", 2)

    logger.info(f"[WIKI PROVIDER] Looking up: '{query}'")

    # Create cache path
    cache_path = _get_cache_path(cache_dir, query)

    # Check cache first
    if _is_cache_valid(cache_path, cache_ttl_hours):
        logger.info("[WIKI PROVIDER] Using cached result")
        cached_data = _load_from_cache(cache_path)
        if cached_data:
            return KnowledgeResult(**cached_data)

    # Prepare API request
    slug = _slugify_query(query)
    url = f"{WIKIPEDIA_API_BASE}/{slug}"

    # Make request with retries
    for attempt in range(max_retries + 1):
        try:
            logger.info(f"[WIKI PROVIDER] Requesting: {url} (attempt {attempt + 1})")
            response = requests.get(url, timeout=timeout_seconds)
            response.raise_for_status()

            # Parse response
            data = response.json()

            # Extract relevant information
            title = data.get("title", "")
            summary = data.get("extract", "")
            wiki_url = data.get("content_urls", {}).get("desktop", {}).get("page", "")

            # Calculate confidence based on whether we got actual content
            confidence = 1.0 if summary and title else 0.0

            result = KnowledgeResult(
                title=title,
                summary=summary,
                url=wiki_url,
                confidence=confidence
            )

            # Cache successful results
            if confidence > 0:
                _save_to_cache(cache_path, result.to_dict())

            logger.info(f"[WIKI PROVIDER] ✅ Success: '{title}' (confidence: {confidence})")
            return result

        except requests.exceptions.HTTPError as e:
            if response.status_code == 404:
                # Page doesn't exist
                result = KnowledgeResult(
                    error=True,
                    error_type="NotFound",
                    error_message=f"No Wikipedia page found for '{query}'"
                )
                # Cache negative results too (shorter TTL)
                _save_to_cache(cache_path, result.to_dict())
                logger.info(f"[WIKI PROVIDER] ❌ Not found: '{query}'")
                return result
            elif attempt < max_retries:
                logger.warning(f"[WIKI PROVIDER] HTTP error (attempt {attempt + 1}): {e}")
                continue
            else:
                logger.error(f"[WIKI PROVIDER] ❌ HTTP error after {max_retries + 1} attempts: {e}")
                return KnowledgeResult(
                    error=True,
                    error_type="HTTPError",
                    error_message=f"Wikipedia API error: {str(e)}"
                )

        except requests.exceptions.Timeout:
            if attempt < max_retries:
                logger.warning(f"[WIKI PROVIDER] Timeout (attempt {attempt + 1})")
                continue
            else:
                logger.error(f"[WIKI PROVIDER] ❌ Timeout after {max_retries + 1} attempts")
                return KnowledgeResult(
                    error=True,
                    error_type="Timeout",
                    error_message=f"Wikipedia API timeout after {timeout_seconds}s"
                )

        except requests.exceptions.RequestException as e:
            if attempt < max_retries:
                logger.warning(f"[WIKI PROVIDER] Request error (attempt {attempt + 1}): {e}")
                continue
            else:
                logger.error(f"[WIKI PROVIDER] ❌ Request error after {max_retries + 1} attempts: {e}")
                return KnowledgeResult(
                    error=True,
                    error_type="NetworkError",
                    error_message=f"Network error: {str(e)}"
                )

        except json.JSONDecodeError as e:
            logger.error(f"[WIKI PROVIDER] ❌ JSON decode error: {e}")
            return KnowledgeResult(
                error=True,
                error_type="ParseError",
                error_message=f"Failed to parse Wikipedia response: {str(e)}"
            )

        except Exception as e:
            logger.error(f"[WIKI PROVIDER] ❌ Unexpected error: {e}")
            return KnowledgeResult(
                error=True,
                error_type="UnknownError",
                error_message=f"Unexpected error: {str(e)}"
            )

    # This should never be reached, but just in case
    return KnowledgeResult(
        error=True,
        error_type="MaxRetriesExceeded",
        error_message=f"Failed after {max_retries + 1} attempts"
    )
