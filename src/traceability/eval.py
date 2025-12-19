"""
Lightweight evaluation helpers for traceability alignment.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List


def evaluate_investigation_alignment(records: Iterable[Dict[str, Any]]) -> List[Dict[str, str]]:
    """
    Return a list of issues where investigations lack evidence coverage.
    """
    issues: List[Dict[str, str]] = []
    for index, record in enumerate(records):
        tool_runs = record.get("tool_runs") or []
        evidence = record.get("evidence") or []
        has_evidence = any(ev.get("evidence_id") or ev.get("url") for ev in evidence)
        if tool_runs and not has_evidence:
            issues.append(
                {
                    "investigation_id": str(record.get("id") or f"record-{index}"),
                    "reason": "missing_evidence",
                }
            )
    return issues

