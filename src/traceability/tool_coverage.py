"""
Registry that documents which automation tools emit evidence for traceability.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List


@dataclass(frozen=True)
class ToolCoverage:
    produces_evidence: bool
    notes: str = ""

    @property
    def conversation_only(self) -> bool:
        return not self.produces_evidence


TOOL_COVERAGE_REGISTRY: Dict[str, ToolCoverage] = {
    "slash:slack": ToolCoverage(
        produces_evidence=True,
        notes="Slash Slack summaries emit references + evidence cards (thread permalinks).",
    ),
    "slash:git": ToolCoverage(
        produces_evidence=True,
        notes="Slash Git summaries emit PR/commit references with canonical IDs.",
    ),
    "slash:youtube": ToolCoverage(
        produces_evidence=True,
        notes="Slash YouTube summaries emit transcript snippets with timestamps and trace links.",
    ),
    # Non-evidence slash commands (example placeholder for future commands)
    "slash:clear": ToolCoverage(
        produces_evidence=False,
        notes="Utility command that clears the session and intentionally produces no evidence.",
    ),
}


def validate_tool_coverage(tool_names: Iterable[str]) -> None:
    """
    Ensure every tool name has an explicit coverage declaration.
    """
    missing: List[str] = []
    for tool in tool_names:
        if tool not in TOOL_COVERAGE_REGISTRY:
            missing.append(tool)
    if missing:
        raise ValueError(
            "Traceability coverage missing for tools: "
            + ", ".join(sorted(missing))
            + ". Update src/traceability/tool_coverage.py."
        )

