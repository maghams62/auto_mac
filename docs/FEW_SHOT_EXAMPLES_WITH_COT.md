# Few-Shot Examples with Chain-of-Thought Reasoning

## Design Principles

1. **Teach reasoning process**, not final answers
2. **Show the 4-stage pattern** in action
3. **Demonstrate tool selection logic**
4. **Cover diverse query types** without overwhelming
5. **Include CoT (Chain of Thought)** for each decision

---

## Example Structure

Each example includes:
- **User Query** - What the user asked
- **Reasoning (CoT)** - Step-by-step thought process
- **Stage Identification** - Which stages are needed
- **Tool Selection** - Why each tool was chosen
- **Final Plan** - The executable workflow

---

## Example 1: Simple Discovery + Action

**Pattern:** DISCOVER → ACT (2 stages)

### User Query
```
"Email all PDF files to me"
```

### Chain of Thought Reasoning

```
Step 1: Parse the request
- What does the user want? "All PDF files"
- What action? "Email to me"
- Any filtering/analysis needed? No, just PDFs

Step 2: Identify required stages
- DISCOVER: Yes - need to find all PDF files
- ANALYZE: No - no pattern detection or categorization needed
- TRANSFORM: Yes - need to filter to only PDFs
- ACT: Yes - email them

Step 3: Choose specific tools
- For DISCOVER: Use discover(scope="all_files") to get all files
  Why: Need to see all files first before filtering

- For TRANSFORM: Use transform(items, "filter", "only PDF files")
  Why: Need to keep only PDFs from all files

- For ACT: Use compose_email(attachments=$step2.filtered_items, send=true)
  Why: User said "email to me" (action verb) = send immediately

Step 4: Verify logic
- Will this get all PDFs? Yes - discover gets all, transform filters
- Will it email correctly? Yes - send=true because user said "email to me"
- Any missing steps? No
```

### Final Plan
```json
{
  "goal": "Email all PDF files to the user",
  "reasoning": "Simple pipeline: get all files, filter to PDFs, email them",
  "stages": ["DISCOVER", "TRANSFORM", "ACT"],
  "plan": [
    {
      "id": 1,
      "action": "discover",
      "parameters": {
        "scope": "all_files"
      },
      "dependencies": [],
      "reasoning": "Get complete list of all files in indexed folders",
      "expected_output": "List of all files with metadata (names, paths, types)"
    },
    {
      "id": 2,
      "action": "transform",
      "parameters": {
        "items": "$step1.files",
        "operation": "filter",
        "criteria": "only PDF files (files with .pdf extension)"
      },
      "dependencies": [1],
      "reasoning": "Filter the complete list to keep only PDF files",
      "expected_output": "Filtered list containing only PDF files"
    },
    {
      "id": 3,
      "action": "compose_email",
      "parameters": {
        "subject": "All PDF Files",
        "body": "Attached are all the PDF files from your folders.",
        "recipient": null,
        "attachments": "$step2.filtered_items",
        "send": true
      },
      "dependencies": [2],
      "reasoning": "User said 'email to me' which is an action verb, so send=true for automatic sending",
      "expected_output": "Email sent with PDF files attached"
    }
  ]
}
```

---

## Example 2: Discovery + Analysis + Action

**Pattern:** DISCOVER → ANALYZE → ACT (3 stages)

### User Query
```
"Send all duplicated docs in my folder to my email"
```

### Chain of Thought Reasoning

