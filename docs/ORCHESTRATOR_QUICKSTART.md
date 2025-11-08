# LangGraph Orchestrator - Quick Start

Get up and running with the LangGraph orchestrator in 5 minutes!

## Prerequisites

- Python 3.9+
- macOS (for Mail.app, Keynote, Pages integration)
- OpenAI API key

## Installation

### 1. Clone/Navigate to Project

```bash
cd /path/to/auto_mac
```

### 2. Install Dependencies

```bash
# Activate virtual environment (if using one)
source venv/bin/activate

# Install new dependencies
pip install -r requirements.txt
```

This will install:
- LangGraph for orchestration
- LlamaIndex for RAG
- All existing dependencies

### 3. Set Up Environment

```bash
# Create .env file if not exists
echo "OPENAI_API_KEY=your-api-key-here" > .env

# Or export directly
export OPENAI_API_KEY="your-api-key-here"
```

### 4. Index Your Documents

```bash
# First time: index documents for search
python -c "
from src.utils import load_config
from src.documents import DocumentIndexer

config = load_config()
indexer = DocumentIndexer(config)
count = indexer.index_documents()
print(f'Indexed {count} documents')
"
```

## Quick Test

### Run Predefined Tests

```bash
python main_orchestrator.py
```

This will run three test scenarios:
1. Find and email a document
2. Create a Keynote presentation
3. Extract and email a screenshot

### Interactive Mode

```bash
python main_orchestrator.py --interactive
```

Then enter your requests:

```
Goal: Find the Perfect guitar tab and email it to test@example.com
Context: {}

Goal: Create a presentation about AI from my documents
Context: {"max_slides": 10}
```

## Basic Usage

### In Your Code

```python
from src.utils import load_config
from src.documents import DocumentIndexer
from src.orchestrator import LangGraphOrchestrator
from src.orchestrator.state import Budget

# Initialize
config = load_config()
indexer = DocumentIndexer(config)
orchestrator = LangGraphOrchestrator(config, indexer)

# Execute
result = orchestrator.execute(
    goal="Find guitar tabs and email them to me",
    context={
        "user_preference": "fingerstyle",
        "include_full_document": True
    },
    budget=Budget(
        tokens=50000,    # Max tokens
        time_s=300,      # Max 5 minutes
        steps=20         # Max 20 steps
    )
)

# Check result
if result["success"]:
    print(f"✓ {result['summary']}")
    for key, value in result["key_outputs"].items():
        print(f"  {key}: {value}")
else:
    print(f"✗ Failed: {result.get('error', 'Unknown error')}")
```

## Example Requests

### 1. Document Search and Email

```python
orchestrator.execute(
    goal="Find document about 'machine learning' and email to user@example.com",
    context={"email_tone": "professional"}
)
```

### 2. Create Presentation

```python
orchestrator.execute(
    goal="Create a Keynote presentation from my AI research document",
    context={
        "presentation_style": "technical",
        "max_slides": 15
    }
)
```

### 3. Extract and Screenshot

```python
orchestrator.execute(
    goal="Find the Hallelujah guitar tab, take screenshot of page 2, and email it",
    context={"recipient": "friend@example.com"}
)
```

### 4. Complex Multi-Step

```python
orchestrator.execute(
    goal="Find all documents about Python, create a summary, and make a Pages document",
    context={
        "document_format": "technical_report",
        "include_code_examples": True
    },
    budget=Budget(tokens=100000, time_s=600, steps=30)
)
```

## Understanding the Output

```python
result = orchestrator.execute(...)

{
    "success": True,                    # Overall success
    "summary": "Email sent with...",    # Brief description

    "key_outputs": {                    # Important results
        "email_sent": True,
        "document_path": "/path/to/doc.pdf",
        "presentation_path": "/path/to/slides.key"
    },

    "next_actions": [                   # Suggestions
        "Review the email draft",
        "Open the presentation"
    ],

    "metadata": {                       # Execution stats
        "run_id": "uuid",
        "steps_executed": 5,
        "steps_failed": 0,
        "budget_used": {
            "tokens": 12340,
            "time_s": 45.6,
            "steps": 5
        }
    }
}
```

## Configuration

Edit `config.yaml` to customize:

```yaml
openai:
  model: "gpt-4o"
  temperature: 0.7

documents:
  folders:
    - "/path/to/your/documents"

orchestrator:
  state_storage_dir: "data/orchestrator_states"
  max_replans: 3
```

## What Happens Under the Hood

When you execute a goal:

1. **Plan** - GPT-4o creates a DAG of steps
2. **Validate** - Evaluator checks plan soundness
3. **Execute** - Each step runs in dependency order
   - Simple tools: Direct invocation
   - Complex tasks: LlamaIndex worker with RAG
4. **Evaluate** - Check if outputs meet criteria
5. **Replan** - If issues, repair and retry
6. **Synthesize** - Create final result summary

## Debugging

Enable debug logging:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

Check state files:

```bash
ls -la data/orchestrator_states/
```

View detailed logs:

```bash
tail -f data/app.log
```

## Common Issues

### "No documents found"

**Solution:** Index your documents first:
```bash
python -c "from src.documents import DocumentIndexer; from src.utils import load_config; DocumentIndexer(load_config()).index_documents()"
```

### "Tool not found"

**Solution:** Check that all tools are registered in [tools.py](src/agent/tools.py)

### "Budget exceeded"

**Solution:** Increase budget limits:
```python
budget=Budget(tokens=100000, time_s=600, steps=40)
```

### "Plan validation failed"

**Solution:** Check logs for specific issues. Common causes:
- Invalid tool names
- Circular dependencies
- Missing inputs

## Next Steps

1. **Read Full Guide**: See [ORCHESTRATOR_GUIDE.md](ORCHESTRATOR_GUIDE.md) for details
2. **Add Custom Tools**: Extend the tool catalog
3. **Create Workflows**: Build domain-specific workflows
4. **Enable Persistence**: Use checkpoints for long-running tasks

## Key Features

✅ **Automatic Planning** - Breaks down complex goals
✅ **Self-Healing** - Replans on failures
✅ **Budget-Aware** - Tracks tokens, time, steps
✅ **Resumable** - Save and restore state
✅ **RAG-Powered** - LlamaIndex for complex reasoning
✅ **Tool-Agnostic** - Easy to add new tools

## Comparison to Original System

| Feature | Original | Orchestrator |
|---------|----------|--------------|
| Planning | Static | Dynamic DAG |
| Error Recovery | Retry only | Retry + Replan |
| State | In-memory | Persistent |
| Evaluation | None | Full validation |
| Dependencies | Sequential | Parallel-capable |

## Support

- **Issues**: Check logs in `data/app.log`
- **Documentation**: [ORCHESTRATOR_GUIDE.md](ORCHESTRATOR_GUIDE.md)
- **Architecture**: [AGENT_ARCHITECTURE.md](AGENT_ARCHITECTURE.md)

## License

Same as main project

---

**Ready to build? Start with:**

```bash
python main_orchestrator.py --interactive
```

Have fun automating! 🚀
