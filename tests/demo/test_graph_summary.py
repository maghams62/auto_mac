from pathlib import Path

from src.demo.graph_summary import GraphNeighborhoodSummarizer
from src.demo.scenario_classifier import PAYMENTS_SCENARIO
from tests.demo.test_vector_retriever import FakeEmbeddingProvider, _build_indexes


def test_graph_summary_falls_back_to_local_indexes(tmp_path):
    provider = FakeEmbeddingProvider()
    config, store_paths = _build_indexes(tmp_path, provider)
    summarizer = GraphNeighborhoodSummarizer(config, store_paths=store_paths)
    summary = summarizer.summarize(PAYMENTS_SCENARIO, max_events=2)

    assert summary.api == "/v1/payments/create"
    assert "core-api-service" in summary.services
    assert summary.git_events
    assert summary.slack_events

