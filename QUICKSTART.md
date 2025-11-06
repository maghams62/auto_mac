# Quick Start Guide

Get the Mac Automation Assistant running in 3 minutes!

## Step 1: Install Dependencies

```bash
# Create virtual environment
python3 -m venv venv

# Activate it
source venv/bin/activate

# Install all dependencies
pip install -r requirements.txt
```

This will install:
- OpenAI API client
- FAISS for vector search
- PDF/DOCX parsers
- Rich for terminal UI
- And more...

## Step 2: Verify API Key

Your API key is already configured in `.env`:
```bash
cat .env
# Should show: OPENAI_API_KEY=sk-proj-...
```

## Step 3: Configure Document Folders (Optional)

Edit `config.yaml` to choose which folders to index:

```yaml
documents:
  folders:
    - "~/Documents"     # Your main documents
    - "~/Downloads"     # Downloaded files
    # Add more folders as needed
```

## Step 4: Run the Application

```bash
# Easy way (handles everything automatically)
./run.sh

# Or manually
python main.py
```

You should see:
```
Mac Automation Assistant
========================

AI-powered document search and email automation for macOS.

Commands:
- Type your request naturally
- /index - Reindex all documents
- /test - Test system components
- /help - Show help
- /quit - Exit
```

## Step 5: Index Your Documents

Type this command in the app:
```
/index
```

Wait for indexing to complete (this may take a few minutes depending on how many documents you have).

## Step 6: Try It Out!

Now try a natural language request:

```
"Find my resume and send me just the first page"
```

or

```
"Get me the Tesla Autopilot document — just the summary"
```

The app will:
1. 🔍 Search your documents semantically
2. 📄 Extract the requested section
3. ✉️ Compose a draft email in Mail.app

## Test the System

Run system tests:
```
/test
```

You should see:
- ✓ Mail App
- ✓ Index Loaded
- ✓ OpenAI API

## Troubleshooting

### "Import dotenv could not be resolved"
This is just an IDE warning before installing dependencies. Run:
```bash
pip install -r requirements.txt
```

### "No documents indexed"
Run `/index` command inside the app.

### "OpenAI API error"
Check your API key in `.env` file.

### "Mail.app not accessible"
- macOS will prompt for permission
- Allow automation access in System Preferences

## Example Requests

```
"Send me the Q3 earnings report — page 5"

"Find the contract with Acme Corp and email section 3"

"Get the machine learning paper, just the introduction"

"Find my presentation about Tesla and send the summary"
```

## Next Steps

- Read [README.md](README.md) for complete documentation
- Customize `config.yaml` for your needs
- Add more document folders
- Explore advanced features

---

Need help? Run `/help` in the app or check the full [README.md](README.md)!
