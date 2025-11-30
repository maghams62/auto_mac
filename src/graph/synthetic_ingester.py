from __future__ import annotations

import json
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set

from ..vector.canonical_ids import CanonicalIdRegistry
from ..synthetic.mappings import (
    API_COMPONENT_MAP,
    DOC_API_MAP,
    DOC_COMPONENT_MAP,
)
from .ingestor import GraphIngestor
from .service import GraphService

logger = logging.getLogger(__name__)


@dataclass
class SyntheticGraphPayload:
    services: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    components: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    service_components: Dict[str, Set[str]] = field(default_factory=dict)
    apis: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    docs: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    git_events: List[Dict[str, Any]] = field(default_factory=list)
    slack_events: List[Dict[str, Any]] = field(default_factory=list)


class SyntheticGraphIngester:
    """Loads synthetic fixtures and upserts them into Neo4j via GraphIngestor."""

    def __init__(
        self,
        config: Dict[str, Any],
        *,
        graph_service: Optional[GraphService] = None,
        canonical_ids: Optional[CanonicalIdRegistry] = None,
        slack_path: Optional[Path] = None,
        git_events_path: Optional[Path] = None,
        git_prs_path: Optional[Path] = None,
    ):
        self.config = config
        self.graph_service = graph_service or GraphService(config)
        self.ingestor = GraphIngestor(self.graph_service)
        self.registry = canonical_ids or CanonicalIdRegistry.from_file()

        self.slack_path = slack_path or Path("data/synthetic_slack/slack_events.json")
        self.git_events_path = git_events_path or Path("data/synthetic_git/git_events.json")
        self.git_prs_path = git_prs_path or Path("data/synthetic_git/git_prs.json")
        self.synthetic_git_root = Path("data/synthetic_git")

    def ingest(self) -> Dict[str, int]:
        payload = self.build_payload()
        summary = {
            "services": len(payload.services),
            "components": len(payload.components),
            "apis": len(payload.apis),
            "docs": len(payload.docs),
            "git_events": len(payload.git_events),
            "slack_events": len(payload.slack_events),
        }

        if not self.ingestor.available():
            logger.warning("[GRAPH] Neo4j disabled or unreachable; returning payload summary only.")
            return summary

        graph_uri = getattr(self.graph_service, "uri", None)
        logger.info(
            "[GRAPH] Neo4j enabled%s; ingesting synthetic graph payload.",
            f" ({graph_uri})" if graph_uri else "",
        )
        for service_id, props in payload.services.items():
            self.ingestor.upsert_service(service_id, props)

        for component_id, props in payload.components.items():
            self.ingestor.upsert_component(component_id, props)

        for service_id, component_ids in payload.service_components.items():
            for component_id in component_ids:
                self.ingestor.link_service_component(service_id, component_id)

        for api_id, api_data in payload.apis.items():
            self.ingestor.upsert_api_endpoint(
                api_id,
                component_id=api_data.get("component"),
                properties=api_data.get("properties"),
            )

        for doc_id, doc_data in payload.docs.items():
            self.ingestor.upsert_doc(
                doc_id,
                component_ids=doc_data.get("components", []),
                endpoint_ids=doc_data.get("apis", []),
                properties=doc_data.get("properties"),
            )

        for git_event in payload.git_events:
            self.ingestor.upsert_git_event(
                git_event["id"],
                component_ids=git_event.get("component_ids", []),
                endpoint_ids=git_event.get("apis", []),
                properties=git_event.get("properties"),
            )

        for slack_event in payload.slack_events:
            self.ingestor.upsert_slack_event(
                slack_event["id"],
                component_ids=slack_event.get("component_ids", []),
                endpoint_ids=slack_event.get("apis", []),
                properties=slack_event.get("properties"),
            )

        logger.info(
            "[GRAPH] Synthetic ingestion complete (services=%s components=%s apis=%s docs=%s git_events=%s slack_events=%s)",
            summary["services"],
            summary["components"],
            summary["apis"],
            summary["docs"],
            summary["git_events"],
            summary["slack_events"],
        )
        return summary

    # ------------------------------------------------------------------
    # Payload construction helpers
    # ------------------------------------------------------------------
    def build_payload(self) -> SyntheticGraphPayload:
        slack_events = self._load_json(self.slack_path)
        git_events = self._load_json(self.git_events_path)
        git_prs = self._load_json(self.git_prs_path)
        combined_git_events = git_events + git_prs

        payload = SyntheticGraphPayload()
        payload.services = {
            service_id: {"name": self._humanize_identifier(service_id)}
            for service_id in sorted(self.registry.services)
        }
        payload.components = {
            component_id: {"name": self._humanize_component(component_id)}
            for component_id in sorted(self.registry.components)
        }
        payload.service_components = self._derive_service_component_links(slack_events, combined_git_events)
        payload.apis = self._build_api_payloads()
        payload.docs = self._build_doc_payloads()
        payload.git_events = [self._format_git_event(event) for event in combined_git_events]
        payload.slack_events = [self._format_slack_event(event) for event in slack_events]
        return payload

    def _build_api_payloads(self) -> Dict[str, Dict[str, Any]]:
        apis: Dict[str, Dict[str, Any]] = {}
        for api_id in sorted(self.registry.apis):
            apis[api_id] = {
                "component": API_COMPONENT_MAP.get(api_id),
                "properties": {
                    "path": api_id,
                    "name": api_id,
                },
            }
        return apis

    def _build_doc_payloads(self) -> Dict[str, Dict[str, Any]]:
        docs: Dict[str, Dict[str, Any]] = {}
        for doc_id in sorted(self.registry.docs):
            components = DOC_COMPONENT_MAP.get(doc_id, [])
            apis = DOC_API_MAP.get(doc_id, [])
            docs[doc_id] = {
                "components": components,
                "apis": apis,
                "properties": {
                    "path": doc_id,
                    "title": self._doc_title(doc_id),
                },
            }
        return docs

    def _derive_service_component_links(
        self,
        slack_events: Iterable[Dict[str, Any]],
        git_events: Iterable[Dict[str, Any]],
    ) -> Dict[str, Set[str]]:
        mapping: Dict[str, Set[str]] = defaultdict(set)

        def _apply(events: Iterable[Dict[str, Any]]) -> None:
            for event in events:
                services = event.get("service_ids") or []
                components = event.get("component_ids") or []
                for service_id in services:
                    if service_id not in self.registry.services:
                        continue
                    for component_id in components:
                        if component_id in self.registry.components:
                            mapping[service_id].add(component_id)

        _apply(slack_events)
        _apply(git_events)
        return mapping

    def _format_git_event(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        event_id = raw.get("id") or raw.get("commit_sha") or raw.get("pr_number")
        timestamp = self._parse_timestamp(raw.get("timestamp"))
        component_ids = [cid for cid in (raw.get("component_ids") or []) if cid in self.registry.components]
        apis = [api for api in (raw.get("changed_apis") or []) if api in self.registry.apis]
        return {
            "id": event_id,
            "component_ids": component_ids,
            "apis": apis,
            "properties": {
                "kind": "git_pr" if "pr_number" in raw else "git_commit",
                "repo": raw.get("repo"),
                "message": raw.get("message") or raw.get("title"),
                "summary": raw.get("text_for_embedding"),
                "timestamp": timestamp.isoformat(),
                "author": raw.get("author"),
                "repo_url": raw.get("repo_url"),
            },
        }

    def _format_slack_event(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        component_ids = [cid for cid in (raw.get("component_ids") or []) if cid in self.registry.components]
        apis = [api for api in (raw.get("related_apis") or []) if api in self.registry.apis]
        timestamp = self._parse_timestamp(raw.get("timestamp"))
        return {
            "id": raw.get("id"),
            "component_ids": component_ids,
            "apis": apis,
            "properties": {
                "channel": raw.get("channel"),
                "labels": raw.get("labels", []),
                "text": raw.get("text_raw"),
                "workspace": raw.get("workspace"),
                "timestamp": timestamp.isoformat(),
            },
        }

    # ------------------------------------------------------------------
    # Utility helpers
    # ------------------------------------------------------------------
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

    def _doc_title(self, doc_rel_path: str) -> str:
        path = self._resolve_doc_path(doc_rel_path)
        if not path or not path.exists():
            return doc_rel_path
        try:
            for line in path.read_text().splitlines():
                line = line.strip()
                if line:
                    return line.lstrip("# ").strip()
        except Exception:
            pass
        return doc_rel_path

    def _resolve_doc_path(self, doc_rel_path: str) -> Optional[Path]:
        candidate = self.synthetic_git_root / doc_rel_path
        if candidate.exists():
            return candidate
        matches = list(self.synthetic_git_root.glob(f"**/{doc_rel_path}"))
        return matches[0] if matches else None

    @staticmethod
    def _humanize_identifier(identifier: str) -> str:
        return identifier.replace("-", " ").replace("_", " ").title()

    @staticmethod
    def _humanize_component(component_id: str) -> str:
        if "." in component_id:
            namespace, name = component_id.split(".", 1)
            return f"{namespace.title()} · {name.replace('_', ' ').title()}"
        return component_id.title()

    def _load_json(self, path: Path) -> List[Dict[str, Any]]:
        if not path.exists():
            logger.warning("[GRAPH] Fixture missing: %s", path)
            return []
        try:
            return json.loads(path.read_text())
        except json.JSONDecodeError as exc:
            logger.error("[GRAPH] Failed to parse %s: %s", path, exc)
            return []

