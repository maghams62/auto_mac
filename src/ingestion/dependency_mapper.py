"""
Dependency mapper that upserts component/code dependencies from YAML.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import yaml

from ..graph import GraphIngestor, GraphService

logger = logging.getLogger(__name__)


class DependencyMapper:
    """
    Loads dependency metadata from YAML and writes it to the graph.
    """

    def __init__(
        self,
        config: Dict[str, Any],
        graph_service: Optional[GraphService] = None,
    ):
        cr_cfg = config.get("context_resolution", {}) or {}
        self.file_paths: List[str] = cr_cfg.get("dependency_files", [])
        self.graph_service = graph_service or GraphService(config)
        self.ingestor = GraphIngestor(self.graph_service)

    def ingest(self) -> Dict[str, int]:
        """
        Load all configured dependency files and upsert their data.
        """
        if not self.ingestor.available():
            logger.info("[DEPENDENCY MAPPER] Graph service unavailable; skipping ingestion.")
            return {}

        counts = {
            "components": 0,
            "artifacts": 0,
            "docs": 0,
            "endpoints": 0,
            "dependencies": 0,
        }

        for file_path in self.file_paths:
            path = Path(file_path)
            if not path.exists():
                logger.warning("[DEPENDENCY MAPPER] File not found: %s", path)
                continue

            try:
                with path.open("r", encoding="utf-8") as handle:
                    data = yaml.safe_load(handle) or {}
            except yaml.YAMLError as exc:
                logger.error("[DEPENDENCY MAPPER] Failed to parse %s: %s", path, exc)
                continue

            for component_entry in data.get("components", []):
                self._ingest_component(component_entry, counts)

            for dependency_entry in data.get("dependencies", []):
                if self._ingest_dependency(dependency_entry):
                    counts["dependencies"] += 1

        logger.info("[DEPENDENCY MAPPER] Completed ingestion: %s", counts)
        return counts

    # ------------------------------------------------------------------
    # Component ingestion helpers
    # ------------------------------------------------------------------
    def _ingest_component(self, entry: Dict[str, Any], counts: Dict[str, int]) -> None:
        component_id = entry.get("id")
        if not component_id:
            logger.warning("[DEPENDENCY MAPPER] Skipping component entry without id: %s", entry)
            return

        properties = {
            key: value
            for key, value in entry.items()
            if key not in {"id", "artifacts", "endpoints", "docs"}
        }
        self.ingestor.upsert_component(component_id, properties=properties)
        counts["components"] += 1

        for artifact in entry.get("artifacts", []) or []:
            artifact_id = artifact.get("id")
            depends_on_ids = artifact.get("depends_on", [])
            artifact_props = {
                key: value for key, value in artifact.items() if key not in {"id", "depends_on"}
            }
            self.ingestor.upsert_code_artifact(
                artifact_id=artifact_id,
                component_ids=[component_id],
                depends_on_ids=depends_on_ids,
                properties=artifact_props,
            )
            counts["artifacts"] += 1

        for endpoint in entry.get("endpoints", []) or []:
            endpoint_id = endpoint.get("id")
            endpoint_props = {
                key: value for key, value in endpoint.items() if key != "id"
            }
            self.ingestor.upsert_api_endpoint(
                api_id=endpoint_id,
                component_id=component_id,
                properties=endpoint_props,
            )
            counts["endpoints"] += 1

        for doc in entry.get("docs", []) or []:
            doc_id = doc.get("id")
            doc_props = {
                key: value for key, value in doc.items() if key != "id"
            }
            self.ingestor.upsert_doc(
                doc_id=doc_id,
                component_ids=[component_id],
                properties=doc_props,
            )
            counts["docs"] += 1

    def _ingest_dependency(self, entry: Dict[str, Any]) -> bool:
        """
        Handle explicit dependency declarations (component→component or artifact→artifact).
        """
        from_artifact = entry.get("from_artifact")
        to_artifact = entry.get("to_artifact")
        from_component = entry.get("from_component")
        to_component = entry.get("to_component")

        if from_artifact and to_artifact:
            query = """
            MATCH (src:CodeArtifact {id: $src_id})
            MATCH (dst:CodeArtifact {id: $dst_id})
            MERGE (src)-[r:DEPENDS_ON]->(dst)
            SET r.reason = $reason
            """
            self.graph_service.run_write(
                query,
                {
                    "src_id": from_artifact,
                    "dst_id": to_artifact,
                    "reason": entry.get("reason"),
                },
            )
            return True

        if from_component and to_component:
            query = """
            MATCH (src:Component {id: $src_id})
            MATCH (dst:Component {id: $dst_id})
            MERGE (src)-[r:DEPENDS_ON]->(dst)
            SET r.reason = $reason
            """
            self.graph_service.run_write(
                query,
                {
                    "src_id": from_component,
                    "dst_id": to_component,
                    "reason": entry.get("reason"),
                },
            )
            return True

        logger.warning("[DEPENDENCY MAPPER] Unsupported dependency entry: %s", entry)
        return False

