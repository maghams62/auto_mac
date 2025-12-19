from pathlib import Path
from typing import Dict, List, Optional

from src.commands.cerebros_command import CerebrosCommand
from src.commands.index_command import IndexCommand
from src.commands.setup_command import SetupCommand
from src.graph.schema import GraphComponentSummary
from src.search import load_search_config, SearchRegistry
from src.search.modalities.base import BaseModalityHandler
from src.search.query_trace import QueryTraceStore
from src.services.hashtag_resolver import ResolvedTarget
from src.services.slash_query_plan import SlashQueryIntent, SlashQueryPlan


def _base_config(extra_modalities: Optional[Dict[str, Dict]] = None) -> Dict:
    modalities = {
        "slack": {"enabled": True, "max_results": 3},
    }
    if extra_modalities:
        modalities.update(extra_modalities)
    return {
        "search": {
            "enabled": True,
            "workspace_id": "test",
            "modalities": modalities,
        }
    }


class FakeHandler(BaseModalityHandler):
    def __init__(self, modality_config, *, ingestable=True, results: Optional[List[Dict]] = None):
        super().__init__(modality_config)
        self.ingestable = ingestable
        self.ingest_calls = 0
        self.query_calls = 0
        self.results = results or [
            {
                "modality": modality_config.modality_id,
                "source_type": modality_config.modality_id,
                "chunk_id": f"{modality_config.modality_id}-chunk",
                "entity_id": f"{modality_config.modality_id}:entity",
                "title": "result",
                "text": "result text",
                "score": 0.9,
                "url": None,
            }
        ]

    def can_ingest(self) -> bool:
        return self.ingestable

    def ingest(self, *, scope_override=None):
        self.ingest_calls += 1
        return {"ingested": 5 * self.ingest_calls}

    def query(self, query_text: str, *, limit: int | None = None):
        self.query_calls += 1
        results = list(self.results)
        for item in results:
            item["title"] = query_text
        return results


def _build_registry(tmp_path: Path, config: Optional[Dict] = None) -> tuple[SearchRegistry, Dict[str, FakeHandler]]:
    config_obj = load_search_config(config or _base_config())
    registry = SearchRegistry(config_obj, state_path=tmp_path / "search_state.json")
    handlers: Dict[str, FakeHandler] = {}
    for modality_id, modality_cfg in config_obj.modalities.items():
        handler = FakeHandler(modality_cfg)
        registry.register_handler(handler)
        handlers[modality_id] = handler
    return registry, handlers


def test_setup_command_reports_modalities(tmp_path: Path):
    registry, _ = _build_registry(tmp_path)
    cmd = SetupCommand(registry.config, registry)
    payload = cmd.run()
    assert payload["status"] == "success"
    modalities = payload["data"]["modalities"]
    assert modalities[0]["modality"] == "slack"
    assert modalities[0]["needs_reindex"] is False


def test_setup_command_warns_on_config_hash_mismatch(tmp_path: Path):
    registry, _ = _build_registry(tmp_path)
    slack_state = registry.get_state("slack")
    slack_state.config_hash = "old-hash"
    registry._state["slack"] = slack_state
    cmd = SetupCommand(registry.config, registry)
    payload = cmd.run()
    modality_entry = payload["data"]["modalities"][0]
    assert modality_entry["needs_reindex"] is True
    assert "Needs re-index" in payload["message"]


def test_index_command_runs_requested_modality(tmp_path: Path):
    registry, handlers = _build_registry(tmp_path)
    cmd = IndexCommand(registry)
    payload = cmd.run("slack")
    assert handlers["slack"].ingest_calls == 1
    assert payload["data"]["slack"]["status"] == "success"
    assert registry.get_state("slack").last_indexed_at is not None


