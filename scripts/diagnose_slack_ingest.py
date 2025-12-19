#!/usr/bin/env python3
"""
Sanity-check Slack ingest credentials before running the live pipeline.

Usage:
    python scripts/diagnose_slack_ingest.py
    python scripts/diagnose_slack_ingest.py --channel C12345678
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from typing import Dict, Optional

import requests


API_BASE = "https://slack.com/api"


class SlackDiagError(RuntimeError):
    """Raised when Slack diagnostics fail."""


@dataclass
class SlackDiagResult:
    ok: bool
    message: str
    detail: Optional[str] = None


def _build_headers(token: str) -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json; charset=utf-8",
        "User-Agent": "CerebrosLiveDiag/1.0",
    }


def _request(endpoint: str, token: str, params: Optional[Dict[str, str]] = None) -> Dict[str, object]:
    response = requests.get(f"{API_BASE}/{endpoint}", headers=_build_headers(token), params=params, timeout=30)
    response.raise_for_status()
    data = response.json()
    if not data.get("ok"):
        raise SlackDiagError(f"{endpoint} failed: {data.get('error', 'unknown_error')}")
    return data


def _auth_test(token: str) -> SlackDiagResult:
    data = _request("auth.test", token)
    team = data.get("team") or data.get("team_id") or "unknown team"
    user = data.get("user") or data.get("user_id") or "unknown user"
    return SlackDiagResult(ok=True, message=f"Token valid for {team} as {user}.")


def _channel_probe(token: str, channel: str) -> SlackDiagResult:
    info = _request("conversations.info", token, params={"channel": channel})
    channel_info = info.get("channel") or {}
    name = channel_info.get("name") or channel
    if not channel_info.get("is_member", True):
        return SlackDiagResult(
            ok=False,
            message=f"Bot/user is not in #{name}",
            detail="Invite the Slack app or user token to the channel and rerun.",
        )
    return SlackDiagResult(ok=True, message=f"Channel #{name} reachable.")


def _history_probe(token: str, channel: str) -> SlackDiagResult:
    history = _request(
        "conversations.history",
        token,
        params={
            "channel": channel,
            "limit": 3,
        },
    )
    messages = history.get("messages") or []
    preview = [
        {
            "user": msg.get("user") or msg.get("username"),
            "ts": msg.get("ts"),
            "text": (msg.get("text") or "").strip(),
        }
        for msg in messages
    ]
    snippet = json.dumps(preview, indent=2)
    return SlackDiagResult(
        ok=True,
        message=f"Fetched {len(messages)} messages via conversations.history.",
        detail=f"Sample:\n{snippet}",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Diagnose Slack ingest connectivity.")
    parser.add_argument(
        "--token",
        default=os.getenv("SLACK_TOKEN") or os.getenv("SLACK_BOT_TOKEN"),
        help="Slack bot token to test (default: SLACK_TOKEN env var, falling back to SLACK_BOT_TOKEN).",
    )
    parser.add_argument(
        "--channel",
        default=os.getenv("SLACK_CHANNEL_ID"),
        help="Channel ID to probe (default: SLACK_CHANNEL_ID env var).",
    )
    parser.add_argument(
        "--skip-history",
        action="store_true",
        help="Skip the conversations.history probe (useful when rate limited).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.token:
        print("❌ SLACK_TOKEN (or legacy SLACK_BOT_TOKEN) is not set.\nSet it in your shell or DONT_PUSH_env_stuff.md and rerun.")
        sys.exit(1)
    if not args.channel:
        print("❌ SLACK_CHANNEL_ID is not set.\nProvide --channel explicitly or export SLACK_CHANNEL_ID.")
        sys.exit(1)

    print("🔍 Slack ingest diagnostics\n")
    try:
        auth = _auth_test(args.token)
        print(f"✅ {auth.message}\n")

        channel = _channel_probe(args.token, args.channel)
        if channel.ok:
            print(f"✅ {channel.message}\n")
        else:
            print(f"❌ {channel.message}")
            if channel.detail:
                print(channel.detail)
            sys.exit(1)

        if not args.skip_history:
            history = _history_probe(args.token, args.channel)
            print(f"✅ {history.message}")
            if history.detail:
                print(history.detail)

        print("\nSlack credentials look good — ready for `run_activity_ingestion.py --sources slack`.")
    except SlackDiagError as exc:
        print(f"❌ Slack API rejected the request: {exc}")
        print("   → Double-check the token scopes (channels:history, channels:read, search:read, users:read).")
        sys.exit(1)
    except requests.RequestException as exc:
        print(f"❌ Network error while calling Slack: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()


