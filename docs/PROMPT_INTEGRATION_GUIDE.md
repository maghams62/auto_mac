# Prompt Integration Guide: Few-Shot Examples with CoT

## Overview

This guide explains how to integrate the Chain-of-Thought few-shot examples into your prompts **without overwhelming the LLM** while maximizing learning.

---

## The Strategy

### ❌ What NOT to Do
- Add 50+ examples trying to cover every case
- Put all examples in one massive prompt
- Show only final plans without reasoning
- Use domain-specific examples (too narrow)

### ✅ What TO Do
- Add 5-6 **strategically chosen** examples
- Show **complete reasoning process** (CoT)
- Teach **patterns** not specific cases
- Balance **simple, medium, complex** examples

---

## Prompt File Structure

### File 1: `prompts/task_decomposition.md`

**Purpose:** Core reasoning framework and pattern

**Add Section:**
```markdown
## Universal File Operation Framework

### The 4-Stage Pattern
Every file/folder operation follows this pattern:
DISCOVER → ANALYZE → TRANSFORM → ACT

[... framework from GENERALIZATION_ARCHITECTURE.md ...]

### Decision Trees

**When to use discover(scope="search"):**
- Content-based queries: "documents about X"
- Semantic concepts: "financial reports", "vacation photos"
- Leverage embeddings for meaning

**When to use discover(scope="all_files"):**
- Structural queries: "all PDFs", "files from last week"
- Need complete list for analysis
- Then use transform/analyze to filter

[... decision logic ...]
```

**Token Budget:** ~1,500 tokens (framework only, no examples here)

---

### File 2: `prompts/few_shot_examples.md`

**Purpose:** Concrete examples with reasoning

**Structure:**
```markdown
# Few-Shot Examples with Chain-of-Thought Reasoning

## How to Use These Examples

These examples demonstrate the 4-stage pattern with complete reasoning.
Learn the THINKING PROCESS, not just the final plans.

Each example shows:
1. User query
2. Step-by-step reasoning (CoT)
3. Stage identification
4. Tool selection logic
5. Final executable plan

---

## Example 1: Simple Pattern (DISCOVER → TRANSFORM → ACT)

**Query:** "Email all PDF files to me"

**Reasoning Process:**
[Full CoT from FEW_SHOT_EXAMPLES_WITH_COT.md]

**Final Plan:**
[JSON plan]

---

## Example 2: Medium Pattern (DISCOVER → ANALYZE → ACT)

**Query:** "Send all duplicated docs in my folder to my email"

**Reasoning Process:**
[Full CoT]

**Final Plan:**
[JSON plan]

---

## Example 3: Complex Pattern (DISCOVER → TRANSFORM → ANALYZE → ACT)

**Query:** "Find financial PDFs from last quarter and organize by topic"

**Reasoning Process:**
[Full CoT]

**Final Plan:**
[JSON plan]

---

## Example 4: Semantic Search Decision

**Query:** "Email me all documents about machine learning"

**Reasoning Process:**
[Shows decision between semantic search vs list+filter]

**Final Plan:**
[JSON plan]

---

## Example 5: Multi-Action with Looping

**Query:** "Categorize my images by topic and create folders"

**Reasoning Process:**
[Shows how to handle one-to-many actions]

**Final Plan:**
[JSON plan]

---

## Key Patterns Learned

From these 5 examples, you learned:
✅ How to apply the 4-stage pattern
✅ When to use semantic search vs. list+filter
✅ How to detect and handle action verbs (email vs create)
✅ How to chain tools with dependencies
✅ How to handle multi-action scenarios with looping

**Apply these patterns to ANY file/folder query!**
```

**Token Budget:** ~4,000 tokens (5 examples with full CoT)

---

## Token Allocation Strategy

**Total Budget:** ~5,500 tokens for examples and framework

