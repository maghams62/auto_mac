from src.agent.slash_git_assistant import SlashGitAssistant
from src.demo.graph_summary import GraphSummary
from src.demo.scenario_classifier import PAYMENTS_SCENARIO
from src.demo.vector_retriever import VectorRetrievalBundle
from src.reasoners import DocDriftAnswer


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
    assistant = SlashGitAssistant(registry, session_manager, {"slash_git": {"doc_drift_reasoner": False}})

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
    assistant = SlashGitAssistant(registry, None, {"slash_git": {"doc_drift_reasoner": False}})

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
    assistant = SlashGitAssistant(registry, FakeSessionManager(), {"slash_git": {"doc_drift_reasoner": False}})

    response = assistant.handle("last commit", session_id="session-x")

    assert response["status"] == "success"
    assert "`main`" in response["message"]
    assert response["data"]["commits"][0]["short_sha"] == "abc123d"


class FakeDocReasoner:
    def __init__(self):
        self.calls = 0

    def answer_question(self, question: str, source: str = "git") -> DocDriftAnswer:
        self.calls += 1
        return DocDriftAnswer(
            question=question,
            scenario=PAYMENTS_SCENARIO,
            summary="Payments doc drift detected.",
            sections={
                "topics": [{"title": "Payments", "insight": "VAT mismatch noted.", "evidence_ids": []}],
                "decisions": [],
                "tasks": [],
                "open_questions": [],
                "references": [],
            },
            impacted={
                "apis": [PAYMENTS_SCENARIO.api],
                "services": ["core-api-service"],
                "components": ["core.payments"],
                "docs": ["docs/payments_api.md"],
            },
            evidence=[{"id": "git-1", "source": "git", "text": "Commit updated VAT handling."}],
            graph_summary=GraphSummary(api=PAYMENTS_SCENARIO.api),
            vector_bundle=VectorRetrievalBundle(),
            doc_drift=[{"doc": "docs/payments_api.md", "issue": "Missing vat_code", "services": ["core-api-service"], "components": ["core.payments"], "apis": [PAYMENTS_SCENARIO.api], "labels": ["doc_drift"]}],
            next_steps=["Patch docs"],
            metadata={"scenario": PAYMENTS_SCENARIO.name},
        )


def test_doc_drift_reasoner_short_circuit():
    registry = DummyRegistry({})
    reasoner = FakeDocReasoner()
    assistant = SlashGitAssistant(registry, None, {"slash_git": {"doc_drift_reasoner": True}}, reasoner=reasoner)

    response = assistant.handle("Why are payments docs drifting?", session_id=None)

    assert response["status"] == "success"
    assert "Payments doc drift detected." in response["message"]
    assert response["data"]["impacted"]["apis"] == [PAYMENTS_SCENARIO.api]
    assert reasoner.calls == 1

