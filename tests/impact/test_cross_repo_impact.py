from pathlib import Path
import textwrap

from src.graph.dependency_graph import DependencyGraphBuilder
from src.impact import GitChangePayload, GitFileChange, ImpactAnalyzer
from src.impact.doc_issues import DocIssueService
from src.impact.models import SlackComplaintContext


def test_cross_repo_change_propagates_docs(tmp_path, impact_test_config):
    dependency_file = _write_cross_repo_dependency_map(tmp_path)
    impact_test_config["context_resolution"]["dependency_files"] = [str(dependency_file)]
    graph = DependencyGraphBuilder(impact_test_config).build(write_to_graph=False)
    analyzer = ImpactAnalyzer(graph)

    payload = GitChangePayload(
        identifier="repo-a@123",
        title="Repo A routing change",
        repo="repo-a",
        files=[GitFileChange(path="src/repo_a/service.py", repo="repo-a")],
    )

    report = analyzer.analyze_git_change(payload)

    impacted_components = {entity.entity_id for entity in report.impacted_components}
    assert "comp:repoB" in impacted_components
    assert "comp:repoC" in impacted_components

    impacted_docs = {doc.entity_id for doc in report.impacted_docs}
    assert "doc:repo-c-guide" in impacted_docs


def test_slack_context_enriched_doc_issue(tmp_path, impact_test_config):
    dependency_file = _write_cross_repo_dependency_map(tmp_path)
    impact_test_config["context_resolution"]["dependency_files"] = [str(dependency_file)]
    graph = DependencyGraphBuilder(impact_test_config).build(write_to_graph=False)
    analyzer = ImpactAnalyzer(graph)

    payload = GitChangePayload(
        identifier="repo-a@456",
        title="Repo A regression",
        repo="repo-a",
        files=[GitFileChange(path="src/repo_a/service.py", repo="repo-a")],
    )
    slack_context = SlackComplaintContext(
        thread_id="slack:C999:1234.56",
        channel="C999",
        component_ids=["comp:repoA"],
        api_ids=[],
        text="Clients seeing timeout in repo A",
        permalink="https://workspace.slack.com/archives/C999/p123456",
    )
    report = analyzer.analyze_git_change(payload, slack_context=slack_context)

    store_path = tmp_path / "doc_issues.json"
    doc_service = DocIssueService(store_path)
    issues = doc_service.create_from_impact(report, graph)

    assert issues, "Doc issues should be created for downstream docs"
    issue = issues[0]
    assert issue.get("slack_context", {}).get("thread_id") == slack_context.thread_id
    assert issue.get("doc_update_hint")
    assert issue.get("doc_url")
    assert issue.get("severity") in {"high", "medium", "low"}


def _write_cross_repo_dependency_map(tmp_path: Path) -> Path:
    path = tmp_path / "dependency_cross_repo.yaml"
    path.write_text(
        textwrap.dedent(
            """
            components:
              - id: comp:repoA
                repo: repo-a
                artifacts:
                  - id: code:repoA:service
                    repo: repo-a
                    path: src/repo_a/service.py
              - id: comp:repoB
                repo: repo-b
                artifacts:
                  - id: code:repoB:worker
                    repo: repo-b
                    path: workers/repo_b.py
              - id: comp:repoC
                repo: repo-c
                artifacts:
                  - id: code:repoC:client
                    repo: repo-c
                    path: clients/repo_c.py
                docs:
                  - id: doc:repo-c-guide
                    title: Repo C Guide
                    repo: docs-site
                    path: docs/repo_c.md
            dependencies:
              - from_component: comp:repoB
                to_component: comp:repoA
                reason: "Repo B builds on Repo A"
              - from_component: comp:repoC
                to_component: comp:repoB
                reason: "Repo C relies on Repo B outputs"
            """
        ).strip()
    )
    return path

