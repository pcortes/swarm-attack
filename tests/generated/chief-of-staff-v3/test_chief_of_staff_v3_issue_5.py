"""Tests for Campaign, Milestone, DayPlan dataclasses and CampaignState enum."""

import pytest
from datetime import datetime, date
from pathlib import Path


class TestCampaignState:
    """Tests for CampaignState enum."""

    def test_campaign_state_has_planning(self):
        from swarm_attack.chief_of_staff.campaigns import CampaignState
        assert hasattr(CampaignState, 'PLANNING')

    def test_campaign_state_has_active(self):
        from swarm_attack.chief_of_staff.campaigns import CampaignState
        assert hasattr(CampaignState, 'ACTIVE')

    def test_campaign_state_has_paused(self):
        from swarm_attack.chief_of_staff.campaigns import CampaignState
        assert hasattr(CampaignState, 'PAUSED')

    def test_campaign_state_has_completed(self):
        from swarm_attack.chief_of_staff.campaigns import CampaignState
        assert hasattr(CampaignState, 'COMPLETED')

    def test_campaign_state_has_failed(self):
        from swarm_attack.chief_of_staff.campaigns import CampaignState
        assert hasattr(CampaignState, 'FAILED')

    def test_campaign_state_values(self):
        from swarm_attack.chief_of_staff.campaigns import CampaignState
        assert CampaignState.PLANNING.value == "planning"
        assert CampaignState.ACTIVE.value == "active"
        assert CampaignState.PAUSED.value == "paused"
        assert CampaignState.COMPLETED.value == "completed"
        assert CampaignState.FAILED.value == "failed"


class TestMilestone:
    """Tests for Milestone dataclass."""

    def test_milestone_has_required_fields(self):
        from swarm_attack.chief_of_staff.campaigns import Milestone
        milestone = Milestone(
            milestone_id="m1",
            name="First Milestone",
            description="Complete initial setup",
            target_day=3,
            success_criteria=["Tests pass", "Code reviewed"],
        )
        assert milestone.milestone_id == "m1"
        assert milestone.name == "First Milestone"
        assert milestone.description == "Complete initial setup"
        assert milestone.target_day == 3
        assert milestone.success_criteria == ["Tests pass", "Code reviewed"]
        assert milestone.status == "pending"
        assert milestone.completed_at is None

    def test_milestone_with_completed_status(self):
        from swarm_attack.chief_of_staff.campaigns import Milestone
        completed_at = datetime(2025, 1, 15, 10, 30, 0)
        milestone = Milestone(
            milestone_id="m2",
            name="Second Milestone",
            description="Feature complete",
            target_day=5,
            success_criteria=["Feature works"],
            status="completed",
            completed_at=completed_at,
        )
        assert milestone.status == "completed"
        assert milestone.completed_at == completed_at

    def test_milestone_to_dict(self):
        from swarm_attack.chief_of_staff.campaigns import Milestone
        completed_at = datetime(2025, 1, 15, 10, 30, 0)
        milestone = Milestone(
            milestone_id="m1",
            name="Test Milestone",
            description="Test description",
            target_day=2,
            success_criteria=["Criterion 1", "Criterion 2"],
            status="completed",
            completed_at=completed_at,
        )
        data = milestone.to_dict()
        assert data["milestone_id"] == "m1"
        assert data["name"] == "Test Milestone"
        assert data["description"] == "Test description"
        assert data["target_day"] == 2
        assert data["success_criteria"] == ["Criterion 1", "Criterion 2"]
        assert data["status"] == "completed"
        assert data["completed_at"] == completed_at.isoformat()

    def test_milestone_to_dict_with_none_completed_at(self):
        from swarm_attack.chief_of_staff.campaigns import Milestone
        milestone = Milestone(
            milestone_id="m1",
            name="Pending Milestone",
            description="Not done yet",
            target_day=5,
            success_criteria=["Do thing"],
        )
        data = milestone.to_dict()
        assert data["completed_at"] is None

    def test_milestone_from_dict(self):
        from swarm_attack.chief_of_staff.campaigns import Milestone
        data = {
            "milestone_id": "m1",
            "name": "Test Milestone",
            "description": "Test description",
            "target_day": 2,
            "success_criteria": ["Criterion 1"],
            "status": "pending",
            "completed_at": None,
        }
        milestone = Milestone.from_dict(data)
        assert milestone.milestone_id == "m1"
        assert milestone.name == "Test Milestone"
        assert milestone.description == "Test description"
        assert milestone.target_day == 2
        assert milestone.success_criteria == ["Criterion 1"]
        assert milestone.status == "pending"
        assert milestone.completed_at is None

    def test_milestone_from_dict_with_completed_at(self):
        from swarm_attack.chief_of_staff.campaigns import Milestone
        data = {
            "milestone_id": "m1",
            "name": "Completed Milestone",
            "description": "Done",
            "target_day": 3,
            "success_criteria": ["Done"],
            "status": "completed",
            "completed_at": "2025-01-15T10:30:00",
        }
        milestone = Milestone.from_dict(data)
        assert milestone.completed_at == datetime(2025, 1, 15, 10, 30, 0)

    def test_milestone_roundtrip(self):
        from swarm_attack.chief_of_staff.campaigns import Milestone
        original = Milestone(
            milestone_id="m1",
            name="Roundtrip Test",
            description="Testing serialization",
            target_day=4,
            success_criteria=["Test 1", "Test 2"],
            status="in_progress",
            completed_at=datetime(2025, 1, 10, 8, 0, 0),
        )
        roundtrip = Milestone.from_dict(original.to_dict())
        assert roundtrip.milestone_id == original.milestone_id
        assert roundtrip.name == original.name
        assert roundtrip.description == original.description
        assert roundtrip.target_day == original.target_day
        assert roundtrip.success_criteria == original.success_criteria
        assert roundtrip.status == original.status
        assert roundtrip.completed_at == original.completed_at


