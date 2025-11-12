"""
Folder Agent LLM Orchestrator - Implements the LLM-first policy for folder operations.

This module extends the basic folder agent with LLM-driven workflow orchestration
that follows the folder agent policy.
"""

from typing import Dict, Any, Optional
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
import json
import logging
from pathlib import Path

from ..utils import get_temperature_for_model

logger = logging.getLogger(__name__)


class FolderAgentOrchestrator:
    """
    LLM orchestrator for folder operations.

    Implements the folder agent policy:
    - Parses user intent
    - Selects appropriate tool chain
    - Enforces confirmation discipline
    - Presents results with scope badge
    """

    def __init__(self, config: Dict[str, Any]):
        """Initialize the orchestrator."""
        self.config = config
        openai_config = config.get("openai", {})
        self.llm = ChatOpenAI(
            model=openai_config.get("model", "gpt-4o"),
            temperature=get_temperature_for_model(config, default_temperature=0.0),
            api_key=openai_config.get("api_key")
        )

        # Load policy prompt
        policy_path = Path(__file__).parent.parent.parent / "prompts" / "folder_agent_policy.md"
        if policy_path.exists():
            with open(policy_path, 'r') as f:
                self.policy_prompt = f.read()
        else:
            logger.warning(f"[FOLDER AGENT LLM] Policy file not found: {policy_path}")
            self.policy_prompt = "Follow folder agent policy for LLM-driven folder management."

        logger.info("[FOLDER AGENT LLM] Orchestrator initialized")

    def execute_with_policy(
        self,
        user_task: str,
        folder_agent,
        conversation_history: Optional[list] = None
    ) -> Dict[str, Any]:
        """
        Execute a folder task using LLM policy.

        This method:
        1. Parses user intent using LLM
        2. Determines tool chain to execute
        3. Executes tools in sequence
        4. Formats output with scope badge
        5. Handles confirmations if needed

        Args:
            user_task: User's natural language task
            folder_agent: FolderAgent instance
            conversation_history: Optional conversation context

        Returns:
            Execution result with formatted output
        """
        logger.info(f"[FOLDER AGENT LLM] Executing task: {user_task}")

        try:
            # Get tool descriptions
            tools = folder_agent.get_tools()
            tool_descriptions = []
            for tool in tools:
                tool_descriptions.append(f"### {tool.name}\n{tool.description}\n")

            # Create planning prompt
            planning_prompt = f"""{self.policy_prompt}

## Available Tools

{chr(10).join(tool_descriptions)}

## Your Task

User request: "{user_task}"

Analyze the user's intent and determine:
1. Which tool(s) to call
2. In what order
3. What parameters to use
4. Whether confirmation is needed

Respond with JSON:
{{
  "intent": "list|organize|check_scope|other",
  "tool_chain": [
    {{"tool": "tool_name", "parameters": {{}}, "reason": "why"}},
    ...
  ],
  "needs_confirmation": true/false,
  "scope_folder": "folder path or null for default",
  "explanation": "Brief explanation for user"
}}

Remember: ALWAYS use dry_run=True for folder_apply initially.
"""

            # Get LLM plan
            messages = [
                SystemMessage(content="You are the Folder Agent orchestrator. Follow the policy strictly."),
                HumanMessage(content=planning_prompt)
            ]

            response = self.llm.invoke(messages)
            content = response.content.strip()

            # Extract JSON
            import re
            json_match = re.search(r'\{[\s\S]*\}', content)
            if json_match:
                content = json_match.group()

            plan = json.loads(content)

            logger.info(f"[FOLDER AGENT LLM] Plan: intent={plan['intent']}, tools={len(plan['tool_chain'])}")

            # Execute tool chain
            results = []
            for step in plan['tool_chain']:
                tool_name = step['tool']
                parameters = step['parameters']
                reason = step.get('reason', '')

                logger.info(f"[FOLDER AGENT LLM] Executing {tool_name}: {reason}")

                result = folder_agent.execute(tool_name, parameters)
                results.append({
                    "tool": tool_name,
                    "parameters": parameters,
                    "result": result,
                    "reason": reason
                })

                # If any tool failed, stop execution
                if result.get('error'):
                    logger.error(f"[FOLDER AGENT LLM] Tool {tool_name} failed: {result.get('error_message')}")
                    break

            # Format output with scope badge and results
            formatted_output = self._format_output(
                plan=plan,
                results=results,
                folder_agent=folder_agent
            )

            return {
                "success": True,
                "intent": plan['intent'],
                "results": results,
                "formatted_output": formatted_output,
                "needs_confirmation": plan.get('needs_confirmation', False)
            }

        except Exception as e:
            logger.error(f"[FOLDER AGENT LLM] Execution error: {e}", exc_info=True)
            return {
                "error": True,
                "error_type": "OrchestrationError",
                "error_message": str(e),
                "retry_possible": True
            }

    def _format_output(
        self,
        plan: Dict[str, Any],
        results: list,
        folder_agent
    ) -> str:
        """
        Format execution results with scope badge and readable presentation.

        Args:
            plan: LLM-generated plan
            results: List of tool execution results
            folder_agent: FolderAgent instance

        Returns:
            Formatted output string
        """
        from src.automation.folder_tools import FolderTools

        tools = FolderTools(self.config)
        allowed_folder = tools.allowed_folder

        output_lines = []

        # Add scope badge
        output_lines.append(f"🔒 Folder scope: {Path(allowed_folder).name} (absolute: {allowed_folder})")
        output_lines.append("")

        # Add explanation
        if plan.get('explanation'):
            output_lines.append(plan['explanation'])
            output_lines.append("")

        # Format results based on intent
        intent = plan.get('intent', 'other')

        if intent == 'list':
            # Format folder listing
            for result_item in results:
                if result_item['tool'] == 'folder_list':
                    result = result_item['result']
                    if not result.get('error'):
                        output_lines.append(self._format_folder_list(result))

        elif intent == 'organize':
            # Format organization plan
            for result_item in results:
                if result_item['tool'] == 'folder_plan_alpha':
                    result = result_item['result']
                    if not result.get('error'):
                        output_lines.append(self._format_organization_plan(result))

                elif result_item['tool'] == 'folder_apply':
                    result = result_item['result']
                    if not result.get('error'):
                        if result.get('dry_run'):
                            output_lines.append("✓ Dry-run validation successful")
                            output_lines.append("")
                            output_lines.append("⚠️ This was a dry-run. No files were modified.")
                            output_lines.append("To apply changes, confirm and I'll execute with dry_run=False.")
                        else:
                            output_lines.append(self._format_apply_result(result))

        elif intent == 'check_scope':
            # Format scope check
            for result_item in results:
                if result_item['tool'] == 'folder_check_sandbox':
                    result = result_item['result']
                    if result.get('is_safe'):
                        output_lines.append(f"✅ {result.get('message')}")
                        output_lines.append(f"   Resolved: {result.get('resolved_path')}")
                    else:
                        output_lines.append(f"🚫 {result.get('message')}")
                        output_lines.append(f"   Allowed: {result.get('allowed_folder')}")

        else:
            # Generic formatting
            for result_item in results:
                result = result_item['result']
                if result.get('error'):
                    output_lines.append(f"❌ {result.get('error_message')}")
                else:
                    output_lines.append(f"✅ {result_item['tool']}: Success")

        return "\n".join(output_lines)

    def _format_folder_list(self, result: Dict[str, Any]) -> str:
        """Format folder listing as table."""
        items = result.get('items', [])
        folder_path = result.get('relative_path', result.get('folder_path', ''))
        total = result.get('total_count', 0)

        lines = []
        lines.append(f"📁 Contents of {folder_path}/ ({total} items)")
        lines.append("")
        lines.append("NAME" + " " * 20 + "TYPE    SIZE        MODIFIED")
        lines.append("─" * 60)

        for item in items:
            name = item['name'][:24].ljust(24)
            item_type = item['type'].ljust(7)

            if item['type'] == 'file':
                size = self._format_size(item.get('size', 0))
            else:
                size = "-"
            size = size.ljust(11)

            # Format modified time
            import time
            modified = item.get('modified', 0)
            time_diff = time.time() - modified
            if time_diff < 86400:
                modified_str = "today"
            elif time_diff < 172800:
                modified_str = "yesterday"
            elif time_diff < 604800:
                modified_str = f"{int(time_diff / 86400)} days ago"
            else:
                modified_str = f"{int(time_diff / 604800)} weeks ago"

            lines.append(f"{name} {item_type} {size} {modified_str}")

        return "\n".join(lines)

    def _format_organization_plan(self, result: Dict[str, Any]) -> str:
        """Format organization plan as diff table."""
        plan = result.get('plan', [])
        needs_changes = result.get('needs_changes', False)
        changes_count = result.get('changes_count', 0)

        lines = []
        lines.append(f"📋 Normalization Plan ({changes_count} changes needed)")
        lines.append("")
        lines.append("CURRENT NAME" + " " * 12 + "→  PROPOSED NAME" + " " * 11 + "REASON")
        lines.append("─" * 80)

        for item in plan:
            if not item.get('needs_change'):
                continue

            current = item['current_name'][:24].ljust(24)
            proposed = item['proposed_name'][:24].ljust(24)
            reason = item.get('reason', '')[:30]

            lines.append(f"{current} →  {proposed} {reason}")

        lines.append("")
        lines.append(f"✓ {len([p for p in plan if not p.get('needs_change')])} items already normalized")
        lines.append(f"⚠️ {changes_count} items need changes")

        if needs_changes:
            lines.append("")
            lines.append("Would you like me to apply these changes? (I'll validate first with a dry-run)")

        return "\n".join(lines)

    def _format_apply_result(self, result: Dict[str, Any]) -> str:
        """Format apply result with success/failure details."""
        applied = result.get('applied', [])
        skipped = result.get('skipped', [])
        errors = result.get('errors', [])
        success = result.get('success', False)

        lines = []

        if success:
            lines.append(f"✅ Successfully renamed {len(applied)} items")
        else:
            lines.append(f"⚠️ Partially completed ({len(applied)}/{len(applied) + len(errors)} succeeded)")

        if applied:
            lines.append("")
            lines.append("✅ Successfully renamed:")
            for item in applied[:10]:  # Show first 10
                lines.append(f"   - {item['current_name']} → {item['proposed_name']}")
            if len(applied) > 10:
                lines.append(f"   ... and {len(applied) - 10} more")

        if errors:
            lines.append("")
            lines.append("❌ Failed:")
            for item in errors[:10]:
                lines.append(f"   - {item['current_name']}: {item['error']}")
            if len(errors) > 10:
                lines.append(f"   ... and {len(errors) - 10} more")

        return "\n".join(lines)

    def _format_size(self, size_bytes: int) -> str:
        """Format file size in human-readable format."""
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes / (1024 * 1024):.1f} MB"
        else:
            return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"
