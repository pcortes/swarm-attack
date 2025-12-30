"""Tests for Issue #7: CampaignPlanner.plan() with backward planning.

This module tests the CampaignPlanner class's plan() method that generates
day_plans using backward planning from deadline.
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


class TestCampaignPlannerInit:
    """Tests for CampaignPlanner initialization."""

    def test_init_with_config(self):
        """CampaignPlanner should initialize with ChiefOfStaffConfig."""
        config = ChiefOfStaffConfig()
        planner = CampaignPlanner(config)
        assert planner is not None
        assert planner._config == config


class TestCampaignPlannerPlan:
    """Tests for CampaignPlanner.plan() method."""

    def test_plan_returns_campaign_with_day_plans(self):
        """plan() should return a Campaign with generated day_plans."""
        config = ChiefOfStaffConfig()
        planner = CampaignPlanner(config)

        # Create a campaign with milestones but no day_plans
        today = date.today()
        deadline = today + timedelta(days=5)

        campaign = Campaign(
            id="test-campaign",
            name="Test Campaign",
            state=CampaignState.PLANNING,
            start_date=today,
            planned_days=5,
            milestones=[
                Milestone(
                    id="m1",
                    description="Setup infrastructure",
                    target_date=today + timedelta(days=2),
                    completed=False,
                ),
                Milestone(
                    id="m2",
                    description="Implement core feature",
                    target_date=today + timedelta(days=4),
                    completed=False,
                ),
                Milestone(
                    id="m3",
                    description="Final testing and polish",
                    target_date=deadline,
                    completed=False,
                ),
            ],
        )

        result = planner.plan(campaign)

        assert result is not None
        assert len(result.day_plans) > 0
        assert isinstance(result, Campaign)

    def test_plan_generates_day_plans_for_each_day(self):
        """plan() should generate a DayPlan for each day of the campaign."""
        config = ChiefOfStaffConfig()
        planner = CampaignPlanner(config)

        today = date.today()
        planned_days = 5

        campaign = Campaign(
            id="test-campaign",
            name="Test Campaign",
            state=CampaignState.PLANNING,
            start_date=today,
            planned_days=planned_days,
            milestones=[
                Milestone(
                    id="m1",
                    description="Complete feature",
                    target_date=today + timedelta(days=planned_days),
                    completed=False,
                ),
            ],
        )

        result = planner.plan(campaign)

        # Should have exactly planned_days day plans
        assert len(result.day_plans) == planned_days

    def test_plan_assigns_goals_based_on_milestones(self):
        """plan() should assign goals to day_plans based on milestone assignments."""
        config = ChiefOfStaffConfig()
        planner = CampaignPlanner(config)

        today = date.today()

        campaign = Campaign(
            id="test-campaign",
            name="Test Campaign",
            state=CampaignState.PLANNING,
            start_date=today,
            planned_days=3,
            milestones=[
                Milestone(
                    id="m1",
                    description="First milestone",
                    target_date=today + timedelta(days=1),
                    completed=False,
                ),
                Milestone(
                    id="m2",
                    description="Second milestone",
                    target_date=today + timedelta(days=3),
                    completed=False,
                ),
            ],
        )

        result = planner.plan(campaign)

        # Day plans should have goals assigned
        total_goals = sum(len(dp.goals) for dp in result.day_plans)
        assert total_goals >= len(campaign.milestones)

    def test_plan_backward_planning_from_deadline(self):
        """plan() should work backwards from deadline to assign milestones."""
        config = ChiefOfStaffConfig()
        planner = CampaignPlanner(config)

        today = date.today()
        # With planned_days=5, days are: day0=today, day1=today+1, ..., day4=today+4
        # So the last day is today+4
        last_day = today + timedelta(days=4)

        campaign = Campaign(
            id="test-campaign",
            name="Test Campaign",
            state=CampaignState.PLANNING,
            start_date=today,
            planned_days=5,
            milestones=[
                Milestone(
                    id="m1",
                    description="Final milestone",
                    target_date=last_day,
                    completed=False,
                ),
            ],
        )

        result = planner.plan(campaign)

        # The last day_plan should include the final milestone's goal
        last_day_plan = result.day_plans[-1]
        assert last_day_plan.date == last_day
        assert len(last_day_plan.goals) > 0

    def test_plan_respects_available_hours_per_day(self):
        """plan() should distribute work based on available_hours_per_day."""
        config = ChiefOfStaffConfig()
        planner = CampaignPlanner(config)

        today = date.today()

        campaign = Campaign(
            id="test-campaign",
            name="Test Campaign",
            state=CampaignState.PLANNING,
            start_date=today,
            planned_days=3,
            milestones=[
                Milestone(
                    id="m1",
                    description="Task 1",
                    target_date=today + timedelta(days=1),
                    completed=False,
                ),
                Milestone(
                    id="m2",
                    description="Task 2",
                    target_date=today + timedelta(days=2),
                    completed=False,
                ),
                Milestone(
                    id="m3",
                    description="Task 3",
                    target_date=today + timedelta(days=3),
                    completed=False,
                ),
            ],
        )

        # With fewer hours, might need to spread work differently
        result = planner.plan(campaign, available_hours_per_day=4.0)

        assert len(result.day_plans) == 3
        assert all(isinstance(dp, DayPlan) for dp in result.day_plans)

    def test_plan_includes_buffer_time(self):
        """plan() should include buffer time for unexpected issues."""
        config = ChiefOfStaffConfig()
        planner = CampaignPlanner(config)

        today = date.today()

        # Create a campaign with milestones that fit in 4 days
        campaign = Campaign(
            id="test-campaign",
            name="Test Campaign",
            state=CampaignState.PLANNING,
            start_date=today,
            planned_days=5,  # 5 days total
            milestones=[
                Milestone(
                    id="m1",
                    description="Core work",
                    target_date=today + timedelta(days=3),
                    completed=False,
                ),
            ],
        )

        result = planner.plan(campaign)

        # With buffer, not all capacity should be used on early days
        # Last day(s) should have lighter load or no goals (buffer)
        assert len(result.day_plans) == 5

    def test_plan_sets_day_numbers_correctly(self):
        """plan() should set day_number on each DayPlan."""
        config = ChiefOfStaffConfig()
        planner = CampaignPlanner(config)

        today = date.today()

        campaign = Campaign(
            id="test-campaign",
            name="Test Campaign",
            state=CampaignState.PLANNING,
            start_date=today,
            planned_days=3,
            milestones=[
                Milestone(
                    id="m1",
                    description="Task",
                    target_date=today + timedelta(days=3),
                    completed=False,
                ),
            ],
        )

        result = planner.plan(campaign)

        # Day numbers should be sequential starting from 1
        for i, day_plan in enumerate(result.day_plans, start=1):
            assert day_plan.day_number == i

    def test_plan_sets_dates_correctly(self):
        """plan() should set correct dates on each DayPlan."""
        config = ChiefOfStaffConfig()
        planner = CampaignPlanner(config)

        today = date.today()

        campaign = Campaign(
            id="test-campaign",
            name="Test Campaign",
            state=CampaignState.PLANNING,
            start_date=today,
            planned_days=3,
            milestones=[
                Milestone(
                    id="m1",
                    description="Task",
                    target_date=today + timedelta(days=3),
                    completed=False,
                ),
            ],
        )

        result = planner.plan(campaign)

        # Dates should match the campaign days
        for i, day_plan in enumerate(result.day_plans):
            expected_date = today + timedelta(days=i)
            assert day_plan.date == expected_date

    def test_plan_empty_milestones(self):
        """plan() should handle campaigns with no milestones."""
        config = ChiefOfStaffConfig()
        planner = CampaignPlanner(config)

        today = date.today()

        campaign = Campaign(
            id="test-campaign",
            name="Test Campaign",
            state=CampaignState.PLANNING,
            start_date=today,
            planned_days=3,
            milestones=[],
        )

        result = planner.plan(campaign)

        # Should still create day_plans (empty goals)
        assert len(result.day_plans) == 3
        for day_plan in result.day_plans:
            assert day_plan.goals == []

    def test_plan_preserves_campaign_metadata(self):
        """plan() should preserve campaign metadata (id, name, state, etc.)."""
        config = ChiefOfStaffConfig()
        planner = CampaignPlanner(config)

        today = date.today()

        campaign = Campaign(
            id="my-campaign",
            name="My Important Campaign",
            state=CampaignState.PLANNING,
            description="A very important campaign",
            start_date=today,
            planned_days=3,
            milestones=[
                Milestone(
                    id="m1",
                    description="Task",
                    target_date=today + timedelta(days=3),
                    completed=False,
                ),
            ],
        )

        result = planner.plan(campaign)

        assert result.id == "my-campaign"
        assert result.name == "My Important Campaign"
        assert result.description == "A very important campaign"
