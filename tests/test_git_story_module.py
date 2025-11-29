from pathlib import Path

from src.utils.git_story import (
    STORY_FILE_RELATIVE,
    build_story_entry,
    discover_story_branch,
    ensure_story_file_exists,
)


def test_build_story_entry_is_deterministic_with_seed():
    entry_a, headline_a = build_story_entry(seed=42)
    entry_b, headline_b = build_story_entry(seed=42)

    assert entry_a == entry_b
    assert headline_a == headline_b
    assert "telemetry" in entry_a or "subsystem" in entry_a


def test_discover_story_branch_prefers_explicit_keys():
    config = {
        "slash_git": {"test_branch": "slash-git-fixtures"},
        "github": {"base_branch": "main"},
    }
    assert discover_story_branch(config) == "slash-git-fixtures"

    config_no_slash = {
        "github": {"test_branch": "github-test", "base_branch": "main"},
    }
    assert discover_story_branch(config_no_slash) == "github-test"


def test_discover_branch_falls_back_to_activity_repo():
    config = {
        "github": {"repo_owner": "maghams62", "repo_name": "auto_mac", "base_branch": "main"},
        "activity_ingest": {
            "git": {
                "repos": [
                    {"owner": "maghams62", "name": "auto_mac", "branch": "slash-git-lab"},
                ]
            }
        },
    }
    branch = discover_story_branch(config)
    assert branch == "slash-git-lab"


def test_ensure_story_file_exists_creates_header(tmp_path: Path):
    repo_root = tmp_path
    story_path = ensure_story_file_exists(repo_root)

    assert story_path.exists()
    contents = story_path.read_text()
    assert "Telemetry Story Log" in contents
    assert story_path.relative_to(repo_root) == STORY_FILE_RELATIVE

