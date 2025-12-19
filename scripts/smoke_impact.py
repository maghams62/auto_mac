#!/usr/bin/env python3
"""
One-stop helper to exercise Cerebros ImpactService endpoints.

Example usage:
  python scripts/smoke_impact.py git-change --repo acme/service-auth --commits 123abc 456def
  python scripts/smoke_impact.py git-pr --repo acme/service-auth --pr 512
  python scripts/smoke_impact.py slack-complaint --channel "#docs-bugs" --message "Docs broken" --timestamp 1700000000.55
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

DEFAULT_BASE_URL = "http://127.0.0.1:8000"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Smoke-test Cerebros ImpactService endpoints.")
    parser.add_argument("mode", choices=["git-change", "git-pr", "slack-complaint"], help="Endpoint to invoke.")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="Cerebros API base (default: %(default)s)")
    parser.add_argument("--repo", help="GitHub repo in owner/name form.")
    parser.add_argument("--commits", nargs="*", help="Commit SHAs for git-change.")
    parser.add_argument("--files", nargs="*", help="File paths to include in git-change payload.")
    parser.add_argument("--title", help="Optional title/summary for git-change.")
    parser.add_argument("--description", help="Optional description for git-change.")
    parser.add_argument("--pr", type=int, help="PR number for git-pr mode.")
    parser.add_argument("--channel", help="Slack channel (e.g., #docs-bugs) for slack-complaint mode.")
    parser.add_argument("--message", help="Slack message/complaint body.")
    parser.add_argument("--timestamp", help="Slack thread timestamp (e.g., 1700000000.55).")
    parser.add_argument("--component", action="append", dest="component_ids", help="Component hint for slack complaints.")
    parser.add_argument("--api", action="append", dest="api_ids", help="API hint for slack complaints.")
    parser.add_argument(
        "--verify-doc-issues",
        action="store_true",
        help="Fetch /impact/doc-issues after the call to confirm persistence.",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Optional path to write the JSON response (default: print to stdout only).",
    )
    return parser


def write_output(payload: Dict[str, Any], destination: Optional[str]) -> None:
    if destination is None:
        return
    path = Path(destination)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True))
    print(f"Saved response to {path.resolve()}")


def run_git_change(args: argparse.Namespace, client: httpx.Client) -> Dict[str, Any]:
    if not args.repo:
        raise SystemExit("--repo is required for git-change")
    if not args.commits and not args.files:
        raise SystemExit("Provide at least one commit SHA or file path for git-change mode.")

    payload: Dict[str, Any] = {
        "repo": args.repo,
        "title": args.title,
        "description": args.description,
    }
    if args.commits:
        payload["commits"] = args.commits
    if args.files:
        payload["files"] = [{"path": file_path, "change_type": "modified"} for file_path in args.files]

    response = client.post("/impact/git-change", json=payload)
    response.raise_for_status()
    return response.json()


def run_git_pr(args: argparse.Namespace, client: httpx.Client) -> Dict[str, Any]:
    if not args.repo or args.pr is None:
        raise SystemExit("--repo and --pr are required for git-pr mode.")
    payload = {"repo": args.repo, "pr_number": int(args.pr)}
    response = client.post("/impact/git-pr", json=payload)
    response.raise_for_status()
    return response.json()


def run_slack_complaint(args: argparse.Namespace, client: httpx.Client) -> Dict[str, Any]:
    if not args.channel or not args.message:
        raise SystemExit("--channel and --message are required for slack-complaint mode.")
    payload = {
        "channel": args.channel,
        "message": args.message,
        "timestamp": args.timestamp or "",
        "context": {
            "component_ids": args.component_ids,
            "api_ids": args.api_ids,
        },
    }
    response = client.post("/impact/slack-complaint", json=payload)
    response.raise_for_status()
    return response.json()


def fetch_doc_issues(client: httpx.Client) -> List[Dict[str, Any]]:
    response = client.get("/impact/doc-issues", params={"source": "impact-report"})
    response.raise_for_status()
    payload = response.json()
    return payload.get("doc_issues", [])


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    base_url = args.base_url.rstrip("/")
    print(f"Targeting Cerebros API at {base_url}")

    with httpx.Client(base_url=base_url, timeout=20.0) as client:
        if args.mode == "git-change":
            result = run_git_change(args, client)
        elif args.mode == "git-pr":
            result = run_git_pr(args, client)
        else:
            result = run_slack_complaint(args, client)

        print("\n✅ ImpactService call succeeded. Summary:")
        print(json.dumps(result, indent=2, sort_keys=True))
        write_output(result, args.output)

        if args.verify_doc_issues:
            doc_issues = fetch_doc_issues(client)
            print(f"\n📄 DocIssues count: {len(doc_issues)}")
            if doc_issues:
                latest = doc_issues[-1]
                print("Most recent DocIssue:")
                print(json.dumps(latest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

