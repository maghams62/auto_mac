from types import SimpleNamespace

from src.orchestrator.slash_slack.llm_formatter import SlashSlackLLMFormatter


class StubPromptBundle:
    def __init__(self):
        self.system_prompt = ""
        self.examples_block = ""


def test_graph_highlights_collects_services_components_and_topics():
    formatter = SlashSlackLLMFormatter(
        config={},
        llm_client=SimpleNamespace(),  # Prevent real LLM calls
        prompt_bundle=StubPromptBundle(),
    )
    query = {"mode": "channel_recap", "raw": "/slack recap", "time_range": {"start": None, "end": None}}
    context = {
        "channel_id": "C123",
        "channel_name": "incidents",
        "channel_label": "#incidents",
        "time_window_label": "last 4h",
    }
    sections = {"topics": [], "decisions": [], "tasks": [], "open_questions": [], "references": []}
    messages = [
        {
            "ts": "1",
            "user_name": "alice",
            "user_id": "U1",
            "text": "Pager triggered for vat_code rollout.",
            "permalink": "https://slack/1",
            "service_ids": ["core-api-service"],
            "component_ids": ["core.payments"],
            "related_apis": ["/v1/payments/create"],
            "labels": ["incident"],
        },
        {
            "ts": "2",
            "user_name": "bob",
            "user_id": "U2",
            "text": "Checkout taking ownership.",
            "permalink": "https://slack/2",
            "service_ids": ["checkout-service"],
            "component_ids": ["billing.checkout"],
            "related_apis": ["/v1/payments/create"],
            "labels": ["handoff"],
        },
    ]
    graph = {
        "nodes": [
            {"id": "topic-1", "type": "Topic", "props": {"name": "checkout 500s", "sample": "EU users hit 500s", "mentions": 2}},
            {"id": "decision-1", "type": "Decision", "props": {}},
            {"id": "task-1", "type": "Task", "props": {}},
        ],
        "edges": [],
    }

    payload = formatter._build_prompt_payload(
        query=query,
        context=context,
        sections=sections,
        messages=messages,
        graph=graph,
    )

    highlights = payload["graph_highlights"]
    assert highlights["services"] == ["checkout-service", "core-api-service"]
    assert highlights["components"] == ["billing.checkout", "core.payments"]
    assert highlights["apis"] == ["/v1/payments/create"]
    assert highlights["decision_count"] == 1
    assert highlights["task_count"] == 1
    topic_names = [topic["topic"] for topic in highlights["topic_samples"]]
    assert "checkout 500s" in topic_names
    participant_counts = {entry["user"]: entry["messages"] for entry in highlights["top_participants"]}
    assert participant_counts["alice"] == 1
    assert participant_counts["bob"] == 1