```
Step 1: Parse the request
- What does the user want? "Duplicated docs"
- From where? "My folder" (all indexed folders)
- What action? "Send to my email"
- Key challenge: What are "duplicates"? Need to identify them

Step 2: Identify required stages
- DISCOVER: Yes - need to get all documents first
- ANALYZE: Yes - must identify which docs are "duplicated"
- TRANSFORM: No - analysis will already group duplicates
- ACT: Yes - send via email

Step 3: Choose specific tools
- For DISCOVER: Use discover(scope="all_files")
  Why: Need all documents to compare for duplicates
  Alternative considered: discover(scope="search", query="documents")
  Why not: Too narrow, might miss files. Better to get all and analyze.

- For ANALYZE: Use analyze(items, "similarity", "find duplicates")
  Why: "Duplicates" means similar/identical files - this is a similarity detection task
  Criteria: Natural language description of what makes files duplicates
  The LLM will compare file names, sizes, potentially content

- For ACT: Use compose_email(attachments, send=true)
  Why: User said "send" (action verb) = immediate sending

Step 4: Verify logic
- How will it find duplicates? analyze() uses LLM to compare files
- What if no duplicates found? analyze() will return empty groups, email will say "no duplicates"
- Is send=true correct? Yes - "send to my email" is explicit action
```

### Final Plan
```json
{
  "goal": "Identify duplicate documents and email them to the user",
  "reasoning": "Need to discover all docs, analyze for duplicates, then email. This requires LLM reasoning to detect similarity.",
  "stages": ["DISCOVER", "ANALYZE", "ACT"],
  "plan": [
    {
      "id": 1,
      "action": "discover",
      "parameters": {
        "scope": "all_files"
      },
      "dependencies": [],
      "reasoning": "Get all files to analyze for duplicates. Cannot determine duplicates without seeing all files.",
      "expected_output": "Complete list of all indexed files with metadata"
    },
    {
      "id": 2,
      "action": "analyze",
      "parameters": {
        "items": "$step1.files",
        "task": "similarity",
        "criteria": "Find documents that are duplicates - files with identical or very similar names, or identical file sizes that suggest they are the same document. Group potential duplicates together."
      },
      "dependencies": [1],
      "reasoning": "Use LLM to identify duplicate documents by comparing file names, sizes, and characteristics. The similarity task is appropriate for finding duplicates.",
      "expected_output": "Groups of duplicate files with similarity explanations"
    },
    {
      "id": 3,
      "action": "compose_email",
      "parameters": {
        "subject": "Duplicate Documents Found",
        "body": "Here are the duplicate documents found in your folders:\n\n$step2.summary\n\nTotal groups of duplicates: $step2.group_count",
        "recipient": null,
        "attachments": "$step2.duplicate_files",
        "send": true
      },
      "dependencies": [2],
      "reasoning": "User said 'send to my email' - this is an action verb indicating immediate sending. Use send=true.",
      "expected_output": "Email sent with duplicate files attached"
    }
  ]
}
```

---

## Example 3: Discovery + Transform + Analysis + Action

**Pattern:** DISCOVER → TRANSFORM → ANALYZE → ACT (4 stages)

### User Query
```
"Find all financial PDFs from last quarter and organize them by topic into folders"
```

### Chain of Thought Reasoning

```
Step 1: Parse the request
- What does the user want? "Financial PDFs from last quarter"
- Multiple filters: (1) must be PDFs, (2) must be financial, (3) from last quarter
- What action? "Organize by topic into folders"
- Key insight: Need to categorize by topic, then create folders

Step 2: Identify required stages
- DISCOVER: Yes - could use semantic search OR get all files
- TRANSFORM: Yes - need to filter by file type and date
- ANALYZE: Yes - need to categorize by topic
- ACT: Yes - organize into folders (one per topic)

Step 3: Choose specific tools and order
- Option A: discover(search="financial") → transform(filter PDFs) → transform(filter date) → analyze(categorize) → organize
- Option B: discover(all_files) → transform(filter PDFs) → analyze(match "financial") → transform(filter date) → analyze(categorize) → organize

- Choosing Option A:
  Why: Start with semantic search for "financial" is efficient
  The term "financial" is content-based, perfect for embeddings

- DISCOVER: discover(scope="search", query="financial documents reports")
  Why: "Financial" is semantic - embeddings will find relevant docs

- TRANSFORM (filter PDFs): transform(items, "filter", "only PDF files")
  Why: From search results, keep only PDFs

- TRANSFORM (filter date): transform(items, "filter", "from last quarter")
  Why: Further narrow to date range

- ANALYZE (categorize): analyze(items, "categorize", "by financial topic")
  Why: Need to group by topic for folder organization

- ACT (organize): organize_files() per category
  Why: Create one folder per topic

Step 4: Verify logic
- Why search first vs. get all? "Financial" is content-based, embeddings excel at this
- Could we do all filters in one transform? Could, but separate steps are clearer
- Why categorize before organizing? Need topic groups to know folder names
- Is this efficient? Yes - semantic search narrows scope early
```

