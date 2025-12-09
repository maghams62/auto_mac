from src.graph.dependency_graph import DependencyGraphBuilder
from src.impact import GitChangePayload, GitFileChange, ImpactAnalyzer, ImpactPipeline, SlackComplaintContext


def test_pipeline_processes_git_and_slack_flows(impact_config_context, dependency_map_file):
    config = impact_config_context.data
    config["context_resolution"]["dependency_files"] = [str(dependency_map_file)]
    builder = DependencyGraphBuilder(config)
    graph = builder.build(write_to_graph=False)
    analyzer = ImpactAnalyzer(graph)

    notifications = []
    pipeline = ImpactPipeline(
        analyzer=analyzer,
        dependency_graph=graph,
        notifier=lambda report: notifications.append(report.change_id),
        config_context=impact_config_context,
    )

    payload = GitChangePayload(
        identifier="PR-42",
        title="Alpha refactor",
        repo="repo-alpha",
        files=[GitFileChange(path="src/alpha/service.py", repo="repo-alpha")],
    )

    report = pipeline.process_git_event(payload)
    assert report.evidence
    assert notifications == ["PR-42"]

    slack_ctx = SlackComplaintContext(
        thread_id="slack:C1:1700",
        channel="#core",
        component_ids=["comp:alpha"],
        text="Alpha still failing",
    )

    slack_report = pipeline.process_slack_complaint(slack_ctx)
    assert slack_report.slack_threads

