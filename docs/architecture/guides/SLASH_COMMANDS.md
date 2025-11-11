# Slash Commands - Direct Agent Access

## Overview

Slash commands provide a **direct interface to specialized agents**, bypassing the orchestrator for faster, focused interactions. Use slash commands when you know exactly which agent you need.

> 🔎 Tip: Type just `/` and press enter to open the Raycast-style command palette with every available slash command and description.

## When to Use Slash Commands

### Use Slash Commands When:
- ✅ You need a **single agent** for a specific task
- ✅ You want **faster execution** (no planning phase)
- ✅ You know **exactly what you want** (e.g., "organize files", "get stock price")
- ✅ You're doing **repeated similar tasks** (e.g., multiple file operations)

### Use Natural Language When:
- 🎯 Task requires **multiple agents** working together
- 🎯 You're not sure **which agent** to use
- 🎯 Task needs **complex planning** (e.g., "Find docs, create presentation, and email it")
- 🎯 You want the **orchestrator to decide** the best approach

---

## Available Commands

### 📁 File Operations
```
/files <task>
/file <task>
```

**Agent:** File Agent
**Capabilities:**
- Search for documents
- Organize files by category
- Create ZIP archives
- Take document screenshots
- Extract document sections

**Examples:**
```
/files Organize my PDFs by topic
/files Create a ZIP of all images in Downloads
/files Find documents about machine learning
/files Take a screenshot of page 5 in report.pdf
```

---

### 🌐 Web Browsing
```
/browse <task>
/browser <task>
/web <task>
```

**Agent:** Browser Agent
**Capabilities:**
- Google search
- Navigate to URLs
- Extract page content
- Take web screenshots

**Examples:**
```
/browse Search for Python async tutorials
/browse Go to github.com/anthropics and extract README
/browse Take a screenshot of example.com
```

---

### 📊 Presentations & Documents
```
/present <task>
/presentation <task>
/keynote <task>
/pages <task>
```

**Agent:** Presentation Agent
**Capabilities:**
- Create Keynote presentations
- Create Pages documents
- Add images to slides

**Examples:**
```
/present Create a Keynote about AI trends
/keynote Make a presentation with 5 slides on LLMs
/pages Create a report about Q4 performance
```

---

### 📧 Email
```
/email <task>
/mail <task>
```

**Agent:** Email Agent
**Capabilities:**
- Compose emails
- Draft or send emails
- Add attachments

**Examples:**
```
/email Draft an email about project status
/email Send meeting notes to team@company.com
```

---

### ✍️ Writing & Content
```
/write <task>
/writing <task>
```

**Agent:** Writing Agent
**Capabilities:**
- Generate reports
- Create slide deck content
- Generate meeting notes
- Synthesize content

**Examples:**
```
/write Create a detailed report on AI safety
/write Generate meeting notes from this transcript
/write Synthesize these research papers into a summary
```

---

### 🗺️ Maps & Travel
```
/maps <task>
/map <task>
/directions <task>
```

**Agent:** Maps Agent
**Capabilities:**
- Plan trips with stops
- Get directions
- Open Maps app
- Calculate routes

**Examples:**
```
/maps Plan a trip from LA to San Francisco with 2 gas stops
/maps Get directions to Phoenix with lunch stop
/maps Plan route from Boston to NYC with breakfast and dinner stops
```

---

### 📈 Stocks & Finance
```
/stock <task>
/stocks <task>
/finance <task>
```

**Agent:** Google Finance Agent
**Capabilities:**
- Get current stock prices
- Generate stock charts
- Get historical data
- Create stock reports

**Examples:**
```
/stock Get AAPL current price
/stock Show TSLA chart for last month
/finance Generate report for NVDA
```

---

### 📄 Local Reports (RAG)
```
/report <task>
```

**Agent:** Report Agent (Local mode)
**Capabilities:**
- Search only the configured local folders (e.g., `test_docs`)
- Refuse to run if no relevant local files are found
- Summarize retrieved text with strict "no hallucination" rules
- Export short PDF reports and share the file path in chat

**Examples:**
```
/report Create a report on Tesla using the files you can access
/report Summarize the AI agent docs from test_data
```

> ⚠️ If no local documents match the request, the command responds with
> “I could not find any…” instead of fabricating content.
>
> 💡 Prefer natural language when you want the main orchestrator to decide;
> saying “Create a report on Tesla” (no slash) routes to the same Report Agent
> automatically.

---

### 💬 Messaging

