# RAG Summaries - File Content Understanding

## Pattern: Summarize/Explain Files Using RAG Pipeline

When users ask to "summarize" or "explain" files about a topic, use the RAG (Retrieval-Augmented Generation) pipeline that combines semantic search with content synthesis.

## Standard RAG Pipeline

```
search_documents → extract_section → synthesize_content → reply_to_user
```

## Example 1: Summarize Topic Files Using Content-Based Semantic Search (Natural Language)

**Request:** "Summarize documents about melanoma diagnosis"

**Intent:** User wants a summary of CONTENT. The query "melanoma diagnosis" is NOT in any filename - this requires semantic search to find documents containing this medical content.

**Key Point:** This query will find documents by their CONTENT (using embeddings), not by filename matching. The system searches for documents that semantically match the medical concepts, even if filenames don't contain these terms.

**Plan:**
```json
{
  "goal": "Summarize documents about melanoma diagnosis using RAG pipeline",
  "steps": [
    {
      "id": 1,
      "action": "search_documents",
      "parameters": {
        "query": "melanoma diagnosis",
        "user_request": "Summarize documents about melanoma diagnosis"
      },
      "dependencies": [],
      "reasoning": "Search for documents containing 'melanoma diagnosis' using semantic search (embeddings). This will find documents by CONTENT, not filename - the query matches document body text semantically.",
      "expected_output": "doc_path and doc_title of document containing melanoma-related content"
    },
    {
      "id": 2,
      "action": "extract_section",
      "parameters": {
        "doc_path": "$step1.doc_path",
        "section": "all"
      },
      "dependencies": [1],
      "reasoning": "Extract full content from the found document",
      "expected_output": "extracted_text with all document content"
    },
    {
      "id": 3,
      "action": "synthesize_content",
      "parameters": {
        "source_contents": ["$step2.extracted_text"],
        "topic": "Melanoma Diagnosis Summary",
        "synthesis_style": "concise"
      },
      "dependencies": [2],
      "reasoning": "Synthesize extracted content into a concise summary",
      "expected_output": "synthesized_content with summary"
    },
    {
      "id": 4,
      "action": "reply_to_user",
      "parameters": {
        "message": "$step3.synthesized_content"
      },
      "dependencies": [3],
      "reasoning": "Present the synthesized summary to the user",
      "expected_output": "User receives summary"
    }
  ],
  "complexity": "medium"
}
```

## Example 2: Explain Topic Files Using Semantic Content Search (Natural Language)

**Request:** "Explain documents about perspective taking and empathy"

**Intent:** User wants explanation of CONTENT. The query "perspective taking and empathy" searches for documents containing these research concepts semantically, not by filename.

**Key Point:** Semantic search finds documents based on conceptual content (using embeddings), allowing discovery of relevant documents even when filenames don't mention the specific concepts.

**Plan:**
```json
{
  "goal": "Explain documents about perspective taking using RAG pipeline",
  "steps": [
    {
      "id": 1,
      "action": "search_documents",
      "parameters": {
        "query": "perspective taking and empathy",
        "user_request": "Explain documents about perspective taking and empathy"
      },
      "dependencies": [],
      "reasoning": "Search for documents containing 'perspective taking' and 'empathy' concepts using semantic search. This uses embeddings to find documents by research content, not filename matching.",
      "expected_output": "doc_path of document containing perspective-taking/empathy research content"
    },
    {
      "id": 2,
      "action": "extract_section",
      "parameters": {
        "doc_path": "$step1.doc_path",
        "section": "all"
      },
      "dependencies": [1],
      "reasoning": "Extract all content for comprehensive explanation",
      "expected_output": "extracted_text"
    },
    {
      "id": 3,
      "action": "synthesize_content",
      "parameters": {
        "source_contents": ["$step2.extracted_text"],
        "topic": "Perspective Taking and Empathy Explanation",
        "synthesis_style": "comprehensive"
      },
      "dependencies": [2],
      "reasoning": "Create comprehensive explanation of Tesla documents",
      "expected_output": "synthesized_content with detailed explanation"
    },
    {
      "id": 4,
      "action": "reply_to_user",
      "parameters": {
        "message": "$step3.synthesized_content"
      },
      "dependencies": [3],
      "reasoning": "Present explanation to user",
      "expected_output": "User receives explanation"
    }
  ],
  "complexity": "medium"
}
```

## Example 3: RAG Summary via Slash Command with Filename-Based Query

**Request:** "/files Summarize the Ed Sheeran files"

**Intent:** Slash command with summarize intent → Use RAG pipeline. Query contains filename pattern "Ed Sheeran" that semantic search can match.

**Key Point:** 
- Slash commands detect "summarize/explain" keywords and route through RAG pipeline
- Semantic search uses embeddings which can match BOTH filenames AND content
- Query "Ed Sheeran" will find files with "Ed Sheeran" in filename OR content
- This is LLM-driven semantic matching (embeddings), not hardcoded filename pattern matching

**Plan:** Same as Example 1, but triggered via `/files` slash command. The semantic search will find documents containing "Ed Sheeran" in filename or content using embeddings.

