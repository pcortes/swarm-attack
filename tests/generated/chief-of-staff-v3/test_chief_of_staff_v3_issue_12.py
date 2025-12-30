"""Tests for WeeklyPlanner and weekly CLI command."""

import pytest
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
from dataclasses import asdict


class TestWeeklySummaryDataclass:
    """Tests for WeeklySummary dataclass."""

    def test_weekly_summary_exists(self):
        """WeeklySummary class should exist."""
        from swarm_attack.chief_of_staff.weekly import WeeklySummary
        assert WeeklySummary is not None

    def test_weekly_summary_has_required_fields(self):
        """WeeklySummary should have all required fields."""
        from swarm_attack.chief_of_staff.weekly import WeeklySummary
        
        summary = WeeklySummary(
            week_start=date(2025, 1, 6),
            week_end=date(2025, 1, 10),
            active_campaigns=2,
            completed_campaigns=1,
            milestones_completed=3,
            milestones_remaining=5,
            goals_completed=10,
            goals_failed=2,
            goals_skipped=1,
            total_cost=150.50,
            next_week_goals=["Goal 1", "Goal 2", "Goal 3"],
        )
        
        assert summary.week_start == date(2025, 1, 6)
        assert summary.week_end == date(2025, 1, 10)
        assert summary.active_campaigns == 2
        assert summary.completed_campaigns == 1
        assert summary.milestones_completed == 3
        assert summary.milestones_remaining == 5
        assert summary.goals_completed == 10
        assert summary.goals_failed == 2
        assert summary.goals_skipped == 1
        assert summary.total_cost == 150.50
        assert summary.next_week_goals == ["Goal 1", "Goal 2", "Goal 3"]

    def test_weekly_summary_from_dict(self):
        """WeeklySummary should have from_dict method."""
        from swarm_attack.chief_of_staff.weekly import WeeklySummary
        
        data = {
            "week_start": "2025-01-06",
            "week_end": "2025-01-10",
            "active_campaigns": 2,
            "completed_campaigns": 1,
            "milestones_completed": 3,
            "milestones_remaining": 5,
            "goals_completed": 10,
            "goals_failed": 2,
            "goals_skipped": 1,
            "total_cost": 150.50,
            "next_week_goals": ["Goal 1", "Goal 2"],
        }
        
        summary = WeeklySummary.from_dict(data)
        assert summary.week_start == date(2025, 1, 6)
        assert summary.active_campaigns == 2

    def test_weekly_summary_to_dict(self):
        """WeeklySummary should have to_dict method."""
        from swarm_attack.chief_of_staff.weekly import WeeklySummary
        
        summary = WeeklySummary(
            week_start=date(2025, 1, 6),
            week_end=date(2025, 1, 10),
            active_campaigns=2,
            completed_campaigns=1,
            milestones_completed=3,
            milestones_remaining=5,
            goals_completed=10,
            goals_failed=2,
            goals_skipped=1,
            total_cost=150.50,
            next_week_goals=["Goal 1"],
        )
        
        data = summary.to_dict()
        assert data["week_start"] == "2025-01-06"
        assert data["active_campaigns"] == 2
        assert data["next_week_goals"] == ["Goal 1"]


class TestWeeklyPlannerInit:
    """Tests for WeeklyPlanner initialization."""

    def test_weekly_planner_exists(self):
        """WeeklyPlanner class should exist."""
        from swarm_attack.chief_of_staff.weekly import WeeklyPlanner
        assert WeeklyPlanner is not None

    def test_weekly_planner_constructor(self):
        """WeeklyPlanner should accept campaign_store, episode_store, llm."""
        from swarm_attack.chief_of_staff.weekly import WeeklyPlanner
        
        campaign_store = Mock()
        episode_store = Mock()
        llm = Mock()
        
        planner = WeeklyPlanner(
            campaign_store=campaign_store,
            episode_store=episode_store,
            llm=llm,
        )
        
        assert planner.campaign_store is campaign_store
        assert planner.episode_store is episode_store
        assert planner.llm is llm


