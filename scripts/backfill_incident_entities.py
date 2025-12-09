#!/usr/bin/env python3
"""
Backfill `incident_entities` for incidents stored in JSON (data/live/investigations.jsonl by default).

Usage:
    python scripts/backfill_incident_entities.py --input data/live/investigations.jsonl --write
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Dict, List

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.traceability.incidents import summarize_incident_entities


def _compute_entities(record: Dict[str, Any]) -> List[Dict[str, Any]]:
    context = record.get("incident_context") or {}
    scope = context.get("impacted_nodes") or context.get("incident_scope") or {}
    doc_priorities = record.get("doc_priorities") or (
        (record.get("metadata") or {}).get("incident_candidate_snapshot", {}).get("doc_priorities")
        if isinstance(record.get("metadata"), dict)
        else []
    )
    dependency_impact = record.get("dependency_impact") or (
        (record.get("metadata") or {}).get("incident_candidate_snapshot", {}).get("dependency_impact")
        if isinstance(record.get("metadata"), dict)
        else None
    )
    evidence = record.get("evidence") or (
        (record.get("metadata") or {}).get("incident_candidate_snapshot", {}).get("evidence")
        if isinstance(record.get("metadata"), dict)
        else []
    )
    activity_signals = record.get("activity_signals") or (
        (record.get("metadata") or {}).get("incident_candidate_snapshot", {}).get("activity_signals")
        if isinstance(record.get("metadata"), dict)
        else None
    )
    dissatisfaction_signals = record.get("dissatisfaction_signals") or (
        (record.get("metadata") or {}).get("incident_candidate_snapshot", {}).get("dissatisfaction_signals")
        if isinstance(record.get("metadata"), dict)
        else None
    )
    return summarize_incident_entities(
        scope,
        doc_priorities,
        dependency_impact,
        evidence,
        activity_signals,
        dissatisfaction_signals,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill incident_entities for stored incidents.")
    parser.add_argument("--input", type=Path, default=Path("data/live/investigations.jsonl"))
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional output path. If omitted, --write controls in-place updates.",
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="Persist changes back to --input when no --output is provided.",
    )
    args = parser.parse_args()

    if not args.input.exists():
        raise SystemExit(f"Input file {args.input} does not exist.")

    payload = json.loads(args.input.read_text(encoding="utf-8")) or []
    updated = 0
    for record in payload:
        if not isinstance(record, dict):
            continue
        entities = _compute_entities(record)
        if entities:
            record["incident_entities"] = entities
        elif "incident_entities" in record:
            del record["incident_entities"]
        updated += 1 if entities else 0

    target_path = args.output or args.input
    if args.output or args.write:
        target_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"Wrote updated incidents to {target_path} (entities computed for {updated} records).")
    else:
        print(f"(dry run) Computed incident_entities for {updated} records. Use --write to persist changes.")


if __name__ == "__main__":
    main()
