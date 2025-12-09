from datetime import datetime, timezone

from types import SimpleNamespace

from src.slash_git.executor import GitQueryExecutor
from src.slash_git.models import GitQueryMode, GitQueryPlan, GitTargetCatalog, TimeWindow


CATALOG = GitTargetCatalog.from_file("config/slash_git_targets.yaml")
DATA_CONFIG = {
    "slash_git": {
        "synthetic_data": {
            "events_path": "data/synthetic_git/git_events.json",
            "prs_path": "data/synthetic_git/git_prs.json",
        },
        "graph_emit_enabled": False,
    }
}


class StubGitSource:
    def __init__(self):
        self.commits = []
        self.prs = []

    def get_commits(self, repo, component, window, **kwargs):
        return self.commits

    def get_prs(self, repo, component, window, **kwargs):
        return self.prs


def _plan(repo_id="core-api", component_id="core.webhooks"):
    repo = CATALOG.get_repo(repo_id)
    component = repo.components[component_id]
    return GitQueryPlan(
        mode=GitQueryMode.COMPONENT_ACTIVITY,
        repo=repo,
        component=component,
        time_window=TimeWindow(
            start=datetime(2025, 11, 23, tzinfo=timezone.utc),
            end=datetime(2025, 11, 27, tzinfo=timezone.utc),
            label="story window",
            source="test",
        ),
    )


def test_executor_filters_commits_by_component_paths():
    stub = StubGitSource()
    stub.commits = [
        {"repo": "core-api", "commit_sha": "abc", "author": "alice", "timestamp": "2025-11-24T00:00:00Z", "message": "", "text_for_embedding": "", "files_changed": ["src/auth.py"]},
        {"repo": "core-api", "commit_sha": "xyz", "author": "bob", "timestamp": "2025-11-24T01:00:00Z", "message": "", "text_for_embedding": "", "files_changed": ["docs/README.md"]},
    ]
    executor = GitQueryExecutor(DATA_CONFIG, CATALOG, data_source=stub)
    snapshot = executor.run(_plan())

    assert len(snapshot["commits"]) == 2
    assert snapshot["meta"]["component_id"] == "core.webhooks"

