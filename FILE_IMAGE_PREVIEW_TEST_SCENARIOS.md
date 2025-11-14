# File and Image Preview Test Scenarios

This document outlines comprehensive test scenarios to verify file and image preview functionality.

## Implementation Summary

### Changes Made:

1. **Enhanced `FileList.tsx`**:
   - Added support for image thumbnails (displays thumbnail instead of icon for images)
   - Added preview button for previewable files (PDFs, images, HTML)
   - Integrated `DocumentPreviewModal` for file previews
   - Added `thumbnail_url` and `preview_url` fields to `FileHit` interface
   - Added `result_type` field to distinguish between documents and images

2. **Enhanced `list_related_documents` tool**:
   - Now searches for both documents AND images
   - Includes `thumbnail_url` and `preview_url` for image results
   - Returns `result_type: "image"` for images
   - Combines and sorts document and image results by relevance score

3. **API Response Format**:
   - `list_related_documents` returns `file_list` type with proper structure
   - Image results include `thumbnail_url` and `preview_url` fields
   - All results include `result_type` field ("document" or "image")

## Test Scenarios

### Test 1: "Pull up my files"

**User Query**: "pull up my files"

**Expected Behavior**:
1. Planner should use `list_related_documents` or `list_documents` tool
2. Results should be displayed in `FileList` component
3. Each file should show:
   - File name
   - File path
   - Similarity score
   - File type
   - Preview button (if previewable)
   - Reveal button
   - Copy button

**Verification Steps**:
1. Send query: "pull up my files"
2. Check that plan includes `list_related_documents` or `list_documents`
3. Verify files are displayed in `FileList` component
4. Verify each file has name, path, score, and meta fields
5. Verify preview button appears for previewable files (PDFs, images, HTML)

**Success Criteria**:
- ✅ Files are displayed correctly
- ✅ File metadata is shown (name, path, type, score)
- ✅ Preview button appears for previewable files
- ✅ No errors in console

---

### Test 2: "Pull up that image of the mountain"

**User Query**: "pull up that image of the mountain"

**Expected Behavior**:
1. Planner should use `search_documents` or `list_related_documents` with `include_images=True`
2. Image results should include `thumbnail_url` and `preview_url`
3. Image thumbnail should be displayed (not just icon)
4. Preview button should be available
5. Clicking preview should open `DocumentPreviewModal`
6. Image should display correctly in modal
7. "Open in New Tab" button should open file in browser

**Verification Steps**:
1. Send query: "pull up that image of the mountain"
2. Check that plan includes image search (`include_images=True`)
3. Verify result has `result_type: "image"`
4. Verify `thumbnail_url` and `preview_url` are present in response
5. Verify image thumbnail is displayed in `FileList` (not just icon)
6. Click preview button → verify modal opens
7. Verify image displays correctly in modal
8. Click "Open in New Tab" → verify file opens in browser

**Success Criteria**:
- ✅ Image is found via semantic search
- ✅ Image thumbnail is displayed (not just icon)
- ✅ Preview button is available
- ✅ Preview modal opens correctly
- ✅ Image displays in modal
- ✅ "Open in New Tab" opens file correctly

---

### Test 3: Image Preview in FileList

**User Query**: Any query that returns images (e.g., "show me images", "find photos")

**Expected Behavior**:
1. Images should show thumbnails (not just icons)
2. Thumbnails should be clickable or have preview button
3. Preview modal should open on click

**Verification Steps**:
1. Search for images
2. Verify `FileList` shows image thumbnails (60x60px)
3. Verify thumbnails are displayed correctly
4. Click preview button → verify modal opens
5. Verify image displays in modal

**Success Criteria**:
- ✅ Images show thumbnails (not just icons)
- ✅ Thumbnails are displayed correctly
- ✅ Preview button works
- ✅ Preview modal opens correctly

---

### Test 4: File Preview (PDF)

**User Query**: "show me PDF files" or "pull up my PDFs"

**Expected Behavior**:
1. PDF files should show preview button
2. Clicking preview should open `DocumentPreviewModal`
3. PDF should display in iframe
4. "Open in New Tab" should open PDF in browser

