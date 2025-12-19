from __future__ import annotations

from typing import Any, Dict

import pytest

import scripts.verify_vectordb as verifier


class StubResponse:
    def __init__(self, status_code: int = 200, payload: Dict[str, Any] | None = None):
        self.status_code = status_code
        self._payload = payload or {}

    def json(self) -> Dict[str, Any]:
        return self._payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class StubClient:
    def __init__(self, fail_put: bool = False):
        self.calls = []
        self.fail_put = fail_put
        self.base_url = "http://stub"

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()

    def get(self, path: str):
        self.calls.append(("get", path))
        return StubResponse(200, {"result": {"collections": []}})

    def put(self, path: str, json: Dict[str, Any] | None = None):
        self.calls.append(("put", path, json))
        if self.fail_put:
            raise RuntimeError("boom")
        return StubResponse(200, {"result": {}})

    def delete(self, path: str, params: Dict[str, Any] | None = None):
        self.calls.append(("delete", path, params))
        return StubResponse(200, {"result": {}})

    def close(self):
        self.calls.append(("close",))


def _mock_config():
    return {
        "collection": "test",
        "dimension": 4,
        "url": "http://localhost:6333",
        "api_key": "",
        "timeout_seconds": 1,
    }


def test_verify_vectordb_skip_mutation(monkeypatch):
    stub = StubClient()
    monkeypatch.setattr(verifier, "get_config", lambda: {})
    monkeypatch.setattr(verifier, "validate_vectordb_config", lambda cfg: _mock_config())
    monkeypatch.setattr(verifier, "_build_http_client", lambda config: stub)

    exit_code = verifier.verify_vectordb(skip_mutation=True)

    assert exit_code == 0
    assert ("get", "/collections") in stub.calls
    assert not any(call[0] == "put" for call in stub.calls)


def test_verify_vectordb_handles_write_failure(monkeypatch):
    stub = StubClient(fail_put=True)
    monkeypatch.setattr(verifier, "get_config", lambda: {})
    monkeypatch.setattr(verifier, "validate_vectordb_config", lambda cfg: _mock_config())
    monkeypatch.setattr(verifier, "_build_http_client", lambda config: stub)

    exit_code = verifier.verify_vectordb(skip_mutation=False)

    assert exit_code == 4
    assert any(call[0] == "put" for call in stub.calls)

