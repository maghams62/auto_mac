#!/usr/bin/env python3
"""
Quick checklist to verify Cerebros live-ingest environment variables.

Usage:
    python scripts/check_live_env.py
    python scripts/check_live_env.py --dotenv my.env --dashboard-dotenv oqoqo-dashboard/.env.local
"""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

REQUIRED_CORE_VARS = [
    "GITHUB_TOKEN",
    "SLACK_TOKEN",
    "SLACK_SIGNING_SECRET",
    "NEO4J_URI",
    "NEO4J_USER",
    "NEO4J_PASSWORD",
]

ALIAS_KEYS = {
    "SLACK_TOKEN": ["SLACK_BOT_TOKEN"],
}

DASHBOARD_VARS = [
    "CEREBROS_API_BASE",
    "NEXT_PUBLIC_CEREBROS_API_BASE",
]


@dataclass
class EnvReport:
    missing: List[str]
    empty: List[str]

    @property
    def ok(self) -> bool:
        return not self.missing and not self.empty


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate live ingest environment variables.")
    parser.add_argument(
        "--dotenv",
        default=".env",
        help="Path to the backend .env file (default: .env)",
    )
    parser.add_argument(
        "--dashboard-dotenv",
        default="oqoqo-dashboard/.env.local",
        help="Path to the dashboard env file (default: oqoqo-dashboard/.env.local)",
    )
    parser.add_argument(
        "--require-dashboard",
        action="store_true",
        help="Fail if dashboard env values are missing.",
    )
    return parser.parse_args()


def load_env_file(path: Path) -> Dict[str, str]:
    if not path.exists():
        return {}
    entries: Dict[str, str] = {}
    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        entries[key.strip()] = value.strip().strip('"').strip("'")
    return entries


def resolve_value(key: str, env_map: Dict[str, str]) -> tuple[Optional[str], Optional[str]]:
    candidates = [key] + ALIAS_KEYS.get(key, [])
    for candidate in candidates:
        value = env_map.get(candidate, os.getenv(candidate))
        if value is not None:
            return candidate, value
    return None, None


def evaluate(keys: List[str], env_map: Dict[str, str]) -> EnvReport:
    missing: List[str] = []
    empty: List[str] = []
    for key in keys:
        _source, value = resolve_value(key, env_map)
        if value is None:
            missing.append(key)
        elif str(value).strip() == "":
            empty.append(key)
    return EnvReport(missing=missing, empty=empty)


def main() -> None:
    args = parse_args()

    backend_env = load_env_file(Path(args.dotenv))
    dashboard_env = load_env_file(Path(args.dashboard_dotenv))

    core_report = evaluate(REQUIRED_CORE_VARS, backend_env)
    dash_report = evaluate(DASHBOARD_VARS, {**backend_env, **dashboard_env})

    print("🔍 Live ingest secrets check\n")
    print(f"Backend env file: {Path(args.dotenv).resolve()}")
    print(f"Dashboard env file: {Path(args.dashboard_dotenv).resolve()}\n")

    if core_report.ok:
        print("✅ Core Cerebros ingest variables are present.")
    else:
        if core_report.missing:
            print("❌ Missing variables:")
            for key in core_report.missing:
                print(f"   - {key}")
        if core_report.empty:
            print("\n⚠️  Empty variables (set a real value):")
            for key in core_report.empty:
                print(f"   - {key}")

    if dash_report.ok:
        print("\n✅ Dashboard bridge variables detected.")
    else:
        if dash_report.missing:
            print("\n⚠️  Dashboard variables missing:")
            for key in dash_report.missing:
                print(f"   - {key}")
        if dash_report.empty:
            print("\n⚠️  Dashboard variables empty:")
            for key in dash_report.empty:
                print(f"   - {key}")

    if core_report.ok and (dash_report.ok or not args.require_dashboard):
        print("\nAll required variables detected — ready for `run_activity_ingestion.py`.")
        sys.exit(0)

    print("\nResolve the missing values above, then rerun this script.")
    sys.exit(1)


if __name__ == "__main__":
    main()

