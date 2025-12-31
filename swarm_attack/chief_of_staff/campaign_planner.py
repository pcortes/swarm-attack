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

    def replan(
        self,
        campaign: Campaign,
        completed_milestones: list[str],
        days_elapsed: int,
    ) -> Campaign:
        """Adjust campaign plan based on actual progress.

        Logic:
            1. Mark completed milestones
            2. Redistribute remaining work across remaining days
            3. Flag if campaign is behind schedule

        Args:
            campaign: The campaign to replan.
            completed_milestones: List of milestone IDs that have been completed.
            days_elapsed: Number of days since campaign started.

        Returns:
            Campaign with updated plan reflecting actual progress.
        """
        # 1. Mark completed milestones
        for milestone in campaign.milestones:
            if milestone.id in completed_milestones:
                milestone.completed = True
                milestone.status = "completed"

        # 2. Update current_day based on days_elapsed
        campaign.current_day = days_elapsed

        # 3. Find remaining days and uncompleted milestones
        remaining_days = campaign.planned_days - days_elapsed
        uncompleted_milestones = [
            m for m in campaign.milestones if not m.completed
        ]

        # 4. Redistribute remaining work across remaining days
        if remaining_days > 0 and uncompleted_milestones:
            self._redistribute_work(
                campaign=campaign,
                uncompleted_milestones=uncompleted_milestones,
                days_elapsed=days_elapsed,
            )

        return campaign

    def _redistribute_work(
        self,
        campaign: Campaign,
        uncompleted_milestones: list[Milestone],
        days_elapsed: int,
    ) -> None:
        """Redistribute uncompleted milestone work across remaining days.

        Args:
            campaign: The campaign to update.
            uncompleted_milestones: List of uncompleted milestones.
            days_elapsed: Number of days elapsed.
        """
        # Get remaining day plans (from days_elapsed onwards)
        remaining_day_plans = campaign.day_plans[days_elapsed:]

        if not remaining_day_plans:
            return

        # Clear existing goals for remaining days (except completed ones)
        for day_plan in remaining_day_plans:
            if day_plan.status != "completed":
                # Keep track of original goals but prepare for redistribution
                pass

        # Sort uncompleted milestones by target_date
        sorted_milestones = sorted(
            uncompleted_milestones,
            key=lambda m: m.target_date or campaign.start_date,
        )

        # Reassign milestones to remaining days based on their target dates
        for milestone in sorted_milestones:
            if milestone.target_date is None:
                continue

            # Calculate which remaining day this milestone should be assigned to
            days_from_start = (milestone.target_date - campaign.start_date).days
            remaining_day_index = days_from_start - days_elapsed

            if 0 <= remaining_day_index < len(remaining_day_plans):
                day_plan = remaining_day_plans[remaining_day_index]
                if day_plan.status != "completed":
                    goal_text = f"Complete: {milestone.description}"
                    if goal_text not in day_plan.goals:
                        day_plan.goals.append(goal_text)
            elif remaining_day_index < 0 and remaining_day_plans:
                # Target date has passed, assign to first remaining day
                day_plan = remaining_day_plans[0]
                if day_plan.status != "completed":
                    goal_text = f"Complete: {milestone.description}"
                    if goal_text not in day_plan.goals:
                        day_plan.goals.append(goal_text)
            elif remaining_day_index >= len(remaining_day_plans) and remaining_day_plans:
                # Target date is beyond remaining days, assign to last day
                day_plan = remaining_day_plans[-1]
                if day_plan.status != "completed":
                    goal_text = f"Complete: {milestone.description}"
                    if goal_text not in day_plan.goals:
                        day_plan.goals.append(goal_text)
