from src.config.models import ImpactEvidenceSettings
from src.impact.evidence_graph import EvidenceGraphFormatter
from src.impact.models import ImpactEntityType, ImpactLevel, ImpactReport, ImpactedEntity


def test_evidence_formatter_builds_bullets():
    report = ImpactReport(
        change_id="PR-2",
        impact_level=ImpactLevel.MEDIUM,
        changed_components=[
            ImpactedEntity(
                entity_id="comp:alpha",
                entity_type=ImpactEntityType.COMPONENT,
                confidence=0.95,
                reason="1 file(s) mapped to comp:alpha",
                impact_level=ImpactLevel.HIGH,
            )
        ],
        changed_apis=[],
        impacted_components=[
            ImpactedEntity(
                entity_id="comp:beta",
                entity_type=ImpactEntityType.COMPONENT,
                confidence=0.6,
                reason="Depends on comp:alpha",
                impact_level=ImpactLevel.MEDIUM,
                metadata={"dependency_depth": 1},
            )
        ],
        impacted_services=[],
        impacted_docs=[],
        impacted_apis=[],
        slack_threads=[],
        recommendations=[],
    )

    settings = ImpactEvidenceSettings(llm_enabled=False, llm_model=None, max_bullets=3)
    formatter = EvidenceGraphFormatter(settings)
    formatter.annotate(report)

    assert len(report.evidence) == 2
    assert "comp:alpha" in report.evidence[0].statement
    assert report.evidence_summary
    assert report.evidence_mode == "deterministic"

