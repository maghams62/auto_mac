# Prompt Consumption Audit Report

## Executive Summary

The codebase contains approximately **6000 lines** of few-shot examples across multiple files:
- `docs/FEW_SHOT_EXAMPLES_WITH_COT.md`: 991 lines
- `prompts/few_shot_examples.md`: 4974 lines

**Critical Finding**: The system loads the entire corpus for most agent requests, which can consume significant context windows and potentially cause hallucination or degraded reasoning performance.

## Current Prompt Loading Architecture

### 1. Primary Loading Mechanism: PromptRepository
- **Location**: `src/prompt_repository.py`
- **Design**: Modular, agent-scoped loading via `index.json` configuration
- **Usage**: `src/agent/agent.py` loads prompts via `PromptRepository().to_prompt_block("automation")`
- **Fallback**: Falls back to monolithic `prompts/few_shot_examples.md` if PromptRepository fails

### 2. Monolithic Fallback File
- **Path**: `prompts/few_shot_examples.md`
- **Size**: 4974 lines (~500KB)
- **Status**: Still used as fallback, not deprecated

### 3. Legacy Documentation File
- **Path**: `docs/FEW_SHOT_EXAMPLES_WITH_COT.md`
- **Size**: 991 lines
- **Usage**: Documentation only (referenced in docs but not loaded by runtime)

## Current Usage Patterns

### Agent Loading (src/agent/agent.py)
```python
# Primary path: Modular loading
from src.prompt_repository import PromptRepository
repo = PromptRepository()
few_shot_content = repo.to_prompt_block("automation")
prompts["few_shot_examples"] = few_shot_content

# Fallback path: Monolithic loading
fallback_path = prompts_dir / "few_shot_examples.md"
if fallback_path.exists():
    prompts["few_shot_examples"] = fallback_path.read_text()
```

### Modular Structure (prompts/examples/index.json)
- **Categories**: 14 categories (core, general, email, maps, stocks, etc.)
- **Agent Mappings**: 30+ agents mapped to relevant category combinations
- **Example Count**: 65 individual example files across categories

## Risk Assessment

### High-Risk Areas
1. **Full Corpus Loading**: Automation agent loads 5 categories (core, general, safety, cross_domain, disambiguation) totaling ~2000+ lines
2. **Fallback Mechanism**: If PromptRepository fails, loads entire 4974-line monolithic file
3. **No Granular Access**: Current API loads entire categories, not individual examples
4. **Caching**: `load_category()` uses `@lru_cache(maxsize=128)` but still loads entire categories

### Potential Issues
- **Context Window Pressure**: 2000+ lines of examples per request
- **Reasoning Degradation**: Overwhelming context may dilute task-specific reasoning
- **Inconsistent Access**: Some agents may need different example subsets

## Recommendations

1. **Implement Atomic Task Access**: Modify PromptRepository to support task-specific example loading
2. **Add Consumption Monitoring**: Track token usage and example access patterns
3. **Validate Chunking**: Ensure examples are loaded on-demand, not eagerly
4. **Expand Example Coverage**: Add diverse examples for underrepresented task types

## Next Steps

1. Audit current example coverage and identify gaps
2. Implement task-atomic prompt loading
3. Add monitoring and validation safeguards
4. Test performance impact of granular access
