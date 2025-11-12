# Folder/File Agent Capability Audit

## Executive Summary

This audit examines the current folder and file agent capabilities in the auto_mac system, identifying gaps in natural language intent interpretation and suggesting expansions to support diverse file organization routines that users commonly perform on their laptops.

## Current Folder Agent Capabilities

### Core Tools (from `src/agent/folder_agent.py`)

1. **folder_list** - Lists folder contents (non-recursive, alphabetically sorted)
   - ✅ Returns items with name, type, size, modified, extension
   - ✅ Sandbox validation enforced
   - ✅ Non-recursive (top-level only)

2. **folder_plan_alpha** - Plans filename normalization (dry-run)
   - ✅ Proposes lowercase, underscores, no special chars
   - ✅ Read-only operation
   - ✅ Returns detailed plan with changes needed

3. **folder_apply** - Executes rename plans (with confirmation required)
   - ✅ Atomic renames with conflict detection
   - ✅ Dry-run support required before execution
   - ✅ Security validation on every operation

4. **folder_organize_by_type** - Groups files by extension
   - ✅ Creates extension-based subfolders (PDF/, TXT/, etc.)
   - ✅ Moves files into matching folders
   - ✅ Dry-run preview support

5. **folder_find_duplicates** - Content-based duplicate detection
   - ✅ SHA-256 hash comparison
   - ✅ Reports wasted space
   - ✅ Groups duplicates by content

6. **folder_check_sandbox** - Path validation
   - ✅ Validates paths against configured sandbox
   - ✅ Resolves symlinks and checks parent directory traversal

### Current File Agent Capabilities

### Core Tools (from `src/agent/file_agent.py`)

1. **search_documents** - Semantic document search
   - ✅ LLM-determined search parameters (no hardcoded top_k)
   - ✅ Returns relevance scores and metadata
   - ✅ Content previews included

2. **extract_section** - Content extraction with LLM interpretation
   - ✅ No hardcoded patterns - uses LLM for section understanding
   - ✅ Supports semantic search for content location
   - ✅ Page-level extraction

3. **take_screenshot** - Document visual capture
   - ✅ Converts PDF pages to images
   - ✅ Configurable page selection

4. **organize_files** - LLM-driven file organization
   - ✅ Uses LLM to determine which files match categories
   - ✅ Creates folders and moves files
   - ✅ Provides reasoning for each decision

5. **create_zip_archive** - File compression
   - ✅ Configurable filtering by extensions
   - ✅ Include/exclude patterns supported

## Current Prompt Coverage

### Folder Agent Policy (`prompts/folder_agent_policy.md`)
- ✅ Comprehensive intent parsing for basic operations
- ✅ Two-step confirmation discipline
- ✅ Scope badge requirements
- ✅ Error handling patterns
- ✅ Limited to core folder operations (list, organize, check_scope)

### File Agent Examples (`prompts/examples/file/`)
- ✅ Document search and extraction patterns
- ✅ File organization by category
- ✅ ZIP archive creation

### Folder Agent Examples (`prompts/examples/general/`)
- ✅ Duplicate detection and email reporting
- ✅ Duplicate listing and space analysis
- ❌ **GAP**: No folder-specific examples in dedicated folder/ directory

## Key Gaps in Natural Language Intent Support

### Missing Folder Operations
1. **Folder Summaries** - "summarize this folder", "what's in my documents folder"
   - Current: Raw list output
   - Missing: LLM-generated summaries, statistics, insights

2. **File Explanations** - "explain this file", "what is this document about"
   - Current: File metadata only
   - Missing: Content-based explanations using semantic search

3. **Advanced Organization Patterns**
   - "group files by date", "organize by size", "sort by modification date"
   - "move old files to archive", "create backup folders"
   - "organize by project" (semantic grouping)

4. **Content-Based Operations**
   - "find files containing X", "group documents by topic"
   - "show me files related to Y"

### Missing Cross-Agent Integration
1. **Folder + File Agent Handoffs**
   - Folder listing → File search for content explanation
   - Duplicate detection → File extraction for content comparison

2. **Folder + Email Agent Integration**
   - Send folder summaries via email
   - Email file organization reports

### Missing Output Formats
1. **Structured Summaries**
   - File type distributions
   - Size analysis
   - Age analysis
   - Content themes (when integrated with search)

2. **Visual Organization Previews**
   - Tree structures
   - Before/after comparisons
   - Impact assessments

## User Intent Diversity Analysis

### Common Laptop File Organization Tasks (Not Currently Supported)

1. **Discovery & Understanding**
   - "What's taking up space in my downloads?"
   - "Show me my biggest files"
   - "What files haven't I touched in months?"
   - "Summarize what's in this project folder"

2. **Content-Based Organization**
   - "Group all my work documents together"
   - "Move all photos to a media folder"
   - "Organize files by topic or project"

3. **Maintenance & Cleanup**
   - "Archive files older than 6 months"
   - "Delete empty folders"
   - "Find and merge duplicate folders"
   - "Clean up my desktop organization"

4. **Search & Navigation**
   - "Find files related to [topic]"
   - "Show me all PDFs about [subject]"
   - "What documents mention [keyword]?"

5. **Archival & Backup**
   - "Create monthly archives"
   - "Backup my important documents"
   - "Organize files by year/month"

## Technical Implementation Gaps

### Missing Tools in Folder Agent
1. **folder_summarize** - Generate folder statistics and insights
2. **folder_sort_by** - Sort files by various criteria (date, size, type)
3. **folder_archive_old** - Move old files to archive folders
4. **folder_find_by_content** - Cross-agent handoff to file search
5. **folder_explain_file** - Content explanation via file agent

### Missing Tools in File Agent
1. **Enhanced organize_files** - More sophisticated categorization
2. **batch_extract** - Extract from multiple files
3. **file_compare** - Content comparison tools

### Orchestrator Limitations
1. **Limited Intent Recognition** - Only basic folder operations
2. **No Cross-Agent Handoffs** - Can't seamlessly use file tools for folder operations
3. **Rigid Output Formatting** - Limited to tabular displays

## Recommendations

### Phase 1: Core Expansion
1. Add folder summary and explanation tools
2. Extend orchestrator intent recognition
3. Create folder-specific few-shot examples
4. Add cross-agent handoff patterns

### Phase 2: Advanced Features
1. Content-based organization
2. Archival automation
3. Visual organization previews
4. Integration with email for reports

### Phase 3: AI-Enhanced Organization
1. Semantic folder grouping
2. Content theme analysis
3. Predictive organization suggestions
4. Learning from user patterns

## Success Metrics

### Coverage Goals
- Support 80% of common file organization tasks
- Enable natural language queries for folder operations
- Seamless integration between folder and file operations
- Rich, actionable output formats

### Quality Goals
- Zero sandbox violations
- Clear error messages and recovery options
- Consistent two-step confirmation for writes
- Performance suitable for large folders (1000+ files)

## Implementation Priority

### High Priority (User Pain Points)
1. Folder summaries and statistics
2. File explanations using content
3. Basic sorting and filtering operations
4. Cross-agent folder+file operations

### Medium Priority (Nice-to-Have)
1. Advanced organization patterns
2. Archival automation
3. Visual previews and comparisons

### Low Priority (Future Enhancement)
1. AI-driven organization suggestions
2. Predictive cleanup recommendations
3. Integration with external storage services
