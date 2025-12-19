"""Tests for campaign progress in standup command."""

import pytest
from datetime import datetime, date
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import asyncio


class TestCampaignStandupSection:
    """Tests for the Active Campaigns section in standup."""

    def test_format_campaign_progress_basic(self):
        """Test formatting a basic campaign progress display."""
        from swarm_attack.chief_of_staff.campaigns import (
            Campaign, CampaignState, Milestone, DayPlan
        )
        from swarm_attack.chief_of_staff.standup_campaigns import format_campaign_progress

        campaign = Campaign(
            campaign_id="camp1",
            name="Test Campaign",
            description="A test campaign",
            start_date=date(2025, 1, 15),
            planned_days=5,
            total_budget_usd=500.0,
            state=CampaignState.ACTIVE,
            current_day=2,
            spent_usd=150.0,
            milestones=[
                Milestone(
                    milestone_id="m1",
                    name="First Milestone",
                    description="Complete setup",
                    target_day=2,
                    success_criteria=["Tests pass"],
                    status="completed",
                ),
                Milestone(
                    milestone_id="m2",
                    name="Second Milestone",
                    description="Feature complete",
                    target_day=4,
                    success_criteria=["Feature works"],
                    status="pending",
                ),
            ],
            day_plans=[
                DayPlan(
                    day_number=2,
                    date=date.today(),
                    goals=["Goal 1", "Goal 2"],
                    budget_usd=100.0,
                ),
            ],
        )

        result = format_campaign_progress(campaign)
        assert "Test Campaign" in result["name"]
        assert result["current_day"] == 2
        assert result["total_days"] == 5
        assert result["milestones_completed"] == 1
        assert result["milestones_total"] == 2
        assert result["budget_spent"] == 150.0
        assert result["budget_total"] == 500.0

    def test_format_campaign_progress_with_todays_goals(self):
        """Test that today's goals from day_plans are included."""
        from swarm_attack.chief_of_staff.campaigns import (
            Campaign, CampaignState, DayPlan
        )
        from swarm_attack.chief_of_staff.standup_campaigns import format_campaign_progress

        campaign = Campaign(
            campaign_id="camp1",
            name="Test Campaign",
            description="Test",
            start_date=date.today(),
            planned_days=5,
            total_budget_usd=500.0,
            state=CampaignState.ACTIVE,
            current_day=1,
            day_plans=[
                DayPlan(
                    day_number=1,
                    date=date.today(),
                    goals=["Complete feature X", "Review PR"],
                    budget_usd=100.0,
                ),
            ],
        )

        result = format_campaign_progress(campaign)
        assert result["todays_goals"] == ["Complete feature X", "Review PR"]

    def test_format_campaign_progress_no_todays_plan(self):
        """Test handling when there's no day plan for today."""
        from swarm_attack.chief_of_staff.campaigns import Campaign, CampaignState
        from swarm_attack.chief_of_staff.standup_campaigns import format_campaign_progress

        campaign = Campaign(
            campaign_id="camp1",
            name="Test Campaign",
            description="Test",
            start_date=date(2025, 1, 15),
            planned_days=5,
            total_budget_usd=500.0,
            state=CampaignState.ACTIVE,
            current_day=2,
            day_plans=[],  # No day plans
        )

        result = format_campaign_progress(campaign)
        assert result["todays_goals"] == []


