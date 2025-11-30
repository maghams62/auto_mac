from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from ..graph.service import GraphService
from ..synthetic.mappings import API_COMPONENT_MAP, DOC_API_MAP, DOC_COMPONENT_MAP, services_for_components
from .scenario_classifier import DemoScenario

DEFAULT_STORE_PATHS = {
    "slack": Path("data/vector_index/slack_index.json"),
    "git": Path("data/vector_index/git_index.json"),
}


@dataclass
class GraphSummary:
    api: str
    services: List[str] = field(default_factory=list)
    components: List[str] = field(default_factory=list)
    docs: List[str] = field(default_factory=list)
    git_events: List[str] = field(default_factory=list)
    slack_events: List[str] = field(default_factory=list)


class GraphNeighborhoodSummarizer:
    """Produces a lightweight graph neighborhood summary for the demo harness."""

    def __init__(
        self,
        config,
        *,
        graph_service: Optional[GraphService] = None,
        store_paths: Optional[Dict[str, Path]] = None,
    ):
        self.config = config
        self.graph_service = graph_service or GraphService(config)
        self.store_paths = {**DEFAULT_STORE_PATHS, **(store_paths or {})}

    def summarize(self, scenario: DemoScenario, *, max_events: int = 5) -> GraphSummary:
        summary = self._query_graph(scenario, max_events=max_events)
        if summary:
            return summary
        return self._fallback_summary(scenario, max_events=max_events)

    # ------------------------------------------------------------------
    def _query_graph(self, scenario: DemoScenario, *, max_events: int) -> Optional[GraphSummary]:
        if not self.graph_service.is_available():
            return None

        query = """
        MATCH (api:APIEndpoint {id: $api_id})
        OPTIONAL MATCH (svc:Service)-[:HAS_COMPONENT]->(comp:Component)-[:EXPOSES_ENDPOINT]->(api)
        OPTIONAL MATCH (doc:Doc)-[:DESCRIBES_ENDPOINT]->(api)
        OPTIONAL MATCH (ge:GitEvent)-[:MODIFIES_API]->(api)
        OPTIONAL MATCH (se:SlackEvent)-[:COMPLAINS_ABOUT_API]->(api)
        RETURN
            collect(DISTINCT svc.id) AS services,
            collect(DISTINCT comp.id) AS components,
            collect(DISTINCT doc.id) AS docs,
            collect(DISTINCT ge.id)[0..$limit] AS git_events,
            collect(DISTINCT se.id)[0..$limit] AS slack_events
        """
        records = self.graph_service.run_query(query, {"api_id": scenario.api, "limit": max_events})
        if not records:
            return None

        record = records[0]
        return GraphSummary(
            api=scenario.api,
            services=sorted(filter(None, record.get("services", []))),
            components=sorted(filter(None, record.get("components", []))),
            docs=sorted(filter(None, record.get("docs", []))),
            git_events=list(filter(None, record.get("git_events", []))),
            slack_events=list(filter(None, record.get("slack_events", []))),
        )

    def _fallback_summary(self, scenario: DemoScenario, *, max_events: int) -> GraphSummary:
        components = [API_COMPONENT_MAP.get(scenario.api)] if scenario.api in API_COMPONENT_MAP else []
        components = [c for c in components if c]
        docs = [doc for doc, apis in DOC_API_MAP.items() if scenario.api in apis]
        component_docs = DOC_COMPONENT_MAP.copy()
        doc_components = component_docs.get(docs[0], []) if docs else []

        services = set(services_for_components(components + doc_components))

        git_events = self._load_event_ids(
            path=self.store_paths.get("git"),
            api=scenario.api,
            max_events=max_events,
        )
        slack_events = self._load_event_ids(
            path=self.store_paths.get("slack"),
            api=scenario.api,
            max_events=max_events,
        )

        return GraphSummary(
            api=scenario.api,
            services=sorted(services),
            components=sorted(set(components + doc_components)),
            docs=sorted(docs),
            git_events=git_events,
            slack_events=slack_events,
        )

    def _load_event_ids(self, *, path: Optional[Path], api: str, max_events: int) -> List[str]:
        if not path or not path.exists():
            return []
        try:
            records = json.loads(path.read_text())
        except json.JSONDecodeError:
            return []

        matching = []
        for record in records:
            apis = record.get("apis") or []
            if api in apis:
                matching.append(record.get("event_id"))
            if len(matching) >= max_events:
                break
        return [event_id for event_id in matching if event_id]

