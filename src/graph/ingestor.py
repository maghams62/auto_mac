"""
GraphIngestor - convenience helpers for upserting nodes/relationships.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Iterable, Optional

from .schema import NodeLabels, RelationshipTypes
from .service import GraphService

logger = logging.getLogger(__name__)


class GraphIngestor:
    """Provides small helpers for writing data into Neo4j."""

    def __init__(self, graph_service: GraphService):
        self.graph_service = graph_service

    def available(self) -> bool:
        return self.graph_service.is_available()

    def upsert_component(self, component_id: str, properties: Optional[Dict[str, str]] = None) -> None:
        self._merge_node(NodeLabels.COMPONENT, component_id, properties)

    def upsert_service(self, service_id: str, properties: Optional[Dict[str, str]] = None) -> None:
        self._merge_node(NodeLabels.SERVICE, service_id, properties)
        # Ensure service nodes carry a default name for readability

    def upsert_repository(self, repo_id: str, properties: Optional[Dict[str, str]] = None) -> None:
        self._merge_node(NodeLabels.REPOSITORY, repo_id, properties)

    def upsert_channel(self, channel_id: str, properties: Optional[Dict[str, Any]] = None) -> None:
        self._merge_node(NodeLabels.CHANNEL, channel_id, properties)

    def upsert_playlist(self, playlist_id: str, properties: Optional[Dict[str, Any]] = None) -> None:
        self._merge_node(NodeLabels.PLAYLIST, playlist_id, properties)

    def upsert_video(self, video_id: str, properties: Optional[Dict[str, Any]] = None) -> None:
        self._merge_node(NodeLabels.VIDEO, video_id, properties)

    def link_video_channel(self, video_id: str, channel_id: str) -> None:
        self._merge_relationship(
            NodeLabels.VIDEO,
            video_id,
            RelationshipTypes.BELONGS_TO_CHANNEL,
            NodeLabels.CHANNEL,
            channel_id,
        )

    def link_video_playlist(self, video_id: str, playlist_id: str) -> None:
        self._merge_relationship(
            NodeLabels.VIDEO,
            video_id,
            RelationshipTypes.PART_OF_PLAYLIST,
            NodeLabels.PLAYLIST,
            playlist_id,
        )

    def upsert_transcript_chunk(self, chunk_id: str, properties: Optional[Dict[str, Any]] = None) -> None:
        self._merge_node(NodeLabels.TRANSCRIPT_CHUNK, chunk_id, properties)

    def link_video_chunk(self, video_id: str, chunk_id: str) -> None:
        self._merge_relationship(
            NodeLabels.VIDEO,
            video_id,
            RelationshipTypes.HAS_CHUNK,
            NodeLabels.TRANSCRIPT_CHUNK,
            chunk_id,
        )

    def upsert_concept(self, concept_id: str, properties: Optional[Dict[str, Any]] = None) -> None:
        self._merge_node(NodeLabels.CONCEPT, concept_id, properties)

    def link_chunk_concept(self, chunk_id: str, concept_id: str, properties: Optional[Dict[str, Any]] = None) -> None:
        self._merge_relationship(
            NodeLabels.TRANSCRIPT_CHUNK,
            chunk_id,
            RelationshipTypes.MENTIONS_CONCEPT,
            NodeLabels.CONCEPT,
            concept_id,
            properties,
        )

    def link_service_component(self, service_id: str, component_id: str) -> None:
        self._merge_relationship(
            NodeLabels.SERVICE,
            service_id,
            RelationshipTypes.HAS_COMPONENT,
            NodeLabels.COMPONENT,
            component_id,
        )

    def link_repo_component(self, repo_id: str, component_id: str) -> None:
        self._merge_relationship(
            NodeLabels.REPOSITORY,
            repo_id,
            RelationshipTypes.REPO_OWNS_COMPONENT,
            NodeLabels.COMPONENT,
            component_id,
        )

    def link_repo_artifact(self, repo_id: str, artifact_id: str) -> None:
        self._merge_relationship(
            NodeLabels.REPOSITORY,
            repo_id,
            RelationshipTypes.REPO_OWNS_ARTIFACT,
            NodeLabels.CODE_ARTIFACT,
            artifact_id,
        )

    def link_component_dependency(
        self,
        source_component: str,
        target_component: str,
        properties: Optional[Dict[str, Any]] = None,
    ) -> None:
        self._merge_relationship(
            NodeLabels.COMPONENT,
            source_component,
            RelationshipTypes.COMPONENT_USES_COMPONENT,
            NodeLabels.COMPONENT,
            target_component,
            properties,
        )

    def link_service_calls_api(self, service_id: str, api_id: str) -> None:
        self._merge_relationship(
            NodeLabels.SERVICE,
            service_id,
            RelationshipTypes.SERVICE_CALLS_API,
            NodeLabels.API_ENDPOINT,
            api_id,
        )

    def upsert_code_artifact(
        self,
        artifact_id: str,
        component_ids: Iterable[str] = (),
        depends_on_ids: Iterable[str] = (),
        properties: Optional[Dict[str, str]] = None,
    ) -> None:
        """
        Upsert a CodeArtifact node and wire ownership/dependency relationships.
        """
        self._merge_node(NodeLabels.CODE_ARTIFACT, artifact_id, properties)
        for component_id in component_ids:
            self._merge_relationship(
                NodeLabels.COMPONENT,
                component_id,
                RelationshipTypes.OWNS_CODE,
                NodeLabels.CODE_ARTIFACT,
                artifact_id,
            )
        for dependency_id in depends_on_ids:
            self._merge_relationship(
                NodeLabels.CODE_ARTIFACT,
                artifact_id,
                RelationshipTypes.DEPENDS_ON,
                NodeLabels.CODE_ARTIFACT,
                dependency_id,
            )

    def upsert_doc(
        self,
        doc_id: str,
        component_ids: Iterable[str] = (),
        endpoint_ids: Iterable[str] = (),
        properties: Optional[Dict[str, str]] = None,
    ) -> None:
        self._merge_node(NodeLabels.DOC, doc_id, properties)
        for component_id in component_ids:
            self._merge_relationship(
                NodeLabels.DOC,
                doc_id,
                RelationshipTypes.DESCRIBES_COMPONENT,
                NodeLabels.COMPONENT,
                component_id,
            )
            self._merge_relationship(
                NodeLabels.DOC,
                doc_id,
                RelationshipTypes.DOC_DOCUMENTS_COMPONENT,
                NodeLabels.COMPONENT,
                component_id,
            )
        for endpoint_id in endpoint_ids:
            self._merge_relationship(
                NodeLabels.DOC,
                doc_id,
                RelationshipTypes.DESCRIBES_ENDPOINT,
                NodeLabels.API_ENDPOINT,
                endpoint_id,
            )
            self._merge_relationship(
                NodeLabels.DOC,
                doc_id,
                RelationshipTypes.DOC_DOCUMENTS_API,
                NodeLabels.API_ENDPOINT,
                endpoint_id,
            )

    def upsert_issue(
        self,
        issue_id: str,
        component_ids: Iterable[str] = (),
        endpoint_ids: Iterable[str] = (),
        doc_ids: Iterable[str] = (),
        properties: Optional[Dict[str, str]] = None,
    ) -> None:
        self._merge_node(NodeLabels.ISSUE, issue_id, properties)
        for component_id in component_ids:
            self._merge_relationship(
                NodeLabels.ISSUE,
                issue_id,
                RelationshipTypes.AFFECTS_COMPONENT,
                NodeLabels.COMPONENT,
                component_id,
            )
        for endpoint_id in endpoint_ids:
            self._merge_relationship(
                NodeLabels.ISSUE,
                issue_id,
                RelationshipTypes.REFERENCES_ENDPOINT,
                NodeLabels.API_ENDPOINT,
                endpoint_id,
            )
        for doc_id in doc_ids:
            self._merge_relationship(
                NodeLabels.ISSUE,
                issue_id,
                RelationshipTypes.IMPACTS_DOC,
                NodeLabels.DOC,
                doc_id,
            )

    def upsert_pr(
        self,
        pr_id: str,
        component_ids: Iterable[str] = (),
        endpoint_ids: Iterable[str] = (),
        properties: Optional[Dict[str, str]] = None,
    ) -> None:
        self._merge_node(NodeLabels.PR, pr_id, properties)
        for component_id in component_ids:
            self._merge_relationship(
                NodeLabels.PR,
                pr_id,
                RelationshipTypes.MODIFIES_COMPONENT,
                NodeLabels.COMPONENT,
                component_id,
            )

    def upsert_git_event(
        self,
        event_id: str,
        *,
        component_ids: Iterable[str] = (),
        endpoint_ids: Iterable[str] = (),
        properties: Optional[Dict[str, Any]] = None,
    ) -> None:
        self._merge_node(NodeLabels.GIT_EVENT, event_id, properties)
        for component_id in component_ids:
            self._merge_relationship(
                NodeLabels.GIT_EVENT,
                event_id,
                RelationshipTypes.TOUCHES_COMPONENT,
                NodeLabels.COMPONENT,
                component_id,
            )
        for endpoint_id in endpoint_ids:
            self._merge_relationship(
                NodeLabels.GIT_EVENT,
                event_id,
                RelationshipTypes.MODIFIES_API,
                NodeLabels.API_ENDPOINT,
                endpoint_id,
            )

    def link_git_event_to_pr(self, event_id: str, pr_id: str) -> None:
        self._merge_relationship(
            NodeLabels.GIT_EVENT,
            event_id,
            RelationshipTypes.DERIVED_FROM,
            NodeLabels.PR,
            pr_id,
        )

    def link_git_event_to_issue(self, event_id: str, issue_id: str) -> None:
        self._merge_relationship(
            NodeLabels.GIT_EVENT,
            event_id,
            RelationshipTypes.DERIVED_FROM,
            NodeLabels.ISSUE,
            issue_id,
        )
    def upsert_api_endpoint(
        self,
        api_id: str,
        component_id: Optional[str] = None,
        properties: Optional[Dict[str, str]] = None,
    ) -> None:
        self._merge_node(NodeLabels.API_ENDPOINT, api_id, properties)
        if component_id:
            self._merge_relationship(
                NodeLabels.COMPONENT,
                component_id,
                RelationshipTypes.EXPOSES_ENDPOINT,
                NodeLabels.API_ENDPOINT,
                api_id,
            )

    def upsert_slack_thread(
        self,
        thread_id: str,
        component_ids: Iterable[str] = (),
        issue_ids: Iterable[str] = (),
        properties: Optional[Dict[str, str]] = None,
    ) -> None:
        """
        Upsert a SlackThread node with relationships to components and issues.

        Args:
            thread_id: Unique thread identifier (e.g., "slack:C123456:1234567890.123456")
            component_ids: Components discussed in this thread
            issue_ids: Issues referenced in this thread
            properties: Optional properties (channel, started_at, topic, participants)
        """
        self._merge_node(NodeLabels.SLACK_THREAD, thread_id, properties)
        for component_id in component_ids:
            self._merge_relationship(
                NodeLabels.SLACK_THREAD,
                thread_id,
                RelationshipTypes.DISCUSSES_COMPONENT,
                NodeLabels.COMPONENT,
                component_id,
            )
        for issue_id in issue_ids:
            self._merge_relationship(
                NodeLabels.SLACK_THREAD,
                thread_id,
                RelationshipTypes.DISCUSSES_ISSUE,
                NodeLabels.ISSUE,
                issue_id,
            )

    def upsert_slack_event(
        self,
        event_id: str,
        *,
        component_ids: Iterable[str] = (),
        endpoint_ids: Iterable[str] = (),
        properties: Optional[Dict[str, Any]] = None,
    ) -> None:
        self._merge_node(NodeLabels.SLACK_EVENT, event_id, properties)
        for component_id in component_ids:
            self._merge_relationship(
                NodeLabels.SLACK_EVENT,
                event_id,
                RelationshipTypes.ABOUT_COMPONENT,
                NodeLabels.COMPONENT,
                component_id,
            )
        for endpoint_id in endpoint_ids:
            self._merge_relationship(
                NodeLabels.SLACK_EVENT,
                event_id,
                RelationshipTypes.COMPLAINS_ABOUT_API,
                NodeLabels.API_ENDPOINT,
                endpoint_id,
            )

    def upsert_activity_signal(
        self,
        signal_id: str,
        component_ids: Iterable[str] = (),
        endpoint_ids: Iterable[str] = (),
        properties: Optional[Dict[str, str]] = None,
        signal_weight: Optional[float] = None,
        last_seen: Optional[str] = None,
    ) -> None:
        """
        Upsert an ActivitySignal node and connect it to related components/endpoints.
        """
        self._merge_node(NodeLabels.ACTIVITY_SIGNAL, signal_id, properties)
        rel_props = self._build_signal_properties(signal_weight, last_seen)
        for component_id in component_ids:
            self._merge_relationship(
                NodeLabels.ACTIVITY_SIGNAL,
                signal_id,
                RelationshipTypes.SIGNALS_COMPONENT,
                NodeLabels.COMPONENT,
                component_id,
                rel_props,
            )
        for endpoint_id in endpoint_ids:
            self._merge_relationship(
                NodeLabels.ACTIVITY_SIGNAL,
                signal_id,
                RelationshipTypes.SIGNALS_ENDPOINT,
                NodeLabels.API_ENDPOINT,
                endpoint_id,
                rel_props,
            )

    def upsert_support_case(
        self,
        case_id: str,
        component_ids: Iterable[str] = (),
        endpoint_ids: Iterable[str] = (),
        properties: Optional[Dict[str, str]] = None,
        sentiment_weight: Optional[float] = None,
        last_seen: Optional[str] = None,
    ) -> None:
        """
        Upsert a SupportCase node and link it to impacted components/endpoints.
        """
        self._merge_node(NodeLabels.SUPPORT_CASE, case_id, properties)
        rel_props = self._build_signal_properties(sentiment_weight, last_seen)
        for component_id in component_ids:
            self._merge_relationship(
                NodeLabels.SUPPORT_CASE,
                case_id,
                RelationshipTypes.SUPPORTS_COMPONENT,
                NodeLabels.COMPONENT,
                component_id,
                rel_props,
            )
        for endpoint_id in endpoint_ids:
            self._merge_relationship(
                NodeLabels.SUPPORT_CASE,
                case_id,
                RelationshipTypes.SUPPORTS_ENDPOINT,
                NodeLabels.API_ENDPOINT,
                endpoint_id,
                rel_props,
            )

    def upsert_impact_event(
        self,
        event_id: str,
        *,
        properties: Optional[Dict[str, Any]] = None,
        component_ids: Iterable[str] = (),
        service_ids: Iterable[str] = (),
        doc_ids: Iterable[str] = (),
        slack_thread_ids: Iterable[str] = (),
        git_event_ids: Iterable[str] = (),
    ) -> None:
        self._merge_node(NodeLabels.IMPACT_EVENT, event_id, properties)
        for component_id in component_ids:
            self._merge_relationship(
                NodeLabels.IMPACT_EVENT,
                event_id,
                RelationshipTypes.IMPACTS_COMPONENT,
                NodeLabels.COMPONENT,
                component_id,
            )
        for service_id in service_ids:
            self._merge_relationship(
                NodeLabels.IMPACT_EVENT,
                event_id,
                RelationshipTypes.IMPACTS_SERVICE,
                NodeLabels.SERVICE,
                service_id,
            )
        for doc_id in doc_ids:
            self._merge_relationship(
                NodeLabels.IMPACT_EVENT,
                event_id,
                RelationshipTypes.IMPACTS_DOC,
                NodeLabels.DOC,
                doc_id,
            )
        for slack_id in slack_thread_ids:
            self._merge_relationship(
                NodeLabels.IMPACT_EVENT,
                event_id,
                RelationshipTypes.DERIVED_FROM,
                NodeLabels.SLACK_THREAD,
                slack_id,
            )
        for git_id in git_event_ids:
            self._merge_relationship(
                NodeLabels.IMPACT_EVENT,
                event_id,
                RelationshipTypes.DERIVED_FROM,
                NodeLabels.GIT_EVENT,
                git_id,
            )

    def _merge_node(self, label: NodeLabels, node_id: str, properties: Optional[Dict[str, str]]) -> None:
        if not (self.graph_service.is_available() and node_id):
            return
        props = properties or {}
        query = f"""
        MERGE (n:{label.value} {{id: $id}})
        SET n += $props
        """
        self.graph_service.run_write(query, {"id": node_id, "props": props})

    def _merge_relationship(
        self,
        source_label: NodeLabels,
        source_id: str,
        rel_type: RelationshipTypes,
        target_label: NodeLabels,
        target_id: str,
        properties: Optional[Dict[str, Any]] = None,
    ) -> None:
        if not self.graph_service.is_available():
            return
        if not source_id or not target_id:
            return

        query = f"""
        MERGE (source:{source_label.value} {{id: $source_id}})
        MERGE (target:{target_label.value} {{id: $target_id}})
        MERGE (source)-[rel:{rel_type.value}]->(target)
        SET rel += $props
        """
        self.graph_service.run_write(
            query,
            {
                "source_id": source_id,
                "target_id": target_id,
                "props": properties or {},
            },
        )

    @staticmethod
    def _build_signal_properties(
        weight: Optional[float],
        last_seen: Optional[str],
    ) -> Dict[str, Any]:
        props: Dict[str, Any] = {}
        if weight is not None:
            props["signal_weight"] = weight
        if last_seen:
            props["last_seen"] = last_seen
        return props
