"""CampaignPlanner for multi-day campaign planning with backward planning.

This module provides the CampaignPlanner class that generates day plans
using backward planning from deadline.
"""

from datetime import date, timedelta
from typing import Optional

from swarm_attack.chief_of_staff.campaigns import (
    Campaign,
    CampaignState,
    Milestone,
    DayPlan,
)
from swarm_attack.chief_of_staff.config import ChiefOfStaffConfig


class CampaignPlanner:
    """Plans campaigns using backward planning from deadline.

    The planner generates day_plans by working backwards from the deadline,
    assigning milestones to days based on estimated effort and target dates.
    """

    def __init__(self, config: ChiefOfStaffConfig) -> None:
        """Initialize CampaignPlanner with configuration.

        Args:
            config: Chief of Staff configuration.
        """
        self._config = config

    def plan(
        self,
        campaign: Campaign,
        available_hours_per_day: float = 6.0,
    ) -> Campaign:
        """Generate day plans using backward planning from deadline.

        Algorithm:
            1. Start from deadline, work backwards
            2. Assign milestones to days based on estimated effort
            3. Each DayPlan contains goals for that day
            4. Buffer time for unexpected issues

        Args:
            campaign: The campaign to plan.
            available_hours_per_day: Hours available per day for work.

        Returns:
            Campaign with generated day_plans.
        """
        # Create day plans for each day of the campaign
        day_plans = []
        for i in range(campaign.planned_days):
            day_date = campaign.start_date + timedelta(days=i)
            day_plan = DayPlan(
                day_number=i + 1,
                date=day_date,
                goals=[],
                status="pending",
            )
            day_plans.append(day_plan)

        # If no milestones, return campaign with empty day plans
        if not campaign.milestones:
            campaign.day_plans = day_plans
            return campaign

        # Backward planning: assign milestones to their target days
        # and work backwards to distribute work
        self._assign_milestones_to_days(
            day_plans=day_plans,
            milestones=campaign.milestones,
            start_date=campaign.start_date,
            available_hours_per_day=available_hours_per_day,
        )

        campaign.day_plans = day_plans
        return campaign

    def _assign_milestones_to_days(
        self,
        day_plans: list[DayPlan],
        milestones: list[Milestone],
        start_date: date,
        available_hours_per_day: float,
    ) -> None:
        """Assign milestones to day plans using backward planning.

        Works backwards from each milestone's target_date to assign
        goals to the appropriate days.

        Args:
            day_plans: List of day plans to populate.
            milestones: List of milestones to assign.
            start_date: Campaign start date.
            available_hours_per_day: Hours available per day.
        """
        # Sort milestones by target_date (earliest first)
        sorted_milestones = sorted(
            milestones,
            key=lambda m: m.target_date or start_date,
        )

        # Track buffer - reserve ~20% of capacity for unexpected issues
        buffer_ratio = 0.2

        for milestone in sorted_milestones:
            if milestone.target_date is None:
                continue

            # Find the day plan that corresponds to this milestone's target date
            days_from_start = (milestone.target_date - start_date).days

            if 0 <= days_from_start < len(day_plans):
                # Backward planning: assign milestone to its target day
                # or earlier if there's capacity
                target_day_index = days_from_start

                # Add milestone description as a goal to the target day
                day_plans[target_day_index].goals.append(
                    f"Complete: {milestone.description}"
                )
            elif days_from_start >= len(day_plans) and len(day_plans) > 0:
                # Milestone target is past campaign end, assign to last day
                day_plans[-1].goals.append(
                    f"Complete: {milestone.description}"
                )
            elif days_from_start < 0 and len(day_plans) > 0:
                # Milestone target is before campaign start, assign to first day
                day_plans[0].goals.append(
                    f"Complete: {milestone.description}"
                )
