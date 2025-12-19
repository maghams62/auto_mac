import logging
from typing import Dict

import pytest

from src.config.models import ImpactNotificationSettings
from src.impact.models import ImpactLevel, ImpactReport
from src.impact.notification_service import ImpactNotificationService
from src.impact.notifications import notify_slack_channel, post_pr_comment


def _sample_report() -> ImpactReport:
    return ImpactReport(
        change_id="PR-999",
        change_title="Test change",
        change_summary="Updated auth contract",
        impact_level=ImpactLevel.HIGH,
    )


def test_notify_slack_channel_disabled(caplog: pytest.LogCaptureFixture) -> None:
    settings = ImpactNotificationSettings(
        enabled=False, slack_channel=None, github_app_id=None
    )
    caplog.set_level(logging.INFO)

    notify_slack_channel(_sample_report(), settings)

    assert not caplog.records


def test_notify_slack_channel_enabled_logs(caplog: pytest.LogCaptureFixture) -> None:
    settings = ImpactNotificationSettings(
        enabled=True, slack_channel="#docs-impact", github_app_id=None
    )
    caplog.set_level(logging.INFO)

    notify_slack_channel(_sample_report(), settings)

    assert any("Would notify Slack channel" in record.getMessage() for record in caplog.records)


def test_post_pr_comment_disabled(caplog: pytest.LogCaptureFixture) -> None:
    settings = ImpactNotificationSettings(
        enabled=False, slack_channel=None, github_app_id=None
    )
    caplog.set_level(logging.INFO)

    post_pr_comment(42, "summary", settings)

    assert not caplog.records


def test_post_pr_comment_warns_without_app(caplog: pytest.LogCaptureFixture) -> None:
    settings = ImpactNotificationSettings(
        enabled=True, slack_channel=None, github_app_id=None
    )
    caplog.set_level(logging.WARNING)

    post_pr_comment(42, "summary", settings)

    assert any("GitHub App ID missing" in record.getMessage() for record in caplog.records)


class _NotifierRecorder:
    def __init__(self) -> None:
        self.slack_calls = []
        self.pr_calls = []

    def slack(self, *args, **kwargs):
        self.slack_calls.append({"args": args, "kwargs": kwargs})

    def pr(self, *args, **kwargs):
        self.pr_calls.append({"args": args, "kwargs": kwargs})


def _doc_issue(level: str = "high") -> Dict[str, object]:
    return {
        "impact_level": level,
        "component_ids": ["comp:payments"],
        "service_ids": ["svc:payments"],
        "doc_id": "doc:payments-guide",
        "doc_title": "Payments Guide",
        "doc_url": "https://example.com/docs/payments",
        "links": [
            {"type": "git", "label": "PR-321", "url": "https://github.com/acme/auth/pull/321"},
        ],
        "change_context": {"pr_number": 321},
    }


def test_notification_service_respects_threshold() -> None:
    recorder = _NotifierRecorder()
    settings = ImpactNotificationSettings(
        enabled=True,
        slack_channel="#docs-impact",
        github_app_id="gh-app",
        min_impact_level=ImpactLevel.HIGH,
    )
    service = ImpactNotificationService(
        settings,
        slack_notifier=recorder.slack,
        pr_notifier=recorder.pr,
    )

    emitted = service.maybe_notify(_sample_report(), [_doc_issue(level="medium")])

    assert not emitted
    assert recorder.slack_calls == []
    assert recorder.pr_calls == []


def test_notification_service_emits_payload_when_threshold_met() -> None:
    recorder = _NotifierRecorder()
    settings = ImpactNotificationSettings(
        enabled=True,
        slack_channel="#docs-impact",
        github_app_id="gh-app",
        min_impact_level=ImpactLevel.MEDIUM,
    )
    service = ImpactNotificationService(
        settings,
        slack_notifier=recorder.slack,
        pr_notifier=recorder.pr,
    )

    emitted = service.maybe_notify(_sample_report(), [_doc_issue(level="high")])

    assert emitted
    assert len(recorder.slack_calls) == 1
    slack_kwargs = recorder.slack_calls[0]["kwargs"]
    assert "payload" in slack_kwargs
    assert slack_kwargs["payload"]["impact_level"] == ImpactLevel.HIGH
    assert "High" in slack_kwargs["message"]

    assert len(recorder.pr_calls) == 1
    pr_args = recorder.pr_calls[0]["args"]
    assert pr_args[0] == 321

