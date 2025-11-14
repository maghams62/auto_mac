# Comprehensive Test Plan: Image Preview Endpoint with Telemetry

## Status: NOT TESTED YET

**Date Created:** 2025-01-13
**Purpose:** Test the enhanced `/api/files/preview` endpoint with OpenTelemetry instrumentation, HEAD method support, and frontend preview modal improvements.

---

## Prerequisites

1. **Restart API Server** (required for new code to take effect):
   ```bash
   # Kill existing server
   pkill -f "api_server.py"
   
   # Start fresh
   cd /Users/siddharthsuresh/Downloads/auto_mac
   python api_server.py
   ```

2. **Verify Services Running:**
   - API Server: `http://localhost:8000`
   - Frontend: `http://localhost:3000` (or 3001/3002)

3. **Test File Exists:**
   - Path: `/Users/siddharthsuresh/Downloads/auto_mac/tests/data/test_docs/mountain_landscape.jpg`
   - Verify: `ls -la tests/data/test_docs/mountain_landscape.jpg`

---

## Test Phase 1: Backend API Testing (curl)

### Test 1.1: HEAD Request - Success Case

**Command:**
```bash
curl -I "http://localhost:8000/api/files/preview?path=/Users/siddharthsuresh/Downloads/auto_mac/tests/data/test_docs/mountain_landscape.jpg"
```

**Expected Results:**
- ✅ Status: `200 OK`
- ✅ Headers include:
  - `Content-Type: image/jpeg`
  - `Content-Length: <file_size>`
- ✅ No response body (HEAD method)

**Backend Logs to Check:**
```bash
grep "\[FILE PREVIEW\]" api_server.log | tail -5
```

**Expected Log Entries:**
```
INFO:__main__:[FILE PREVIEW] HEAD request for path: /Users/siddharthsuresh/Downloads/auto_mac/tests/data/test_docs/mountain_landscape.jpg
INFO:__main__:[FILE PREVIEW] Allowed directories: [...]
INFO:__main__:[FILE PREVIEW] HEAD request successful for ... (content-type: image/jpeg)
```

**Telemetry to Verify:**
- Check for `file_preview` span with attributes:
  - `file_preview.method = "HEAD"`
  - `file_preview.is_allowed = "True"`
  - `file_preview.status_code = "200"`

---

### Test 1.2: GET Request - Success Case

**Command:**
```bash
curl -v "http://localhost:8000/api/files/preview?path=/Users/siddharthsuresh/Downloads/auto_mac/tests/data/test_docs/mountain_landscape.jpg" -o /tmp/test_image.jpg
```

**Expected Results:**
- ✅ Status: `200 OK`
- ✅ Headers include: `Content-Type: image/jpeg`
- ✅ File downloaded successfully
- ✅ File size matches original

**Verify Downloaded File:**
```bash
file /tmp/test_image.jpg
# Should show: JPEG image data
```

**Backend Logs to Check:**
```
INFO:__main__:[FILE PREVIEW] GET request for path: ...
INFO:__main__:[FILE PREVIEW] GET request successful for ... (content-type: image/jpeg)
```

---

### Test 1.3: HEAD Request - Access Denied (403)

**Command:**
```bash
curl -I "http://localhost:8000/api/files/preview?path=/etc/passwd"
```

**Expected Results:**
- ✅ Status: `403 Forbidden`
- ✅ Error message in response body

**Backend Logs to Check:**
```
WARNING:__main__:[FILE PREVIEW] Access denied for /etc/passwd. Allowed roots: [...]
```

**Telemetry to Verify:**
- `file_preview.is_allowed = "False"`
- `file_preview.status_code = "403"`
- `file_preview.error_type = "HTTPException"`

---

### Test 1.4: HEAD Request - File Not Found (404)

**Command:**
```bash
curl -I "http://localhost:8000/api/files/preview?path=/Users/siddharthsuresh/Downloads/auto_mac/tests/data/test_docs/nonexistent.jpg"
```

**Expected Results:**
- ✅ Status: `404 Not Found`
- ✅ Error message in response body

**Backend Logs to Check:**
```
WARNING:__main__:[FILE PREVIEW] File not found: ...
```

**Telemetry to Verify:**
- `file_preview.status_code = "404"`
- `file_preview.error_type = "FileNotFoundError"`

---

## Test Phase 2: Frontend UI Testing (Browser Automation)

### Test 2.1: Full UI Flow - Mountain Image Search

