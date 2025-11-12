# Reasoning Trace System

**Status**: ✅ Phase 1 Complete (Foundation)
**Feature Flag**: `reasoning_trace.enabled` in config.yaml (default: `false`)

## Overview

The Reasoning Trace system is a **hybrid memory architecture** that tracks decisions, evidence, and commitments across agent executions. It reduces reliance on prompt engineering by providing actual execution history instead of hypothetical examples.

### Key Benefits

1. **Reduced Prompt Engineering**: Use real execution history instead of writing scenario-specific examples
2. **Self-Correction**: Critic feedback flows through trace for adaptive replanning
3. **Delivery Validation**: Track commitments (e.g., "send email", "attach files") to prevent incomplete executions
4. **Context Continuity**: Maintain reasoning chain across planning → execution → verification

### Design Philosophy

- **HYBRID**: Complements existing prompts, doesn't replace them
- **ADDITIVE**: Extends SessionMemory without breaking existing code
- **OPT-IN**: Feature flag controlled, disabled by default for safety
- **LIGHTWEIGHT**: Minimal overhead (~0.4ms per entry)

---

## Architecture

### Data Structures

```python
# Core trace entry
@dataclass
class ReasoningEntry:
    entry_id: str
    interaction_id: str
    timestamp: str
    stage: str  # planning, execution, verification, correction, finalization

    # Decision & Intent
    thought: str  # High-level reasoning
    action: Optional[str]  # Tool/agent invoked
    parameters: Dict[str, Any]

    # Evidence & Observations
    evidence: List[str]
    outcome: str  # pending, success, partial, failed, skipped
    error: Optional[str]

    # Commitments & Artifacts
    commitments: List[str]  # e.g., ["send_email", "attach_document"]
    attachments: List[Dict[str, Any]]  # Files/artifacts discovered

    # Corrective Guidance
    corrections: List[str]  # From Critic agent
```

### Integration Points

1. **SessionMemory**: Stores and manages traces per interaction
2. **Planner**: Records planning decisions, injects trace summary into prompts
3. **Executor**: Records step execution, updates outcomes and attachments
4. **Critic**: Adds corrective guidance to trace
5. **Finalization**: Validates commitments were fulfilled

---

## Usage Patterns

### Pattern 1: Enable Trace for Session

```python
from src.memory import SessionMemory

# Without trace (default, backward compatible)
memory = SessionMemory()

# With trace (opt-in)
memory = SessionMemory(enable_reasoning_trace=True)
```

### Pattern 2: Record Reasoning During Execution

```python
# Start trace for an interaction
interaction_id = memory.add_interaction(user_request="Search and email docs")
memory.start_reasoning_trace(interaction_id)

# Planning phase
entry_id = memory.add_reasoning_entry(
    stage="planning",
    thought="User wants documents searched and emailed",
    evidence=["Detected delivery intent: email, attach"],
    commitments=["send_email", "attach_documents"],
    outcome="success"
)

# Execution phase - before tool call
search_entry = memory.add_reasoning_entry(
    stage="execution",
    thought="Executing document search",
    action="search_documents",
    parameters={"query": "Tesla"},
    outcome="pending"
)

# After tool call - update with results
memory.update_reasoning_entry(
    search_entry,
    outcome="success",
    evidence=["Found 3 PDFs"],
    attachments=[
        {"type": "file", "path": "/docs/tesla.pdf", "status": "found"}
    ]
)
```

### Pattern 3: Get Trace Summary for LLM Context

```python
# Get formatted summary for prompt injection
summary = memory.get_reasoning_summary(max_entries=10)

# Hybrid prompt construction
existing_examples = load_prompt_examples()
trace_context = memory.get_reasoning_summary()

if trace_context:
    # Augment examples with real history
    full_prompt = f"{existing_examples}\n\n{trace_context}\n\n{current_task}"
else:
    # Fall back to examples only
    full_prompt = f"{existing_examples}\n\n{current_task}"
```

### Pattern 4: Validate Delivery Commitments

```python
# During finalization
pending_commitments = memory.get_pending_commitments()
attachments = memory.get_trace_attachments()

if "send_email" in pending_commitments:
    # Check if email was actually sent
    email_result = find_step_result(state, "compose_email")
    if not email_result or email_result.get("status") != "sent":
        return {"status": "partial_success", "message": "Email drafted but not sent"}

if "attach_documents" in pending_commitments:
    if not attachments:
        return {"status": "partial_success", "warning": "No attachments found"}
```

