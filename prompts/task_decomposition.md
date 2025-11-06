# Task Decomposition Prompt

## Objective

Given a user request, break it down into a sequence of executable steps using available tools.

## Available Tools

1. **search_documents** - Find documents by semantic search
2. **extract_section** - Extract specific content from documents
3. **take_screenshot** - Capture page images from documents
4. **compose_email** - Create and send emails
5. **create_keynote** - Generate Keynote presentations
6. **create_pages_doc** - Generate Pages documents

## Instructions

1. Parse the user's request to understand the goal
2. Identify all required actions to achieve the goal
3. Determine dependencies between actions
4. Create an ordered execution plan
5. Include reasoning for each step

## Output Format

```json
{
  "goal": "What the user wants to achieve",
  "steps": [
    {
      "id": 1,
      "action": "tool_name",
      "parameters": {
        "param1": "value1"
      },
      "dependencies": [],
      "reasoning": "Why this step is needed",
      "expected_output": "What this step will produce"
    }
  ],
  "complexity": "simple | medium | complex"
}
```

## Guidelines

- **Simple tasks** (1-2 steps): Direct execution
- **Medium tasks** (3-5 steps): Sequential with some dependencies
- **Complex tasks** (6+ steps): Multi-stage with branching logic

- Always start with search if document needs to be found
- Extract before processing (screenshots, content)
- Compose/create actions come last (they consume earlier outputs)
- Use context passing between steps

## Few-Shot Examples

See [few_shot_examples.md](./few_shot_examples.md) for detailed examples of task decomposition.
