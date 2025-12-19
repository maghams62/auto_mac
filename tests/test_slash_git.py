from datetime import datetime, timedelta, timezone

from src.agent.slash_git_assistant import SlashGitAssistant
from src.demo.graph_summary import GraphSummary
from src.demo.scenario_classifier import PAYMENTS_SCENARIO
from src.demo.vector_retriever import VectorRetrievalBundle
from src.reasoners import DocDriftAnswer
from src.slash_git.models import GitQueryMode, GitQueryPlan, GitTargetRepo, TimeWindow
from src.slash_git.pipeline import SlashGitPipeline


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


class FakeGitFormatter:
    def __init__(self):
        self.calls = 0

    def generate(self, plan, snapshot, graph=None):
        self.calls += 1
        payload = {
            "summary": "synthetic summary",
            "sections": [],
            "notable_prs": [],
            "breaking_changes": [],
            "next_actions": [],
            "references": [],
            "debug_metadata": {"repo_id": plan.repo_id, "component_id": plan.component_id, "time_window": plan.time_window.label if plan.time_window else None, "evidence_counts": {"commits": len(snapshot.get('commits', [])), "prs": len(snapshot.get('prs', [])), "issues": len(snapshot.get('issues', []))}},
        }
        return payload, None


def build_assistant(registry, session_manager=None, config=None, **kwargs):
    cfg = config or {"slash_git": {"doc_drift_reasoner": False, "graph_emit_enabled": False}}
    formatter = kwargs.pop("git_formatter", FakeGitFormatter())
    return SlashGitAssistant(
        registry,
        session_manager,
        cfg,
        git_formatter=formatter,
        **kwargs,
    )


def test_branch_switch_sets_context():
    registry = DummyRegistry({
        "list_repository_branches": {"count": 2, "branches": ["main", "develop"], "default_branch": "main"},
    })
    session_manager = FakeSessionManager()
    assistant = build_assistant(registry, session_manager)

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
    assistant = build_assistant(registry, None)

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
    assistant = build_assistant(registry, FakeSessionManager())

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
            sources=[
                {
                    "id": "git-1",
                    "type": "git",
                    "label": "Commit git-1",
                    "url": "https://github.com/acme/core-api/commit/git-1",
                }
            ],
        )


PIPELINE_CONFIG = {
    "slash_git": {
        "doc_drift_reasoner": False,
        "graph_emit_enabled": False,
        "target_catalog_path": "config/slash_git_targets.yaml",
        "default_repo_id": "core-api",
    }
}


def test_pipeline_component_activity_snapshot():
    registry = DummyRegistry({})
    formatter = FakeGitFormatter()
    assistant = SlashGitAssistant(registry, None, PIPELINE_CONFIG, git_formatter=formatter)

    response = assistant.handle("what changed in core api last 7 days?", session_id=None)

    assert response["status"] == "success"
    plan = response["data"]["plan"]
    snapshot = response["data"]["snapshot"]
    assert plan["repo_id"] == "core-api"
    assert isinstance(snapshot["commits"], list)
    assert snapshot["commits"]
    assert "analysis" in response["data"]
    assert formatter.calls == 1


def test_doc_drift_reasoner_short_circuit():
    registry = DummyRegistry({})
    reasoner = FakeDocReasoner()
    assistant = SlashGitAssistant(
        registry,
        None,
        {"slash_git": {"doc_drift_reasoner": True}},
        reasoner=reasoner,
        git_formatter=FakeGitFormatter(),
    )

    response = assistant.handle("Why are payments docs drifting?", session_id=None)

    assert response["status"] == "success"
    assert "Payments doc drift detected." in response["message"]
    assert response["data"]["impacted"]["apis"] == [PAYMENTS_SCENARIO.api]
    assert response["sources"][0]["url"].startswith("https://github.com")
    assert reasoner.calls == 1


def test_pipeline_extends_time_window_when_default_window_has_no_activity():
    repo = GitTargetRepo(
        id="core-api",
        name="Core API",
        repo_owner="acme",
        repo_name="core-api",
        default_branch="main",
    )
    default_window = TimeWindow(
        start=datetime.now(timezone.utc) - timedelta(days=7),
        end=datetime.now(timezone.utc),
        label="last 7 days",
        source="default",
    )
    base_plan = GitQueryPlan(mode=GitQueryMode.REPO_ACTIVITY, repo=repo, time_window=default_window)

    class StubPlanner:
        def plan(self, command: str):
            return base_plan

    class StubExecutor:
        def __init__(self):
            self.calls = []

        def run(self, plan):
            self.calls.append(plan)
            if len(self.calls) == 1:
                return {"commits": [], "prs": [], "issues": []}
            return {"commits": [{"sha": "abc123"}], "prs": [], "issues": []}

    class StubGraphLogger:
        def __init__(self):
            self.emits = []

        def emit(self, plan, snapshot):
            self.emits.append((plan, snapshot))

    pipeline = SlashGitPipeline(PIPELINE_CONFIG)
    pipeline.planner = StubPlanner()
    pipeline.executor = StubExecutor()
    pipeline.graph_logger = StubGraphLogger()

    result = pipeline.run("what changed in billing checkout?")

    assert result is not None
    # Executor should be invoked twice (initial + fallback run).
    assert len(pipeline.executor.calls) == 2
    # Fallback plan uses the auto-extended window and produces activity.
    assert result.plan.time_window.source == "fallback_recent"
    assert result.snapshot["commits"]
    # Graph logger should record the fallback plan as well.
    assert pipeline.graph_logger.emits
    logged_plan, logged_snapshot = pipeline.graph_logger.emits[0]
    assert logged_plan.time_window.source == "fallback_recent"
    assert logged_snapshot["commits"]

