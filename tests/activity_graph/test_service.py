import copy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Optional

from src.config.context import ConfigContext, get_config_context
from src.config_validator import ConfigAccessor
from src.activity_graph.models import TimeWindow
from src.activity_graph.service import ActivityGraphService
from src.activity_graph.signals import (
    DocIssueCounts,
    DocIssueSignalsExtractor,
    GitSignalCounts,
    SlackSignalCounts,
    SignalEvent,
)
from src.graph.dependency_graph import DependencyGraphBuilder
from src.ingestion.loggers import SignalLogWriter
from src.impact.doc_issues import DocIssueService
from src.impact.models import (
    GitChangePayload,
    GitFileChange,
    ImpactEntityType,
    ImpactLevel,
    ImpactReport,
    ImpactedEntity,
)
from src.impact.pipeline import ImpactPipeline


class StubGitSignals:
    def __init__(self, counts: GitSignalCounts, per_window: Optional[Dict[str, GitSignalCounts]] = None):
        self.counts = counts
        self.per_window = per_window or {}

    def count_events(self, repo, component, window):
        return self.per_window.get(window.label, self.counts)


class StubSlackSignals:
    def __init__(self, counts: SlackSignalCounts, per_window: Optional[Dict[str, SlackSignalCounts]] = None):
        self.counts = counts
        self.per_window = per_window or {}

    def count(self, component_id, window):
        return self.per_window.get(window.label, self.counts)


class StubDocIssueSignals:
    def __init__(self, counts: DocIssueCounts, per_window: Optional[Dict[str, DocIssueCounts]] = None):
        self.counts = counts
        self.per_window = per_window or {}

    def count(self, component_id):
        return self.counts


def _event_timestamp(age_hours: float = 0.0) -> datetime:
    return datetime.now(timezone.utc) - timedelta(hours=age_hours)


def _git_counts(commits: int = 0, prs: int = 0, age_hours: float = 0.01) -> GitSignalCounts:
    events = []
    for _ in range(commits):
        events.append(SignalEvent(kind="commit", timestamp=_event_timestamp(age_hours)))
    for _ in range(prs):
        events.append(SignalEvent(kind="pr", timestamp=_event_timestamp(age_hours)))
    return GitSignalCounts(commits=commits, prs=prs, events=events)


def _slack_counts(conversations: int = 0, complaints: int = 0, age_hours: float = 0.01) -> SlackSignalCounts:
    events = []
    for idx in range(conversations):
        kind = "complaint" if idx < complaints else "conversation"
        events.append(
            SignalEvent(
                kind=kind,
                timestamp=_event_timestamp(age_hours),
                metadata={"channel_id": "C1", "channel_name": "#test"},
            )
        )
    return SlackSignalCounts(conversations=conversations, complaints=complaints, events=events)


def _doc_counts(breakdown: Optional[Dict[str, int]] = None) -> DocIssueCounts:
    template = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    if breakdown:
        template.update(breakdown)
    weights = {"critical": 2.0, "high": 1.5, "medium": 1.0, "low": 0.5}
    severity_weight = sum(template[key] * weights[key] for key in template)
    open_issues = sum(template.values())
    return DocIssueCounts(open_issues=open_issues, severity_weight=severity_weight, severity_breakdown=template)


def test_compute_component_activity_with_stub_data():
    config = {"slash_git": {"target_catalog_path": "config/slash_git_targets.yaml"}, "activity_graph": {"cache": {"enabled": False}}}
    service = ActivityGraphService(
        config,
        git_signals=StubGitSignals(_git_counts(commits=1, prs=1)),
        slack_signals=StubSlackSignals(_slack_counts(conversations=2, complaints=1)),
        doc_issue_signals=StubDocIssueSignals(_doc_counts({"critical": 1})),
        cache=None,
    )
    window = TimeWindow(
        start=datetime(2025, 11, 24, tzinfo=timezone.utc),
        end=datetime(2025, 11, 26, tzinfo=timezone.utc),
        label="test window",
    )
    activity = service.compute_component_activity("core.payments", window)

    assert activity.git_events == 2
    assert activity.slack_conversations == 2
    assert activity.slack_complaints == 1
    assert activity.open_doc_issues == 1
    assert activity.activity_score == 2.8  # (0.8 commit + 1.2 pr + 0.8 slack)
    assert activity.dissatisfaction_score == 3.9  # (0.9 slack + 3.0 doc issue)


