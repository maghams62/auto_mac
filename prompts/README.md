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

### 3. [examples/](./examples/README.md)
**Purpose:** Agent-scoped few-shot library that replaces the monolithic `few_shot_examples.md`.

**Structure:**
- `core/` — universal planning rules, capability checks, context hand-off patterns
- `general/` — cross-agent orchestration templates used by the automation planner
- Domain folders (`maps/`, `email/`, `writing/`, `stocks/`, etc.) — atomic exemplars for specialised agents
- `index.json` — maps each category to its markdown files and records which categories each agent consumes

**Usage:**
- Loaded through `src.prompt_repository.PromptRepository`
- Automation agent consumes `core`, `general`, and `safety`
- Specialised agents receive only the categories listed for them in `index.json`

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
from src.prompt_repository import PromptRepository

class AutomationAgent:
    def __init__(self, config: Dict[str, Any], session_manager: Optional[SessionManager] = None):
        ...
        self.prompt_repository = PromptRepository()
        self.prompts = self._load_prompts()

    def _load_prompts(self) -> Dict[str, str]:
        prompts_dir = Path(__file__).parent.parent.parent / "prompts"

        prompts: Dict[str, str] = {}
        for prompt_file in ["system.md", "task_decomposition.md"]:
            path = prompts_dir / prompt_file
            if path.exists():
                prompts[prompt_file.replace(".md", "")] = path.read_text()

        prompts["few_shot_examples"] = self.prompt_repository.to_prompt_block("automation")
        return prompts
```

## Prompt Assembly Order (CRITICAL!)

When constructing the planning prompt, components are assembled in this specific order:

```
1. System Prompt (system.md)
   ↓ Establishes agent identity, high-level behavior, orchestration rules

2. Task Decomposition (task_decomposition.md)
   ↓ Provides planning methodology, capability assessment, tool selection rules

3. User Context (from ConfigAccessor)
   ↓ Injects user-specific constraints from config.yaml (folders, defaults, etc.)

4. Tool Catalog (runtime injection)
   ↓ Dynamically generated list of available tools with full parameter schemas

5. Few-Shot Examples (from PromptRepository)
   ↓ Agent-scoped examples showing correct planning patterns
```

### **Rationale for This Order**

This sequence follows the principle: **General → Specific → Examples**

1. **System first**: Establishes fundamental agent capabilities and behavior patterns
2. **Decomposition second**: Provides concrete methodology for breaking down tasks
3. **User context third**: Applies user-specific constraints that limit scope
4. **Tools fourth**: Shows what's actually available to execute with
5. **Examples last**: LLMs have recency bias - examples placed last get highest attention

### **Why Examples Come Last**

Research shows LLMs weight recent context more heavily. By placing examples last:
- Correct patterns are freshest in the model's "mind"
- Examples can reference earlier concepts (system principles, tool names)
- Reduces risk of early examples being "forgotten" by the time planning happens

### **Anti-Hallucination Architecture**

The tool catalog (Level 4) is **NEVER hardcoded** - it's generated at runtime from the actual tool registry:

```python
# src/agent/agent.py:182-207
for tool in ALL_AGENT_TOOLS:
    schema = tool.args_schema.schema()
    # Generates full parameter specs with types & requirements
```

This prevents tool drift where prompts reference tools that no longer exist.

## Workflow Integration

```
User Request
    │
    ▼
┌─────────────────────────────────────┐
│  Planning Node                      │
│  ├─ system.md (agent behavior)             │
│  ├─ task_decomposition.md (rules)          │
│  └─ PromptRepository → examples/ (few-shot │
│      bundles per agent)                    │
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

1. Create a markdown file under `examples/<category>/`. Pick an existing category such as `maps/`, `email/`, or `writing/`; add a new folder only when introducing a brand new domain.
2. Append the relative path (`"<category>/<filename>.md"`) to the matching list in `examples/index.json` under `categories`.
3. Update the `agents` mapping in `examples/index.json` so the right agents consume the new category.

```markdown
## Example: Your New Pattern

### User Request
"Your example request here"

### Decomposition
\`\`\`json
{
  "goal": "What the user wants to achieve",
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
3. Add examples in the relevant folder under [examples/](./examples/README.md) and update `examples/index.json`
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
- **v1.1** (2025-02-XX) - Modular prompt hierarchy
  - Replaced `few_shot_examples.md` with agent-scoped folders under `examples/`
  - Added `PromptRepository` for loading category-specific bundles
  - Extended documentation and tests to reflect scoped prompts
