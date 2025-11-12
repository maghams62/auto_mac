# Test Index

**Central repository for all Mac Automation Assistant test files**

This index provides a comprehensive mapping of all test files organized by category, agent, feature, and test type. Use this as the primary reference for finding tests without searching the entire codebase.

---

## Quick Navigation

- [Agent Tests](#agent-tests)
- [Feature Tests](#feature-tests)
- [Workflow Tests](#workflow-tests)
- [System Tests](#system-tests)
- [Integration Tests](#integration-tests)
- [Debug & Fix Tests](#debug--fix-tests)
- [Test Data](#test-data)
- [Test Scripts](#test-scripts)

---

## Agent Tests

### File Agent
| File | Description | Type |
|------|-------------|------|
| `test_file_organize.py` | File organization tests | Unit |
| `test_document_search_fix.py` | Document search functionality | Unit |
| `test_duplicates_simple.py` | Duplicate file detection | Unit |

### Browser Agent
| File | Description | Type |
|------|-------------|------|
| `test_google_agent.py` | Google search agent tests | Unit |
| `test_google_search.py` | Google search functionality | Unit |
| `test_google_finance.py` | Google Finance integration | Unit |
| `test_bluesky_browser.py` | Bluesky browser integration | Integration |
| `test_direct_browser_stock.py` | Browser-based stock tests | Integration |

### Maps Agent
| File | Description | Type |
|------|-------------|------|
| `test_maps_agent.py` | Maps agent core functionality | Unit |
| `test_maps_applescript.py` | AppleScript Maps automation | Unit |
| `test_maps_improved.py` | Improved Maps functionality | Unit |
| `test_maps_enhancements.py` | Maps enhancements | Unit |
| `test_maps_url_display.py` | Maps URL display | Unit |
| `test_maps_url_normalization.py` | URL normalization | Unit |
| `test_llm_driven_maps.py` | LLM-driven Maps planning | Integration |
| `test_maps_with_agent.py` | Maps with agent integration | Integration |
| `test_auto_send_maps.py` | Auto-send Maps functionality | Integration |
| `test_imessage_maps.py` | iMessage Maps integration | Integration |
| `test_trip_planning_la_sd.py` | Trip planning (LA to SD) | Integration |
| `test_transit_query.py` | Transit query tests | Unit |

### Email Agent
| File | Description | Type |
|------|-------------|------|
| `test_email_scenarios.py` | Email scenario tests | Integration |
| `test_email_intent.py` | Email intent parsing | Unit |
| `test_email_reading.py` | Email reading functionality | Unit |
| `test_email_reply.py` | Email reply functionality | Unit |

### Stock/Finance Agent
| File | Description | Type |
|------|-------------|------|
| `test_new_stock_agent.py` | Stock agent tests | Unit |
| `test_stock_capture.py` | Stock data capture | Unit |
| `test_stock_chart_capture.py` | Stock chart capture | Unit |
| `test_stock_report_system.py` | Stock report generation | Integration |
| `test_stock_workflow_final.py` | Final stock workflow | Integration |
| `test_stock_workflow_fix.py` | Stock workflow fixes | Debug |
| `test_complete_stock_presentation.py` | Stock presentation creation | Integration |
| `test_hybrid_stock_workflow.py` | Hybrid stock workflow | Integration |
| `test_enriched_nvidia.py` | Enriched stock data (NVIDIA) | Integration |
| `test_nvidia_stock.py` | NVIDIA stock tests | Unit |
| `test_nvidia_report.py` | NVIDIA report generation | Integration |

### Writing Agent
| File | Description | Type |
|------|-------------|------|
| `test_writing_agent.py` | Writing agent tests | Unit |
| `test_writing_agent_planning.py` | Writing agent planning | Unit |

### Folder Agent
| File | Description | Type |
|------|-------------|------|
| `test_folder_agent.py` | Folder agent tests | Unit |
| `test_folder_slash_reply.py` | Folder slash command reply | Unit |
| `test_folder_workflow_queries.py` | Folder workflow queries | Integration |
| `test_folder_workflows.py` | Folder workflow tests | Integration |
| `test_dotards_group.py` | Dotards group tests | Unit |
| `test_dotards_read.py` | Dotards read tests | Unit |

### Twitter/X Agent
| File | Description | Type |
|------|-------------|------|
| `test_twitter_agent.py` | Twitter agent tests | Unit |
| `test_x_command.py` | X (Twitter) command tests | Unit |

### Bluesky Agent
| File | Description | Type |
|------|-------------|------|
| `test_bluesky_agent.py` | Bluesky agent tests | Unit |
| `test_bluesky_command.py` | Bluesky command tests | Unit |
| `test_bluesky_integration.py` | Bluesky integration tests | Integration |

### WhatsApp Agent
| File | Description | Type |
|------|-------------|------|
| `test_whatsapp_simple.py` | Simple WhatsApp tests | Unit |
| `test_whatsapp_integration.py` | WhatsApp integration | Integration |
| `test_whatsapp_comprehensive.py` | Comprehensive WhatsApp tests | Integration |
| `test_whatsapp_functional.py` | WhatsApp functional tests | Integration |
| `verify_whatsapp.py` | WhatsApp verification script | Verification |

### Spotify Agent
| File | Description | Type |
|------|-------------|------|
| `test_spotify_functional.py` | Spotify functional tests | Unit |
| `test_spotify_slash.py` | Spotify slash command tests | Unit |
| `test_play_music_natural.py` | Natural language music playback | Integration |

### Celebration Agent
| File | Description | Type |
|------|-------------|------|
| `test_confetti.py` | Confetti celebration tests | Unit |
| `test_confetti_comprehensive.py` | Comprehensive confetti tests | Integration |

### Screen/Vision Agent
| File | Description | Type |
|------|-------------|------|
| `test_screenshot_auto.py` | Automatic screenshot tests | Unit |
| `test_screenshot_fix.py` | Screenshot fix tests | Debug |
| `test_keynote_image_debug.py` | Keynote image debug | Debug |

---

## Feature Tests

### Slash Commands
| File | Description | Type |
|------|-------------|------|
| `test_slash_commands.py` | Slash command tests | Unit |
| `test_slash_commands_fixed.py` | Fixed slash command tests | Debug |
| `test_slash_parsing.py` | Slash command parsing | Unit |
| `test_clear_command.py` | Clear command tests | Unit |

### Help System
| File | Description | Type |
|------|-------------|------|
| `test_help_registry.py` | Help registry tests | Unit |

### Configuration
| File | Description | Type |
|------|-------------|------|
| `test_config_api.py` | Config API tests | Unit |
| `test_config_update.py` | Config update tests | Unit |

### Session & Memory
| File | Description | Type |
|------|-------------|------|
| `test_session_memory.py` | Session memory tests | Unit |

### WebSocket
| File | Description | Type |
|------|-------------|------|
| `test_websocket_client.py` | WebSocket client tests | Integration |

---

## Workflow Tests

### Complete Workflows
| File | Description | Type |
|------|-------------|------|
| `test_complete_workflow.py` | Complete workflow tests | Integration |
| `test_complete_workflow_msft.py` | Microsoft workflow tests | Integration |
| `test_full_flow.py` | Full flow tests | Integration |
| `test_natural_language_flow.py` | Natural language flow | Integration |

### Orchestration
| File | Description | Type |
|------|-------------|------|
| `test_comprehensive_orchestration.py` | Comprehensive orchestration | Integration |
| `test_orchestrator_simple.py` | Simple orchestrator tests | Unit |

### Parsing & Planning
| File | Description | Type |
|------|-------------|------|
| `test_all_parsing_scenarios.py` | All parsing scenarios | Unit |
| `test_parsing_fix.py` | Parsing fix tests | Debug |
| `test_prompt_rules.py` | Prompt rules tests | Unit |
| `test_prompt_validation.py` | Prompt validation | Unit |
| `test_template_resolution.py` | Template resolution | Unit |
| `test_variable_resolution.py` | Variable resolution | Unit |

---

## System Tests

### Comprehensive System Tests
| File | Description | Type |
|------|-------------|------|
| `test_comprehensive_system.py` | Full system tests | System |
| `test_agents_comprehensive.py` | Comprehensive agent tests | System |
| `test_all_tools.py` | All tools tests | System |
| `test_direct_agent.py` | Direct agent API tests | System |
| `test_agent_search.py` | Agent search tests | System |
| `test_sub_agent_functionality.py` | Sub-agent functionality | System |

---

## Integration Tests

### Multi-Agent Integration
| File | Description | Type |
|------|-------------|------|
| `test_both_integrations.py` | Multiple integrations | Integration |
| `test_phoenix_la.py` | Phoenix LA integration | Integration |

### Tool Integration
| File | Description | Type |
|------|-------------|------|
| `test_tool_parameter_index.py` | Tool parameter indexing | Integration |

---

## Debug & Fix Tests

### Fix Validation Tests
| File | Description | Type |
|------|-------------|------|
| `test_fix.py` | General fix tests | Debug |
| `test_status_fix.py` | Status fix tests | Debug |
| `test_search_debug.py` | Search debug tests | Debug |

---

## Test Data

### Test Data Directories
| Directory | Path | Description |
|-----------|------|-------------|
| Test Data | `tests/data/test_data/` | General test data files |
| Test Documents | `tests/data/test_doc/` | Test document files |
| Test Docs | `tests/data/test_docs/` | Additional test documents |

### Test Logs
| Directory | Path | Description |
|-----------|------|-------------|
| Test Logs | `tests/logs/` | Test execution logs |

---

## Test Scripts

### Execution Scripts
| File | Description |
|------|-------------|
| `run_tests.sh` | Main test runner script |
| `quick_tool_tests.sh` | Quick tool test runner |
| `demo_all_slash_commands.py` | Demo all slash commands |
| `demo_folder_command.py` | Demo folder command |

### Import Checks
| Directory | Path | Description |
|-----------|------|-------------|
| Import Checks | `tests/import_checks/` | Import validation tests |
| - `test_critical_imports.py` | Critical imports check |
| - `check_all_imports.py` | All imports check |
| - `README.md` | Import checks documentation |

---

## Test Organization by Type

### Unit Tests
Tests individual components and agents in isolation:
- Agent-specific tests (file, browser, maps, email, etc.)
- Feature tests (slash commands, help system, config)
- Parsing and validation tests
- Tool-specific tests

### Integration Tests
Tests interactions between components:
- Multi-agent workflows
- Complete workflows
- Cross-agent integration
- API integrations

### System Tests
End-to-end tests of the entire system:
- Comprehensive system tests
- All tools tests
- Direct agent API tests
- Full flow tests

### Debug Tests
Tests for specific fixes and debugging:
- Fix validation tests
- Debug scenario tests
- Status fix tests

---

## Running Tests

### Run All Tests
```bash
python -m pytest tests/
```

### Run Specific Category
```bash
# Agent tests
python -m pytest tests/test_*_agent.py

# Integration tests
python -m pytest tests/test_*_integration.py tests/test_complete_*.py

# System tests
python -m pytest tests/test_comprehensive_*.py tests/test_all_*.py
```

### Run with Scripts
```bash
./tests/run_tests.sh
./tests/quick_tool_tests.sh
```

### Run Specific Test File
```bash
python tests/test_direct_agent.py
python tests/test_maps_agent.py
```

---

## Test Data Paths

After reorganization, test data is located at:
- `tests/data/test_data/` - General test data
- `tests/data/test_doc/` - Test documents
- `tests/data/test_docs/` - Additional test documents

**Note**: Some tests may reference test data with relative paths. After moving test data to `tests/data/`, tests should use paths like:
- `tests/data/test_data/...`
- `tests/data/test_doc/...`
- `tests/data/test_docs/...`

---

## Quick Reference

### Most Important Tests
| Test | Path | When to Use |
|------|------|------------|
| Comprehensive System | `test_comprehensive_system.py` | Full system validation |
| All Tools | `test_all_tools.py` | Tool coverage verification |
| Direct Agent | `test_direct_agent.py` | Agent API testing |
| Complete Workflow | `test_complete_workflow.py` | End-to-end workflows |

### By Agent
| Agent | Primary Test | Additional Tests |
|-------|-------------|-----------------|
| File | `test_file_organize.py` | `test_document_search_fix.py` |
| Browser | `test_google_agent.py` | `test_google_search.py`, `test_bluesky_browser.py` |
| Maps | `test_maps_agent.py` | `test_maps_applescript.py`, `test_llm_driven_maps.py` |
| Email | `test_email_scenarios.py` | `test_email_intent.py`, `test_email_reply.py` |
| Stock | `test_new_stock_agent.py` | `test_stock_workflow_final.py`, `test_hybrid_stock_workflow.py` |
| Writing | `test_writing_agent.py` | `test_writing_agent_planning.py` |
| Folder | `test_folder_agent.py` | `test_folder_workflows.py` |

### By Feature
| Feature | Tests |
|---------|-------|
| Slash Commands | `test_slash_commands.py`, `test_slash_parsing.py` |
| Workflows | `test_complete_workflow.py`, `test_full_flow.py` |
| Orchestration | `test_comprehensive_orchestration.py` |
| Parsing | `test_all_parsing_scenarios.py`, `test_parsing_fix.py` |

---

## Maintenance

This index should be updated when:
- New test files are added
- Tests are moved or reorganized
- Test categories change
- New test types are introduced

**Last Updated**: 2024 (during test reorganization)

---

## See Also

- [Documentation Index](../docs/DOCUMENTATION_INDEX.md) - Central documentation repository
- [Tests README](README.md) - Test documentation
- [Main README](../README.md) - Project overview

