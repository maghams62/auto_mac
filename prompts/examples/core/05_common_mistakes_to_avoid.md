## Common Mistakes to Avoid

❌ **Skipping search step**
```json
{
  "steps": [
    {"action": "extract_section", "parameters": {"doc_path": "unknown"}}
  ]
}
```

✅ **Always search first**
```json
{
  "steps": [
    {"action": "search_documents", "parameters": {"query": "..."}},
    {"action": "extract_section", "parameters": {"doc_path": "$step1.doc_path"}}
  ]
}
```

---

❌ **Missing dependencies**
```json
{
  "steps": [
    {"id": 1, "action": "search_documents"},
    {"id": 2, "action": "compose_email", "dependencies": []}  // Wrong!
  ]
}
```

✅ **Explicit dependencies**
```json
{
  "steps": [
    {"id": 1, "action": "search_documents"},
    {"id": 2, "action": "compose_email", "dependencies": [1]}  // Correct
  ]
}
```

---

❌ **Vague parameters**
```json
{
  "action": "extract_section",
  "parameters": {"section": "the important part"}
}
```

✅ **Specific parameters**
```json
{
  "action": "extract_section",
  "parameters": {"section": "summary" | "page 5" | "introduction"}
}
```

---