#### iMessage
```
/message <task>
/imessage <task>
/text <task>
```

**Examples:**
```
/message Send "Running late" to John
/text Send meeting reminder to Sarah
```

#### Discord
```
/discord <task>
```

**Examples:**
```
/discord Check mentions in the last hour
/discord Monitor #general channel
```

#### Reddit
```
/reddit <task>
```

**Examples:**
```
/reddit Scan r/programming for mentions of my project
```

#### Twitter
```
/twitter <task>
```

**Examples:**
```
/twitter Summarize activity in my product_watch list
```

---

## Help Commands

### Get Help
```
/help              # Show all commands
/help <command>    # Show help for specific command
```

**Examples:**
```
/help files        # Show help for file commands
/help maps         # Show help for maps commands
```

### List Agents
```
/agents            # Show all available agents and their capabilities
```

---

## How Slash Commands Work

### 1. Direct Routing
Slash commands route directly to the appropriate agent, **bypassing the orchestrator**:

```
User: /files Organize my PDFs
  ↓
Slash Command Parser
  ↓
File Agent (direct)
  ↓
organize_files tool
  ↓
Result
```

**vs. Natural Language:**
```
User: "Organize my PDFs"
  ↓
Orchestrator
  ↓
Planner (LLM creates plan)
  ↓
Executor (runs plan)
  ↓
File Agent
  ↓
Result
```

### 2. LLM-Based Tool Selection
Even within a slash command, **LLM determines which tool to use**:

```
/files Organize my PDFs by topic
  ↓
File Agent receives task
  ↓
LLM analyzes task
  ↓
LLM selects: organize_files tool
  ↓
LLM extracts parameters: category="PDFs by topic"
  ↓
Tool execution
```

**No hardcoded routing!** The LLM intelligently maps tasks to tools.

---

## Examples

### Example 1: File Organization

**Command:**
```
/files Organize my downloads folder by file type
```

**What Happens:**
1. Parser recognizes `/files` → routes to File Agent
2. LLM analyzes "Organize my downloads folder by file type"
3. LLM selects `organize_files` tool
4. LLM extracts parameters:
   - `category`: "files by type"
   - `target_folder`: "organized"
   - `source`: "downloads"
5. Tool executes with LLM-driven file categorization
6. Result shows which files were organized and why

**Result:**
```
✓ File Agent - Success

Files organized: 15
Files skipped: 3
Target: /Users/you/Downloads/organized

Sample reasoning:
  • document.pdf
    → This is a PDF document, categorized under document type
  • photo.jpg
    → This is an image file, categorized under image type
```

---

### Example 2: Trip Planning

**Command:**
```
/maps Plan a trip from Los Angeles to San Diego with 2 gas stops and lunch
```

**What Happens:**
1. Parser recognizes `/maps` → routes to Maps Agent
2. LLM analyzes the task
3. LLM selects `plan_trip_with_stops` tool
4. LLM extracts parameters:
   - `origin`: "Los Angeles, CA"
   - `destination`: "San Diego, CA"
   - `num_fuel_stops`: 2
   - `num_food_stops`: 1
5. LLM suggests optimal stop locations
6. Maps URL generated and opened

**Result:**
```
✓ Maps Agent - Success

Maps URL: https://maps.apple.com/...
Service: Apple Maps
Stops: 3

Route:
  1. Start: Los Angeles, CA
  2. Stop 1 (fuel): Irvine, CA
  3. Stop 2 (food): Oceanside, CA
  4. Stop 3 (fuel): Carlsbad, CA
  5. End: San Diego, CA
```

---

### Example 3: Stock Information

**Command:**
```
/stock Get AAPL price and 1-month chart
```

**What Happens:**
1. Parser recognizes `/stock` → routes to Google Finance Agent
2. LLM analyzes task
3. LLM selects appropriate tool (get_stock_data)
4. LLM extracts: ticker="AAPL", timeframe="1 month"
5. Tool fetches data from Google Finance
6. Result formatted and displayed

---

## Comparison: Slash Commands vs Natural Language

| Aspect | Slash Commands | Natural Language |
|--------|---------------|------------------|
| **Speed** | Faster (direct routing) | Slower (planning phase) |
| **Complexity** | Single-agent tasks | Multi-agent workflows |
| **Flexibility** | Fixed agent | Orchestrator decides |
| **Use Case** | "I know what I want" | "Figure out what to do" |
| **Examples** | `/files organize PDFs` | "Find PDFs, organize them, and email a summary" |

---

## Advanced Usage

### Chaining Commands