class TestCampaignNeedsAttention:
    """Tests for detecting campaigns that need attention."""

    def test_campaign_needs_attention_behind_schedule(self):
        """Test that behind schedule campaigns are flagged."""
        from swarm_attack.chief_of_staff.campaigns import Campaign, CampaignState
        from swarm_attack.chief_of_staff.standup_campaigns import campaign_needs_attention

        # Campaign that is behind schedule
        campaign = Campaign(
            campaign_id="camp1",
            name="Behind Schedule",
            description="Test",
            start_date=date(2025, 1, 1),  # Started long ago
            planned_days=10,
            total_budget_usd=1000.0,
            state=CampaignState.ACTIVE,
            current_day=2,  # Way behind
        )

        result = campaign_needs_attention(campaign)
        assert result["needs_attention"] is True
        assert "behind" in result["reason"].lower() or "schedule" in result["reason"].lower()

    def test_campaign_needs_attention_nearing_budget(self):
        """Test that campaigns nearing budget limit are flagged."""
        from swarm_attack.chief_of_staff.campaigns import Campaign, CampaignState
        from swarm_attack.chief_of_staff.standup_campaigns import campaign_needs_attention

        # Campaign at 85% of budget
        campaign = Campaign(
            campaign_id="camp1",
            name="Near Budget",
            description="Test",
            start_date=date.today(),
            planned_days=5,
            total_budget_usd=100.0,
            state=CampaignState.ACTIVE,
            current_day=2,
            spent_usd=85.0,  # 85% spent
        )

        result = campaign_needs_attention(campaign)
        assert result["needs_attention"] is True
        assert "budget" in result["reason"].lower()

    def test_campaign_no_attention_needed(self):
        """Test that healthy campaigns don't need attention."""
        from swarm_attack.chief_of_staff.campaigns import Campaign, CampaignState
        from swarm_attack.chief_of_staff.standup_campaigns import campaign_needs_attention

        campaign = Campaign(
            campaign_id="camp1",
            name="Healthy Campaign",
            description="Test",
            start_date=date.today(),
            planned_days=5,
            total_budget_usd=500.0,
            state=CampaignState.ACTIVE,
            current_day=1,
            spent_usd=50.0,  # Only 10% spent
        )

        result = campaign_needs_attention(campaign)
        assert result["needs_attention"] is False


class TestGetActiveCampaigns:
    """Tests for getting active campaigns for standup."""

    def test_get_active_campaigns_filters_by_state(self):
        """Test that only ACTIVE campaigns are returned."""
        from swarm_attack.chief_of_staff.campaigns import Campaign, CampaignState
        from swarm_attack.chief_of_staff.standup_campaigns import get_active_campaigns

        campaigns = [
            Campaign(
                campaign_id="camp1",
                name="Active One",
                description="Test",
                start_date=date.today(),
                planned_days=5,
                total_budget_usd=500.0,
                state=CampaignState.ACTIVE,
            ),
            Campaign(
                campaign_id="camp2",
                name="Planning",
                description="Test",
                start_date=date.today(),
                planned_days=5,
                total_budget_usd=500.0,
                state=CampaignState.PLANNING,
            ),
            Campaign(
                campaign_id="camp3",
                name="Completed",
                description="Test",
                start_date=date.today(),
                planned_days=5,
                total_budget_usd=500.0,
                state=CampaignState.COMPLETED,
            ),
            Campaign(
                campaign_id="camp4",
                name="Paused",
                description="Test",
                start_date=date.today(),
                planned_days=5,
                total_budget_usd=500.0,
                state=CampaignState.PAUSED,
            ),
        ]

        result = get_active_campaigns(campaigns)
        assert len(result) == 1
        assert result[0].name == "Active One"

    def test_get_active_campaigns_empty_list(self):
        """Test handling of empty campaign list."""
        from swarm_attack.chief_of_staff.standup_campaigns import get_active_campaigns

        result = get_active_campaigns([])
        assert result == []


