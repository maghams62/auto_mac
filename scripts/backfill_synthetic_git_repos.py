#!/usr/bin/env python3
"""Push the synthetic git fixtures to live GitHub repositories.

This script loads the repo directories under ``data/synthetic_git`` and, for each
one that has a configured remote, performs the following steps:

1. Clones the remote repository into a temporary directory (respecting any PAT
   embedded in the remote URL or provided via ``GITHUB_TOKEN``).
2. Checks out the configured base branch and creates/updates the synthetic
   branch (default: ``synthetic/<pr-number>``).
3. Replaces the working tree with the local synthetic fixtures, stages the
   result, and commits with either the PR title or a generic backfill message.
4. Pushes the branch to the remote (force-with-lease) and, optionally, opens a
   GitHub pull request using the repo metadata from ``git_prs.json``.
5. Verifies that any required GitHub issues referenced in the synthetic data are
   reachable. The core-api data defaults to requiring issue ``#2041``.

Environment variables
---------------------
The script reads the standard ``.env`` in the repo (if present) and then expects
per-repo overrides for remotes/branches. Variables are discovered dynamically
using the repo name (hyphens converted to underscores). For example, for
``core-api`` the following variables are read:

- ``BACKFILL_CORE_API_REMOTE`` – HTTPS remote, e.g.
  ``https://github.com/maghams62/core-api.git``. If the value does not already
  embed credentials and ``GITHUB_TOKEN`` is set, the token is injected
  automatically.
- ``BACKFILL_CORE_API_BASE`` – Base branch to branch from (default: ``main``).
- ``BACKFILL_CORE_API_BRANCH`` – Branch to push (default: ``synthetic/<pr>`` or
  ``synthetic/core-api`` when no PR metadata exists).
- ``BACKFILL_CORE_API_COMMIT_MESSAGE`` – Optional commit message override.
- ``BACKFILL_CORE_API_REQUIRED_ISSUES`` – Comma separated list of issue numbers
  that must exist (defaults to ``2041`` for ``core-api`` only).

Global fallbacks:

- ``BACKFILL_DEFAULT_REMOTE`` – Used when a repo-specific remote is not set.
- ``BACKFILL_DEFAULT_BASE`` – Default base branch (``main``).
- ``BACKFILL_DEFAULT_BRANCH_PREFIX`` – Prefix used when deriving branch names
  (default ``synthetic``).
- ``BACKFILL_CREATE_PRS`` – ``1`` to always open pull requests (requires
  ``GITHUB_TOKEN``).
- ``BACKFILL_DRY_RUN`` – ``1`` to print the plan without cloning/pushing.

Git identity / credentials:

- ``GITHUB_TOKEN`` – Personal access token with repo scope. Used for API calls
  and injected into remotes when possible.
- ``GIT_AUTHOR_NAME`` / ``GIT_AUTHOR_EMAIL`` – Applied to each temporary clone
  before committing.

Usage
-----
```
python scripts/backfill_synthetic_git_repos.py            # process all repos
python scripts/backfill_synthetic_git_repos.py --repo core-api --repo billing-service
python scripts/backfill_synthetic_git_repos.py --dry-run
```
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple
from urllib.parse import urlencode, urlparse, urlunparse
import urllib.request

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data" / "synthetic_git"
PR_DATA_PATH = DATA_DIR / "git_prs.json"
DEFAULT_BRANCH_PREFIX = os.getenv("BACKFILL_DEFAULT_BRANCH_PREFIX", "synthetic")
DEFAULT_REQUIRED_ISSUES = {"core-api": [2041]}


def load_env_file() -> None:
    """Best effort loader for the project .env file."""

    env_path = PROJECT_ROOT / ".env"
    if not env_path.exists():
        return
    for raw_line in env_path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export "):]
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key in os.environ:
            continue
        cleaned = value.strip().strip('"').strip("'")
        os.environ[key] = cleaned


def run_git(args: Sequence[str], *, cwd: Path, check: bool = True) -> subprocess.CompletedProcess[str]:
    """Run a git command and return the completed process."""

    proc = subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        text=True,
        capture_output=True,
        check=False,
    )
    if check and proc.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {proc.stderr.strip() or proc.stdout.strip()}")
    return proc


def mask_remote(remote: str) -> str:
    """Remove embedded credentials when printing remotes."""

    if "@" not in remote:
        return remote
    parsed = urlparse(remote)
    if parsed.username:
        netloc = parsed.hostname or parsed.netloc
        return urlunparse((parsed.scheme, netloc, parsed.path, parsed.params, parsed.query, parsed.fragment))
    if remote.startswith("git@"):
        return remote.split("@", 1)[-1]
    return remote


def remote_with_token(remote: str, token: str) -> str:
    """Inject the PAT into HTTPS remotes when credentials are missing."""

    if not token:
        return remote
    parsed = urlparse(remote)
    if parsed.scheme not in {"http", "https"}:
        return remote
    if parsed.username:
        return remote
    netloc = parsed.netloc
    return urlunparse((parsed.scheme, f"{token}@{netloc}", parsed.path, parsed.params, parsed.query, parsed.fragment))


def git_identity(cwd: Path) -> None:
    name = os.getenv("GIT_AUTHOR_NAME") or os.getenv("GIT_COMMITTER_NAME") or "Synthetic Backfill"
    email = os.getenv("GIT_AUTHOR_EMAIL") or os.getenv("GIT_COMMITTER_EMAIL") or "synthetic@example.com"
    run_git(["config", "user.name", name], cwd=cwd)
    run_git(["config", "user.email", email], cwd=cwd)


def working_tree_has_changes(cwd: Path) -> bool:
    proc = run_git(["status", "--porcelain"], cwd=cwd)
    return bool(proc.stdout.strip())


def clear_working_tree(cwd: Path) -> None:
    for entry in cwd.iterdir():
        if entry.name == ".git":
            continue
        if entry.is_dir():
            shutil.rmtree(entry)
        else:
            entry.unlink()


def copy_tree(src: Path, dst: Path) -> None:
    for entry in src.iterdir():
        target = dst / entry.name
        if entry.is_dir():
            shutil.copytree(entry, target, dirs_exist_ok=True)
        else:
            shutil.copy2(entry, target)


def parse_owner_repo(remote: str) -> Optional[Tuple[str, str]]:
    if remote.startswith("git@"):
        slug = remote.split(":", 1)[-1]
    else:
        parsed = urlparse(remote)
        slug = parsed.path
    slug = (slug or "").strip("/")
    if slug.endswith(".git"):
        slug = slug[:-4]
    if "/" not in slug:
        return None
    owner, repo = slug.split("/", 1)
    return owner, repo


def api_request(method: str, url: str, token: str, *, data: Optional[Dict[str, object]] = None, params: Optional[Dict[str, object]] = None) -> Dict[str, object]:
    if not token:
        raise RuntimeError("GITHUB_TOKEN is required for GitHub API calls")
    final_url = url
    if params:
        final_url += f"?{urlencode(params)}"
    payload = None
    if data is not None:
        payload = json.dumps(data).encode("utf-8")
    request = urllib.request.Request(
        final_url,
        data=payload,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "synthetic-backfill",
        },
    )
    try:
        with urllib.request.urlopen(request) as response:
            if response.status == 204:
                return {}
            body = response.read().decode("utf-8")
            return json.loads(body)
    except urllib.error.HTTPError as exc:  # type: ignore[attr-defined]
        detail = exc.read().decode("utf-8") if exc.fp else exc.reason
        raise RuntimeError(f"GitHub API {method} {url} failed: {exc.code} {detail}") from exc


def ensure_issue_exists(owner: str, repo: str, issue: int, token: str) -> None:
    url = f"https://api.github.com/repos/{owner}/{repo}/issues/{issue}"
    try:
        api_request("GET", url, token)
        print(f"  ✓ Verified issue #{issue} exists on {owner}/{repo}")
    except RuntimeError as exc:
        raise RuntimeError(
            f"Required issue #{issue} not found on {owner}/{repo}. "
            "Create it or update BACKFILL_*_REQUIRED_ISSUES."
        ) from exc


def ensure_pull_request(owner: str, repo: str, token: str, *, head: str, base: str, title: str, body: str) -> None:
    if not token:
        print("  ! Skipping PR creation (GITHUB_TOKEN not set)")
        return
    existing = api_request(
        "GET",
        f"https://api.github.com/repos/{owner}/{repo}/pulls",
        token,
        params={"head": f"{owner}:{head}", "state": "open"},
    )
    if isinstance(existing, list) and existing:
        print(f"  • PR already exists: {existing[0].get('html_url')}")
        return
    payload = {"title": title, "head": head, "base": base, "body": body or "Synthetic data backfill."}
    created = api_request("POST", f"https://api.github.com/repos/{owner}/{repo}/pulls", token, data=payload)
    print(f"  ✓ Opened PR: {created.get('html_url')}")


@dataclass
class RepoPlan:
    name: str
    local_path: Path
    remote: str
    base_branch: str
    branch: str
    commit_message: str
    pr_title: Optional[str]
    pr_body: Optional[str]
    required_issues: List[int]
    owner_repo: Optional[Tuple[str, str]]


def env_key(repo: str, suffix: str) -> str:
    safe = repo.upper().replace("-", "_")
    return f"BACKFILL_{safe}_{suffix}"


def derive_repo_plan(repo_dir: Path, pr_lookup: Dict[str, Dict[str, object]]) -> Optional[RepoPlan]:
    name = repo_dir.name
    remote = os.getenv(env_key(name, "REMOTE")) or os.getenv("BACKFILL_DEFAULT_REMOTE", "")
    if not remote:
        print(f"[skip] No remote configured for {name}; set {env_key(name, 'REMOTE')}.")
        return None
    base_branch = os.getenv(env_key(name, "BASE")) or os.getenv("BACKFILL_DEFAULT_BASE", "main")
    pr_info = pr_lookup.get(name)
    default_branch = f"{DEFAULT_BRANCH_PREFIX}/{pr_info.get('pr_number')}" if pr_info else f"{DEFAULT_BRANCH_PREFIX}/{name}"
    branch = os.getenv(env_key(name, "BRANCH")) or default_branch
    commit_message = (
        os.getenv(env_key(name, "COMMIT_MESSAGE"))
        or (pr_info.get("title") if pr_info else None)
        or f"chore(backfill): sync synthetic repo {name}"
    )
    pr_title = os.getenv(env_key(name, "PR_TITLE")) or (pr_info.get("title") if pr_info else None)
    pr_body = os.getenv(env_key(name, "PR_BODY")) or (pr_info.get("body") if pr_info else None)
    required_env = os.getenv(env_key(name, "REQUIRED_ISSUES"))
    if required_env:
        required = [int(part.strip()) for part in required_env.split(",") if part.strip().isdigit()]
    else:
        required = DEFAULT_REQUIRED_ISSUES.get(name, [])
    owner_repo = parse_owner_repo(remote)
    return RepoPlan(
        name=name,
        local_path=repo_dir,
        remote=remote,
        base_branch=base_branch,
        branch=branch,
        commit_message=commit_message,
        pr_title=pr_title,
        pr_body=pr_body,
        required_issues=required,
        owner_repo=owner_repo,
    )


def discover_repo_dirs(include: Optional[Iterable[str]]) -> List[Path]:
    include_set = {name for name in include} if include else None
    repo_dirs: List[Path] = []
    for entry in DATA_DIR.iterdir():
        if not entry.is_dir() or entry.name.startswith("."):
            continue
        if include_set and entry.name not in include_set:
            continue
        repo_dirs.append(entry)
    return sorted(repo_dirs)


def load_pr_lookup() -> Dict[str, Dict[str, object]]:
    if not PR_DATA_PATH.exists():
        return {}
    payload = json.loads(PR_DATA_PATH.read_text())
    return {entry["repo"]: entry for entry in payload}


def process_repo(plan: RepoPlan, *, token: str, create_prs: bool, dry_run: bool) -> None:
    auth_remote = remote_with_token(plan.remote, token)
    masked_remote = mask_remote(plan.remote)
    print(f"[repo] {plan.name}")
    print(f"  • remote: {masked_remote}")
    print(f"  • base  : {plan.base_branch}")
    print(f"  • branch: {plan.branch}")
    if dry_run:
        return
    with tempfile.TemporaryDirectory(prefix=f"synthetic-{plan.name}-") as tmp_root:
        tmp_root_path = Path(tmp_root)
        clone_target = tmp_root_path / plan.name
        run_git(["clone", auth_remote, str(clone_target)], cwd=tmp_root_path)
        run_git(["fetch", "origin", plan.base_branch], cwd=clone_target)
        run_git(["checkout", plan.base_branch], cwd=clone_target)
        run_git(["checkout", "-B", plan.branch], cwd=clone_target)
        clear_working_tree(clone_target)
        copy_tree(plan.local_path, clone_target)
        git_identity(clone_target)
        run_git(["add", "-A"], cwd=clone_target)
        if not working_tree_has_changes(clone_target):
            print("  • No changes to commit; skipping push.")
            return
        run_git(["commit", "-m", plan.commit_message], cwd=clone_target)
        # Push directly to the authenticated remote URL to avoid any local
        # remote misconfiguration (e.g., missing or incorrect 'origin').
        run_git(["push", "--force-with-lease", auth_remote, plan.branch], cwd=clone_target)
        print("  ✓ Pushed branch")
        if plan.required_issues and plan.owner_repo:
            owner, repo = plan.owner_repo
            for issue in plan.required_issues:
                ensure_issue_exists(owner, repo, issue, token)
        if create_prs and plan.pr_title and plan.owner_repo:
            owner, repo = plan.owner_repo
            ensure_pull_request(
                owner,
                repo,
                token,
                head=plan.branch,
                base=plan.base_branch,
                title=plan.pr_title,
                body=plan.pr_body or plan.commit_message,
            )
        elif create_prs and not plan.pr_title:
            print("  ! No PR metadata available; skipping PR creation.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backfill synthetic git repos to GitHub.")
    parser.add_argument("--repo", action="append", help="Limit processing to the given repo (repeatable).")
    parser.add_argument("--dry-run", action="store_true", help="Print the plan without cloning/pushing.")
    parser.add_argument(
        "--create-prs",
        action="store_true",
        help="Open GitHub pull requests after pushing (or set BACKFILL_CREATE_PRS=1).",
    )
    return parser.parse_args()


def main() -> None:
    load_env_file()
    args = parse_args()
    pr_lookup = load_pr_lookup()
    target_repos = discover_repo_dirs(args.repo)
    if not target_repos:
        print("No synthetic repos found; aborting.")
        return
    create_prs = args.create_prs or os.getenv("BACKFILL_CREATE_PRS") == "1"
    dry_run = args.dry_run or os.getenv("BACKFILL_DRY_RUN") == "1"
    token = os.getenv("GITHUB_TOKEN", "")
    plans: List[RepoPlan] = []
    for repo_dir in target_repos:
        plan = derive_repo_plan(repo_dir, pr_lookup)
        if plan:
            plans.append(plan)
    if not plans:
        print("No repos configured; nothing to do.")
        return
    for plan in plans:
        try:
            process_repo(plan, token=token, create_prs=create_prs, dry_run=dry_run)
        except Exception as exc:  # pragma: no cover - best effort logging
            print(f"[error] {plan.name}: {exc}", file=sys.stderr)
            raise


if __name__ == "__main__":
    main()
