# Auto Mac Documentation

Welcome to the Auto Mac documentation! This directory contains all system documentation organized by topic.

## 📚 Documentation Structure

### 🚀 [Quickstart](quickstart/)
Get started quickly with Auto Mac.

- **[SETUP.md](quickstart/SETUP.md)** - Installation and configuration
- **[QUICK_START.md](quickstart/QUICK_START.md)** - Your first automation

### 🏗️ [Architecture](architecture/)
Understand how the system works.

- **[OVERVIEW.md](architecture/OVERVIEW.md)** - System architecture overview
- **[AGENT_ARCHITECTURE.md](architecture/AGENT_ARCHITECTURE.md)** - Multi-agent design
- **[NO_HARDCODED_LOGIC.md](architecture/NO_HARDCODED_LOGIC.md)** - LLM-driven verification
- **[LLM_DRIVEN_CHANGES.md](architecture/LLM_DRIVEN_CHANGES.md)** - Design decisions

### 🤖 [Agents](agents/)
Documentation for each specialized agent.

- **[BROWSER_AGENT.md](agents/BROWSER_AGENT.md)** - Web browsing and content extraction
- **[MAPS_AGENT.md](agents/MAPS_AGENT.md)** - Trip planning and navigation
- **[FINANCE_AGENT.md](agents/FINANCE_AGENT.md)** - Stock data and charts

### ✨ [Features](features/)
Key system features and capabilities.

- **[SLASH_COMMANDS.md](features/SLASH_COMMANDS.md)** - Direct agent access commands
- **[SLASH_COMMANDS_COMPLETE.md](features/SLASH_COMMANDS_COMPLETE.md)** - Complete verification
- **[SLASH_COMMAND_COVERAGE.md](features/SLASH_COMMAND_COVERAGE.md)** - Coverage report
- **[SLASH_COMMANDS_IMPLEMENTATION.md](features/SLASH_COMMANDS_IMPLEMENTATION.md)** - Technical details

### 🧪 [Testing](testing/)
Testing documentation and results.

- **[COMPREHENSIVE_TEST_REPORT.md](testing/COMPREHENSIVE_TEST_REPORT.md)** - Full test report (62% pass rate)
- **[TESTING_REPORT.md](testing/TESTING_REPORT.md)** - Testing summary
- **[INTEGRATION_TEST_RESULTS.md](testing/INTEGRATION_TEST_RESULTS.md)** - Integration tests

### 👨‍💻 [Development](development/)
Development documentation.

- **[PROJECT_STRUCTURE.md](development/PROJECT_STRUCTURE.md)** - Codebase organization
- **[PROJECT_OVERVIEW.md](development/PROJECT_OVERVIEW.md)** - Project overview
- **[IMPLEMENTATION_SUMMARY.md](development/IMPLEMENTATION_SUMMARY.md)** - Implementation notes

## 🔍 Quick Links

### For Users
- **Getting Started**: [quickstart/SETUP.md](quickstart/SETUP.md)
- **Slash Commands**: [features/SLASH_COMMANDS.md](features/SLASH_COMMANDS.md)
- **Agent List**: See [architecture/AGENT_ARCHITECTURE.md](architecture/AGENT_ARCHITECTURE.md)

### For Developers
- **Architecture**: [architecture/OVERVIEW.md](architecture/OVERVIEW.md)
- **Project Structure**: [development/PROJECT_STRUCTURE.md](development/PROJECT_STRUCTURE.md)
- **Testing**: [testing/COMPREHENSIVE_TEST_REPORT.md](testing/COMPREHENSIVE_TEST_REPORT.md)

### For AI/LLM Context
- **LLM-Driven Design**: [architecture/LLM_DRIVEN_CHANGES.md](architecture/LLM_DRIVEN_CHANGES.md)
- **No Hardcoded Logic**: [architecture/NO_HARDCODED_LOGIC.md](architecture/NO_HARDCODED_LOGIC.md)
- **Agent Architecture**: [architecture/AGENT_ARCHITECTURE.md](architecture/AGENT_ARCHITECTURE.md)

## 📖 Documentation by Topic

### System Design
- [Architecture Overview](architecture/OVERVIEW.md)
- [Multi-Agent System](architecture/AGENT_ARCHITECTURE.md)
- [LLM-Driven Decisions](architecture/LLM_DRIVEN_CHANGES.md)

### Key Features
- [Slash Commands](features/SLASH_COMMANDS.md) - Direct agent access
- [File Organization](features/) - LLM-based categorization
- [Trip Planning](agents/MAPS_AGENT.md) - Maps integration

### Agents
- **File Agent** - Document search, organization, ZIP, screenshots
- **Browser Agent** - Web search, navigation, content extraction
- **Presentation Agent** - Keynote, Pages creation
- **Email Agent** - Email composition and sending
- **Maps Agent** - Trip planning with stops
- **Finance Agent** - Stock data and charts

### Testing
- [Comprehensive Report](testing/COMPREHENSIVE_TEST_REPORT.md) - Full test results
- [Test Guide](../tests/README.md) - How to run tests

## 🎯 Key Concepts

### LLM-Driven Architecture
The system uses LLM reasoning for ALL decisions:
- ✅ NO hardcoded file patterns
- ✅ NO hardcoded routes or logic
- ✅ Semantic understanding
- ✅ Dynamic decision-making

See: [NO_HARDCODED_LOGIC.md](architecture/NO_HARDCODED_LOGIC.md)

### Multi-Agent System
13 specialized agents, 39+ tools:
- Each agent has clear responsibilities
- Agents work independently or coordinated
- Hierarchical tool organization

See: [AGENT_ARCHITECTURE.md](architecture/AGENT_ARCHITECTURE.md)

### Slash Commands
Direct agent access bypassing orchestrator:
- 2x faster execution
- Single-agent focused tasks
- Built-in help system

See: [SLASH_COMMANDS.md](features/SLASH_COMMANDS.md)

## 📦 Additional Resources

- **Main README**: [../README.md](../README.md)
- **Start Here**: [../START_HERE.md](../START_HERE.md)
- **Tests**: [../tests/](../tests/)
- **Source Code**: [../src/](../src/)

---

**Need help?** Check [quickstart/SETUP.md](quickstart/SETUP.md) or explore the documentation by topic above.