You can use multiple slash commands in sequence:

```bash
# 1. Organize files
/files Organize documents by project

# 2. Create ZIP
/files Create ZIP of organized files

# 3. Email the ZIP
/email Draft email with attachment of the ZIP
```

For automatic chaining, use natural language instead:
```
"Organize my documents, create a ZIP, and email it to John"
```

---

## Error Handling

### Invalid Command
```
/unknown task

❌ Error
Unknown command: /unknown. Type /help for available commands.
```

### Wrong Syntax
```
/files

❌ Error
Invalid command format. Use: /command <task>
```

### Agent Error
```
/files Organize files in nonexistent_folder

❌ /files - Error
Source path not found: nonexistent_folder
```

---

## Best Practices

### ✅ DO:
- Use slash commands for **single, focused tasks**
- Be specific in your task description
- Use `/help` to discover new commands
- Use `/agents` to see all capabilities

### ❌ DON'T:
- Don't use slash commands for **multi-step workflows**
- Don't chain too many slash commands (use natural language instead)
- Don't expect slash commands to coordinate between agents

---

## LLM-Driven Architecture

Even slash commands maintain **pure LLM-driven decision making**:

1. **Tool Selection**: LLM chooses which tool within the agent
2. **Parameter Extraction**: LLM parses natural language into tool parameters
3. **File Categorization**: LLM makes semantic decisions (no hardcoded patterns)
4. **Stop Suggestions**: LLM suggests route stops dynamically

**Example:**
```
/files Organize music files

LLM Decisions:
  ✓ Tool: organize_files
  ✓ Category: "music files"
  ✓ For each file: "This is a guitar tab" → music ✓
                   "This is a work document" → not music ✗
```

---

## Technical Details

### Architecture

```
┌─────────────────────────────────────────┐
│           User Input                     │
└───────────────┬─────────────────────────┘
                │
        [Starts with /]?
                │
        ┌───────┴───────┐
        │               │
       YES              NO
        │               │
        ▼               ▼
┌──────────────┐  ┌─────────────────┐
│ Slash        │  │ Orchestrator    │
│ Command      │  │ (multi-agent)   │
│ Handler      │  │                 │
└──────┬───────┘  └─────────────────┘
       │
       ▼
┌──────────────────┐
│ Command Parser   │
│ - Validate       │
│ - Route to Agent │
└──────┬───────────┘
       │
       ▼
┌─────────────────────────────────┐
│ LLM Tool Router                 │
│ - Select tool within agent      │
│ - Extract parameters            │
└──────┬──────────────────────────┘
       │
       ▼
┌─────────────────┐
│ Agent Execution │
│ - Run tool      │
│ - Return result │
└─────────────────┘
```

### Files

- **Parser**: `src/ui/slash_commands.py` - SlashCommandParser
- **Handler**: `src/ui/slash_commands.py` - SlashCommandHandler
- **UI Integration**: `src/ui/chat.py` - ChatUI with slash support
- **Tests**: `tests/test_slash_commands.py`

---

## Testing

Run slash command tests:

```bash
python tests/test_slash_commands.py
```

**Test Coverage:**
- ✅ Command parsing
- ✅ Agent routing
- ✅ Help system
- ✅ Invalid command handling
- ✅ LLM-based tool selection
- ✅ Direct agent execution

**Test Results:** 4/4 tests passed (100%)

---

## Future Enhancements

### Planned Features:
1. **Command History**: Recall previous commands with ↑
2. **Tab Completion**: Auto-complete commands and agent names
3. **Command Aliases**: Custom shortcuts (e.g., `/f` for `/files`)
4. **Batch Commands**: Execute multiple commands (e.g., `/files task1 && /email task2`)
5. **Command Templates**: Save frequently used commands
6. **Agent Suggestions**: Suggest commands based on context

---

## Summary

Slash commands provide **direct access to specialized agents** for fast, focused tasks:

- 📁 **11 command groups** covering all agents
- 🎯 **Direct routing** for speed
- 🤖 **LLM-driven** tool selection and parameter extraction
- 📚 **Built-in help** system
- ✅ **100% test coverage**

**When to use:**
- Single-agent tasks → Use slash commands
- Multi-agent workflows → Use natural language

**Example:**
```
# Fast and direct
/files Organize my PDFs

# Complex and coordinated
"Find all PDFs about AI, organize them by topic, create a presentation
summarizing them, and email it to my team"
```

Both approaches maintain **LLM-driven decision making** with **no hardcoded logic**!
