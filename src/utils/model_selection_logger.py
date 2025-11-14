"""
Model selection logging utilities.

Logs model selection decisions including rationale, temperature, and parameters.
"""

import logging
from typing import Dict, Any, Optional

from .trajectory_logger import get_trajectory_logger

logger = logging.getLogger(__name__)


def log_model_selection(
    model: str,
    temperature: float,
    max_tokens: Optional[int] = None,
    max_completion_tokens: Optional[int] = None,
    reasoning: Optional[str] = None,
    config: Optional[Dict[str, Any]] = None,
    session_id: Optional[str] = None,
    interaction_id: Optional[str] = None,
    component: str = "unknown"
):
    """
    Log model selection decision.
    
    Args:
        model: Model name selected
        temperature: Temperature value
        max_tokens: Max tokens (for non-o-series models)
        max_completion_tokens: Max completion tokens (for o-series models)
        reasoning: Reasoning for model selection
        config: Configuration dict
        session_id: Session identifier
        interaction_id: Interaction identifier
        component: Component making the selection
    """
    trajectory_logger = get_trajectory_logger(config)
    
    # Determine reasoning if not provided
    if not reasoning:
        if model.startswith(("o1", "o3", "o4")):
            reasoning = f"Selected o-series model {model} (temperature=1.0 required, max_completion_tokens={max_completion_tokens})"
        else:
            reasoning = f"Selected model {model} with temperature={temperature}, max_tokens={max_tokens}"
    
    trajectory_logger.log_trajectory(
        session_id=session_id or "unknown",
        interaction_id=interaction_id,
        phase="planning",
        component=component,
        decision_type="model_selection",
        input_data={
            "config_model": config.get("openai", {}).get("model") if config else None,
            "config_temperature": config.get("openai", {}).get("temperature") if config else None
        },
        output_data={
            "model": model,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "max_completion_tokens": max_completion_tokens,
            "is_o_series": model.startswith(("o1", "o3", "o4"))
        },
        reasoning=reasoning,
        model_used=model,
        success=True
    )
    
    logger.debug(f"[MODEL SELECTION] {component}: {model} (temp={temperature}, max_tokens={max_tokens or max_completion_tokens})")