### Final Plan
```json
{
  "goal": "Find financial PDFs from last quarter, categorize by topic, organize into folders",
  "reasoning": "Multi-stage pipeline: semantic search for financial content, filter by type and date, categorize by topic, then organize into topic-based folders",
  "stages": ["DISCOVER", "TRANSFORM", "TRANSFORM", "ANALYZE", "ACT"],
  "plan": [
    {
      "id": 1,
      "action": "discover",
      "parameters": {
        "scope": "search",
        "query": "financial documents reports statements budgets"
      },
      "dependencies": [],
      "reasoning": "Use semantic search because 'financial' is content-based. Embeddings will find documents about financial topics even if filename doesn't contain 'financial'.",
      "expected_output": "Documents with financial-related content"
    },
    {
      "id": 2,
      "action": "transform",
      "parameters": {
        "items": "$step1.files",
        "operation": "filter",
        "criteria": "only PDF files (file extension is .pdf)"
      },
      "dependencies": [1],
      "reasoning": "User specifically requested PDFs. Filter search results to keep only PDF file types.",
      "expected_output": "Financial documents that are PDFs"
    },
    {
      "id": 3,
      "action": "transform",
      "parameters": {
        "items": "$step2.filtered_items",
        "operation": "filter",
        "criteria": "files created or modified in the last quarter (last 3 months)"
      },
      "dependencies": [2],
      "reasoning": "User specified 'from last quarter'. Filter by date to keep only recent files.",
      "expected_output": "Financial PDFs from the last quarter"
    },
    {
      "id": 4,
      "action": "analyze",
      "parameters": {
        "items": "$step3.filtered_items",
        "task": "categorize",
        "criteria": "Categorize these financial documents by topic or subject matter. Examples: Budgets, Reports, Statements, Invoices, Tax Documents, etc. Create logical categories based on the document names and descriptions."
      },
      "dependencies": [3],
      "reasoning": "Need to group by topic to organize into folders. LLM will analyze document names/metadata to create logical financial categories.",
      "expected_output": "Financial PDFs grouped by topic categories"
    },
    {
      "id": 5,
      "action": "organize_files",
      "parameters": {
        "folder_name": "Financial_$step4.category_name",
        "files": "$step4.category_files",
        "move_files": false,
        "create_subfolders": true,
        "repeat_for_each_category": true
      },
      "dependencies": [4],
      "reasoning": "For each category identified in step 4, create a folder with the category name and organize files into it. Use move_files=false to copy rather than move (safer default).",
      "expected_output": "Files organized into topic-based folders"
    }
  ]
}
```

---

## Example 4: Semantic Search vs. List+Filter Decision

**Pattern:** DISCOVER → ACT (but showing decision-making)

### User Query
```
"Email me all documents about machine learning"
```

### Chain of Thought Reasoning

