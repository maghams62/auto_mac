from src.traceability.eval import evaluate_investigation_alignment


def test_evaluate_investigation_alignment_detects_missing_evidence():
    records = [
        {
            "id": "inv-1",
            "tool_runs": [{"tool": "slash:slack"}],
            "evidence": [{"evidence_id": "slack:1", "url": "https://slack"}],
        },
        {
            "id": "inv-2",
            "tool_runs": [{"tool": "slash:git"}],
            "evidence": [],
        },
    ]
    issues = evaluate_investigation_alignment(records)
    assert len(issues) == 1
    assert issues[0]["investigation_id"] == "inv-2"


def test_evaluate_investigation_alignment_ignores_conversation_only():
    records = [
        {
            "id": "inv-1",
            "tool_runs": [],
            "evidence": [],
        }
    ]
    issues = evaluate_investigation_alignment(records)
    assert issues == []

