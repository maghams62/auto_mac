import json

from src.graph.dependency_graph import DependencyGraphBuilder
from src.impact.doc_issues import DocIssueService
from src.impact.models import ImpactEntityType, ImpactLevel, ImpactReport, ImpactedEntity


def _build_report(reason: str = "Documents impacted dependency comp:alpha") -> ImpactReport:
    return ImpactReport(
        change_id="repo-alpha#PR-42",
        change_title="Touch alpha",
        change_summary="Removed deprecated field",
        impact_level=ImpactLevel.HIGH,
        changed_components=[
            ImpactedEntity(
                entity_id="comp:alpha",
                entity_type=ImpactEntityType.COMPONENT,
                confidence=0.9,
                reason="1 file mapped to comp:alpha",
                impact_level=ImpactLevel.HIGH,
            )
        ],
        impacted_components=[],
        impacted_services=[],
        impacted_docs=[
            ImpactedEntity(
                entity_id="doc:alpha-guide",
                entity_type=ImpactEntityType.DOC,
                confidence=0.8,
                reason=reason,
                impact_level=ImpactLevel.MEDIUM,
                metadata={"component_id": "comp:alpha"},
            )
        ],
        impacted_apis=[],
        slack_threads=[],
        metadata={
            "change": {
                "identifier": "repo-alpha#PR-42",
                "repo": "repo-alpha",
                "metadata": {"url": "https://example.com/pr/42", "pr_number": 42},
            }
        },
    )


def test_doc_issue_service_creates_issue(tmp_path, impact_test_config, dependency_map_file):
    impact_test_config["context_resolution"]["dependency_files"] = [str(dependency_map_file)]
    graph = DependencyGraphBuilder(impact_test_config).build(write_to_graph=False)

    store_path = tmp_path / "doc_issues.json"
    service = DocIssueService(store_path)
    report = _build_report()

    records = service.create_from_impact(report, graph)

    assert len(records) == 1
    saved = json.loads(store_path.read_text())
    issue = saved[0]
    assert issue["doc_id"] == "doc:alpha-guide"
    assert issue["severity"] == "medium"
    assert issue["repo_id"] == "repo-alpha"
    assert issue["component_ids"] == ["comp:alpha"]
    assert issue["service_ids"] == ["svc:alpha"]
    assert issue["linked_change"] == "repo-alpha#PR-42"
    assert issue["source"] == "impact-report"
    assert issue["change_context"]["identifier"] == "repo-alpha#PR-42"
    assert issue["links"][0]["type"] == "git"


def test_doc_issue_service_updates_existing_issue(tmp_path, impact_test_config, dependency_map_file):
    impact_test_config["context_resolution"]["dependency_files"] = [str(dependency_map_file)]
    graph = DependencyGraphBuilder(impact_test_config).build(write_to_graph=False)

    store_path = tmp_path / "doc_issues.json"
    service = DocIssueService(store_path)
    first = _build_report(reason="Initial reason")
    second = _build_report(reason="Updated downstream impact")

    service.create_from_impact(first, graph)
    service.create_from_impact(second, graph)

    saved = json.loads(store_path.read_text())
    assert len(saved) == 1
    issue = saved[0]
    assert issue["summary"] == "Updated downstream impact"
    assert issue["linked_change"] == "repo-alpha#PR-42"
    assert issue["created_at"] <= issue["updated_at"]

