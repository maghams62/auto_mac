#!/usr/bin/env python3
"""
Run canonical /slack and /git commands against a live Cerebros deployment.

Example:
    python scripts/check_slash_live.py --base-url http://localhost:8000
"""
from __future__ import annotations

import argparse
import sys
import uuid
from typing import Dict, List, Optional

import requests


CANONICAL_COMMANDS: List[Dict[str, Optional[List[str]]]] = [
    {"name": "slack_incidents", "command": "/slack what's the latest in #incidents?", "expect": ["incidents"]},
    {"name": "slack_support_billing", "command": "/slack summarize billing complaints in #support", "expect": ["billing"]},
    {"name": "slack_thread", "command": "/slack summarize the thread https://slack.com/archives/C123INCIDENTS/p1764147600000000", "expect": ["thread", "incidents"]},
    {"name": "slack_action_items", "command": "/slack list action items about atlas billing last 48h", "expect": ["follow", "task"]},
    {"name": "slack_cross_search", "command": "/slack search incidents mentioning \"vat_code\" across channels", "expect": ["vat"]},
    {"name": "git_billing_summary", "command": "/git what changed recently in the billing-service repo?", "expect": ["commit", "billing"]},
    {"name": "git_doc_drift", "command": "/git doc drift around Atlas billing docs?", "expect": ["doc", "drift"]},
    {"name": "git_core_api", "command": "/git what changed in core-api since release/2024.10", "expect": ["core", "api"]},
    {"name": "git_pr_compare", "command": "/git list closed PRs targeting main", "expect": ["pr", "branch"]},
    {"name": "git_commit_search", "command": "/git show commits mentioning vat_code last 2 days", "expect": ["commit"]},
]


def summarize_payload(payload: Dict[str, any]) -> str:
    """Flatten the API response into a short human-readable summary."""
    for key in ("message", "response", "result", "final_result"):
        value = payload.get(key)
        if not value:
            continue
        if isinstance(value, str):
            summary = value
            break
        if isinstance(value, dict):
            summary = (
                value.get("message")
                or value.get("summary")
                or value.get("content")
                or value.get("details")
            )
            if summary:
                break
    else:
        summary = ""

    if not summary:
        summary = payload.get("status") or ""

    summary = (summary or "").strip().replace("\n", " ")
    if len(summary) > 250:
        summary = summary[:247] + "..."
    return summary


def command_passed(summary: str, required: Optional[List[str]]) -> bool:
    if not required:
        return bool(summary)
    lowered = summary.lower()
    return all(token in lowered for token in required)


def run_command(base_url: str, session_id: str, entry: Dict[str, any], timeout: int) -> bool:
    command = entry["command"]
    try:
        response = requests.post(
            f"{base_url.rstrip('/')}/api/chat",
            json={"message": command, "session_id": session_id},
            timeout=timeout,
        )
    except requests.RequestException as exc:
        print(f"⛔  {entry['name']}: request error {exc}", file=sys.stderr)
        return False

    if not response.ok:
        print(f"⛔  {entry['name']}: HTTP {response.status_code} → {response.text}", file=sys.stderr)
        return False

    payload = response.json()
    summary = summarize_payload(payload)
    ok = command_passed(summary, entry.get("expect"))
    status = payload.get("status") or payload.get("result", {}).get("status") or "n/a"
    prefix = "✅" if ok else "⚠️"
    print(f"{prefix}  {entry['name']} [{status}]")
    if summary:
        print(f"    {summary}")
    else:
        print("    (No textual summary returned)")
    return ok


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate canonical /slack and /git flows against a live backend.")
    parser.add_argument("--base-url", default="http://localhost:8000", help="API server base URL")
    parser.add_argument("--timeout", type=int, default=60, help="HTTP timeout in seconds")
    parser.add_argument("--session-prefix", default="slash-health", help="Prefix for generated session IDs")
    parser.add_argument(
        "--only",
        help="Comma-separated list of scenario names to run (defaults to all).",
    )
    args = parser.parse_args()

    selected = {name.strip() for name in args.only.split(",")} if args.only else None
    entries = [entry for entry in CANONICAL_COMMANDS if not selected or entry["name"] in selected]
    if not entries:
        print("No slash scenarios selected; exiting.")
        return

    print(f"Running {len(entries)} slash scenarios against {args.base_url}...\n")
    aggregated_success = True
    for entry in entries:
        session_id = f"{args.session_prefix}-{entry['name']}-{uuid.uuid4().hex[:6]}"
        ok = run_command(args.base_url, session_id, entry, args.timeout)
        aggregated_success &= ok
        print()

    if aggregated_success:
        print("All slash scenarios returned content. ✅")
    else:
        print("At least one slash scenario failed validation. See logs above. ⚠️")
        sys.exit(1)


if __name__ == "__main__":
    main()