### Pattern 5: Critic Feedback Integration

```python
# When a step fails
memory.update_reasoning_entry(
    step_entry_id,
    outcome="failed",
    error="No documents found with query 'very_specific_term'"
)

# Critic analyzes failure
memory.add_reasoning_entry(
    stage="correction",
    thought="Search query too specific",
    evidence=["0 results returned", "Query length: 3 words"],
    corrections=[
        "Retry with broader query",
        "Consider stemming or fuzzy matching"
    ],
    outcome="success"
)

# Get corrections for replanning
corrections = memory.get_trace_corrections()
# Use corrections to guide next planning attempt
```

---

## Configuration

### config.yaml

```yaml
# Reasoning Trace Configuration (Experimental)
reasoning_trace:
  enabled: false  # Default: false for safety
  # When enabled:
  # - Tracks planning decisions and evidence
  # - Records execution outcomes and artifacts
  # - Captures Critic corrections
  # - Monitors delivery commitments
```

### Enable for Specific Sessions

```python
# Read config
config = load_config()
trace_enabled = config.get("reasoning_trace", {}).get("enabled", False)

# Create session with trace
memory = SessionMemory(enable_reasoning_trace=trace_enabled)
```

---

## Migration Path

### Phase 1: Foundation (✅ Complete)
- ✅ ReasoningTrace data structures
- ✅ SessionMemory integration
- ✅ Feature flag and configuration
- ✅ Unit tests (20/20 passing)
- ✅ Integration tests (6/6 passing)
- ✅ Backward compatibility verified

### Phase 2: Instrumentation (Next)
- [ ] Add trace collection to Planner
- [ ] Add trace collection to Executor
- [ ] Add trace collection to Critic
- [ ] Test with existing workflows (disabled by default)

### Phase 3: Prompt Integration
- [ ] Inject trace summaries into planner prompts
- [ ] A/B test: examples vs. trace-driven context
- [ ] Measure success rates and LLM token usage

### Phase 4: Delivery Validation
- [ ] Add commitment tracking to finalization
- [ ] Implement attachment validation
- [ ] Add safety guardrails (reject if commitments unfulfilled)

---

## Testing

### Run Unit Tests

```bash
python -m pytest tests/test_reasoning_trace.py -v
# Expected: 20/20 tests passing
```

### Run Integration Tests

```bash
python -m pytest tests/test_reasoning_trace_integration.py -v
# Expected: 6/6 tests passing
```

### Verify Backward Compatibility

```bash
python -m pytest tests/test_fix.py -v
# Existing tests should pass unchanged
```

### Performance Benchmarks

- Trace collection overhead: **< 0.5ms per entry**
- Summary generation (50 entries): **< 10ms**
- Memory footprint: **~500 bytes per entry**

---

## Examples

### Example 1: Search and Email Workflow

```python
# User: "Search for Tesla documents and email them"

# Planning
memory.add_reasoning_entry(
    stage="planning",
    thought="Need to: (1) search documents, (2) email with attachments",
    commitments=["send_email", "attach_documents"],
    outcome="success"
)

# Execution: Search
search_entry = memory.add_reasoning_entry(
    stage="execution",
    thought="Searching for Tesla documents",
    action="search_documents",
    parameters={"query": "Tesla"},
    outcome="pending"
)

# Update with results
memory.update_reasoning_entry(
    search_entry,
    outcome="success",
    evidence=["Found 3 PDFs in /docs"],
    attachments=[
        {"type": "file", "path": "/docs/tesla_report.pdf"},
        {"type": "file", "path": "/docs/tesla_analysis.pdf"},
        {"type": "file", "path": "/docs/tesla_summary.pdf"}
    ]
)

# Execution: Email
memory.add_reasoning_entry(
    stage="execution",
    thought="Sending email with 3 attachments",
    action="compose_email",
    parameters={
        "recipient": "user@example.com",
        "subject": "Tesla Documents",
        "attachments": ["/docs/tesla_report.pdf", ...]
    },
    outcome="success",
    evidence=["Email sent successfully"]
)

# Finalization: Validate
attachments = memory.get_trace_attachments()
assert len(attachments) == 3  # All documents attached
```

### Example 2: Critic-Driven Retry

