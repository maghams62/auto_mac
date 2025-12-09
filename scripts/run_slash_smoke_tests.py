#!/usr/bin/env python3
"""
Quick smoke test runner for slash commands (Slack, GitHub, Cerebros).

Usage examples:
    python scripts/run_slash_smoke_tests.py \
        --base-url http://localhost:8000 \
        --slack-channel C0123456789 \
        --pr-number 128

Requires the API server to be running and real tokens configured
in your environment/config.yaml.
"""
from __future__ import annotations

import argparse
import sys
import textwrap
from typing import List

import requests


def run_command(base_url: str, session_id: str, command: str) -> None:
    """Send a slash command to /api/chat and print the response summary."""
    try:
        response = requests.post(
            f"{base_url.rstrip('/')}/api/chat",
            json={"message": command, "session_id": session_id},
            timeout=60,
        )
    except requests.RequestException as exc:
        print(f"⛔  Request error for '{command}': {exc}", file=sys.stderr)
        return

    if not response.ok:
        print(f"⛔  HTTP {response.status_code} for '{command}': {response.text}", file=sys.stderr)
        return

    payload = response.json()
    status = payload.get("status", "unknown")
    summary = payload.get("response") or payload.get("message") or ""

    if isinstance(summary, dict):
        # Some agents return structured payloads; collapse to a short message
        summary = summary.get("message") or summary.get("summary") or str(summary)[:400]

    summary = summary.strip().replace("\n", " ")
    if len(summary) > 200:
        summary = summary[:197] + "..."

    print(f"✅  {command} [{status}]")
    if summary:
        print(f"    {summary}")
    else:
        print("    (No textual response returned – check backend logs for details.)")


def build_command_list(args: argparse.Namespace) -> List[str]:
    """Assemble the slash commands to run based on CLI inputs."""
    commands: List[str] = []

    if not args.skip_setup:
        commands.append("/setup")

    if not args.skip_index:
        index_targets = (args.index_targets or "").strip()
        if index_targets and index_targets.lower() != "all":
            commands.append(f"/index {index_targets}")
        else:
            commands.append("/index")

    commands.extend(
        [
            "/slack list channels",
            "/git list open PRs on main",
            "/cerebros Summarize the latest Slack and GitHub activity",
        ]
    )

    if args.slack_channel:
        commands.append(f"/slack fetch {args.slack_channel} limit {args.slack_limit}")

    if args.pr_number:
        commands.append(f"/pr {args.pr_number}")

    if args.slack_query:
        commands.append(f"/slack search {args.slack_query}")

    if args.cerebros_question:
        commands.append(f"/cerebros {args.cerebros_question}")

    return commands


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run smoke tests for Slack/GitHub/Cerebros slash commands.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent(
            """
            Examples:
              python scripts/run_slash_smoke_tests.py --slack-channel C0123456789
              python scripts/run_slash_smoke_tests.py --pr-number 128 --cerebros-question "What's the status of onboarding?"
            """
        ),
    )
    parser.add_argument("--base-url", default="http://localhost:8000", help="API server base URL")
    parser.add_argument("--session-id", default="slash-smoke", help="Session ID to use for the requests")
    parser.add_argument(
        "--skip-setup",
        action="store_true",
        help="Skip running /setup as part of the smoke suite",
    )
    parser.add_argument(
        "--skip-index",
        action="store_true",
        help="Skip running /index as part of the smoke suite",
    )
    parser.add_argument(
        "--index-targets",
        default="slack",
        help="Space-separated modalities to pass to /index (use 'all' for every modality)",
    )
    parser.add_argument("--slack-channel", help="Slack channel ID (C123...) to fetch history for")
    parser.add_argument("--slack-limit", type=int, default=20, help="Number of Slack messages to fetch when using --slack-channel")
    parser.add_argument("--slack-query", help="Additional Slack search query to run")
    parser.add_argument("--pr-number", type=int, help="Specific PR number to summarize via /pr")
    parser.add_argument("--cerebros-question", help="Custom /cerebros question to ask")
    args = parser.parse_args()

    commands = build_command_list(args)
    print(f"Running {len(commands)} slash command smoke tests against {args.base_url}...\n")

    for command in commands:
        run_command(args.base_url, args.session_id, command)

    print("\nDone. Review responses above (and backend logs) for any errors.")


if __name__ == "__main__":
    main()