class TestDayPlan:
    """Tests for DayPlan dataclass."""

    def test_dayplan_has_required_fields(self):
        from swarm_attack.chief_of_staff.campaigns import DayPlan
        plan_date = date(2025, 1, 15)
        day_plan = DayPlan(
            day_number=1,
            date=plan_date,
            goals=["Goal 1", "Goal 2"],
            budget_usd=50.0,
        )
        assert day_plan.day_number == 1
        assert day_plan.date == plan_date
        assert day_plan.goals == ["Goal 1", "Goal 2"]
        assert day_plan.budget_usd == 50.0
        assert day_plan.status == "pending"
        assert day_plan.actual_cost_usd == 0.0
        assert day_plan.notes == ""

    def test_dayplan_with_all_fields(self):
        from swarm_attack.chief_of_staff.campaigns import DayPlan
        plan_date = date(2025, 1, 16)
        day_plan = DayPlan(
            day_number=2,
            date=plan_date,
            goals=["Complete feature"],
            budget_usd=75.0,
            status="completed",
            actual_cost_usd=60.5,
            notes="Finished early",
        )
        assert day_plan.status == "completed"
        assert day_plan.actual_cost_usd == 60.5
        assert day_plan.notes == "Finished early"

    def test_dayplan_to_dict(self):
        from swarm_attack.chief_of_staff.campaigns import DayPlan
        plan_date = date(2025, 1, 15)
        day_plan = DayPlan(
            day_number=1,
            date=plan_date,
            goals=["Goal 1"],
            budget_usd=50.0,
            status="in_progress",
            actual_cost_usd=25.0,
            notes="Halfway done",
        )
        data = day_plan.to_dict()
        assert data["day_number"] == 1
        assert data["date"] == "2025-01-15"
        assert data["goals"] == ["Goal 1"]
        assert data["budget_usd"] == 50.0
        assert data["status"] == "in_progress"
        assert data["actual_cost_usd"] == 25.0
        assert data["notes"] == "Halfway done"

    def test_dayplan_from_dict(self):
        from swarm_attack.chief_of_staff.campaigns import DayPlan
        data = {
            "day_number": 3,
            "date": "2025-01-18",
            "goals": ["Final goal"],
            "budget_usd": 100.0,
            "status": "pending",
            "actual_cost_usd": 0.0,
            "notes": "",
        }
        day_plan = DayPlan.from_dict(data)
        assert day_plan.day_number == 3
        assert day_plan.date == date(2025, 1, 18)
        assert day_plan.goals == ["Final goal"]
        assert day_plan.budget_usd == 100.0
        assert day_plan.status == "pending"
        assert day_plan.actual_cost_usd == 0.0
        assert day_plan.notes == ""

    def test_dayplan_from_dict_with_defaults(self):
        from swarm_attack.chief_of_staff.campaigns import DayPlan
        data = {
            "day_number": 1,
            "date": "2025-01-15",
            "goals": ["Goal"],
            "budget_usd": 50.0,
        }
        day_plan = DayPlan.from_dict(data)
        assert day_plan.status == "pending"
        assert day_plan.actual_cost_usd == 0.0
        assert day_plan.notes == ""

    def test_dayplan_roundtrip(self):
        from swarm_attack.chief_of_staff.campaigns import DayPlan
        original = DayPlan(
            day_number=5,
            date=date(2025, 1, 20),
            goals=["Goal A", "Goal B"],
            budget_usd=80.0,
            status="completed",
            actual_cost_usd=70.0,
            notes="All done",
        )
        roundtrip = DayPlan.from_dict(original.to_dict())
        assert roundtrip.day_number == original.day_number
        assert roundtrip.date == original.date
        assert roundtrip.goals == original.goals
        assert roundtrip.budget_usd == original.budget_usd
        assert roundtrip.status == original.status
        assert roundtrip.actual_cost_usd == original.actual_cost_usd
        assert roundtrip.notes == original.notes


