# Workflow Analysis: "Create Nike Stock Report → ZIP → Email"

## User Request

> "Create a report on the current stock price of nike including the current stock price as an image. zip the pdf and email it to spamstuff062@gmail.com"

## Workflow Breakdown

This request requires **3 distinct steps**:

```
Step 1: Create Stock Report
    ↓
Step 2: Create ZIP Archive
    ↓
Step 3: Compose Email with Attachment
```

## Detailed Analysis

### ✅ **STEP 1: Create Stock Report**

**Tool:** `create_stock_report_from_google_finance`

**Action:**
```python
result = create_stock_report_from_google_finance.invoke({
    "company": "NKE",  # Nike's ticker symbol
    "output_format": "pdf"
})
```

**Expected Output:**
- PDF report: `data/reports/nke_gfinance_report_20251107.pdf`
- Chart screenshot: `data/screenshots/nke_gfinance_20251107.png`
- AI research extracted from Google Finance
- Price data and statistics

**Potential Failure Points:**

| Issue | Probability | Solution |
|-------|-------------|----------|
| CAPTCHA (if using "Nike" instead of "NKE") | ~5% | ✅ Use "NKE" ticker symbol |
| Network timeout | ~2% | Retry with longer timeout |
| Google Finance structure changed | <1% | Update CSS selectors |
| Browser not installed | ~1% | Run `playwright install chromium` |

**Status:** ✅ **Should work reliably** (using ticker symbol)

---

### ⚠️ **STEP 2: Create ZIP Archive**

**Tool:** `create_zip_archive` (from file_agent)

**Action:**
```python
from agent.file_agent import create_zip_archive

zip_result = create_zip_archive.invoke({
    "source_path": report_path,  # Path to PDF from Step 1
    "zip_name": "nike_stock_report_20251107.zip"
})
```

**Expected Output:**
- ZIP file: `data/reports/nike_stock_report_20251107.zip` (or similar location)

**Potential Failure Points:**

| Issue | Probability | Solution |
|-------|-------------|----------|
| Wrong parameter names | **HIGH** | ✅ Fixed: Use `source_path` not `files` |
| File permissions | ~5% | Check write permissions on data/reports/ |
| Path resolution | ~10% | Use absolute paths |
| ZIP module missing | <1% | Built-in Python module |

**Status:** ⚠️ **Likely to fail** - Parameter mismatch (FIXED in test)

**Fix Applied:**
```python
# ❌ WRONG (original attempt)
zip_result = create_zip_archive.invoke({
    "files": [report_path],  # Wrong parameter name
    "output_name": zip_name,
    "compression": "medium"
})

# ✅ CORRECT (fixed)
zip_result = create_zip_archive.invoke({
    "source_path": report_path,  # Correct parameter name
    "zip_name": zip_name
})
```

---

### ⚠️ **STEP 3: Compose Email**

**Tool:** `compose_email` (from email_agent)

**Action:**
```python
from agent.email_agent import compose_email

email_result = compose_email.invoke({
    "recipient": "spamstuff062@gmail.com",
    "subject": "Nike (NKE) Stock Report - 2025-11-07",
    "body": email_body,
    "attachments": [zip_path]  # Path to ZIP from Step 2
})
```

**Expected Output:**
- Drafted email in Mail.app with ZIP attachment
- User manually clicks "Send"

**Potential Failure Points:**

| Issue | Probability | Solution |
|-------|-------------|----------|
| Mail.app not accessible | **MEDIUM** | Grant automation permissions |
| Attachment path incorrect | ~20% | Verify ZIP path from Step 2 |
| AppleScript permissions | **MEDIUM** | System Preferences → Security |
| Mail.app not configured | ~10% | Configure email account |

**Status:** ⚠️ **May fail** - Requires macOS permissions

---

## Expected Failure Modes

### Most Likely Failures (in order):

1. **🔴 HIGH RISK: Mail.app Permissions (~40%)**
   ```
   Error: "Mail.app is not allowed to send events"
   Solution: System Preferences → Security & Privacy → Automation
   → Terminal/Python → Check "Mail"
   ```

2. **🟡 MEDIUM RISK: ZIP Path Resolution (~20%)**
   ```
   Error: "Attachment file not found"
   Cause: ZIP created in unexpected location
   Solution: Use absolute paths
   ```

3. **🟡 MEDIUM RISK: Parameter Mismatch (~15%)**
   ```
   Error: "unexpected keyword argument 'files'"
   Cause: Wrong parameter names for create_zip_archive
   Solution: Use correct parameters (source_path, zip_name)
   ```

4. **🟢 LOW RISK: CAPTCHA (~5% if using company name)**
   ```
   Error: "CAPTCHADetected"
   Cause: Used "Nike" instead of "NKE"
   Solution: Always use ticker symbols
   ```

5. **🟢 LOW RISK: Network Issues (~2%)**
   ```
   Error: "Failed to navigate to Google Finance"
   Solution: Check internet connection, retry
   ```

## Test Results

Run the complete workflow test:

```bash
python test_complete_workflow.py
```

### Expected Test Output:

**Scenario A: Full Success (60% probability)**
```
✅ STEP 1 SUCCESS: Nike stock report created
✅ STEP 2 SUCCESS: ZIP archive created
✅ STEP 3 SUCCESS: Email drafted in Mail.app

📧 Email ready to send (user needs to click Send)
```

