# LLM-Based Tool Composition & Query Disambiguation Plan

## Problem Statement

**Current Issue:**
- Query: "send all duplicated docs in my folder to my email"
- System Response: "Missing required capabilities: document duplication detection"

**Root Cause:**
The system looks for a specific `detect_duplicates` tool instead of **composing existing tools** to solve the problem.

**What We Want:**
The LLM should reason: "I can use `explain_files()` to get all files, then use LLM-based analysis to identify duplicates by comparing names/content, then use `compose_email()` to send them."

---

## Core Principle: Tool Composition over Tool Proliferation

### ❌ Bad Approach (Current)
- Create specialized tools for every possible query
- `detect_duplicates`, `find_similar_files`, `compare_documents`, etc.
- **Problem:** Infinite tool proliferation, hardcoded logic, inflexible

### ✅ Good Approach (Proposed)
- Provide **general-purpose primitive tools**
- Let LLM **compose tools** to solve complex queries
- Use **LLM reasoning** for pattern matching, similarity, analysis
- **Benefit:** Flexible, scalable, no hardcoding

---

## Proposed Architecture

### Layer 1: Primitive Tools (Building Blocks)

These are **general-purpose** tools that can be composed:

#### File Discovery Tools
```python
explain_files() -> List[FileInfo]
# Returns ALL files with metadata (name, path, type, size, description)

explain_folder(path) -> List[FileInfo]
# Returns files in a specific folder

search_documents(query) -> FileInfo
# Semantic search for specific content
```

#### File Analysis Tools (NEW - General Purpose)
```python
analyze_files(files: List[str], analysis_type: str, criteria: Optional[str]) -> Dict
# General-purpose file analysis using LLM
# analysis_type: "similarity", "content_match", "pattern_detection", "categorization"
# criteria: User-defined criteria for analysis

compare_files(file_paths: List[str], comparison_aspect: str) -> Dict
# Compare multiple files on a specific aspect
# comparison_aspect: "content", "structure", "metadata", "names"
```

#### Data Processing Tools (NEW - General Purpose)
```python
filter_items(items: List[Any], filter_criteria: str) -> List[Any]
# LLM-based filtering of any list based on natural language criteria

group_items(items: List[Any], grouping_criteria: str) -> Dict[str, List[Any]]
# LLM-based grouping of items

extract_patterns(text: str, pattern_description: str) -> List[str]
# LLM extracts patterns based on description
```

### Layer 2: LLM Reasoning Layer

The LLM planner receives the query and available tools, then:

1. **Decomposes** the query into sub-tasks
2. **Identifies** which primitive tools can help
3. **Composes** tools into a workflow
4. **Uses LLM capabilities** for fuzzy matching, pattern detection, reasoning

---

## Example: "Send all duplicated docs in my folder to my email"

### Current Behavior (❌ Fails)
```
Query: "send all duplicated docs..."
System: "Missing capability: detect_duplicates"
Result: ERROR
```

### Proposed Behavior (✅ Succeeds)

**LLM Planning Process:**

```
Step 1: Understand the Query
- User wants: duplicated documents
- Action: send via email
- Scope: "my folder" (all authorized folders)

Step 2: Decompose into Primitives
- Task 1: Get all files → use explain_files()
- Task 2: Identify duplicates → use analyze_files() with "similarity" analysis
- Task 3: Send results → use compose_email()

Step 3: Create Workflow
[
  {
    "id": 1,
    "action": "explain_files",
    "parameters": {},
    "reasoning": "Get all files to analyze for duplicates",
    "expected_output": "List of all indexed files with metadata"
  },
  {
    "id": 2,
    "action": "analyze_files",
    "parameters": {
      "files": "$step1.files",
      "analysis_type": "similarity",
      "criteria": "Find documents with similar or identical names, or identical content. Group files that are likely duplicates."
    },
    "reasoning": "Use LLM to analyze files and identify potential duplicates",
    "expected_output": "Groups of duplicate files"
  },
  {
    "id": 3,
    "action": "compose_email",
    "parameters": {
      "subject": "Duplicate Documents in Your Folder",
      "body": "Found the following duplicate documents:\n\n$step2.analysis_summary",
      "attachments": "$step2.duplicate_files",
      "send": true
    },
    "reasoning": "Send the duplicate files via email",
    "expected_output": "Email sent with duplicates"
  }
]
```

---

## Implementation Plan

### Phase 1: Add General-Purpose Analysis Tools

