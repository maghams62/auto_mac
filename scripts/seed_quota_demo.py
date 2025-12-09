#!/usr/bin/env python3
"""
Seed + verify the unified free-tier quota demo.

This script can run entirely in synthetic mode (updates fixture files and ingests
them) or live mode (pushes demo commits/Slack threads using configured tokens).
It also runs downstream verification checks so demos fail-fast when signals are
missing from Activity Graph, Doc Issues, or Context Resolution.
"""

from __future__ import annotations

import argparse
import base64
import json
import logging
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import requests
import re

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

try:
    from slack_sdk import WebClient
    from slack_sdk.errors import SlackApiError
except Exception:  # pragma: no cover - optional for synthetic mode
    WebClient = None
    SlackApiError = Exception

from src.agent.doc_insights_agent import (  # type: ignore  # noqa: E402
    get_component_activity,
    get_context_impacts,
    list_doc_issues,
)
from src.config_manager import get_config  # type: ignore  # noqa: E402
from src.ingestion import DocIssueIngestor, GitActivityIngestor, SlackActivityIngestor  # type: ignore  # noqa: E402

logger = logging.getLogger("quota_demo")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def load_json_array(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text(encoding="utf-8")) or []
    except json.JSONDecodeError as exc:  # pragma: no cover - defensive
        logger.warning("Failed to parse %s (%s); treating as empty list", path, exc)
        return []


def dump_json(path: Path, payload: Any) -> None:
    ensure_parent(path)
    path.write_text(json.dumps(payload, indent=2, sort_keys=False) + "\n", encoding="utf-8")


def invoke_tool(tool, **kwargs):
    """
    LangChain 0.1 switched Tool.__call__ signature; prefer invoke() when available.
    """
    if hasattr(tool, "invoke"):
        return tool.invoke(kwargs)
    # Fallback to call for legacy tool instances
    return tool(**kwargs)


@dataclass
class RepoTarget:
    key: str
    repo_id: str
    owner: str
    name: str
    default_branch: str
    demo_branch: str
    component_id: str
    service_id: str
    files: List[str]
    commit_message: str
    api_ids: List[str]
    local_root: Optional[str] = None
    live_mutation: bool = False

    @property
    def full_name(self) -> str:
        return f"{self.owner}/{self.name}"


@dataclass
class DocIssueTemplate:
    key: str
    component_id: str
    repo_id: str
    doc_path: Optional[str]
    severity: str
    tags: List[str]
    summary_template: str


@dataclass
class SlackParticipant:
    handle: str
    user_id: str
    display_name: str
    component_ids: List[str] = field(default_factory=list)
    service_ids: List[str] = field(default_factory=list)


@dataclass
class QuotaSettings:
    legacy: int
    updated: int


@dataclass
class GitCommitSpec:
    repo: RepoTarget
    sha: str
    message: str
    author: str
    timestamp: datetime
    files: List[str]
    description: str

    @property
    def branch(self) -> str:
        return self.repo.demo_branch or self.repo.default_branch


@dataclass
class CheckResult:
    name: str
    passed: bool
    detail: str
    critical: bool = True


class ConfigError(RuntimeError):
    """Raised when required quota_demo config is missing."""


class GitHubAPIError(RuntimeError):
    """Raised when GitHub REST API calls fail."""


