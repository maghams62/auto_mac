from types import SimpleNamespace

from src.agent.slash_git_assistant import SlashGitAssistant


class StubRegistry:
    def execute_tool(self, *args, **kwargs):
        return {}


class StubGitMetadataService:
    def __init__(self, known_branches=None):
        self.repo_id = "acme/core-api"
        self._known_branches = known_branches or []

    def list_branches(self, repo_identifier: str, prefix: str = "", limit: int = 10):
        prefix_lower = (prefix or "").lower()
        branches = [
            SimpleNamespace(name=name)
            for name in self._known_branches
            if not prefix_lower or name.lower().startswith(prefix_lower)
        ]
        return branches[:limit]

    def suggest_branches(self, repo_identifier: str, prefix: str = "", limit: int = 5):
        suggestions = ["main", "develop", "release"]
        prefix_lower = (prefix or "").lower()
        matches = [name for name in suggestions if prefix_lower and name.lower().startswith(prefix_lower)]
        if matches:
            return matches[:limit]
        return suggestions[:limit]


def make_assistant(metadata_service):
    config = {
        "github": {
            "repo_owner": "acme",
            "repo_name": "core-api",
        }
    }
    return SlashGitAssistant(
        agent_registry=StubRegistry(),
        session_manager=None,
        config=config,
        metadata_service=metadata_service,
    )


def test_branch_switch_error_contains_suggestions():
    assistant = make_assistant(StubGitMetadataService(known_branches=[]))
    response = assistant._handle_branch_switch("use branch feature-login", session_id=None)
    assert response.get("status") == "error"
    assert "Did you mean" in response.get("message", "")
    assert "`main`" in response["message"]


def test_branch_switch_accepts_known_metadata_branch():
    assistant = make_assistant(StubGitMetadataService(known_branches=["develop"]))
    response = assistant._handle_branch_switch("use branch develop", session_id=None)
    assert response.get("status") == "success"
    assert response.get("data", {}).get("active_branch") == "develop"