**Verification Steps**:
1. Search for PDF files
2. Verify preview button appears for PDFs
3. Click preview → verify modal opens
4. Verify PDF displays in iframe
5. Click "Open in New Tab" → verify PDF opens in browser

**Success Criteria**:
- ✅ Preview button appears for PDFs
- ✅ PDF displays in modal
- ✅ "Open in New Tab" works correctly

---

### Test 5: Mixed Results (Documents + Images)

**User Query**: "show me files about mountains"

**Expected Behavior**:
1. Results should include both documents and images
2. Documents should show icons
3. Images should show thumbnails
4. Both should have preview buttons if previewable

**Verification Steps**:
1. Search for query that returns both documents and images
2. Verify documents show icons
3. Verify images show thumbnails
4. Verify both have preview buttons (if previewable)
5. Verify results are sorted by relevance score

**Success Criteria**:
- ✅ Documents and images are both displayed
- ✅ Documents show icons, images show thumbnails
- ✅ Preview buttons work for both
- ✅ Results are sorted correctly

---

### Test 6: API Response Format Validation

**Test**: Verify API responses have correct structure

**Expected Structure**:
```json
{
  "type": "file_list",
  "message": "Found X results...",
  "files": [
    {
      "name": "filename.jpg",
      "path": "/path/to/file.jpg",
      "score": 0.85,
      "result_type": "image",
      "thumbnail_url": "/api/files/thumbnail?path=...",
      "preview_url": "/api/files/preview?path=...",
      "meta": {
        "file_type": "jpg",
        "width": 1920,
        "height": 1080
      }
    }
  ],
  "total_count": 10
}
```

**Verification Steps**:
1. Call `list_related_documents` tool directly
2. Verify response has `type: "file_list"`
3. Verify `files` array exists
4. Verify each file has required fields: `name`, `path`, `score`, `meta`
5. Verify images have `thumbnail_url` and `preview_url`
6. Verify images have `result_type: "image"`

**Success Criteria**:
- ✅ Response has correct structure
- ✅ All required fields are present
- ✅ Images have `thumbnail_url` and `preview_url`
- ✅ Images have `result_type: "image"`

---

## Manual Testing Checklist

### Frontend Components

- [ ] `FileList` displays image thumbnails correctly
- [ ] `FileList` shows preview button for previewable files
- [ ] `DocumentPreviewModal` opens when preview button is clicked
- [ ] Image preview displays correctly in modal
- [ ] PDF preview displays correctly in modal
- [ ] "Open in New Tab" button works correctly
- [ ] Thumbnail fallback works if image fails to load
- [ ] File icons display correctly for non-image files

### Backend Tools

- [ ] `list_related_documents` searches for images
- [ ] `list_related_documents` includes `thumbnail_url` and `preview_url` for images
- [ ] `list_related_documents` returns `result_type: "image"` for images
- [ ] Results are sorted by relevance score
- [ ] API response format is correct

### End-to-End Tests

- [ ] "Pull up my files" shows files correctly
- [ ] "Pull up that image of the mountain" shows image preview correctly
- [ ] Clicking preview opens modal correctly
- [ ] Clicking "Open in New Tab" opens file correctly
- [ ] Mixed results (documents + images) display correctly

---

## Known Issues / Limitations

1. **Thumbnail Generation**: Thumbnails are generated on-the-fly via `/api/files/thumbnail` endpoint. If thumbnail generation fails, the component falls back to showing an icon.

2. **Image Indexing**: Images must be indexed before they can be found via search. Ensure image indexing is enabled in config.

3. **File Access**: Files must be in authorized directories (as specified in `config.yaml`) to be previewed.

---

## Test Results

Run the test script:
```bash
python test_file_image_preview.py
```

Expected output:
- ✅ File list format is valid
- ✅ Image results include `thumbnail_url` and `preview_url`
- ✅ All required fields are present

---

## Next Steps

1. **Manual Testing**: Test all scenarios manually in the UI
2. **Integration Testing**: Test with actual indexed files and images
3. **Error Handling**: Test error cases (missing files, permission errors, etc.)
4. **Performance**: Test with large numbers of files/images