class TestStandupCampaignDisplay:
    """Tests for the standup campaign display functions."""

    def test_render_campaign_section_with_campaigns(self):
        """Test rendering campaign section with active campaigns."""
        from swarm_attack.chief_of_staff.campaigns import Campaign, CampaignState, DayPlan
        from swarm_attack.chief_of_staff.standup_campaigns import render_campaign_section

        campaigns = [
            Campaign(
                campaign_id="camp1",
                name="Feature Sprint",
                description="Building feature X",
                start_date=date.today(),
                planned_days=5,
                total_budget_usd=500.0,
                state=CampaignState.ACTIVE,
                current_day=2,
                spent_usd=150.0,
                day_plans=[
                    DayPlan(
                        day_number=2,
                        date=date.today(),
                        goals=["Implement core logic"],
                        budget_usd=100.0,
                    ),
                ],
            ),
        ]

        result = render_campaign_section(campaigns)
        assert "Feature Sprint" in result
        assert "Day 2 / 5" in result or "2/5" in result or "day 2" in result.lower()

    def test_render_campaign_section_no_campaigns(self):
        """Test rendering campaign section when no active campaigns."""
        from swarm_attack.chief_of_staff.standup_campaigns import render_campaign_section

        result = render_campaign_section([])
        assert "no active" in result.lower() or result == ""

    def test_render_campaign_section_shows_budget(self):
        """Test that budget info is included in render."""
        from swarm_attack.chief_of_staff.campaigns import Campaign, CampaignState
        from swarm_attack.chief_of_staff.standup_campaigns import render_campaign_section

        campaigns = [
            Campaign(
                campaign_id="camp1",
                name="Test Campaign",
                description="Test",
                start_date=date.today(),
                planned_days=5,
                total_budget_usd=500.0,
                state=CampaignState.ACTIVE,
                current_day=2,
                spent_usd=200.0,
            ),
        ]

        result = render_campaign_section(campaigns)
        # Should show budget info like "$200/$500" or "200.00/500.00"
        assert "200" in result or "spent" in result.lower()

    def test_render_campaign_section_shows_milestones(self):
        """Test that milestone progress is included in render."""
        from swarm_attack.chief_of_staff.campaigns import (
            Campaign, CampaignState, Milestone
        )
        from swarm_attack.chief_of_staff.standup_campaigns import render_campaign_section

        campaigns = [
            Campaign(
                campaign_id="camp1",
                name="Test Campaign",
                description="Test",
                start_date=date.today(),
                planned_days=5,
                total_budget_usd=500.0,
                state=CampaignState.ACTIVE,
                current_day=2,
                milestones=[
                    Milestone(
                        milestone_id="m1",
                        name="Done",
                        description="Complete",
                        target_day=1,
                        success_criteria=[],
                        status="completed",
                    ),
                    Milestone(
                        milestone_id="m2",
                        name="Pending",
                        description="Not yet",
                        target_day=3,
                        success_criteria=[],
                        status="pending",
                    ),
                ],
            ),
        ]

        result = render_campaign_section(campaigns)
        # Should show milestone progress like "1/2" or "Milestones: 1/2"
        assert "1" in result and "2" in result


class TestStandupCampaignAttentionFlags:
    """Tests for attention flag display in standup."""

    def test_render_attention_flag_for_behind_campaign(self):
        """Test that behind schedule campaigns show attention flag."""
        from swarm_attack.chief_of_staff.campaigns import Campaign, CampaignState
        from swarm_attack.chief_of_staff.standup_campaigns import render_attention_flags

        campaigns = [
            Campaign(
                campaign_id="camp1",
                name="Behind Schedule",
                description="Test",
                start_date=date(2025, 1, 1),
                planned_days=10,
                total_budget_usd=1000.0,
                state=CampaignState.ACTIVE,
                current_day=2,
            ),
        ]

        result = render_attention_flags(campaigns)
        assert len(result) > 0
        assert any("Behind Schedule" in item or "behind" in item.lower() for item in result)

    def test_render_attention_flag_for_budget_campaign(self):
        """Test that budget-constrained campaigns show attention flag."""
        from swarm_attack.chief_of_staff.campaigns import Campaign, CampaignState
        from swarm_attack.chief_of_staff.standup_campaigns import render_attention_flags

        campaigns = [
            Campaign(
                campaign_id="camp1",
                name="Budget Alert",
                description="Test",
                start_date=date.today(),
                planned_days=5,
                total_budget_usd=100.0,
                state=CampaignState.ACTIVE,
                current_day=2,
                spent_usd=90.0,  # 90% spent
            ),
        ]

        result = render_attention_flags(campaigns)
        assert len(result) > 0
        assert any("Budget Alert" in item or "budget" in item.lower() for item in result)

    def test_render_no_attention_flags_for_healthy(self):
        """Test that healthy campaigns have no attention flags."""
        from swarm_attack.chief_of_staff.campaigns import Campaign, CampaignState
        from swarm_attack.chief_of_staff.standup_campaigns import render_attention_flags

        campaigns = [
            Campaign(
                campaign_id="camp1",
                name="Healthy Campaign",
                description="Test",
                start_date=date.today(),
                planned_days=5,
                total_budget_usd=500.0,
                state=CampaignState.ACTIVE,
                current_day=1,
                spent_usd=50.0,
            ),
        ]

        result = render_attention_flags(campaigns)
        assert len(result) == 0