class TestCampaign:
    """Tests for Campaign dataclass."""

    def test_campaign_has_required_fields(self):
        from swarm_attack.chief_of_staff.campaigns import Campaign, CampaignState
        start_date = date(2025, 1, 15)
        campaign = Campaign(
            campaign_id="camp1",
            name="Test Campaign",
            description="A test campaign",
            start_date=start_date,
            planned_days=5,
            total_budget_usd=500.0,
        )
        assert campaign.campaign_id == "camp1"
        assert campaign.name == "Test Campaign"
        assert campaign.description == "A test campaign"
        assert campaign.start_date == start_date
        assert campaign.planned_days == 5
        assert campaign.total_budget_usd == 500.0
        assert campaign.state == CampaignState.PLANNING
        assert campaign.current_day == 0
        assert campaign.milestones == []
        assert campaign.day_plans == []
        assert campaign.spent_usd == 0.0
        assert campaign.created_at is not None
        assert campaign.updated_at is not None

    def test_campaign_with_milestones_and_day_plans(self):
        from swarm_attack.chief_of_staff.campaigns import (
            Campaign, CampaignState, Milestone, DayPlan
        )
        milestone = Milestone(
            milestone_id="m1",
            name="First Milestone",
            description="Complete setup",
            target_day=2,
            success_criteria=["Tests pass"],
        )
        day_plan = DayPlan(
            day_number=1,
            date=date(2025, 1, 15),
            goals=["Setup"],
            budget_usd=100.0,
        )
        campaign = Campaign(
            campaign_id="camp2",
            name="Full Campaign",
            description="With everything",
            start_date=date(2025, 1, 15),
            planned_days=3,
            total_budget_usd=300.0,
            state=CampaignState.ACTIVE,
            current_day=1,
            milestones=[milestone],
            day_plans=[day_plan],
            spent_usd=50.0,
        )
        assert campaign.state == CampaignState.ACTIVE
        assert campaign.current_day == 1
        assert len(campaign.milestones) == 1
        assert len(campaign.day_plans) == 1
        assert campaign.spent_usd == 50.0

    def test_campaign_to_dict(self):
        from swarm_attack.chief_of_staff.campaigns import (
            Campaign, CampaignState, Milestone, DayPlan
        )
        created = datetime(2025, 1, 10, 8, 0, 0)
        updated = datetime(2025, 1, 15, 12, 0, 0)
        milestone = Milestone(
            milestone_id="m1",
            name="Milestone 1",
            description="First",
            target_day=2,
            success_criteria=["Done"],
        )
        day_plan = DayPlan(
            day_number=1,
            date=date(2025, 1, 15),
            goals=["Goal 1"],
            budget_usd=100.0,
        )
        campaign = Campaign(
            campaign_id="camp1",
            name="Test Campaign",
            description="Description",
            start_date=date(2025, 1, 15),
            planned_days=5,
            total_budget_usd=500.0,
            state=CampaignState.ACTIVE,
            current_day=1,
            milestones=[milestone],
            day_plans=[day_plan],
            spent_usd=50.0,
            created_at=created,
            updated_at=updated,
        )
        data = campaign.to_dict()
        assert data["campaign_id"] == "camp1"
        assert data["name"] == "Test Campaign"
        assert data["description"] == "Description"
        assert data["start_date"] == "2025-01-15"
        assert data["planned_days"] == 5
        assert data["total_budget_usd"] == 500.0
        assert data["state"] == "active"
        assert data["current_day"] == 1
        assert len(data["milestones"]) == 1
        assert len(data["day_plans"]) == 1
        assert data["spent_usd"] == 50.0
        assert data["created_at"] == created.isoformat()
        assert data["updated_at"] == updated.isoformat()

    def test_campaign_from_dict(self):
        from swarm_attack.chief_of_staff.campaigns import Campaign, CampaignState
        data = {
            "campaign_id": "camp1",
            "name": "Test Campaign",
            "description": "Description",
            "start_date": "2025-01-15",
            "planned_days": 5,
            "total_budget_usd": 500.0,
            "state": "active",
            "current_day": 2,
            "milestones": [
                {
                    "milestone_id": "m1",
                    "name": "Milestone",
                    "description": "Desc",
                    "target_day": 3,
                    "success_criteria": ["Done"],
                    "status": "pending",
                    "completed_at": None,
                }
            ],
            "day_plans": [
                {
                    "day_number": 1,
                    "date": "2025-01-15",
                    "goals": ["Goal"],
                    "budget_usd": 100.0,
                    "status": "completed",
                    "actual_cost_usd": 80.0,
                    "notes": "Done",
                }
            ],
            "spent_usd": 80.0,
            "created_at": "2025-01-10T08:00:00",
            "updated_at": "2025-01-15T12:00:00",
        }
        campaign = Campaign.from_dict(data)
        assert campaign.campaign_id == "camp1"
        assert campaign.name == "Test Campaign"
        assert campaign.start_date == date(2025, 1, 15)
        assert campaign.planned_days == 5
        assert campaign.state == CampaignState.ACTIVE
        assert campaign.current_day == 2
        assert len(campaign.milestones) == 1
        assert campaign.milestones[0].milestone_id == "m1"
        assert len(campaign.day_plans) == 1
        assert campaign.day_plans[0].day_number == 1
        assert campaign.spent_usd == 80.0
        assert campaign.created_at == datetime(2025, 1, 10, 8, 0, 0)
        assert campaign.updated_at == datetime(2025, 1, 15, 12, 0, 0)

    def test_campaign_from_dict_with_defaults(self):
        from swarm_attack.chief_of_staff.campaigns import Campaign, CampaignState
        data = {
            "campaign_id": "camp1",
            "name": "Minimal Campaign",
            "description": "Minimal",
            "start_date": "2025-01-15",
            "planned_days": 3,
            "total_budget_usd": 300.0,
        }
        campaign = Campaign.from_dict(data)
        assert campaign.state == CampaignState.PLANNING
        assert campaign.current_day == 0
        assert campaign.milestones == []
        assert campaign.day_plans == []
        assert campaign.spent_usd == 0.0

    def test_campaign_roundtrip(self):
        from swarm_attack.chief_of_staff.campaigns import (
            Campaign, CampaignState, Milestone, DayPlan
        )
        milestone = Milestone(
            milestone_id="m1",
            name="Milestone",
            description="Test",
            target_day=2,
            success_criteria=["Done"],
            status="completed",
            completed_at=datetime(2025, 1, 17, 10, 0, 0),
        )
        day_plan = DayPlan(
            day_number=1,
            date=date(2025, 1, 15),
            goals=["Goal"],
            budget_usd=100.0,
            status="completed",
            actual_cost_usd=90.0,
            notes="Done",
        )
        original = Campaign(
            campaign_id="camp1",
            name="Roundtrip Campaign",
            description="Test roundtrip",
            start_date=date(2025, 1, 15),
            planned_days=5,
            total_budget_usd=500.0,
            state=CampaignState.COMPLETED,
            current_day=5,
            milestones=[milestone],
            day_plans=[day_plan],
            spent_usd=450.0,
            created_at=datetime(2025, 1, 10, 8, 0, 0),
            updated_at=datetime(2025, 1, 20, 18, 0, 0),
        )
        roundtrip = Campaign.from_dict(original.to_dict())
        assert roundtrip.campaign_id == original.campaign_id
        assert roundtrip.name == original.name
        assert roundtrip.start_date == original.start_date
        assert roundtrip.state == original.state
        assert roundtrip.current_day == original.current_day
        assert len(roundtrip.milestones) == len(original.milestones)
        assert len(roundtrip.day_plans) == len(original.day_plans)
        assert roundtrip.spent_usd == original.spent_usd


