# Quick Start: New /folder and /google Commands

## TL;DR

Two new commands are now available:
- **`/folder`** - Organize files and folders (LLM-driven, sandboxed)
- **`/google`** - Fast Google searches (official API, no browser)

## /folder Command (Ready to Use)

No setup required! Automatically sandboxed to `test_data` folder.

### Try It Now

```bash
# Start the UI
python src/ui/chat.py

# List folder contents
/folder list

# Organize with normalization (lowercase, underscores)
/folder organize alpha

# Or use the quick alias
/organize
```

### What It Does

- **Lists** folder contents (alphabetically sorted)
- **Normalizes** file/folder names:
  - `Music Notes/` → `music_notes/`
  - `photo 2023.jpg` → `photo_2023.jpg`
  - `Work Document.pdf` → `work_document.pdf`
- **Always asks confirmation** before making changes
- **Shows preview** with dry-run validation
- **Security**: Can only operate in `test_data` folder

### Test It

```bash
# Run comprehensive tests
python tests/test_folder_agent.py

# Try interactive demos
python tests/demo_folder_command.py
```

---

## /google Command (Requires Setup)

Fast, reliable Google searches using the official API (no browser, no CAPTCHA).

### Quick Setup (5 minutes)

#### 1. Get Google API Key

Visit: https://console.cloud.google.com/apis/credentials

1. Create new project (or select existing)
2. Enable "Custom Search API"
3. Create credentials → API key
4. Copy the API key

#### 2. Create Custom Search Engine

Visit: https://programmablesearchengine.google.com/

1. Click "Add"
2. Sites to search: `*.com` (or leave empty)
3. Enable "Search the entire web"
4. Create
5. Copy the "Search engine ID"

#### 3. Set Environment Variables

**Option A: In your shell profile** (~/.zshrc or ~/.bashrc):
```bash
export GOOGLE_API_KEY="your-api-key-here"
export GOOGLE_CSE_ID="your-cse-id-here"
```

**Option B: In .env file**:
```bash
# Copy example and edit
cp .env.example .env

# Edit .env and add:
GOOGLE_API_KEY=your-api-key-here
GOOGLE_CSE_ID=your-cse-id-here
```

#### 4. Install Dependency

```bash
pip install google-api-python-client
```

#### 5. Try It

```bash
# Start the UI
python src/ui/chat.py

# Search Google
/google Python async programming

# Or use the quick alias
/search latest AI news

# Site-specific search
/google site:github.com machine learning
```

### What It Does

- **Fast searches** (sub-second response)
- **Structured results** with titles, links, snippets
- **No CAPTCHA** issues
- **100 free queries/day** (then $5 per 1000)
- **LLM integration** - orchestrator can use it automatically

### Free Tier Limits

- **100 queries/day** free
- **No credit card** required for setup
- Sufficient for development/testing

---

## Examples

### Example 1: Organize Your Files

```
You: /folder list

Agent:
🔒 Folder scope: test_data

📁 Contents: 5 items

Music Notes/        dir     -           2 days ago
photo 2023.jpg      file    2.3 MB      today
Work Document.pdf   file    856 KB      1 week ago

You: /organize

Agent:
📋 Normalization Plan (2 changes needed)

CURRENT NAME        →  PROPOSED NAME
Music Notes/        →  music_notes/
photo 2023.jpg      →  photo_2023.jpg

Would you like me to apply these changes?

You: yes

Agent:
✅ Successfully renamed 2 items

Updated folder:
  music_notes/
  photo_2023.jpg
  work_document.pdf
```

### Example 2: Quick Google Search

```
You: /google Python async best practices

Agent:
Found 5 results in 0.21s

1. **Asyncio Best Practices** (realpython.com)
   Learn the best practices for Python asyncio...
   https://realpython.com/async-io-python/

2. **Python Async/Await Guide** (docs.python.org)
   Official documentation on async programming...
   https://docs.python.org/3/library/asyncio.html

[Results 3-5...]
```

### Example 3: Search Specific Site

```
You: /search site:stackoverflow.com python asyncio

Agent:
Searching stackoverflow.com for "python asyncio"

1. **Understanding Python Asyncio** (stackoverflow.com)
   Q: How does asyncio work internally?
   https://stackoverflow.com/questions/12345...

2. **Asyncio vs Threading** (stackoverflow.com)
   Q: When should I use asyncio vs threads?
   https://stackoverflow.com/questions/67890...
```

---

## Command Reference

### /folder Commands

| Command | Description |
|---------|-------------|
| `/folder list` | Show all files and folders |
| `/folder organize alpha` | Normalize names (lowercase, underscores) |
| `/folder check scope` | Show sandbox boundaries |
| `/organize` | Quick alias for organize alpha |

