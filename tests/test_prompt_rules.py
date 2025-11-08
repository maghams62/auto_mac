from pathlib import Path


def _project_path(*parts) -> Path:
    return Path(__file__).resolve().parents[1].joinpath(*parts)


def test_task_decomposition_enforces_browser_research():
    text = _project_path("prompts", "task_decomposition.md").read_text()
    assert "Mandatory Browser Research" in text
    assert "Latest News Harvest" in text or "latest news" in text.lower()


def test_few_shot_examples_include_ticker_rule():
    text = _project_path("prompts", "few_shot_examples.md").read_text()
    assert "Ticker Discovery Rule" in text
    assert "Bosch Stock Update" in text