class GitHubRepoManager:
    def __init__(self, token: Optional[str]):
        self.token = token
        self.session = requests.Session()
        if token:
            self.session.headers.update(
                {
                    "Authorization": f"token {token}",
                    "Accept": "application/vnd.github+json",
                    "User-Agent": "quota-demo-seeder",
                }
            )

    def ensure_branch(self, repo: RepoTarget) -> None:
        if not self.token:
            raise GitHubAPIError("Missing GITHUB_TOKEN; cannot mutate live repos.")

        target_ref = f"refs/heads/{repo.demo_branch}"
        ref_url = f"https://api.github.com/repos/{repo.full_name}/git/ref/{target_ref}"
        response = self.session.get(ref_url, timeout=30)
        if response.status_code == 200:
            return
        if response.status_code not in (404, 422):
            raise GitHubAPIError(f"Failed to check branch {target_ref}: {response.text}")

        base_ref = f"refs/heads/{repo.default_branch}"
        base_url = f"https://api.github.com/repos/{repo.full_name}/git/ref/{base_ref}"
        base_resp = self.session.get(base_url, timeout=30)
        if base_resp.status_code != 200:
            raise GitHubAPIError(
                f"Failed to read base branch {base_ref}: {base_resp.status_code} {base_resp.text}"
            )
        base_sha = base_resp.json().get("object", {}).get("sha")
        if not base_sha:
            raise GitHubAPIError(f"Base branch {base_ref} missing SHA payload.")

        create_resp = self.session.post(
            f"https://api.github.com/repos/{repo.full_name}/git/refs",
            json={"ref": target_ref, "sha": base_sha},
            timeout=30,
        )
        if create_resp.status_code not in (200, 201):
            raise GitHubAPIError(
                f"Failed to create branch {target_ref}: {create_resp.status_code} {create_resp.text}"
            )
        logger.info("Created branch %s for %s", repo.demo_branch, repo.full_name)

    def update_file(
        self,
        repo: RepoTarget,
        path: str,
        mutate_fn,
        message: str,
    ) -> bool:
        """
        Fetch a file, mutate its contents, and push back to the demo branch.

        Returns True if file changed, False otherwise.
        """
        if not self.token:
            raise GitHubAPIError("Missing GITHUB_TOKEN; cannot mutate live repos.")

        url = f"https://api.github.com/repos/{repo.full_name}/contents/{path.lstrip('/')}"
        params = {"ref": repo.demo_branch or repo.default_branch}
        response = self.session.get(url, params=params, timeout=30)
        if response.status_code != 200:
            raise GitHubAPIError(
                f"Failed to fetch {path} from {repo.full_name}: {response.status_code} {response.text}"
            )
        payload = response.json()
        encoded_content = payload.get("content") or ""
        current_text = base64.b64decode(encoded_content.encode("utf-8")).decode("utf-8")
        updated_text = mutate_fn(current_text)
        if updated_text == current_text:
            logger.info("No live change needed for %s:%s", repo.repo_id, path)
            return False

        put_resp = self.session.put(
            url,
            json={
                "message": message,
                "content": base64.b64encode(updated_text.encode("utf-8")).decode("utf-8"),
                "branch": repo.demo_branch or repo.default_branch,
                "sha": payload.get("sha"),
            },
            timeout=30,
        )
        if put_resp.status_code not in (200, 201):
            raise GitHubAPIError(
                f"Failed to update {path} in {repo.full_name}: {put_resp.status_code} {put_resp.text}"
            )
        logger.info(
            "Updated %s in %s (branch %s)",
            path,
            repo.full_name,
            repo.demo_branch or repo.default_branch,
        )
        return True


class DocIssueStore:
    def __init__(self, scenario_path: Path, aggregate_path: Path):
        self.scenario_path = scenario_path
        self.aggregate_path = aggregate_path

    def sync(self, issues: List[Dict[str, Any]]) -> None:
        dump_json(self.scenario_path, issues)
        aggregate_records = load_json_array(self.aggregate_path)
        by_id = {record.get("id"): record for record in aggregate_records if record.get("id")}
        for issue in issues:
            by_id[issue["id"]] = issue
        dump_json(self.aggregate_path, list(by_id.values()))


