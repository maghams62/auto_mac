# Generalization Architecture: Fundamental Primitives & Reasoning

## Core Insight

**Every file/folder operation reduces to 4 fundamental primitives:**

1. **DISCOVER** - Find/list things (files, folders, content)
2. **ANALYZE** - Understand/interpret things (using LLM + embeddings)
3. **TRANSFORM** - Group/filter/organize things (logical operations)
4. **ACT** - Execute actions (move, email, create, etc.)

**The LLM should learn patterns, not memorize examples.**

---

## Part 1: Minimal Primitive Toolset

### Category 1: DISCOVER (Find Things)

#### `discover`
```python
@tool
def discover(
    scope: str,  # "all_files", "folder", "search"
    query: Optional[str] = None,
    location: Optional[str] = None
) -> Dict[str, Any]:
    """
    Universal discovery tool - find files, folders, or content.

    Scope types:
    - "all_files": List all indexed files
    - "folder": List contents of a specific folder
    - "search": Semantic search for specific content

    Args:
        scope: What to discover
        query: Search query (for scope="search")
        location: Folder path (for scope="folder")

    Returns:
        List of discovered items with metadata

    Examples:
        discover(scope="all_files") → All indexed files
        discover(scope="folder", location="/Documents") → Files in Documents
        discover(scope="search", query="financial reports") → Semantic search results
    """
```

**Reasoning:** One unified discovery interface instead of `explain_files`, `explain_folder`, `search_documents`

---

### Category 2: ANALYZE (Understand Things)

#### `analyze`
```python
@tool
def analyze(
    items: List[Dict],
    task: str,
    criteria: Optional[str] = None
) -> Dict[str, Any]:
    """
    Universal LLM-powered analysis tool.

    Task types:
    - "similarity": Find similar/duplicate items
    - "categorize": Group items by category
    - "match": Find items matching criteria
    - "compare": Compare items on specific aspects
    - "extract": Extract patterns or information

    Args:
        items: List of items to analyze (from discover)
        task: What analysis to perform
        criteria: Natural language criteria (optional)

    Returns:
        Analysis results with reasoning

    Examples:
        analyze(files, "similarity", "find duplicates")
        analyze(files, "categorize", "by topic")
        analyze(files, "match", "PDFs about AI")
        analyze(files, "extract", "all financial documents")
    """
```

**Reasoning:** One analysis tool powered by LLM reasoning, not specialized tools for each analysis type

---

### Category 3: TRANSFORM (Organize Things)

#### `transform`
```python
@tool
def transform(
    items: List[Dict],
    operation: str,
    criteria: Optional[str] = None
) -> Dict[str, Any]:
    """
    Universal transformation tool - filter, group, sort, select.

    Operation types:
    - "filter": Keep only items matching criteria
    - "group": Group items by criteria
    - "sort": Sort items by criteria
    - "select": Select specific items by criteria
    - "dedupe": Remove duplicates

    Args:
        items: List of items to transform
        operation: What transformation to perform
        criteria: Natural language criteria

    Returns:
        Transformed items with reasoning

    Examples:
        transform(files, "filter", "only PDFs")
        transform(files, "group", "by file type")
        transform(files, "sort", "by date, newest first")
        transform(files, "select", "first 5 items")
    """
```

**Reasoning:** One transformation tool for all logical operations, LLM interprets the criteria

---

### Category 4: ACT (Do Things)