```
Step 1: Parse the request
- What: "Documents about machine learning"
- Key word: "about" - this is CONTENT-based, not structural
- Action: "Email me"

Step 2: Decide discovery strategy
- Question: Should I use semantic search or list+filter?

- Analysis of "about machine learning":
  * This is a CONTENT criterion (what the doc contains)
  * Not structural (file type, date, name pattern)
  * Perfect for embeddings!
  * Files might not have "machine learning" in filename

- Decision: Use discover(scope="search")
  Why: Embeddings understand semantic meaning
  Will find: "ML_notes.pdf", "neural_networks.pdf", "AI_research.pdf"
  Even if filename doesn't contain "machine learning"

- Alternative (not chosen):
  discover(all_files) → analyze(match, "about machine learning")
  Why not: Less efficient, semantic search already filters
  When to use: If we needed additional analysis beyond matching

Step 3: Choose tools
- DISCOVER: discover(scope="search", query="machine learning AI ML artificial intelligence")
  Why: Include synonyms and related terms for better results

- ACT: compose_email(send=true)
  Why: "Email me" = action verb = immediate send

Step 4: Verify
- Will this find all ML docs? Yes - embeddings capture semantic meaning
- What if doc has ML content but different terminology? Embeddings handle it
- Should we add filters? No - content search is sufficient
```

### Final Plan
```json
{
  "goal": "Find and email documents about machine learning",
  "reasoning": "Use semantic search for content-based query. Embeddings will find ML-related documents regardless of filename.",
  "stages": ["DISCOVER", "ACT"],
  "plan": [
    {
      "id": 1,
      "action": "discover",
      "parameters": {
        "scope": "search",
        "query": "machine learning ML artificial intelligence neural networks deep learning AI models"
      },
      "dependencies": [],
      "reasoning": "Content-based query ('about machine learning') is perfect for semantic search. Include related terms (ML, AI, neural networks) to capture all relevant documents. Embeddings understand conceptual similarity.",
      "expected_output": "Documents with machine learning related content"
    },
    {
      "id": 2,
      "action": "compose_email",
      "parameters": {
        "subject": "Machine Learning Documents",
        "body": "Attached are all documents related to machine learning found in your folders.",
        "recipient": null,
        "attachments": "$step1.files",
        "send": true
      },
      "dependencies": [1],
      "reasoning": "User said 'email me' - action verb indicates immediate sending",
      "expected_output": "Email sent with ML documents"
    }
  ]
}
```

---

## Example 5: Complex Multi-Group Action

**Pattern:** DISCOVER → ANALYZE → ACT (with looping)

### User Query
```
"Categorize my images by topic and create a folder for each category"
```

### Chain of Thought Reasoning

```
Step 1: Parse the request
- What: "My images"
- Analysis: "Categorize by topic"
- Action: "Create a folder for each category"
- Key insight: This is a ONE-TO-MANY action (multiple folders)

Step 2: Identify stages
- DISCOVER: Yes - need all images
- ANALYZE: Yes - categorize by topic (LLM reasoning)
- TRANSFORM: Maybe - filter to images only
- ACT: Yes - but REPEATED for each category

Step 3: Plan the approach
- Should we search for "images" or list all?
  * "Images" is a file type (structural), not content
  * Better to list all, then filter by type

- How to categorize?
  * analyze(task="categorize", criteria="by topic")
  * LLM will look at image filenames, metadata
  * Will create logical topic groups

- How to handle multiple folders?
  * One organize_files call per category
  * Indicate this is a loop/repeat operation

Step 4: Tool selection
- DISCOVER: discover(scope="all_files")
  Why: Need all files to filter

- TRANSFORM: transform(items, "filter", "only image files")
  Why: Keep only images (jpg, png, gif, etc.)

- ANALYZE: analyze(items, "categorize", "by topic based on names")
  Why: Group images into logical topic categories

- ACT: organize_files (repeated per category)
  Why: Create one folder per topic category

Step 5: Verify
- Will it create multiple folders? Yes - repeat_for_each_category flag
- How does LLM categorize images? By analyzing filenames/metadata
- What if images don't have clear topics? LLM will create best-guess categories
```