**Scenario B: Mail.app Permission Denied (30% probability)**
```
✅ STEP 1 SUCCESS: Nike stock report created
✅ STEP 2 SUCCESS: ZIP archive created
❌ STEP 3 FAILED: Mail.app not accessible

Error: "Not authorized to send Apple events to Mail"
Solution: Grant permissions in System Preferences
```

**Scenario C: ZIP Creation Failed (10% probability)**
```
✅ STEP 1 SUCCESS: Nike stock report created
❌ STEP 2 FAILED: ZIP creation failed

Error: "No such file or directory"
Solution: Check file paths, use absolute paths
```

## Fixes Already Applied

### 1. ✅ Use Ticker Symbol (CAPTCHA Prevention)

```python
# ❌ RISKY: Using company name
result = create_stock_report_from_google_finance.invoke({
    "company": "Nike",  # May trigger Google search
    "output_format": "pdf"
})

# ✅ SAFE: Using ticker symbol
result = create_stock_report_from_google_finance.invoke({
    "company": "NKE",  # Direct URL, 0% CAPTCHA risk
    "output_format": "pdf"
})
```

### 2. ✅ Correct ZIP Parameters

```python
# ❌ WRONG: Incorrect parameters
zip_result = create_zip_archive.invoke({
    "files": [report_path],
    "output_name": zip_name,
    "compression": "medium"
})

# ✅ CORRECT: Proper parameters
zip_result = create_zip_archive.invoke({
    "source_path": report_path,
    "zip_name": zip_name
})
```

### 3. ✅ Absolute Paths for Email Attachment

```python
# ✅ Using absolute path from ZIP creation
zip_path = zip_result['zip_path']  # Already absolute

email_result = compose_email.invoke({
    "attachments": [zip_path]  # Absolute path
})
```

## Manual Verification Steps

### Before Running Test:

1. **Check Playwright Installation:**
   ```bash
   playwright install chromium
   ```

2. **Verify Mail.app Configuration:**
   - Open Mail.app
   - Ensure at least one email account is configured
   - Test sending a manual email

3. **Grant Automation Permissions:**
   - System Preferences → Security & Privacy → Privacy
   - Automation → Terminal/Python → Check "Mail"

4. **Test Individual Components:**
   ```bash
   # Test stock report creation
   python -c "from src.agent.google_finance_agent import create_stock_report_from_google_finance; print(create_stock_report_from_google_finance.invoke({'company': 'NKE', 'output_format': 'pdf'}))"

   # Test ZIP creation
   python -c "from src.agent.file_agent import create_zip_archive; print(create_zip_archive.invoke({'source_path': 'data/reports/', 'zip_name': 'test.zip'}))"

   # Test email composition
   python -c "from src.agent.email_agent import compose_email; print(compose_email.invoke({'recipient': 'test@test.com', 'subject': 'Test', 'body': 'Test'}))"
   ```

## Orchestrator Expectations

When the orchestrator receives this request, it should:

1. **Parse the request** into 3 steps:
   - Create stock report for Nike
   - Create ZIP of the PDF
   - Email ZIP to spamstuff062@gmail.com

2. **Execute sequentially** (not parallel):
   - Step 2 depends on Step 1 (needs report path)
   - Step 3 depends on Step 2 (needs ZIP path)

3. **Handle errors gracefully:**
   - If Step 1 fails → Stop, report error
   - If Step 2 fails → Can still email PDF directly
   - If Step 3 fails → Provide ZIP path for manual email

## Expected Timeline

| Step | Duration | Notes |
|------|----------|-------|
| Step 1: Stock Report | 10-15 seconds | Network-dependent |
| Step 2: ZIP Creation | 1-2 seconds | File I/O |
| Step 3: Email Composition | 2-3 seconds | AppleScript |
| **Total** | **13-20 seconds** | If all successful |

## Success Criteria

**Definition of Success:**
- ✅ PDF report created with Nike stock data
- ✅ Chart image embedded in PDF
- ✅ PDF compressed into ZIP file
- ✅ Email drafted in Mail.app with ZIP attachment
- ⚠️ **Note:** Email will NOT be sent automatically (requires user to click Send)

## Fallback Strategy

If any step fails, the orchestrator should:

1. **Step 1 Fails:**
   ```
   → Retry with ticker symbol "NKE"
   → If still fails, report error to user
   ```

2. **Step 2 Fails:**
   ```
   → Skip ZIP, attach PDF directly
   → Proceed to Step 3 with PDF
   ```

3. **Step 3 Fails:**
   ```
   → Provide file paths to user
   → Suggest manual email with instructions
   ```

## Conclusion

**Overall Success Probability: ~60%**

**Most Likely Outcome:**
- Steps 1 & 2 succeed
- Step 3 fails due to Mail.app permissions
- User needs to grant permissions and retry

**Recommended User Action:**
1. Run: `python test_complete_workflow.py`
2. If permission errors occur, grant permissions
3. Re-run the test
4. Check Mail.app for drafted email
5. Click "Send" manually

**Files to Check After Run:**
- `data/reports/nke_gfinance_report_*.pdf`
- `data/screenshots/nke_gfinance_*.png`
- `data/reports/nike_stock_report_*.zip`
- Mail.app drafts folder
