#!/usr/bin/env python3
"""
Quick Slack token verifier.

Usage:
    python scripts/check_slack_token.py [--token xoxb-...]

Reads the token from --token, SLACK_TOKEN, or SLACK_BOT_TOKEN (in that order)
and calls `auth.test` followed by a lightweight `conversations.list` fetch to
ensure the token has the expected scopes.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request


AUTH_TEST_URL = "https://slack.com/api/auth.test"
CONVERSATIONS_LIST_URL = "https://slack.com/api/conversations.list?limit=1"


def slack_api_call(url: str, token: str) -> dict:
    request = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=utf-8",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            payload = json.loads(response.read().decode("utf-8"))
            return payload
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"Slack request failed ({exc.code}): {exc.reason}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Slack request failed: {exc.reason}") from exc


def verify_token(token: str) -> int:
    print("🔐 Verifying Slack token via auth.test …")
    auth_payload = slack_api_call(AUTH_TEST_URL, token)
    if not auth_payload.get("ok"):
        print("❌ auth.test failed:", auth_payload.get("error", "unknown-error"))
        return 1

    team = auth_payload.get("team") or auth_payload.get("team_id")
    user = auth_payload.get("user") or auth_payload.get("user_id")
    print(f"✅ Token valid for team={team} user={user}")

    print("📡 Checking conversations.list scope …")
    conv_payload = slack_api_call(CONVERSATIONS_LIST_URL, token)
    if not conv_payload.get("ok"):
        print("⚠️ conversations.list failed:", conv_payload.get("error", "unknown-error"))
        print("    The token may be missing channels:read scope.")
        return 2

    channels = conv_payload.get("channels") or []
    channel_ids = [channel.get("id") for channel in channels if channel.get("id")]
    if channel_ids:
        print(f"✅ conversations.list succeeded (sample channel: {channel_ids[0]})")
    else:
        print("ℹ️ conversations.list succeeded but returned no channels (maybe no public channels).")
    return 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Verify a Slack bot token.")
    parser.add_argument(
        "--token",
        help="Slack bot token (xoxb-...). Defaults to SLACK_TOKEN (or legacy SLACK_BOT_TOKEN) env vars.",
    )
    args = parser.parse_args(argv)

    token = args.token or os.getenv("SLACK_TOKEN") or os.getenv("SLACK_BOT_TOKEN")
    if not token:
        print("❌ No token supplied. Pass --token or set SLACK_TOKEN (or SLACK_BOT_TOKEN).", file=sys.stderr)
        return 1

    return verify_token(token.strip())


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

