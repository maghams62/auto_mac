import json
from datetime import datetime, timezone

import pytest

from src.slash_git.models import GitTargetCatalog
from src.slash_git.pipeline import SlashGitPipeline


class _DummyMetadataService:
    def find_repo(self, hint):
        return None

    def list_branches(self, repo_id: str, prefix: str = "", limit: int = 50):
        return []

    def suggest_branches(self, repo_id: str, branch: str, limit: int = 5):
        return []


def _write_catalog(tmp_path, owner_value: str) -> str:
    catalog = tmp_path / "catalog.yaml"
    catalog.write_text(
        "\n".join(
            [
                "repos:",
                "  - id: core-api",
                "    name: Core API",
                f"    repo_owner: \"{owner_value}\"",
                "    repo_name: core-api",
                "    default_branch: main",
                "    components:",
                "      - id: core.payments",
                "        name: Core Payments",
                "        aliases: [payments]",
                "        paths: [src/payments.py]",
            ]
        )
    )
    return str(catalog)


def test_catalog_expands_default_env(monkeypatch, tmp_path):
    monkeypatch.delenv("LIVE_GIT_ORG", raising=False)
    catalog_path = _write_catalog(tmp_path, "${LIVE_GIT_ORG:-maghams62}")
    catalog = GitTargetCatalog.from_file(catalog_path)
    repo = catalog.get_repo("core-api")
    assert repo.repo_owner == "maghams62"


def test_catalog_prefers_env_override(monkeypatch, tmp_path):
    monkeypatch.setenv("LIVE_GIT_ORG", "custom-owner")
    catalog_path = _write_catalog(tmp_path, "${LIVE_GIT_ORG:-maghams62}")
    catalog = GitTargetCatalog.from_file(catalog_path)
    repo = catalog.get_repo("core-api")
    assert repo.repo_owner == "custom-owner"


def test_catalog_raises_on_unexpanded_placeholder(monkeypatch, tmp_path):
    monkeypatch.delenv("LIVE_GIT_ORG", raising=False)
    catalog_path = _write_catalog(tmp_path, "${LIVE_GIT_ORG}")
    with pytest.raises(ValueError, match="placeholder"):
        GitTargetCatalog.from_file(catalog_path)


def test_pipeline_uses_resolved_owner(monkeypatch, tmp_path):
    monkeypatch.delenv("LIVE_GIT_ORG", raising=False)
    catalog_path = _write_catalog(tmp_path, "${LIVE_GIT_ORG:-maghams62}")

    events_path = tmp_path / "events.json"
    prs_path = tmp_path / "prs.json"
    now_iso = datetime.now(timezone.utc).isoformat()
    events_path.write_text(
        json.dumps(
            [
                {
                    "repo": "core-api",
                    "commit_sha": "abc1234",
                    "author": "alice",
                    "timestamp": now_iso,
                    "message": "test commit",
                    "files_changed": ["src/payments.py"],
                    "labels": [],
                }
            ]
        )
    )
    prs_path.write_text("[]")

    config = {
        "slash_git": {
            "target_catalog_path": catalog_path,
            "default_repo_id": "core-api",
            "use_live_data": False,
            "graph_emit_enabled": False,
            "synthetic_data": {
                "events_path": str(events_path),
                "prs_path": str(prs_path),
            },
        }
    }

    pipeline = SlashGitPipeline(config, metadata_service=_DummyMetadataService())
    result = pipeline.run("/git whats the last commit?")

    assert result is not None
    assert result.plan.repo is not None
    assert result.plan.repo.repo_owner == "maghams62"
    assert result.snapshot["commits"], "Expected synthetic commits in snapshot"

