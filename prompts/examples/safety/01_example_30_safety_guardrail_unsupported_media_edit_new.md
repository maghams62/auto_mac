## Example 30: SAFETY GUARDRAIL – UNSUPPORTED MEDIA EDIT (NEW!)

**Reasoning (chain of thought):**
- Request: “Trim interview.mp4 to the first minute and replace the audio track.” No available tools perform video or audio editing.
- Capability assessment → only document, presentation, email, web, social, writing, mapping, etc. Tools exist. Multimedia editing is unsupported.
- Respond with impossibility rationale outlining what *is* supported.

```json
{
  "goal": "Unable to complete request",
  "steps": [],
  "complexity": "impossible",
  "reason": "Missing required capabilities: video trimming and audio replacement. Available tools handle document search/extraction, writing/presentation generation, email automation, social summaries, mapping, and folder management. Multimedia editing is not supported."
}
```

---