### Final Plan
```json
{
  "goal": "Categorize images by topic and organize into separate folders",
  "reasoning": "Get all files, filter to images, use LLM to categorize by topic, then create folder for each category",
  "stages": ["DISCOVER", "TRANSFORM", "ANALYZE", "ACT (repeated)"],
  "plan": [
    {
      "id": 1,
      "action": "discover",
      "parameters": {
        "scope": "all_files"
      },
      "dependencies": [],
      "reasoning": "Get all files. Will filter to images in next step.",
      "expected_output": "Complete list of all files"
    },
    {
      "id": 2,
      "action": "transform",
      "parameters": {
        "items": "$step1.files",
        "operation": "filter",
        "criteria": "only image files (jpg, jpeg, png, gif, bmp, svg, webp, heic)"
      },
      "dependencies": [1],
      "reasoning": "User wants to categorize 'images'. Filter to keep only image file types.",
      "expected_output": "List of only image files"
    },
    {
      "id": 3,
      "action": "analyze",
      "parameters": {
        "items": "$step2.filtered_items",
        "task": "categorize",
        "criteria": "Analyze image filenames and metadata to categorize by topic or subject matter. Examples: vacation photos, work screenshots, family photos, nature images, etc. Create logical groups based on apparent topics."
      },
      "dependencies": [2],
      "reasoning": "Use LLM to analyze image names and create logical topic-based categories",
      "expected_output": "Images grouped into topic categories"
    },
    {
      "id": 4,
      "action": "organize_files",
      "parameters": {
        "folder_name": "Images_$step3.category_name",
        "files": "$step3.category_files",
        "move_files": false,
        "create_subfolders": true,
        "repeat_for_each_category": true
      },
      "dependencies": [3],
      "reasoning": "For EACH category from step 3, create a folder and organize the images. This is a repeated action - one folder per category. Use copy (move_files=false) to preserve originals.",
      "expected_output": "Multiple folders created, one per image category, with images organized"
    }
  ]
}
```

---

## Key Reasoning Patterns Demonstrated

### 1. Discovery Strategy Selection
- **Content-based** queries → `discover(scope="search")` with embeddings
- **Structural** queries → `discover(scope="all_files")` then filter
- **Folder-specific** → `discover(scope="folder", location=...)`

### 2. When to Use analyze()
- **Similarity detection** (duplicates, similar files)
- **Categorization** (group by topic/content)
- **Pattern matching** (find files matching criteria)
- **Comparison** (compare files on aspects)

### 3. When to Use transform()
- **Filtering** (keep subset matching criteria)
- **Grouping** (organize into logical groups)
- **Sorting** (order by some criteria)
- **Selecting** (pick specific items)

### 4. Action Verb Detection
- **"Email to me"** → `send: true` (automatic)
- **"Create an email"** → `send: false` (draft)
- **"Send X"** → `send: true` (explicit action)
- **"Draft X"** → `send: false` (review first)

### 5. Multi-Action Patterns
- **One-to-one**: Single action after analysis
- **One-to-many**: Repeated action per group (use `repeat_for_each`)
- **Sequential**: Chain of actions with dependencies

---

## Teaching the Pattern, Not Memorization

**These examples teach:**

✅ **HOW to think** through the 4-stage pattern
✅ **WHY certain tools** are chosen over others
✅ **WHEN to use** semantic search vs. list+filter
✅ **HOW to handle** complex multi-step queries
✅ **DECISION LOGIC** behind each step

**NOT:**

❌ Specific query → answer mappings
❌ Memorizable templates
❌ Fixed patterns for specific domains

---

## Usage in Prompts

Add these examples to `prompts/few_shot_examples.md` with structure:

```markdown
## Few-Shot Examples with Reasoning

These examples demonstrate the 4-stage pattern (DISCOVER → ANALYZE → TRANSFORM → ACT) with complete reasoning.

### Example 1: [Simple Pattern Name]
**User Query:** "..."
**Reasoning:** [Full CoT reasoning]
**Plan:** [JSON plan]

### Example 2: [Medium Pattern Name]
...

### Example 3: [Complex Pattern Name]
...
```

