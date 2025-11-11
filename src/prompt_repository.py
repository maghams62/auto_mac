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
from functools import lru_cache
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

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
