# Codebase Organization

This document describes the cleaned and organized structure of the auto_mac project.

## Directory Structure

```
auto_mac/
├── src/                        # Main source code
│   ├── agent/                  # Agent implementations
│   │   ├── agent.py           # Main AutomationAgent
│   │   ├── agent_registry.py  # Agent registration system
│   │   ├── browser_agent.py   # Web browser automation
│   │   ├── critic_agent.py    # Task validation
│   │   ├── email_agent.py     # Email composition
│   │   ├── file_agent.py      # File operations
│   │   ├── presentation_agent.py  # Presentation creation
│   │   ├── stock_agent.py     # Stock data retrieval
│   │   ├── writing_agent.py   # Content generation
│   │   ├── tools.py           # Agent tools
│   │   ├── verifier.py        # Result verification
│   │   ├── parameter_resolver.py  # Parameter resolution
│   │   └── section_interpreter.py # Section interpretation
│   │
│   ├── automation/             # Automation modules
│   │   ├── file_organizer.py  # File organization
│   │   ├── keynote_composer.py # Keynote creation
│   │   ├── mail_composer.py   # Email composition
│   │   ├── pages_composer.py  # Pages document creation
│   │   └── web_browser.py     # Web browser control
│   │
│   ├── orchestrator/           # Task orchestration
│   ├── documents/              # Document indexing
│   ├── llm/                    # LLM interactions
│   ├── ui/                     # User interface
│   ├── utils.py               # Utility functions
│   └── workflow.py            # Workflow management
│
├── tests/                      # Active test suite
│   ├── test_all_tools.py      # Comprehensive tool tests
│   ├── test_comprehensive_system.py  # Full system tests
│   ├── test_direct_agent.py   # Direct agent tests
│   ├── test_writing_agent.py  # Writing agent tests
│   ├── run_tests.sh           # Test runner script
│   └── quick_tool_tests.sh    # Quick test script
│
├── docs/                       # Documentation
│   ├── CODEBASE_ORGANIZATION.md  # This file
│   ├── Agent documentation     # Agent-specific docs
│   ├── Feature guides          # Feature documentation
│   ├── Fix summaries          # Historical fixes
│   └── Testing guides         # Testing documentation
│
├── _archive/                   # Archived/obsolete files
│   ├── tests/                 # Old test files
│   └── docs/                  # Superseded documentation
│
├── data/                       # Application data
│   ├── embeddings/            # Vector embeddings
│   └── app.log               # Application logs
│
├── prompts/                    # LLM prompts
├── examples/                   # Example scripts
├── test_data/                  # Test data files
│
├── main.py                     # CLI entry point
├── app.py                      # Web UI entry point (Gradio)
├── config.yaml                 # Configuration
├── requirements.txt            # Python dependencies
├── run.sh                      # Quick start script
├── README.md                   # Main documentation
├── ARCHITECTURE.md            # Architecture overview
├── PROJECT_OVERVIEW.md        # Project overview
├── QUICKSTART.md              # Quick start guide
└── SETUP.md                   # Setup instructions
```

## Key Entry Points

1. **main.py** - CLI interface with chat-based interaction
2. **app.py** - Web-based Gradio interface
3. **run.sh** - Quick start script

## Test Organization

All active tests are in the `tests/` directory:
- `test_all_tools.py` - Tests all 17 tools across 5 agents
- `test_comprehensive_system.py` - Full integration tests
- `test_direct_agent.py` - Direct agent API tests
- `test_writing_agent.py` - Writing agent functionality tests

Old/obsolete tests moved to `_archive/tests/`.

## Documentation Organization

Core documentation remains in root:
- README.md - Main project documentation
- ARCHITECTURE.md - System architecture
- PROJECT_OVERVIEW.md - Project overview
- QUICKSTART.md - Quick start guide
- SETUP.md - Setup instructions

Detailed documentation moved to `docs/`:
- Agent-specific documentation
- Feature guides and quickstarts
- Testing guides
- Historical fix summaries
- Work summaries

## What Was Archived

Files moved to `_archive/`:

### Tests (Redundant or Obsolete)
- test_agent.py - Superseded by test_direct_agent.py
- test_email_request.py - Basic email test
- test_file_organizer.py - Duplicate test via orchestrator
- test_file_organizer_direct.py - Duplicate direct test
- test_keynote_fix.py - Specific fix validation
- test_new_architecture.py - Architecture migration test
- verify_writing_agent.py - Simple verification script
- main_orchestrator.py - Old orchestrator test file

### Other
- guitar_tabs.zip - Large test file
- test_output.log - Old log files
- test_run.log - Old log files

## Agent System

The system uses a multi-agent architecture with 5 specialized agents:

1. **File Agent** (4 tools)
   - search_documents
   - extract_section
   - take_screenshot
   - organize_files

2. **Browser Agent** (5 tools)
   - google_search
   - navigate_to_url
   - extract_page_content
   - take_web_screenshot
   - close_browser

3. **Presentation Agent** (3 tools)
   - create_keynote_with_text
   - create_keynote_with_images
   - create_pages_document

4. **Email Agent** (1 tool)
   - compose_email

5. **Writing Agent** (4 tools)
   - synthesize_content
   - create_slide_deck_content
   - create_detailed_report
   - create_meeting_notes

6. **Stock Agent** (2 tools)
   - get_stock_price
   - get_stock_info

## Next Steps

1. Run tests from `tests/` directory: `cd tests && ./run_tests.sh`
2. Review documentation in `docs/` for specific features
3. Start the application: `python main.py` or `python app.py`
4. For development, obsolete code is preserved in `_archive/`
