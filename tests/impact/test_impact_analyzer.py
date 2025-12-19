from src.graph.dependency_graph import DependencyGraphBuilder
from src.impact import GitChangePayload, GitFileChange, ImpactAnalyzer


def test_analyzer_outputs_docs_and_services(tmp_path, impact_test_config, dependency_map_file):
    impact_test_config["context_resolution"]["dependency_files"] = [str(dependency_map_file)]
    builder = DependencyGraphBuilder(impact_test_config)
    graph = builder.build(write_to_graph=False)

    analyzer = ImpactAnalyzer(graph)
    payload = GitChangePayload(
        identifier="PR-1",
        title="Touch alpha",
        repo="repo-alpha",
        files=[GitFileChange(path="src/alpha/service.py", repo="repo-alpha")],
    )

    report = analyzer.analyze_git_change(payload)

    assert any(entity.entity_id == "comp:alpha" for entity in report.changed_components)
    assert any(doc.entity_id == "doc:alpha-guide" for doc in report.impacted_docs)
    assert report.impacted_services
    assert report.changed_apis  # APIs owned by alpha are marked as changed
    assert report.impact_level.value in {"medium", "high"}

