"""
Recovery Orchestrator for Cerebro OS

This module provides intelligent recovery mechanisms that use logged retry context
to make smarter decisions when handling failures and enabling LLM handoffs.
"""

import logging
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass
from datetime import datetime

from .retry_logger import RetryReason, RecoveryPriority
from .retry_context_manager import RetryContextManager, ExecutionContext
from ..utils.codebase_context import CodebaseContextGenerator


logger = logging.getLogger(__name__)


@dataclass
class RecoveryStrategy:
    """A recovery strategy with success criteria and implementation."""
    name: str
    description: str
    priority: RecoveryPriority
    conditions: List[str]  # Conditions that must be met for this strategy
    implementation: Callable
    success_criteria: List[str]
    fallback_strategies: List[str]  # Names of fallback strategies


@dataclass
class RecoveryPlan:
    """A complete recovery plan for a failed interaction."""
    interaction_id: str
    primary_strategy: str
    fallback_strategies: List[str]
    context_for_llm: str
    codebase_context: str
    estimated_success_probability: float
    reasoning: str


class RecoveryOrchestrator:
    """
    Orchestrates recovery from failures using logged retry context and codebase knowledge.

    This enables:
    1. Smart strategy selection based on failure patterns
    2. LLM handoff preparation with complete context
    3. Progressive fallback strategies
    4. Success probability estimation
    """

    def __init__(self, session_memory):
        """
        Initialize recovery orchestrator.

        Args:
            session_memory: SessionMemory instance with retry logging enabled
        """
        self.session_memory = session_memory
        self.context_generator = CodebaseContextGenerator()
        self._strategies = self._initialize_strategies()

    def create_recovery_plan(self, interaction_id: str) -> Optional[RecoveryPlan]:
        """
        Create a comprehensive recovery plan for a failed interaction.

        Args:
            interaction_id: The interaction that failed

        Returns:
            RecoveryPlan if recoverable, None if not
        """
        retry_context = self.session_memory.get_retry_context(interaction_id)
        if not retry_context:
            logger.info(f"[RECOVERY] No retry context available for {interaction_id}")
            return None

        # Analyze failure patterns
        analysis = self._analyze_failure_patterns(retry_context)

        # Select optimal strategy
        strategy = self._select_recovery_strategy(analysis)

        if not strategy:
            logger.info(f"[RECOVERY] No suitable recovery strategy found for {interaction_id}")
            return None

        # Generate LLM context
        llm_context = self._generate_llm_recovery_context(retry_context, strategy)

        # Generate codebase context
        codebase_context = self.context_generator.generate_retry_context()

        # Estimate success probability
        success_prob = self._estimate_success_probability(retry_context, strategy)

        # Create recovery plan
        plan = RecoveryPlan(
            interaction_id=interaction_id,
            primary_strategy=strategy.name,
            fallback_strategies=strategy.fallback_strategies,
            context_for_llm=llm_context,
            codebase_context=codebase_context,
            estimated_success_probability=success_prob,
            reasoning=self._generate_recovery_reasoning(retry_context, strategy, analysis)
        )

        logger.info(f"[RECOVERY] Created recovery plan for {interaction_id}: {strategy.name} (success prob: {success_prob:.2f})")
        return plan

    def execute_recovery_plan(self, plan: RecoveryPlan) -> Dict[str, Any]:
        """
        Execute a recovery plan.

        Args:
            plan: The recovery plan to execute

        Returns:
            Recovery execution results
        """
        logger.info(f"[RECOVERY] Executing recovery plan for {plan.interaction_id}")

        # Get the strategy
        strategy = self._strategies.get(plan.primary_strategy)
        if not strategy:
            return {
                "success": False,
                "error": f"Strategy {plan.primary_strategy} not found",
                "fallback_attempted": False
            }

        # Execute primary strategy
        try:
            result = strategy.implementation(plan)
            if result.get("success", False):
                logger.info(f"[RECOVERY] Primary strategy {plan.primary_strategy} succeeded")
                return result

            logger.warning(f"[RECOVERY] Primary strategy {plan.primary_strategy} failed, trying fallbacks")

        except Exception as e:
            logger.error(f"[RECOVERY] Primary strategy {plan.primary_strategy} threw exception: {e}")

        # Try fallback strategies
        for fallback_name in plan.fallback_strategies:
            fallback_strategy = self._strategies.get(fallback_name)
            if fallback_strategy:
                try:
                    logger.info(f"[RECOVERY] Trying fallback strategy: {fallback_name}")
                    result = fallback_strategy.implementation(plan)
                    if result.get("success", False):
                        logger.info(f"[RECOVERY] Fallback strategy {fallback_name} succeeded")
                        return result
                except Exception as e:
                    logger.error(f"[RECOVERY] Fallback strategy {fallback_name} failed: {e}")

        return {
            "success": False,
            "error": "All recovery strategies failed",
            "fallback_attempted": True,
            "strategies_tried": [plan.primary_strategy] + plan.fallback_strategies
        }

    def get_fresh_llm_context(self, interaction_id: str) -> str:
        """
        Get complete context for a fresh LLM to take over recovery.

        Args:
            interaction_id: The interaction that failed

        Returns:
            Formatted context string for LLM consumption
        """
        plan = self.create_recovery_plan(interaction_id)
        if not plan:
            # Fallback to basic retry context
            retry_context = self.session_memory.get_retry_context(interaction_id)
            if retry_context:
                return retry_context.get('context_for_fresh_llm', 'No context available')
            return "No recovery context available for this interaction."

        # Combine plan context with codebase knowledge
        full_context = f"""
# CEREBRO OS - FRESH LLM RECOVERY MISSION

## RECOVERY PLAN
**Primary Strategy**: {plan.primary_strategy}
**Success Probability**: {plan.estimated_success_probability:.1%}
**Fallback Strategies**: {', '.join(plan.fallback_strategies)}

## PLAN REASONING
{plan.reasoning}

## EXECUTION CONTEXT
{plan.context_for_llm}

## CODEBASE KNOWLEDGE
{plan.codebase_context}

## YOUR OBJECTIVES
1. Analyze the failure patterns and understand what went wrong
2. Apply the recommended recovery strategy
3. Use the codebase knowledge to make informed decisions
4. Execute with the accumulated wisdom from previous attempts
5. Document your approach for future learning

## AVAILABLE RESOURCES
- Complete reasoning trace from all previous attempts
- Critic feedback and correction suggestions
- Recovery strategies with success probabilities
- Full codebase documentation and architecture
- Configuration and environment details

Remember: You have access to the complete failure history. Use it to make better decisions than the previous attempts.
"""

        return full_context.strip()

    def _initialize_strategies(self) -> Dict[str, RecoveryStrategy]:
        """Initialize available recovery strategies."""
        return {
            "parameter_adjustment": RecoveryStrategy(
                name="parameter_adjustment",
                description="Modify tool parameters based on error analysis",
                priority=RecoveryPriority.HIGH,
                conditions=["error_analysis_available", "parameter_suggestions_exist"],
                implementation=self._execute_parameter_adjustment,
                success_criteria=["modified_parameters_work", "error_resolved"],
                fallback_strategies=["alternative_approach", "human_intervention"]
            ),

            "alternative_approach": RecoveryStrategy(
                name="alternative_approach",
                description="Use alternative tools or methods for the same goal",
                priority=RecoveryPriority.MEDIUM,
                conditions=["alternative_tools_available", "goal_unchanged"],
                implementation=self._execute_alternative_approach,
                success_criteria=["alternative_succeeds", "goal_achieved"],
                fallback_strategies=["simplified_approach", "human_intervention"]
            ),

            "simplified_approach": RecoveryStrategy(
                name="simplified_approach",
                description="Break down complex operations into simpler steps",
                priority=RecoveryPriority.MEDIUM,
                conditions=["complex_operation", "can_be_simplified"],
                implementation=self._execute_simplified_approach,
                success_criteria=["simpler_steps_succeed", "partial_success_acceptable"],
                fallback_strategies=["human_intervention"]
            ),

            "retry_with_backoff": RecoveryStrategy(
                name="retry_with_backoff",
                description="Retry the same operation with exponential backoff",
                priority=RecoveryPriority.LOW,
                conditions=["transient_error", "retry_possible"],
                implementation=self._execute_retry_with_backoff,
                success_criteria=["eventual_success", "error_was_transient"],
                fallback_strategies=["alternative_approach", "human_intervention"]
            ),

            "human_intervention": RecoveryStrategy(
                name="human_intervention",
                description="Escalate to human operator with complete context",
                priority=RecoveryPriority.CRITICAL,
                conditions=["max_retries_reached", "systemic_failure"],
                implementation=self._execute_human_intervention,
                success_criteria=["human_provides_solution"],
                fallback_strategies=[]
            )
        }

    def _analyze_failure_patterns(self, retry_context: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze failure patterns from retry context."""
        summary = retry_context.get("summary", {})
        retry_history = retry_context.get("retry_history", [])

        analysis = {
            "total_failures": summary.get("failed_attempts", 0),
            "error_types": list(set(r.get("error_type", "unknown") for r in retry_history)),
            "common_errors": {},
            "has_critic_feedback": any(r.get("critic_feedback") for r in retry_history),
            "has_alternatives": any(r.get("alternative_approaches") for r in retry_history),
            "avg_attempts": summary.get("total_attempts", 1),
            "last_error_type": retry_history[-1].get("error_type") if retry_history else "unknown"
        }

        # Count common errors
        for retry in retry_history:
            error_type = retry.get("error_type", "unknown")
            analysis["common_errors"][error_type] = analysis["common_errors"].get(error_type, 0) + 1

        # Determine if it's a transient vs systematic error
        analysis["transient_error"] = any(
            "timeout" in r.get("error_message", "").lower() or
            "connection" in r.get("error_message", "").lower() or
            "temporary" in r.get("error_message", "").lower()
            for r in retry_history
        )

        analysis["systemic_error"] = len(analysis["error_types"]) == 1 and analysis["total_failures"] >= 3

        return analysis

    def _select_recovery_strategy(self, analysis: Dict[str, Any]) -> Optional[RecoveryStrategy]:
        """Select the best recovery strategy based on failure analysis."""
        strategies = self._strategies

        # High priority strategies first
        if analysis.get("transient_error"):
            return strategies["retry_with_backoff"]

        if analysis.get("has_alternatives"):
            return strategies["alternative_approach"]

        if analysis.get("has_critic_feedback"):
            return strategies["parameter_adjustment"]

        if analysis.get("total_failures", 0) >= 3:
            return strategies["human_intervention"]

        # Default to alternative approach if we have multiple error types
        if len(analysis.get("error_types", [])) > 1:
            return strategies["alternative_approach"]

        # Fallback to simplified approach
        return strategies["simplified_approach"]

    def _generate_llm_recovery_context(self, retry_context: Dict[str, Any], strategy: RecoveryStrategy) -> str:
        """Generate detailed context for LLM recovery."""
        summary = retry_context.get("summary", {})
        retry_history = retry_context.get("retry_history", [])

        context = f"""
## FAILURE SUMMARY
- Total failed attempts: {summary.get('failed_attempts', 0)}
- Last failure reason: {summary.get('last_failure_reason', 'unknown')}
- Identified patterns: {', '.join(summary.get('patterns_identified', []))}

## RECOMMENDED STRATEGY: {strategy.name.upper()}
**Description**: {strategy.description}
**Why chosen**: Based on failure analysis and error patterns

## PREVIOUS ATTEMPTS SUMMARY
"""

        for i, retry in enumerate(retry_history[-3:], 1):  # Last 3 attempts
            context += f"""
### Attempt {retry.get('attempt_number', i)}
- **Failed Action**: {retry.get('failed_action', 'unknown')}
- **Error**: {retry.get('error_message', 'unknown error')}
- **Suggested Fixes**: {', '.join(retry.get('suggested_fixes', []))}
- **Alternative Approaches**: {', '.join(retry.get('alternative_approaches', []))}
"""

        context += "\n## CRITIC FEEDBACK\n"
        for retry in retry_history:
            feedback = retry.get("critic_feedback", [])
            if feedback:
                for item in feedback:
                    context += f"- {item}\n"

        context += f"""
## EXECUTION GUIDANCE
1. **Review previous attempts** and understand why they failed
2. **Apply the {strategy.name} strategy** as recommended
3. **Use suggested fixes** from the error analysis
4. **Consider alternative approaches** if the primary strategy fails
5. **Document your solution** for future learning

Remember: You have the complete reasoning trace and all previous tool calls available for reference.
"""

        return context.strip()

    def _estimate_success_probability(self, retry_context: Dict[str, Any], strategy: RecoveryStrategy) -> float:
        """Estimate the success probability of a recovery strategy."""
        summary = retry_context.get("summary", {})
        total_attempts = summary.get("total_attempts", 1)

        # Base probabilities by strategy
        base_probs = {
            "parameter_adjustment": 0.6,
            "alternative_approach": 0.5,
            "simplified_approach": 0.4,
            "retry_with_backoff": 0.3,
            "human_intervention": 0.8  # High because human can solve anything
        }

        base_prob = base_probs.get(strategy.name, 0.3)

        # Adjust based on failure patterns
        if summary.get("failed_attempts", 0) >= 3:
            base_prob *= 0.7  # Reduce probability for repeated failures

        if any("timeout" in r.get("error_message", "") for r in retry_context.get("retry_history", [])):
            if strategy.name == "retry_with_backoff":
                base_prob *= 1.5  # Increase for timeout + backoff

        # Cap between 0.1 and 0.95
        return max(0.1, min(0.95, base_prob))

    def _generate_recovery_reasoning(self, retry_context: Dict[str, Any], strategy: RecoveryStrategy, analysis: Dict[str, Any]) -> str:
        """Generate reasoning for why this recovery strategy was chosen."""
        reasoning = f"Selected {strategy.name} strategy because: "

        reasons = []

        if analysis.get("transient_error") and strategy.name == "retry_with_backoff":
            reasons.append("errors appear to be transient (timeouts, connections)")

        if analysis.get("has_alternatives") and strategy.name == "alternative_approach":
            reasons.append("alternative approaches are available from previous analysis")

        if analysis.get("has_critic_feedback") and strategy.name == "parameter_adjustment":
            reasons.append("critic agent provided specific correction suggestions")

        if analysis.get("total_failures", 0) >= 3:
            reasons.append("multiple failures indicate need for human intervention")

        if not reasons:
            reasons.append("it provides the best chance of success based on failure patterns")

        reasoning += ", ".join(reasons) + "."
        return reasoning

    # Strategy implementations
    def _execute_parameter_adjustment(self, plan: RecoveryPlan) -> Dict[str, Any]:
        """Execute parameter adjustment strategy."""
        # This would typically involve modifying tool parameters and retrying
        # For now, return a structured response indicating what should be done
        return {
            "success": False,  # Would be True if the adjustment worked
            "strategy": "parameter_adjustment",
            "message": "Parameter adjustment strategy requires LLM execution with modified parameters",
            "requires_llm_execution": True
        }

    def _execute_alternative_approach(self, plan: RecoveryPlan) -> Dict[str, Any]:
        """Execute alternative approach strategy."""
        return {
            "success": False,
            "strategy": "alternative_approach",
            "message": "Alternative approach strategy requires LLM to select and execute different tools",
            "requires_llm_execution": True
        }

    def _execute_simplified_approach(self, plan: RecoveryPlan) -> Dict[str, Any]:
        """Execute simplified approach strategy."""
        return {
            "success": False,
            "strategy": "simplified_approach",
            "message": "Simplified approach requires breaking down complex operations",
            "requires_llm_execution": True
        }

    def _execute_retry_with_backoff(self, plan: RecoveryPlan) -> Dict[str, Any]:
        """Execute retry with backoff strategy."""
        return {
            "success": False,
            "strategy": "retry_with_backoff",
            "message": "Retry with backoff requires waiting and then retrying the same operation",
            "requires_llm_execution": True,
            "backoff_seconds": 5  # Would be calculated based on attempt count
        }

    def _execute_human_intervention(self, plan: RecoveryPlan) -> Dict[str, Any]:
        """Execute human intervention strategy."""
        return {
            "success": False,
            "strategy": "human_intervention",
            "message": "Escalated to human operator with complete context",
            "requires_human_intervention": True,
            "context_provided": True
        }
