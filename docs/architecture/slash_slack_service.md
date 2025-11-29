# Slash-Slack Service Architecture

## Goals
- Keep `/slack` logic modular and **separate from Cerebros core orchestration**, so new tooling can evolve independently.
- Provide a dedicated **tooling adapter** for Slack APIs (channels, threads, search) that is strictly read-only.
- Establish a **hierarchy of orchestrators**:
  1. Global Slash Command Router (existing)
  2. Slash-Slack Orchestrator (new)
  3. Query Executors (channel recap, thread recap, decision extraction, task extraction, entity/time lenses)
- Produce **graph-aware outputs** (nodes + edges) alongside human-readable summaries so Neo4j ingestion is straightforward.

> **UI note**: The shared slash command palette now surfaces `/git` with the Git emoji (🐙) so validation flows can quickly jump into the graph-aware slash-git assistant alongside `/slack`.

## Layering

```
Slash Command Router (/slack … input)
        │
        ▼
Slash-Slack Orchestrator
        │
        ├─ ChannelRecapExecutor
        ├─ ThreadRecapExecutor
        ├─ DecisionExtractor
        ├─ TaskExtractor
        └─ TopicSearchExecutor
        │
        ▼
SlackToolingAdapter (read-only wrappers)
        │
        ▼
Slack API (remote)
```

### SlashToolingAdapter
- Lives at `src/integrations/slash_slack_tooling.py`.
- Provides high-level primitives:
  - `fetch_channel_messages(channel_id, start_ts=None, end_ts=None, limit=500)`
  - `fetch_thread(channel_id, thread_ts)`
  - `search_messages(query, channel=None, start_ts=None, end_ts=None, limit=200)`
- Handles pagination, rate-limit retries, and consistent normalization (user handles, timestamps, permalinks).
- Emits telemetry (duration, result count, errors) so orchestrators can trace performance.

### Slash-Slack Orchestrator
- Entry point for `/slack …` commands; exposed as `SlashSlackOrchestrator.handle(request)`.
- Responsibilities:
  - Parse command arguments (channel, thread link, timeframe, keywords).
  - Choose the proper executor and pass normalized parameters.
  - Merge executor outputs into a single payload:
    - `summary` (1–2 paragraphs).
    - `sections` (Topics, Decisions, Open Questions, Tasks, References).
    - `graph_payload` (nodes + edges defined below).
  - Surface errors (empty results, permission failures) with actionable messaging.

### Executors
Each executor implements `execute(params: SlashSlackQuery) -> SlashSlackResult`.

| Executor | Key Inputs | Source Tools | Node Types | Notes |
|----------|------------|--------------|------------|-------|
| ChannelRecapExecutor | channel_id, timeframe, keywords | `fetch_channel_messages` | Conversation, Topic, Decision, Task | Clusters contiguous message windows, bias toward code/product themes. |
| ThreadRecapExecutor | channel_id, thread_ts | `fetch_thread` | Conversation, Decision, Task, Reference | Preserves original question + replies metadata. |
| DecisionExtractor | keywords, channel/time filters | `search_messages`, `fetch_thread` | Decision, Topic, Participant | Flags confidence (explicit vs inferred). |
| TaskExtractor | channel/thread/time filters | same | Task, Participant | Detects TODO phrasing, owner heuristics, due text. |
| TopicSearchExecutor | entity keyword | `search_messages` | Topic, Conversation, Reference | Groups by thread/channel, highlights controversies. |

Executors should **never** call Cerebros core tools (files, git, doc retrievers); they only compose Slack data.

## Graph Payload Schema

```
nodes: [
  {id, type: "Conversation", props:{channel_id, thread_ts, title, timeframe}},
  {id, type: "Topic", props:{name, category}},
  {id, type: "Decision", props:{text, rationale, confidence, timestamp}},
  {id, type: "Task", props:{description, assignee, due_hint}},
  {id, type: "Reference", props:{kind, url, label}},
  {id, type: "Participant", props:{user_id, display_name}}
]
edges: [
  {from: Conversation, to: Topic, type: "DISCUSS"},
  {from: Topic, to: Decision, type: "RESULTED_IN"},
  {from: Topic, to: Task, type: "NEXT_STEP"},
  {from: Participant, to: Decision, type: "PROPOSED_BY"},
  {from: Participant, to: Task, type: "ASSIGNED_TO"},
  {from: Decision, to:Reference, type: "EVIDENCED_BY"},
  {from: Conversation, to:Reference, type: "MENTIONS"}
]
```

- IDs should be stable hashes (e.g., `slug(channel_id + thread_ts)`).
- Orchestrator emits `{ "summary": "...", "sections": {...}, "graph": { "nodes": [...], "edges": [...] } }`.
- Graph payload is forwarded to the graph ingestion service (when enabled) or ignored otherwise.

### Persistence Hooks
- When `slash_slack.graph_emit` is true, every summary also appends a JSON line entry to `data/logs/slash/slack_graph.jsonl` (path configurable via `slash_slack.graph_log_path`). Each entry includes `{timestamp, metadata, graph}` so downstream jobs (Neo4j ingestors, audits, etc.) can replay and persist the structured facts without re-scraping Slack.

## Command Input/Output Contracts

### Channel Recap
- **Input:** `/slack summarize #channel --since 2024-11-25 --topic vat`
- **Parsed Params:** `{type:"channel_recap", channel_id, start_ts, end_ts, keywords}`.
- **Output:** summary paragraphs + sections; graph nodes for Conversation, Topic(s), Decisions, Tasks.

### Thread Recap
- **Input:** `/slack summarize https://slack.com/archives/C123/p456`
- **Parsed Params:** `{type:"thread_recap", channel_id, thread_ts}` (permalinks decoded).
- **Output:** sections emphasizing Decisons/Open Questions/Tasks; graph nodes anchored to thread conversation.

### Decision Extraction
- **Input:** `/slack decisions #backend payment api last7d`
- **Output:** list of decisions (each with text, rationale, participants, timestamp, permalink) + graph nodes/edges per decision.

### Task Extraction
- **Input:** `/slack tasks #checkout-dev last week`
- **Output:** tasks list (description, assignee, due hints) + Task nodes linked to Participants and Conversations.

### Topic / Entity Search
- **Input:** `/slack topic billing_service 14d`
- **Output:** grouped results by conversation; graph nodes linking Topic→Conversations→Decisions/Tasks/References.

All outputs follow the **response style** specified in `agents/slash_slack/context.md`.

## Separation from Cerebros Core
- Slash-Slack orchestrator resides under `src/orchestrator/slash_slack/`.
- Registered with `SlashCommandHandler` but runs in its own namespace (no reuse of `main_orchestrator` chains).
- Configuration (`configs/dependency_map.yaml` or new `configs/slash_slack.yaml`) carries Slack token, rate limits, feature flags (e.g., `graph_emit: true/false`).
- Telemetry logs under `data/logs/slash/slack_*.jsonl`.

## Future Extensions
- Multi-channel aggregation (e.g., `/slack summarize #backend + #incidents`).
- Caching layer for repeated queries (store normalized message windows).
- Optional fine-grained Neo4j ingestion (direct driver call vs handing payload to graph service queue).


