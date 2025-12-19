"""
Dependency graph builder for cross-system impact analysis.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import yaml

from ..config_validator import ConfigAccessor
from ..config.models import ContextResolutionSettings
from ..utils import load_config
from .ingestor import GraphIngestor
from .schema import NodeLabels, RelationshipTypes
from .service import GraphService

logger = logging.getLogger(__name__)


def _normalize_path(value: str) -> str:
    value = value.strip()
    if not value:
        return value
    return value.replace("\\", "/").lstrip("./")


@dataclass
class DependencyGraph:
    """In-memory representation of services, components, and docs."""

    settings: ContextResolutionSettings
    components: Dict[str, Dict[str, str]] = field(default_factory=dict)
    services: Dict[str, Dict[str, str]] = field(default_factory=dict)
    repositories: Dict[str, Dict[str, str]] = field(default_factory=dict)
    apis: Dict[str, Dict[str, str]] = field(default_factory=dict)
    docs: Dict[str, Dict[str, str]] = field(default_factory=dict)
    artifacts: Dict[str, Dict[str, str]] = field(default_factory=dict)
    component_to_repo: Dict[str, str] = field(default_factory=dict)
    component_to_service: Dict[str, str] = field(default_factory=dict)
    component_to_apis: Dict[str, Set[str]] = field(default_factory=lambda: defaultdict(set))
    component_to_docs: Dict[str, Set[str]] = field(default_factory=lambda: defaultdict(set))
    doc_to_components: Dict[str, Set[str]] = field(default_factory=lambda: defaultdict(set))
    doc_to_apis: Dict[str, Set[str]] = field(default_factory=lambda: defaultdict(set))
    component_dependencies: Dict[str, Set[str]] = field(default_factory=lambda: defaultdict(set))
    reverse_component_dependencies: Dict[str, Set[str]] = field(default_factory=lambda: defaultdict(set))
    service_api_calls: Dict[str, Set[str]] = field(default_factory=lambda: defaultdict(set))
    file_component_index: Dict[str, List[Tuple[str, str]]] = field(default_factory=lambda: defaultdict(list))
    artifact_to_component: Dict[str, str] = field(default_factory=dict)
    _pending_artifact_edges: List[Tuple[str, str]] = field(default_factory=list)

    def finalize(self) -> None:
        """Resolve pending dependency edges and prepare reverse lookups."""
        for source_artifact, depends_on in self._pending_artifact_edges:
            src_comp = self.artifact_to_component.get(source_artifact)
            dst_comp = self.artifact_to_component.get(depends_on)
            if not src_comp or not dst_comp or src_comp == dst_comp:
                continue
            self.component_dependencies[src_comp].add(dst_comp)
        for src, targets in self.component_dependencies.items():
            for target in targets:
                self.reverse_component_dependencies[target].add(src)
        self._pending_artifact_edges.clear()

    def register_file_mapping(self, repo: str, path: str, component_id: str) -> None:
        for repo_key in self._repo_lookup_keys(repo):
            normalized = _normalize_path(path)
            if not normalized:
                continue
            self.file_component_index[repo_key].append((normalized, component_id))

    def components_for_file(self, repo: str, file_path: str) -> Set[str]:
        normalized = _normalize_path(file_path)
        if not normalized:
            return set()
        matches: Set[str] = set()
        best_length = -1

        for repo_key in self._repo_lookup_keys(repo):
            patterns = self.file_component_index.get(repo_key, [])
            for pattern, component_id in patterns:
                if normalized == pattern or normalized.startswith(f"{pattern.rstrip('/')}/"):
                    pattern_length = len(pattern)
                    if pattern_length > best_length:
                        matches = {component_id}
                        best_length = pattern_length
                    elif pattern_length == best_length:
                        matches.add(component_id)
        return matches

    @staticmethod
    def _repo_lookup_keys(repo: str) -> List[str]:
        if not repo:
            return []
        trimmed = repo.strip()
        if not trimmed:
            return []
        keys = [trimmed]
        if "/" in trimmed:
            alias = trimmed.split("/", 1)[-1].strip()
            if alias:
                keys.append(alias)
        # Deduplicate while preserving order
        seen: Set[str] = set()
        unique_keys: List[str] = []
        for key in keys:
            if key in seen:
                continue
            seen.add(key)
            unique_keys.append(key)
        return unique_keys

    def service_for_component(self, component_id: str) -> Optional[str]:
        return self.component_to_service.get(component_id)

    def docs_for_component(self, component_id: str) -> Set[str]:
        return set(self.component_to_docs.get(component_id, set()))

    def apis_for_component(self, component_id: str) -> Set[str]:
        return set(self.component_to_apis.get(component_id, set()))


class DependencyGraphBuilder:
    """Loads canonical dependency maps and syncs them with the graph store."""

    def __init__(
        self,
        config: Optional[Dict[str, object]] = None,
        *,
        graph_service: Optional[GraphService] = None,
    ):
        self.config = config or load_config()
        self.accessor = ConfigAccessor(self.config)
        self.settings = self.accessor.get_context_resolution_settings()
        self.graph_service = graph_service or GraphService(self.config)
        self.ingestor = GraphIngestor(self.graph_service)

    def build(self, *, write_to_graph: bool = True) -> DependencyGraph:
        graph = DependencyGraph(settings=self.settings)
        for file_path in self.settings.dependency_files:
            self._ingest_file(Path(file_path), graph, write_to_graph)
        graph.finalize()
        if write_to_graph:
            self._sync_service_api_edges(graph)
        return graph

    # ------------------------------------------------------------------
    # Ingestion helpers

    def _ingest_file(self, path: Path, graph: DependencyGraph, write: bool) -> None:
        if not path.exists():
            logger.warning("[DEPENDENCY GRAPH] File not found: %s", path)
            return
        try:
            data = yaml.safe_load(path.read_text()) or {}
        except yaml.YAMLError as exc:
            logger.error("[DEPENDENCY GRAPH] Failed to parse %s: %s", path, exc)
            return

        for component_entry in data.get("components", []) or []:
            self._ingest_component(component_entry, graph, write)

        for dependency_entry in data.get("dependencies", []) or []:
            self._ingest_dependency(dependency_entry, graph, write)

    def _ingest_component(self, entry: Dict[str, object], graph: DependencyGraph, write: bool) -> None:
        component_id = entry.get("id")
        if not component_id:
            logger.warning("[DEPENDENCY GRAPH] Skipping component entry without id: %s", entry)
            return
        component_id = str(component_id)
        component_repo = str(entry.get("repo", "") or "")

        component_metadata = {
            key: value
            for key, value in entry.items()
            if key not in {"artifacts", "endpoints", "docs", "id"}
        }
        graph.components[component_id] = component_metadata
        if component_repo:
            graph.component_to_repo[component_id] = component_repo
            repo_id = f"repo:{component_repo}"
            graph.repositories.setdefault(repo_id, {"name": component_repo})
            if write and self.ingestor.available():
                self.ingestor.upsert_repository(repo_id, {"name": component_repo})
                self.ingestor.link_repo_component(repo_id, component_id)

        if write and self.ingestor.available():
            self.ingestor.upsert_component(component_id, properties=component_metadata)

        service_id = str(entry.get("service_id") or component_id.replace("comp:", "svc:"))
        if service_id:
            graph.services.setdefault(service_id, {"component_id": component_id})
            graph.component_to_service[component_id] = service_id
            if write and self.ingestor.available():
                self.ingestor.upsert_service(service_id, {"component_id": component_id})
                self.ingestor.link_service_component(service_id, component_id)

        for artifact in entry.get("artifacts", []) or []:
            self._ingest_artifact(component_id, artifact, graph, write)

        for endpoint in entry.get("endpoints", []) or []:
            self._ingest_endpoint(component_id, endpoint, graph, write)

        for doc in entry.get("docs", []) or []:
            self._ingest_doc(component_id, doc, graph, write)

    def _ingest_artifact(
        self,
        component_id: str,
        artifact: Dict[str, object],
        graph: DependencyGraph,
        write: bool,
    ) -> None:
        artifact_id = artifact.get("id")
        if not artifact_id:
            return
        artifact_id = str(artifact_id)
        artifact_repo = str(artifact.get("repo", "") or graph.component_to_repo.get(component_id, ""))
        artifact_path = str(artifact.get("path", "") or "")
        artifact_props = {
            key: value for key, value in artifact.items() if key not in {"id", "depends_on"}
        }
        graph.artifacts[artifact_id] = artifact_props
        graph.artifact_to_component[artifact_id] = component_id

        if artifact_repo and artifact_path:
            graph.register_file_mapping(artifact_repo, artifact_path, component_id)
            if write and self.ingestor.available():
                repo_id = f"repo:{artifact_repo}"
                graph.repositories.setdefault(repo_id, {"name": artifact_repo})
                self.ingestor.upsert_repository(repo_id, {"name": artifact_repo})
                self.ingestor.link_repo_artifact(repo_id, artifact_id)

        depends_on = artifact.get("depends_on", []) or []
        for dependency_id in depends_on:
            graph._pending_artifact_edges.append((artifact_id, str(dependency_id)))

        if write and self.ingestor.available():
            self.ingestor.upsert_code_artifact(
                artifact_id=artifact_id,
                component_ids=[component_id],
                depends_on_ids=depends_on,
                properties=artifact_props,
            )

    def _ingest_endpoint(
        self,
        component_id: str,
        endpoint: Dict[str, object],
        graph: DependencyGraph,
        write: bool,
    ) -> None:
        endpoint_id = endpoint.get("id")
        if not endpoint_id:
            return
        endpoint_id = str(endpoint_id)
        graph.apis[endpoint_id] = {k: v for k, v in endpoint.items() if k != "id"}
        graph.component_to_apis[component_id].add(endpoint_id)

        if write and self.ingestor.available():
            self.ingestor.upsert_api_endpoint(
                api_id=endpoint_id,
                component_id=component_id,
                properties=graph.apis[endpoint_id],
            )

    def _ingest_doc(
        self,
        component_id: str,
        doc: Dict[str, object],
        graph: DependencyGraph,
        write: bool,
    ) -> None:
        doc_id = doc.get("id")
        if not doc_id:
            return
        doc_id = str(doc_id)
        doc_props = {k: v for k, v in doc.items() if k not in {"id", "api_ids"}}
        api_ids = [str(api_id) for api_id in doc.get("api_ids", []) or []]

        graph.docs[doc_id] = doc_props
        graph.component_to_docs[component_id].add(doc_id)
        graph.doc_to_components[doc_id].add(component_id)
        if api_ids:
            for api_id in api_ids:
                graph.doc_to_apis[doc_id].add(api_id)

        if write and self.ingestor.available():
            self.ingestor.upsert_doc(
                doc_id,
                component_ids=[component_id],
                endpoint_ids=api_ids,
                properties=doc_props,
            )

    def _ingest_dependency(
        self,
        entry: Dict[str, object],
        graph: DependencyGraph,
        write: bool,
    ) -> None:
        source = entry.get("from_component")
        target = entry.get("to_component")
        if source and target:
            src_id = str(source)
            dst_id = str(target)
            graph.component_dependencies[src_id].add(dst_id)
            graph.reverse_component_dependencies[dst_id].add(src_id)
            if write and self.ingestor.available():
                self.ingestor.link_component_dependency(
                    src_id,
                    dst_id,
                    {"reason": entry.get("reason")},
                )

    def _sync_service_api_edges(self, graph: DependencyGraph) -> None:
        if not self.ingestor.available():
            return
        for component_id, downstream_components in graph.component_dependencies.items():
            service_id = graph.service_for_component(component_id)
            if not service_id:
                continue
            for dependent in downstream_components:
                api_ids = graph.apis_for_component(dependent)
                for api_id in api_ids:
                    self.ingestor.link_service_calls_api(service_id, api_id)
                    graph.service_api_calls[service_id].add(api_id)


__all__ = ["DependencyGraphBuilder", "DependencyGraph"]


def _main() -> None:
    builder = DependencyGraphBuilder()
    graph = builder.build(write_to_graph=True)
    logger.info(
        "[DEPENDENCY GRAPH] Loaded %s components, %s services, %s docs",
        len(graph.components),
        len(graph.services),
        len(graph.docs),
    )


if __name__ == "__main__":
    _main()