**Note:** Semantic search is flexible - it works for:
- Filename queries: "Ed Sheeran files" → finds files with "Ed Sheeran" in filename
- Content queries: "melanoma diagnosis" → finds files with that content even if not in filename
- Both: Uses semantic similarity (embeddings) to match, not hardcoded patterns

## Example 3a: RAG Summary via Slash Command with Content-Based Query

**Request:** "/files Summarize documents about melanoma diagnosis"

**Intent:** Slash command with summarize intent → Use RAG pipeline. Query contains medical content terms that require semantic search.

**Key Point:** 
- The query "melanoma diagnosis" will find documents by CONTENT (semantic similarity), not filename
- This proves RAG uses embeddings for retrieval, not simple filename matching

**Plan:** Same as Example 1, but triggered via `/files` slash command. The semantic search will find documents containing melanoma-related content even if filenames don't mention "melanoma".

## Example 4: Contrast - Zip Files by Filename Pattern (NOT RAG)

**Request:** "Zip files matching VS_Survey"

**Intent:** User wants FILE MANAGEMENT by filename pattern, not content understanding

**Key Distinction:** This uses filename pattern matching (`*VS_Survey*`), NOT semantic content search. File operations match filenames, while RAG searches document content.

**Plan:**
```json
{
  "goal": "Create ZIP archive of VS_Survey files",
  "steps": [
    {
      "id": 1,
      "action": "folder_list",
      "parameters": {
        "folder_path": null
      },
      "dependencies": [],
      "reasoning": "List files to identify VS_Survey files by filename pattern",
      "expected_output": "List of files"
    },
    {
      "id": 2,
      "action": "create_zip_archive",
      "parameters": {
        "source_path": null,
        "zip_name": "vs_survey_files.zip",
        "include_pattern": "*VS_Survey*"
      },
      "dependencies": [1],
      "reasoning": "Create ZIP archive of matching files",
      "expected_output": "zip_path"
    },
    {
      "id": 3,
      "action": "reply_to_user",
      "parameters": {
        "message": "Created ZIP archive: $step2.zip_path with $step2.file_count files"
      },
      "dependencies": [2],
      "reasoning": "Confirm ZIP creation",
      "expected_output": "User receives confirmation"
    }
  ],
  "complexity": "simple"
}
```

## Key Distinctions

### RAG Summaries (Content Understanding via Semantic Search)
- **Keywords:** summarize, explain, describe, what is, tell me about
- **Tools:** `search_documents` → `extract_section` → `synthesize_content` → `reply_to_user`
- **Purpose:** Understand and explain CONTENT
- **Uses:** Semantic search (embeddings) + LLM synthesis
- **Search Method:** Uses semantic embeddings to find documents - can match BOTH filenames AND content
- **Example Queries:** 
  - Filename-based: "Ed Sheeran files" → finds files with "Ed Sheeran" in filename (via semantic similarity)
  - Content-based: "melanoma diagnosis" → finds files with that content even if not in filename
  - Both work because semantic search uses embeddings, not hardcoded pattern matching

### File Operations (File Management by Filename Pattern)
- **Keywords:** zip, organize, move, compress, archive
- **Tools:** `folder_list` → `create_zip_archive` / `organize_files` → `reply_to_user`
- **Purpose:** Manage FILES (move, compress, categorize)
- **Uses:** Folder structure operations + filename pattern matching
- **Search Method:** Matches filenames using patterns (e.g., `*VS_Survey*`), NOT content search

## Disambiguation Pattern

When user says "[action] [content query]":

1. **If action = summarize/explain/describe** → RAG pipeline (semantic content search)
   - Query like "melanoma diagnosis" searches document CONTENT using embeddings
   - Finds documents even if filenames don't contain the query terms
   
2. **If action = zip/organize/move** → File operations (filename pattern matching)
   - Uses filename patterns like `*topic*` to match files
   - Does NOT search document content

3. **If ambiguous** → Prefer RAG for "explain" queries, file ops for "zip" queries

## Semantic Search Verification

Semantic search works for BOTH filename and content queries:

**Filename-Based Queries:**
- ✅ "Ed Sheeran files" → finds files with "Ed Sheeran" in filename (via semantic embeddings)
- ✅ "VS_Survey documents" → finds files with "VS_Survey" in filename
- ✅ Uses semantic similarity, not hardcoded filename pattern matching

**Content-Based Queries:**
- ✅ "melanoma diagnosis" → finds files with that content even if not in filename
- ✅ "perspective taking" → finds research documents by content
- ✅ Match document body text semantically (embeddings similarity > threshold)

**Key Point:** Both work because semantic search uses embeddings (LLM-driven), not hardcoded patterns. The system can find documents by filename OR content through semantic similarity.

## Error Handling

**No documents found:**
```json
{
  "id": 1,
  "action": "search_documents",
  "result": {
    "error": true,
    "error_type": "NotFoundError",
    "error_message": "No documents found matching query: [topic]"
  }
}
```

**Response:** Return structured error in `reply_to_user`:
```json
{
  "id": 2,
  "action": "reply_to_user",
  "parameters": {
    "message": "No documents found matching '[topic]'. Please check your document index or try a different search term."
  }
}
```

