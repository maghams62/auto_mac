#!/usr/bin/env python3
"""
Seed the Activity Graph + doc issues using the bundled synthetic fixtures.

This script is a convenience wrapper around the existing ingestion pipelines:

    python scripts/seed_activity_graph.py

It will:
  1. Run `scripts/run_activity_ingestion.py` in fixture mode (Slack + Git + doc issues)
  2. Refresh doc issues via `scripts/impact_auto_ingest.py --allow-synthetic`

Use --skip-impact to omit step 2 if you only care about ActivitySignal entries.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from typing import List

ROOT = Path(__file__).resolve().parent.parent


def _run(cmd: List[str]) -> None:
    pretty = " ".join(cmd)
    print(f"\n$ {pretty}")
    proc = subprocess.run(cmd, cwd=ROOT, check=False)
    if proc.returncode != 0:
        raise SystemExit(proc.returncode)


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed the Activity Graph using synthetic fixtures.")
    parser.add_argument(
        "--repo-id",
        default="fixtures:activity",
        help="Repo identifier used for git fixture ingestion (default: %(default)s).",
    )
    parser.add_argument(
        "--impact-limit",
        type=int,
        default=20,
        help="Max commits per repo when running impact_auto_ingest.py (default: %(default)s).",
    )
    parser.add_argument(
        "--skip-impact",
        action="store_true",
        help="Skip the impact_auto_ingest refresh step.",
    )
    args = parser.parse_args()

    ingest_cmd = [
        sys.executable,
        "scripts/run_activity_ingestion.py",
        "--sources",
        "slack",
        "git",
        "doc_issues",
        "--fixture-repo-id",
        args.repo_id,
    ]
    _run(ingest_cmd)

    if not args.skip_impact:
        impact_cmd = [
            sys.executable,
            "scripts/impact_auto_ingest.py",
            "--limit",
            str(max(1, args.impact_limit)),
            "--allow-synthetic",
        ]
        _run(impact_cmd)
    else:
        print("[IMPACT] Skipped per --skip-impact")

    print("\n✅ Activity Graph seed complete.")


if __name__ == "__main__":
    main()


