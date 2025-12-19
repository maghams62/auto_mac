import pytest

from src.config_validator import ConfigAccessor, ConfigValidationError


def build_base_config(tmp_path):
    folder = tmp_path / "docs"
    folder.mkdir(exist_ok=True)
    return {
        "openai": {
            "api_key": "test",
            "model": "gpt-4o",
            "embedding_model": "text-embedding-3-small",
            "temperature": 0.1,
            "max_tokens": 1000,
        },
        "documents": {
            "folders": [str(folder)],
            "supported_types": [".txt"],
        },
        "search": {},
        "metadata_cache": {
            "slack": {"ttl_seconds": 600, "max_items": 100, "log_metrics": False},
            "git": {
                "repo_ttl_seconds": 900,
                "branch_ttl_seconds": 300,
                "max_branches_per_repo": 500,
                "log_metrics": False,
            },
        },
    }


def test_slack_ttl_must_be_positive(tmp_path):
    config = build_base_config(tmp_path)
    config["metadata_cache"]["slack"]["ttl_seconds"] = 0
    with pytest.raises(ConfigValidationError):
        ConfigAccessor(config)


def test_slack_max_items_must_be_positive(tmp_path):
    config = build_base_config(tmp_path)
    config["metadata_cache"]["slack"]["max_items"] = -5
    with pytest.raises(ConfigValidationError):
        ConfigAccessor(config)


def test_slack_log_metrics_must_be_bool(tmp_path):
    config = build_base_config(tmp_path)
    config["metadata_cache"]["slack"]["log_metrics"] = "yes"
    with pytest.raises(ConfigValidationError):
        ConfigAccessor(config)


def test_git_ttls_and_limits(tmp_path):
    config = build_base_config(tmp_path)
    config["metadata_cache"]["git"]["repo_ttl_seconds"] = -1
    with pytest.raises(ConfigValidationError):
        ConfigAccessor(config)

    config = build_base_config(tmp_path)
    config["metadata_cache"]["git"]["branch_ttl_seconds"] = 0
    with pytest.raises(ConfigValidationError):
        ConfigAccessor(config)

    config = build_base_config(tmp_path)
    config["metadata_cache"]["git"]["max_branches_per_repo"] = 0
    with pytest.raises(ConfigValidationError):
        ConfigAccessor(config)


def test_git_log_metrics_bool(tmp_path):
    config = build_base_config(tmp_path)
    config["metadata_cache"]["git"]["log_metrics"] = "nope"
    with pytest.raises(ConfigValidationError):
        ConfigAccessor(config)


def test_valid_metadata_cache_passes(tmp_path):
    config = build_base_config(tmp_path)
    try:
        ConfigAccessor(config)
    except ConfigValidationError as exc:
        pytest.fail(f"Config should be valid but raised: {exc}")

