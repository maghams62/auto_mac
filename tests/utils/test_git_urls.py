from __future__ import annotations

import pytest

from src.utils.git_urls import (
    determine_repo_owner_override,
    rewrite_github_url,
    rewrite_repo_slug,
)


@pytest.fixture(autouse=True)
def _clear_repo_owner_env(monkeypatch):
    for key in ("SLASH_GIT_REPO_OWNER", "GITHUB_REPO_OWNER", "GIT_ORG", "LIVE_GIT_ORG"):
        monkeypatch.delenv(key, raising=False)
    yield


def test_determine_repo_owner_override_prefers_config():
    config = {"slash_git": {"repo_owner_override": "custom-owner"}}
    assert determine_repo_owner_override(config) == "custom-owner"


def test_determine_repo_owner_override_falls_back_to_env(monkeypatch):
    monkeypatch.setenv("LIVE_GIT_ORG", "env-owner")
    assert determine_repo_owner_override({}) == "env-owner"


def test_rewrite_github_url_no_override_returns_original():
    url = "https://github.com/acme/core-api/pull/2041"
    assert rewrite_github_url(url) == url


def test_rewrite_github_url_applies_override(monkeypatch):
    monkeypatch.setenv("LIVE_GIT_ORG", "maghams62")
    url = "https://github.com/acme/core-api/pull/2041"
    expected = "https://github.com/maghams62/core-api/pull/2041"
    assert rewrite_github_url(url) == expected


def test_rewrite_repo_slug_applies_override(monkeypatch):
    monkeypatch.setenv("LIVE_GIT_ORG", "maghams62")
    assert rewrite_repo_slug("acme/core-api") == "maghams62/core-api"


def test_rewrite_github_url_ignores_non_github(monkeypatch):
    monkeypatch.setenv("LIVE_GIT_ORG", "maghams62")
    url = "https://example.com/docs/index.html"
    assert rewrite_github_url(url) == url

