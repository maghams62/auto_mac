#!/usr/bin/env python3
"""
Verify that the GitHub org/repos referenced by live ingest actually exist.

Usage:
    python scripts/diagnose_git_ingest.py
    python scripts/diagnose_git_ingest.py --org myorg --repos core-api docs-portal
"""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from typing import Iterable, List, Optional, Tuple

import requests


API_BASE = "https://api.github.com"


@dataclass
class RepoSpec:
    owner: str
    name: str
    branch: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Diagnose Git ingest configuration.")
    parser.add_argument(
        "--org",
        default=os.getenv("LIVE_GIT_ORG"),
        help="GitHub org/owner to probe (defaults to LIVE_GIT_ORG or repo-specific overrides).",
    )
    parser.add_argument(
        "--repos",
        nargs="*",
        default=[],
        help="Explicit repo slugs (owner/name) to test. Overrides env detection.",
    )
    parser.add_argument(
        "--branch",
        default=None,
        help="Override branch to probe (default: repo-specific env var or main).",
    )
    return parser.parse_args()


def _env_repo_specs(org: Optional[str]) -> List[RepoSpec]:
    default_owner = org or os.getenv("LIVE_GIT_ORG") or ""

    def spec(repo_env: str, branch_env: str, fallback_name: str) -> Optional[RepoSpec]:
        raw = os.getenv(repo_env, fallback_name)
        if not raw:
            return None
        if "/" in raw:
            owner, name = raw.split("/", 1)
        else:
            owner, name = default_owner, raw
        branch = os.getenv(branch_env, "main")
        return RepoSpec(owner=owner or default_owner, name=name, branch=branch)

    specs = [
        spec("CORE_API_REPO", "CORE_API_BRANCH", "core-api"),
        spec("BILLING_SERVICE_REPO", "BILLING_SERVICE_BRANCH", "billing-service"),
        spec("DOCS_PORTAL_REPO", "DOCS_PORTAL_BRANCH", "docs-portal"),
    ]
    return [repo for repo in specs if repo and repo.owner]


def _explicit_specs(slugs: Iterable[str], branch_override: Optional[str]) -> List[RepoSpec]:
    specs: List[RepoSpec] = []
    for slug in slugs:
        owner, name = slug.split("/", 1) if "/" in slug else ("", slug)
        specs.append(RepoSpec(owner=owner, name=name, branch=branch_override or "main"))
    return specs


def _headers() -> dict:
    token = os.getenv("GIT_TOKEN") or os.getenv("GITHUB_TOKEN")
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "CerebrosLiveDiag/1.0",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _get(path: str, params: Optional[dict] = None) -> requests.Response:
    response = requests.get(f"{API_BASE}/{path}", headers=_headers(), params=params, timeout=30)
    response.raise_for_status()
    return response


def _check_repo(spec: RepoSpec) -> Tuple[bool, str]:
    try:
        _get(f"repos/{spec.owner}/{spec.name}")
    except requests.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else "unknown"
        return False, f"{spec.owner}/{spec.name} missing or inaccessible (status {status})."
    except requests.RequestException as exc:
        return False, f"{spec.owner}/{spec.name} request failed: {exc}"

    try:
        _get(f"repos/{spec.owner}/{spec.name}/branches/{spec.branch}")
    except requests.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else "unknown"
        return False, f"Branch {spec.branch} not found in {spec.owner}/{spec.name} (status {status})."
    except requests.RequestException as exc:
        return False, f"Branch lookup failed for {spec.owner}/{spec.name}: {exc}"

    try:
        commits = _get(
            f"repos/{spec.owner}/{spec.name}/commits",
            params={"sha": spec.branch, "per_page": 1},
        ).json()
        sha = commits[0]["sha"] if commits else "unknown"
    except Exception:
        sha = "unknown"
    return True, f"{spec.owner}/{spec.name}@{spec.branch} reachable (head {sha[:7]})."


def main() -> None:
    args = parse_args()
    specs = (
        _explicit_specs(args.repos, args.branch)
        if args.repos
        else _env_repo_specs(args.org)
    )

    if not specs:
        print("❌ No repositories configured. Set LIVE_GIT_ORG/CORE_API_REPO/etc or pass --repos owner/name.")
        sys.exit(1)

    print("🔍 Git ingest diagnostics\n")
    failures = 0
    for spec in specs:
        ok, message = _check_repo(spec)
        indicator = "✅" if ok else "❌"
        print(f"{indicator} {message}")
        if not ok:
            failures += 1

    if failures:
        print(
            "\nFix the missing repos/branches above. "
            "Update LIVE_GIT_ORG and *_REPO env vars, then rerun this script."
        )
        sys.exit(1)

    print("\nAll repositories reachable — ready for `run_activity_ingestion.py --sources git`.")


if __name__ == "__main__":
    main()