class TestNoCampaignsHandling:
    """Tests for graceful handling when no campaigns exist."""

    def test_standup_campaigns_graceful_no_campaigns(self):
        """Test that standup handles no active campaigns gracefully."""
        from swarm_attack.chief_of_staff.standup_campaigns import render_campaign_section

        result = render_campaign_section([])
        # Should return empty string or message about no campaigns
        assert result == "" or "no active" in result.lower()

    def test_get_active_campaigns_returns_empty_list(self):
        """Test that get_active_campaigns returns empty list when none exist."""
        from swarm_attack.chief_of_staff.standup_campaigns import get_active_campaigns

        result = get_active_campaigns([])
        assert result == []
        assert isinstance(result, list)


class TestCampaignStoreIntegration:
    """Tests for CampaignStore integration with standup."""

    def test_get_campaign_store_from_cli(self):
        """Test that we can get a CampaignStore from CLI context."""
        from swarm_attack.chief_of_staff.standup_campaigns import get_campaign_store
        from pathlib import Path
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            base_path = Path(tmpdir)
            store = get_campaign_store(base_path)
            assert store is not None
            assert hasattr(store, 'list_all_sync')

    def test_load_campaigns_for_standup(self):
        """Test loading campaigns for standup display."""
        from swarm_attack.chief_of_staff.standup_campaigns import load_campaigns_for_standup
        from swarm_attack.chief_of_staff.campaigns import CampaignStore, Campaign, CampaignState
        from pathlib import Path
        import tempfile
        import json

        with tempfile.TemporaryDirectory() as tmpdir:
            base_path = Path(tmpdir)
            campaigns_dir = base_path / "campaigns"
            campaigns_dir.mkdir(parents=True)

            # Create a test campaign file
            campaign_data = {
                "campaign_id": "test-camp",
                "name": "Test Campaign",
                "description": "Test",
                "start_date": date.today().isoformat(),
                "planned_days": 5,
                "total_budget_usd": 500.0,
                "state": "active",
                "current_day": 1,
                "milestones": [],
                "day_plans": [],
                "spent_usd": 0.0,
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
            }
            with open(campaigns_dir / "test-camp.json", "w") as f:
                json.dump(campaign_data, f)

            campaigns = load_campaigns_for_standup(base_path)
            assert len(campaigns) == 1
            assert campaigns[0].name == "Test Campaign"


class TestStandupModuleExists:
    """Test that the standup_campaigns module file exists."""

    def test_standup_campaigns_module_exists(self):
        path = Path.cwd() / "swarm_attack" / "chief_of_staff" / "standup_campaigns.py"
        assert path.exists(), "standup_campaigns.py must exist"


class TestCalculateBudgetRemaining:
    """Tests for budget remaining calculation."""

    def test_calculate_budget_remaining(self):
        """Test calculating remaining budget."""
        from swarm_attack.chief_of_staff.campaigns import Campaign, CampaignState
        from swarm_attack.chief_of_staff.standup_campaigns import calculate_budget_remaining

        campaign = Campaign(
            campaign_id="camp1",
            name="Test",
            description="Test",
            start_date=date.today(),
            planned_days=5,
            total_budget_usd=500.0,
            state=CampaignState.ACTIVE,
            current_day=2,
            spent_usd=200.0,
        )

        remaining = calculate_budget_remaining(campaign)
        assert remaining == 300.0

    def test_calculate_budget_remaining_zero(self):
        """Test when budget is fully spent."""
        from swarm_attack.chief_of_staff.campaigns import Campaign, CampaignState
        from swarm_attack.chief_of_staff.standup_campaigns import calculate_budget_remaining

        campaign = Campaign(
            campaign_id="camp1",
            name="Test",
            description="Test",
            start_date=date.today(),
            planned_days=5,
            total_budget_usd=500.0,
            state=CampaignState.ACTIVE,
            current_day=5,
            spent_usd=500.0,
        )

        remaining = calculate_budget_remaining(campaign)
        assert remaining == 0.0


