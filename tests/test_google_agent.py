import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.agent.google_agent import google_search


class DummyResponse:
    def __init__(self, text: str, status_code: int = 200):
        self.text = text
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise Exception("HTTP error")


@pytest.fixture(autouse=True)
def openai_stub(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")


def test_google_search_fallback_and_summary(monkeypatch):
    config = {"openai": {"model": "gpt-4o"}}
    monkeypatch.setattr("src.agent.google_agent.load_config", lambda: config)

    # Primary googlesearch returns no results
    monkeypatch.setattr("src.agent.google_agent._run_primary_search", lambda *args, **kwargs: [])

    html = """
    <html><body>
      <div class="g">
        <a href="https://example.com/article1">Link</a>
        <h3>Top Trend One</h3>
        <div class="VwiC3b"><span>Preview snippet one.</span></div>
      </div>
      <div class="g">
        <a href="https://example.com/article2">Link</a>
        <h3>Top Trend Two</h3>
        <div class="VwiC3b"><span>Preview snippet two.</span></div>
      </div>
    </body></html>
    """

    def fake_requests_get(url, *args, **kwargs):
        if "google.com/search" in url:
            return DummyResponse(html)
        return DummyResponse("<html><body>Long form article content about trends.</body></html>")

    monkeypatch.setattr("src.agent.google_agent.requests.get", fake_requests_get)

    class DummyLLM:
        def __init__(self, *args, **kwargs):
            pass

        def invoke(self, messages):
            return SimpleNamespace(content="• Trend one is rising\n• Trend two is notable")

    monkeypatch.setattr("src.agent.google_agent.ChatOpenAI", DummyLLM)

    result = google_search.invoke({"query": "what's trending", "num_results": 5})

    assert result["total_results"] == 2
    assert "Trend" in result["results"][0]["title"]
    assert "summary" in result
    assert "Trend one" in result["summary"]
    assert result["message"] == result["summary"]