#### Tool 1: `analyze_files`
```python
@tool
def analyze_files(
    files: List[Dict[str, Any]],
    analysis_type: str,
    criteria: Optional[str] = None
) -> Dict[str, Any]:
    """
    General-purpose file analysis using LLM reasoning.

    Args:
        files: List of file dictionaries with metadata (from explain_files)
        analysis_type: Type of analysis - "similarity", "categorization", "pattern_detection"
        criteria: Optional natural language criteria for analysis

    Returns:
        Analysis results with identified patterns, groups, or matches

    Examples:
        - Find duplicates: analysis_type="similarity", criteria="identical or very similar names"
        - Categorize: analysis_type="categorization", criteria="group by topic or content type"
        - Find patterns: analysis_type="pattern_detection", criteria="files related to project X"
    """

    # Use LLM to analyze files based on criteria
    # LLM has access to file names, paths, descriptions, metadata
    # LLM returns structured analysis
```

#### Tool 2: `filter_list`
```python
@tool
def filter_list(
    items: List[Any],
    filter_criteria: str
) -> Dict[str, Any]:
    """
    Filter a list of items using LLM-based natural language criteria.

    Args:
        items: List of items (can be files, search results, any data)
        filter_criteria: Natural language description of what to keep

    Returns:
        Filtered list and explanation

    Examples:
        - "only PDF files"
        - "files modified in the last week"
        - "documents containing financial data"
        - "items with names starting with 'report'"
    """

    # LLM evaluates each item against criteria
    # Returns filtered list with reasoning
```

#### Tool 3: `group_items`
```python
@tool
def group_items(
    items: List[Any],
    grouping_criteria: str
) -> Dict[str, Any]:
    """
    Group items using LLM-based natural language criteria.

    Args:
        items: List of items to group
        grouping_criteria: Natural language description of how to group

    Returns:
        Dictionary of groups with items and reasoning

    Examples:
        - "by file type"
        - "by topic or subject matter"
        - "by similarity (duplicates together)"
        - "by date created"
    """

    # LLM analyzes items and creates logical groups
    # Returns structured groups with explanations
```

### Phase 2: Enhance Task Decomposition Prompts

Update `prompts/task_decomposition.md` with:

#### Section: Tool Composition Strategy

```markdown
## Tool Composition Strategy (CRITICAL!)

**IMPORTANT: Compose primitive tools instead of looking for specialized tools**

### Approach for Complex Queries

When faced with a complex query that seems to require a specialized tool:

1. **DO NOT** immediately reject due to "missing capabilities"
2. **DO** break down the query into primitive operations
3. **DO** use general-purpose tools + LLM reasoning
4. **DO** compose multiple tool calls to solve the problem

### Example Decompositions

#### Query: "Send all duplicated docs in my folder to my email"

❌ **Wrong Approach:**
- Look for `detect_duplicates` tool
- Fail with "missing capability"

✅ **Right Approach:**
1. Use `explain_files()` → get all files
2. Use `analyze_files(files, "similarity", "find duplicates")` → identify duplicates
3. Use `compose_email(attachments, send=true)` → send results

#### Query: "Find all PDF files about AI and summarize them"

✅ **Right Approach:**
1. Use `explain_files()` → get all files
2. Use `filter_list(files, "PDF files with content about AI")` → filter
3. For each file: `extract_section(file, "all")` → get content
4. Use `synthesize_content(contents)` → create summary
5. Use `reply_to_user(summary)` → present results

#### Query: "Organize my documents by topic and create folders"

✅ **Right Approach:**
1. Use `explain_files()` → get all files
2. Use `group_items(files, "by topic or subject matter")` → categorize
3. Use `organize_files(folder_name, files, move_files=true)` for each group

### Primitive Tools Available

**File Discovery:**
- `explain_files()` - Get all files with metadata
- `explain_folder(path)` - Get files in specific folder
- `search_documents(query)` - Semantic search

**File Analysis (LLM-powered):**
- `analyze_files(files, analysis_type, criteria)` - General analysis
- `filter_list(items, criteria)` - Filter by criteria
- `group_items(items, criteria)` - Group by criteria

**File Operations:**
- `organize_files(...)` - Move/copy files
- `create_zip_archive(...)` - Create archives
- `extract_section(...)` - Get content

**Content Generation:**
- `synthesize_content(...)` - Combine/analyze content
- `create_slide_deck_content(...)` - Create presentation content
- `create_detailed_report(...)` - Generate reports

### Decision Tree

```
User Query
    ↓
Does it require a SPECIFIC tool that doesn't exist?
    ↓
YES → Can I break it into primitive operations?
    ↓
YES → Use tool composition!
    ↓
NO → Check if it's truly impossible (e.g., "delete files" when no delete tool exists)
    ↓
Report missing capability ONLY if truly impossible
```
```

