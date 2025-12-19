from datetime import datetime, timedelta, timezone
from typing import Dict

from src.activity_graph.models import TimeWindow
from src.activity_graph.service import ActivityGraphService
from src.activity_graph.signals import DocIssueCounts, GitSignalCounts, SlackSignalCounts, SignalEvent


def _event_timestamp(age_hours: float = 0.01) -> datetime:
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
        events.append(SignalEvent(kind=kind, timestamp=_event_timestamp(age_hours)))
    return SlackSignalCounts(conversations=conversations, complaints=complaints, events=events)


def _doc_counts(breakdown: Dict[str, int]) -> DocIssueCounts:
    template = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    template.update(breakdown)
    weights = {"critical": 2.0, "high": 1.5, "medium": 1.0, "low": 0.5}
    severity_weight = sum(template[key] * weights[key] for key in template)
    open_issues = sum(template.values())
    return DocIssueCounts(open_issues=open_issues, severity_weight=severity_weight, severity_breakdown=template)


class StubGitSignals:
    def __init__(self, commits=0, prs=0):
        self.counts = _git_counts(commits=commits, prs=prs)

    def count_events(self, repo, component, window):
        return self.counts


class StubSlackSignals:
    def __init__(self, conversations=0, complaints=0):
        self.counts = _slack_counts(conversations=conversations, complaints=complaints)

    def count(self, component_id, window):
        return self.counts


class StubDocIssueSignals:
    def __init__(self, breakdown=None):
        breakdown = breakdown or {}
        self.counts = _doc_counts(breakdown)

    def count(self, component_id):
        return self.counts


def _service(git=None, slack=None, doc=None):
    config = {"slash_git": {"target_catalog_path": "config/slash_git_targets.yaml"}, "activity_graph": {"cache": {"enabled": False}}}
    return ActivityGraphService(
        config,
        git_signals=git or StubGitSignals(),
        slack_signals=slack or StubSlackSignals(),
        doc_issue_signals=doc or StubDocIssueSignals(),
        cache=None,
    )


def _window():
    return TimeWindow(
        start=datetime(2025, 11, 24, tzinfo=timezone.utc),
        end=datetime(2025, 11, 26, tzinfo=timezone.utc),
        label="test window",
    )


def test_git_events_increase_activity():
    service = _service(git=StubGitSignals(commits=2, prs=1))
    activity = service.compute_component_activity("core.payments", _window())
    assert activity.activity_score == 2.8


def test_slack_complaint_increases_dissatisfaction():
    service = _service(slack=StubSlackSignals(conversations=1, complaints=1))
    activity = service.compute_component_activity("core.payments", _window())
    assert activity.dissatisfaction_score == 0.9


def test_high_severity_doc_issue_spikes_dissatisfaction():
    service = _service(doc=StubDocIssueSignals(breakdown={"high": 1}))
    activity = service.compute_component_activity("core.payments", _window())
    assert activity.dissatisfaction_score == 2.0


def test_custom_weights_are_respected():
    config = {
        "slash_git": {"target_catalog_path": "config/slash_git_targets.yaml"},
        "activity_graph": {
            "cache": {"enabled": False},
            "scoring": {
                "slack": {"conversation_weight": 0.2, "complaint_weight": 1.5},
                "doc_issues": {"severity_weights": {"medium": 3.0}},
                "time_decay": {"buckets": {"1h": 1.0}, "default": 1.0},
            },
        },
    }
    service = ActivityGraphService(
        config,
        git_signals=StubGitSignals(),
        slack_signals=StubSlackSignals(conversations=2, complaints=2),
        doc_issue_signals=StubDocIssueSignals(breakdown={"medium": 1}),
        cache=None,
    )
    activity = service.compute_component_activity("core.payments", _window(), include_debug=True)
    assert activity.dissatisfaction_score == 2 * 1.5 + 1 * 3.0
    assert activity.debug_breakdown["slack_complaints_score"] == 3.0
    assert activity.debug_breakdown["doc_issues_score"] == 3.0


