from src.graph.dependency_graph import DependencyGraphBuilder


def test_dependency_graph_resolves_components(tmp_path, impact_test_config, dependency_map_file):
    impact_test_config["context_resolution"]["dependency_files"] = [str(dependency_map_file)]

    builder = DependencyGraphBuilder(impact_test_config)
    graph = builder.build(write_to_graph=False)

    assert "comp:alpha" in graph.components
    assert "doc:alpha-guide" in graph.docs
    assert graph.components_for_file("repo-alpha", "src/alpha/service.py") == {"comp:alpha"}
    assert graph.component_dependencies["comp:alpha"] == {"comp:beta"}

