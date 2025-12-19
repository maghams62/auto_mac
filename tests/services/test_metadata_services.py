import logging

import pytest

from src.services.slack_metadata import SlackMetadataService, SlackAPIError
from src.services.git_metadata import GitMetadataService, RepoMetadata, BranchMetadata
from src.services.github_pr_service import GitHubAPIError


class StubSlackClient:
    def __init__(self):
        self.channel_calls = 0
        self.user_calls = 0
        self.raise_error = False

    def list_channels(self, limit=100, exclude_archived=True, types="public_channel,private_channel", cursor=None):
        self.channel_calls += 1
        if self.raise_error:
            raise SlackAPIError("boom")
        return {
            "ok": True,
            "channels": [
                {"id": "C1", "name": "backend", "is_private": False, "is_archived": False, "num_members": 10},
                {"id": "C2", "name": "core-api", "is_private": True, "is_archived": False, "num_members": 5},
            ],
            "response_metadata": {"next_cursor": ""},
        }

    def list_users(self, limit=200, cursor=None):
        self.user_calls += 1
        return {
            "ok": True,
            "members": [
                {"id": "U1", "name": "alice", "profile": {"real_name": "Alice Doe", "display_name": "alice"}},
            ],
            "response_metadata": {"next_cursor": ""},
        }

    def get_channel_info(self, channel):
        return {"ok": True, "channel": {"id": channel, "name": channel}}

    def get_user_info(self, user):
        return {"ok": True, "user": {"id": user, "name": user}}


def test_slack_metadata_refresh_force_invalidates(monkeypatch, caplog):
    client = StubSlackClient()
    service = SlackMetadataService(
        config={"metadata_cache": {"slack": {"ttl_seconds": 10, "max_items": 100, "log_metrics": True}}},
        client=client,
    )
    caplog.set_level(logging.INFO)
    service.suggest_channels()
    assert client.channel_calls == 1
    service.refresh_channels(force=True)
    service.suggest_channels(prefix="core")
    assert client.channel_calls == 2
    assert any("slack_channels" in record.message for record in caplog.records)


def test_slack_metadata_handles_api_errors_without_crashing():
    client = StubSlackClient()
    client.raise_error = True
    service = SlackMetadataService(
        config={"metadata_cache": {"slack": {"ttl_seconds": 10, "max_items": 100}}},
        client=client,
    )
    channels = service.suggest_channels()
    assert channels == []


class StubGitMetadataService(GitMetadataService):
    def __init__(self):
        super().__init__(
            config={
                "metadata_cache": {"git": {"repo_ttl_seconds": 10, "branch_ttl_seconds": 5, "max_branches_per_repo": 50, "log_metrics": True}},
                "github": {},
            }
        )
        repo = RepoMetadata(
            id="acme/core-api",
            owner="acme",
            name="core-api",
            full_name="acme/core-api",
            default_branch="main",
            description="Core API",
            topics=("payments",),
        )
        self._merge_repo(repo)
        self._branch_fetch_count = 0

    def _fetch_branches(self, repo: RepoMetadata):
        self._branch_fetch_count += 1
        return [
            BranchMetadata(name="main", is_default=True, protected=True),
            BranchMetadata(name="develop", is_default=False, protected=False),
            BranchMetadata(name="release-candidate", is_default=False, protected=False),
        ]


def test_git_metadata_branch_refresh_and_suggestions(caplog):
    service = StubGitMetadataService()
    caplog.set_level(logging.INFO)
    matches = service.list_branches("acme/core-api", prefix="dev")
    assert matches[0].name == "develop"
    suggestions = service.suggest_branches("acme/core-api", prefix="rel", limit=2)
    assert suggestions[0] == "release-candidate"
    # Force refresh should trigger fetch again
    previous_fetches = service._branch_fetch_count
    service.refresh_branches("acme/core-api", force=True)
    assert service._branch_fetch_count > previous_fetches
    assert any("git_branches:acme/core-api" in record.message for record in caplog.records)


def test_git_metadata_handles_github_errors(monkeypatch):
    service = GitMetadataService(config={"metadata_cache": {"git": {}}})
    repo = RepoMetadata(
        id="acme/core-api",
        owner="acme",
        name="core-api",
        full_name="acme/core-api",
        default_branch="main",
        description=None,
        topics=(),
    )
    service._merge_repo(repo)

    class ErrorService:
        def list_branches(self, *args, **kwargs):
            raise GitHubAPIError("boom")

    monkeypatch.setattr(service, "_service_for", lambda owner, name: ErrorService())
    branches = service.list_branches("acme/core-api")
    assert branches == []


def test_git_metadata_graph_mode_uses_catalog(tmp_path):
    catalog_path = tmp_path / "catalog.yaml"
    catalog_path.write_text(
        """
repos:
  - id: core-api
    name: "Core API"
    repo_owner: "acme"
    repo_name: "core-api"
    default_branch: "main"
    aliases:
      - "core api"
"""
    )
    config = {
        "slash_git": {
            "graph_mode": {"require": True},
            "target_catalog_path": str(catalog_path),
        },
        "metadata_cache": {"git": {}},
    }
    service = GitMetadataService(config)
    repos = service.list_repos()
    assert len(repos) == 1
    assert repos[0].id == "core-api"

    branches = service.list_branches("core-api")
    assert len(branches) == 1
    assert branches[0].name == "main"
    assert branches[0].is_default