Keep to **5-6 strategically chosen examples** that cover:
1. Simple (2 stages)
2. Medium (3 stages)
3. Complex (4 stages)
4. Semantic search decision
5. Multi-action with looping
6. Explanation/Summarization (reply_to_user)

This teaches the **reasoning process** without overwhelming with dozens of specific cases!

---

## Example 6: Explanation/Summarization Pattern

**Pattern:** DISCOVER → reply_to_user (Information Presentation)

### User Query
```
"What files do I have in my Documents folder?"
```

### Chain of Thought Reasoning

```
Step 1: Parse the request
- What does the user want? "Files in Documents folder"
- What action? NONE - user wants information, not an action
- Key insight: This is a QUESTION, not an ACTION request

Step 2: Identify intent type
- Is this an ACTION request? (email, organize, create, move)
  → NO - user didn't ask to DO anything

- Is this an INFORMATION request? (what, show, list, explain)
  → YES - user wants to KNOW what files exist

Step 3: Identify required stages
- DISCOVER: Yes - need to find files in Documents folder
- ANALYZE: No - just listing, no pattern detection needed
- TRANSFORM: No - no filtering needed
- ACT: Yes - but ACT = reply_to_user (present information)

Step 4: Choose specific tools
- For DISCOVER: Use discover(scope="folder", location="/Documents")
  Why: User specified "Documents folder" - folder-specific discovery

  Alternative considered: discover(scope="all_files") then filter
  Why not: Less efficient, user knows exact folder

- For ACT: Use reply_to_user (NOT organize_files, NOT compose_email)
  Why: User wants INFORMATION presented, not files moved or emailed

  Key distinction:
  * "Email me the files" → compose_email (action)
  * "What files do I have?" → reply_to_user (information)
  * "Organize the files" → organize_files (action)

Step 5: Structure the reply
- Include file list with names
- Show file types
- Include explanations from discover() output
- Format clearly for user

Step 6: Verify logic
- Will user get the information they want? Yes
- Should we take any action? No - user just asked a question
- Is reply_to_user the right tool? Yes - presents information back
```

### Final Plan
```json
{
  "goal": "Show user what files exist in their Documents folder",
  "reasoning": "Information request, not action request. Use discover to find files, then reply_to_user to present the information.",
  "stages": ["DISCOVER", "ACT (reply)"],
  "plan": [
    {
      "id": 1,
      "action": "discover",
      "parameters": {
        "scope": "folder",
        "location": "/Users/siddharthsuresh/Documents"
      },
      "dependencies": [],
      "reasoning": "User asked about a specific folder. Use folder-scoped discovery to list contents with explanations.",
      "expected_output": "List of files in Documents folder with metadata and brief descriptions"
    },
    {
      "id": 2,
      "action": "reply_to_user",
      "parameters": {
        "message": "Here are the files in your Documents folder:\n\n$step1.file_list",
        "details": "Total files: $step1.total_count\n\nFile breakdown:\n$step1.file_summary",
        "artifacts": [],
        "status": "success"
      },
      "dependencies": [1],
      "reasoning": "User asked a question (what files do I have?), so reply with the information. Do NOT email, organize, or take other actions - just present the answer.",
      "expected_output": "User receives formatted list of their Documents folder contents"
    }
  ]
}
```

---

## Example 7: Summarization with Content Analysis

**Pattern:** DISCOVER → ANALYZE → reply_to_user (Analysis + Presentation)

### User Query
```
"Explain what types of documents I have and summarize them"
```

### Chain of Thought Reasoning

