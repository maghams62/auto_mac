from src.agent.evidence import Evidence, EvidenceCollection
from src.agent.multi_source_reasoner import MultiSourceReasoner


def _build_reasoner() -> MultiSourceReasoner:
    reasoner = object.__new__(MultiSourceReasoner)
    reasoner.config = {}
    return reasoner


def test_summary_prompt_includes_metadata_and_incident_sections():
    reasoner = _build_reasoner()

    evidence = EvidenceCollection(query="comp:core-api")
    evidence.add(
        Evidence(
            source_type="doc_issue",
            source_name="Doc issue – VAT guide",
            content="Docs still mention optional vat_code\nSeverity: high",
            metadata={
                "severity": "high",
                "component_ids": ["comp:core-api"],
                "doc_issue_id": "docissue-vat",
                "doc_path": "docs/payments_api.md",
            },
        )
    )
    evidence.add(
        Evidence(
            source_type="git",
            source_name="PR #118",
            content="Require vat_code flag in checkout",
            metadata={"component_id": "comp:core-api"},
        )
    )

    prompt = reasoner._build_summary_prompt(evidence, conflicts=[], gaps=[])

    # Basic structural sanity checks on the summary prompt.
    assert "METADATA YOU MUST USE" in prompt
    assert "Doc drift candidates" in prompt
    # New top-level headings required by the response format.
    assert "SOURCE EVIDENCE:" in prompt
    assert "GRAPH EVIDENCE:" in prompt
    assert "DRIFT:" in prompt
    assert "CANONICAL CURRENT TRUTH:" in prompt
    assert "ACTIONS:" in prompt
    assert "GAPS:" in prompt
    assert "INCIDENT SUGGESTION:" in prompt
