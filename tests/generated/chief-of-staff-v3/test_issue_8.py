"""Tests for Issue #8: CampaignPlanner.replan() method.

This module tests the CampaignPlanner.replan() method that adjusts
campaign plans based on actual progress.
"""

import pytest
from datetime import date, timedelta
from unittest.mock import MagicMock

from swarm_attack.chief_of_staff.campaigns import (
    Campaign,
    CampaignState,
    Milestone,
    DayPlan,
)
from swarm_attack.chief_of_staff.config import ChiefOfStaffConfig
from swarm_attack.chief_of_staff.campaign_planner import CampaignPlanner


class TestCampaignPlannerReplan:
    """Tests for CampaignPlanner.replan() method."""

    def test_replan_returns_campaign(self):
        """replan() should return a Campaign object."""
        config = ChiefOfStaffConfig()
        planner = CampaignPlanner(config)

        today = date.today()
        campaign = Campaign(
            id="test-campaign",
            name="Test Campaign",
            state=CampaignState.ACTIVE,
            start_date=today - timedelta(days=2),
            planned_days=5,
            milestones=[
                Milestone(
                    id="m1",
                    description="First milestone",
                    target_date=today - timedelta(days=1),
                    completed=True,
                ),
                Milestone(
                    id="m2",
                    description="Second milestone",
                    target_date=today + timedelta(days=2),
                    completed=False,
                ),
            ],
            day_plans=[
                DayPlan(day_number=1, date=today - timedelta(days=2), goals=["Task 1"]),
                DayPlan(day_number=2, date=today - timedelta(days=1), goals=["Task 2"]),
                DayPlan(day_number=3, date=today, goals=["Task 3"]),
                DayPlan(day_number=4, date=today + timedelta(days=1), goals=["Task 4"]),
                DayPlan(day_number=5, date=today + timedelta(days=2), goals=["Task 5"]),
            ],
        )

        result = planner.replan(
            campaign=campaign,
            completed_milestones=["m1"],
            days_elapsed=2,
        )

        assert isinstance(result, Campaign)

    def test_replan_marks_completed_milestones(self):
        """replan() should mark specified milestones as completed."""
        config = ChiefOfStaffConfig()
        planner = CampaignPlanner(config)

        today = date.today()
        campaign = Campaign(
            id="test-campaign",
            name="Test Campaign",
            state=CampaignState.ACTIVE,
            start_date=today - timedelta(days=2),
            planned_days=5,
            milestones=[
                Milestone(
                    id="m1",
                    description="First milestone",
                    target_date=today - timedelta(days=1),
                    completed=False,  # Not yet marked completed
                ),
                Milestone(
                    id="m2",
                    description="Second milestone",
                    target_date=today + timedelta(days=2),
                    completed=False,
                ),
            ],
            day_plans=[
                DayPlan(day_number=1, date=today - timedelta(days=2), goals=["Task 1"]),
                DayPlan(day_number=2, date=today - timedelta(days=1), goals=["Task 2"]),
                DayPlan(day_number=3, date=today, goals=["Task 3"]),
                DayPlan(day_number=4, date=today + timedelta(days=1), goals=["Task 4"]),
                DayPlan(day_number=5, date=today + timedelta(days=2), goals=["Task 5"]),
            ],
        )

        result = planner.replan(
            campaign=campaign,
            completed_milestones=["m1"],
            days_elapsed=2,
        )

        # Find m1 in result milestones and verify it's marked completed
        m1 = next((m for m in result.milestones if m.id == "m1"), None)
        assert m1 is not None
        assert m1.completed is True

    def test_replan_redistributes_remaining_work(self):
        """replan() should redistribute remaining work across remaining days."""
        config = ChiefOfStaffConfig()
        planner = CampaignPlanner(config)

        today = date.today()
        campaign = Campaign(
            id="test-campaign",
            name="Test Campaign",
            state=CampaignState.ACTIVE,
            start_date=today - timedelta(days=2),
            planned_days=5,
            milestones=[
                Milestone(
                    id="m1",
                    description="First milestone",
                    target_date=today - timedelta(days=1),
                    completed=True,
                ),
                Milestone(
                    id="m2",
                    description="Second milestone",
                    target_date=today + timedelta(days=1),
                    completed=False,
                ),
                Milestone(
                    id="m3",
                    description="Third milestone",
                    target_date=today + timedelta(days=2),
                    completed=False,
                ),
            ],
            day_plans=[
                DayPlan(day_number=1, date=today - timedelta(days=2), goals=["Setup"]),
                DayPlan(day_number=2, date=today - timedelta(days=1), goals=["M1 work"]),
                DayPlan(day_number=3, date=today, goals=["M2 work"]),
                DayPlan(day_number=4, date=today + timedelta(days=1), goals=["M2 completion"]),
                DayPlan(day_number=5, date=today + timedelta(days=2), goals=["M3 work"]),
            ],
        )

        result = planner.replan(
            campaign=campaign,
            completed_milestones=["m1"],
            days_elapsed=2,
        )

        # Remaining days should have goals redistributed for uncompleted milestones
        remaining_day_plans = [dp for dp in result.day_plans if dp.date >= today]
        assert len(remaining_day_plans) > 0

    def test_replan_handles_overdue_milestones(self):
        """replan() should redistribute overdue milestones to remaining days."""
        config = ChiefOfStaffConfig()
        planner = CampaignPlanner(config)

        today = date.today()
        # Campaign started 3 days ago, only milestone 1 completed (should have had 2)
        campaign = Campaign(
            id="test-campaign",
            name="Test Campaign",
            state=CampaignState.ACTIVE,
            start_date=today - timedelta(days=3),
            planned_days=5,
            current_day=1,  # Only on day 1, should be on day 3
            milestones=[
                Milestone(
                    id="m1",
                    description="First milestone",
                    target_date=today - timedelta(days=2),
                    completed=True,
                ),
                Milestone(
                    id="m2",
                    description="Second milestone",
                    target_date=today - timedelta(days=1),
                    completed=False,  # Overdue - should have been done yesterday
                ),
                Milestone(
                    id="m3",
                    description="Third milestone",
                    target_date=today + timedelta(days=1),
                    completed=False,
                ),
            ],
            day_plans=[
                DayPlan(day_number=1, date=today - timedelta(days=3), goals=["Task 1"]),
                DayPlan(day_number=2, date=today - timedelta(days=2), goals=["M1"]),
                DayPlan(day_number=3, date=today - timedelta(days=1), goals=["M2"]),
                DayPlan(day_number=4, date=today, goals=["Task 4"]),
                DayPlan(day_number=5, date=today + timedelta(days=1), goals=["M3"]),
            ],
        )

        result = planner.replan(
            campaign=campaign,
            completed_milestones=["m1"],
            days_elapsed=3,
        )

        # Overdue milestone m2 should be redistributed to today (day 4)
        today_plan = next((dp for dp in result.day_plans if dp.date == today), None)
        assert today_plan is not None
        # Should have the overdue milestone added
        assert any("Second milestone" in goal for goal in today_plan.goals)

    def test_replan_updates_current_day(self):
        """replan() should update current_day based on days_elapsed."""
        config = ChiefOfStaffConfig()
        planner = CampaignPlanner(config)

        today = date.today()
        campaign = Campaign(
            id="test-campaign",
            name="Test Campaign",
            state=CampaignState.ACTIVE,
            start_date=today - timedelta(days=2),
            planned_days=5,
            current_day=1,  # Was on day 1
            milestones=[
                Milestone(
                    id="m1",
                    description="First milestone",
                    target_date=today + timedelta(days=2),
                    completed=False,
                ),
            ],
            day_plans=[
                DayPlan(day_number=1, date=today - timedelta(days=2), goals=["Task 1"]),
                DayPlan(day_number=2, date=today - timedelta(days=1), goals=["Task 2"]),
                DayPlan(day_number=3, date=today, goals=["Task 3"]),
                DayPlan(day_number=4, date=today + timedelta(days=1), goals=["Task 4"]),
                DayPlan(day_number=5, date=today + timedelta(days=2), goals=["Task 5"]),
            ],
        )

        result = planner.replan(
            campaign=campaign,
            completed_milestones=[],
            days_elapsed=3,
        )

        # current_day should be updated to reflect days elapsed
        assert result.current_day == 3

    def test_replan_preserves_completed_day_plans(self):
        """replan() should preserve day plans for completed days."""
        config = ChiefOfStaffConfig()
        planner = CampaignPlanner(config)

        today = date.today()
        campaign = Campaign(
            id="test-campaign",
            name="Test Campaign",
            state=CampaignState.ACTIVE,
            start_date=today - timedelta(days=2),
            planned_days=5,
            milestones=[
                Milestone(
                    id="m1",
                    description="First milestone",
                    target_date=today + timedelta(days=2),
                    completed=False,
                ),
            ],
            day_plans=[
                DayPlan(day_number=1, date=today - timedelta(days=2), goals=["Completed Task 1"], status="completed"),
                DayPlan(day_number=2, date=today - timedelta(days=1), goals=["Completed Task 2"], status="completed"),
                DayPlan(day_number=3, date=today, goals=["Task 3"], status="pending"),
                DayPlan(day_number=4, date=today + timedelta(days=1), goals=["Task 4"], status="pending"),
                DayPlan(day_number=5, date=today + timedelta(days=2), goals=["Task 5"], status="pending"),
            ],
        )

        result = planner.replan(
            campaign=campaign,
            completed_milestones=[],
            days_elapsed=2,
        )

        # First two day plans should be preserved
        assert result.day_plans[0].goals == ["Completed Task 1"]
        assert result.day_plans[1].goals == ["Completed Task 2"]

    def test_replan_with_no_milestones_completed(self):
        """replan() should handle case where no milestones have been completed."""
        config = ChiefOfStaffConfig()
        planner = CampaignPlanner(config)

        today = date.today()
        campaign = Campaign(
            id="test-campaign",
            name="Test Campaign",
            state=CampaignState.ACTIVE,
            start_date=today - timedelta(days=1),
            planned_days=5,
            milestones=[
                Milestone(
                    id="m1",
                    description="First milestone",
                    target_date=today,
                    completed=False,
                ),
                Milestone(
                    id="m2",
                    description="Second milestone",
                    target_date=today + timedelta(days=3),
                    completed=False,
                ),
            ],
            day_plans=[
                DayPlan(day_number=1, date=today - timedelta(days=1), goals=["Task 1"]),
                DayPlan(day_number=2, date=today, goals=["Task 2"]),
                DayPlan(day_number=3, date=today + timedelta(days=1), goals=["Task 3"]),
                DayPlan(day_number=4, date=today + timedelta(days=2), goals=["Task 4"]),
                DayPlan(day_number=5, date=today + timedelta(days=3), goals=["Task 5"]),
            ],
        )

        result = planner.replan(
            campaign=campaign,
            completed_milestones=[],
            days_elapsed=1,
        )

        # All milestones should still be incomplete
        for milestone in result.milestones:
            assert milestone.completed is False

    def test_replan_with_all_milestones_completed(self):
        """replan() should handle case where all milestones are completed."""
        config = ChiefOfStaffConfig()
        planner = CampaignPlanner(config)

        today = date.today()
        campaign = Campaign(
            id="test-campaign",
            name="Test Campaign",
            state=CampaignState.ACTIVE,
            start_date=today - timedelta(days=3),
            planned_days=5,
            milestones=[
                Milestone(
                    id="m1",
                    description="First milestone",
                    target_date=today - timedelta(days=2),
                    completed=False,
                ),
                Milestone(
                    id="m2",
                    description="Second milestone",
                    target_date=today - timedelta(days=1),
                    completed=False,
                ),
            ],
            day_plans=[
                DayPlan(day_number=1, date=today - timedelta(days=3), goals=["Task 1"]),
                DayPlan(day_number=2, date=today - timedelta(days=2), goals=["M1"]),
                DayPlan(day_number=3, date=today - timedelta(days=1), goals=["M2"]),
                DayPlan(day_number=4, date=today, goals=["Buffer"]),
                DayPlan(day_number=5, date=today + timedelta(days=1), goals=["Buffer"]),
            ],
        )

        result = planner.replan(
            campaign=campaign,
            completed_milestones=["m1", "m2"],
            days_elapsed=3,
        )

        # All milestones should be marked completed
        for milestone in result.milestones:
            assert milestone.completed is True

    def test_replan_preserves_campaign_metadata(self):
        """replan() should preserve campaign metadata (id, name, etc.)."""
        config = ChiefOfStaffConfig()
        planner = CampaignPlanner(config)

        today = date.today()
        campaign = Campaign(
            id="my-campaign",
            name="My Important Campaign",
            state=CampaignState.ACTIVE,
            description="A very important campaign",
            start_date=today - timedelta(days=1),
            planned_days=5,
            milestones=[
                Milestone(
                    id="m1",
                    description="First milestone",
                    target_date=today + timedelta(days=3),
                    completed=False,
                ),
            ],
            day_plans=[
                DayPlan(day_number=1, date=today - timedelta(days=1), goals=["Task 1"]),
                DayPlan(day_number=2, date=today, goals=["Task 2"]),
                DayPlan(day_number=3, date=today + timedelta(days=1), goals=["Task 3"]),
                DayPlan(day_number=4, date=today + timedelta(days=2), goals=["Task 4"]),
                DayPlan(day_number=5, date=today + timedelta(days=3), goals=["Task 5"]),
            ],
        )

        result = planner.replan(
            campaign=campaign,
            completed_milestones=[],
            days_elapsed=1,
        )

        assert result.id == "my-campaign"
        assert result.name == "My Important Campaign"
        assert result.description == "A very important campaign"