Keep existing specific action tools (they're already minimal):
- `organize_files` - Move/copy files to folders
- `create_zip_archive` - Create archives
- `compose_email` - Send emails
- `create_keynote` - Create presentations
- `extract_section` - Extract document content

**Reasoning:** Actions are specific and well-defined, no need to generalize further

---

## Part 2: Reasoning Framework (No Few-Shot Examples!)

Instead of showing specific examples, teach the LLM **patterns and reasoning principles**.

### Prompt Structure

```markdown
## Universal File Operation Reasoning Framework

### The 4-Stage Pipeline

Every file/folder operation follows this pattern:

1. **DISCOVER** → Find the things you need
2. **ANALYZE** → Understand what you found (if needed)
3. **TRANSFORM** → Organize/filter them (if needed)
4. **ACT** → Do something with the results

### Discovery Stage

Ask yourself: "What things do I need to work with?"

- Need all files? → `discover(scope="all_files")`
- Need files in a folder? → `discover(scope="folder", location=...)`
- Need specific content? → `discover(scope="search", query=...)`

**Output:** A list of items with metadata (paths, names, types, descriptions)

### Analysis Stage (Optional)

Ask yourself: "Do I need to understand relationships or patterns?"

- Find duplicates? → `analyze(items, "similarity", "find duplicates")`
- Categorize by topic? → `analyze(items, "categorize", "by subject matter")`
- Match criteria? → `analyze(items, "match", "financial documents")`
- Compare items? → `analyze(items, "compare", "on content")`

**Output:** Analysis results with groups, matches, or patterns identified

### Transform Stage (Optional)

Ask yourself: "Do I need to filter, group, or organize the results?"

- Filter subset? → `transform(items, "filter", "only PDFs")`
- Group items? → `transform(items, "group", "by file type")`
- Sort items? → `transform(items, "sort", "by date")`
- Select specific items? → `transform(items, "select", "top 5 largest files")`

**Output:** Transformed/organized list of items

### Action Stage

Ask yourself: "What should I do with these items?"

- Send via email? → `compose_email(attachments=items, send=true)`
- Move to folders? → `organize_files(folder_name, files, move_files=true)`
- Create archive? → `create_zip_archive(folder_path, output_name)`
- Create presentation? → extract content → create slides

**Output:** Completed action

---

## Decision Tree (Natural Language Reasoning)

Instead of examples, provide decision logic:

### Query: "Send all duplicated docs to my email"

**Step 1 - Parse Intent:**
- What things? "duplicated docs"
- Do what? "send to my email"

**Step 2 - Identify Stages:**
- Need to discover? YES - need all docs
- Need to analyze? YES - need to identify "duplicated"
- Need to transform? MAYBE - might want to filter
- Need to act? YES - "send to email"

**Step 3 - Map to Primitives:**
1. DISCOVER: `discover(scope="all_files")` → get all docs
2. ANALYZE: `analyze(items, "similarity", "find duplicates")` → identify duplicates
3. ACT: `compose_email(attachments=$step2.duplicate_files, send=true)` → send

**Step 4 - Execute Pipeline:**
```
All Files → Find Duplicates → Email Them
```

---

### Query: "Find PDFs about AI and organize them into a folder"

**Step 1 - Parse Intent:**
- What things? "PDFs about AI"
- Do what? "organize into a folder"

**Step 2 - Identify Stages:**
- Need to discover? YES - need to find files
- Need to analyze? YES - need to identify "about AI"
- Need to transform? YES - filter to "only PDFs"
- Need to act? YES - "organize into folder"

**Step 3 - Map to Primitives:**
1. DISCOVER: `discover(scope="all_files")` → get all files
2. TRANSFORM: `transform(items, "filter", "only PDF files")` → keep PDFs only
3. ANALYZE: `analyze(items, "match", "content about AI or artificial intelligence")` → find AI-related
4. ACT: `organize_files(folder_name="AI Documents", files=$step3.matched_files, move_files=true)`

**Step 4 - Execute Pipeline:**
```
All Files → Filter PDFs → Match AI Content → Organize to Folder
```

---

### Query: "Group my documents by topic and create a folder for each group"

**Step 1 - Parse Intent:**
- What things? "my documents"
- Do what? "group by topic and create folders"

**Step 2 - Identify Stages:**
- Need to discover? YES - need all documents
- Need to analyze? YES - need to identify "topics"
- Need to transform? YES - need to "group"
- Need to act? YES - "create folders" for each group

**Step 3 - Map to Primitives:**
1. DISCOVER: `discover(scope="all_files")` → get all documents
2. ANALYZE: `analyze(items, "categorize", "by topic or subject matter")` → identify topics
3. For each category from step 2:
   - ACT: `organize_files(folder_name=$category.name, files=$category.files, move_files=false)`

**Step 4 - Execute Pipeline:**
```
All Files → Categorize by Topic → Create Folder per Category
```
```

---

## Part 3: Embedding-Aware Reasoning

Since you're indexing documents with `/slash index`, teach the LLM when to use semantic search vs. listing:

```markdown
## Search Strategy: When to Use Semantic Search

### Use `discover(scope="search")` when:
- ✅ User specifies **content-based criteria**: "documents about X", "files containing Y"
- ✅ Need to find **specific topics** across many files
- ✅ Query is conceptual: "financial reports", "meeting notes from Q2"

**Why:** Embeddings understand **semantic meaning**, not just filenames

### Use `discover(scope="all_files")` when:
- ✅ User wants **all files** or **everything in a category**
- ✅ Need complete list for further analysis/transformation
- ✅ Criteria are **structural** not content-based: "PDFs", "files created last week"

**Why:** Then use `transform` or `analyze` to filter/organize

### Combined Strategy:

**Query: "Find all financial reports from last quarter"**

Option 1 (Semantic Search):
```
discover(scope="search", query="financial reports Q4 2024")
```

Option 2 (List + Filter):
```
discover(scope="all_files")
→ transform(items, "filter", "documents about financial reports")
→ transform(items, "filter", "created in last quarter")
```

**Both are valid!** Choose based on:
- Is the user's criteria primarily **content-based**? → Use semantic search
- Is it primarily **structural** (file type, date, name pattern)? → Use list + filter
```

---

## Part 4: Prompt Updates (Pattern-Based, Not Examples)

### Update to task_decomposition.md

Instead of many examples, add this section:

```markdown
## Universal File Operation Framework

### Core Principle
Every file/folder request maps to a 4-stage pipeline:
DISCOVER → ANALYZE → TRANSFORM → ACT

### Available Primitives

**Discovery:**
- `discover(scope, query, location)` - Universal file/folder discovery

**Analysis (LLM-powered):**
- `analyze(items, task, criteria)` - Pattern detection, categorization, similarity

**Transformation (LLM-powered):**
- `transform(items, operation, criteria)` - Filter, group, sort, select

**Actions (Specific):**
- `organize_files(...)` - Move/copy to folders
- `compose_email(...)` - Send via email
- `create_zip_archive(...)` - Create archives
- `extract_section(...)` - Get document content

### Reasoning Process

For any file/folder query, ask:

1. **What things do I need?** → Map to DISCOVER
   - All files? `discover(scope="all_files")`
   - Specific content? `discover(scope="search", query=...)`
   - Folder contents? `discover(scope="folder", location=...)`

2. **Do I need to understand patterns?** → Map to ANALYZE
   - Find duplicates? `analyze(..., "similarity", ...)`
   - Categorize? `analyze(..., "categorize", ...)`
   - Match criteria? `analyze(..., "match", ...)`

3. **Do I need to organize/filter?** → Map to TRANSFORM
   - Filter subset? `transform(..., "filter", ...)`
   - Group items? `transform(..., "group", ...)`
   - Sort? `transform(..., "sort", ...)`

4. **What action should I take?** → Map to ACT
   - Move files? `organize_files(...)`
   - Send email? `compose_email(...)`
   - Create archive? `create_zip_archive(...)`

### Query → Pipeline Examples

Use this mental model to decompose any query:

**"Send duplicated docs to my email"**
```
DISCOVER (all files) → ANALYZE (find duplicates) → ACT (email)
```

**"Organize PDFs by topic into folders"**
```
DISCOVER (all files) → TRANSFORM (filter PDFs) → ANALYZE (categorize) → ACT (organize)
```

**"Find financial documents and zip them"**
```
DISCOVER (search "financial") → ACT (create zip)
or
DISCOVER (all files) → ANALYZE (match "financial") → ACT (create zip)
```

**"Group images by similarity"**
```
DISCOVER (all files) → TRANSFORM (filter images) → ANALYZE (similarity) → ACT (organize by group)
```

### Key Insight

You don't need specific examples for every query type. Learn the **4-stage pattern** and apply it universally:
- Discover things
- Analyze patterns (if needed)
- Transform/organize (if needed)
- Take action

The LLM tools (`analyze`, `transform`) handle the reasoning. You compose them into pipelines.
```

---

## Part 5: Minimal Few-Shot Examples (Teach Patterns)

Add just **3 meta-examples** that demonstrate the pattern, not specific queries:

### Example 1: Discovery → Action (Simple)
```json
{
  "query": "Email all PDF files to me",
  "reasoning": "Simple pipeline: need all PDFs, then email them",
  "pipeline": ["DISCOVER", "TRANSFORM", "ACT"],
  "plan": [
    {
      "action": "discover",
      "parameters": {"scope": "all_files"},
      "reasoning": "Get all files first"
    },
    {
      "action": "transform",
      "parameters": {"items": "$step1.files", "operation": "filter", "criteria": "only PDF files"},
      "reasoning": "Filter to just PDFs"
    },
    {
      "action": "compose_email",
      "parameters": {"attachments": "$step2.filtered_items", "send": true},
      "reasoning": "Email the filtered PDFs"
    }
  ]
}
```

### Example 2: Discovery → Analysis → Action (Medium)
```json
{
  "query": "Find duplicate images and move them to a duplicates folder",
  "reasoning": "Need to find images, identify duplicates, then organize",
  "pipeline": ["DISCOVER", "TRANSFORM", "ANALYZE", "ACT"],
  "plan": [
    {
      "action": "discover",
      "parameters": {"scope": "all_files"},
      "reasoning": "Get all files"
    },
    {
      "action": "transform",
      "parameters": {"items": "$step1.files", "operation": "filter", "criteria": "only image files (jpg, png, etc)"},
      "reasoning": "Keep only images"
    },
    {
      "action": "analyze",
      "parameters": {"items": "$step2.filtered_items", "task": "similarity", "criteria": "find duplicate or very similar images"},
      "reasoning": "LLM identifies duplicate images"
    },
    {
      "action": "organize_files",
      "parameters": {"folder_name": "Duplicates", "files": "$step3.duplicate_files", "move_files": true},
      "reasoning": "Move duplicates to dedicated folder"
    }
  ]
}
```

### Example 3: Discovery → Multiple Analyses → Multiple Actions (Complex)
```json
{
  "query": "Categorize my documents by topic and create a folder for each category",
  "reasoning": "Need all docs, categorize them, then create folders for each category",
  "pipeline": ["DISCOVER", "ANALYZE", "ACT (per category)"],
  "plan": [
    {
      "action": "discover",
      "parameters": {"scope": "all_files"},
      "reasoning": "Get all documents"
    },
    {
      "action": "analyze",
      "parameters": {"items": "$step1.files", "task": "categorize", "criteria": "group by topic or subject matter"},
      "reasoning": "LLM categorizes documents into logical groups"
    },
    {
      "action": "organize_files",
      "parameters": {
        "folder_name": "$step2.category_name",
        "files": "$step2.category_files",
        "move_files": false,
        "repeat_for_each_category": true
      },
      "reasoning": "For each category from step 2, create a folder and organize files. This is a loop over categories."
    }
  ]
}
```

**That's it! Just 3 examples showing the PATTERN, not teaching specific queries.**

---

## Part 6: Benefits of This Approach

### ✅ Minimal Tool Surface Area
- 3 universal tools (`discover`, `analyze`, `transform`) + existing action tools
- LLM learns 4-stage pattern, not hundreds of specific workflows

### ✅ Infinite Generalization
- Works for ANY file/folder query
- No need to add examples for new query types
- LLM reasons about the pattern, not memorizes examples

### ✅ Embedding-Aware
- LLM knows when to use semantic search vs. listing
- Leverages your `/slash index` embeddings intelligently

### ✅ No Overwhelmed Prompts
- Teach **reasoning framework** not specific examples
- 3 meta-examples show pattern application
- LLM extrapolates to infinite queries

### ✅ Composable & Flexible
- Can combine stages in any order
- Can skip stages if not needed
- Natural language criteria make it adaptable

---

## Implementation Checklist

### Phase 1: Implement Universal Tools
- [ ] `discover(scope, query, location)` - Unify explain_files, explain_folder, search_documents
- [ ] `analyze(items, task, criteria)` - LLM-powered analysis
- [ ] `transform(items, operation, criteria)` - LLM-powered transformations

### Phase 2: Update Prompts
- [ ] Add "Universal File Operation Framework" to task_decomposition.md
- [ ] Add 4-stage pipeline reasoning guide
- [ ] Add decision tree for when to use each stage
- [ ] Add embedding-aware search strategy guide

### Phase 3: Add Minimal Examples
- [ ] 1 simple example (DISCOVER → ACT)
- [ ] 1 medium example (DISCOVER → ANALYZE → ACT)
- [ ] 1 complex example (DISCOVER → ANALYZE → loop ACT)

### Phase 4: Test Generalization
- [ ] "Send duplicated docs to email" (your original query)
- [ ] "Find PDFs about AI and organize by date"
- [ ] "Group images by topic and create slide deck"
- [ ] "Archive all documents from last month"
- [ ] "Find similar documents to report.pdf"

---

## The Key Insight

Instead of:
❌ Teaching the LLM hundreds of specific query → plan mappings

Do this:
✅ Teach the LLM **one universal pattern**: DISCOVER → ANALYZE → TRANSFORM → ACT

The LLM learns to:
1. Parse user intent into stages
2. Map each stage to a primitive tool
3. Compose primitives into a pipeline
4. Execute with natural language criteria

**Result:** Works for infinite query types without additional examples!

---

## Example: Your Query Resolved

**Query:** "Send all duplicated docs in my folder to my email"

**LLM Reasoning:**
1. Parse: Need "duplicated docs", action is "send to email"
2. Stage mapping:
   - DISCOVER: Get all docs → `discover(scope="all_files")`
   - ANALYZE: Find duplicates → `analyze(items, "similarity", "duplicates")`
   - ACT: Send email → `compose_email(attachments, send=true)`
3. Create pipeline: DISCOVER → ANALYZE → ACT
4. Execute

**No hardcoding. No specific example needed. Just pattern application!**
