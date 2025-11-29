from src.agent.slash_git_assistant import SlashGitAssistant


class DummyRegistry:
    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    def execute_tool(self, tool_name, params, session_id=None):
        self.calls.append((tool_name, params))
        handler = self.responses.get(tool_name)
        if handler is None:
            raise AssertionError(f"No stubbed response for {tool_name}")
        if callable(handler):
            return handler(params)
        return handler


class FakeSessionMemory:
    def __init__(self):
        self.shared_context = {}

    def get_context(self, key, default=None):
        return self.shared_context.get(key, default)

    def set_context(self, key, value):
        self.shared_context[key] = value


class FakeSessionManager:
    def __init__(self):
        self.memory = FakeSessionMemory()

    def get_or_create_session(self, session_id=None, user_id=None):
        return self.memory


def test_branch_switch_sets_context():
    registry = DummyRegistry({
        "list_repository_branches": {"count": 2, "branches": ["main", "develop"], "default_branch": "main"},
    })
    session_manager = FakeSessionManager()
    assistant = SlashGitAssistant(registry, session_manager, {})

    response = assistant.handle("use develop", session_id="abc")

    assert response["status"] == "success"
    assert session_manager.memory.get_context(SlashGitAssistant.CONTEXT_KEY) == "develop"


def test_repo_info_summary_mentions_default_branch():
    registry = DummyRegistry({
        "get_repo_overview": {
            "repo": {
                "full_name": "demo/auto_mac",
                "default_branch": "main",
                "html_url": "https://github.com/demo/auto_mac",
                "owner": "demo",
                "visibility": "public",
                "topics": ["agents"],
                "pushed_at": "2025-01-01T00:00:00Z",
            }
        }
    })
    assistant = SlashGitAssistant(registry, None, {})

    response = assistant.handle("repo info", session_id=None)

    assert response["status"] == "success"
    assert "`main`" in response["message"]
    assert response["data"]["repo"]["full_name"] == "demo/auto_mac"


def test_recent_commits_use_default_branch_when_no_context():
    registry = DummyRegistry({
        "get_repo_overview": {
            "repo": {
                "full_name": "demo/auto_mac",
                "default_branch": "main",
                "html_url": "https://github.com/demo/auto_mac",
                "owner": "demo",
                "visibility": "public",
                "topics": [],
                "pushed_at": "2025-01-01T00:00:00Z",
            }
        },
        "list_branch_commits": {
            "count": 1,
            "branch": "main",
            "commits": [
                {
                    "sha": "abc123def456",
                    "short_sha": "abc123d",
                    "author": "alice",
                    "date": "2025-01-02T12:00:00Z",
                    "message": "Fix VAT rounding",
                    "url": "https://github.com/demo/auto_mac/commit/abc123def456",
                }
            ],
        },
    })
    assistant = SlashGitAssistant(registry, FakeSessionManager(), {})

    response = assistant.handle("last commit", session_id="session-x")

    assert response["status"] == "success"
    assert "`main`" in response["message"]
    assert response["data"]["commits"][0]["short_sha"] == "abc123d"

