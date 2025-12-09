import json
from pathlib import Path

import yaml

from src.config_manager import ConfigManager, set_global_config_manager
from src.settings.manager import SettingsManager, set_global_settings_manager
from src.settings.git import resolve_repo_branch


def _write_minimal_config(tmp_path: Path) -> Path:
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    config_payload = {
        "openai": {"api_key": "test", "model": "gpt-4o"},
        "documents": {"folders": [str(docs_dir)], "supported_types": [".md"]},
        "search": {"top_k": 5},
        "github": {"repo_owner": "oqoqo", "repo_name": "atlas", "base_branch": "main"},
        "activity_ingest": {
            "git": {
                "default_branch": "main",
                "repos": [
                    {
                        "owner": "oqoqo",
                        "name": "atlas",
                        "project_id": "atlas",
                    }
                ],
            }
        },
        "impact": {"auto_from_slash": True},
    }
    config_path = tmp_path / "config.yaml"
    with config_path.open("w") as handle:
        yaml.safe_dump(config_payload, handle)
    return config_path


def test_settings_manager_builds_defaults_and_persists_overrides(tmp_path: Path):
    config_path = _write_minimal_config(tmp_path)
    config_manager = ConfigManager(str(config_path))
    set_global_config_manager(config_manager)
    settings_path = tmp_path / "settings.json"
    manager = SettingsManager(config_manager, settings_path=str(settings_path))
    set_global_settings_manager(manager)

    defaults = manager.get_defaults()
    assert defaults["gitMonitor"]["defaultBranch"] == "main"
    assert "api_params" in defaults["sourceOfTruth"]["domains"]

    payload = manager.update_settings(
        {
            "gitMonitor": {
                "projects": {
                    "atlas": [{"repoId": "oqoqo/atlas", "branch": "develop"}],
                }
            }
        }
    )
    assert payload["gitMonitor"]["projects"]["atlas"][0]["branch"] == "develop"
    overrides = json.loads(settings_path.read_text())
    assert overrides["gitMonitor"]["projects"]["atlas"][0]["branch"] == "develop"

    branch = resolve_repo_branch("oqoqo/atlas", project_id="atlas")
    assert branch == "develop"

    set_global_settings_manager(None)
    set_global_config_manager(None)