| Section | Tokens | Purpose |
|---------|--------|---------|
| Framework (task_decomposition.md) | 1,500 | Pattern, decision trees, principles |
| Example 1 (Simple) | 600 | Basic pattern application |
| Example 2 (Medium) | 900 | Duplicate detection (your use case!) |
| Example 3 (Complex) | 1,000 | Multi-stage with all 4 stages |
| Example 4 (Search) | 800 | Semantic search decision-making |
| Example 5 (Loop) | 700 | Multi-action patterns |
| **Total** | **5,500** | Complete learning material |

**Result:** Comprehensive learning without overwhelming (vs. 10,000+ for 50 examples)

---

## Example Selection Rationale

### Example 1: Simple Pattern ✓
- **Why:** Shows basic pipeline
- **Teaches:** Simple discovery → filter → action
- **Pattern:** 2-3 stages
- **Coverage:** Structural filtering (file types)

### Example 2: Duplicate Detection ✓
- **Why:** This is YOUR actual use case!
- **Teaches:** Analysis for pattern detection
- **Pattern:** 3 stages with analyze()
- **Coverage:** LLM-powered similarity detection

### Example 3: Complex Multi-Stage ✓
- **Why:** Shows all 4 stages in action
- **Teaches:** When to use each stage
- **Pattern:** Full 4-stage pipeline
- **Coverage:** Semantic search + transforms + analysis

### Example 4: Semantic Search ✓
- **Why:** Critical decision point
- **Teaches:** When embeddings are powerful
- **Pattern:** Content-based vs structural queries
- **Coverage:** Embedding-aware reasoning

### Example 5: Multi-Action ✓
- **Why:** Common pattern for organization
- **Teaches:** Looping actions, one-to-many
- **Pattern:** Repeated actions per group
- **Coverage:** Complex organization workflows

**These 5 cover ~90% of query patterns while teaching reasoning skills**

---

## Integration Steps

### Step 1: Update task_decomposition.md

Add the framework section:

```bash
# Add after existing "Planning Philosophy" section
# Around line 50 in task_decomposition.md

## Universal File Operation Framework

[Insert framework from GENERALIZATION_ARCHITECTURE.md]
- 4-stage pattern explanation
- Decision trees
- Tool selection logic
```

**Location:** `prompts/task_decomposition.md` (lines 50-100 approximately)

---

### Step 2: Update few_shot_examples.md

Replace or supplement existing examples:

```bash
# In prompts/few_shot_examples.md
# Clear old domain-specific examples
# Add new pattern-based examples with CoT

## Few-Shot Examples with Chain-of-Thought Reasoning

[Insert 5 examples from FEW_SHOT_EXAMPLES_WITH_COT.md]
```

**Location:** `prompts/few_shot_examples.md` (full replacement or major revision)

---

### Step 3: Update tool_definitions.md

Add the universal tools:

```bash
# Add new section in prompts/tool_definitions.md

## Universal Discovery & Analysis Tools

### discover(scope, query, location)
[Definition and usage]

### analyze(items, task, criteria)
[Definition and usage]

### transform(items, operation, criteria)
[Definition and usage]
```

**Location:** `prompts/tool_definitions.md` (add before existing tools)

---

## Testing After Integration

Test with queries that WERE NOT in examples:

### Novel Query 1
"Find all Excel files about budgets and zip them"
- **Expected:** discover → transform(filter Excel) → analyze(match budgets) → create_zip
- **Tests:** Combination of filtering and content matching

### Novel Query 2
"Show me documents similar to quarterly_report.pdf"
- **Expected:** discover → analyze(similarity, "similar to quarterly_report.pdf")
- **Tests:** Similarity detection with reference file

### Novel Query 3
"Organize my videos by year into folders"
- **Expected:** discover → transform(filter videos) → transform(group by year) → organize (loop)
- **Tests:** Temporal grouping and organization

### Novel Query 4
"Email me presentation files from last month"
- **Expected:** discover → transform(filter presentations) → transform(filter date) → compose_email
- **Tests:** Multiple filters before action

