# Slash Prompt Bundle

These prompts scope the LLM behavior for slash commands that short-circuit
the main LangGraph planner (e.g., `/slack`, `/git`). Each slash agent gets
its own lightweight instruction pack that can be injected when the command
is active (tier‑2 overlays).

## Conventions

1. **Stateless role** – the LLM acts as the “owner” of the slash subsystem.
   It must interpret the user command, call the exposed tools, and format the
   final answer without inventing new capabilities.
2. **Plan hooks** – instructions reference the `interpret → execute → respond`
   lifecycle so the automation agent can emit the same plan/disambiguation
   animation as other commands.
3. **Graph awareness** – slash prompts describe the structured payload we
   expect back (entities, services, APIs, evidence) so the orchestrator can
   log graph nodes/edges or feed downstream systems later.
4. **No hardcoded outputs** – the prompt tells the model to rely on
   tool outputs (Slack fetchers, Git helpers, etc.) and never emit canned
   summaries.

Add new slash prompts as `prompts/slash/<agent>_*.md` and keep them modular
so tiered prompt loaders can cherry-pick only what the active command needs.