def test_debug_breakdown_included_when_requested():
    config = {
        "slash_git": {"target_catalog_path": "config/slash_git_targets.yaml"},
        "activity_graph": {
            "cache": {"enabled": False},
            "scoring": {
                "git": {"commit_weight": 2.0, "pr_weight": 1.5},
                "slack": {"conversation_weight": 1.0, "complaint_weight": 2.0},
                "doc_issues": {"severity_weights": {"critical": 4.0, "medium": 2.0, "low": 1.0}},
                "time_decay": {"buckets": {"1h": 1.0}, "default": 1.0},
            },
        },
    }
    service = ActivityGraphService(
        config,
        git_signals=StubGitSignals(_git_counts(commits=1)),
        slack_signals=StubSlackSignals(_slack_counts(conversations=2, complaints=1)),
        doc_issue_signals=StubDocIssueSignals(_doc_counts({"critical": 1, "medium": 1})),
        cache=None,
    )
    window = TimeWindow(
        start=datetime(2025, 11, 24, tzinfo=timezone.utc),
        end=datetime(2025, 11, 26, tzinfo=timezone.utc),
        label="test window",
    )
    activity = service.compute_component_activity("core.payments", window, include_debug=True)

    assert activity.debug_breakdown == {
        "git_commits_score": 2.0,
        "git_prs_score": 0.0,
        "slack_conversations_score": 2.0,
        "slack_complaints_score": 2.0,
        "doc_issues_score": 6.0,
    }
    assert activity.activity_score == 4.0
    assert activity.dissatisfaction_score == 8.0


def test_fastapi_doc_issue_surfaces_in_activity_graph(tmp_path):
    doc_issue_path = tmp_path / "doc_issues.json"
    doc_issue_service = DocIssueService(doc_issue_path)
    graph = DependencyGraphBuilder().build(write_to_graph=False)

    report = ImpactReport(
        change_id="fastapi#PR-999",
        change_title="Update FastAPI tutorial",
        change_summary="Docs refresh for tutorial",
        impact_level=ImpactLevel.HIGH,
        changed_components=[
            ImpactedEntity(
                entity_id="comp:fastapi-core",
                entity_type=ImpactEntityType.COMPONENT,
                confidence=0.9,
                reason="docs/en/docs/tutorial touched",
                impact_level=ImpactLevel.HIGH,
            )
        ],
        impacted_components=[],
        impacted_services=[],
        impacted_docs=[
            ImpactedEntity(
                entity_id="doc:fastapi-tutorial",
                entity_type=ImpactEntityType.DOC,
                confidence=0.8,
                reason="Tutorial references outdated APIs",
                impact_level=ImpactLevel.MEDIUM,
                metadata={"component_id": "comp:fastapi-core"},
            )
        ],
        impacted_apis=[],
        slack_threads=[],
        metadata={
            "change": {
                "identifier": "fastapi#PR-999",
                "repo": "fastapi",
                "metadata": {"url": "https://github.com/tiangolo/fastapi/pull/999"},
            }
        },
    )
    doc_issue_service.create_from_impact(report, graph)

    config = {
        "slash_git": {"target_catalog_path": "config/slash_git_targets.yaml"},
        "activity_graph": {
            "doc_issues_path": str(doc_issue_path),
            "slack_graph_path": str(tmp_path / "slack.jsonl"),
            "git_graph_path": str(tmp_path / "git.jsonl"),
            "cache": {"enabled": False},
        },
    }
    service = ActivityGraphService(
        config,
        git_signals=StubGitSignals(GitSignalCounts(commits=0, prs=0)),
        slack_signals=StubSlackSignals(SlackSignalCounts(conversations=0, complaints=0)),
        doc_issue_signals=DocIssueSignalsExtractor(Path(doc_issue_path)),
        cache=None,
    )

    top = service.top_dissatisfied_components(limit=3)
    assert any(activity.component_id == "comp:fastapi-core" and activity.open_doc_issues > 0 for activity in top)


def _override_activity_paths(doc_issue_path: Path, slack_log_path: Path, git_log_path: Path) -> ConfigContext:
    base_ctx = get_config_context()
    config_data = copy.deepcopy(base_ctx.data)
    activity_cfg = config_data.setdefault("activity_graph", {})
    activity_cfg["doc_issues_path"] = str(doc_issue_path)
    activity_cfg["slack_graph_path"] = str(slack_log_path)
    activity_cfg["git_graph_path"] = str(git_log_path)
    impact_cfg = config_data.setdefault("impact", {})
    impact_cfg["data_mode"] = "live"
    accessor = ConfigAccessor(config_data)
    return ConfigContext(data=config_data, accessor=accessor)