```python
# Attempt 1: Fails
memory.add_reasoning_entry(
    stage="execution",
    thought="Searching with specific query",
    action="search_documents",
    parameters={"query": "tesla_v3_final_FINAL"},
    outcome="failed",
    error="No documents found"
)

# Critic analyzes
memory.add_reasoning_entry(
    stage="correction",
    thought="Query too specific, user likely wants broader search",
    corrections=["Remove version suffixes", "Try 'tesla' only"],
    outcome="success"
)

# Attempt 2: Succeeds
memory.add_reasoning_entry(
    stage="execution",
    thought="Retrying with broader query",
    action="search_documents",
    parameters={"query": "tesla"},
    outcome="success",
    evidence=["Found 12 documents"]
)

# Next time: Planner sees this correction in trace summary
# and avoids overly-specific queries
```

---

## Best Practices

### DO ✅
- Enable trace only when needed (testing, debugging, complex workflows)
- Use hybrid approach: combine examples + trace context
- Check `is_reasoning_trace_enabled()` before assuming trace methods work
- Update entries after tool execution (pending → success/failed)
- Track commitments for delivery-critical workflows
- Use trace summary to reduce scenario-specific prompts

### DON'T ❌
- Don't enable globally in production until Phase 3 complete
- Don't rely solely on trace (keep existing prompts as fallback)
- Don't log sensitive data in trace entries
- Don't forget to call `start_reasoning_trace()` before adding entries
- Don't assume trace is always available (check `REASONING_TRACE_AVAILABLE`)

---

## Troubleshooting

### Trace Not Working

**Symptom**: `add_reasoning_entry()` returns `None`

**Solutions**:
1. Check feature flag: `config.yaml` → `reasoning_trace.enabled: true`
2. Enable for session: `SessionMemory(enable_reasoning_trace=True)`
3. Start trace: `memory.start_reasoning_trace(interaction_id)`
4. Verify module available: `from src.memory.session_memory import REASONING_TRACE_AVAILABLE`

### Summary is Empty

**Symptom**: `get_reasoning_summary()` returns `""`

**Solutions**:
1. Check entries exist: `len(memory._reasoning_traces[interaction_id].entries) > 0`
2. Verify correct interaction_id is active
3. Ensure `start_reasoning_trace()` was called

### Backward Compatibility Issues

**Symptom**: Existing code breaks after adding trace

**Solutions**:
1. All trace methods are safe to call when disabled (return `None`, `""`, or `[]`)
2. Check existing SessionMemory calls still work
3. Run regression tests: `pytest tests/test_fix.py`

---

## API Reference

### SessionMemory Methods

```python
# Enable/check trace
is_reasoning_trace_enabled() -> bool
start_reasoning_trace(interaction_id: str) -> bool

# Add/update entries
add_reasoning_entry(stage: str, thought: str, **kwargs) -> Optional[str]
update_reasoning_entry(entry_id: str, **kwargs) -> bool

# Query trace
get_reasoning_summary(max_entries=10, include_corrections_only=False) -> str
get_pending_commitments(interaction_id=None) -> List[str]
get_trace_attachments(interaction_id=None) -> List[Dict]
get_trace_corrections(interaction_id=None) -> List[str]
```

### ReasoningStage Enum

- `PLANNING`: Planner creating plan
- `EXECUTION`: Executor running tool
- `VERIFICATION`: Verifier checking output
- `CORRECTION`: Critic analyzing failure
- `FINALIZATION`: Final delivery checks

### OutcomeStatus Enum

- `PENDING`: Not yet completed
- `SUCCESS`: Completed successfully
- `PARTIAL`: Partially successful
- `FAILED`: Failed with error
- `SKIPPED`: Skipped due to dependencies

---

## Future Enhancements

### Phase 5: Advanced Features (Future)
- Cross-interaction pattern learning
- Automatic prompt optimization based on trace
- Trace-based confidence scoring
- Visual trace debugging UI

### Integration Ideas
- Export trace to external observability tools (Datadog, Honeycomb)
- Trace-based A/B testing framework
- LLM fine-tuning from successful traces

---

## Support

For questions, issues, or contributions:

1. Check this documentation
2. Review test files: `tests/test_reasoning_trace*.py`
3. Review source: `src/memory/reasoning_trace.py`
4. File issue with `[reasoning-trace]` tag
