from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional

from ..vector import create_vector_store, EmbeddingProvider
from .scenario_classifier import DemoScenario


DEFAULT_STORE_PATHS = {
    "slack": Path("data/vector_index/slack_index.json"),
    "git": Path("data/vector_index/git_index.json"),
    "docs": Path("data/vector_index/doc_index.json"),
}


@dataclass
class VectorSnippet:
    source: str
    score: float
    text: str
    metadata: Dict[str, object] = field(default_factory=dict)


@dataclass
class VectorRetrievalBundle:
    slack: List[VectorSnippet] = field(default_factory=list)
    git: List[VectorSnippet] = field(default_factory=list)
    docs: List[VectorSnippet] = field(default_factory=list)

    def total_snippets(self) -> int:
        return len(self.slack) + len(self.git) + len(self.docs)


class VectorRetriever:
    """Fetch Slack/Git/Doc snippets for a given scenario using the selected vector backend."""

    def __init__(
        self,
        config,
        *,
        store_paths: Optional[Dict[str, Path]] = None,
        embedding_provider: Optional[EmbeddingProvider] = None,
    ):
        self.config = config
        self.embedding_provider = embedding_provider or EmbeddingProvider(config)
        path_map = {**DEFAULT_STORE_PATHS, **(store_paths or {})}

        self.stores = {
            "slack": create_vector_store("slack", local_path=path_map["slack"], config=config),
            "git": create_vector_store("git", local_path=path_map["git"], config=config),
            "docs": create_vector_store("docs", local_path=path_map["docs"], config=config),
        }

    def fetch_context(
        self,
        scenario: DemoScenario,
        *,
        question: str,
        top_k_slack: int = 4,
        top_k_git: int = 4,
        top_k_docs: int = 3,
        lookback_days: int = 14,
    ) -> VectorRetrievalBundle:
        filters = {"apis": [scenario.api]}
        since = datetime.now(timezone.utc) - timedelta(days=lookback_days)

        slack = self._search_store(
            store=self.stores["slack"],
            label="Slack",
            question=question,
            top_k=top_k_slack,
            filters=filters,
            since=since,
        )
        git = self._search_store(
            store=self.stores["git"],
            label="Git",
            question=question,
            top_k=top_k_git,
            filters=filters,
            since=since,
        )
        docs = self._search_store(
            store=self.stores["docs"],
            label="Doc",
            question=question,
            top_k=top_k_docs,
            filters=filters,
            since=None,
        )

        return VectorRetrievalBundle(slack=slack, git=git, docs=docs)

    def _search_store(
        self,
        *,
        store,
        label: str,
        question: str,
        top_k: int,
        filters: Dict[str, List[str]],
        since: Optional[datetime],
    ) -> List[VectorSnippet]:
        results = store.search(
            question,
            embedding_provider=self.embedding_provider,
            top_k=top_k,
            filters=filters,
            since=since,
        )

        snippets: List[VectorSnippet] = []
        for item in results:
            record = dict(item.get("record") or {})
            text = record.pop("text", "")
            record.pop("embedding", None)
            snippet = VectorSnippet(
                source=label,
                score=item.get("score") or 0.0,
                text=text,
                metadata=record,
            )
            snippets.append(snippet)
        return snippets

