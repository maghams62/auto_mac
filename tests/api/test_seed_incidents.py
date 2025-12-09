from pathlib import Path
import json


def test_seed_incidents_cover_core_scenarios():
    payload = json.loads(Path("data/live/investigations.jsonl").read_text(encoding="utf-8"))
    incidents = [record for record in payload if (record.get("type") or "").lower() == "incident"]
    assert incidents, "expected seeded incidents in investigations store"

    def score(record: dict, field: str) -> float:
        value = record.get(field)
        if isinstance(value, (int, float)):
            return float(value)
        return 0.0

    activity_heavy = [
        record
        for record in incidents
        if score(record, "activity_score") >= 60 and score(record, "dissatisfaction_score") < 30
    ]
    dissatisfaction_heavy = [
        record for record in incidents if score(record, "dissatisfaction_score") >= 60
    ]
    cross_system = []
    for record in incidents:
        impact = record.get("dependency_impact")
        if not isinstance(impact, dict):
            continue
        impacts = impact.get("impacts")
        if isinstance(impacts, list) and impacts:
            cross_system.append(record)
    doc_drift_only = [
        record
        for record in incidents
        if score(record, "activity_score") <= 25
        and len(record.get("doc_priorities") or []) >= 1
        and not record.get("activity_signals", {}).get("git_events")
    ]

    assert activity_heavy, "seed data should include a high-activity scenario"
    assert dissatisfaction_heavy, "seed data should include a high-dissatisfaction scenario"
    assert cross_system, "seed data should include a cross-system dependency scenario"
    assert doc_drift_only, "seed data should include a doc-drift-only scenario"
    entities_present = [record for record in incidents if isinstance(record.get("incident_entities"), list)]
    assert entities_present, "seed data should include at least one incident with a populated report table"
    assert any(
        isinstance(record.get("incident_entities"), list) and record["incident_entities"]
        for record in cross_system
    ), "cross-system incidents should expose incident_entities rows"
