#!/usr/bin/env python3
"""
Quick alignment check for investigations.jsonl.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, List

from src.traceability.eval import evaluate_investigation_alignment


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate investigation evidence alignment.")
    parser.add_argument(
        "--path",
        default="data/live/investigations.jsonl",
        help="Path to investigations store (JSON array).",
    )
    args = parser.parse_args()

    path = Path(args.path)
    if not path.exists():
        raise SystemExit(f"Store file not found: {path}")

    try:
        records: List[dict[str, Any]] = json.loads(path.read_text(encoding="utf-8") or "[]")
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid JSON: {exc}") from exc

    issues = evaluate_investigation_alignment(records)
    if not issues:
        print("✅ All investigations with tool runs have evidence.")
        return

    print(f"⚠️  Found {len(issues)} investigations missing evidence context:")
    for issue in issues:
        print(f" - {issue['investigation_id']}: {issue['reason']}")


if __name__ == "__main__":
    main()