### Phase 3: Add Examples to Few-Shot Prompts

Add to `prompts/few_shot_examples.md`:

```markdown
### Example: Tool Composition for Complex Queries

**User Query:** "Find all duplicate documents and email them to me"

**Correct Planning (Tool Composition):**
```json
{
  "capability_assessment": {
    "required_capabilities": [
      "file listing",
      "duplicate detection",
      "email sending"
    ],
    "available_tools": [
      "explain_files - can list all files",
      "analyze_files - can detect patterns/similarities using LLM",
      "compose_email - can send emails"
    ],
    "can_complete": true,
    "reasoning": "No specialized 'detect_duplicates' tool exists, but can compose: (1) explain_files to get all files, (2) analyze_files with 'similarity' analysis to identify duplicates, (3) compose_email to send results"
  },
  "plan": [
    {
      "id": 1,
      "action": "explain_files",
      "parameters": {},
      "reasoning": "Get complete list of files to analyze",
      "expected_output": "List of all files with metadata"
    },
    {
      "id": 2,
      "action": "analyze_files",
      "parameters": {
        "files": "$step1.files",
        "analysis_type": "similarity",
        "criteria": "Identify files that are duplicates based on similar names, identical content, or matching metadata. Group potential duplicates together."
      },
      "dependencies": [1],
      "reasoning": "Use LLM analysis to identify duplicate files by comparing names and characteristics",
      "expected_output": "Groups of duplicate files with similarity scores"
    },
    {
      "id": 3,
      "action": "compose_email",
      "parameters": {
        "subject": "Duplicate Documents Found",
        "body": "Here are the duplicate documents found in your folder:\n\n$step2.summary",
        "recipient": null,
        "attachments": "$step2.duplicate_file_paths",
        "send": true
      },
      "dependencies": [2],
      "reasoning": "Send the duplicate files via email (send=true because user said 'email them to me')",
      "expected_output": "Email sent with duplicate files attached"
    }
  ]
}
```
```

---

## Key Benefits

### 1. No Hardcoding
- ✅ LLM handles pattern matching, similarity detection, categorization
- ✅ No need to write specialized Python logic for every query type
- ✅ Criteria defined in natural language, not code

### 2. Flexibility
- ✅ Works for ANY file analysis query
- ✅ Adapts to new types of questions without code changes
- ✅ User can specify custom criteria

### 3. Scalability
- ✅ Add one general tool (`analyze_files`) instead of 100 specialized tools
- ✅ Same tools work for many different queries
- ✅ LLM reasoning provides the specialization

### 4. Transparency
- ✅ User sees how the query was decomposed
- ✅ Clear workflow with reasoning at each step
- ✅ Easier to debug and improve

---

## Implementation Checklist

### Step 1: Create New Tools (Priority)
- [ ] Implement `analyze_files` with LLM-based analysis
- [ ] Implement `filter_list` for general filtering
- [ ] Implement `group_items` for general grouping
- [ ] Add tests for each tool

### Step 2: Update Prompts
- [ ] Add "Tool Composition Strategy" section to `task_decomposition.md`
- [ ] Add decision tree for when to compose vs. reject
- [ ] Add examples of tool composition to `few_shot_examples.md`
- [ ] Update tool definitions with composition guidance

### Step 3: Test with Real Queries
- [ ] "Send all duplicated docs to my email"
- [ ] "Find all PDF files about AI"
- [ ] "Group my documents by topic"
- [ ] "Show me files similar to [filename]"
- [ ] "Find all reports from last month"

### Step 4: Iterate
- [ ] Collect failure cases
- [ ] Enhance prompts based on learnings
- [ ] Add more examples to few-shot prompts

---

## Example Queries That Will Now Work

1. **"Send all duplicated docs to my email"**
   - explain_files → analyze_files(similarity) → compose_email

2. **"Find all PDFs about machine learning"**
   - explain_files → filter_list("PDFs about ML") → reply_to_user

3. **"Group my documents by topic and show me"**
   - explain_files → group_items("by topic") → reply_to_user

4. **"Find files similar to report.pdf"**
   - explain_files → analyze_files(similarity, "similar to report.pdf") → reply_to_user

5. **"Create a slide deck from all my research notes"**
   - explain_files → filter_list("research notes") → extract_section → synthesize_content → create_keynote

6. **"Email me all documents created last week"**
   - explain_files → filter_list("created last week") → compose_email

7. **"Find duplicate images and move them to a 'duplicates' folder"**
   - explain_files → filter_list("images") → analyze_files(similarity) → organize_files

---

## Technical Design: `analyze_files` Tool