class TestCountCompletedMilestones:
    """Tests for counting completed milestones."""

    def test_count_completed_milestones(self):
        """Test counting completed milestones."""
        from swarm_attack.chief_of_staff.campaigns import Campaign, CampaignState, Milestone
        from swarm_attack.chief_of_staff.standup_campaigns import count_completed_milestones

        campaign = Campaign(
            campaign_id="camp1",
            name="Test",
            description="Test",
            start_date=date.today(),
            planned_days=5,
            total_budget_usd=500.0,
            state=CampaignState.ACTIVE,
            milestones=[
                Milestone(
                    milestone_id="m1",
                    name="Done",
                    description="Complete",
                    target_day=1,
                    success_criteria=[],
                    status="completed",
                ),
                Milestone(
                    milestone_id="m2",
                    name="Also Done",
                    description="Complete",
                    target_day=2,
                    success_criteria=[],
                    status="completed",
                ),
                Milestone(
                    milestone_id="m3",
                    name="Pending",
                    description="Not yet",
                    target_day=3,
                    success_criteria=[],
                    status="pending",
                ),
            ],
        )

        completed = count_completed_milestones(campaign)
        assert completed == 2

    def test_count_completed_milestones_none_completed(self):
        """Test when no milestones are completed."""
        from swarm_attack.chief_of_staff.campaigns import Campaign, CampaignState, Milestone
        from swarm_attack.chief_of_staff.standup_campaigns import count_completed_milestones

        campaign = Campaign(
            campaign_id="camp1",
            name="Test",
            description="Test",
            start_date=date.today(),
            planned_days=5,
            total_budget_usd=500.0,
            state=CampaignState.ACTIVE,
            milestones=[
                Milestone(
                    milestone_id="m1",
                    name="Pending",
                    description="Not yet",
                    target_day=1,
                    success_criteria=[],
                    status="pending",
                ),
            ],
        )

        completed = count_completed_milestones(campaign)
        assert completed == 0


class TestGetTodaysGoals:
    """Tests for getting today's goals from campaign."""

    def test_get_todays_goals_from_campaign(self):
        """Test getting today's goals from day_plans."""
        from swarm_attack.chief_of_staff.campaigns import Campaign, CampaignState, DayPlan
        from swarm_attack.chief_of_staff.standup_campaigns import get_todays_goals_from_campaign

        campaign = Campaign(
            campaign_id="camp1",
            name="Test",
            description="Test",
            start_date=date.today(),
            planned_days=5,
            total_budget_usd=500.0,
            state=CampaignState.ACTIVE,
            current_day=1,
            day_plans=[
                DayPlan(
                    day_number=1,
                    date=date.today(),
                    goals=["Goal A", "Goal B"],
                    budget_usd=100.0,
                ),
                DayPlan(
                    day_number=2,
                    date=date(2025, 12, 20),  # Tomorrow
                    goals=["Goal C"],
                    budget_usd=100.0,
                ),
            ],
        )

        goals = get_todays_goals_from_campaign(campaign)
        assert goals == ["Goal A", "Goal B"]

    def test_get_todays_goals_no_plan_for_today(self):
        """Test when there's no plan for today."""
        from swarm_attack.chief_of_staff.campaigns import Campaign, CampaignState, DayPlan
        from swarm_attack.chief_of_staff.standup_campaigns import get_todays_goals_from_campaign

        campaign = Campaign(
            campaign_id="camp1",
            name="Test",
            description="Test",
            start_date=date(2025, 1, 1),
            planned_days=5,
            total_budget_usd=500.0,
            state=CampaignState.ACTIVE,
            current_day=1,
            day_plans=[
                DayPlan(
                    day_number=1,
                    date=date(2025, 1, 1),  # Past date
                    goals=["Old goal"],
                    budget_usd=100.0,
                ),
            ],
        )

        goals = get_todays_goals_from_campaign(campaign)
        assert goals == []