"""
Centralized loader for agent-specific prompt examples.

This module reads the structured few-shot hierarchy under ``prompts/examples``
and exposes convenience methods for retrieving prompt sections by agent or
category.  It replaces the monolithic ``prompts/few_shot_examples.md`` file
with an indexed layout so each agent can opt in to the minimal context it
needs.
"""

from __future__ import annotations

import json
import logging
import re
from functools import lru_cache
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple, Set

logger = logging.getLogger(__name__)


class PromptRepository:
    """
    Repository for loading agent-scoped few-shot examples.

    The repository expects an ``index.json`` file with the structure:

    .. code-block:: json

        {
          "categories": {
            "core": ["core/01_preface.md", ...],
            ...
          },
          "agents": {
            "automation": ["core", "general", "safety"],
            ...
          }
        }

    Each category entry is a list of Markdown files relative to ``prompts/examples``.
    """

    def __init__(self, repo_root: Optional[Path] = None) -> None:
        self.repo_root = Path(repo_root) if repo_root else Path(__file__).resolve().parents[1]
        self.examples_dir = self.repo_root / "prompts" / "examples"
        self._index = self._load_index()

    # --------------------------------------------------------------------- #
    # Internal helpers
    # --------------------------------------------------------------------- #
    def _load_index(self) -> Dict[str, Dict[str, List[str]]]:
        """Load the index file describing available categories and agents."""
        index_path = self.examples_dir / "index.json"
        if not index_path.exists():
            logger.warning("Prompt index not found at %s", index_path)
            return {"categories": {}, "agents": {}}

        try:
            return json.loads(index_path.read_text())
        except json.JSONDecodeError as exc:
            logger.error("Failed to parse prompt index %s: %s", index_path, exc)
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.error("Unexpected error loading prompt index %s: %s", index_path, exc)
        return {"categories": {}, "agents": {}}

    # --------------------------------------------------------------------- #
    # Public API
    # --------------------------------------------------------------------- #
    def available_categories(self) -> List[str]:
        """Return all category keys defined in the index."""
        return sorted(self._index.get("categories", {}).keys())

    def get_categories_for_agent(self, agent_name: str, *, fallback: Optional[str] = "automation") -> List[str]:
        """
        Resolve the ordered list of categories for the given agent.

        Args:
            agent_name: Logical agent identifier (e.g., ``"email"``).
            fallback: Optional fallback agent whose categories should be used
                      when the requested agent is not explicitly defined.
                      Pass ``None`` to disable fallback behaviour.
        """
        agent_categories = self._index.get("agents", {})
        if agent_name in agent_categories:
            return agent_categories[agent_name]

        if fallback and fallback in agent_categories:
            logger.debug(
                "Prompt categories for '%s' not found; using fallback agent '%s'",
                agent_name,
                fallback,
            )
            return agent_categories[fallback]

        return []

    @lru_cache(maxsize=128)
    def load_category(self, category: str) -> str:
        """
        Load and concatenate all prompt snippets for a category.

        The result is cached to avoid re-reading files across calls.
        """
        files = self._index.get("categories", {}).get(category, [])
        if not files:
            logger.debug("No prompt files registered for category '%s'", category)
            return ""

        sections: List[str] = []
        for rel_path in files:
            path = self.examples_dir / rel_path
            if not path.exists():
                logger.warning("Prompt file missing for category '%s': %s", category, rel_path)
                continue
            try:
                sections.append(path.read_text().strip())
            except Exception as exc:  # pragma: no cover - defensive logging
                logger.error("Failed to read prompt file %s: %s", path, exc)

        return "\n\n".join(section for section in sections if section)

    def load_categories(self, categories: Iterable[str]) -> List[Tuple[str, str]]:
        """
        Load multiple categories and return ordered (category, content) pairs.

        Args:
            categories: Iterable of category keys to load.
        """
        ordered_sections: List[Tuple[str, str]] = []
        for category in categories:
            content = self.load_category(category)
            if content:
                ordered_sections.append((category, content))
        return ordered_sections

    def load_agent_examples(self, agent_name: str, *, include_fallback: bool = True) -> List[Tuple[str, str]]:
        """
        Load the prompt sections associated with an agent.

        Args:
            agent_name: Logical agent identifier.
            include_fallback: When True (default), fall back to the automation
                              agent categories if the agent has no explicit entry.
        """
        categories = self.get_categories_for_agent(agent_name, fallback="automation" if include_fallback else None)
        if not categories and not include_fallback:
            return []
        if not categories and include_fallback:
            categories = self.get_categories_for_agent("automation", fallback=None)
        return self.load_categories(categories)

    def to_prompt_block(self, agent_name: str) -> str:
        """
        Render the agent's prompt sections into a single Markdown block.

        Each category is prefixed with a heading so downstream prompts can
        retain context without recombining raw files manually.
        """
        sections = self.load_agent_examples(agent_name)
        formatted: List[str] = []
        for category, content in sections:
            heading = category.replace("_", " ").title()
            formatted.append(f"### {heading} Examples\n{content}")
        return "\n\n".join(formatted).strip()

    # --------------------------------------------------------------------- #
    # Atomic Task Access (NEW)
    # --------------------------------------------------------------------- #

    def extract_task_metadata(self, example_content: str) -> Dict[str, str]:
        """
        Extract task metadata from an example file.

        Looks for patterns like:
        - User Request: "..." (task description)
        - ## Example X: ... (title)
        - task_type, complexity in JSON
        - Derives task types from titles and content
        """
        metadata = {}

        # Extract title from header
        title_match = re.search(r'##\s*(Example\s+\d+:?\s*)(.+)', example_content, re.IGNORECASE)
        if title_match:
            metadata['title'] = title_match.group(2).strip()
        else:
            # Fallback: try to find any ## header
            header_match = re.search(r'##\s*(.+)', example_content, re.IGNORECASE)
            if header_match:
                metadata['title'] = header_match.group(1).strip()

        # Extract user request
        request_match = re.search(r'###\s*User\s+Request\s*\n[""]([^""]+)[""]', example_content, re.IGNORECASE | re.DOTALL)
        if request_match:
            metadata['user_request'] = request_match.group(1).strip()

        # Extract task type and complexity from JSON-like structures
        json_match = re.search(r'"task_type"\s*:\s*"([^"]+)"', example_content)
        if json_match:
            metadata['task_type'] = json_match.group(1)

        complexity_match = re.search(r'"complexity"\s*:\s*"([^"]+)"', example_content)
        if complexity_match:
            metadata['complexity'] = complexity_match.group(1)

        # Derive task type from title if not explicitly set
        if 'task_type' not in metadata and 'title' in metadata:
            title = metadata['title'].lower()

            # Map titles to task types
            if 'email' in title and 'read' in title:
                metadata['task_type'] = 'email_reading'
            elif 'email' in title and 'summarize' in title:
                metadata['task_type'] = 'email_summarization'
            elif 'email' in title and 'send' in title or 'compose' in title:
                metadata['task_type'] = 'email_composition'
            elif 'file' in title and 'zip' in title:
                metadata['task_type'] = 'file_archiving'
            elif 'file' in title and 'search' in title:
                metadata['task_type'] = 'file_search'
            elif 'screenshot' in title:
                metadata['task_type'] = 'screen_capture'
            elif 'stock' in title:
                metadata['task_type'] = 'stock_analysis'
            elif 'map' in title or 'trip' in title:
                metadata['task_type'] = 'trip_planning'
            elif 'slide' in title or 'presentation' in title:
                metadata['task_type'] = 'presentation_creation'
            elif 'weather' in title:
                metadata['task_type'] = 'weather_query'
            elif 'web' in title and 'search' in title:
                metadata['task_type'] = 'web_search'
            elif 'web' in title and ('scrap' in title or 'download' in title):
                metadata['task_type'] = 'web_scraping'
            elif 'error' in title or 'handling' in title:
                metadata['task_type'] = 'error_handling'

        # Derive domain from title
        if 'email' in metadata.get('title', '').lower():
            metadata['domain'] = 'email'
        elif 'file' in metadata.get('title', '').lower():
            metadata['domain'] = 'file'
        elif 'stock' in metadata.get('title', '').lower():
            metadata['domain'] = 'stocks'
        elif 'map' in metadata.get('title', '').lower() or 'trip' in metadata.get('title', '').lower():
            metadata['domain'] = 'maps'
        elif 'screen' in metadata.get('title', '').lower():
            metadata['domain'] = 'screen'
        elif 'weather' in metadata.get('title', '').lower():
            metadata['domain'] = 'weather'
        elif 'slide' in metadata.get('title', '').lower() or 'presentation' in metadata.get('title', '').lower():
            metadata['domain'] = 'writing'

        return metadata

    @lru_cache(maxsize=256)
    def get_example_metadata(self, category: str, filename: str) -> Dict[str, str]:
        """
        Get metadata for a specific example file.

        Cached to avoid re-parsing files.
        """
        # filename already includes category path (e.g., "maps/01_...")
        path = self.examples_dir / filename
        if not path.exists():
            return {}

        try:
            content = path.read_text()
            metadata = self.extract_task_metadata(content)
            metadata['category'] = category
            metadata['filename'] = filename
            metadata['path'] = str(path)
            return metadata
        except Exception as exc:
            logger.warning("Failed to extract metadata from %s: %s", path, exc)
            return {}

    def find_examples_by_task_type(self, task_type: str, limit: int = 3) -> List[Tuple[str, str, Dict[str, str]]]:
        """
        Find examples matching a specific task type.

        Args:
            task_type: The task type to search for (e.g., "email_reading", "file_search")
            limit: Maximum number of examples to return

        Returns:
            List of (category, filename, metadata) tuples
        """
        matching_examples = []

        for category, files in self._index.get("categories", {}).items():
            for filename in files:
                # filename already includes category prefix (e.g., "email/01_...")
                metadata = self.get_example_metadata(category, filename)
                found_task_type = metadata.get('task_type')
                logger.debug(f"Checking {filename}: task_type={found_task_type}, looking for {task_type}")
                if found_task_type == task_type:
                    matching_examples.append((category, filename, metadata))
                    logger.debug(f"Found match: {filename}")

        # Return most relevant examples (could be enhanced with scoring)
        return matching_examples[:limit]

    def load_atomic_examples(self, task_characteristics: Dict[str, str], max_tokens: int = 4000) -> str:
        """
        Load examples atomically based on task characteristics.

        This is the key method for atomic prompt access. Instead of loading
        entire categories, it selects specific examples that match the task.

        Args:
            task_characteristics: Dict with keys like 'task_type', 'complexity', 'domain'
            max_tokens: Maximum token budget for examples

        Returns:
            Concatenated example content within token budget
        """
        examples_content = []
        total_tokens = 0

        # Strategy 1: Exact task type matches
        if 'task_type' in task_characteristics:
            task_type_examples = self.find_examples_by_task_type(
                task_characteristics['task_type'],
                limit=2
            )

            for category, filename, metadata in task_type_examples:
                content = self.load_single_example(category, filename)
                if content:
                    content_tokens = self._estimate_tokens(content)
                    if total_tokens + content_tokens <= max_tokens:
                        examples_content.append(content)
                        total_tokens += content_tokens
                    else:
                        break

        # Strategy 2: Fallback to category-based loading if no specific matches
        if not examples_content and 'domain' in task_characteristics:
            domain = task_characteristics['domain']
            if domain in self._index.get("categories", {}):
                category_content = self.load_category(domain)
                category_tokens = self._estimate_tokens(category_content)
                if category_tokens <= max_tokens:
                    examples_content.append(f"### {domain.title()} Examples\n{category_content}")
                    total_tokens += category_tokens

        # Strategy 3: Load core examples if still no matches
        if not examples_content:
            core_content = self.load_category('core')
            core_tokens = self._estimate_tokens(core_content)
            if core_tokens <= max_tokens:
                examples_content.append(f"### Core Examples\n{core_content}")
                total_tokens += core_tokens

        logger.info(
            "Loaded %d examples (%d tokens) for task: %s",
            len(examples_content),
            total_tokens,
            task_characteristics
        )

        return "\n\n".join(examples_content)

    @lru_cache(maxsize=512)
    def load_single_example(self, category: str, filename: str) -> str:
        """
        Load a single example file.

        Cached to avoid re-reading files.
        """
        # filename already includes category path (e.g., "maps/01_...")
        path = self.examples_dir / filename
        if not path.exists():
            logger.warning("Example file not found: %s/%s", category, filename)
            return ""

        try:
            content = path.read_text().strip()
            return content
        except Exception as exc:
            logger.error("Failed to read example file %s: %s", path, exc)
            return ""

    def _estimate_tokens(self, text: str) -> int:
        """Rough token estimation for budget tracking."""
        words = len(text.split())
        return int(words * 1.3)  # Conservative estimate
