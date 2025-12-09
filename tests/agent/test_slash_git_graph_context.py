from types import SimpleNamespace

from src.agent.slash_git_assistant import SlashGitAssistant
from src.services.git_metadata import GitMetadataService
from src.slash_git.models import GitQueryMode, GitQueryPlan, GitTargetRepo, TimeWindow


class StubRegistry:
    def execute_tool(self, *_, **__):
        return {}


class StubGitMetadataService:
    def __init__(self):
        self.repo_id = "acme/billing-service"


def _make_assistant():
    config = {
        "github": {
            "repo_owner": "acme",
            "repo_name": "billing-service",
        }
    }
    return SlashGitAssistant(
        agent_registry=StubRegistry(),
        session_manager=None,
        config=config,
        metadata_service=StubGitMetadataService(),
        git_pipeline=SimpleNamespace(run=lambda *_: None),
        git_formatter=SimpleNamespace(generate=lambda *_, **__: (None, None)),
    )


def test_pipeline_graph_context_tracks_incident_signals_and_files():
    assistant = _make_assistant()
    repo = GitTargetRepo(
        id="billing-service",
        name="billing-service",
        repo_owner="acme",
        repo_name="billing-service",
        default_branch="main",
        aliases=[],
        synthetic_root=None,
        components={},
    )
    plan = GitQueryPlan(
        mode=GitQueryMode.REPO_ACTIVITY,
        repo=repo,
        time_window=TimeWindow(label="last 48 hours"),
    )
    snapshot = {
        "commits": [
            {
                "commit_sha": "abc123",
                "author": "bob",
                "message": "rollback checkout hotfix",
                "service_ids": ["billing-service"],
                "component_ids": ["billing.checkout"],
                "files_changed": ["src/checkout.py"],
                "labels": [],
                "changed_apis": ["/v1/payments/create"],
            },
            {
                "commit_sha": "def456",
                "author": "eve",
                "message": "docs_followup for vat_code",
                "service_ids": ["docs-portal"],
                "component_ids": ["docs.payments"],
                "files_changed": ["docs/api_usage.md"],
                "labels": ["docs_followup"],
                "changed_apis": ["/v1/payments/create"],
            },
        ],
        "prs": [
            {
                "pr_number": 118,
                "author": "bob",
                "title": "Fix 400 errors by adding vat_code",
                "service_ids": ["core-api-service"],
                "component_ids": ["core.payments"],
                "files_changed": ["src/core_api_client.py", "src/checkout.py"],
                "labels": ["incident"],
                "changed_apis": ["/v1/payments/create"],
            }
        ],
    }

    context = assistant._build_pipeline_graph_context(plan, snapshot)

    assert context["services"] == ["billing-service", "core-api-service", "docs-portal"]
    assert context["components"] == ["billing.checkout", "core.payments", "docs.payments"]
    assert context["apis"] == ["/v1/payments/create"]
    assert context["activity_counts"] == {"commits": 2, "prs": 1}
    assert context["branch"] == "main"
    assert context["time_window"] == "last 48 hours"
    assert any(signal["reason"].startswith("label") for signal in context["incident_signals"])
    top_file_paths = [entry["path"] for entry in context["top_files"]]
    assert "src/checkout.py" in top_file_paths
    assert "docs/api_usage.md" in top_file_paths


class BlockingRegistry:
    def __init__(self):
        self.calls = 0

    def execute_tool(self, *_, **__):
        self.calls += 1
        raise AssertionError("Registry should not be invoked when graph-only guard is active")


def test_live_git_tools_blocked_in_graph_only_mode(tmp_path):
    catalog_path = tmp_path / "catalog.yaml"
    catalog_path.write_text(
        """
repos:
  - id: core-api
    name: "Core API"
    repo_owner: "acme"
    repo_name: "core-api"
    default_branch: "main"
"""
    )
    config = {
        "github": {
            "repo_owner": "acme",
            "repo_name": "core-api",
        },
        "slash_git": {
            "graph_mode": {"require": True},
            "target_catalog_path": str(catalog_path),
        },
    }
    metadata_service = GitMetadataService(
        {
            **config,
            "metadata_cache": {"git": {}},
        }
    )
    assistant = SlashGitAssistant(
        agent_registry=BlockingRegistry(),
        session_manager=None,
        config=config,
        metadata_service=metadata_service,
        git_pipeline=SimpleNamespace(run=lambda *_: None),
        git_formatter=SimpleNamespace(generate=lambda *_, **__: (None, None)),
    )
    response = assistant._execute_git_tool("list_repository_branches", {}, None)
    assert response["error"] is True
    assert response["error_type"] == "LiveGitDisabled"

