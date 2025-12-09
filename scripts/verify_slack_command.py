#!/usr/bin/env python3
"""
Smoke-test helper for `/slack` channel recaps without opening the UI.

Example:
    python scripts/verify_slack_command.py \
        --query "/slack whats the conversation in #incidents" \
        --expected-channel incidents
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.orchestrator.slash_slack.orchestrator import SlashSlackOrchestrator
from src.services.slash_query_plan import SlashQueryPlanner
from src.ui.slash_commands import SlashCommandParser
from src.utils import load_config


def canonical_channel(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    cleaned = value.strip()
    if cleaned.startswith("#"):
        cleaned = cleaned[1:]
    return cleaned.lower() or None


def normalize_token(token: Optional[str]) -> Optional[str]:
    if not token:
        return None
    cleaned = "".join(ch for ch in token.lower() if ch.isalnum())
    return cleaned or None


def any_token_matches(values: Iterable[Optional[str]], expected: str) -> bool:
    for candidate in values:
        candidate_norm = normalize_token(candidate)
        if candidate_norm and expected in candidate_norm:
            return True
    return False


def collect_scope_labels(result: Dict[str, any]) -> List[str]:
    metadata = result.get("metadata") or {}
    context = result.get("context") or {}
    scope: List[str] = []
    for value in metadata.get("channel_scope") or []:
        scope.append(str(value))
    for value in metadata.get("channel_scope_labels") or []:
        scope.append(str(value))
    for value in context.get("channel_scope_labels") or []:
        scope.append(str(value))
    sources = result.get("sources") or []
    for source in sources:
        channel = source.get("channel")
        if channel:
            scope.append(str(channel))
    return scope


def print_check(passed: bool, label: str, detail: str) -> None:
    status = "[OK ]" if passed else "[FAIL]"
    print(f"{status} {label}: {detail}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify /slack channel summaries via backend components.")
    parser.add_argument(
        "--query",
        default="/slack whats the conversation in #incidents",
        help="Slash command to execute.",
    )
    parser.add_argument(
        "--expected-channel",
        default="incidents",
        help="Expected channel slug (without #).",
    )
    parser.add_argument(
        "--config",
        default=str(REPO_ROOT / "config.yaml"),
        help="Path to config.yaml (defaults to repository root).",
    )
    parser.add_argument(
        "--ignore-warnings",
        action="store_true",
        help="Do not fail when retrieval warnings (API errors, fallbacks) occur.",
    )
    args = parser.parse_args()

    expected_token = normalize_token(canonical_channel(args.expected_channel))
    if not expected_token:
        print("Expected channel must contain at least one alphanumeric character.", file=sys.stderr)
        return 2

    config_path = str(Path(args.config).expanduser())
    config = load_config(config_path, use_global_manager=False)
    slash_parser = SlashCommandParser()
    parsed = slash_parser.parse(args.query)
    planner = SlashQueryPlanner(config)
    if parsed.get("command") != "slack":
        print("Provided query is not a /slack command.", file=sys.stderr)
        return 2

    plan = planner.plan(parsed["task"], command="slack")
    plan_targets = [
        canonical_channel(target.label)
        or canonical_channel(target.identifier)
        or canonical_channel(target.raw)
        for target in plan.targets
    ]
    disambiguation_passed = any_token_matches(plan_targets, expected_token)
    print_check(
        disambiguation_passed,
        "Task disambiguation",
        f"targets={plan_targets or ['<none>']}",
    )

    orchestrator = SlashSlackOrchestrator(config=config)
    result = orchestrator.handle(parsed["task"], plan=plan)
    if result.get("error"):
        print_check(False, "Orchestrator execution", result.get("message", "Unknown error"))
        return 1
    else:
        print_check(True, "Orchestrator execution", result.get("type") or "slash_slack_summary")

    metadata = result.get("metadata") or {}
    scope_labels = collect_scope_labels(result)
    scope_tokens = [canonical_channel(label) for label in scope_labels if label]
    channel_passed = any_token_matches(scope_tokens, expected_token)
    channel_detail = f"scope={scope_labels or ['<none>']}"
    print_check(channel_passed, "Channel scope", channel_detail)

    message_text = (result.get("message") or "").strip()
    summary_passed = len(message_text) > 0
    summary_detail = message_text[:200] + ("…" if len(message_text) > 200 else "")
    print_check(summary_passed, "Summary generated", summary_detail or "<empty>")

    sources = result.get("sources") or []
    permalink = next((source.get("permalink") for source in sources if source.get("permalink")), None)
    deep_link_passed = bool(permalink)
    deep_link_detail = permalink or "<missing>"
    print_check(deep_link_passed, "Slack deep link", deep_link_detail)

    warnings = metadata.get("retrieval_warnings") or []
    warnings_passed = args.ignore_warnings or not warnings
    for warning in warnings:
        print_check(False, "Retrieval warning", warning)

    all_passed = disambiguation_passed and channel_passed and summary_passed and deep_link_passed and warnings_passed
    overall_label = "PASS" if all_passed else "FAIL"
    print(f"\nOverall result: {overall_label}")
    return 0 if all_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())

