from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from urllib.parse import urlparse

from ..canonical_ids import CanonicalIdRegistry
from ..embedding_provider import EmbeddingProvider
from ..vector_event import VectorEvent
from ..vector_store_factory import create_vector_store

logger = logging.getLogger(__name__)


class GitVectorIndexer:
    """Transforms synthetic Git commits/PRs into vector events."""

    def __init__(
        self,
        config,
        *,
        events_path: Optional[Path] = None,
        prs_path: Optional[Path] = None,
        output_path: Optional[Path] = None,
        embedding_provider: Optional[EmbeddingProvider] = None,
        vector_store=None,
        canonical_registry: Optional[CanonicalIdRegistry] = None,
    ):
        self.config = config
        self.events_path = events_path or Path("data/synthetic_git/git_events.json")
        self.prs_path = prs_path or Path("data/synthetic_git/git_prs.json")
        self.output_path = output_path or Path("data/vector_index/git_index.json")
        self.embedding_provider = embedding_provider or EmbeddingProvider(config)
        self.vector_store = vector_store or create_vector_store(
            "git",
            local_path=self.output_path,
            config=config,
        )
        self.registry = canonical_registry or CanonicalIdRegistry.from_file()
        backend = os.getenv("VECTOR_BACKEND") or (config.get("vectordb") or {}).get("backend") or "local"
        backend = backend.strip().lower()
        target = getattr(self.vector_store, "collection", str(self.output_path))
        logger.info("[GIT INDEXER] Using vector backend='%s' target='%s'", backend, target)

    def build(self) -> Dict[str, int]:
        commits = self._load_file(self.events_path)
        prs = self._load_file(self.prs_path)
        if not commits and not prs:
            logger.warning("[GIT INDEXER] No git events found.")
            return {"indexed": 0}

        vector_events: List[VectorEvent] = []
        for commit in commits:
            vector_events.append(self._to_vector_event(commit, source_type="git_commit"))
        for pr in prs:
            vector_events.append(self._to_vector_event(pr, source_type="git_pr"))

        texts = [event.text for event in vector_events]
        embeddings = self.embedding_provider.embed_batch(texts, batch_size=32)

        ready_events: List[VectorEvent] = []
        for event, embedding in zip(vector_events, embeddings):
            if not embedding:
                logger.warning("[GIT INDEXER] Missing embedding for event %s; skipping", event.event_id)
                continue
            event.embedding = embedding
            ready_events.append(event)

        if not ready_events:
            logger.error("[GIT INDEXER] No git events were embedded successfully.")
            return {"indexed": 0}

        self.vector_store.upsert(ready_events)
        logger.info("[GIT INDEXER] Indexed %s git events", len(ready_events))
        return {"indexed": len(ready_events)}

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _load_file(self, path: Path) -> List[Dict]:
        if not path.exists():
            logger.warning("[GIT INDEXER] File missing: %s", path)
            return []
        try:
            return json.loads(path.read_text())
        except json.JSONDecodeError as exc:
            logger.error("[GIT INDEXER] Failed to parse %s: %s", path, exc)
            return []

    def _to_vector_event(self, raw: Dict, *, source_type: str) -> VectorEvent:
        event_id = raw.get("id") or self._fallback_id(raw, source_type)
        timestamp = self._parse_timestamp(raw.get("timestamp"))
        service_ids = raw.get("service_ids") or []
        component_ids = raw.get("component_ids") or []
        apis = raw.get("changed_apis") or []
        labels = raw.get("labels") or []

        self.registry.assert_valid(
            services=service_ids,
            components=component_ids,
            apis=apis,
            context=event_id,
        )

        doc_paths = self._doc_paths(raw.get("files_changed"))
        if doc_paths:
            self.registry.assert_valid(docs=doc_paths, context=event_id)

        permalink = self._build_permalink(raw, source_type)
        metadata = {
            "repo": raw.get("repo"),
            "repo_url": raw.get("repo_url"),
            "branch": raw.get("branch"),
            "author": raw.get("author"),
            "commit_sha": raw.get("commit_sha"),
            "pr_number": raw.get("pr_number"),
            "files_changed": raw.get("files_changed", []),
            "doc_paths": doc_paths,
            "service_ids": service_ids,
            "component_ids": component_ids,
            "apis": apis,
            "labels": labels,
            "url": permalink,
            "permalink": permalink,
            "repo_slug": self._extract_repo_slug(raw),
        }

        event_text = self._compose_text(raw, source_type, doc_paths)

        return VectorEvent(
            event_id=event_id,
            source_type=source_type,
            text=event_text,
            timestamp=timestamp,
            service_ids=service_ids,
            component_ids=component_ids,
            apis=apis,
            labels=labels,
            metadata=metadata,
        )

    @staticmethod
    def _fallback_id(raw: Dict, source_type: str) -> str:
        if source_type == "git_pr":
            return f"git_pr:{raw.get('pr_number') or 'unknown'}"
        sha = raw.get("commit_sha") or raw.get("id") or "unknown"
        return f"git_commit:{sha}"

    @staticmethod
    def _parse_timestamp(ts: Optional[str]) -> datetime:
        if not ts:
            return datetime.now(timezone.utc)
        try:
            if ts.endswith("Z"):
                ts = ts.replace("Z", "+00:00")
            return datetime.fromisoformat(ts)
        except ValueError:
            return datetime.now(timezone.utc)

    def _doc_paths(self, files: Optional[Iterable[str]]) -> List[str]:
        if not files:
            return []
        return [path for path in files if path in self.registry.docs]

    def _compose_text(self, raw: Dict, source_type: str, doc_paths: List[str]) -> str:
        repo = raw.get("repo")
        author = raw.get("author")
        timestamp = raw.get("timestamp")
        header = f"[{source_type.upper()}] {repo} by {author} @ {timestamp}"
        summary = raw.get("text_for_embedding") or raw.get("message") or raw.get("title") or ""

        lines = [
            header,
            f"Branch: {raw.get('branch')}",
            f"Changed APIs: {', '.join(raw.get('changed_apis') or []) or 'n/a'}",
        ]

        if doc_paths:
            lines.append(f"Affected Docs: {', '.join(doc_paths)}")

        if source_type == "git_pr":
            lines.append(f"PR Title: {raw.get('title')}")
            lines.append(f"PR Body: {raw.get('body') or 'n/a'}")

        lines.append("")
        lines.append(summary.strip())

        files_changed = raw.get("files_changed") or []
        if files_changed:
            lines.append("")
            lines.append("Files Changed:")
            for file_path in files_changed:
                lines.append(f"- {file_path}")

        return "\n".join(line for line in lines if line is not None)

    @staticmethod
    def _extract_repo_slug(raw: Dict) -> Optional[str]:
        repo_url = raw.get("repo_url") or ""
        if repo_url:
            try:
                parsed = urlparse(repo_url)
                slug = parsed.path.strip("/")
                if slug:
                    return slug
            except ValueError:
                pass
        repo = (raw.get("repo") or "").strip("/")
        owner = (raw.get("repo_owner") or "").strip("/")
        if repo and owner:
            return f"{owner}/{repo}"
        return repo or None

    def _build_permalink(self, raw: Dict, source_type: str) -> Optional[str]:
        slug = self._extract_repo_slug(raw)
        if not slug:
            return None
        if source_type == "git_pr":
            pr_number = raw.get("pr_number")
            if pr_number:
                return f"https://github.com/{slug}/pull/{pr_number}"
        sha = raw.get("commit_sha")
        if sha:
            return f"https://github.com/{slug}/commit/{sha}"
        return None

