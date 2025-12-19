from pathlib import Path
import json

from src.cache.startup_cache import StartupCacheManager


def test_startup_cache_round_trip(tmp_path):
    config_path = tmp_path / "config.yaml"
    config_path.write_text("openai:\n  model: gpt-4o", encoding="utf-8")

    prompts_dir = tmp_path / "prompts"
    prompts_dir.mkdir()
    (prompts_dir / "system.md").write_text("# system prompt", encoding="utf-8")

    cache_path = tmp_path / "startup_cache.json"
    manager = StartupCacheManager(str(cache_path), [config_path, prompts_dir])

    # Cache miss on cold start
    assert manager.load_section("automation_bootstrap") is None

    payload = {"prompts": {"system": "hello"}, "generated_at": "now"}
    manager.save_section("automation_bootstrap", payload)

    cached = manager.load_section("automation_bootstrap")
    assert cached == payload

    # Fingerprint change invalidates cache
    (prompts_dir / "system.md").write_text("# updated system prompt", encoding="utf-8")
    assert manager.load_section("automation_bootstrap") is None


def test_startup_cache_describe(tmp_path):
    config_path = tmp_path / "config.yaml"
    config_path.write_text("foo: bar", encoding="utf-8")
    prompts_dir = tmp_path / "prompts"
    prompts_dir.mkdir()
    cache_path = tmp_path / "startup_cache.json"

    manager = StartupCacheManager(str(cache_path), [config_path, prompts_dir])
    manager.save_section("automation_bootstrap", {"prompts": {}})

    metadata = manager.describe()
    assert metadata["cache_path"] == str(cache_path)
    assert "automation_bootstrap" in metadata["sections"]
    assert Path(metadata["cache_path"]).exists()
    assert json.loads(Path(metadata["cache_path"]).read_text(encoding="utf-8"))["payload"]["automation_bootstrap"] == {"prompts": {}}