```
Step 1: Parse the request
- What does the user want? Understanding of their documents
- Key verbs: "Explain", "Summarize" - these are INFORMATION verbs
- No action verbs (email, send, organize, move, create)

Step 2: Identify intent type
- ACTION request? NO - no action verb present
- INFORMATION request? YES - "explain" and "summarize" want info
- Analysis needed? YES - need to categorize and understand patterns

Step 3: Identify required stages
- DISCOVER: Yes - need all documents
- ANALYZE: Yes - need to categorize by type and understand patterns
- TRANSFORM: Maybe - might group by type for clarity
- ACT: Yes - reply_to_user to present the analysis

Step 4: Choose specific tools
- For DISCOVER: Use discover(scope="all_files")
  Why: "What types of documents" requires seeing all documents

- For ANALYZE: Use analyze(items, "categorize", "by document type and purpose")
  Why: Need to understand what types exist and their purposes
  The LLM will analyze and create logical categories

- For ACT: Use reply_to_user with analysis summary
  Why: User wants to UNDERSTAND their documents, not move/email them

  Critical distinction:
  * "Explain my documents" → reply_to_user (information)
  * "Organize my documents" → organize_files (action)
  * "Email me a summary" → compose_email (action)

Step 5: Structure the reply
- Categories of documents found
- Count per category
- Brief explanation of each category
- Overall summary

Step 6: Verify logic
- Will user understand their document collection? Yes
- Is any action needed? No - pure information request
- Should we organize/email? No - user didn't ask for that
```

### Final Plan
```json
{
  "goal": "Analyze and explain the user's document collection",
  "reasoning": "Information request with analysis. Discover all files, categorize them, then present the analysis via reply_to_user.",
  "stages": ["DISCOVER", "ANALYZE", "ACT (reply)"],
  "plan": [
    {
      "id": 1,
      "action": "discover",
      "parameters": {
        "scope": "all_files"
      },
      "dependencies": [],
      "reasoning": "Need complete view of all documents to analyze and categorize",
      "expected_output": "Complete list of all indexed files"
    },
    {
      "id": 2,
      "action": "analyze",
      "parameters": {
        "items": "$step1.files",
        "task": "categorize",
        "criteria": "Analyze and categorize documents by type and purpose. Examples: Work documents, Personal files, Financial records, Media files, etc. Provide a clear explanation of what each category represents."
      },
      "dependencies": [1],
      "reasoning": "User asked to 'explain what types' - need LLM to analyze and categorize the document collection",
      "expected_output": "Documents categorized into logical groups with explanations"
    },
    {
      "id": 3,
      "action": "reply_to_user",
      "parameters": {
        "message": "Here's a summary of your document collection:\n\n$step2.category_summary",
        "details": "Total documents: $step1.total_count\n\nBreakdown by category:\n$step2.detailed_breakdown\n\nKey insights:\n$step2.insights",
        "artifacts": [],
        "status": "success"
      },
      "dependencies": [2],
      "reasoning": "User asked to 'explain' and 'summarize' - this is an information request. Present the analysis results via reply_to_user, do not email or organize.",
      "expected_output": "User receives comprehensive explanation and summary of their documents"
    }
  ]
}
```

---

## Example 8: Explanation with Specific Folder

**Pattern:** DISCOVER (folder) → reply_to_user (Direct Information)

### User Query
```
"Show me what's in my Downloads folder"
```

### Chain of Thought Reasoning

```
Step 1: Parse the request
- What does the user want? Contents of Downloads folder
- Key verb: "Show me" - this is INFORMATION/PRESENTATION
- No action requested

Step 2: Identify intent type
- ACTION? NO - "show" doesn't mean move/email/organize
- INFORMATION? YES - user wants to SEE the contents

Step 3: Identify required stages
- DISCOVER: Yes - need contents of Downloads folder
- ANALYZE: No - just listing, no analysis needed
- TRANSFORM: No - no filtering or grouping needed
- ACT: Yes - reply_to_user to show the information

Step 4: Choose specific tools
- For DISCOVER: Use discover(scope="folder", location="/Downloads")
  Why: Specific folder mentioned - use folder-scoped discovery
  This will return files with brief explanations

- For ACT: Use reply_to_user
  Why: "Show me" = present information to user

  Common confusion to avoid:
  * "Show me the files" → reply_to_user ✓
  * "Email me the files" → compose_email ✓
  * "Show me" ≠ "send me" (different intent!)

Step 5: Verify logic
- Will user see their Downloads? Yes
- Should we do anything with files? No
- Is reply_to_user correct? Yes - it presents information
```

