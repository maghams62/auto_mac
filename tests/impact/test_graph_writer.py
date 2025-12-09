import json

from src.graph.dependency_graph import DependencyGraphBuilder
from src.impact.graph_writer import ImpactGraphWriter
from src.impact.models import ImpactEntityType, ImpactLevel, ImpactReport, ImpactedEntity


class FakeIngestor:
    def __init__(self):
        self.called = False
        self.last_event = None

    def available(self) -> bool:
        return True

    def upsert_impact_event(
        self,
        event_id,
        *,
        properties,
        component_ids,
        service_ids,
        doc_ids,
        slack_thread_ids,
        git_event_ids,
    ):
        self.called = True
        self.last_event = {
            "event_id": event_id,
            "properties": properties,
            "component_ids": component_ids,
            "service_ids": service_ids,
            "doc_ids": doc_ids,
            "slack_thread_ids": slack_thread_ids,
            "git_event_ids": git_event_ids,
        }


def test_graph_writer_emits_event(tmp_path, impact_test_config, dependency_map_file):
    impact_test_config["context_resolution"]["dependency_files"] = [str(dependency_map_file)]
    graph = DependencyGraphBuilder(impact_test_config).build(write_to_graph=False)

    ingestor = FakeIngestor()
    log_path = tmp_path / "impact_events.jsonl"
    writer = ImpactGraphWriter(ingestor, log_path)

    report = ImpactReport(
        change_id="repo-alpha#PR-10",
        change_title="Refactor alpha",
        change_summary="Touched alpha docs",
        impact_level=ImpactLevel.MEDIUM,
        changed_components=[
            ImpactedEntity(
                entity_id="comp:alpha",
                entity_type=ImpactEntityType.COMPONENT,
                confidence=0.9,
                reason="changed files",
                impact_level=ImpactLevel.HIGH,
            )
        ],
        impacted_components=[
            ImpactedEntity(
                entity_id="comp:beta",
                entity_type=ImpactEntityType.COMPONENT,
                confidence=0.7,
                reason="depends on alpha",
                impact_level=ImpactLevel.MEDIUM,
            )
        ],
        impacted_services=[],
        impacted_docs=[
            ImpactedEntity(
                entity_id="doc:alpha-guide",
                entity_type=ImpactEntityType.DOC,
                confidence=0.8,
                reason="documents alpha",
                impact_level=ImpactLevel.MEDIUM,
            )
        ],
        impacted_apis=[],
        slack_threads=[
            ImpactedEntity(
                entity_id="slack:#alpha:123",
                entity_type=ImpactEntityType.SLACK_THREAD,
                confidence=0.6,
                reason="Slack complaint",
                impact_level=ImpactLevel.MEDIUM,
            )
        ],
        metadata={
            "change": {
                "identifier": "repo-alpha#PR-10",
                "repo": "repo-alpha",
                "metadata": {"url": "https://example.com/pr/10"},
            },
            "slack_context": {
                "thread_id": "slack:#alpha:123",
                "permalink": "https://slack.com/archives/alpha/p123",
            },
        },
    )

    doc_issues = [{"id": "impact:doc:repo-alpha#PR-10"}]

    writer.write(report, graph, doc_issues)

    assert ingestor.called
    assert ingestor.last_event["event_id"] == "repo-alpha#PR-10"
    assert "comp:alpha" in ingestor.last_event["component_ids"]
    assert "comp:beta" in ingestor.last_event["component_ids"]
    assert ingestor.last_event["doc_ids"] == ["doc:alpha-guide"]
    assert ingestor.last_event["slack_thread_ids"] == ["slack:#alpha:123"]
    assert ingestor.last_event["properties"]["source_kind"] == "slack"

    lines = log_path.read_text().strip().splitlines()
    assert len(lines) == 1
    payload = json.loads(lines[0])
    assert payload["doc_issue_ids"] == ["impact:doc:repo-alpha#PR-10"]
    assert payload["properties"]["impact_level"] == "medium"

