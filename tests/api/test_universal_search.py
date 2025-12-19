import copy
import time
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

import api_server


class StubSearchService:
    def __init__(self, documents):
        self._documents = documents

    def search_and_group(self, query: str):
        return self._documents


class StubImageIndexer:
    def __init__(self, images):
        self._images = images

    def search_images(self, query: str, top_k: int = 5):
        return self._images


@pytest.fixture()
def search_env(monkeypatch, tmp_path):
    folder_a = tmp_path / "project_alpha"
    folder_b = tmp_path / "project_beta"
    folder_a.mkdir()
    folder_b.mkdir()

    doc_results = [
        {
            "file_path": str(folder_a / "alpha-spec.pdf"),
            "file_name": "alpha-spec.pdf",
            "file_type": ".pdf",
            "total_pages": 1,
            "max_similarity": 0.92,
            "chunks": [
                {
                    "full_content": "alpha details",
                    "similarity": 0.92,
                    "page_number": 1,
                    "file_mtime": time.time(),
                }
            ],
        },
        {
            "file_path": str(folder_b / "beta-notes.md"),
            "file_name": "beta-notes.md",
            "file_type": ".md",
            "total_pages": 1,
            "max_similarity": 0.81,
            "chunks": [
                {
                    "full_content": "beta notes",
                    "similarity": 0.81,
                    "page_number": 1,
                    "file_mtime": time.time(),
                }
            ],
        },
    ]

    image_results = [
        {
            "file_path": str(folder_a / "diagram.png"),
            "file_name": "diagram.png",
            "file_type": ".png",
            "similarity_score": 0.77,
            "caption": "Architecture diagram",
            "breadcrumb": "project_alpha/diagram.png",
            "width": 640,
            "height": 480,
        }
    ]

    stub_orchestrator = SimpleNamespace(
        search=StubSearchService(doc_results),
        indexer=SimpleNamespace(image_indexer=StubImageIndexer(image_results)),
    )
    monkeypatch.setattr(api_server, "get_orchestrator", lambda: stub_orchestrator)

    original_config = api_server.config_manager.get_config()
    config_state = {
        "folders": [str(folder_a), str(folder_b)],
        "allowed_paths_only": False,
    }

    def fake_get_config():
        config_copy = copy.deepcopy(original_config)
        documents_cfg = config_copy.setdefault("documents", {})
        documents_cfg["folders"] = config_state["folders"]
        security_cfg = config_copy.setdefault("universal_search", {}).setdefault("security", {})
        security_cfg["allowed_paths_only"] = config_state["allowed_paths_only"]
        return config_copy

    monkeypatch.setattr(api_server.config_manager, "get_config", fake_get_config)

    client = TestClient(api_server.app, raise_server_exceptions=False)
    return {
        "client": client,
        "config_state": config_state,
        "folder_a": str(folder_a),
        "folder_b": str(folder_b),
    }


def test_universal_search_filters_by_folder_and_scope(search_env):
    env = search_env
    env["config_state"]["allowed_paths_only"] = False
    client = env["client"]
    folder_label = Path(env["folder_a"]).name

    resp = client.get(
        "/api/universal-search",
        params={
            "q": "spec",
            "folders": folder_label,
            "scope": "files",
        },
    )
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["count"] == 1
    result = payload["results"][0]
    assert result["folder_label"] == folder_label
    assert result["ingest_scope"] == "files"
    assert "indexed_at" in result and result["indexed_at"]


def test_universal_search_without_filters_returns_all(search_env):
    env = search_env
    env["config_state"]["allowed_paths_only"] = False
    client = env["client"]

    resp = client.get("/api/universal-search", params={"q": "spec"})
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["count"] == 3  # 2 docs + 1 image
    file_names = {result["file_name"] for result in payload["results"]}
    assert {"alpha-spec.pdf", "beta-notes.md", "diagram.png"}.issubset(file_names)


def test_universal_search_respects_allowed_paths_only(search_env):
    env = search_env
    env["config_state"]["folders"] = [env["folder_a"]]  # Only allow project_alpha
    env["config_state"]["allowed_paths_only"] = True
    client = env["client"]

    resp = client.get("/api/universal-search", params={"q": "spec"})
    assert resp.status_code == 200
    payload = resp.json()
    # Only alpha-spec + diagram should remain; beta-notes filtered out
    assert payload["count"] == 2
    file_names = {result["file_name"] for result in payload["results"]}
    assert "alpha-spec.pdf" in file_names
    assert "diagram.png" in file_names
    assert "beta-notes.md" not in file_names

