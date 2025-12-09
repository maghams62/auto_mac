import pytest
from fastapi.testclient import TestClient

import api_server
from src.services.slack_metadata import SlackMetadataService
from src.services.git_metadata import RepoMetadata, BranchMetadata


class StubSlackClient:
    def __init__(self):
        self.channel_calls = 0
        self.user_calls = 0

    def list_channels(self, limit=100, exclude_archived=True, types="public_channel,private_channel", cursor=None):
        self.channel_calls += 1
        return {
            "ok": True,
            "channels": [
                {
                    "id": "C123",
                    "name": "backend",
                    "is_private": False,
                    "is_archived": False,
                    "num_members": 42,
                },
                {
                    "id": "C456",
                    "name": "core-api",
                    "is_private": True,
                    "is_archived": False,
                    "num_members": 8,
                },
            ],
            "response_metadata": {"next_cursor": ""},
        }

    def list_users(self, limit=200, cursor=None):
        self.user_calls += 1
        return {
            "ok": True,
            "members": [
                {
                    "id": "U1",
                    "name": "alice",
                    "profile": {"real_name": "Alice Doe", "display_name": "alice"},
                },
                {
                    "id": "U2",
                    "name": "bob",
                    "profile": {"real_name": "Bob Smith", "display_name": "bobby"},
                },
            ],
            "response_metadata": {"next_cursor": ""},
        }

    def get_channel_info(self, channel):
        return {"ok": True, "channel": {"id": channel, "name": channel}}

    def get_user_info(self, user):
        return {"ok": True, "user": {"id": user, "name": user}}


class StubGitMetadataService:
    def __init__(self):
        self.repo_calls = 0
        self.branch_calls = 0
        self.repos = [
            RepoMetadata(
                id="core-api",
                owner="acme",
                name="core-api",
                full_name="acme/core-api",
                default_branch="main",
                description="Core API",
                topics=("payments",),
            ),
            RepoMetadata(
                id="billing",
                owner="acme",
                name="billing",
                full_name="acme/billing",
                default_branch="main",
                description="Billing",
                topics=("billing",),
            ),
        ]
        self.branch_map = {
            "core-api": [
                BranchMetadata(name="main", is_default=True, protected=True),
                BranchMetadata(name="develop", is_default=False, protected=False),
            ],
            "billing": [
                BranchMetadata(name="main", is_default=True, protected=True),
            ],
        }

    def list_repos(self, prefix: str = "", limit: int = 10):
        self.repo_calls += 1
        prefix_lower = (prefix or "").lower()
        results = [
            repo
            for repo in self.repos
            if not prefix_lower or repo.full_name.lower().startswith(prefix_lower)
        ]
        return results[:limit]

    def list_branches(self, repo_identifier: str, prefix: str = "", limit: int = 10):
        self.branch_calls += 1
        prefix_lower = (prefix or "").lower()
        branches = self.branch_map.get(repo_identifier, [])
        filtered = [
            branch for branch in branches if not prefix_lower or branch.name.lower().startswith(prefix_lower)
        ]
        return filtered[:limit]


@pytest.fixture()
def metadata_services(monkeypatch):
    slack_client = StubSlackClient()
    slack_service = SlackMetadataService(
        config={"metadata_cache": {"slack": {"ttl_seconds": 600, "max_items": 100}}},
        client=slack_client,
    )
    git_service = StubGitMetadataService()
    monkeypatch.setattr(api_server, "slack_metadata_service", slack_service)
    monkeypatch.setattr(api_server, "git_metadata_service", git_service)
    return slack_service, slack_client, git_service


@pytest.fixture()
def client(metadata_services):
    return TestClient(api_server.app, raise_server_exceptions=False)


def test_slack_channels_endpoint_uses_cache(client, metadata_services):
    slack_service, slack_client, _ = metadata_services
    resp1 = client.get("/api/metadata/slack/channels?query=back")
    resp2 = client.get("/api/metadata/slack/channels?query=back")
    assert resp1.status_code == 200
    assert resp2.status_code == 200
    assert resp1.json()["channels"][0]["name"] == "backend"
    assert slack_client.channel_calls == 1, "cache should avoid duplicate Slack API fetches"


def test_slack_users_endpoint_accepts_prefix_alias(client, metadata_services):
    resp = client.get("/api/metadata/slack/users?prefix=bo")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["count"] == 1
    assert payload["users"][0]["display_name"] == "bobby"


def test_slack_metadata_error_surfaces_failure(client, metadata_services, monkeypatch):
    slack_service, _, _ = metadata_services

    def boom(*args, **kwargs):
        raise RuntimeError("cache busted")

    monkeypatch.setattr(slack_service, "suggest_channels", boom)
    resp = client.get("/api/metadata/slack/channels?query=test")
    assert resp.status_code == 500


def test_git_repos_endpoint_filters_by_prefix(client, metadata_services):
    resp = client.get("/api/metadata/git/repos?query=acme/cor")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["count"] == 1
    assert payload["repos"][0]["full_name"] == "acme/core-api"


def test_git_branches_endpoint_filters(client, metadata_services):
    resp = client.get("/api/metadata/git/repos/core-api/branches?query=dev")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["count"] == 1
    assert payload["branches"][0]["name"] == "develop"


def test_git_branches_endpoint_error(client, metadata_services, monkeypatch):
    _, _, git_service = metadata_services

    def explode(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(git_service, "list_branches", explode)
    resp = client.get("/api/metadata/git/repos/core-api/branches?query=dev")
    assert resp.status_code == 500