### Final Plan
```json
{
  "goal": "Display contents of Downloads folder to user",
  "reasoning": "Pure information request. Discover folder contents and present via reply_to_user.",
  "stages": ["DISCOVER", "ACT (reply)"],
  "plan": [
    {
      "id": 1,
      "action": "discover",
      "parameters": {
        "scope": "folder",
        "location": "/Users/siddharthsuresh/Downloads"
      },
      "dependencies": [],
      "reasoning": "User asked about specific folder. Use folder discovery to get contents with explanations.",
      "expected_output": "List of files in Downloads with metadata"
    },
    {
      "id": 2,
      "action": "reply_to_user",
      "parameters": {
        "message": "Contents of your Downloads folder:\n\n$step1.file_list",
        "details": "Total items: $step1.total_count\n\n$step1.file_details",
        "artifacts": [],
        "status": "success"
      },
      "dependencies": [1],
      "reasoning": "User said 'show me' which is a presentation request, not an action request. Use reply_to_user to display the information.",
      "expected_output": "User sees formatted list of Downloads folder contents"
    }
  ]
}
```

---

## Key Patterns for Information vs. Action

### Information Verbs → reply_to_user
- "What files do I have?"
- "Show me my documents"
- "List the files in X folder"
- "Explain my documents"
- "Summarize my files"
- "What's in my Downloads?"
- "Tell me about my photos"

**Pattern:** DISCOVER → (optional ANALYZE) → **reply_to_user**

### Action Verbs → Specific Actions
- "Email me the files" → compose_email
- "Send the documents" → compose_email
- "Organize into folders" → organize_files
- "Create a zip" → create_zip_archive
- "Move the files" → organize_files

**Pattern:** DISCOVER → (optional ANALYZE) → **action_tool**

### The Critical Distinction

```
User says: "What files do I have?"
           ↓
    Information request
           ↓
    DISCOVER → reply_to_user ✓

User says: "Email me my files"
           ↓
      Action request
           ↓
    DISCOVER → compose_email ✓
```

**Never confuse information requests with action requests!**

---

## Updated Example Coverage

With these additions, we now have **8 strategic examples** covering:

1. ✅ Simple action (DISCOVER → TRANSFORM → ACT)
2. ✅ Duplicate detection (DISCOVER → ANALYZE → ACT)
3. ✅ Complex multi-stage (all 4 stages)
4. ✅ Semantic search decision
5. ✅ Multi-action with looping
6. ✅ **Folder explanation (DISCOVER → reply_to_user)**
7. ✅ **Document summarization (DISCOVER → ANALYZE → reply_to_user)**
8. ✅ **Information presentation (show/explain pattern)**

**Total token budget:** ~6,500 tokens (still manageable!)

---

## When to Use reply_to_user

### ✅ Use reply_to_user when:
- User asks a question (what, which, how many, where)
- User wants information presented (show, list, display, tell)
- User wants explanation (explain, summarize, describe)
- User wants analysis results shown (NOT acted upon)
- **No action verb present** (no email, send, organize, create, move)

### ❌ Don't use reply_to_user when:
- User requests an action (email, send, organize, create)
- User wants files moved, copied, or modified
- User wants something sent or shared
- **Action verb present** → Use appropriate action tool

### Decision Tree

```
Parse user query
     ↓
Does it contain action verb?
     ↓
YES → Use action tool (compose_email, organize_files, etc.)
     ↓
NO → Is it a question or information request?
     ↓
YES → Use reply_to_user
     ↓
```

This teaches the LLM to **route information requests through reply_to_user** instead of always trying to take actions!
