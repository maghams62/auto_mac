# Documentation Index

**Central repository for all Cerebro OS documentation**

This index provides a comprehensive mapping of all documentation files organized by category, purpose, and location. Use this as the primary reference for finding documentation without searching the entire codebase.

---

## Quick Navigation

- [Architecture & System Design](#architecture--system-design)
- [Agents](#agents)
- [Features](#features)
- [Testing](#testing)
- [Development](#development)
- [Changelog & Fixes](#changelog--fixes)
- [Quick Start Guides](#quick-start-guides)
- [Prompts](#prompts)
- [Root-Level Documentation](#root-level-documentation)

---

## Architecture & System Design

### Core Architecture
| File | Path | Description |
|------|------|-------------|
| System Overview | `docs/architecture/OVERVIEW.md` | High-level system architecture |
| Agent Architecture | `docs/architecture/AGENT_ARCHITECTURE.md` | Multi-agent design and LangGraph implementation |
| Agent Hierarchy | `docs/architecture/AGENT_HIERARCHY.md` | Complete catalog of agents and tools |
| Master Agent Guide | `docs/MASTER_AGENT_GUIDE.md` | **START HERE** - Authoritative reference for agents |
| LLM-Driven Changes | `docs/architecture/LLM_DRIVEN_CHANGES.md` | Design decisions and LLM-driven patterns |
| LLM-Driven Decisions | `docs/architecture/LLM_DRIVEN_DECISIONS.md` | Historical decision log |
| No Hardcoded Logic | `docs/architecture/NO_HARDCODED_LOGIC.md` | LLM-driven verification principles |

### Architecture Guides
| File | Path | Description |
|------|------|-------------|
| Semantic Page Search | `docs/architecture/guides/SEMANTIC_PAGE_SEARCH.md` | Document search implementation |
| Session Memory System | `docs/architecture/guides/SESSION_MEMORY_SYSTEM.md` | Memory and context management |
| Session Memory Architecture | `docs/architecture/SESSION_MEMORY_ARCHITECTURE.md` | Technical memory architecture |
| Slash Commands Guide | `docs/architecture/guides/SLASH_COMMANDS.md` | Slash command architecture |
| Maps Trip Planner Architecture | `docs/architecture/MAPS_TRIP_PLANNER_ARCHITECTURE.md` | Maps agent architecture details |

### System Design Documents
| File | Path | Description |
|------|------|-------------|
| Generalization Architecture | `docs/GENERALIZATION_ARCHITECTURE.md` | Generalization patterns |
| Tool Composition Plan | `docs/TOOL_COMPOSITION_PLAN.md` | Tool composition strategy |
| Prompt Integration Guide | `docs/PROMPT_INTEGRATION_GUIDE.md` | How prompts integrate with system |
| Implementation Roadmap | `docs/IMPLEMENTATION_ROADMAP.md` | Future implementation plans |

---

## Agents

### Agent Documentation
| File | Path | Description |
|------|------|-------------|
| Browser Agent | `docs/agents/BROWSER_AGENT.md` | Web browsing and content extraction |
| Maps Agent | `docs/agents/MAPS_AGENT.md` | Trip planning and navigation |
| Maps Trip Planner Summary | `docs/agents/MAPS_TRIP_PLANNER_SUMMARY.md` | Maps agent summary |
| Finance Agent | `docs/agents/FINANCE_AGENT.md` | Stock data and charts |
| Stock Agent | `docs/agents/STOCK_AGENT.md` | Stock analysis capabilities |
| Writing Agent | `docs/agents/WRITING_AGENT.md` | Content generation agent |

---

## Features

### Core Features
| File | Path | Description |
|------|------|-------------|
| Slash Commands | `docs/features/SLASH_COMMANDS.md` | Direct agent access commands |
| Slash Commands Complete | `docs/features/SLASH_COMMANDS_COMPLETE.md` | Complete verification |
| Slash Command Coverage | `docs/features/SLASH_COMMAND_COVERAGE.md` | Coverage report |
| Slash Commands Implementation | `docs/features/SLASH_COMMANDS_IMPLEMENTATION.md` | Technical implementation |
| Folder Command | `docs/features/FOLDER_COMMAND.md` | Folder organization feature |
| Orchestrator Guide | `docs/features/ORCHESTRATOR_GUIDE.md` | Orchestrator usage |
| Orchestrator Summary | `docs/features/ORCHESTRATOR_SUMMARY.md` | Orchestrator overview |

### Integration Features
| File | Path | Description |
|------|------|-------------|
| WhatsApp Integration | `docs/features/WHATSAPP_INTEGRATION.md` | WhatsApp agent integration |
| Voice Integration | `docs/features/VOICE_INTEGRATION.md` | Voice input capabilities |
| Twitter/X Command | `docs/features/TWITTER_X_COMMAND.md` | Twitter agent features |
| Google Search API | `docs/features/GOOGLE_SEARCH_API.md` | Google search integration |
| Raycast Enhancements | `docs/features/RAYCAST_ENHANCEMENTS.md` | Raycast integration |

### UI Features
| File | Path | Description |
|------|------|-------------|
| UI Fix Success Report | `docs/features/UI_FIX_SUCCESS_REPORT.md` | UI improvements |
| UI Security Audit Report | `docs/features/UI_SECURITY_AUDIT_REPORT.md` | Security audit results |

### Feature Summaries (Root Level - To Be Moved)
| File | Path | Description |
|------|------|-------------|
| Email Reply Feature | `EMAIL_REPLY_FEATURE.md` | Email reply capabilities |
| Email Reply Agent Integration | `EMAIL_REPLY_AGENT_INTEGRATION.md` | Email agent integration details |
| Email Reading Feature | `EMAIL_READING_FEATURE.md` | Email reading capabilities |
| Email Feature Summary | `EMAIL_FEATURE_SUMMARY.md` | Email features overview |
| Maps Transit Feature | `MAPS_TRANSIT_FEATURE.md` | Maps transit directions |
| Bluesky Integration Summary | `BLUESKY_INTEGRATION_SUMMARY.md` | Bluesky integration overview |
| DuckDuckGo Migration | `DUCKDUCKGO_MIGRATION.md` | Search engine migration |
| Stock Workflow Improvements | `STOCK_WORKFLOW_IMPROVEMENTS.md` | Stock analysis improvements |
| Help System Implementation | `HELP_SYSTEM_IMPLEMENTATION.md` | Help system features |

---

## Testing

### Test Documentation
| File | Path | Description |
|------|------|-------------|
| Comprehensive Test Report | `docs/testing/COMPREHENSIVE_TEST_REPORT.md` | Full test results (62% pass rate) |
| Testing Report | `docs/testing/TESTING_REPORT.md` | Testing summary |
| Integration Test Results | `docs/testing/INTEGRATION_TEST_RESULTS.md` | Integration test results |
| Browser Testing | `docs/testing/BROWSER_TESTING.md` | Browser agent tests |
| Stress Test Suite | `docs/testing/STRESS_TEST_SUITE.md` | Stress testing documentation |

### Testing Guides (Root Level - To Be Moved)
| File | Path | Description |
|------|------|-------------|
| Testing Methodology | `TESTING_METHODOLOGY.md` | Testing approach and methodology |
| Comprehensive Test Suite | `COMPREHENSIVE_TEST_SUITE.md` | Test suite overview |
| Focused Test Suite | `FOCUSED_TEST_SUITE.md` | Focused test documentation |
| WhatsApp Test Guide | `WHATSAPP_TEST_GUIDE.md` | WhatsApp testing guide |
| WhatsApp Verification Complete | `WHATSAPP_VERIFICATION_COMPLETE.md` | WhatsApp verification results |
| WhatsApp Verification Report | `WHATSAPP_VERIFICATION_REPORT.md` | WhatsApp verification details |
| WhatsApp Verification Summary | `WHATSAPP_VERIFICATION_SUMMARY.md` | WhatsApp verification summary |
| WhatsApp Dotards Test Report | `WHATSAPP_DOTARDS_TEST_REPORT.md` | Specific WhatsApp test report |
| Bluesky Testing Results | `BLUESKY_TESTING_RESULTS.md` | Bluesky test results |
| Search Verification | `SEARCH_VERIFICATION.md` | Search functionality verification |

---

## Development

### Project Structure
| File | Path | Description |
|------|------|-------------|
| Project Structure | `docs/development/PROJECT_STRUCTURE.md` | Codebase organization |
| Project Overview | `docs/development/PROJECT_OVERVIEW.md` | Project overview |
| Codebase Organization | `docs/development/CODEBASE_ORGANIZATION.md` | File structure details |
| Implementation Summary | `docs/development/IMPLEMENTATION_SUMMARY.md` | Implementation notes |
| Frontend Structure | `docs/development/frontend_structure.txt` | Frontend code structure |

### Development History
| File | Path | Description |
|------|------|-------------|
| Reorganization Complete | `docs/development/history/REORGANIZATION_COMPLETE.md` | Reorganization summary |
| Reorganization Plan | `docs/development/history/REORGANIZATION_PLAN.md` | Reorganization planning |
| Implementation Complete | `docs/development/history/IMPLEMENTATION_COMPLETE.md` | Implementation completion |
| Implementation Summary | `docs/development/history/IMPLEMENTATION_SUMMARY.md` | Historical implementation notes |
| Session Memory Implementation | `docs/development/history/SESSION_MEMORY_IMPLEMENTATION_COMPLETE.md` | Session memory implementation |
| Profile Implementation Verification | `docs/development/history/PROFILE_IMPLEMENTATION_VERIFICATION.md` | Profile feature verification |
| Applescript MCP Integration Plan | `docs/development/history/APPLESCRIPT_MCP_INTEGRATION_PLAN.md` | MCP integration planning |

### Development Summaries (Root Level - To Be Moved)
| File | Path | Description |
|------|------|-------------|
| Session Summary | `SESSION_SUMMARY.md` | Session management summary |
| Session Complete Summary | `SESSION_COMPLETE_SUMMARY.md` | Session completion details |
| Final Summary | `FINAL_SUMMARY.md` | Final implementation summary |
| Directory Map | `DIRECTORY_MAP.md` | Directory structure mapping |
| Reorganization 2024 | `docs/REORGANIZATION_2024.md` | 2024 reorganization notes |

---

## Changelog & Fixes

### Changelog (docs/changelog/)
| File | Path | Description |
|------|------|-------------|
| Agent Fixes and Notifications | `docs/changelog/AGENT_FIXES_AND_NOTIFICATIONS.md` | Agent-related fixes |
| Bug Fixes Applied | `docs/changelog/BUG_FIXES_APPLIED.md` | Historical bug fixes |
| Config Hot Reload Fix | `docs/changelog/CONFIG_HOT_RELOAD_FIX.md` | Config reload improvements |
| Config Validation Guide | `docs/changelog/CONFIG_VALIDATION_GUIDE.md` | Configuration validation |
| Defensive Programming Guide | `docs/changelog/DEFENSIVE_PROGRAMMING_GUIDE.md` | Defensive coding practices |
| API Parameter Validation | `docs/changelog/API_PARAMETER_VALIDATION.md` | API validation improvements |
| Quick API Validation Guide | `docs/changelog/QUICK_API_VALIDATION_GUIDE.md` | Quick validation reference |
| Race Condition Fixes | `docs/changelog/RACE_CONDITION_FIXES.md` | Race condition resolutions |
| Loading Fix | `docs/changelog/LOADING_FIX.md` | Loading improvements |
| Lazy Loading Optimization | `docs/changelog/LAZY_LOADING_OPTIMIZATION.md` | Performance optimizations |
| Twitter API Fix | `docs/changelog/TWITTER_API_FIX.md` | Twitter API fixes |

### Fix Summaries (Root Level - To Be Moved to docs/changelog/)
| File | Path | Description |
|------|------|-------------|
| Complete Fix Summary | `COMPLETE_FIX_SUMMARY.md` | Comprehensive fix summary |
| Complete Permanent Fix | `COMPLETE_PERMANENT_FIX.md` | Permanent fixes applied |
| Permanent Fix Summary | `PERMANENT_FIX_SUMMARY.md` | Summary of permanent fixes |
| Exhaustive Fix Summary | `EXHAUSTIVE_FIX_SUMMARY.md` | Exhaustive fix documentation |
| Final Comprehensive Fix | `FINAL_COMPREHENSIVE_FIX.md` | Final comprehensive fixes |
| Final Comprehensive Fix V2 | `FINAL_COMPREHENSIVE_FIX_V2.md` | Updated comprehensive fixes |
| Fixes Complete | `FIXES_COMPLETE.md` | Fix completion summary |
| Parsing Fix Summary | `PARSING_FIX_SUMMARY.md` | Parsing improvements |
| Template Resolution Fix | `TEMPLATE_RESOLUTION_FIX.md` | Template resolution fixes |
| Shared Template Resolver Fix | `SHARED_TEMPLATE_RESOLVER_FIX.md` | Template resolver improvements |
| Folder Operations Fix | `FOLDER_OPERATIONS_FIX.md` | Folder operation fixes |
| Search and Email Fix | `SEARCH_AND_EMAIL_FIX.md` | Search and email improvements |
| UI Data Formatting Fix | `UI_DATA_FORMATTING_FIX.md` | UI formatting improvements |
| Transcription Fix | `TRANSCRIPTION_FIX.md` | Transcription fixes |
| Import Fix Summary | `IMPORT_FIX_SUMMARY.md` | Import resolution fixes |
| Delivery Intent Fix Complete | `DELIVERY_INTENT_FIX_COMPLETE.md` | Delivery intent fixes |
| Bluesky Slideshow Email Fix | `BLUESKY_SLIDESHOW_EMAIL_FIX.md` | Bluesky integration fixes |
| Prompt Segregation Complete | `PROMPT_SEGREGATION_COMPLETE.md` | Prompt organization fixes |
| Agent Atomicity Audit | `AGENT_ATOMICITY_AUDIT.md` | Agent atomicity review |
| Hardcode Inventory | `HARDCODE_INVENTORY.md` | Hardcoded values inventory |
| Hardcode Refactor Progress | `HARDCODE_REFACTOR_PROGRESS.md` | Hardcode removal progress |

---

## Quick Start Guides

### Quick Start (docs/quickstart/)
| File | Path | Description |
|------|------|-------------|
| Setup | `docs/quickstart/SETUP.md` | Installation and configuration |
| Quick Start | `docs/quickstart/QUICK_START.md` | Your first automation |
| Quick Start New Features | `docs/quickstart/QUICK_START_NEW_FEATURES.md` | New features guide |
| Session Memory Quickstart | `docs/quickstart/SESSION_MEMORY_QUICKSTART.md` | Session memory guide |

### Quick Start Guides (Root Level - To Be Moved to docs/quickstart/)
| File | Path | Description |
|------|------|-------------|
| Quick Start | `QUICK_START.md` | Quick start guide (duplicate) |
| Start Here | `START_HERE.md` | **START HERE** - Getting started |
| Start UI Guide | `START_UI_GUIDE.md` | Web UI quick start |
| Start Servers | `START_SERVERS.md` | Server startup guide |
| Restart Server | `RESTART_SERVER.md` | Server restart instructions |

---

## Prompts

### Prompt Documentation
| File | Path | Description |
|------|------|-------------|
| Prompt README | `prompts/README.md` | Prompt system overview |
| System Prompts | `prompts/system.md` | System-level prompts |
| Few Shot Examples | `prompts/few_shot_examples.md` | Example patterns |
| Task Decomposition | `prompts/task_decomposition.md` | Task planning prompts |
| Tool Definitions | `prompts/tool_definitions.md` | Tool definition prompts |
| Folder Agent Policy | `prompts/folder_agent_policy.md` | Folder agent prompts |
| Delivery Intent | `prompts/delivery_intent.md` | Delivery intent prompts |

### Prompt Examples
| Directory | Path | Description |
|-----------|------|-------------|
| Examples README | `prompts/examples/README.md` | Examples overview |
| Core Examples | `prompts/examples/core/` | Core planning examples |
| General Examples | `prompts/examples/general/` | General workflow examples |
| Email Examples | `prompts/examples/email/` | Email agent examples |
| Maps Examples | `prompts/examples/maps/` | Maps agent examples |
| Stocks Examples | `prompts/examples/stocks/` | Stock agent examples |
| Writing Examples | `prompts/examples/writing/` | Writing agent examples |
| Screen Examples | `prompts/examples/screen/` | Screenshot examples |
| Web Examples | `prompts/examples/web/` | Web browsing examples |
| Cross Domain Examples | `prompts/examples/cross_domain/` | Multi-agent examples |
| Safety Examples | `prompts/examples/safety/` | Safety guardrails |
| File Examples | `prompts/examples/file/` | File agent examples |

### Prompt Documentation (docs/)
| File | Path | Description |
|------|------|-------------|
| Few Shot Examples with CoT | `docs/FEW_SHOT_EXAMPLES_WITH_COT.md` | Chain-of-thought examples |

---

## Root-Level Documentation

These files are currently in the root directory and will be organized into appropriate `docs/` subdirectories:

### Main Documentation
- `README.md` - Main project README
- `DIRECTORY_MAP.md` - Directory structure (move to docs/development/)

### Quick Start (move to docs/quickstart/)
- `QUICK_START.md`
- `START_HERE.md`
- `START_UI_GUIDE.md`
- `START_SERVERS.md`
- `RESTART_SERVER.md`

### Features (move to docs/features/)
- `EMAIL_REPLY_FEATURE.md`
- `EMAIL_REPLY_AGENT_INTEGRATION.md`
- `EMAIL_READING_FEATURE.md`
- `EMAIL_FEATURE_SUMMARY.md`
- `MAPS_TRANSIT_FEATURE.md`
- `BLUESKY_INTEGRATION_SUMMARY.md`
- `DUCKDUCKGO_MIGRATION.md`
- `STOCK_WORKFLOW_IMPROVEMENTS.md`
- `HELP_SYSTEM_IMPLEMENTATION.md`

### Testing (move to docs/testing/)
- `TESTING_METHODOLOGY.md`
- `COMPREHENSIVE_TEST_SUITE.md`
- `FOCUSED_TEST_SUITE.md`
- `WHATSAPP_TEST_GUIDE.md`
- `WHATSAPP_VERIFICATION_COMPLETE.md`
- `WHATSAPP_VERIFICATION_REPORT.md`
- `WHATSAPP_VERIFICATION_SUMMARY.md`
- `WHATSAPP_DOTARDS_TEST_REPORT.md`
- `BLUESKY_TESTING_RESULTS.md`
- `SEARCH_VERIFICATION.md`

### Changelog/Fixes (move to docs/changelog/)
- `COMPLETE_FIX_SUMMARY.md`
- `COMPLETE_PERMANENT_FIX.md`
- `PERMANENT_FIX_SUMMARY.md`
- `EXHAUSTIVE_FIX_SUMMARY.md`
- `FINAL_COMPREHENSIVE_FIX.md`
- `FINAL_COMPREHENSIVE_FIX_V2.md`
- `FIXES_COMPLETE.md`
- `PARSING_FIX_SUMMARY.md`
- `TEMPLATE_RESOLUTION_FIX.md`
- `SHARED_TEMPLATE_RESOLVER_FIX.md`
- `FOLDER_OPERATIONS_FIX.md`
- `SEARCH_AND_EMAIL_FIX.md`
- `UI_DATA_FORMATTING_FIX.md`
- `TRANSCRIPTION_FIX.md`
- `IMPORT_FIX_SUMMARY.md`
- `DELIVERY_INTENT_FIX_COMPLETE.md`
- `BLUESKY_SLIDESHOW_EMAIL_FIX.md`
- `PROMPT_SEGREGATION_COMPLETE.md`
- `AGENT_ATOMICITY_AUDIT.md`
- `HARDCODE_INVENTORY.md`
- `HARDCODE_REFACTOR_PROGRESS.md`

### Development (move to docs/development/)
- `SESSION_SUMMARY.md`
- `SESSION_COMPLETE_SUMMARY.md`
- `FINAL_SUMMARY.md`
- `DIRECTORY_MAP.md`

---

## Documentation by Purpose

### For Users
- **Getting Started**: `docs/quickstart/SETUP.md`, `docs/quickstart/QUICK_START.md`, `START_HERE.md`
- **Using Features**: `docs/features/SLASH_COMMANDS.md`, `docs/features/ORCHESTRATOR_GUIDE.md`
- **Agent Capabilities**: `docs/agents/`, `docs/architecture/AGENT_HIERARCHY.md`

### For Developers
- **Architecture**: `docs/architecture/OVERVIEW.md`, `docs/architecture/AGENT_ARCHITECTURE.md`
- **Code Structure**: `docs/development/PROJECT_STRUCTURE.md`, `docs/development/CODEBASE_ORGANIZATION.md`
- **Implementation**: `docs/MASTER_AGENT_GUIDE.md` (**START HERE**)

### For AI/LLM Agents
- **Master Guide**: `docs/MASTER_AGENT_GUIDE.md` - **PRIMARY ENTRY POINT**
- **Architecture**: `docs/architecture/AGENT_ARCHITECTURE.md`
- **LLM Patterns**: `docs/architecture/NO_HARDCODED_LOGIC.md`, `docs/architecture/LLM_DRIVEN_CHANGES.md`
- **Tool Definitions**: `prompts/tool_definitions.md`
- **Examples**: `prompts/few_shot_examples.md`, `docs/FEW_SHOT_EXAMPLES_WITH_COT.md`

### For Testing
- **Test Reports**: `docs/testing/COMPREHENSIVE_TEST_REPORT.md`
- **Test Methodology**: `TESTING_METHODOLOGY.md` (to be moved)
- **Test Index**: `tests/TEST_INDEX.md` (see tests directory)

---

## Quick Reference Tables

### Most Important Documents
| Document | Path | When to Use |
|---------|------|------------|
| Master Agent Guide | `docs/MASTER_AGENT_GUIDE.md` | **START HERE** for any coding task |
| Agent Architecture | `docs/architecture/AGENT_ARCHITECTURE.md` | Understanding system design |
| Agent Hierarchy | `docs/architecture/AGENT_HIERARCHY.md` | Finding available tools |
| Slash Commands | `docs/features/SLASH_COMMANDS.md` | User-facing commands |
| Project Structure | `docs/development/PROJECT_STRUCTURE.md` | Codebase navigation |

### By Agent Type
| Agent | Documentation | Examples |
|-------|---------------|----------|
| File Agent | `docs/agents/` (implicit) | `prompts/examples/file/` |
| Browser Agent | `docs/agents/BROWSER_AGENT.md` | `prompts/examples/web/` |
| Maps Agent | `docs/agents/MAPS_AGENT.md` | `prompts/examples/maps/` |
| Email Agent | `EMAIL_REPLY_FEATURE.md` | `prompts/examples/email/` |
| Stock Agent | `docs/agents/STOCK_AGENT.md` | `prompts/examples/stocks/` |
| Writing Agent | `docs/agents/WRITING_AGENT.md` | `prompts/examples/writing/` |

### By Topic
| Topic | Primary Docs | Related Docs |
|-------|--------------|--------------|
| Architecture | `docs/architecture/OVERVIEW.md` | `docs/architecture/AGENT_ARCHITECTURE.md` |
| Agents | `docs/MASTER_AGENT_GUIDE.md` | `docs/architecture/AGENT_HIERARCHY.md` |
| Prompts | `prompts/README.md` | `prompts/few_shot_examples.md` |
| Testing | `docs/testing/COMPREHENSIVE_TEST_REPORT.md` | `TESTING_METHODOLOGY.md` |
| Features | `docs/features/SLASH_COMMANDS.md` | `docs/features/ORCHESTRATOR_GUIDE.md` |

---

## Maintenance

This index should be updated when:
- New documentation files are added
- Files are moved or reorganized
- Documentation structure changes
- New categories are created

**Last Updated**: 2024 (during documentation reorganization)

---

## See Also

- [Test Index](../tests/TEST_INDEX.md) - Central test file repository
- [Main README](../README.md) - Project overview
- [Tests README](../tests/README.md) - Test documentation