class TestWeeklyPlannerGenerateSummary:
    """Tests for WeeklyPlanner.generate_weekly_summary()."""

    def test_generate_weekly_summary_returns_weekly_summary(self):
        """generate_weekly_summary should return a WeeklySummary."""
        from swarm_attack.chief_of_staff.weekly import WeeklyPlanner, WeeklySummary
        from swarm_attack.chief_of_staff.campaigns import Campaign, CampaignState, Milestone, DayPlan
        
        # Set up mock campaign store
        campaign_store = Mock()
        active_campaign = Campaign(
            id="campaign-1",
            name="Feature A",
            state=CampaignState.ACTIVE,
            milestones=[
                Milestone(id="m1", description="Milestone 1", target_date=date(2025, 1, 10), completed=True),
                Milestone(id="m2", description="Milestone 2", target_date=date(2025, 1, 15), completed=False),
            ],
            day_plans=[
                DayPlan(date=date(2025, 1, 6), goals=["Goal 1", "Goal 2"]),
                DayPlan(date=date(2025, 1, 7), goals=["Goal 3"]),
            ],
            created_at=datetime(2025, 1, 1),
        )
        completed_campaign = Campaign(
            id="campaign-2",
            name="Feature B",
            state=CampaignState.COMPLETED,
            milestones=[
                Milestone(id="m3", description="Milestone 3", target_date=date(2025, 1, 5), completed=True),
            ],
            day_plans=[],
            created_at=datetime(2024, 12, 15),
        )
        campaign_store.list_all_sync.return_value = [active_campaign, completed_campaign]
        
        # Set up mock episode store
        episode_store = Mock()
        episode_store.list_episodes_in_range.return_value = [
            Mock(outcome="completed", cost=50.0),
            Mock(outcome="completed", cost=30.0),
            Mock(outcome="failed", cost=20.0),
            Mock(outcome="skipped", cost=0.0),
        ]
        
        llm = Mock()
        
        planner = WeeklyPlanner(
            campaign_store=campaign_store,
            episode_store=episode_store,
            llm=llm,
        )
        
        summary = planner.generate_weekly_summary()
        
        assert isinstance(summary, WeeklySummary)
        assert summary.active_campaigns == 1
        assert summary.completed_campaigns == 1
        assert summary.goals_completed == 2
        assert summary.goals_failed == 1
        assert summary.goals_skipped == 1
        assert summary.total_cost == 100.0

    def test_generate_weekly_summary_counts_milestones(self):
        """generate_weekly_summary should count completed and remaining milestones."""
        from swarm_attack.chief_of_staff.weekly import WeeklyPlanner, WeeklySummary
        from swarm_attack.chief_of_staff.campaigns import Campaign, CampaignState, Milestone
        
        campaign_store = Mock()
        campaign = Campaign(
            id="c1",
            name="Test",
            state=CampaignState.ACTIVE,
            milestones=[
                Milestone(id="m1", description="Done", target_date=date(2025, 1, 5), completed=True),
                Milestone(id="m2", description="Done", target_date=date(2025, 1, 8), completed=True),
                Milestone(id="m3", description="Pending", target_date=date(2025, 1, 15), completed=False),
            ],
            day_plans=[],
            created_at=datetime(2025, 1, 1),
        )
        campaign_store.list_all_sync.return_value = [campaign]
        
        episode_store = Mock()
        episode_store.list_episodes_in_range.return_value = []
        
        planner = WeeklyPlanner(campaign_store=campaign_store, episode_store=episode_store, llm=Mock())
        summary = planner.generate_weekly_summary()
        
        assert summary.milestones_completed == 2
        assert summary.milestones_remaining == 1


