"""CampaignExecutor - executes daily goals for campaigns.

This module provides the CampaignExecutor class that manages execution of
campaign day plans via the AutopilotRunner.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING, Optional

from swarm_attack.chief_of_staff.campaigns import (
    Campaign,
    CampaignState,
    CampaignStore,
    DayPlan,
)
from swarm_attack.chief_of_staff.goal_tracker import DailyGoal, GoalStatus, GoalPriority

if TYPE_CHECKING:
    from swarm_attack.chief_of_staff.config import ChiefOfStaffConfig
    from swarm_attack.chief_of_staff.autopilot_runner import AutopilotRunner


@dataclass
class DayExecutionResult:
    """Result from executing a day's goals in a campaign.

    Attributes:
        goals_completed: Number of goals that were completed successfully.
        goals_blocked: List of goal IDs that were blocked or failed.
        cost_usd: Total cost in USD for the day's execution.
        needs_replan: Whether the campaign needs replanning due to being behind schedule.
    """

    goals_completed: int
    goals_blocked: list[str]
    cost_usd: float
    needs_replan: bool


class CampaignExecutor:
    """Executes daily goals for campaigns.

    The CampaignExecutor coordinates campaign execution by:
    1. Loading the campaign and finding the day plan for the specified date
    2. Converting day plan goals to DailyGoal objects
    3. Running the goals via AutopilotRunner
    4. Updating campaign state with results (cost, progress)
    5. Detecting if replanning is needed

    Usage:
        executor = CampaignExecutor(
            config=config,
            campaign_store=campaign_store,
            autopilot_runner=autopilot_runner,
        )

        result = await executor.execute_day("campaign-id", day=date.today())
    """

    def __init__(
        self,
        config: "ChiefOfStaffConfig",
        campaign_store: CampaignStore,
        autopilot_runner: "AutopilotRunner",
    ) -> None:
        """Initialize CampaignExecutor.

        Args:
            config: Chief of Staff configuration.
            campaign_store: Store for loading/saving campaigns.
            autopilot_runner: Runner for executing goals.
        """
        self.config = config
        self.campaign_store = campaign_store
        self.autopilot_runner = autopilot_runner

    async def execute_day(
        self,
        campaign_id: str,
        day: Optional[date] = None,
    ) -> DayExecutionResult:
        """Execute goals for a specific day in a campaign.

        Args:
            campaign_id: The ID of the campaign to execute.
            day: The date to execute goals for. Defaults to today.

        Returns:
            DayExecutionResult with execution outcome.

        Raises:
            ValueError: If campaign not found or not in active state.
        """
        # Default to today if not specified
        if day is None:
            day = date.today()

        # Load campaign
        campaign = await self.campaign_store.load(campaign_id)
        if campaign is None:
            raise ValueError(f"Campaign not found: {campaign_id}")

        # Check campaign is active
        if campaign.state != CampaignState.ACTIVE:
            raise ValueError(
                f"Campaign '{campaign_id}' is not active (state: {campaign.state.value})"
            )

        # Find day plan for the specified date
        day_plan = self._find_day_plan(campaign, day)

        if day_plan is None or not day_plan.goals:
            # No goals for this day
            return DayExecutionResult(
                goals_completed=0,
                goals_blocked=[],
                cost_usd=0.0,
                needs_replan=campaign.needs_replan(),
            )

        # Convert day plan goals to DailyGoal objects
        daily_goals = self._convert_to_daily_goals(day_plan, campaign_id)

        # Execute via autopilot runner
        result = self.autopilot_runner.start(
            goals=daily_goals,
            budget_usd=self.config.budget_usd,
            duration_minutes=self.config.duration_minutes,
        )

        # Extract blocked goals from session
        goals_blocked = self._extract_blocked_goals(result.session.goals)

        # Update campaign state
        campaign.spent_usd += result.total_cost_usd
        if result.goals_completed > 0:
            campaign.current_day = day_plan.day_number

        # Mark day plan as complete if all goals completed
        if result.goals_completed == result.goals_total:
            day_plan.status = "complete"
        day_plan.actual_cost_usd = result.total_cost_usd

        # Save updated campaign
        await self.campaign_store.save(campaign)

        return DayExecutionResult(
            goals_completed=result.goals_completed,
            goals_blocked=goals_blocked,
            cost_usd=result.total_cost_usd,
            needs_replan=campaign.needs_replan(),
        )

    def _find_day_plan(self, campaign: Campaign, day: date) -> Optional[DayPlan]:
        """Find the day plan for a specific date.

        Args:
            campaign: The campaign to search.
            day: The date to find.

        Returns:
            The DayPlan for that date, or None if not found.
        """
        for day_plan in campaign.day_plans:
            if day_plan.date == day:
                return day_plan
        return None

    def _convert_to_daily_goals(
        self, day_plan: DayPlan, campaign_id: str
    ) -> list[DailyGoal]:
        """Convert day plan goals to DailyGoal objects.

        Args:
            day_plan: The day plan with goals.
            campaign_id: The campaign ID for linking.

        Returns:
            List of DailyGoal objects ready for execution.
        """
        daily_goals = []
        for i, goal_desc in enumerate(day_plan.goals):
            goal = DailyGoal(
                goal_id=f"{campaign_id}-day{day_plan.day_number}-goal{i+1}",
                description=goal_desc,
                priority=GoalPriority.MEDIUM,
                status=GoalStatus.PENDING,
                estimated_minutes=60,  # Default estimate
            )
            daily_goals.append(goal)
        return daily_goals

    def _extract_blocked_goals(self, session_goals: list) -> list[str]:
        """Extract blocked goal IDs from session goals.

        Args:
            session_goals: List of goal dictionaries from session.

        Returns:
            List of goal IDs that are blocked.
        """
        blocked = []
        for goal in session_goals:
            if isinstance(goal, dict):
                status = goal.get("status", "")
                if status == "blocked":
                    blocked.append(goal.get("goal_id", "unknown"))
            elif hasattr(goal, "status"):
                if goal.status == GoalStatus.BLOCKED or goal.status == "blocked":
                    blocked.append(getattr(goal, "goal_id", "unknown"))
        return blocked