**Steps:**
1. Navigate to `http://localhost:3000`
2. Wait for WebSocket connection
3. Type query: `"pull up the picture of a mountain"`
4. Wait for response with file_list
5. Verify image thumbnail appears in FileList
6. Click on image thumbnail
7. Verify preview modal opens
8. Verify image loads in modal
9. Close modal

**Browser Console Logs to Check:**
```javascript
// Should see:
[PreviewModal] Checking preview access { previewUrl: "...", filePath: "..." }
[PreviewModal] Preview HEAD successful { status: 200, contentType: "image/jpeg", ... }
```

**Network Tab to Verify:**
1. Find `HEAD /api/files/preview?path=...` request
   - Status: `200 OK`
   - Response Headers: `Content-Type: image/jpeg`
2. Find `GET /api/files/preview?path=...` request (if image loads directly)
   - Status: `200 OK`
   - Response Type: `image/jpeg`

**Backend Logs to Check:**
```bash
# Should see both HEAD and GET requests logged
grep "\[FILE PREVIEW\]" api_server.log | grep "mountain_landscape.jpg"
```

**Expected Sequence:**
```
INFO:__main__:[FILE PREVIEW] HEAD request for path: ...
INFO:__main__:[FILE PREVIEW] HEAD request successful for ... (content-type: image/jpeg)
INFO:__main__:[FILE PREVIEW] GET request for path: ...
INFO:__main__:[FILE PREVIEW] GET request successful for ... (content-type: image/jpeg)
```

---

### Test 2.2: Error Handling - Invalid Path

**Steps:**
1. Manually trigger preview with invalid path (via browser console or test)
2. Verify error message displays in modal
3. Check console logs for error details

**Expected Console Logs:**
```javascript
[PreviewModal] Preview HEAD failed { status: 403, statusText: "Forbidden", ... }
// OR
[PreviewModal] Preview HEAD error { error: ..., errorType: "...", ... }
```

---

## Test Phase 3: Telemetry Verification

### Test 3.1: Verify No Attribute Type Warnings

**Check Backend Logs:**
```bash
grep "Invalid type dict for attribute" api_server.log | tail -10
```

**Expected Result:**
- ✅ **NO warnings** (or significantly fewer than before)

**If warnings still appear:**
- Check `telemetry/config.py` - `sanitize_value()` function
- Verify dicts/lists are converted to JSON strings

---

### Test 3.2: Verify Span Creation

**Check for Span Attributes:**
- Spans should have all attributes as strings/primitives
- No dict or complex object attributes

**Note:** If OTLP collector is not running, export warnings are expected and can be ignored.

---

## Test Phase 4: End-to-End Integration Test

### Test 4.1: Complete Mountain Image Query Flow

**Run Full Test Script:**
```bash
python test_mountain_image_ui.py
```

**Or Manual Browser Test:**
1. Open browser to `http://localhost:3000`
2. Open browser DevTools (Console + Network tabs)
3. Execute query: `"pull up the picture of a mountain"`
4. Wait for results
5. Click image thumbnail
6. Verify preview modal opens and image displays

**Success Criteria:**
- ✅ Image thumbnail visible in FileList
- ✅ Thumbnail clickable
- ✅ Preview modal opens
- ✅ HEAD request returns 200
- ✅ GET request returns 200
- ✅ Image displays in modal (not error message)
- ✅ Modal can be closed
- ✅ No console errors
- ✅ Backend logs show `[FILE PREVIEW]` entries
- ✅ Browser console shows `[PreviewModal]` logs

---

## Expected Log Output Examples

### Backend Logs (api_server.log)

**First Request (Shows Allowed Directories):**
```
INFO:__main__:[FILE PREVIEW] HEAD request for path: /Users/siddharthsuresh/Downloads/auto_mac/tests/data/test_docs/mountain_landscape.jpg
INFO:__main__:[FILE PREVIEW] Allowed directories: ['/Users/siddharthsuresh/Downloads/auto_mac/data/reports', '/Users/siddharthsuresh/Downloads/auto_mac/data/presentations', '/Users/siddharthsuresh/Downloads/auto_mac/data/screenshots', '/Users/siddharthsuresh/Downloads/auto_mac/tests/data/test_docs']
INFO:__main__:[FILE PREVIEW] HEAD request successful for /Users/siddharthsuresh/Downloads/auto_mac/tests/data/test_docs/mountain_landscape.jpg (content-type: image/jpeg)
```

