from src.activity_graph.prioritization import (
    compute_doc_priorities,
    get_activity_signal_weights,
)


def test_get_activity_signal_weights_uses_config_overrides():
    config = {
        "activity_signals": {
            "weights": {
                "git": 5,
                "issues": 1,
                "support": 2,
                "slack": 0.5,
                "docs": 3,
            }
        }
    }

    weights = get_activity_signal_weights(config)

    assert weights["git"] == 5
    assert weights["issues"] == 1
    assert weights["support"] == 2
    assert weights["slack"] == 0.5
    assert weights["docs"] == 3


def test_compute_doc_priorities_ranks_high_severity_docs_first():
    weights = {
        "git": 3.0,
        "issues": 2.0,
        "support": 1.5,
        "slack": 1.0,
        "docs": 1.0,
    }
    component_activity = {
        "git_events": 12,
        "slack_conversations": 4,
        "slack_complaints": 2,
        "open_doc_issues": 3,
    }
    doc_issues = [
        {
            "doc_id": "doc:low",
            "doc_title": "Docs overview",
            "severity": "low",
            "impact_level": "low",
            "confidence": 0.4,
        },
        {
            "doc_id": "doc:high",
            "doc_title": "Core API Rollout",
            "severity": "high",
            "impact_level": "high",
            "confidence": 0.95,
        },
    ]

    priorities = compute_doc_priorities(doc_issues, component_activity, weights, max_results=2)

    assert len(priorities) == 2
    assert priorities[0]["doc_id"] == "doc:high"
    assert priorities[0]["score"] > priorities[1]["score"]


def test_prioritization_prefers_high_severity_doc_when_support_weight_high(capsys):
    weights = {
        "git": 3.0,
        "issues": 1.0,
        "support": 4.0,
        "slack": 0.5,
        "docs": 1.0,
    }
    component_activity = {
        "git_events": 12,
        "slack_conversations": 3,
        "slack_complaints": 5,
        "open_doc_issues": 3,
    }
    doc_issues = [
        {
            "doc_id": "doc:git-heavy",
            "doc_title": "Git Heavy Doc",
            "severity": "low",
            "impact_level": "low",
            "confidence": 0.7,
        },
        {
            "doc_id": "doc:support-heavy",
            "doc_title": "Support Heavy Doc",
            "severity": "high",
            "impact_level": "high",
            "confidence": 0.7,
        },
    ]

    priorities = compute_doc_priorities(doc_issues, component_activity, weights, max_results=2)

    print(
        "Doc priority scores:",
        [(item["doc_id"], round(item["score"], 4)) for item in priorities],
    )
    captured = capsys.readouterr()
    assert "doc:git-heavy" in captured.out
    assert "doc:support-heavy" in captured.out

    assert priorities[0]["doc_id"] == "doc:support-heavy"
    assert priorities[0]["score"] > priorities[1]["score"]