class QuotaDemoSeeder:
    def __init__(self, config: Dict[str, Any], *, mode: str, dry_run: bool = False):
        self.config = config
        self.mode = mode
        self.dry_run = dry_run
        self.demo_cfg = config.get("quota_demo") or {}
        if not self.demo_cfg:
            raise ConfigError("quota_demo block missing from config.yaml")
        self.quota = QuotaSettings(
            legacy=int(self._config_get(("quotas", "legacy_free_tier"), fallback=1000)),
            updated=int(self._config_get(("quotas", "updated_free_tier"), fallback=300)),
        )
        self.synthetic_paths = {
            "slack": self._resolve_path(("synthetic", "slack_fixture_path")),
            "git_events": self._resolve_path(("synthetic", "git_events_path")),
            "git_prs": self._resolve_path(("synthetic", "git_prs_path")),
            "doc_issues": self._resolve_path(("synthetic", "doc_issues_path")),
        }
        ag_cfg = config.get("activity_graph") or {}
        self.aggregate_doc_issue_path = PROJECT_ROOT / Path(
            ag_cfg.get("doc_issues_path", "data/live/doc_issues.json")
        )
        self.doc_issue_store = DocIssueStore(
            scenario_path=self.synthetic_paths["doc_issues"],
            aggregate_path=self.aggregate_doc_issue_path,
        )
        self.slack_cfg = self.demo_cfg.get("slack") or {}
        self.repo_targets = self._load_repo_targets()
        self.doc_issue_templates = self._load_doc_issue_templates()
        self.slack_participants = self._load_participants()
        verification_cfg = self.demo_cfg.get("verification") or {}
        self.verification_targets = {
            "activity": verification_cfg.get("activity_component"),
            "doc": verification_cfg.get("doc_component"),
            "context": verification_cfg.get("context_root_component"),
            "doc_repo": verification_cfg.get("doc_repo_id", "docs-portal"),
        }
        missing = [key for key, value in self.verification_targets.items() if not value]
        if missing:
            raise ConfigError(f"quota_demo.verification missing keys: {', '.join(missing)}")
        self.step_results: List[CheckResult] = []

    def _config_get(self, path: Sequence[str], fallback: Any = None) -> Any:
        data = self.demo_cfg
        for key in path:
            if not isinstance(data, dict) or key not in data:
                return fallback
            data = data[key]
        return data

    def _resolve_path(self, path: Sequence[str]) -> Path:
        raw = self._config_get(path)
        if not raw:
            raise ConfigError(f"Missing quota_demo.{'.'.join(path)}")
        return PROJECT_ROOT / Path(raw)

    def _load_repo_targets(self) -> List[RepoTarget]:
        repo_cfg = (self.demo_cfg.get("git") or {}).get("repos") or {}
        targets: List[RepoTarget] = []
        for key, value in repo_cfg.items():
            try:
                targets.append(
                    RepoTarget(
                        key=key,
                        repo_id=str(value.get("repo_id") or key),
                        owner=value["owner"],
                        name=value["name"],
                        default_branch=value.get("default_branch", "main"),
                        demo_branch=value.get("demo_branch", "quota-demo"),
                        component_id=value["component_id"],
                        service_id=value["service_id"],
                        files=list(value.get("files") or []),
                        commit_message=value["commit_message"],
                        api_ids=list(value.get("api_ids") or []),
                        local_root=value.get("local_root"),
                        live_mutation=bool(value.get("live_mutation", False)),
                    )
                )
            except KeyError as exc:  # pragma: no cover - config guards
                raise ConfigError(f"quota_demo.git.repos.{key} missing {exc}") from exc
        if not targets:
            raise ConfigError("quota_demo.git.repos is empty")
        return targets

    def _load_doc_issue_templates(self) -> List[DocIssueTemplate]:
        templates_cfg = (self.demo_cfg.get("doc_issues") or {}).get("templates") or []
        templates = []
        for entry in templates_cfg:
            templates.append(
                DocIssueTemplate(
                    key=entry["key"],
                    component_id=entry["component_id"],
                    repo_id=entry["repo_id"],
                    doc_path=entry.get("doc_path"),
                    severity=entry.get("severity", "high"),
                    tags=list(entry.get("tags") or []),
                    summary_template=entry.get("summary_template", ""),
                )
            )
        if not templates:
            raise ConfigError("quota_demo.doc_issues.templates is empty")
        return templates

    def _load_participants(self) -> Dict[str, SlackParticipant]:
        participants_cfg = self.slack_cfg.get("participants") or []
        participants: Dict[str, SlackParticipant] = {}
        for entry in participants_cfg:
            handle = entry.get("handle")
            if not handle:
                continue
            participants[handle] = SlackParticipant(
                handle=handle,
                user_id=entry.get("user_id", handle),
                display_name=entry.get("display_name", handle),
                component_ids=list(entry.get("component_ids") or []),
                service_ids=list(entry.get("service_ids") or []),
            )
        return participants

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def run(self) -> bool:
        logger.info("Running quota demo seeder (mode=%s, dry_run=%s)", self.mode, self.dry_run)
        if self.mode == "synthetic":
            self._run_synthetic()
        else:
            self._run_live()

        if self.dry_run:
            logger.info("Dry-run complete; verification skipped.")
            self._record_result(
                CheckResult(
                    name="Verification",
                    passed=True,
                    detail="Skipped because --dry-run enabled",
                    critical=False,
                )
            )
            self._print_summary()
            return True

        self._run_verification_checks()
        self._print_summary()
        return all(result.passed or not result.critical for result in self.step_results)

    # ------------------------------------------------------------------
    # Synthetic mode
    # ------------------------------------------------------------------
    def _run_synthetic(self) -> None:
        logger.info("Seeding synthetic fixtures")
        commits = self._build_synthetic_commits()
        slack_messages = self._build_slack_messages()
        doc_issues = self._build_doc_issues(commits)

        if self.dry_run:
            logger.info("[dry-run] Would write %s git commits, %s slack messages, %s doc issues",
                        len(commits), len(slack_messages), len(doc_issues))
            return

        self._write_git_events(commits)
        self._write_slack_events(slack_messages)
        self.doc_issue_store.sync(doc_issues)
        self._record_result(CheckResult("Fixtures", True, "Synthetic fixtures updated", critical=False))

        self._ingest_synthetic(slack_messages, commits)

    def _build_synthetic_commits(self) -> List[GitCommitSpec]:
        specs: List[GitCommitSpec] = []
        start_time = utc_now() - timedelta(minutes=15)
        for idx, repo in enumerate(self.repo_targets):
            if repo.repo_id not in {"core-api", "billing-service"}:
                continue
            timestamp = start_time + timedelta(minutes=idx * 5)
            sha = f"quota-demo-{repo.repo_id}-{timestamp.strftime('%Y%m%d%H%M%S')}"
            message = repo.commit_message.format(legacy=self.quota.legacy, updated=self.quota.updated)
            description = (
                f"Update {repo.repo_id} free tier settings so services enforce {self.quota.updated} calls "
                f"instead of {self.quota.legacy}."
            )
            specs.append(
                GitCommitSpec(
                    repo=repo,
                    sha=sha,
                    message=message,
                    author="quota-demo-bot",
                    timestamp=timestamp,
                    files=list(repo.files),
                    description=description,
                )
            )
        return specs

    def _build_slack_messages(self) -> List[Dict[str, Any]]:
        channel = self.slack_cfg.get("channel_name", "#support")
        channel_id = self.slack_cfg.get("channel_id", "CDEMO")
        workspace = self.slack_cfg.get("workspace", "quota-demo")
        base_ts = utc_now() - timedelta(minutes=2)
        root_ts = self.slack_cfg.get("default_thread_ts") or f"{base_ts.timestamp():.5f}"
        thread_entries = self._slack_story_templates()

        messages: List[Dict[str, Any]] = []
        for idx, entry in enumerate(thread_entries):
            ts_epoch = base_ts + timedelta(seconds=idx * 75)
            message_ts = f"{ts_epoch.timestamp():.5f}"
            participant = self.slack_participants.get(entry["handle"])
            user_name = participant.display_name if participant else entry["handle"]
            text = entry["text"].format(
                legacy=f"{self.quota.legacy:,}",
                updated=f"{self.quota.updated:,}",
            )
            component_ids = entry.get("component_ids") or (participant.component_ids if participant else [])
            service_ids = entry.get("service_ids") or (participant.service_ids if participant else [])
            payload = {
                "id": f"slack_message:{channel}:{message_ts}",
                "source_type": "slack_message",
                "workspace": workspace,
                "channel": channel,
                "channel_id": channel_id,
                "thread_ts": root_ts,
                "message_ts": message_ts,
                "user": user_name,
                "timestamp": ts_epoch.isoformat(),
                "text_raw": text,
                "service_ids": service_ids,
                "component_ids": component_ids,
                "related_apis": entry.get("api_ids"),
                "labels": entry.get("labels"),
            }
            messages.append(payload)

        summary_text = (
            "Support thread capturing quota drift: customers are throttled at "
            f"{self.quota.updated:,} calls while docs/UI still promise {self.quota.legacy:,}."
        )
        messages.append(
            {
                "id": f"slack_thread:{channel}:{root_ts}",
                "source_type": "slack_thread_summary",
                "workspace": workspace,
                "channel": channel,
                "channel_id": channel_id,
                "thread_ts": root_ts,
                "message_ts": root_ts,
                "timestamp": base_ts.isoformat(),
                "start_timestamp": base_ts.isoformat(),
                "end_timestamp": (base_ts + timedelta(seconds=len(thread_entries) * 75)).isoformat(),
                "text_raw": summary_text,
                "service_ids": ["core-api-service", "billing-service"],
                "component_ids": ["comp:core-api", "comp:billing-service"],
                "related_apis": ["/v1/payments/create"],
                "labels": ["support_summary", "quota_drift"],
            }
        )
        return messages

    def _slack_story_templates(self) -> List[Dict[str, Any]]:
        return [
            {
                "handle": "csm",
                "labels": ["support_complaint", "quota", "doc_drift"],
                "component_ids": ["comp:web-dashboard", "comp:docs-portal", "comp:core-api"],
                "service_ids": ["web-dashboard-service", "docs-portal", "core-api-service"],
                "api_ids": ["/v1/payments/create"],
                "text": (
                    "Seeing a spike in tickets: free-tier customers get throttled after ~{updated} requests "
                    "but our docs + dashboard still promise {legacy} per month."
                ),
            },
            {
                "handle": "se",
                "labels": ["incident", "quota"],
                "component_ids": ["comp:core-api"],
                "service_ids": ["core-api-service"],
                "api_ids": ["/v1/payments/create"],
                "text": (
                    "Confirmed in logs: core-api rolled out monetization last week and now enforces {updated} "
                    "calls for free tier."
                ),
            },
            {
                "handle": "billing",
                "labels": ["coordination", "billing"],
                "component_ids": ["comp:billing-service"],
                "service_ids": ["billing-service"],
                "api_ids": ["/v1/payments/create"],
                "text": (
                    "billing-service config is synced to {updated}. I don't see any commits on web-dashboard "
                    "or docs-portal updating the {legacy} copy though."
                ),
            },
            {
                "handle": "docs",
                "labels": ["doc_issue"],
                "component_ids": ["comp:docs-portal"],
                "service_ids": ["docs-portal"],
                "api_ids": ["/v1/payments/create"],
                "text": (
                    "Docs in docs-portal/pricing/free_tier.md still advertise {legacy} calls/month. "
                    "Logging a doc issue now."
                ),
            },
            {
                "handle": "pm",
                "labels": ["alignment", "quota"],
                "component_ids": ["comp:core-api", "comp:web-dashboard", "comp:docs-portal"],
                "service_ids": ["core-api-service", "web-dashboard-service", "docs-portal"],
                "api_ids": ["/v1/payments/create"],
                "text": (
                    "For the next release we must align core-api, billing-service, web-dashboard, and docs-portal. "
                    "Free tier == {updated} requests until we revisit pricing."
                ),
            },
        ]

    def _build_doc_issues(self, commits: List[GitCommitSpec]) -> List[Dict[str, Any]]:
        now_iso = utc_now().isoformat()
        commit_lookup = {commit.repo.repo_id: commit for commit in commits}
        issues: List[Dict[str, Any]] = []
        for template in self.doc_issue_templates:
            linked_change = f"{template.repo_id}@quota-demo"
            change = commit_lookup.get(template.repo_id)
            if change:
                linked_change = f"{template.repo_id}@{change.sha}"
            summary = template.summary_template.format(
                legacy=f"{self.quota.legacy:,}",
                updated=f"{self.quota.updated:,}",
            )
            doc_path = template.doc_path or f"docs/{template.key}.md"
            doc_id = f"doc:{doc_path}"
            repo_target = next((repo for repo in self.repo_targets if repo.repo_id == template.repo_id), None)
            doc_url = ""
            if repo_target:
                doc_url = (
                    f"https://github.com/{repo_target.full_name}/blob/"
                    f"{repo_target.demo_branch or repo_target.default_branch}/{doc_path}"
                )
            issues.append(
                {
                    "id": f"impact:quota-demo:{template.key}",
                    "doc_id": doc_id,
                    "doc_title": template.key.replace("-", " ").title(),
                    "doc_path": doc_path,
                    "doc_url": doc_url,
                    "repo_id": template.repo_id,
                    "component_ids": [template.component_id],
                    "service_ids": [repo_target.service_id] if repo_target else [],
                    "impact_level": "high" if template.severity == "high" else "medium",
                    "severity": template.severity,
                    "source": "impact-report",
                    "linked_change": linked_change,
                    "change_context": {
                        "identifier": linked_change,
                        "repo": template.repo_id,
                        "title": "Quota alignment demo",
                        "source_kind": "git",
                    },
                    "change_title": "Quota misalignment",
                    "summary": summary,
                    "labels": template.tags,
                    "created_at": now_iso,
                    "updated_at": now_iso,
                    "detected_at": now_iso,
                    "state": "open",
                }
            )
        return issues

    def _write_git_events(self, commits: List[GitCommitSpec]) -> None:
        events = load_json_array(self.synthetic_paths["git_events"])
        by_id = {entry.get("id"): entry for entry in events if entry.get("id")}
        for commit in commits:
            event = {
                "id": f"git_commit:{commit.repo.repo_id}:{commit.sha}",
                "source_type": "git_commit",
                "repo": commit.repo.repo_id,
                "repo_url": f"https://github.com/{commit.repo.full_name}",
                "branch": commit.branch,
                "commit_sha": commit.sha,
                "author": commit.author,
                "timestamp": commit.timestamp.isoformat(),
                "message": commit.message,
                "files_changed": commit.files,
                "text_for_embedding": f"{commit.message}\n\n{commit.description}",
                "service_ids": [commit.repo.service_id],
                "component_ids": [commit.repo.component_id],
                "changed_apis": commit.repo.api_ids,
                "is_doc_change": False,
            }
            by_id[event["id"]] = event
        dump_json(self.synthetic_paths["git_events"], list(by_id.values()))

    def _write_slack_events(self, messages: List[Dict[str, Any]]) -> None:
        events = load_json_array(self.synthetic_paths["slack"])
        by_id = {entry.get("id"): entry for entry in events if entry.get("id")}
        for message in messages:
            by_id[message["id"]] = message
        dump_json(self.synthetic_paths["slack"], list(by_id.values()))

    def _ingest_synthetic(self, slack_messages: List[Dict[str, Any]], commits: List[GitCommitSpec]) -> None:
        config = get_config()
        slack_ingestor = SlackActivityIngestor(config)

        try:
            slack_result = slack_ingestor.ingest_fixture_messages({"messages": slack_messages})
            git_fixtures_by_repo = self._group_commits_by_repo(commits)
            for repo_id, payload in git_fixtures_by_repo.items():
                repo, repo_commits = payload
                repo_config = self._with_single_repo(config, repo_id)
                repo_ingestor = GitActivityIngestor(repo_config)
                repo_ingestor.ingest_fixtures(
                    {"commits": repo_commits},
                    repo_identifier=repo_id,
                )
                repo_ingestor.close()
            doc_cfg = self._with_doc_issue_override(config)
            doc_ingestor = DocIssueIngestor(doc_cfg)
            doc_ingestor.ingest()
            doc_ingestor.close()
            self._record_result(
                CheckResult(
                    name="Ingestion",
                    passed=True,
                    detail=f"Synthetic ingest complete (slack={slack_result.get('ingested')})",
                )
            )
        finally:
            slack_ingestor.close()

    def _group_commits_by_repo(
        self,
        commits: List[GitCommitSpec],
    ) -> Dict[str, Tuple[RepoTarget, List[Dict[str, Any]]]]:
        grouped: Dict[str, Tuple[RepoTarget, List[Dict[str, Any]]]] = {}
        for commit in commits:
            entry = {
                "sha": commit.sha,
                "message": commit.message,
                "author": commit.author,
                "date": commit.timestamp.isoformat(),
                "files": [{"filename": filename, "status": "modified"} for filename in commit.files],
            }
            repo_id = commit.repo.repo_id
            if repo_id not in grouped:
                grouped[repo_id] = (commit.repo, [])
            grouped[repo_id][1].append(entry)
        return grouped

    def _with_single_repo(self, config: Dict[str, Any], repo_id: str) -> Dict[str, Any]:
        cloned = json.loads(json.dumps(config))
        git_cfg = (cloned.get("activity_ingest") or {}).get("git") or {}
        repos = git_cfg.get("repos") or []
        filtered = [repo for repo in repos if repo.get("name") == repo_id or repo.get("repo_id") == repo_id]
        if not filtered and repos:
            filtered = [repos[0]]
        git_cfg["repos"] = filtered
        cloned.setdefault("activity_ingest", {})["git"] = git_cfg
        return cloned

    def _with_doc_issue_override(self, config: Dict[str, Any]) -> Dict[str, Any]:
        cloned = json.loads(json.dumps(config))
        doc_cfg = (cloned.setdefault("activity_ingest", {}).setdefault("doc_issues", {}))
        doc_cfg["enabled"] = True
        doc_cfg["path"] = str(self.synthetic_paths["doc_issues"])
        return cloned

    # ------------------------------------------------------------------
    # Live mode
    # ------------------------------------------------------------------
    def _run_live(self) -> None:
        logger.info("Seeding live quota scenario")
        if self.dry_run:
            logger.info("[dry-run] would push live commits/slack/doc issues")
            return

        self._seed_live_git()
        self._seed_live_slack()
        self.doc_issue_store.sync(self._build_doc_issues(self._build_synthetic_commits()))
        self._record_result(CheckResult("Fixtures", True, "Live repos/slack seeded", critical=False))
        self._ingest_live()

    def _seed_live_git(self) -> None:
        github_token = os.getenv("GITHUB_TOKEN")
        manager = GitHubRepoManager(github_token)
        changed = False
        for repo in self.repo_targets:
            if not repo.live_mutation:
                continue
            if not github_token:
                raise GitHubAPIError("GITHUB_TOKEN not set; cannot run live mode.")
            manager.ensure_branch(repo)
            for path in repo.files:
                changed = manager.update_file(
                    repo,
                    path,
                    mutate_fn=lambda text, r=repo: self._mutate_quota_file(r, text),
                    message=repo.commit_message.format(legacy=self.quota.legacy, updated=self.quota.updated),
                ) or changed
        logger.info("Live git seeding complete (changed=%s)", changed)

    def _mutate_quota_file(self, repo: RepoTarget, text: str) -> str:
        legacy = str(self.quota.legacy)
        updated = str(self.quota.updated)
        replacements = (
            (r"(free_tier_quota\s*:\s*)([0-9_,]+)", r"\g<1>" + updated),
            (r"(FREE_TIER_QUOTA\s*=\s*)([0-9_,]+)", r"\g<1>" + updated),
        )
        new_text = text
        for pattern, repl in replacements:
            new_text, count = re.subn(pattern, repl, new_text, flags=re.IGNORECASE)
            if count:
                return new_text
        # Fallback: replace legacy literal if present
        if legacy in text and updated not in text:
            return text.replace(legacy, updated)
        return text

    def _seed_live_slack(self) -> None:
        if not WebClient:
            logger.warning("slack_sdk unavailable; skipping live Slack seeding.")
            return
        token = os.getenv("SLACK_TOKEN") or os.getenv("SLACK_BOT_TOKEN")
        if not token:
            raise RuntimeError("SLACK_TOKEN (or legacy SLACK_BOT_TOKEN) missing; cannot seed live Slack.")
        client = WebClient(token=token)
        channel_id = self.slack_cfg.get("channel_id")
        if not channel_id:
            raise ConfigError("quota_demo.slack.channel_id required for live mode.")

        thread_entries = self._slack_story_templates()
        thread_ts: Optional[str] = None
        for entry in thread_entries:
            text = entry["text"].format(
                legacy=f"{self.quota.legacy:,}",
                updated=f"{self.quota.updated:,}",
            )
            prefix = self.slack_participants.get(entry["handle"], SlackParticipant(entry["handle"], "", entry["handle"])).display_name
            payload = {
                "channel": channel_id,
                "text": f"*{prefix}*: {text}",
            }
            if thread_ts:
                payload["thread_ts"] = thread_ts
            try:
                response = client.chat_postMessage(**payload)
                if not thread_ts:
                    thread_ts = response.get("ts")
            except SlackApiError as exc:  # pragma: no cover - requires live Slack
                raise RuntimeError(f"Failed to post Slack message: {exc.response['error']}") from exc
        logger.info("Seeded live Slack thread at channel %s thread_ts=%s", channel_id, thread_ts)

    def _ingest_live(self) -> None:
        config = get_config()
        slack_ingestor = SlackActivityIngestor(config)
        git_ingestor = GitActivityIngestor(config)
        doc_cfg = self._with_doc_issue_override(config)
        doc_ingestor = DocIssueIngestor(doc_cfg)
        try:
            slack_ingestor.ingest()
            git_ingestor.ingest()
            doc_ingestor.ingest()
            self._record_result(CheckResult("Ingestion", True, "Live ingest completed"))
        finally:
            slack_ingestor.close()
            git_ingestor.close()
            doc_ingestor.close()

    # ------------------------------------------------------------------
    # Verification
    # ------------------------------------------------------------------
    def _run_verification_checks(self) -> None:
        self._record_result(self._check_activity_graph())
        self._record_result(self._check_doc_issues())
        self._record_result(self._check_context_resolution())

    def _check_activity_graph(self) -> CheckResult:
        component_id = self.verification_targets["activity"]
        result = invoke_tool(get_component_activity, component_id=component_id, window="7d")
        if result.get("error"):
            return CheckResult("Activity Graph", False, result["error"])
        if result.get("open_doc_issues", 0) < 1:
            return CheckResult(
                "Activity Graph",
                False,
                f"{component_id} has zero doc issues; ingestion missing?",
            )
        if result.get("dissatisfaction_score", 0.0) <= 0:
            return CheckResult(
                "Activity Graph",
                False,
                f"{component_id} dissatisfaction score is zero.",
            )
        return CheckResult(
            "Activity Graph",
            True,
            f"{component_id} activity={result.get('activity_score')} doc_issues={result.get('open_doc_issues')}",
        )

    def _check_doc_issues(self) -> CheckResult:
        component_id = self.verification_targets["doc"]
        response = invoke_tool(list_doc_issues, component_id=component_id)
        if response.get("error"):
            return CheckResult("Doc Issues", False, response["error"])
        issues = response.get("doc_issues") or []
        if not issues:
            return CheckResult("Doc Issues", False, f"No doc issues found for {component_id}")
        legacy = f"{self.quota.legacy:,}"
        updated = f"{self.quota.updated:,}"
        summaries = [issue.get("summary", "") for issue in issues]
        if not any(legacy in summary and updated in summary for summary in summaries):
            return CheckResult(
                "Doc Issues",
                False,
                f"Doc issues exist but none mention both {legacy} and {updated}",
            )
        return CheckResult(
            "Doc Issues",
            True,
            f"{component_id} doc issues: {len(issues)}",
        )

    def _check_context_resolution(self) -> CheckResult:
        component_id = self.verification_targets["context"]
        response = invoke_tool(get_context_impacts, component_id=component_id, include_docs=True)
        if response.get("error"):
            return CheckResult("Context Resolution", False, response["error"])
        impacted = response.get("impacts") or []
        if not impacted:
            return CheckResult("Context Resolution", False, "Context graph returned zero impacts.")
        dependents = set()
        docs = set()
        for entry in impacted:
            dependents.update(entry.get("dependent_components") or [])
            docs.update(entry.get("docs") or [])
        missing_components = {"comp:web-dashboard", "comp:docs-portal"} - dependents
        if missing_components:
            return CheckResult(
                "Context Resolution",
                False,
                f"Missing dependents in context graph: {sorted(missing_components)}",
            )
        expected_docs = {"doc:web-dashboard-pricing", "doc:docs-portal-free-tier"}
        missing_docs = expected_docs - docs
        if missing_docs:
            return CheckResult(
                "Context Resolution",
                False,
                f"Docs/pricing artifacts not surfaced: {sorted(missing_docs)}",
            )
        return CheckResult("Context Resolution", True, f"Dependents={sorted(dependents)}")

    # ------------------------------------------------------------------
    # Results & summary
    # ------------------------------------------------------------------
    def _record_result(self, result: CheckResult) -> None:
        self.step_results.append(result)

    def _print_summary(self) -> None:
        print("\n=== Quota Demo Report ===")
        for result in self.step_results:
            status = "PASS" if result.passed else "FAIL"
            print(f"{status:4} – {result.name}: {result.detail}")
        critical_fail = any((not r.passed and r.critical) for r in self.step_results)
        if critical_fail:
            print("One or more critical checks failed.")
        else:
            print("Quota demo seeding complete.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed + verify the free-tier quota demo.")
    parser.add_argument(
        "--mode",
        choices=["synthetic", "live"],
        required=True,
        help="Synthetic fixtures vs live Git/Slack mutations.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print planned actions without mutating files, repos, or Slack.",
    )
    return parser.parse_args()


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )
    args = parse_args()
    config = get_config()
    try:
        seeder = QuotaDemoSeeder(config, mode=args.mode, dry_run=args.dry_run)
        success = seeder.run()
        return 0 if success else 1
    except (ConfigError, GitHubAPIError, RuntimeError) as exc:
        logger.error("Quota demo seeding failed: %s", exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())


