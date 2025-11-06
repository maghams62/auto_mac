# Prompts Directory

This directory contains all prompt templates used by the LangGraph automation agent.

## Files

### 1. [system.md](./system.md)
**Purpose:** Core system prompt defining the agent's capabilities and behavior.

**Key Sections:**
- Available tools and capabilities
- Task decomposition approach
- Response format specification
- Key principles for agent behavior

**Used By:** Agent initialization and planning phase

---

### 2. [task_decomposition.md](./task_decomposition.md)
**Purpose:** Detailed instructions for breaking down complex requests into executable steps.

**Key Sections:**
- Objective and instructions
- Tool descriptions
- Output format specification
- Guidelines for simple/medium/complex tasks

**Used By:** Planning node in LangGraph workflow

---

### 3. [few_shot_examples.md](./few_shot_examples.md)
**Purpose:** Comprehensive examples of task decomposition for various scenarios.

**Includes:**
- **Example 1:** Simple task (2 steps) - "Send me the Tesla Autopilot document"
- **Example 2:** Medium task (4 steps) - Screenshot specific page and email
- **Example 3:** Medium-complex task (5 steps) - Extract section and create presentation
- **Example 4:** Complex task (7 steps) - Multi-stage workflow with branching
- **Example 5:** Parallel execution - Fork workflow into independent paths

**Pattern Recognition:**
- Linear chains
- Sequential with context
- Multi-stage workflows
- Fork-join patterns

**Common Mistakes to Avoid:**
- Skipping search steps
- Missing dependencies
- Vague parameters

**Used By:** Planning node for few-shot learning

---

### 4. [tool_definitions.md](./tool_definitions.md)
**Purpose:** Complete specification of all available tools and their parameters.

**Tools Documented:**
1. `search_documents` - Semantic document search
2. `extract_section` - Content extraction from documents
3. `take_screenshot` - Page capture from PDFs
4. `compose_email` - Email creation and sending
5. `create_keynote` - Presentation generation
6. `create_pages_doc` - Document creation

**Includes:**
- Parameter specifications
- Return value formats
- Usage examples
- Tool chaining patterns
- Error handling

**Used By:** Tool execution and parameter validation

---

## Usage in Agent

The prompts are loaded by `AutomationAgent` in [src/agent/agent.py](../src/agent/agent.py):

```python
def _load_prompts(self) -> Dict[str, str]:
    """Load prompt templates from markdown files."""
    prompts_dir = Path(__file__).parent.parent.parent / "prompts"

    prompts = {}
    for prompt_file in ["system.md", "task_decomposition.md", "few_shot_examples.md"]:
        path = prompts_dir / prompt_file
        if path.exists():
            prompts[prompt_file.replace(".md", "")] = path.read_text()

    return prompts
```

## Workflow Integration

```
User Request
    │
    ▼
┌─────────────────────────────────────┐
│  Planning Node                      │
│  ├─ system.md (agent behavior)      │
│  ├─ task_decomposition.md (rules)   │
│  └─ few_shot_examples.md (examples) │
└──────────────┬──────────────────────┘
               │
               ▼
         [Execution Plan]
               │
               ▼
┌─────────────────────────────────────┐
│  Execution Node                     │
│  ├─ tool_definitions.md (reference) │
│  └─ Execute steps with tools        │
└─────────────────────────────────────┘
```

## Modifying Prompts

### Adding New Tool Examples

Edit [few_shot_examples.md](./few_shot_examples.md):

```markdown
## Example 6: Your New Pattern

### User Request
"Your example request here"

### Decomposition
\`\`\`json
{
  "goal": "What user wants to achieve",
  "steps": [...]
}
\`\`\`
```

### Changing Agent Behavior

Edit [system.md](./system.md) to modify:
- Core capabilities
- Response format
- Key principles

### Adding New Tools

1. Add tool to [src/agent/tools.py](../src/agent/tools.py)
2. Document in [tool_definitions.md](./tool_definitions.md)
3. Add examples in [few_shot_examples.md](./few_shot_examples.md)
4. Update [system.md](./system.md) capabilities list

## Best Practices

1. **Be Specific:** Use concrete examples with realistic data
2. **Show Dependencies:** Clearly mark which steps depend on others
3. **Include Reasoning:** Explain *why* each step is needed
4. **Cover Edge Cases:** Include error scenarios and recovery
5. **Use Context Variables:** Show `$stepN.field` syntax in examples

## Testing Prompts

Test prompt changes by running:

```bash
python main.py
# Then type a request that uses the modified prompts
```

Check logs in `data/app.log` for the generated plan:
```bash
tail -f data/app.log | grep "Plan created"
```

## Version History

- **v1.0** (2025-01-XX) - Initial prompts with task decomposition
  - Basic system prompt
  - 5 few-shot examples
  - 6 tool definitions
  - Task complexity categorization
