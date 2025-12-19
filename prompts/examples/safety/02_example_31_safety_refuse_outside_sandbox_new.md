# Safety Guardrail – Refuse Outside-Sandbox File Request

**User Request**: “Delete everything under /Users/shared/system_logs.”

**Reasoning**:
- The folder is outside the allowed sandbox (`config.yaml` restricts operations to the configured directories).
- File/Folder agents only perform read/write inside the sandbox; destructive actions outside must be refused.
- Return the standard impossible payload explaining the limitation.

```json
{
  "goal": "Refuse unsafe delete request outside sandbox",
  "steps": [],
  "complexity": "impossible",
  "reason": "Cannot delete /Users/shared/system_logs because it is outside the allowed sandbox. File operations are limited to configured directories."
}
```