def test_fastapi_git_pipeline_feeds_activity_graph(tmp_path):
    doc_issue_path = tmp_path / "doc_issues.json"
    slack_log_path = tmp_path / "slack.jsonl"
    git_log_path = tmp_path / "git.jsonl"
    ctx = _override_activity_paths(doc_issue_path, slack_log_path, git_log_path)

    pipeline = ImpactPipeline(config_context=ctx)
    change = GitChangePayload(
        identifier="fastapi@test",
        title="Docs + core update",
        description="Simulated FastAPI change touching docs + routing",
        repo="fastapi",
        files=[
            GitFileChange(path="fastapi/routing.py", repo="fastapi", change_type="modified"),
            GitFileChange(path="docs/en/docs/tutorial/index.md", repo="fastapi", change_type="modified"),
        ],
        metadata={"repo_full_name": "tiangolo/fastapi"},
    )
    pipeline.process_git_event(change)

    config = {
        "slash_git": {"target_catalog_path": "config/slash_git_targets.yaml"},
        "activity_graph": {
            "doc_issues_path": str(doc_issue_path),
            "slack_graph_path": str(slack_log_path),
            "git_graph_path": str(git_log_path),
            "cache": {"enabled": False},
        },
    }
    service = ActivityGraphService(config)
    window = TimeWindow.last_days(7)
    results = service.top_dissatisfied_components(limit=5, time_window=window)
    assert any(result.component_id == "comp:fastapi-core" and result.open_doc_issues > 0 for result in results)


def test_slack_signal_contributes_to_activity_graph(tmp_path):
    doc_issue_path = tmp_path / "doc_issues.json"
    doc_issue_path.write_text("[]", encoding="utf-8")
    slack_log_path = tmp_path / "slack.jsonl"
    git_log_path = tmp_path / "git.jsonl"

    writer = SignalLogWriter(slack_log_path)
    timestamp = datetime.now(timezone.utc).isoformat()
    writer.write(
        {
            "component_ids": ["comp:fastapi-core"],
            "properties": {
                "timestamp": timestamp,
                "labels": ["complaint"],
                "channel_id": "CFASTAPI",
                "channel_name": "#fastapi-alerts",
            },
        }
    )

    config = {
        "slash_git": {"target_catalog_path": "config/slash_git_targets.yaml"},
        "activity_graph": {
            "doc_issues_path": str(doc_issue_path),
            "slack_graph_path": str(slack_log_path),
            "git_graph_path": str(git_log_path),
            "cache": {"enabled": False},
        },
    }
    service = ActivityGraphService(config)
    window = TimeWindow.last_days(7)
    activity = service.compute_component_activity("comp:fastapi-core", window)

    assert activity.slack_conversations >= 1
    assert activity.slack_complaints >= 1
    assert activity.dissatisfaction_score > 0


def test_time_decay_reduces_old_git_signals():
    config = {"slash_git": {"target_catalog_path": "config/slash_git_targets.yaml"}, "activity_graph": {"cache": {"enabled": False}}}
    previous_key = "previous last 7 days"
    fresh_git = _git_counts(commits=1, age_hours=0.01)
    stale_git = _git_counts(commits=1, age_hours=200)

    fresh_service = ActivityGraphService(
        config,
        git_signals=StubGitSignals(fresh_git, per_window={previous_key: _git_counts()}),
        slack_signals=StubSlackSignals(_slack_counts(), per_window={previous_key: _slack_counts()}),
        doc_issue_signals=StubDocIssueSignals(_doc_counts(), per_window={previous_key: _doc_counts()}),
        cache=None,
    )
    stale_service = ActivityGraphService(
        config,
        git_signals=StubGitSignals(stale_git, per_window={previous_key: _git_counts()}),
        slack_signals=StubSlackSignals(_slack_counts(), per_window={previous_key: _slack_counts()}),
        doc_issue_signals=StubDocIssueSignals(_doc_counts(), per_window={previous_key: _doc_counts()}),
        cache=None,
    )
    window = TimeWindow.last_days(7)

    fresh_activity = fresh_service.compute_component_activity("core.payments", window)
    stale_activity = stale_service.compute_component_activity("core.payments", window)

    assert fresh_activity.activity_score == 0.8
    assert stale_activity.activity_score == 0.12  # 0.8 * 0.15 decay


def test_trend_delta_uses_previous_window_counts():
    config = {"slash_git": {"target_catalog_path": "config/slash_git_targets.yaml"}, "activity_graph": {"cache": {"enabled": False}}}
    previous_label = "previous last 7 days"
    current_git = _git_counts(prs=1, age_hours=0.01)
    previous_git = _git_counts(prs=0, commits=0)
    current_slack = _slack_counts(conversations=0, complaints=0)
    previous_slack = _slack_counts(conversations=0, complaints=0)

    service = ActivityGraphService(
        config,
        git_signals=StubGitSignals(current_git, per_window={previous_label: previous_git}),
        slack_signals=StubSlackSignals(current_slack, per_window={previous_label: previous_slack}),
        doc_issue_signals=StubDocIssueSignals(_doc_counts()),
        cache=None,
    )

    window = TimeWindow.last_days(7)
    activity = service.compute_component_activity("core.payments", window)

    assert activity.activity_score == 1.2  # single PR weight
    assert activity.trend_delta == 1.2  # previous window had zero activity

