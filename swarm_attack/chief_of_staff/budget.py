"""Budget management for Chief of Staff autopilot execution.

This module provides budget-related functions for:
- Calculating default estimated costs by goal type
- Checking budget availability before execution
- Computing remaining budget
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from swarm_attack.chief_of_staff.goal_tracker import DailyGoal


# Default costs by goal type (in USD)
DEFAULT_FEATURE_COST = 3.0
DEFAULT_BUG_COST = 2.0
DEFAULT_SPEC_COST = 1.0
DEFAULT_MANUAL_COST = 0.0


def get_default_estimated_cost(goal: "DailyGoal") -> float:
    """Get the default estimated cost for a goal based on its type.

    Args:
        goal: The DailyGoal to estimate cost for.

    Returns:
        Default cost in USD:
        - Feature-linked: $3
        - Bug-linked: $2
        - Spec-linked: $1
        - Manual (no links): $0
    """
    if goal.linked_feature:
        return DEFAULT_FEATURE_COST
    elif goal.linked_bug:
        return DEFAULT_BUG_COST
    elif goal.linked_spec:
        return DEFAULT_SPEC_COST
    else:
        return DEFAULT_MANUAL_COST


def get_effective_cost(goal: "DailyGoal") -> float:
    """Get the effective cost for a goal.

    If the goal has an explicit estimated_cost_usd, use that.
    Otherwise, use the default cost based on goal type.

    Args:
        goal: The DailyGoal to get cost for.

    Returns:
        The effective cost in USD.
    """
    if goal.estimated_cost_usd is not None:
        return goal.estimated_cost_usd
    return get_default_estimated_cost(goal)


def check_budget(remaining_budget: float, min_execution_budget: float) -> bool:
    """Check if there is sufficient budget for execution.

    Args:
        remaining_budget: The remaining budget in USD.
        min_execution_budget: The minimum budget required to execute.

    Returns:
        True if remaining_budget >= min_execution_budget, False otherwise.
    """
    return remaining_budget >= min_execution_budget


def calculate_remaining_budget(budget_usd: float, cost_spent_usd: float) -> float:
    """Calculate the remaining budget.

    Args:
        budget_usd: Total budget in USD.
        cost_spent_usd: Amount already spent in USD.

    Returns:
        Remaining budget (budget_usd - cost_spent_usd).
    """
    return budget_usd - cost_spent_usd