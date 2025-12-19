import json

from src.impact.models import GitChangePayload, GitFileChange, ImpactLevel
from src.impact.service import ImpactService, SlackComplaintInput


class FakeGitIntegration:
    def build_payload_from_pr(self, repo_full: str, pr_number: int) -> GitChangePayload:
        return GitChangePayload(
            identifier=f"{repo_full}#PR-{pr_number}",
            title="Fake PR",
            repo=repo_full,
            files=[GitFileChange(path="src/alpha/service.py", repo=repo_full)],
            metadata={"repo_full_name": repo_full},
        )

    def build_payload_from_commits(
        self,
        repo_full: str,
        commit_shas,
        *,
        title=None,
        description=None,
    ) -> GitChangePayload:
        return GitChangePayload(
            identifier=f"{repo_full}@manual",
            title=title or "Manual",
            repo=repo_full,
            files=[GitFileChange(path="src/alpha/service.py", repo=repo_full)],
            description=description,
            metadata={"repo_full_name": repo_full, "commits": list(commit_shas)},
        )

    def recent_component_changes(self, repo_full, components, graph, limit, branch=None, *, since=None):
        return []


class FakeDocIssueService:
    def __init__(self, issues):
        self._issues = issues

    def list(self):
        return self._issues


def test_service_manual_git_change(impact_config_context, dependency_map_file):
    impact_config_context.data["context_resolution"]["dependency_files"] = [str(dependency_map_file)]
    service = ImpactService(impact_config_context, git_integration=FakeGitIntegration())
    report = service.analyze_git_change(
        repo="repo-alpha",
        files=[GitFileChange(path="src/alpha/service.py", repo="repo-alpha")],
        title="Manual change",
    )
    assert any(entity.entity_id == "comp:alpha" for entity in report.changed_components)
    assert report.impact_level in {ImpactLevel.MEDIUM, ImpactLevel.HIGH}


def test_service_slack_complaint_infers_components(impact_config_context, dependency_map_file):
    impact_config_context.data["context_resolution"]["dependency_files"] = [str(dependency_map_file)]
    service = ImpactService(impact_config_context, git_integration=FakeGitIntegration())
    complaint = SlackComplaintInput(
        channel="#alerts",
        message="Seeing errors in Alpha component today",
        timestamp="123.45",
    )
    report = service.analyze_slack_complaint(complaint)
    assert any(thread.entity_type.value == "slack_thread" for thread in report.slack_threads)
    assert any(entity.entity_id == "comp:alpha" for entity in report.changed_components)


def test_service_slack_complaint_adds_permalink(monkeypatch, impact_config_context, dependency_map_file):
    monkeypatch.setenv("SLACK_WORKSPACE_URL", "https://example.slack.com")
    impact_config_context.data["context_resolution"]["dependency_files"] = [str(dependency_map_file)]
    service = ImpactService(impact_config_context, git_integration=FakeGitIntegration())
    complaint = SlackComplaintInput(
        channel="C99ALPHA",
        message="Thread needs attention",
        timestamp="1700000000.12345",
        component_ids=["comp:alpha"],
    )
    report = service.analyze_slack_complaint(complaint)
    slack_meta = report.metadata.get("slack_context") or {}
    assert slack_meta.get("permalink", "").startswith(
        "https://example.slack.com/archives/C99ALPHA/p170000000012345"
    )


def test_get_impact_health_reports_repo_state(tmp_path, monkeypatch, impact_config_context, dependency_map_file):
    impact_config_context.data["context_resolution"]["dependency_files"] = [str(dependency_map_file)]
    impact_config_context.data.setdefault("activity_ingest", {}).setdefault("git", {})["repos"] = [
        {
            "owner": "tiangolo",
            "name": "fastapi",
            "branch": "master",
            "repo_id": "fastapi",
        }
    ]
    state_path = tmp_path / "impact_state.json"
    state_payload = {
        "repos": {
            "tiangolo/fastapi": {
                "last_run_started_at": "2025-01-01T00:00:00Z",
                "last_run_completed_at": "2025-01-01T00:05:00Z",
                "last_success_at": "2025-01-01T00:05:00Z",
                "last_cursor": "2025-01-01T00:00:00Z",
                "processed_ids": ["fastapi@abc123"],
            }
        }
    }
    state_path.write_text(json.dumps(state_payload), encoding="utf-8")
    impact_config_context.data.setdefault("impact", {})["auto_ingest_state_path"] = str(state_path)
    service = ImpactService(impact_config_context, git_integration=FakeGitIntegration())
    fake_issues = [
        {"repo_id": "fastapi", "updated_at": "2025-01-01T01:00:00Z"},
        {"repo_id": "fastapi", "updated_at": "2025-01-01T02:00:00Z"},
    ]
    service.doc_issue_service = FakeDocIssueService(fake_issues)
    monkeypatch.setattr(service, "_recent_impact_events", lambda limit=10: [])
    health = service.get_impact_health()
    assert health["doc_issues"]["count"] == 2
    repo_entry = next((repo for repo in health["repos"] if repo["repo_id"] == "fastapi"), None)
    assert repo_entry is not None
    assert repo_entry["doc_issues_open"] == 2
    assert repo_entry["last_cursor"] == "2025-01-01T00:00:00Z"
    assert repo_entry["last_run_completed_at"] == "2025-01-01T00:05:00Z"