def test_index_command_updates_multiple_modalities_and_registry(tmp_path: Path):
    config = _base_config({"files": {"enabled": True}})
    registry, handlers = _build_registry(tmp_path, config)
    cmd = IndexCommand(registry)
    payload = cmd.run("")
    assert handlers["slack"].ingest_calls == 1
    assert handlers["files"].ingest_calls == 1
    assert payload["data"]["slack"]["status"] == "success"
    assert payload["data"]["files"]["status"] == "success"
    assert registry.get_state("slack").last_indexed_at is not None
    assert registry.get_state("files").last_indexed_at is not None


def test_cerebros_command_returns_ranked_matches(tmp_path: Path):
    registry, handlers = _build_registry(tmp_path)
    trace_store = QueryTraceStore(tmp_path / "traces.jsonl")
    cmd = CerebrosCommand(registry, trace_store=trace_store)
    payload = cmd.search("latest status")
    assert handlers["slack"].query_calls == 1
    assert payload["status"] == "success"
    assert payload["data"]["results"]
    trace = trace_store.get(payload["data"]["query_id"])
    assert trace is not None
    assert trace.question == "latest status"
    assert "slack" in trace.modalities_used
    assert trace.retrieved_chunks


def test_cerebros_planner_limits_modalities(tmp_path: Path):
    cfg = _base_config({"git": {"enabled": True}})
    registry, handlers = _build_registry(tmp_path, cfg)
    trace_store = QueryTraceStore(tmp_path / "traces.jsonl")
    cmd = CerebrosCommand(registry, trace_store=trace_store)
    cmd.search("Stack trace failing in production")
    assert handlers["git"].query_calls == 1
    assert handlers["slack"].query_calls == 0


def test_cerebros_web_not_called_when_internal_hits(tmp_path: Path):
    cfg = _base_config({"web_search": {"enabled": True, "fallback_only": True}})
    registry, handlers = _build_registry(tmp_path, cfg)
    trace_store = QueryTraceStore(tmp_path / "traces.jsonl")
    cmd = CerebrosCommand(registry, trace_store=trace_store)
    cmd.search("Where did we mention onboarding?")
    assert handlers["slack"].query_calls == 1
    assert handlers["web_search"].query_calls == 0


def test_cerebros_web_fallback_only_runs_on_empty_results(tmp_path: Path):
    cfg = {
        "search": {
            "enabled": True,
            "workspace_id": "test",
            "modalities": {
                "slack": {"enabled": True},
                "web_search": {"enabled": True, "fallback_only": True},
            },
        }
    }
    registry, handlers = _build_registry(tmp_path, cfg)
    handlers["slack"].results = []
    trace_store = QueryTraceStore(tmp_path / "traces.jsonl")
    cmd = CerebrosCommand(registry, trace_store=trace_store)
    cmd.search("General question with no hits")
    assert handlers["slack"].query_calls == 1
    assert handlers["web_search"].query_calls == 1


def test_cerebros_plan_adds_graph_context(tmp_path: Path):
    class StubGraphService:
        def is_available(self) -> bool:
            return True

        def get_component_neighborhood(self, component_id: str) -> GraphComponentSummary:
            return GraphComponentSummary(
                component_id=component_id,
                docs=["doc:sample"],
                issues=["issue:sample"],
                pull_requests=["pr:sample"],
                slack_threads=["slack_thread:sample"],
                api_endpoints=["api:/v1/sample"],
            )

    registry, handlers = _build_registry(tmp_path)
    trace_store = QueryTraceStore(tmp_path / "traces.jsonl")
    cmd = CerebrosCommand(registry, trace_store=trace_store, graph_service=StubGraphService())

    plan = SlashQueryPlan(
        raw="status core api",
        command="cerebros",
        intent=SlashQueryIntent.INVESTIGATE,
        targets=[ResolvedTarget(raw="#comp:core-api", target_type="component", identifier="comp:core-api")],
        hashtags=["comp:core-api"],
        keywords=["core", "api"],
    )

    payload = cmd.search("status update", plan=plan)
    assert handlers["slack"].query_calls == 1
    graph_context = payload["data"]["graph_context"]
    assert graph_context["components"][0]["component_id"] == "comp:core-api"
    assert graph_context["highlight_node_ids"]

