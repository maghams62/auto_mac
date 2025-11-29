"""
Context resolution service for cross-repo impact analysis.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from ..graph import GraphService

logger = logging.getLogger(__name__)


class ContextResolutionService:
    """
    Provides blast-radius analysis for API/component changes.
    """

    def __init__(
        self,
        graph_service: GraphService,
        default_max_depth: int = 2,
        context_config: Optional[Dict[str, Any]] = None,
    ):
        self.graph_service = graph_service
        self.default_max_depth = max(1, default_max_depth)
        self.context_config = context_config or {}
        self.repo_strategy = self.context_config.get("repo_mode", "polyrepo").lower()
        self.default_include_cross_repo = self.repo_strategy != "monorepo"
        self.default_activity_window_hours = self.context_config.get("activity_window_hours", 168)

    def is_available(self) -> bool:
        return self.graph_service.is_available()

    def resolve_impacts(
        self,
        api_id: Optional[str] = None,
        component_id: Optional[str] = None,
        max_depth: Optional[int] = None,
        include_docs: bool = True,
        include_services: bool = True,
    ) -> Dict[str, Any]:
        if not self.is_available():
            return {"impacts": []}
        if not api_id and not component_id:
            raise ValueError("api_id or component_id required")

        depth = max(1, max_depth or self.default_max_depth)
        params = {
            "api_id": api_id,
            "component_id": component_id,
            "depth": depth,
        }

        query = """
        CALL {
            WITH $api_id AS api_id, $component_id AS component_id
            MATCH (target:Component)
            WHERE
                (api_id IS NOT NULL AND EXISTS {
                    MATCH (target)-[:EXPOSES_ENDPOINT]->(:APIEndpoint {id: api_id})
                })
                OR (component_id IS NOT NULL AND target.id = component_id)
            RETURN DISTINCT target
        }
        OPTIONAL MATCH (target)-[:EXPOSES_ENDPOINT]->(api:APIEndpoint)
        OPTIONAL MATCH (dependentArtifact:CodeArtifact)-[:DEPENDS_ON*1..$depth]->(:CodeArtifact)<-[:OWNS_CODE]-(target)
        OPTIONAL MATCH (dependentComponent:Component)-[:OWNS_CODE]->(dependentArtifact)
        OPTIONAL MATCH (doc:Doc)-[:DESCRIBES_COMPONENT|DESCRIBES_ENDPOINT]->(target)
        OPTIONAL MATCH (service:Service)-[:CALLS_ENDPOINT]->(api)
        WITH target,
             collect(DISTINCT dependentComponent.id) AS impacted_components,
             collect(DISTINCT doc.id) AS docs,
             collect(DISTINCT service.id) AS services,
             collect(DISTINCT api.id) AS apis
        RETURN target.id AS component_id,
               apis AS exposed_apis,
               impacted_components AS dependents,
               docs AS docs,
               services AS services
        """

        rows = self.graph_service.run_query(query, params)
        results = []
        for row in rows:
            entry = {
                "component_id": row.get("component_id"),
                "exposed_apis": row.get("exposed_apis", []),
                "dependent_components": row.get("dependents", []),
            }
            if include_docs:
                entry["docs"] = row.get("docs", [])
            if include_services:
                entry["services"] = row.get("services", [])
            results.append(entry)

        return {
            "api_id": api_id,
            "component_id": component_id,
            "max_depth": depth,
            "impacts": results,
        }

    def resolve_change_impacts(
        self,
        component_id: Optional[str] = None,
        artifact_ids: Optional[List[str]] = None,
        max_depth: Optional[int] = None,
        include_docs: bool = True,
        include_activity: bool = True,
        include_cross_repo: Optional[bool] = None,
        activity_window_hours: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Given a component or specific artifacts, return downstream components/docs to update.
        """
        if not self.is_available():
            return {"impacts": []}
        if not component_id and not artifact_ids:
            raise ValueError("component_id or artifact_ids required")

        depth = max(1, max_depth or self.default_max_depth)
        include_cross = (
            self.default_include_cross_repo if include_cross_repo is None else include_cross_repo
        )
        window_hours = activity_window_hours or self.default_activity_window_hours
        cutoff = self._cutoff_iso(window_hours)
        artifact_ids = artifact_ids or []

        query = """
        CALL {
            WITH $component_id AS component_id, $artifact_ids AS artifact_ids
            WITH coalesce(artifact_ids, []) AS explicit_ids, component_id
            OPTIONAL MATCH (seed:Component {id: component_id})-[:OWNS_CODE]->(owned:CodeArtifact)
            WITH explicit_ids + collect(DISTINCT owned.id) AS combined
            UNWIND combined AS artifact_id
            WITH DISTINCT artifact_id
            MATCH (root:CodeArtifact {id: artifact_id})
            RETURN collect(root) AS roots
        }
        UNWIND roots AS root
        OPTIONAL MATCH (root_owner:Component)-[:OWNS_CODE]->(root)
        OPTIONAL MATCH path=(root)<-[:DEPENDS_ON*0..$depth]-(dependentArtifact:CodeArtifact)<-[:OWNS_CODE]-(dependent:Component)
        WHERE dependent IS NOT NULL
          AND (
            $include_cross_repo
            OR coalesce(root.repo, "") = coalesce(dependentArtifact.repo, root.repo, "")
          )
        WITH
            root,
            root_owner,
            dependent,
            collect(DISTINCT dependentArtifact.id) AS dependency_artifacts
        OPTIONAL MATCH (doc:Doc)-[:DESCRIBES_COMPONENT]->(dependent)
        OPTIONAL MATCH (signal:ActivitySignal)-[rel:SIGNALS_COMPONENT]->(dependent)
        WHERE $activity_cutoff IS NULL OR rel.last_seen IS NULL OR datetime(rel.last_seen) >= datetime($activity_cutoff)
        WITH
            dependent,
            root,
            root_owner,
            dependency_artifacts,
            collect(DISTINCT doc.id) AS docs,
            sum(coalesce(rel.signal_weight, 0.0)) AS activity_score,
            [s IN collect(
                CASE
                    WHEN signal IS NULL THEN NULL
                    ELSE {
                        id: signal.id,
                        weight: coalesce(rel.signal_weight, 1.0),
                        last_seen: rel.last_seen
                    }
                END
            ) WHERE s IS NOT NULL] AS signals
        RETURN
            dependent.id AS component_id,
            dependency_artifacts AS dependency_artifacts,
            docs AS docs,
            activity_score AS activity_score,
            signals AS signals,
            root.id AS root_artifact_id,
            coalesce(root.repo, '') AS root_repo,
            root_owner.id AS root_component_id
        """

        rows = self.graph_service.run_query(
            query,
            {
                "component_id": component_id,
                "artifact_ids": artifact_ids,
                "depth": depth,
                "include_cross_repo": bool(include_cross),
                "activity_cutoff": cutoff,
            },
        )

        impacts: Dict[str, Dict[str, Any]] = {}
        for row in rows:
            comp_id = row.get("component_id")
            if not comp_id:
                continue

            bucket = impacts.setdefault(
                comp_id,
                {
                    "component_id": comp_id,
                    "dependent_artifacts": set(),
                    "docs_to_update": set(),
                    "activity_score": 0.0,
                    "recent_signals": {},
                    "root_artifacts": set(),
                    "source_components": set(),
                    "repos": set(),
                },
            )

            bucket["dependent_artifacts"].update(row.get("dependency_artifacts") or [])
            if include_docs:
                bucket["docs_to_update"].update(row.get("docs", []) or [])
            bucket["activity_score"] += float(row.get("activity_score") or 0.0) if include_activity else 0.0
            if include_activity:
                for signal in row.get("signals") or []:
                    signal_id = signal.get("id")
                    if not signal_id:
                        continue
                    bucket["recent_signals"][signal_id] = signal

            root_artifact = row.get("root_artifact_id")
            if root_artifact:
                bucket["root_artifacts"].add(root_artifact)
            root_component = row.get("root_component_id")
            if root_component:
                bucket["source_components"].add(root_component)
            root_repo = row.get("root_repo")
            if root_repo:
                bucket["repos"].add(root_repo)

        impacts_list: List[Dict[str, Any]] = []
        for entry in impacts.values():
            impacts_list.append(
                {
                    "component_id": entry["component_id"],
                    "dependent_artifacts": sorted(entry["dependent_artifacts"]),
                    "docs_to_update": sorted(entry["docs_to_update"]) if include_docs else [],
                    "activity_score": round(entry["activity_score"], 4) if include_activity else 0.0,
                    "recent_signals": list(entry["recent_signals"].values()) if include_activity else [],
                    "root_artifacts": sorted(entry["root_artifacts"]),
                    "source_components": sorted(entry["source_components"]),
                    "repos": sorted(entry["repos"]),
                }
            )

        return {
            "component_id": component_id,
            "artifact_ids": artifact_ids,
            "max_depth": depth,
            "include_cross_repo": bool(include_cross),
            "activity_window_hours": window_hours,
            "impacts": impacts_list,
        }

    @staticmethod
    def _cutoff_iso(window_hours: Optional[int]) -> Optional[str]:
        if not window_hours or window_hours <= 0:
            return None
        cutoff_dt = datetime.now(timezone.utc) - timedelta(hours=window_hours)
        return cutoff_dt.isoformat()

