"""
Programmatic plan validator - prevents hallucinated tools.

This validator runs BEFORE the LLM evaluator to catch issues programmatically.
It's a hard constraint that cannot be bypassed by prompt engineering.
"""

import logging
from typing import Dict, Any, List, Tuple


logger = logging.getLogger(__name__)


class PlanValidator:
    """
    Programmatic validator that enforces hard constraints on plans.

    This is NOT LLM-based - it's deterministic validation that prevents:
    - Hallucinated tools
    - Invalid dependencies
    - Missing required parameters
    - Malformed plan structure
    """

    def __init__(self, available_tools: List[Dict[str, Any]]):
        """
        Initialize validator with available tools.

        Args:
            available_tools: List of tool specifications
        """
        self.available_tools = available_tools
        self.tool_names = {tool["name"] for tool in available_tools}
        self.tool_specs = {tool["name"]: tool for tool in available_tools}

        logger.info(f"PlanValidator initialized with {len(self.tool_names)} valid tools: {sorted(self.tool_names)}")

    def validate_plan(self, plan: List[Dict[str, Any]]) -> Tuple[bool, List[Dict[str, Any]]]:
        """
        Validate a plan with hard programmatic checks.

        Args:
            plan: List of plan steps

        Returns:
            Tuple of (is_valid, list_of_errors)
            Each error is: {"step_id": str, "error_type": str, "message": str, "severity": str}
        """
        errors = []

        # Check 1: Plan must be a non-empty list
        if not isinstance(plan, list):
            errors.append({
                "step_id": None,
                "error_type": "invalid_plan_structure",
                "message": f"Plan must be a list, got {type(plan)}",
                "severity": "error"
            })
            return False, errors

        if len(plan) == 0:
            errors.append({
                "step_id": None,
                "error_type": "empty_plan",
                "message": "Plan cannot be empty",
                "severity": "error"
            })
            return False, errors

        # Track seen step IDs for dependency validation
        seen_step_ids = set()

        # Validate each step
        for i, step in enumerate(plan):
            step_id = step.get("id", f"step_{i}")
            seen_step_ids.add(step_id)

            # Check 2: Step must have required fields
            required_fields = ["id", "tool"]
            for field in required_fields:
                if field not in step:
                    errors.append({
                        "step_id": step_id,
                        "error_type": "missing_required_field",
                        "message": f"Step missing required field: '{field}'",
                        "severity": "error"
                    })

            # Check 3: Tool must exist (CRITICAL - prevents hallucination)
            tool_name = step.get("tool")
            if tool_name and tool_name not in self.tool_names:
                # This is the key check that prevents hallucinated tools
                errors.append({
                    "step_id": step_id,
                    "error_type": "hallucinated_tool",
                    "message": f"Tool '{tool_name}' does not exist. Available tools: {sorted(self.tool_names)}",
                    "severity": "error",
                    "suggested_tools": self._suggest_similar_tools(tool_name)
                })

            # Check 4: Validate dependencies
            deps = step.get("deps", [])
            for dep_id in deps:
                # Check dependency exists
                if dep_id not in seen_step_ids:
                    # Check if it's a forward reference (not allowed in DAG)
                    future_step_ids = {plan[j].get("id", f"step_{j}") for j in range(i+1, len(plan))}
                    if dep_id in future_step_ids:
                        errors.append({
                            "step_id": step_id,
                            "error_type": "forward_dependency",
                            "message": f"Step depends on future step '{dep_id}' - this creates a cycle or forward reference",
                            "severity": "error"
                        })
                    else:
                        errors.append({
                            "step_id": step_id,
                            "error_type": "missing_dependency",
                            "message": f"Step depends on non-existent step '{dep_id}'",
                            "severity": "error"
                        })

                # Check for self-dependency
                if dep_id == step_id:
                    errors.append({
                        "step_id": step_id,
                        "error_type": "self_dependency",
                        "message": "Step cannot depend on itself",
                        "severity": "error"
                    })

            # Check 5: Validate required parameters for the tool
            if tool_name and tool_name in self.tool_specs:
                param_errors = self._validate_tool_parameters(step_id, tool_name, step.get("inputs", {}))
                errors.extend(param_errors)

        # Check 6: Detect cycles in dependency graph
        cycle_errors = self._detect_cycles(plan)
        errors.extend(cycle_errors)

        # Determine if plan is valid
        has_critical_errors = any(e["severity"] == "error" for e in errors)
        is_valid = not has_critical_errors

        if not is_valid:
            logger.error(f"Plan validation failed with {len(errors)} errors")
            for error in errors:
                logger.error(f"  - {error['error_type']}: {error['message']}")
        else:
            logger.info(f"Plan validation passed ({len(errors)} warnings)")

        return is_valid, errors

    def _validate_tool_parameters(
        self,
        step_id: str,
        tool_name: str,
        inputs: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Validate that tool parameters are present and correct type.

        Args:
            step_id: Step ID
            tool_name: Tool name
            inputs: Input parameters

        Returns:
            List of parameter validation errors
        """
        errors = []
        tool_spec = self.tool_specs.get(tool_name)

        if not tool_spec:
            return errors

        # Get required parameters from tool spec
        required_params = tool_spec.get("io", {}).get("in", [])

        # Parse parameter names from "name: type" format
        param_names = []
        for param_spec in required_params:
            if ":" in param_spec:
                param_name = param_spec.split(":")[0].strip()
                param_names.append(param_name)

        # Check if required parameters are provided
        # Note: We're lenient here because parameters might reference previous steps
        # We just warn if a parameter is completely missing
        for param_name in param_names:
            if param_name not in inputs and not param_name.startswith("Optional"):
                # This is a warning, not an error, because the parameter might be optional
                # or might be filled in by the executor
                errors.append({
                    "step_id": step_id,
                    "error_type": "missing_parameter",
                    "message": f"Parameter '{param_name}' not provided for tool '{tool_name}'",
                    "severity": "warning"
                })

        return errors

    def _detect_cycles(self, plan: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Detect cycles in the dependency graph using DFS.

        Args:
            plan: List of plan steps

        Returns:
            List of cycle errors
        """
        errors = []

        # Build adjacency list
        graph = {}
        for step in plan:
            step_id = step.get("id")
            deps = step.get("deps", [])
            graph[step_id] = deps

        # DFS to detect cycles
        visited = set()
        rec_stack = set()

        def has_cycle(node, path):
            visited.add(node)
            rec_stack.add(node)
            path.append(node)

            for neighbor in graph.get(node, []):
                if neighbor not in visited:
                    if has_cycle(neighbor, path):
                        return True
                elif neighbor in rec_stack:
                    # Found a cycle
                    cycle_start = path.index(neighbor)
                    cycle = path[cycle_start:] + [neighbor]
                    errors.append({
                        "step_id": node,
                        "error_type": "dependency_cycle",
                        "message": f"Cycle detected: {' -> '.join(cycle)}",
                        "severity": "error"
                    })
                    return True

            path.pop()
            rec_stack.remove(node)
            return False

        for node in graph:
            if node not in visited:
                has_cycle(node, [])

        return errors

    def _suggest_similar_tools(self, hallucinated_tool: str) -> List[str]:
        """
        Suggest similar valid tools based on name similarity.

        Args:
            hallucinated_tool: The hallucinated tool name

        Returns:
            List of suggested tool names
        """
        # Simple similarity: check if any real tool name contains part of the hallucinated name
        suggestions = []

        hallucinated_lower = hallucinated_tool.lower()

        for tool_name in self.tool_names:
            tool_lower = tool_name.lower()

            # Check for substring matches
            if hallucinated_lower in tool_lower or tool_lower in hallucinated_lower:
                suggestions.append(tool_name)

        # Common hallucinations and their correct alternatives
        hallucination_map = {
            "list_files": ["organize_files"],
            "create_folder": ["organize_files"],
            "create_directory": ["organize_files"],
            "move_files": ["organize_files"],
            "copy_files": ["organize_files"],
            "find_files": ["search_documents", "organize_files"],
            "read_file": ["extract_section"],
            "write_file": ["create_pages_doc"],
            "send_email": ["compose_email"],
            "make_presentation": ["create_keynote", "create_keynote_with_images"],
        }

        if hallucinated_tool in hallucination_map:
            suggestions.extend(hallucination_map[hallucinated_tool])

        return list(set(suggestions))  # Remove duplicates


def validate_plan_strict(
    plan: List[Dict[str, Any]],
    available_tools: List[Dict[str, Any]]
) -> Tuple[bool, List[Dict[str, Any]]]:
    """
    Strict programmatic validation - NO LLM involved.

    This is a convenience function that creates a validator and validates the plan.

    Args:
        plan: Plan to validate
        available_tools: List of available tool specifications

    Returns:
        Tuple of (is_valid, list_of_errors)
    """
    validator = PlanValidator(available_tools)
    return validator.validate_plan(plan)
