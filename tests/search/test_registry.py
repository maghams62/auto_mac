from pathlib import Path

from src.search.config import load_search_config
from src.search.modalities.base import BaseModalityHandler
from src.search.registry import SearchRegistry


class FakeHandler(BaseModalityHandler):
    def __init__(self, modality_config, *, ingestable=True, queryable=True):
        super().__init__(modality_config)
        self._ingestable = ingestable
        self._queryable = queryable
        self.ingest_calls = 0
        self.query_calls = 0

    def can_ingest(self) -> bool:
        return self._ingestable

    def can_query(self) -> bool:
        return self._queryable

    def ingest(self, *, scope_override=None):
        self.ingest_calls += 1
        return {"status": "ok"}

    def query(self, query_text: str, *, limit=None):
        self.query_calls += 1
        return [{"text": query_text, "limit": limit}]


def _build_config():
    app_cfg = {
        "search": {
            "enabled": True,
            "workspace_id": "acme",
            "modalities": {
                "slack": {"enabled": True},
                "web_search": {"enabled": True, "fallback_only": True},
            },
        }
    }
    return load_search_config(app_cfg)


def test_registry_filters_handlers(tmp_path: Path):
    cfg = _build_config()
    registry = SearchRegistry(cfg, state_path=tmp_path / "state.json")

    slack_handler = FakeHandler(cfg.modalities["slack"])
    web_handler = FakeHandler(cfg.modalities["web_search"])

    registry.register_handler(slack_handler)
    registry.register_handler(web_handler)

    ingestion_handlers = list(registry.iter_ingestion_handlers())
    assert len(ingestion_handlers) == 1
    handler, config, state = ingestion_handlers[0]
    assert handler is slack_handler
    assert config.modality_id == "slack"
    assert state.modality_id == "slack"

    query_handlers = list(registry.iter_query_handlers(include_fallback=False))
    assert len(query_handlers) == 1
    assert query_handlers[0][0] is slack_handler

    fallback_handlers = list(registry.iter_query_handlers(include_fallback=True))
    assert len(fallback_handlers) == 2
    assert fallback_handlers[1][0] is web_handler

    filtered_handlers = list(
        registry.iter_query_handlers(include_fallback=False, modalities=["slack"])
    )
    assert len(filtered_handlers) == 1
    assert filtered_handlers[0][0] is slack_handler


def test_registry_persists_state(tmp_path: Path):
    cfg = _build_config()
    registry = SearchRegistry(cfg, state_path=tmp_path / "state.json")
    slack_handler = FakeHandler(cfg.modalities["slack"])
    registry.register_handler(slack_handler)

    registry.update_state("slack", extra={"chunks": 10})
    assert registry.get_state("slack").extra["chunks"] == 10

    # Reload registry and ensure state was persisted
    registry2 = SearchRegistry(cfg, state_path=tmp_path / "state.json")
    assert registry2.get_state("slack").extra["chunks"] == 10