**Success Criteria:**
✅ LLM applies pattern to novel queries
✅ Correct tool selection
✅ Proper reasoning in dependencies
✅ Appropriate use of semantic search vs. filtering

---

## Monitoring & Iteration

### What to Watch

1. **Token usage:** Are prompts staying under 6,000 tokens?
2. **Generalization:** Does it work for queries not in examples?
3. **Reasoning quality:** Are plans well-reasoned with dependencies?
4. **Tool selection:** Is discover/analyze/transform used appropriately?

### When to Add Examples

**Add a new example if:**
- ❌ A pattern fails consistently (after trying 3+ times)
- ❌ A common query type is not covered by existing patterns
- ❌ Users frequently hit edge cases

**Don't add examples if:**
- ✅ It's a rare edge case (handle with better framework explanation)
- ✅ It's a variation of existing pattern (LLM should generalize)
- ✅ It would add >800 tokens (refine existing examples instead)

### Iteration Process

```
1. Deploy with 5 examples
2. Collect failures over 1 week
3. Analyze failure patterns
4. Update framework if pattern issue
5. Add 1 example if genuinely novel pattern
6. Remove least useful example if over token budget
```

---

## Example Prompt Assembly

**Final prompt to LLM will be:**

```
[System Message]

[task_decomposition.md with framework] (~1,500 tokens)
↓
[tool_definitions.md with universal tools] (~2,000 tokens)
↓
[few_shot_examples.md with 5 CoT examples] (~4,000 tokens)
↓
[User Query]
```

**Total context:** ~7,500 tokens + user query

**Leaves room for:** LLM's response (plan generation with reasoning)

---

## Benefits of This Approach

### ✅ Efficient Learning
- 5 examples teach patterns for infinite queries
- LLM learns HOW to think, not WHAT to memorize
- CoT reasoning makes decision process transparent

### ✅ Token Efficient
- ~5,500 tokens vs. 10,000+ for comprehensive coverage
- Leaves room for user query and response
- No prompt truncation issues

### ✅ Maintainable
- Easy to add/remove examples
- Framework updates don't require example changes
- Clear separation of concerns

### ✅ Generalizable
- Patterns apply to novel queries
- No need for examples of every query type
- LLM extrapolates from learned reasoning

---

## Common Pitfalls to Avoid

### ❌ Too Many Examples
- **Problem:** LLM gets confused, picks wrong pattern
- **Symptom:** Plans that mix patterns inappropriately
- **Fix:** Stick to 5-6 strategic examples

### ❌ Examples Without CoT
- **Problem:** LLM memorizes answers, doesn't learn reasoning
- **Symptom:** Works for similar queries, fails for variations
- **Fix:** Always include full reasoning process

### ❌ Domain-Specific Examples
- **Problem:** LLM thinks pattern only applies to that domain
- **Symptom:** Fails on queries from different domains
- **Fix:** Use generic file operation examples

### ❌ Inconsistent Pattern Teaching
- **Problem:** Examples use different reasoning approaches
- **Symptom:** Inconsistent plan quality
- **Fix:** All examples follow same 4-stage framework

---

## Success Metrics

After integration, you should see:

✅ **High success rate** (>80%) on novel queries
✅ **Consistent reasoning** in generated plans
✅ **Appropriate tool usage** (discover, analyze, transform)
✅ **Good CoT explanations** in plan reasoning fields
✅ **Efficient pipelines** (minimal unnecessary steps)
✅ **Correct action verb detection** (send vs. draft)

---

## Summary

**Integration Plan:**
1. Add framework to `task_decomposition.md` (~1,500 tokens)
2. Add 5 CoT examples to `few_shot_examples.md` (~4,000 tokens)
3. Update `tool_definitions.md` with universal tools (~500 tokens)

**Total:** ~6,000 tokens for complete learning system

**Result:** LLM learns pattern-based reasoning, handles infinite query types, no overwhelming prompts!

**Next Step:** Implement the 3 universal tools, then integrate these examples and test!
