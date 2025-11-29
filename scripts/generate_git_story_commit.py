#!/usr/bin/env python3
"""
Generate a themed commit on the slash-git test branch.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
os.chdir(PROJECT_ROOT)
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.utils import load_config
from src.utils.git_story import (
    STORY_FILE_RELATIVE,
    build_story_entry,
    discover_story_branch,
    ensure_story_file_exists,
)


def git(*args: str, capture: bool = False) -> str:
    result = subprocess.run(["git", *args], check=True, capture_output=capture, text=True)
    return result.stdout.strip() if capture else ""


def ensure_clean_worktree() -> None:
    status = git("status", "--porcelain", capture=True)
    if status:
        sys.exit("Working tree has uncommitted changes. Please commit/stash before running the story script.")


def ensure_on_branch(target_branch: str, allow_switch: bool) -> None:
    current = git("rev-parse", "--abbrev-ref", "HEAD", capture=True)
    if current == target_branch:
        return
    if allow_switch:
        git("switch", target_branch)
        return
    sys.exit(
        f"You are on '{current}'. Switch to '{target_branch}' or re-run with --allow-switch to continue."
    )


def append_story_entry(repo_root: Path, entry_line: str) -> None:
    story_path = ensure_story_file_exists(repo_root)
    with story_path.open("a", encoding="utf-8") as handle:
        handle.write(entry_line + "\n")


def commit_story(repo_root: Path, message: str) -> None:
    rel_path = STORY_FILE_RELATIVE.as_posix()
    git("add", rel_path)
    git("commit", "-m", message)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a synthetic slash-git commit.")
    parser.add_argument("--branch", help="Explicit branch to use (otherwise discovered from config).")
    parser.add_argument("--allow-switch", action="store_true", help="Allow auto git switch to the target branch.")
    parser.add_argument("--skip-pull", action="store_true", help="Skip pulling latest changes before committing.")
    parser.add_argument("--skip-push", action="store_true", help="Skip pushing after commit (for dry runs).")
    parser.add_argument("--dry-run", action="store_true", help="Print the generated entry without committing.")
    args = parser.parse_args()

    repo_root = Path(git("rev-parse", "--show-toplevel", capture=True))
    config = load_config()
    github_cfg = config.get("github") or {}
    target_branch = discover_story_branch(
        config,
        repo_owner=github_cfg.get("repo_owner"),
        repo_name=github_cfg.get("repo_name"),
        override=args.branch,
    )

    ensure_clean_worktree()
    ensure_on_branch(target_branch, allow_switch=args.allow_switch)

    if not args.skip_pull:
        git("pull", "--ff-only", "origin", target_branch)

    entry_line, headline = build_story_entry()
    if args.dry_run:
        print(f"[DRY RUN] {entry_line}")
        return

    append_story_entry(repo_root, entry_line)
    commit_story(repo_root, f"chore(story): {headline}")

    if not args.skip_push:
        git("push", "origin", target_branch)

    new_sha = git("rev-parse", "HEAD", capture=True)
    print(f"Created commit {new_sha} on {target_branch}: {headline}")


if __name__ == "__main__":
    main()

