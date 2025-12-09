"""
Rule-based impact analyzer that maps git/slack signals to downstream blast radius.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Set, Tuple

from ..config.models import ImpactSettings
from ..config.context import get_config_context
from ..graph import DependencyGraph, DependencyGraphBuilder, GraphService
from .models import (
    GitChangePayload,
    GitFileChange,
    ImpactEntityType,
    ImpactRecommendation,
    ImpactReport,
    ImpactedEntity,
    ImpactLevel,
    SlackComplaintContext,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ComponentDependencyInfo:
    depth: int
    relation: str
    confidence: float


def _group_files_by_component(
    files: Iterable[GitFileChange],
    graph: DependencyGraph,
    default_repo: str,
) -> Dict[str, List[GitFileChange]]:
    grouped: Dict[str, List[GitFileChange]] = defaultdict(list)
    for file_change in files:
        repo = file_change.repo or default_repo
        candidates = graph.components_for_file(repo, file_change.path)
        for component_id in candidates:
            grouped[component_id].append(file_change)
    return grouped


class ImpactAnalyzer:
    """Computes structured impact reports for git changes."""

    def __init__(
        self,
        dependency_graph: Optional[DependencyGraph] = None,
        *,
        graph_service: Optional[GraphService] = None,
        impact_settings: Optional[ImpactSettings] = None,
    ):
        if dependency_graph is None:
            ctx = get_config_context()
            self.dependency_graph = DependencyGraphBuilder(ctx.data, graph_service=graph_service).build(
                write_to_graph=False
            )
        else:
            self.dependency_graph = dependency_graph
        self.graph_service = graph_service
        self.impact_settings = impact_settings or self.dependency_graph.settings.impact

    def analyze_git_change(
        self,
        change: GitChangePayload,
        slack_context: Optional[SlackComplaintContext] = None,
        seed_components: Optional[Set[str]] = None,
    ) -> ImpactReport:
        grouped = _group_files_by_component(change.files, self.dependency_graph, change.repo)
        if seed_components:
            for component_id in seed_components:
                grouped.setdefault(component_id, [])
        changed_component_entities = self._build_component_entities(grouped)
        changed_component_ids = {entity.entity_id for entity in changed_component_entities}

        downstream_components = self._walk_component_dependencies(changed_component_ids)
        impacted_component_entities = self._build_downstream_entities(downstream_components, changed_component_ids)

        impacted_docs = self._collect_impacted_docs(changed_component_ids, downstream_components)
        changed_apis, impacted_apis = self._collect_api_entities(changed_component_ids, downstream_components)
        impacted_services = self._collect_impacted_services(changed_component_ids, downstream_components)
        slack_threads = self._collect_slack_entities(slack_context, changed_component_ids, downstream_components)

        recommendations = self._build_recommendations(
            docs=impacted_docs,
            services=impacted_services,
            slack_threads=slack_threads,
        )

        metadata = {
            "change": change.to_dict(),
            "slack_context": slack_context.to_dict() if slack_context else None,
            "changed_component_ids": sorted(changed_component_ids),
            "changed_api_ids": sorted({api.entity_id for api in changed_apis}),
            "impacted_component_ids": sorted({entity.entity_id for entity in impacted_component_entities}),
        }

        impact_level = self._derive_report_level(
            changed_component_entities,
            impacted_component_entities,
            impacted_services,
            impacted_docs,
        )

        return ImpactReport(
            change_id=change.identifier,
            change_title=change.title,
            change_summary=change.description,
            impact_level=impact_level,
            changed_components=changed_component_entities,
            changed_apis=changed_apis,
            impacted_components=impacted_component_entities,
            impacted_services=impacted_services,
            impacted_docs=impacted_docs,
            impacted_apis=impacted_apis,
            slack_threads=slack_threads,
            recommendations=recommendations,
            metadata=metadata,
        )

    # ------------------------------------------------------------------
    # Builders

    def _build_component_entities(
        self,
        grouped: Dict[str, List[GitFileChange]],
    ) -> List[ImpactedEntity]:
        entities: List[ImpactedEntity] = []
        for component_id, files in grouped.items():
            reason = f"{len(files)} file(s) mapped to {component_id}"
            metadata = {
                "files": [file.to_dict() for file in files],
                "source": "git_change",
            }
            confidence = 0.95
            entities.append(
                ImpactedEntity(
                    entity_id=component_id,
                    entity_type=ImpactEntityType.COMPONENT,
                    confidence=confidence,
                    reason=reason,
                    impact_level=self._level_for_confidence(confidence),
                    metadata=metadata,
                )
            )
        return entities

    def _walk_component_dependencies(self, seeds: Set[str]) -> Dict[str, ComponentDependencyInfo]:
        """
        Traverse reverse component edges so we surface downstream dependents when an upstream component changes.
        Adds confidence scoring, relation metadata, and guards against cycles.
        """
        max_depth = max(1, self.impact_settings.default_max_depth)
        dependency_map: Dict[str, ComponentDependencyInfo] = {}

        def traverse(component_id: str, depth: int, chain: Set[str]) -> None:
            if depth >= max_depth:
                return
            dependents = self.dependency_graph.reverse_component_dependencies.get(component_id, set())
            for dependent in dependents:
                if dependent in seeds or dependent in chain:
                    continue
                next_depth = depth + 1
                relation = "direct" if next_depth == 1 else "indirect"
                confidence = self._dependency_confidence(next_depth)
                existing = dependency_map.get(dependent)
                if existing and existing.depth <= next_depth:
                    continue
                dependency_map[dependent] = ComponentDependencyInfo(
                    depth=next_depth,
                    relation=relation,
                    confidence=confidence,
                )
                traverse(dependent, next_depth, chain | {dependent})

        for seed in seeds:
            traverse(seed, 0, {seed})

        return dependency_map

    @staticmethod
    def _dependency_confidence(depth: int) -> float:
        """
        Depth-aware confidence: direct dependencies (depth=1) score highest with gradual decay.
        """
        score = 0.9 - 0.15 * (depth - 1)
        return max(0.4, round(score, 3))

    def _build_downstream_entities(
        self,
        downstream: Dict[str, ComponentDependencyInfo],
        changed_component_ids: Set[str],
    ) -> List[ImpactedEntity]:
        entities: List[ImpactedEntity] = []
        joined_changed = "/".join(sorted(changed_component_ids))
        for component_id, info in downstream.items():
            reason = f"{info.relation.title()} dependency on {joined_changed} (depth={info.depth})"
            confidence = max(0.5, info.confidence)
            entities.append(
                ImpactedEntity(
                    entity_id=component_id,
                    entity_type=ImpactEntityType.COMPONENT,
                    confidence=confidence,
                    reason=reason,
                    impact_level=self._level_for_confidence(confidence),
                    metadata={
                        "dependency_depth": info.depth,
                        "dependency_relation": info.relation,
                    },
                )
            )
        return entities

    def _collect_impacted_docs(
        self,
        changed_components: Set[str],
        downstream_components: Dict[str, ComponentDependencyInfo],
    ) -> List[ImpactedEntity]:
        if not self.impact_settings.include_docs:
            return []

        entities: List[ImpactedEntity] = []
        visited: Set[str] = set()

        def _add_doc(
            doc_id: str,
            component_id: str,
            confidence: float,
            reason_prefix: str,
            relation: Optional[str],
            depth: int,
        ) -> None:
            if doc_id in visited:
                return
            visited.add(doc_id)
            reason = f"{reason_prefix} {component_id}"
            metadata = {"component_id": component_id}
            if relation:
                metadata["dependency_relation"] = relation
            if depth:
                metadata["dependency_depth"] = depth
            level = self._level_for_confidence(confidence)
            entities.append(
                ImpactedEntity(
                    entity_id=doc_id,
                    entity_type=ImpactEntityType.DOC,
                    confidence=confidence,
                    reason=reason,
                    impact_level=level,
                    metadata=metadata,
                )
            )

        for component_id in changed_components:
            for doc_id in self.dependency_graph.docs_for_component(component_id):
                _add_doc(doc_id, component_id, 0.85, "Documents changed component", "direct", 0)

        for component_id, info in downstream_components.items():
            confidence = max(0.4, info.confidence - 0.05)
            relation = info.relation
            for doc_id in self.dependency_graph.docs_for_component(component_id):
                _add_doc(
                    doc_id,
                    component_id,
                    confidence,
                    f"Documents {relation} dependency",
                    relation,
                    info.depth,
                )

        return entities

    def _collect_api_entities(
        self,
        changed_components: Set[str],
        downstream_components: Dict[str, ComponentDependencyInfo],
    ) -> Tuple[List[ImpactedEntity], List[ImpactedEntity]]:
        changed: List[ImpactedEntity] = []
        impacted: List[ImpactedEntity] = []
        impacted_map: Dict[str, ImpactedEntity] = {}

        for component_id in changed_components:
            for api_id in self.dependency_graph.apis_for_component(component_id):
                confidence = 0.9
                changed.append(
                    ImpactedEntity(
                        entity_id=api_id,
                        entity_type=ImpactEntityType.API,
                        confidence=confidence,
                        reason="API owned by changed component",
                        impact_level=self._level_for_confidence(confidence),
                        metadata={"components": [component_id]},
                    )
                )

        for component_id, info in downstream_components.items():
            for api_id in self.dependency_graph.apis_for_component(component_id):
                confidence = max(0.4, info.confidence - 0.1)
                entity = impacted_map.get(api_id)
                if entity:
                    if confidence > entity.confidence:
                        entity.confidence = confidence
                        entity.reason = "API owned by dependent component"
                        entity.impact_level = self._level_for_confidence(confidence)
                    components = set(entity.metadata.get("components") or [])
                    components.add(component_id)
                    entity.metadata["components"] = sorted(components)
                    continue
                impacted_map[api_id] = ImpactedEntity(
                    entity_id=api_id,
                    entity_type=ImpactEntityType.API,
                    confidence=confidence,
                    reason="API owned by dependent component",
                    impact_level=self._level_for_confidence(confidence),
                    metadata={
                        "components": [component_id],
                        "dependency_relation": info.relation,
                        "dependency_depth": info.depth,
                    },
                )

        return changed, list(impacted_map.values())

    def _collect_impacted_services(
        self,
        changed_components: Set[str],
        downstream_components: Dict[str, ComponentDependencyInfo],
    ) -> List[ImpactedEntity]:
        if not self.impact_settings.include_services:
            return []

        service_map: Dict[str, ImpactedEntity] = {}
        all_components = set(changed_components) | set(downstream_components.keys())

        for component_id in all_components:
            service_id = self.dependency_graph.service_for_component(component_id)
            if not service_id:
                continue
            if component_id in changed_components:
                confidence = 0.9
                reason = "Owns changed component"
                relation = "changed"
            else:
                info = downstream_components.get(component_id)
                confidence = info.confidence if info else 0.6
                relation = info.relation if info else "indirect"
                reason = (
                    "Direct dependency on changed component"
                    if relation == "direct"
                    else "Depends on changed component"
                )
            existing = service_map.get(service_id)
            metadata = {"component_id": component_id}
            level = self._level_for_confidence(confidence)
            entity = ImpactedEntity(
                entity_id=service_id,
                entity_type=ImpactEntityType.SERVICE,
                confidence=confidence,
                reason=reason,
                impact_level=level,
                metadata={**metadata, "dependency_relation": relation},
            )
            if existing is None or confidence > existing.confidence:
                service_map[service_id] = entity

        return list(service_map.values())

    def _collect_slack_entities(
        self,
        slack_context: Optional[SlackComplaintContext],
        changed_components: Set[str],
        downstream_components: Dict[str, ComponentDependencyInfo],
    ) -> List[ImpactedEntity]:
        if not (slack_context and self.impact_settings.include_slack_threads):
            return []
        mentioned_components = set(slack_context.component_ids or [])
        intersecting_components = list(mentioned_components & (changed_components | set(downstream_components.keys())))
        reason = (
            "Slack complaint overlaps changed components"
            if intersecting_components
            else "Slack complaint mapped to monitored components"
        )
        confidence = 0.7 if intersecting_components else 0.5
        metadata = slack_context.to_dict()
        metadata["matching_components"] = intersecting_components
        level = self._level_for_confidence(confidence)
        return [
            ImpactedEntity(
                entity_id=slack_context.thread_id,
                entity_type=ImpactEntityType.SLACK_THREAD,
                confidence=confidence,
                reason=reason,
                impact_level=level,
                metadata=metadata,
            )
        ]

    def _build_recommendations(
        self,
        *,
        docs: List[ImpactedEntity],
        services: List[ImpactedEntity],
        slack_threads: List[ImpactedEntity],
    ) -> List[ImpactRecommendation]:
        recs: List[ImpactRecommendation] = []

        for doc in docs[: self.impact_settings.max_recommendations]:
            recs.append(
                ImpactRecommendation(
                    description=f"Review and refresh {doc.entity_id}",
                    reason=doc.reason,
                    confidence=doc.confidence,
                    related_entities=[doc.entity_id],
                )
            )

        for service in services[: self.impact_settings.max_recommendations]:
            recs.append(
                ImpactRecommendation(
                    description=f"Coordinate regression tests with {service.entity_id}",
                    reason=service.reason,
                    confidence=service.confidence,
                    related_entities=[service.entity_id],
                )
            )

        for slack in slack_threads:
            recs.append(
                ImpactRecommendation(
                    description=f"Respond in Slack thread {slack.entity_id}",
                    reason=slack.reason,
                    confidence=slack.confidence,
                    related_entities=[slack.entity_id],
                )
            )

        return recs

    # ------------------------------------------------------------------
    # Severity helpers

    @staticmethod
    def _level_for_confidence(confidence: float) -> ImpactLevel:
        if confidence >= 0.8:
            return ImpactLevel.HIGH
        if confidence >= 0.5:
            return ImpactLevel.MEDIUM
        return ImpactLevel.LOW

    def _derive_report_level(
        self,
        changed_components: List[ImpactedEntity],
        impacted_components: List[ImpactedEntity],
        impacted_services: List[ImpactedEntity],
        impacted_docs: List[ImpactedEntity],
    ) -> ImpactLevel:
        confidences: List[float] = []
        confidences.extend(entity.confidence for entity in changed_components)
        confidences.extend(entity.confidence for entity in impacted_components)
        confidences.extend(entity.confidence for entity in impacted_services)
        confidences.extend(entity.confidence for entity in impacted_docs)
        if not confidences:
            return ImpactLevel.LOW
        max_conf = max(confidences)
        return self._level_for_confidence(max_conf)