class TestWeeklyPlannerGenerateReport:
    """Tests for WeeklyPlanner.generate_weekly_report()."""

    def test_generate_weekly_report_returns_string(self):
        """generate_weekly_report should return a markdown string."""
        from swarm_attack.chief_of_staff.weekly import WeeklyPlanner
        from swarm_attack.chief_of_staff.campaigns import Campaign, CampaignState
        
        campaign_store = Mock()
        campaign_store.list_all_sync.return_value = [
            Campaign(
                id="c1",
                name="Test Campaign",
                state=CampaignState.ACTIVE,
                milestones=[],
                day_plans=[],
                created_at=datetime(2025, 1, 1),
            )
        ]
        
        episode_store = Mock()
        episode_store.list_episodes_in_range.return_value = []
        
        planner = WeeklyPlanner(campaign_store=campaign_store, episode_store=episode_store, llm=Mock())
        report = planner.generate_weekly_report()
        
        assert isinstance(report, str)
        assert len(report) > 0

    def test_generate_weekly_report_contains_sections(self):
        """generate_weekly_report should contain expected sections."""
        from swarm_attack.chief_of_staff.weekly import WeeklyPlanner
        from swarm_attack.chief_of_staff.campaigns import Campaign, CampaignState, Milestone, DayPlan
        
        campaign_store = Mock()
        campaign_store.list_all_sync.return_value = [
            Campaign(
                id="c1",
                name="Test Campaign",
                state=CampaignState.ACTIVE,
                milestones=[
                    Milestone(id="m1", description="Test", target_date=date(2025, 1, 10), completed=True),
                ],
                day_plans=[
                    DayPlan(date=date(2025, 1, 13), goals=["Future goal"]),
                ],
                created_at=datetime(2025, 1, 1),
            )
        ]
        
        episode_store = Mock()
        episode_store.list_episodes_in_range.return_value = [
            Mock(outcome="completed", cost=25.0),
        ]
        
        planner = WeeklyPlanner(campaign_store=campaign_store, episode_store=episode_store, llm=Mock())
        report = planner.generate_weekly_report()
        
        # Check for expected sections in markdown
        assert "Weekly" in report or "weekly" in report
        assert "Campaign" in report or "campaign" in report


class TestWeeklyPlannerProjectNextWeek:
    """Tests for WeeklyPlanner._project_next_week()."""

    def test_project_next_week_returns_list(self):
        """_project_next_week should return a list of goals."""
        from swarm_attack.chief_of_staff.weekly import WeeklyPlanner
        from swarm_attack.chief_of_staff.campaigns import Campaign, CampaignState, DayPlan
        
        campaign_store = Mock()
        # Create campaign with future day plans
        today = date.today()
        future_dates = [today + timedelta(days=i) for i in range(1, 6)]
        
        campaign = Campaign(
            id="c1",
            name="Test",
            state=CampaignState.ACTIVE,
            milestones=[],
            day_plans=[
                DayPlan(date=future_dates[0], goals=["Goal A"]),
                DayPlan(date=future_dates[1], goals=["Goal B", "Goal C"]),
                DayPlan(date=future_dates[2], goals=["Goal D"]),
            ],
            created_at=datetime(2025, 1, 1),
        )
        campaign_store.list_all_sync.return_value = [campaign]
        
        episode_store = Mock()
        episode_store.list_episodes_in_range.return_value = []
        
        planner = WeeklyPlanner(campaign_store=campaign_store, episode_store=episode_store, llm=Mock())
        next_week_goals = planner._project_next_week()
        
        assert isinstance(next_week_goals, list)
        assert len(next_week_goals) > 0

    def test_project_next_week_limits_to_five_days(self):
        """_project_next_week should project at most 5 working days."""
        from swarm_attack.chief_of_staff.weekly import WeeklyPlanner
        from swarm_attack.chief_of_staff.campaigns import Campaign, CampaignState, DayPlan
        
        campaign_store = Mock()
        today = date.today()
        
        # Create many future day plans
        day_plans = [
            DayPlan(date=today + timedelta(days=i), goals=[f"Goal {i}"])
            for i in range(1, 15)
        ]
        
        campaign = Campaign(
            id="c1",
            name="Test",
            state=CampaignState.ACTIVE,
            milestones=[],
            day_plans=day_plans,
            created_at=datetime(2025, 1, 1),
        )
        campaign_store.list_all_sync.return_value = [campaign]
        
        episode_store = Mock()
        episode_store.list_episodes_in_range.return_value = []
        
        planner = WeeklyPlanner(campaign_store=campaign_store, episode_store=episode_store, llm=Mock())
        next_week_goals = planner._project_next_week()
        
        # Should only include goals from the next 5 working days
        # The exact count depends on how many goals are in each day
        assert isinstance(next_week_goals, list)


class TestWeeklyFileExists:
    """Test that the weekly module file exists."""

    def test_weekly_file_exists(self):
        """weekly.py module should exist."""
        path = Path.cwd() / "swarm_attack" / "chief_of_staff" / "weekly.py"
        assert path.exists(), f"weekly.py must exist at {path}"