```python
@tool
def analyze_files(
    files: List[Dict[str, Any]],
    analysis_type: str,
    criteria: Optional[str] = None
) -> Dict[str, Any]:
    """
    General-purpose file analysis using LLM reasoning.

    FILE AGENT - LEVEL 2: File Analysis
    Use this to analyze files for patterns, similarities, or categorization.

    Args:
        files: List of file metadata from explain_files() or explain_folder()
               Each file dict contains: file_path, file_name, file_type, size, description
        analysis_type: Type of analysis to perform
                      - "similarity": Find similar or duplicate files
                      - "categorization": Group files by category/topic
                      - "pattern_detection": Find files matching a pattern
                      - "content_match": Find files matching content criteria
        criteria: Natural language criteria for analysis (optional but recommended)
                 Examples: "find duplicates by name similarity"
                          "group by topic or subject matter"
                          "find files related to project X"

    Returns:
        Dictionary with:
        - analysis_type: The type of analysis performed
        - results: Structured results (groups, matches, patterns)
        - summary: Human-readable summary
        - details: Detailed reasoning for each finding

    Examples:
        >>> # Find duplicates
        >>> files = explain_files()["files"]
        >>> result = analyze_files(
        ...     files=files,
        ...     analysis_type="similarity",
        ...     criteria="Find files with identical or very similar names, likely duplicates"
        ... )

        >>> # Categorize by topic
        >>> result = analyze_files(
        ...     files=files,
        ...     analysis_type="categorization",
        ...     criteria="Group documents by subject matter or topic"
        ... )
    """

    logger.info(f"[FILE AGENT] Tool: analyze_files(analysis_type='{analysis_type}')")

    try:
        from openai import OpenAI
        import os

        # Build prompt for LLM analysis
        files_info = "\n".join([
            f"{i+1}. {f['file_name']} ({f['file_type']}) - {f.get('description', 'No description')}"
            for i, f in enumerate(files[:100])  # Limit to prevent token overflow
        ])

        if analysis_type == "similarity":
            task_prompt = f"""Analyze these files and identify duplicates or very similar files.
Criteria: {criteria or 'Find files with similar names, likely duplicates'}

Files:
{files_info}

Return a JSON object with:
{{
  "groups": [
    {{
      "similarity_reason": "why these files are similar",
      "files": ["file1.pdf", "file2.pdf"],
      "confidence": "high/medium/low"
    }}
  ],
  "summary": "brief summary of findings"
}}"""

        elif analysis_type == "categorization":
            task_prompt = f"""Analyze and categorize these files into logical groups.
Criteria: {criteria or 'Group by topic, subject matter, or content type'}

Files:
{files_info}

Return a JSON object with:
{{
  "categories": [
    {{
      "category_name": "Reports",
      "description": "why these belong together",
      "files": ["file1.pdf", "file2.pdf"]
    }}
  ],
  "summary": "brief summary of categorization"
}}"""

        elif analysis_type == "pattern_detection":
            task_prompt = f"""Find files matching this pattern or criteria:
{criteria}

Files:
{files_info}

Return a JSON object with:
{{
  "matches": [
    {{
      "file": "filename.pdf",
      "match_reason": "why it matches the criteria",
      "relevance": "high/medium/low"
    }}
  ],
  "summary": "brief summary of matches"
}}"""

        else:
            return {
                "error": True,
                "error_message": f"Unknown analysis_type: {analysis_type}"
            }

        # Call LLM
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a file analysis assistant. Analyze files and return structured JSON results."},
                {"role": "user", "content": task_prompt}
            ],
            temperature=0.3,
            response_format={"type": "json_object"}
        )

        analysis_result = json.loads(response.choices[0].message.content)

        return {
            "analysis_type": analysis_type,
            "criteria": criteria,
            "results": analysis_result,
            "summary": analysis_result.get("summary", "Analysis complete"),
            "file_count": len(files)
        }

    except Exception as e:
        logger.error(f"[FILE AGENT] Error in analyze_files: {e}")
        return {
            "error": True,
            "error_type": "AnalysisError",
            "error_message": str(e),
            "retry_possible": False
        }
```

---

## Conclusion

This approach:
- ✅ **Eliminates hardcoding** - LLM handles logic
- ✅ **Enables composition** - Combine simple tools for complex queries
- ✅ **Scales infinitely** - Same tools work for unlimited query types
- ✅ **Transparent** - Clear reasoning at each step
- ✅ **Flexible** - Adapts to new queries without code changes

**Next Steps:**
1. Implement `analyze_files`, `filter_list`, `group_items` tools
2. Update task decomposition prompts with composition strategy
3. Test with real complex queries
4. Iterate based on results
