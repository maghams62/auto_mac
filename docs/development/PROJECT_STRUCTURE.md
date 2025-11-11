# Project Structure

This document describes the organization of the Mac Automation Assistant codebase.

## Directory Structure

```
auto_mac/
├── app.py                    # Web UI entry point (Gradio)
├── main.py                   # Terminal UI entry point
├── config.yaml              # Configuration file
├── requirements.txt         # Python dependencies
├── run.sh                   # Startup script
├── README.md                # Main project README
│
├── src/                     # Source code
│   ├── agent/              # Agent implementations
│   │   ├── agent_registry.py
│   │   ├── browser_agent.py
│   │   ├── file_agent.py
│   │   ├── reddit_agent.py
│   │   └── ... (other agents)
│   │
│   ├── automation/         # Automation modules
│   │   ├── web_browser.py
│   │   ├── reddit_scanner.py
│   │   ├── keynote_composer.py
│   │   └── ... (other automation)
│   │
│   ├── documents/          # Document processing
│   │   ├── indexer.py
│   │   ├── parser.py
│   │   └── search.py
│   │
│   ├── llm/                # LLM integration
│   │   ├── planner.py
│   │   └── prompts.py
│   │
│   ├── orchestrator/       # Orchestration logic
│   │   ├── main_orchestrator.py
│   │   ├── planner.py
│   │   ├── executor.py
│   │   └── ... (other orchestrator files)
│   │
│   ├── ui/                 # User interface
│   │   └── chat.py
│   │
│   ├── utils.py            # Utility functions
│   └── workflow.py         # Workflow orchestrator
│
├── tests/                  # Test files
│   ├── test_direct_agent.py
│   ├── test_complete_workflow.py
│   ├── test_all_tools.py
│   └── ... (other tests)
│
├── scripts/                # Utility and debug scripts
│   ├── debug_stock_page.py
│   ├── demo_maps_llm.py
│   ├── verify_agent_distinction.py
│   └── verify_maps.py
│
├── examples/               # Example usage scripts
│   ├── create_presentation_example.py
│   └── stock_report_example.py
│
├── docs/                   # Documentation
│   ├── ARCHITECTURE.md
│   ├── QUICKSTART.md
│   ├── AGENT_ARCHITECTURE.md
│   └── ... (other docs)
│
├── prompts/                # Prompt templates
│   ├── system.md
│   ├── tool_definitions.md
│   └── task_decomposition.md
│
├── data/                   # Data directory
│   ├── embeddings/        # FAISS index files
│   ├── logs/              # Application logs
│   ├── screenshots/       # Screenshot files
│   ├── presentations/     # Generated presentations
│   └── reports/           # Generated reports
│
├── test_data/             # Test data files
│   └── ... (PDFs and test documents)
│
├── test_docs/             # Test documents
│   └── ... (test PDFs and text files)
│
├── _archive/              # Archived files
│   └── ... (old files)
│
└── venv/                  # Virtual environment (not committed)
```

## Key Directories

### `src/` - Source Code
Contains all the main application code organized by functionality:
- **agent/**: Individual agent implementations (FileAgent, BrowserAgent, etc.)
- **automation/**: Automation modules for external services (browser, Reddit, etc.)
- **documents/**: Document processing and indexing
- **llm/**: LLM integration and prompts
- **orchestrator/**: Main orchestration logic
- **ui/**: User interface components

### `tests/` - Test Files
All test files are organized here:
- Unit tests for individual components
- Integration tests for workflows
- System tests for end-to-end functionality

### `scripts/` - Utility Scripts
Development and debugging scripts:
- Debug scripts for troubleshooting
- Verification scripts for testing components
- Demo scripts for showcasing features

### `examples/` - Example Scripts
Example usage scripts demonstrating how to use the framework.

### `docs/` - Documentation
All project documentation:
- Architecture documents
- Quickstart guides
- Implementation summaries
- Agent documentation

### `data/` - Data Directory
Runtime data:
- **embeddings/**: FAISS index files
- **logs/**: Application logs
- **screenshots/**: Generated screenshots
- **presentations/**: Generated presentations
- **reports/**: Generated reports

## File Organization Principles

1. **Root Directory**: Contains only entry points and configuration files
2. **Source Code**: All source code in `src/` organized by functionality
3. **Tests**: All tests in `tests/` directory
4. **Scripts**: Utility scripts in `scripts/` directory
5. **Documentation**: All docs in `docs/` directory
6. **Data**: Runtime data in `data/` directory with subdirectories by type

## Adding New Files

When adding new files:
- **Agents**: Add to `src/agent/`
- **Automation**: Add to `src/automation/`
- **Tests**: Add to `tests/`
- **Scripts**: Add to `scripts/`
- **Documentation**: Add to `docs/`
- **Examples**: Add to `examples/`

## Import Paths

All imports should use relative imports within `src/` or absolute imports from the project root:

```python
# Within src/
from .agent import AgentRegistry
from ..automation import RedditScanner

# From project root
from src.agent import AgentRegistry
from src.automation import RedditScanner
```

