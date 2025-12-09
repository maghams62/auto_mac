"""
Transforms structured impact reports into human-readable reasoning traces.
"""

from __future__ import annotations

from typing import Callable, List, Optional, Tuple

from ..config.models import ImpactEvidenceSettings
from .models import ImpactEvidence, ImpactReport


class EvidenceGraphFormatter:
    """
    Creates deterministic evidence statements from ImpactReport entities.

    Optionally delegates to an LLM for polishing when enabled in config.
    """

    def __init__(
        self,
        settings: ImpactEvidenceSettings,
        *,
        llm_client: Optional[Callable[[str], str]] = None,
    ):
        self.settings = settings
        self._llm_client = llm_client

    def build(self, report: ImpactReport) -> List[ImpactEvidence]:
        bullets = self._build_bullets(report)
        if self.settings.llm_enabled and self._llm_client:
            prompt = self._render_prompt(report, bullets)
            llm_text = self._llm_client(prompt)
            return [ImpactEvidence(statement=line.strip()) for line in llm_text.splitlines() if line.strip()]
        return [ImpactEvidence(statement=bullet) for bullet in bullets]

    def summarize(self, report: ImpactReport, bullets: List[str]) -> Tuple[Optional[str], str]:
        mode = "deterministic"
        summary: Optional[str] = None
        if not bullets:
            return summary, mode

        if self.settings.llm_enabled and self._llm_client:
            prompt = self._render_prompt(report, bullets)
            try:
                summary_text = self._llm_client(prompt).strip()
                if summary_text:
                    summary = summary_text
                    mode = "llm"
                    return summary, mode
            except Exception:
                # Fall back to deterministic summary
                summary = None

        summary = self._deterministic_summary(bullets)
        return summary, mode

    def annotate(self, report: ImpactReport) -> ImpactReport:
        bullets = self._build_bullets(report)
        report.evidence = [ImpactEvidence(statement=bullet) for bullet in bullets]
        summary, mode = self.summarize(report, bullets)
        report.evidence_summary = summary
        report.evidence_mode = mode
        return report

    # ------------------------------------------------------------------
    # Internal helpers

    def _build_bullets(self, report: ImpactReport) -> List[str]:
        bullets: List[str] = []

        for entity in report.changed_components:
            bullets.append(f"{entity.entity_id} changed ({entity.reason})")

        for entity in report.changed_apis:
            bullets.append(f"API {entity.entity_id} updated ({entity.reason})")

        for entity in report.impacted_components:
            bullets.append(
                f"{entity.entity_id} impacted via dependency depth {entity.metadata.get('dependency_depth', '?')}"
            )

        for doc in report.impacted_docs:
            bullets.append(
                f"Documentation {doc.entity_id} references impacted component {doc.metadata.get('component_id')}"
            )

        for service in report.impacted_services:
            bullets.append(f"Service {service.entity_id} must react because {service.reason}")

        for slack in report.slack_threads:
            bullets.append(f"Slack thread {slack.entity_id} highlights user confusion ({slack.reason})")

        max_items = max(1, self.settings.max_bullets)
        return bullets[:max_items]

    def _deterministic_summary(self, bullets: List[str]) -> str:
        if not bullets:
            return ""
        if len(bullets) == 1:
            return bullets[0]
        first, second, *rest = bullets
        summary_parts = [first, second]
        if rest:
            summary_parts.append(f"Additional context: {rest[0]}")
        return " ".join(summary_parts)

    def _render_prompt(self, report: ImpactReport, bullets: List[str]) -> str:
        lines = [
            "You are a release manager summarizing why documentation/services need updates.",
            "Use the bullet list below and rewrite it with concise natural language sentences.",
            "",
            "Bullets:",
        ]
        for bullet in bullets:
            lines.append(f"- {bullet}")
        lines.append("")
        lines.append("Produce 2-4 sentences. Do not invent facts beyond the bullets.")
        return "\n".join(lines)

