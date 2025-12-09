from __future__ import annotations

from datetime import datetime, timezone

from src.ingestion.slack_activity_ingestor import SlackActivityIngestor
from src.ingestion.git_activity_ingestor import GitActivityIngestor


def _base_config() -> dict:
    return {
        "activity_ingest": {
            "slack": {
                "enabled": True,
                "graph_log_path": "data/logs/slash/slack_graph.jsonl",
                "channels": [
                    {"id": "C123", "name": "core-api", "components": ["comp:core-api"]},
                ],
            },
            "git": {
                "enabled": True,
                "repos": [],
            },
        },
        "graph": {"enabled": False},
        "slash_git": {},
    }


def test_slack_chunk_includes_graph_metadata():
    config = _base_config()
    ingestor = SlackActivityIngestor(config, vector_service=None)
    channel_cfg = {"id": "C123", "name": "core-api", "components": ["comp:core-api"]}
    message = {
        "text": "Deploy finished",
        "ts": "1700000000.000001",
        "user": "alice",
    }
    chunk = ingestor._build_chunk(message, channel_cfg)
    assert chunk.entity_id.startswith("slack:C123:")
    assert chunk.metadata["graph_node_id"] == chunk.entity_id
    assert chunk.metadata["source_modality"] == "slack"
    assert chunk.metadata["source_id"] == chunk.entity_id


def test_git_commit_chunk_includes_graph_metadata():
    config = _base_config()
    ingestor = GitActivityIngestor(config, vector_service=None)
    commit = {
        "sha": "abc123def456",
        "message": "Fix billing bug",
        "author": "bob",
        "date": datetime(2025, 1, 1, tzinfo=timezone.utc).isoformat(),
        "files": [],
    }
    chunk = ingestor._build_commit_chunk(
        commit,
        component_ids=["comp:core-api"],
        repo_identifier="demo/core-api",
        project_id=None,
        branch_name="main",
    )
    assert chunk.entity_id == "commit:abc123def456"
    assert chunk.metadata["graph_node_id"] == chunk.entity_id
    assert chunk.metadata["source_modality"] == "git"
    assert chunk.metadata["source_id"] == chunk.entity_id