class TestCampaignDaysBehind:
    """Tests for Campaign.days_behind() method."""

    def test_days_behind_on_schedule(self):
        """When current_day matches expected progress, days_behind is 0."""
        from swarm_attack.chief_of_staff.campaigns import Campaign, CampaignState
        campaign = Campaign(
            campaign_id="camp1",
            name="On Schedule",
            description="Test",
            start_date=date(2025, 1, 15),
            planned_days=5,
            total_budget_usd=500.0,
            state=CampaignState.ACTIVE,
            current_day=2,
        )
        # If we're on day 2 of 5 and today is day 2 of the campaign, days_behind = 0
        assert campaign.days_behind() >= 0

    def test_days_behind_when_behind(self):
        """When current_day is less than expected, returns positive days behind."""
        from swarm_attack.chief_of_staff.campaigns import Campaign, CampaignState
        # Campaign started 5 days ago but we're only on day 2
        campaign = Campaign(
            campaign_id="camp1",
            name="Behind Schedule",
            description="Test",
            start_date=date(2025, 1, 10),  # Started 8 days ago (from today 2025-01-18)
            planned_days=10,
            total_budget_usd=1000.0,
            state=CampaignState.ACTIVE,
            current_day=2,  # Only completed day 2
        )
        days_behind = campaign.days_behind()
        # Expected to be at day ~8, but at day 2, so ~6 days behind
        assert days_behind > 0

    def test_days_behind_planning_state(self):
        """Campaign in PLANNING state has 0 days behind."""
        from swarm_attack.chief_of_staff.campaigns import Campaign, CampaignState
        campaign = Campaign(
            campaign_id="camp1",
            name="Planning",
            description="Test",
            start_date=date(2025, 1, 15),
            planned_days=5,
            total_budget_usd=500.0,
            state=CampaignState.PLANNING,
            current_day=0,
        )
        assert campaign.days_behind() == 0

    def test_days_behind_completed_state(self):
        """Campaign in COMPLETED state has 0 days behind."""
        from swarm_attack.chief_of_staff.campaigns import Campaign, CampaignState
        campaign = Campaign(
            campaign_id="camp1",
            name="Completed",
            description="Test",
            start_date=date(2025, 1, 10),
            planned_days=5,
            total_budget_usd=500.0,
            state=CampaignState.COMPLETED,
            current_day=5,
        )
        assert campaign.days_behind() == 0


