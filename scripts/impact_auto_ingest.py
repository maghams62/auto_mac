#!/usr/bin/env python3
"""
Kick off impact analysis runs for recent commits across configured repos.

Safe for cron/launchd usage:
- Respects per-repo limits and since-cursors so it never reprocesses the entire history.
- Dedupes by commit/PR identifier so reruns after crashes do not double-create DocIssues.
- Honors ``impact.data_mode`` (will not write to synthetic stores unless explicitly allowed).
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, MutableMapping, Optional, Sequence

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config.context import get_config_context
from src.graph.dependency_graph import DependencyGraphBuilder
from src.impact.models import ImpactReport
from src.impact.service import ImpactService

logger = logging.getLogger("impact_auto_ingest")
STATE_PATH = ROOT / "data/state/impact_auto_ingest.json"
DEFAULT_CURSOR_KEEP = 256


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _iso_hours_ago(hours: float) -> str:
    delta = timedelta(hours=float(hours))
    return _iso(_utc_now() - delta)


def _load_state(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {"repos": {}}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning("Failed to load state from %s: %s", path, exc)
        return {"repos": {}}


def _save_state(path: Path, state: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")


def _repo_state(state: Dict[str, Any], repo_full: str) -> MutableMapping[str, Any]:
    repos = state.setdefault("repos", {})
    return repos.setdefault(repo_full, {"processed_ids": []})


def _maybe_backoff_cursor(cursor: Optional[str]) -> Optional[str]:
    if not cursor:
        return None
    try:
        dt = datetime.fromisoformat(cursor.replace("Z", "+00:00"))
    except ValueError:
        return cursor
    return _iso(dt - timedelta(minutes=1))


def _component_ids_for_repo(graph, repo_name: str) -> List[str]:
    return sorted(
        {
            component_id
            for component_id, repo in graph.component_to_repo.items()
            if repo == repo_name
        }
    )


def _discover_repos(config: Dict[str, object]) -> List[Dict[str, object]]:
    return list((config.get("activity_ingest") or {}).get("git", {}).get("repos", []) or [])


def _run_for_repo(
    service: ImpactService,
    graph,
    repo_cfg: Dict[str, object],
    *,
    limit: int,
    dry_run: bool,
    since: Optional[str],
    state_bucket: MutableMapping[str, Any],
    cursor_keep: int,
) -> Sequence[ImpactReport]:
    owner = repo_cfg.get("owner")
    name = repo_cfg.get("name")
    if not owner or not name:
        logger.warning("Skipping repo with missing owner/name: %s", repo_cfg)
        return []
    repo_full = f"{owner}/{name}"
    components = _component_ids_for_repo(graph, name)
    if not components:
        logger.debug("No dependency-map coverage for %s; skipping.", repo_full)
        return []
    logger.info(
        "Fetching recent commits for %s (components=%s, limit=%s, since=%s)",
        repo_full,
        components,
        limit,
        since,
    )
    changes = service.git_integration.recent_component_changes(
        repo_full,
        components,
        graph,
        limit=limit,
        branch=repo_cfg.get("branch"),
        since=since,
    )
    reports: List[ImpactReport] = []
    processed_ids: List[str] = list(state_bucket.get("processed_ids") or [])
    seen = set(processed_ids)
    for change in changes:
        if change.identifier in seen:
            logger.debug("Skipping already-processed change %s", change.identifier)
            continue
        if dry_run:
            logger.info("[DRY-RUN] Would analyze %s (%s files)", change.identifier, len(change.files))
            continue
        report = service.pipeline.process_git_event(change)
        reports.append(report)
        logger.info(
            "[IMPACT][AUTO] %s -> components=%s docs=%s level=%s",
            change.identifier,
            len(report.changed_components),
            len(report.impacted_docs),
            report.impact_level.value,
        )
        processed_ids.append(change.identifier)
        if len(processed_ids) > cursor_keep:
            processed_ids = processed_ids[-cursor_keep:]
        seen.add(change.identifier)
        state_bucket["processed_ids"] = processed_ids
        committed_at = ((change.metadata or {}).get("committed_at")) if hasattr(change, "metadata") else None
        if committed_at:
            state_bucket["last_cursor"] = committed_at
        state_bucket["last_success_at"] = _iso(_utc_now())
    return reports


def main() -> None:
    parser = argparse.ArgumentParser(description="Auto-ingest recent commits for impact analysis.")
    parser.add_argument(
        "--limit",
        type=int,
        default=5,
        help="Max commits per repo (default: %(default)s)",
    )
    parser.add_argument(
        "--since",
        help="ISO timestamp to bound commit search (overrides repo/state cursors).",
    )
    parser.add_argument(
        "--since-hours",
        type=float,
        help="Look back this many hours from now (alternative to --since).",
    )
    parser.add_argument(
        "--repo",
        action="append",
        dest="repos",
        help="Specific owner/name repo to target (can be repeated). Defaults to all configured repos.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Log intended analyses without calling the pipeline.",
    )
    parser.add_argument(
        "--state-path",
        default=str(STATE_PATH),
        help="Path to ingest cursor state file (default: %(default)s).",
    )
    parser.add_argument(
        "--cursor-keep",
        type=int,
        default=DEFAULT_CURSOR_KEEP,
        help="How many processed IDs to keep per repo for dedupe (default: %(default)s).",
    )
    parser.add_argument(
        "--allow-synthetic",
        action="store_true",
        help="Override safety check and allow runs when impact.data_mode=synthetic.",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    ctx = get_config_context()
    impact_mode = (ctx.data.get("impact") or {}).get("data_mode", "live").lower()
    if impact_mode == "synthetic" and not args.allow_synthetic:
        logger.warning(
            "impact_auto_ingest aborted: impact.data_mode=%s. Set --allow-synthetic to override for test fixtures.",
            impact_mode,
        )
        return

    service = ImpactService(ctx)
    builder = DependencyGraphBuilder(ctx.data, graph_service=service.graph_service)
    graph = builder.build(write_to_graph=False)
    target_repos = _discover_repos(ctx.data)
    if args.repos:
        filters = set(args.repos)
        target_repos = [cfg for cfg in target_repos if f"{cfg.get('owner')}/{cfg.get('name')}" in filters]
    if not target_repos:
        logger.warning("No repos configured for auto-ingest. Nothing to do.")
        return

    state_path = Path(args.state_path)
    state = _load_state(state_path)
    cursor_keep = max(50, args.cursor_keep or DEFAULT_CURSOR_KEEP)

    for repo_cfg in target_repos:
        owner = repo_cfg.get("owner")
        name = repo_cfg.get("name")
        if not owner or not name:
            continue
        repo_full = f"{owner}/{name}"
        repo_state = _repo_state(state, repo_full)
        repo_state["last_run_started_at"] = _iso(_utc_now())
        repo_since = _resolve_since(args, repo_cfg, repo_state)
        max_commits = int(repo_cfg.get("max_commits") or args.limit or 5)
        try:
            _run_for_repo(
                service,
                graph,
                repo_cfg,
                limit=max_commits,
                dry_run=args.dry_run,
                since=repo_since,
                state_bucket=repo_state,
                cursor_keep=cursor_keep,
            )
            repo_state["last_run_completed_at"] = _iso(_utc_now())
            repo_state["last_error"] = None
            repo_state.pop("last_error_at", None)
        except Exception as exc:  # noqa: BLE001
            repo_state["last_error"] = str(exc)
            repo_state["last_error_at"] = _iso(_utc_now())
            logger.exception("Auto-ingest failed for %s", repo_full)
        finally:
            _save_state(state_path, state)


def _resolve_since(args, repo_cfg: Dict[str, object], repo_state: MutableMapping[str, Any]) -> Optional[str]:
    if args.since:
        return args.since
    if args.since_hours:
        return _iso_hours_ago(args.since_hours)
    cfg_since = repo_cfg.get("since")
    if isinstance(cfg_since, str) and cfg_since.strip():
        return cfg_since
    cfg_hours = repo_cfg.get("since_hours")
    if cfg_hours is not None:
        try:
            return _iso_hours_ago(float(cfg_hours))
        except (TypeError, ValueError):
            logger.warning("Invalid since_hours=%s for repo %s/%s", cfg_hours, repo_cfg.get("owner"), repo_cfg.get("name"))
    cursor = repo_state.get("last_cursor")
    return _maybe_backoff_cursor(cursor)


if __name__ == "__main__":
    main()

