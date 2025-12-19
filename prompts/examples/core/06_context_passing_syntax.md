## Context Passing Syntax

Use `$step{N}.{field}` to reference outputs from earlier steps:

- `$step1.doc_path` - Document path from search
- `$step2.extracted_text` - Text from extraction
- `$step3.screenshot_path` - Screenshot file path
- `$step4.keynote_path` - Keynote file path

This enables chaining steps together with explicit data flow.

---
