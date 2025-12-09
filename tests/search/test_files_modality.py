from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

import pytest

from src.search.config import load_search_config
from src.search.modalities.files import FilesModalityHandler


class FakeVectorService:
    def __init__(self):
        self.indexed: List[Any] = []

    def index_chunks(self, chunks):
        self.indexed.extend(chunks)
        return True


class StubGraphService:
    def __init__(self, *args, **kwargs):
        self.writes: List[Dict[str, Any]] = []

    def is_available(self) -> bool:
        return True

    def run_write(self, query, params=None):
        self.writes.append({"query": query, "params": params})


def _build_config(root: Path) -> Dict[str, Any]:
    return {
        "search": {
            "enabled": True,
            "workspace_id": "test-workspace",
            "modalities": {
                "files": {
                    "enabled": True,
                    "roots": [str(root)],
                }
            },
        }
    }


def test_files_ingest_indexes_vector_and_graph(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    docs_root = tmp_path / "docs"
    docs_root.mkdir()
    (docs_root / "sample.md").write_text("# Title\n\nContent about Cerebros universal graph.", encoding="utf-8")

    app_config = _build_config(docs_root)
    cfg = load_search_config(app_config)

    stub_graph = StubGraphService()
    monkeypatch.setattr("src.search.modalities.files.GraphService", lambda *_args, **_kwargs: stub_graph)

    vector_service = FakeVectorService()
    handler = FilesModalityHandler(cfg.modalities["files"], app_config, vector_service=vector_service)

    result = handler.ingest()

    assert result["files_indexed"] > 0
    assert vector_service.indexed, "Expected chunks to be indexed in vector service"
    assert stub_graph.writes, "Expected graph writes for file chunks"

