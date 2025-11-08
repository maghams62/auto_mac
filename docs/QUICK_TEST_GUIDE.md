# Quick Test Guide 🚀

## 1️⃣ First: View All Tests (30 seconds)

```bash
./run_tests.sh dry-run
```

This shows all 31 test cases without running them.

## 2️⃣ Test the Original Bug Fix (2-3 minutes)

```bash
./run_tests.sh original
```

This runs: "Take screenshot of Google News, add to presentation, email it"

**Expected**: ✅ PASS (bug is now fixed!)

## 3️⃣ Quick Agent Tests (5-10 minutes each)

### Test Browser Agent
```bash
./run_tests.sh browser
```
Tests: Search, navigate, extract, screenshot, cleanup (6 tests)

### Test File Agent
```bash
./run_tests.sh file
```
Tests: Search docs, extract, screenshot, organize (5 tests)

### Test Presentation Agent
```bash
./run_tests.sh presentation
```
Tests: Keynote, Keynote with images, Pages (3 tests)

### Test Email Agent
```bash
./run_tests.sh email
```
Tests: Draft emails, attachments (2 tests)

## 4️⃣ Full System Test (30-90 minutes)

```bash
./run_tests.sh all
```

Runs all 31 tests with user confirmations.

## 📊 Check Results

After any test run:

```bash
# View detailed results
cat test_results.json | python -m json.tool

# View execution logs
tail -100 data/app.log
```

## 🎯 Test Categories Reference

| Command | Tests | Time | Description |
|---------|-------|------|-------------|
| `dry-run` | Shows all | < 1s | View test definitions |
| `original` | 2 | 2-5 min | Original failing test |
| `browser` | 6 | 5-15 min | Web browsing tests |
| `file` | 5 | 5-10 min | File operations tests |
| `presentation` | 3 | 5-10 min | Keynote/Pages tests |
| `email` | 2 | 2-5 min | Email tests |
| `multi` | 12 | 20-60 min | Multi-agent workflows |
| `edge` | 3 | 5-10 min | Error handling tests |
| `all` | 31 | 30-90 min | Complete suite |

## 🐛 If Tests Fail

1. **Browser hangs**: Press Ctrl+C, check timeout settings
2. **Missing tools**: Check `src/agent/` files
3. **Permission errors**: Check file permissions
4. **Network errors**: Check internet connection

See `TESTING_README.md` for full troubleshooting guide.

## ✅ Success Indicators

You'll know tests are passing when you see:
- ✅ "TEST PASSED" messages
- No timeout errors
- Browser windows open/close properly
- Files created successfully
- test_results.json shows high pass rate

## 📝 Test Examples

### Example 1: Simple Test
```
Name: Browser Agent - Google Search
Goal: Search Google for 'LangChain documentation'
Tools: google_search
Time: ~10 seconds
```

### Example 2: Complex Test
```
Name: Multi-Agent - Full Workflow (ORIGINAL TEST)
Goal: Screenshot Google News → Presentation → Email
Tools: navigate_to_url, take_web_screenshot, 
       create_keynote_with_images, compose_email
Time: ~60 seconds
```

### Example 3: Ultimate Test
```
Name: Multi-Agent - Ultimate Full Stack Test
Goal: Find tab → organize → web search → screenshots → 
      presentation → email
Tools: All 7 tools across all 5 agents
Time: ~120 seconds
```

## 🎨 Recommended Testing Sequence

```
Day 1: Quick Validation
├─ ./run_tests.sh dry-run     (view tests)
├─ ./run_tests.sh original    (verify bug fix)
└─ ./run_tests.sh browser     (test web features)

Day 2: Complete Testing
├─ ./run_tests.sh file         (test file ops)
├─ ./run_tests.sh presentation (test presentations)
├─ ./run_tests.sh email        (test email)
└─ Review results

Day 3: Full Suite
└─ ./run_tests.sh all          (complete validation)
```

## 🚀 Quick Start Commands

```bash
# Make script executable (first time only)
chmod +x run_tests.sh

# View help
./run_tests.sh help

# Run most important test
./run_tests.sh original

# Run full suite
./run_tests.sh all
```

---

**TIP**: Start with `./run_tests.sh dry-run` to see what will be tested!