### /google Commands

| Command | Description |
|---------|-------------|
| `/google <query>` | Search Google |
| `/search <query>` | Quick alias for Google search |
| `/google site:<domain> <query>` | Search specific site |

---

## Troubleshooting

### /folder Issues

**Error: "Path outside sandbox"**
- ✅ This is working as designed
- All operations restricted to `test_data` folder
- Edit `config.yaml` to change sandbox folder

**Error: "Conflict: destination already exists"**
- File with normalized name already exists
- Options: Skip, manual rename, or cancel

### /google Issues

**Error: "Google API credentials not configured"**
- Missing `GOOGLE_API_KEY` or `GOOGLE_CSE_ID`
- Follow setup steps above
- Verify with: `echo $GOOGLE_API_KEY`

**Error: "Quota exceeded"**
- Free tier limit (100/day) reached
- Wait until midnight PT for reset
- Or enable billing in Google Cloud Console

**Error: "google-api-python-client not installed"**
- Run: `pip install google-api-python-client`

---

## Testing

### Test /folder

```bash
# Comprehensive test suite
python tests/test_folder_agent.py

# Should output:
# ✅ PASS: Sandbox Validation
# ✅ PASS: Folder Listing
# ✅ PASS: Plan Alpha
# ✅ PASS: Apply Dry-Run
# ✅ PASS: Apply Actual
# ✅ PASS: Conflict Handling
# ✅ PASS: Agent Initialization
# ✅ PASS: Tool Execution
# ✅ PASS: Complete Workflow
#
# Total: 9 tests
# Passed: 9
# Failed: 0

# Interactive demos
python tests/demo_folder_command.py
```

### Test /google

```bash
# Test with Python
python -c "
from src.agent.google_agent import GoogleAgent
from src.utils import load_config

agent = GoogleAgent(load_config())
result = agent.execute('google_search', {
    'query': 'test query',
    'num_results': 3
})

if result.get('error'):
    print(f'❌ Error: {result[\"error_message\"]}')
else:
    print(f'✅ Found {result[\"num_results\"]} results')
    for r in result['results']:
        print(f'  - {r[\"title\"]}')
"

# Test via UI
# python src/ui/chat.py
# /google test query
```

---

## Documentation

Full documentation available:

- **`docs/features/FOLDER_COMMAND.md`** - Complete /folder guide
- **`docs/features/GOOGLE_SEARCH_API.md`** - Complete /google guide
- **`IMPLEMENTATION_SUMMARY.md`** - Technical implementation details

---

## What's Different from Existing Commands?

### /folder vs /files

| Feature | `/folder` | `/files` |
|---------|-----------|----------|
| **Purpose** | Organize folder structure | Search & organize file content |
| **Scope** | Folder/file names | Document text content |
| **Operations** | Rename, normalize | Search, extract, screenshot, zip |
| **LLM Role** | Tool selection | Content categorization |

Both work together:
- `/files` finds documents by content
- `/folder` organizes by naming structure

### /google vs /browse

| Feature | `/google` (NEW) | `/browse` (Existing) |
|---------|-----------------|----------------------|
| **Method** | Official Google API | Browser automation |
| **Speed** | ⚡ <1s | 🐢 3-5s |
| **Reliability** | ✅ Always works | ⚠️ CAPTCHA risk |
| **Content** | Snippets only | Full page |
| **Cost** | API quota (100 free/day) | Free |
| **Setup** | Requires credentials | None |

Use `/google` for quick searches, `/browse` for full content.

---

## Integration with Orchestrator

Both commands work standalone AND are available to the orchestrator:

```
User: "Search Google for Python tutorials and organize my
       local Python PDFs into a clean folder structure"

Orchestrator will automatically:
1. Use google_search tool (from GoogleAgent)
2. Use search_documents tool (from FileAgent)
3. Use folder_plan_alpha + folder_apply (from FolderAgent)

No need to use slash commands - orchestrator has access to all tools!
```

---

## Summary

### ✅ Ready to Use Now

- `/folder` command (no setup)
- Test suite available
- Interactive demos

### ⚙️ Requires 5-Min Setup

- `/google` command
- Get API key from Google Cloud
- Create Custom Search Engine
- Set 2 environment variables

### 📚 Full Documentation

- Architecture details
- Security guarantees
- API limits & pricing
- Troubleshooting guides

**Total New Tools**: 7 (4 folder + 3 google)
**Total New Code**: 3,000+ lines
**Breaking Changes**: 0

Enjoy the new commands! 🚀