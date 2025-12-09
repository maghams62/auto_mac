import textwrap
from pathlib import Path
from typing import Dict

import pytest

from src.config.context import ConfigContext
from src.config_validator import ConfigAccessor


@pytest.fixture
def dependency_map_file(tmp_path: Path) -> Path:
    path = tmp_path / "dependency_map.yaml"
    path.write_text(
        textwrap.dedent(
            """
            components:
              - id: comp:alpha
                repo: repo-alpha
                artifacts:
                  - id: code:alpha:service
                    repo: repo-alpha
                    path: src/alpha/service.py
                    depends_on:
                      - code:beta:client
                endpoints:
                  - id: api:alpha:/foo
                    method: GET
                    path: /foo
                docs:
                  - id: doc:alpha-guide
                    title: Alpha Guide
                    url: /docs/alpha
                    api_ids:
                      - api:alpha:/foo
                    repo: repo-alpha
                    path: docs/alpha.md

              - id: comp:beta
                repo: repo-beta
                artifacts:
                  - id: code:beta:client
                    repo: repo-beta
                    path: src/beta/client.py
                docs:
                  - id: doc:beta-guide
                    title: Beta Guide
                    url: /docs/beta
                    repo: repo-beta
                    path: docs/beta.md

            dependencies:
              - from_component: comp:alpha
                to_component: comp:beta
                reason: "Alpha calls Beta"
            """
        ).strip()
    )
    return path


def _base_config(tmp_path: Path) -> Dict[str, object]:
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    return {
        "openai": {
            "api_key": "test-key",
            "model": "gpt-4o",
            "embedding_model": "text-embedding-3-small",
            "temperature": 0.2,
            "max_tokens": 512,
        },
        "documents": {
            "folders": [str(docs_dir)],
            "supported_types": [".md"],
        },
        "search": {"top_k": 5},
        "context_resolution": {
            "dependency_files": [],
            "repo_mode": "polyrepo",
            "activity_window_hours": 24,
            "impact": {
                "default_max_depth": 2,
                "include_docs": True,
                "include_services": True,
                "include_components": True,
                "include_slack_threads": True,
                "max_recommendations": 3,
                "evidence": {
                    "llm_enabled": False,
                    "llm_model": None,
                    "max_bullets": 4,
                },
                "pipeline": {
                    "slack_lookup_hours": 24,
                    "git_lookup_hours": 168,
                    "notify_slack": False,
                },
                "notifications": {
                    "enabled": False,
                    "slack_channel": None,
                    "github_app_id": None,
                    "min_impact_level": "high",
                },
            },
        },
    }


@pytest.fixture
def impact_test_config(tmp_path: Path) -> Dict[str, object]:
    return _base_config(tmp_path)


@pytest.fixture
def impact_config_context(impact_test_config: Dict[str, object]) -> ConfigContext:
    accessor = ConfigAccessor(impact_test_config)
    return ConfigContext(data=impact_test_config, accessor=accessor)