**Subsequent Requests:**
```
INFO:__main__:[FILE PREVIEW] GET request for path: /Users/siddharthsuresh/Downloads/auto_mac/tests/data/test_docs/mountain_landscape.jpg
INFO:__main__:[FILE PREVIEW] GET request successful for /Users/siddharthsuresh/Downloads/auto_mac/tests/data/test_docs/mountain_landscape.jpg (content-type: image/jpeg)
```

### Browser Console Logs

**Successful Preview:**
```javascript
[PreviewModal] Checking preview access { previewUrl: "http://localhost:8000/api/files/preview?path=...", filePath: "..." }
[PreviewModal] Preview HEAD successful { status: 200, contentType: "image/jpeg", previewUrl: "..." }
```

**Failed Preview:**
```javascript
[PreviewModal] Preview HEAD failed { status: 403, statusText: "Forbidden", previewUrl: "...", filePath: "..." }
// OR
[PreviewModal] Preview HEAD error { error: TypeError: Failed to fetch, errorType: "TypeError", errorMessage: "...", ... }
```

---

## Test Execution Checklist

- [ ] **Phase 1.1:** HEAD request success (curl)
- [ ] **Phase 1.2:** GET request success (curl)
- [ ] **Phase 1.3:** HEAD request 403 error (curl)
- [ ] **Phase 1.4:** HEAD request 404 error (curl)
- [ ] **Phase 2.1:** Full UI flow (browser)
- [ ] **Phase 2.2:** Error handling (browser)
- [ ] **Phase 3.1:** No telemetry warnings
- [ ] **Phase 3.2:** Span attributes correct
- [ ] **Phase 4.1:** End-to-end integration test

---

## Failure Investigation Guide

### If HEAD Request Fails (405 Method Not Allowed)
- **Check:** Server was restarted after code changes
- **Fix:** Restart API server

### If Preview Shows "Unable to load file"
- **Check Browser Console:** Look for `[PreviewModal]` error logs
- **Check Backend Logs:** Look for `[FILE PREVIEW]` entries
- **Check Network Tab:** Verify HEAD request status code
- **Common Causes:**
  - CORS issue (check CORS headers in response)
  - Path encoding issue (check URL encoding)
  - File not in allowed directories (check backend logs)

### If Image Doesn't Display in Modal
- **Check:** `fileType="image"` is passed to `DocumentPreviewModal`
- **Check:** Image URL is correct in network tab
- **Check:** Browser console for image load errors

### If Telemetry Warnings Persist
- **Check:** `telemetry/config.py` - `sanitize_value()` function
- **Verify:** All dict/list values are converted to JSON strings
- **Check:** No direct `set_attribute()` calls with dict values

---

## Success Criteria Summary

✅ **Backend:**
- HEAD requests return 200 with proper headers
- GET requests return 200 with image content
- All requests logged with `[FILE PREVIEW]` prefix
- Telemetry spans created with correct attributes
- No "Invalid type dict" warnings

✅ **Frontend:**
- Preview modal opens on thumbnail click
- HEAD request succeeds (200)
- Image loads and displays in modal
- Console logs show `[PreviewModal]` entries
- No console errors

✅ **Integration:**
- Full flow works: query → search → file_list → preview
- Image visible, clickable, and previewable
- All success criteria from `test_mountain_image_ui.py` pass

---

## Next Steps After Testing

1. **If All Tests Pass:**
   - Document results in test report
   - Mark todos as complete
   - Consider adding automated regression test

2. **If Tests Fail:**
   - Collect logs (backend + browser console)
   - Identify specific failure point
   - Fix issue and re-test
   - Update this plan with findings

---

## Test Report Template

After running tests, create a report with:

```markdown
# Image Preview Endpoint Test Report

**Date:** [DATE]
**Tester:** [NAME]
**Status:** [PASS/FAIL]

## Test Results

### Phase 1: Backend API
- [ ] Test 1.1: HEAD Success
- [ ] Test 1.2: GET Success
- [ ] Test 1.3: HEAD 403
- [ ] Test 1.4: HEAD 404

### Phase 2: Frontend UI
- [ ] Test 2.1: Full UI Flow
- [ ] Test 2.2: Error Handling

### Phase 3: Telemetry
- [ ] Test 3.1: No Warnings
- [ ] Test 3.2: Span Attributes

### Phase 4: Integration
- [ ] Test 4.1: End-to-End

## Logs Captured
- Backend logs: [LOCATION]
- Browser console: [SCREENSHOT/LOCATION]
- Network requests: [SCREENSHOT/LOCATION]

## Issues Found
[LIST ANY ISSUES]

## Recommendations
[ANY RECOMMENDATIONS]
```

---

**END OF TEST PLAN**

