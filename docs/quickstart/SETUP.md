# Quick Setup Guide

## Prerequisites Checklist

- [ ] macOS 10.15 or later
- [ ] Python 3.8+ installed
- [ ] OpenAI API key (get one at https://platform.openai.com)
- [ ] Mail.app configured with at least one email account

## 5-Minute Setup

### 1. Install Dependencies

```bash
# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# Install packages
pip install -r requirements.txt
```

### 2. Configure OpenAI API Key

```bash
# Option A: Environment variable
export OPENAI_API_KEY='sk-your-key-here'

# Option B: .env file
cp .env.example .env
# Edit .env and add your key
```

### 3. Configure Document Folders

Edit `config.yaml` and set the folders you want to index:

```yaml
documents:
  folders:
    - "~/Documents"
    - "~/Downloads"
    # Add more folders as needed
```

### 4. Run the Application

```bash
# Using the startup script (recommended)
./run.sh

# Or directly
python main.py
```

### 5. Index Your Documents

Once the app is running, type:
```
/index
```

Wait for indexing to complete. This may take a few minutes depending on how many documents you have.

### 6. Test It Out!

Try a request like:
```
"Find my resume and send me just the first page"
```

## Troubleshooting First Run

### Python Version Issues

```bash
# Check Python version
python3 --version

# Should be 3.8 or higher
```

### Permission Errors for Mail.app

- macOS will prompt you to allow automation access
- Go to: System Preferences → Security & Privacy → Privacy → Automation
- Enable access for Terminal or your Python application

### FAISS Installation Issues

If `faiss-cpu` fails to install:

```bash
# Try using conda instead
conda install -c pytorch faiss-cpu

# Or use pip with specific version
pip install faiss-cpu==1.7.4
```

### OpenAI API Rate Limits

If you hit rate limits during indexing:
- Wait a few minutes and try again
- Consider indexing smaller folders first
- Contact OpenAI to increase your rate limits

## Verification

Run the test command to verify everything works:
```
/test
```

You should see:
- ✓ Mail App
- ✓ Index Loaded
- ✓ OpenAI API

## Next Steps

1. Review the full [README.md](README.md) for detailed usage
2. Try the example requests
3. Customize `config.yaml` for your needs
4. Set up a keyboard shortcut (optional)

## Common Configuration Tweaks

### Increase Search Results

```yaml
search:
  top_k: 10  # Default: 5
```

### Lower Similarity Threshold (More Results)

```yaml
search:
  similarity_threshold: 0.6  # Default: 0.7
```

### Change GPT Model

```yaml
openai:
  model: "gpt-4"  # Or "gpt-4-turbo"
```

## Getting Help

- Check logs: `cat data/app.log`
- Run with debug logging: Edit `config.yaml` and set `logging.level: DEBUG`
- Review the [README.md](README.md) troubleshooting section

---

Ready to automate! 🚀
