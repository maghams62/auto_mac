#!/usr/bin/env python3
"""
Seed multi-modal synthetic incident scenarios for development and tests.

This script rewrites the activity ingestion fixture files with richer data so
graph/LLM flows can exercise high-activity, high-dissatisfaction, cross-system,
and doc-drift scenarios. It can also optionally run the ingestion pipeline to
push the fixtures into the activity graph/vector store.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Sequence

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SLACK_FIXTURE = PROJECT_ROOT / "tests/fixtures/activity/slack_activity.yaml"
DEFAULT_GIT_FIXTURE = PROJECT_ROOT / "tests/fixtures/activity/git_activity.yaml"
DEFAULT_DOC_ISSUES_PATH = PROJECT_ROOT / "data/live/doc_issues.json"
DEFAULT_SLACK_EVENTS_PATH = PROJECT_ROOT / "data/synthetic_slack/slack_events.json"
DEFAULT_GIT_EVENTS_PATH = PROJECT_ROOT / "data/synthetic_git/git_events.json"
DEFAULT_GIT_PRS_PATH = PROJECT_ROOT / "data/synthetic_git/git_prs.json"
DEFAULT_SYNTHETIC_DOC_ISSUES_PATH = PROJECT_ROOT / "data/synthetic_git/doc_issues.json"


BASE_TIME = datetime(2025, 12, 6, 15, tzinfo=timezone.utc)


def iso(hours_ago: float) -> str:
    return (BASE_TIME - timedelta(hours=hours_ago)).replace(microsecond=0).isoformat()


def slack_ts(hours_ago: float) -> str:
    dt = BASE_TIME - timedelta(hours=hours_ago)
    return f"{int(dt.timestamp())}.000000"


@dataclass
class SlackMessage:
    channel_id: str
    channel_name: str
    user: str
    text: str
    hours_ago: float
    reactions: List[Dict[str, Any]] = field(default_factory=list)
    thread_ts: str | None = None
    component_ids: Sequence[str] = field(default_factory=list)
    service_ids: Sequence[str] = field(default_factory=list)
    related_apis: Sequence[str] = field(default_factory=list)
    labels: Sequence[str] = field(default_factory=list)

    def to_fixture(self) -> Dict[str, Any]:
        payload = {
            "channel_id": self.channel_id,
            "channel_name": self.channel_name,
            "ts": slack_ts(self.hours_ago),
            "user": self.user,
            "text": self.text,
            "reactions": self.reactions or [],
        }
        if self.thread_ts:
            payload["thread_ts"] = self.thread_ts
        return payload

    def to_event(self, scenario_id: str) -> Dict[str, Any]:
        ts_value = slack_ts(self.hours_ago)
        labels = list(self.labels or [])
        if scenario_id not in labels:
            labels.append(scenario_id)
        return {
            "id": f"slack_message:{self.channel_name}:{ts_value}",
            "source_type": "slack_message",
            "workspace": "demo",
            "channel": self.channel_name,
            "channel_id": self.channel_id,
            "thread_ts": self.thread_ts or ts_value,
            "message_ts": ts_value,
            "user": self.user,
            "timestamp": iso(self.hours_ago),
            "text_raw": self.text,
            "service_ids": list(self.service_ids),
            "component_ids": list(self.component_ids),
            "related_apis": list(self.related_apis),
            "labels": labels,
        }


@dataclass
class GitFile:
    filename: str
    status: str = "modified"
    additions: int = 0
    deletions: int = 0

    def to_fixture(self) -> Dict[str, Any]:
        return {
            "filename": self.filename,
            "status": self.status,
            "additions": self.additions,
            "deletions": self.deletions,
        }


@dataclass
class GitCommit:
    sha: str
    message: str
    author: str
    hours_ago: float
    files: Sequence[GitFile]
    repo: str
    branch: str = "main"
    repo_url: str | None = None
    component_ids: Sequence[str] = field(default_factory=list)
    service_ids: Sequence[str] = field(default_factory=list)
    changed_apis: Sequence[str] = field(default_factory=list)
    is_doc_change: bool = False

    def to_fixture(self) -> Dict[str, Any]:
        return {
            "sha": self.sha,
            "message": self.message,
            "author": self.author,
            "date": iso(self.hours_ago),
            "files": [file.to_fixture() for file in self.files],
        }

    def to_event(self, scenario_id: str) -> Dict[str, Any]:
        repo_url = self.repo_url or f"https://github.com/acme/{self.repo}"
        files_changed = [file.filename for file in self.files]
        labels = [scenario_id]
        return {
            "id": f"git_commit:{self.repo}:{self.sha}",
            "source_type": "git_commit",
            "repo": self.repo,
            "repo_url": repo_url,
            "branch": self.branch,
            "commit_sha": self.sha,
            "author": self.author,
            "timestamp": iso(self.hours_ago),
            "message": self.message,
            "files_changed": files_changed,
            "text_for_embedding": self.message,
            "service_ids": list(self.service_ids),
            "component_ids": list(self.component_ids),
            "changed_apis": list(self.changed_apis),
            "is_doc_change": self.is_doc_change,
            "labels": labels,
        }


@dataclass
class GitPR:
    number: int
    title: str
    author: str
    hours_ago: float
    files: Sequence[GitFile]
    description: str = ""
    state: str = "merged"
    url: str | None = None
    repo: str = "core-api"
    branch: str = "main"
    repo_url: str | None = None
    component_ids: Sequence[str] = field(default_factory=list)
    service_ids: Sequence[str] = field(default_factory=list)
    changed_apis: Sequence[str] = field(default_factory=list)
    labels: Sequence[str] = field(default_factory=list)

    def to_fixture(self) -> Dict[str, Any]:
        merged_at = iso(self.hours_ago)
        return {
            "number": self.number,
            "title": self.title,
            "author": self.author,
            "state": self.state,
            "merged_at": merged_at,
            "url": self.url or f"https://example.com/pr/{self.number}",
            "description": self.description,
            "files": [file.to_fixture() for file in self.files],
        }

    def to_event(self, scenario_id: str) -> Dict[str, Any]:
        repo_url = self.repo_url or f"https://github.com/acme/{self.repo}"
        files_changed = [file.filename for file in self.files]
        labels = list(self.labels or [])
        if scenario_id not in labels:
            labels.append(scenario_id)
        return {
            "id": f"git_pr:{self.repo}:{self.number}",
            "source_type": "git_pr",
            "repo": self.repo,
            "repo_url": repo_url,
            "branch": self.branch,
            "pr_number": self.number,
            "author": self.author,
            "timestamp": iso(self.hours_ago),
            "title": self.title,
            "body": self.description,
            "merged": self.state.lower() == "merged",
            "files_changed": files_changed,
            "text_for_embedding": f"PR #{self.number}: {self.title}",
            "service_ids": list(self.service_ids),
            "component_ids": list(self.component_ids),
            "changed_apis": list(self.changed_apis),
            "labels": labels,
        }


@dataclass
class GitIssue:
    number: int
    title: str
    labels: Sequence[str]
    hours_ago: float
    body: str = ""
    state: str = "open"
    reactions: int = 0
    comments: int = 0
    url: str | None = None
    author: str = "synthetic-user"

    def to_fixture(self) -> Dict[str, Any]:
        return {
            "number": self.number,
            "title": self.title,
            "body": self.body,
            "state": self.state,
            "labels": list(self.labels),
            "reactions": self.reactions,
            "comments": self.comments,
            "updated_at": iso(self.hours_ago),
            "created_at": iso(self.hours_ago + 2),
            "url": self.url or f"https://example.com/issues/{self.number}",
            "author": self.author,
        }


@dataclass
class DocIssue:
    issue_id: str
    summary: str
    component_ids: Sequence[str]
    severity: str
    repo_id: str
    doc_path: str | None
    doc_title: str
    hours_ago: float
    tags: Sequence[str] = field(default_factory=list)
    state: str = "open"
    doc_url: str | None = None

    def to_record(self) -> Dict[str, Any]:
        timestamp = iso(self.hours_ago)
        return {
            "id": self.issue_id,
            "summary": self.summary,
            "component_ids": list(self.component_ids),
            "severity": self.severity,
            "repo_id": self.repo_id,
            "doc_path": self.doc_path,
            "doc_title": self.doc_title,
            "doc_url": self.doc_url,
            "source": "impact-report",
            "state": self.state,
            "labels": list(self.tags),
            "created_at": timestamp,
            "updated_at": timestamp,
        }


@dataclass
class Scenario:
    scenario_id: str
    label: str
    slack: Sequence[SlackMessage] = field(default_factory=list)
    git_commits: Sequence[GitCommit] = field(default_factory=list)
    git_prs: Sequence[GitPR] = field(default_factory=list)
    git_issues: Sequence[GitIssue] = field(default_factory=list)
    doc_issues: Sequence[DocIssue] = field(default_factory=list)


def build_scenarios() -> List[Scenario]:
    return [
        Scenario(
            scenario_id="core_api_vat_break",
            label="High activity, low dissatisfaction",
            slack=[
                SlackMessage(
                    channel_id="C0123PAYMENTS",
                    channel_name="#payments-team",
                    user="alice",
                    text="Vat enforcement landing now. Please validate downstream clients but no user noise so far.",
                    hours_ago=6,
                    reactions=[{"name": "eyes", "count": 3}],
                ),
                SlackMessage(
                    channel_id="C0123PAYMENTS",
                    channel_name="#payments-team",
                    user="pm",
                    text="Docs PR is queued. Billing service confirmed incompatibilities resolved.",
                    hours_ago=4.5,
                ),
            ],
            git_commits=[
                GitCommit(
                    sha="coreapi-require-vat",
                    message="feat!: require vat_code for EU payments",
                    author="alice",
                    hours_ago=30,
                    files=[
                        GitFile("core-api/src/payments.py", additions=64, deletions=18),
                        GitFile("core-api/openapi/payments.yaml", additions=20, deletions=4),
                    ],
                    repo="core-api",
                    component_ids=["core.payments"],
                    service_ids=["core-api-service"],
                    changed_apis=["/v1/payments/create"],
                ),
                GitCommit(
                    sha="billing-honor-vat",
                    message="feat: update billing checkout to send vat_code",
                    author="bob",
                    hours_ago=22,
                    files=[
                        GitFile("billing-service/src/checkout.py", additions=48, deletions=12),
                        GitFile("billing-service/src/core_api_client.py", additions=16, deletions=2),
                    ],
                    repo="billing-service",
                    component_ids=["billing.checkout"],
                    service_ids=["billing-service"],
                    changed_apis=["/v1/payments/create"],
                ),
                GitCommit(
                    sha="docs-portal-vat-refresh",
                    message="docs: refresh payments API guide with vat_code details",
                    author="eve",
                    hours_ago=18,
                    files=[
                        GitFile("docs-portal/docs/payments_api.md", additions=32, deletions=6),
                        GitFile("docs-portal/docs/billing_flows.md", additions=18, deletions=3),
                    ],
                    repo="docs-portal",
                    component_ids=["docs.payments"],
                    service_ids=["docs-portal"],
                    changed_apis=["/v1/payments/create"],
                    is_doc_change=True,
                ),
            ],
            git_prs=[
                GitPR(
                    number=2041,
                    title="feat!: enforce vat_code in core API",
                    author="alice",
                    hours_ago=20,
                    files=[
                        GitFile("core-api/src/payments.py", additions=64, deletions=18),
                        GitFile("core-api/openapi/payments.yaml", additions=20, deletions=4),
                    ],
                    description="Breaking change for EU merchants. Downstream services must send vat_code.",
                    repo="core-api",
                    component_ids=["core.payments"],
                    service_ids=["core-api-service"],
                    changed_apis=["/v1/payments/create"],
                    labels=["breaking_change"],
                )
            ],
            git_issues=[
                GitIssue(
                    number=9832,
                    title="Docs still suggest vat_code optional",
                    labels=["docs", "bug"],
                    hours_ago=15,
                    reactions=4,
                    comments=3,
                    body="Payments docs still say vat_code is optional which contradicts new release.",
                )
            ],
            doc_issues=[
                DocIssue(
                    issue_id="docissue-coreapi-vat",
                    summary="Docs portal promises optional vat_code but API enforces it.",
                    component_ids=["docs.payments", "core.payments"],
                    severity="high",
                    repo_id="docs-portal",
                    doc_path="docs/payments_api.md",
                    doc_title="Payments API",
                    doc_url="https://docs.example.com/payments",
                    hours_ago=14,
                    tags=["vat", "payments"],
                )
            ],
        ),
        Scenario(
            scenario_id="billing_support_spike",
            label="High dissatisfaction, moderate activity",
            slack=[
                SlackMessage(
                    channel_id="C123SUPPORT",
                    channel_name="#support",
                    user="csm",
                    text="Merchants on plan B seeing 429s after quota change. Need hotfix asap.",
                    hours_ago=9,
                    reactions=[{"name": "thumbsdown", "count": 4}],
                ),
                SlackMessage(
                    channel_id="C0A0DNAHK2R",
                    channel_name="#incidents",
                    user="support",
                    text="Escalated to Sev2. Customers referencing ticket INC-4412 and INC-4413.",
                    hours_ago=8.5,
                    reactions=[{"name": "rage", "count": 2}],
                ),
                SlackMessage(
                    channel_id="C123SUPPORT",
                    channel_name="#support",
                    user="se",
                    text="Need billing-service patch that respects new quota config by noon PT.",
                    hours_ago=8,
                ),
            ],
            git_commits=[
                GitCommit(
                    sha="billing-guardrails",
                    message="fix: respect dynamic quota config",
                    author="carol",
                    hours_ago=7.5,
                    files=[
                        GitFile("billing-service/src/pricing/plan_config.py", additions=28, deletions=6),
                        GitFile("billing-service/src/checkout.py", additions=12, deletions=3),
                    ],
                    repo="billing-service",
                    component_ids=["billing.checkout"],
                    service_ids=["billing-service"],
                    changed_apis=["/v1/payments/create"],
                )
            ],
            git_prs=[
                GitPR(
                    number=3120,
                    title="fix: stop hard-coding free tier quota",
                    author="carol",
                    hours_ago=7,
                    files=[
                        GitFile("billing-service/src/pricing/plan_config.py", additions=28, deletions=6),
                        GitFile("billing-service/src/checkout.py", additions=12, deletions=3),
                    ],
                    description="Pull quota from config service so UI + backend align.",
                    state="open",
                    repo="billing-service",
                    component_ids=["billing.checkout"],
                    service_ids=["billing-service"],
                    changed_apis=["/v1/payments/create"],
                    labels=["support_escalation"],
                )
            ],
            git_issues=[
                GitIssue(
                    number=9931,
                    title="Customers hitting 429 despite upgraded plan",
                    labels=["bug", "priority"],
                    hours_ago=9.5,
                    reactions=6,
                    comments=5,
                    body="Quota mismatch causing premium customers to throttle at 300 requests.",
                )
            ],
            doc_issues=[
                DocIssue(
                    issue_id="docissue-billing-free-tier",
                    summary="Billing onboarding doc still references 1000 free requests.",
                    component_ids=["docs.payments", "billing.checkout"],
                    severity="high",
                    repo_id="docs-portal",
                    doc_path="docs/billing_flows.md",
                    doc_title="Billing Flows",
                    doc_url="https://docs.example.com/billing/onboarding",
                    hours_ago=9,
                    tags=["quota", "billing"],
                )
            ],
        ),
        Scenario(
            scenario_id="notifications_template_break",
            label="Cross-system API break",
            slack=[
                SlackMessage(
                    channel_id="C0A0DNAHK2R",
                    channel_name="#incidents",
                    user="ops",
                    text="Template version requirement broke ServiceB + ServiceC notifications.",
                    hours_ago=5.5,
                    reactions=[{"name": "warning", "count": 2}, {"name": "thumbsdown", "count": 1}],
                ),
                SlackMessage(
                    channel_id="C0456AUTH",
                    channel_name="#security-team",
                    user="dave",
                    text="Compliance insisted on template_version. Need downstream owners aligned.",
                    hours_ago=5,
                ),
            ],
            git_commits=[
                GitCommit(
                    sha="notifications-template-version",
                    message="feat!: require template_version for receipt notifications",
                    author="dave",
                    hours_ago=12,
                    files=[
                        GitFile("notifications-service/src/notifications.py", additions=44, deletions=10),
                        GitFile("notifications-service/src/scheduler.py", additions=10, deletions=2),
                    ],
                    repo="notifications-service",
                    component_ids=["notifications.dispatch"],
                    service_ids=["notifications-service"],
                    changed_apis=["/v1/notifications/send"],
                ),
                GitCommit(
                    sha="docs-template-gap",
                    message="docs: backlog TODO for template_version rollout",
                    author="eve",
                    hours_ago=10,
                    files=[
                        GitFile("docs-portal/docs/notification_playbook.md", additions=15, deletions=1),
                        GitFile("docs-portal/docs/changelog.md", additions=6, deletions=0),
                    ],
                    repo="docs-portal",
                    component_ids=["docs.notifications"],
                    service_ids=["docs-portal"],
                    changed_apis=["/v1/notifications/send"],
                    is_doc_change=True,
                ),
            ],
            git_prs=[
                GitPR(
                    number=4102,
                    title="feat: template version enforcement",
                    author="dave",
                    hours_ago=11.5,
                    files=[
                        GitFile("notifications-service/src/notifications.py", additions=44, deletions=10),
                        GitFile("notifications-service/src/scheduler.py", additions=10, deletions=2),
                    ],
                    description="Enforce template_version to unblock compliance auditing.",
                    repo="notifications-service",
                    component_ids=["notifications.dispatch"],
                    service_ids=["notifications-service"],
                    changed_apis=["/v1/notifications/send"],
                    labels=["cross_system"],
                )
            ],
            git_issues=[
                GitIssue(
                    number=10011,
                    title="Docs missing template_version guidance",
                    labels=["documentation", "notifications"],
                    hours_ago=9.5,
                    reactions=2,
                    comments=1,
                    body="Notification playbook never mentions template_version, causing integrators to fail.",
                )
            ],
            doc_issues=[
                DocIssue(
                    issue_id="docissue-notifications-template",
                    summary="Notification playbook omits template_version field required by API.",
                    component_ids=["docs.notifications", "notifications.dispatch"],
                    severity="medium",
                    repo_id="docs-portal",
                    doc_path="docs/notification_playbook.md",
                    doc_title="Notification Playbook",
                    hours_ago=9,
                    tags=["notifications", "template-version"],
                )
            ],
        ),
        Scenario(
            scenario_id="docs_drift_only",
            label="Doc drift with minimal activity",
            slack=[
                SlackMessage(
                    channel_id="C0123PAYMENTS",
                    channel_name="#payments-team",
                    user="docs",
                    text="Docs still say free tier is 1000 calls. Need final copy review?",
                    hours_ago=3.5,
                )
            ],
            git_commits=[
                GitCommit(
                    sha="coreapi-plan-config",
                    message="chore: tweak free tier defaults to match growth plan",
                    author="quota-demo-bot",
                    hours_ago=40,
                    files=[
                        GitFile("core-api/config/plans/free_tier.yaml", additions=8, deletions=8),
                    ],
                    repo="core-api",
                    component_ids=["core.payments"],
                    service_ids=["core-api-service"],
                    changed_apis=["/v1/payments/create"],
                )
            ],
            doc_issues=[
                DocIssue(
                    issue_id="docissue-pricing-drft",
                    summary="Pricing dashboard copy still promises legacy quotas.",
                    component_ids=["comp:web-dashboard", "comp:docs-portal"],
                    severity="medium",
                    repo_id="web-dashboard",
                    doc_path="src/pages/Pricing.tsx",
                    doc_title="Pricing Page",
                    hours_ago=12,
                    tags=["pricing", "free-tier"],
                )
            ],
        ),
    ]


def build_slack_events(scenarios: Sequence[Scenario]) -> List[Dict[str, Any]]:
    events: List[Dict[str, Any]] = []
    for scenario in scenarios:
        for message in scenario.slack:
            events.append(message.to_event(scenario.scenario_id))
    return events


def build_git_events(scenarios: Sequence[Scenario]) -> List[Dict[str, Any]]:
    events: List[Dict[str, Any]] = []
    for scenario in scenarios:
        for commit in scenario.git_commits:
            events.append(commit.to_event(scenario.scenario_id))
    return events


def build_git_pr_events(scenarios: Sequence[Scenario]) -> List[Dict[str, Any]]:
    events: List[Dict[str, Any]] = []
    for scenario in scenarios:
        for pr in scenario.git_prs:
            events.append(pr.to_event(scenario.scenario_id))
    return events


def dump_yaml(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(payload, handle, sort_keys=False)


def dump_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def run_ingestion(target: str, with_impact: bool = False) -> None:
    cmd = [sys.executable, "scripts/cerebros.py", "ingest", target]
    if with_impact and target in {"all", "git"}:
        cmd.append("--with-impact")
    print(f"[INGEST] Running {' '.join(cmd)}")
    subprocess.run(cmd, cwd=PROJECT_ROOT, check=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed synthetic incident scenarios.")
    parser.add_argument("--slack-fixture", type=Path, default=DEFAULT_SLACK_FIXTURE)
    parser.add_argument("--git-fixture", type=Path, default=DEFAULT_GIT_FIXTURE)
    parser.add_argument("--doc-issues", type=Path, default=DEFAULT_DOC_ISSUES_PATH)
    parser.add_argument("--slack-events", type=Path, default=DEFAULT_SLACK_EVENTS_PATH)
    parser.add_argument("--git-events", type=Path, default=DEFAULT_GIT_EVENTS_PATH)
    parser.add_argument("--git-prs", type=Path, default=DEFAULT_GIT_PRS_PATH)
    parser.add_argument(
        "--synthetic-doc-issues",
        type=Path,
        default=DEFAULT_SYNTHETIC_DOC_ISSUES_PATH,
        help="Location for synthetic doc issue JSON payloads.",
    )
    parser.add_argument("--ingest", action="store_true", help="Run `scripts/cerebros.py ingest` after writing fixtures.")
    parser.add_argument(
        "--ingest-target",
        choices=["all", "slack", "git"],
        default="all",
        help="Target passed to `scripts/cerebros.py ingest` when --ingest is enabled.",
    )
    parser.add_argument(
        "--with-impact",
        action="store_true",
        help="Also trigger doc-issue ingest when calling the Cerebros CLI.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print summary without writing files.")
    args = parser.parse_args()

    scenarios = build_scenarios()
    slack_payload = {
        "messages": [msg.to_fixture() for scenario in scenarios for msg in scenario.slack],
    }
    git_payload = {
        "commits": [commit.to_fixture() for scenario in scenarios for commit in scenario.git_commits],
        "pull_requests": [pr.to_fixture() for scenario in scenarios for pr in scenario.git_prs],
        "issues": [issue.to_fixture() for scenario in scenarios for issue in scenario.git_issues],
    }
    doc_payload = [doc.to_record() for scenario in scenarios for doc in scenario.doc_issues]
    slack_events = build_slack_events(scenarios)
    git_events = build_git_events(scenarios)
    git_pr_events = build_git_pr_events(scenarios)

    if args.dry_run:
        print(json.dumps({"slack_messages": len(slack_payload["messages"]),
                          "git_commits": len(git_payload["commits"]),
                          "git_prs": len(git_payload["pull_requests"]),
                          "git_issues": len(git_payload["issues"]),
                          "doc_issues": len(doc_payload)}, indent=2))
        return 0

    dump_yaml(args.slack_fixture, slack_payload)
    dump_yaml(args.git_fixture, git_payload)
    dump_json(args.doc_issues, doc_payload)
    print(f"[WRITE] Slack fixture -> {args.slack_fixture}")
    print(f"[WRITE] Git fixture   -> {args.git_fixture}")
    print(f"[WRITE] Doc issues    -> {args.doc_issues}")
    dump_json(args.slack_events, slack_events)
    dump_json(args.git_events, git_events)
    dump_json(args.git_prs, git_pr_events)
    dump_json(args.synthetic_doc_issues, doc_payload)
    print(f"[WRITE] Synthetic slack events -> {args.slack_events}")
    print(f"[WRITE] Synthetic git events   -> {args.git_events}")
    print(f"[WRITE] Synthetic git PRs      -> {args.git_prs}")
    print(f"[WRITE] Synthetic doc issues   -> {args.synthetic_doc_issues}")

    if args.ingest:
        run_ingestion(args.ingest_target, args.with_impact)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

