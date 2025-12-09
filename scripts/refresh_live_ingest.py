#!/usr/bin/env python3
"""
Convenience wrapper to refresh all live ingest artifacts in one go.

It runs:
  1. scripts/check_live_env.py --require-dashboard
  2. scripts/run_activity_ingestion.py --sources <selected>
  3. scripts/impact_auto_ingest.py --limit <N>

Usage:
    python scripts/refresh_live_ingest.py
    python scripts/refresh_live_ingest.py --skip-slack --limit 10
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from typing import List


ROOT = Path(__file__).resolve().parent.parent


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Rebuild Slack/Git/DocIssue live data end-to-end.")
    parser.add_argument("--skip-slack", action="store_true", help="Do not run the Slack ingestion step.")
    parser.add_argument("--skip-git", action="store_true", help="Do not run the Git ingestion step.")
    parser.add_argument("--skip-impact", action="store_true", help="Do not refresh impact/doc issues.")
    parser.add_argument("--limit", type=int, default=20, help="Doc issue ingest limit (default: 20).")
    parser.add_argument(
        "--dotenv",
        default=".env",
        help="Backend dotenv passed to check_live_env (default: .env).",
    )
    parser.add_argument(
        "--dashboard-dotenv",
        default="oqoqo-dashboard/.env.local",
        help="Dashboard dotenv passed to check_live_env (default: oqoqo-dashboard/.env.local).",
    )
    return parser.parse_args()


def _run(cmd: List[str]) -> None:
    process = subprocess.run(cmd, cwd=ROOT, check=False)
    if process.returncode != 0:
        raise RuntimeError(f"{' '.join(cmd)} failed (exit {process.returncode}).")


def main() -> None:
    args = parse_args()
    ingest_sources: List[str] = []
    if not args.skip_slack:
        ingest_sources.append("slack")
    if not args.skip_git:
        ingest_sources.append("git")

    print("🔁 Refreshing live ingest data\n")
    try:
        _run(
            [
                sys.executable,
                "scripts/check_live_env.py",
                f"--dotenv={args.dotenv}",
                f"--dashboard-dotenv={args.dashboard_dotenv}",
                "--require-dashboard",
            ]
        )

        if ingest_sources:
            print(f"\n▶️  Running activity ingestion for: {', '.join(ingest_sources)}")
            _run(
                [
                    sys.executable,
                    "scripts/run_activity_ingestion.py",
                    "--sources",
                    ",".join(ingest_sources),
                ]
            )
        else:
            print("\n⚠️  Skipping activity ingestion entirely (both --skip-slack and --skip-git supplied).")

        if not args.skip_impact:
            print("\n▶️  Refreshing doc issues via impact_auto_ingest.py")
            _run(
                [
                    sys.executable,
                    "scripts/impact_auto_ingest.py",
                    "--limit",
                    str(max(1, args.limit)),
                ]
            )
        else:
            print("\n⚠️  Skipped impact/doc issue refresh.")

        print("\n✅ Live ingest refresh complete.")
    except RuntimeError as exc:
        print(f"\n❌ {exc}")
        print("Resolve the failure above, then rerun this script.")
        sys.exit(1)


if __name__ == "__main__":
    main()


