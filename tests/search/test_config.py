from src.search.config import load_search_config


def test_load_search_config_defaults():
    cfg = load_search_config({})
    assert cfg.enabled is False
    assert cfg.workspace_id == "default_workspace"
    assert cfg.defaults.max_results_per_modality == 5
    assert cfg.defaults.timeout_ms_per_modality == 2000
    assert cfg.defaults.web_fallback_weight == 0.6
    assert cfg.modalities == {}


def test_load_search_config_modalities():
    app_cfg = {
        "search": {
            "enabled": True,
            "workspace_id": "acme",
            "defaults": {
                "max_results_per_modality": 4,
                "timeout_ms_per_modality": 1500,
                "web_fallback_weight": 0.4,
            },
            "modalities": {
                "slack": {
                    "enabled": True,
                    "channels": ["#incidents"],
                    "weight": 1.2,
                    "timeout_ms": 1800,
                    "max_results": 6,
                },
                "web_search": {
                    "enabled": True,
                    "fallback_only": True,
                },
            },
        }
    }

    cfg = load_search_config(app_cfg)
    assert cfg.enabled is True
    assert cfg.workspace_id == "acme"
    assert cfg.defaults.max_results_per_modality == 4
    assert "slack" in cfg.modalities
    slack = cfg.modalities["slack"]
    assert slack.enabled is True
    assert slack.scope["channels"] == ["#incidents"]
    assert slack.weight == 1.2
    assert slack.timeout_ms == 1800
    assert slack.max_results == 6

    web = cfg.modalities["web_search"]
    assert web.fallback_only is True
    assert web.is_queryable() is False

    enabled = cfg.enabled_modalities(include_fallback=False)
    assert set(enabled.keys()) == {"slack"}

