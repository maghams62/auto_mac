"""
Slash Git pipeline package.

Holds planner/executor logic for the /git command surface.
"""

from .models import (  # noqa: F401
    GitQueryMode,
    GitQueryPlan,
    GitTargetCatalog,
    GitTargetComponent,
    GitTargetRepo,
    TimeWindow,
)