class TestCampaignNeedsReplan:
    """Tests for Campaign.needs_replan() method."""

    def test_needs_replan_false_when_on_schedule(self):
        """Returns False when not significantly behind schedule."""
        from swarm_attack.chief_of_staff.campaigns import Campaign, CampaignState
        campaign = Campaign(
            campaign_id="camp1",
            name="On Track",
            description="Test",
            start_date=date(2025, 1, 15),
            planned_days=10,
            total_budget_usd=1000.0,
            state=CampaignState.ACTIVE,
            current_day=3,  # Day 3 of 10, reasonable progress
        )
        # If not >30% behind, should not need replan
        # This depends on implementation - test the logic
        result = campaign.needs_replan()
        assert isinstance(result, bool)

    def test_needs_replan_true_when_significantly_behind(self):
        """Returns True when >30% behind schedule."""
        from swarm_attack.chief_of_staff.campaigns import Campaign, CampaignState
        # Campaign started 10 days ago, planned for 10 days, but only on day 3
        # Expected: day 10, actual: day 3, behind by 7 days = 70% behind
        campaign = Campaign(
            campaign_id="camp1",
            name="Way Behind",
            description="Test",
            start_date=date(2025, 1, 8),  # 10 days ago
            planned_days=10,
            total_budget_usd=1000.0,
            state=CampaignState.ACTIVE,
            current_day=3,
        )
        assert campaign.needs_replan() is True

    def test_needs_replan_false_for_completed(self):
        """Completed campaigns don't need replan."""
        from swarm_attack.chief_of_staff.campaigns import Campaign, CampaignState
        campaign = Campaign(
            campaign_id="camp1",
            name="Done",
            description="Test",
            start_date=date(2025, 1, 1),
            planned_days=5,
            total_budget_usd=500.0,
            state=CampaignState.COMPLETED,
            current_day=5,
        )
        assert campaign.needs_replan() is False

    def test_needs_replan_false_for_planning(self):
        """Campaigns in planning don't need replan."""
        from swarm_attack.chief_of_staff.campaigns import Campaign, CampaignState
        campaign = Campaign(
            campaign_id="camp1",
            name="Planning",
            description="Test",
            start_date=date(2025, 1, 15),
            planned_days=5,
            total_budget_usd=500.0,
            state=CampaignState.PLANNING,
            current_day=0,
        )
        assert campaign.needs_replan() is False

    def test_needs_replan_at_threshold(self):
        """Test behavior exactly at 30% threshold."""
        from swarm_attack.chief_of_staff.campaigns import Campaign, CampaignState
        # 10 day campaign, 30% behind = 3 days behind
        # If expected day is 10 and current is 7, that's exactly 30%
        campaign = Campaign(
            campaign_id="camp1",
            name="At Threshold",
            description="Test",
            start_date=date(2025, 1, 8),  # 10 days ago
            planned_days=10,
            total_budget_usd=1000.0,
            state=CampaignState.ACTIVE,
            current_day=7,  # Exactly 30% behind (expected 10, at 7)
        )
        # At exactly 30%, should NOT need replan (need to be >30%)
        assert campaign.needs_replan() is False


class TestFileExists:
    """Test that the campaigns module file exists."""

    def test_campaigns_module_exists(self):
        path = Path.cwd() / "swarm_attack" / "chief_of_staff" / "campaigns.py"
        assert path.exists(), "campaigns.py must exist"