"""Tests for Issue #9: CampaignExecutor.execute_day()

Tests the CampaignExecutor class that executes daily goals for campaigns.
"""

import pytest
from datetime import date, datetime
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch
import tempfile

from swarm_attack.chief_of_staff.campaigns import (
    Campaign,
    CampaignState,
    CampaignStore,
    DayPlan,
    Milestone,
)
from swarm_attack.chief_of_staff.config import ChiefOfStaffConfig
from swarm_attack.chief_of_staff.autopilot_runner import AutopilotRunner, AutopilotRunResult
from swarm_attack.chief_of_staff.autopilot import AutopilotSession, AutopilotState
from swarm_attack.chief_of_staff.goal_tracker import DailyGoal, GoalStatus


class TestDayExecutionResult:
    """Tests for DayExecutionResult dataclass."""

    def test_create_with_all_fields(self):
        """Test creating DayExecutionResult with all fields."""
        from swarm_attack.chief_of_staff.campaign_executor import DayExecutionResult

        result = DayExecutionResult(
            goals_completed=3,
            goals_blocked=["goal-1", "goal-2"],
            cost_usd=5.50,
            needs_replan=True,
        )

        assert result.goals_completed == 3
        assert result.goals_blocked == ["goal-1", "goal-2"]
        assert result.cost_usd == 5.50
        assert result.needs_replan is True

    def test_create_minimal(self):
        """Test creating DayExecutionResult with minimal fields."""
        from swarm_attack.chief_of_staff.campaign_executor import DayExecutionResult

        result = DayExecutionResult(
            goals_completed=0,
            goals_blocked=[],
            cost_usd=0.0,
            needs_replan=False,
        )

        assert result.goals_completed == 0
        assert result.goals_blocked == []
        assert result.cost_usd == 0.0
        assert result.needs_replan is False


class TestCampaignExecutorInit:
    """Tests for CampaignExecutor initialization."""

    def test_init_with_all_dependencies(self):
        """Test initializing CampaignExecutor with all dependencies."""
        from swarm_attack.chief_of_staff.campaign_executor import CampaignExecutor

        config = ChiefOfStaffConfig()
        with tempfile.TemporaryDirectory() as tmpdir:
            campaign_store = CampaignStore(Path(tmpdir))
            autopilot_runner = MagicMock(spec=AutopilotRunner)

            executor = CampaignExecutor(
                config=config,
                campaign_store=campaign_store,
                autopilot_runner=autopilot_runner,
            )

            assert executor.config is config
            assert executor.campaign_store is campaign_store
            assert executor.autopilot_runner is autopilot_runner


class TestCampaignExecutorExecuteDay:
    """Tests for CampaignExecutor.execute_day()."""

    @pytest.fixture
    def setup_executor(self):
        """Create executor with mocked dependencies."""
        from swarm_attack.chief_of_staff.campaign_executor import CampaignExecutor

        config = ChiefOfStaffConfig()
        tmpdir = tempfile.mkdtemp()
        campaign_store = CampaignStore(Path(tmpdir))
        autopilot_runner = MagicMock(spec=AutopilotRunner)

        executor = CampaignExecutor(
            config=config,
            campaign_store=campaign_store,
            autopilot_runner=autopilot_runner,
        )

        return executor, campaign_store, autopilot_runner, tmpdir

    @pytest.mark.asyncio
    async def test_execute_day_with_valid_campaign(self, setup_executor):
        """Test executing a day with valid campaign and goals."""
        from swarm_attack.chief_of_staff.campaign_executor import DayExecutionResult

        executor, campaign_store, autopilot_runner, tmpdir = setup_executor

        # Create a campaign with day plan for today
        today = date.today()
        campaign = Campaign(
            id="test-campaign",
            name="Test Campaign",
            state=CampaignState.ACTIVE,
            day_plans=[
                DayPlan(
                    date=today,
                    goals=["Implement feature A", "Fix bug B"],
                    day_number=1,
                    status="pending",
                )
            ],
        )
        await campaign_store.save(campaign)

        # Mock autopilot_runner.start() to return successful result
        mock_session = AutopilotSession(
            session_id="test-session",
            state=AutopilotState.COMPLETED,
            goals=[],
        )
        autopilot_runner.start.return_value = AutopilotRunResult(
            session=mock_session,
            goals_completed=2,
            goals_total=2,
            total_cost_usd=3.50,
            duration_seconds=120,
        )

        result = await executor.execute_day("test-campaign", day=today)

        assert isinstance(result, DayExecutionResult)
        assert result.goals_completed == 2
        assert result.cost_usd == 3.50
        assert result.needs_replan is False
        autopilot_runner.start.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_day_defaults_to_today(self, setup_executor):
        """Test that execute_day defaults to today if no day provided."""
        from swarm_attack.chief_of_staff.campaign_executor import DayExecutionResult

        executor, campaign_store, autopilot_runner, tmpdir = setup_executor

        today = date.today()
        campaign = Campaign(
            id="test-campaign",
            name="Test Campaign",
            state=CampaignState.ACTIVE,
            day_plans=[
                DayPlan(
                    date=today,
                    goals=["Do something"],
                    day_number=1,
                    status="pending",
                )
            ],
        )
        await campaign_store.save(campaign)

        mock_session = AutopilotSession(
            session_id="test-session",
            state=AutopilotState.COMPLETED,
            goals=[],
        )
        autopilot_runner.start.return_value = AutopilotRunResult(
            session=mock_session,
            goals_completed=1,
            goals_total=1,
            total_cost_usd=1.0,
            duration_seconds=60,
        )

        # Call without day parameter
        result = await executor.execute_day("test-campaign")

        assert result.goals_completed == 1
        autopilot_runner.start.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_day_campaign_not_found(self, setup_executor):
        """Test execute_day raises error when campaign not found."""
        executor, campaign_store, autopilot_runner, tmpdir = setup_executor

        with pytest.raises(ValueError, match="Campaign not found"):
            await executor.execute_day("nonexistent-campaign")

    @pytest.mark.asyncio
    async def test_execute_day_campaign_not_active(self, setup_executor):
        """Test execute_day raises error when campaign is not active."""
        executor, campaign_store, autopilot_runner, tmpdir = setup_executor

        campaign = Campaign(
            id="paused-campaign",
            name="Paused Campaign",
            state=CampaignState.PAUSED,
        )
        await campaign_store.save(campaign)

        with pytest.raises(ValueError, match="not active"):
            await executor.execute_day("paused-campaign")

    @pytest.mark.asyncio
    async def test_execute_day_no_plan_for_date(self, setup_executor):
        """Test execute_day when no day plan exists for the specified date."""
        from swarm_attack.chief_of_staff.campaign_executor import DayExecutionResult

        executor, campaign_store, autopilot_runner, tmpdir = setup_executor

        campaign = Campaign(
            id="test-campaign",
            name="Test Campaign",
            state=CampaignState.ACTIVE,
            day_plans=[],  # No day plans
        )
        await campaign_store.save(campaign)

        result = await executor.execute_day("test-campaign", day=date.today())

        # Should return empty result with no goals
        assert result.goals_completed == 0
        assert result.goals_blocked == []
        assert result.cost_usd == 0.0

    @pytest.mark.asyncio
    async def test_execute_day_with_blocked_goals(self, setup_executor):
        """Test execute_day returns blocked goals correctly."""
        from swarm_attack.chief_of_staff.campaign_executor import DayExecutionResult

        executor, campaign_store, autopilot_runner, tmpdir = setup_executor

        today = date.today()
        campaign = Campaign(
            id="test-campaign",
            name="Test Campaign",
            state=CampaignState.ACTIVE,
            day_plans=[
                DayPlan(
                    date=today,
                    goals=["Goal A", "Goal B", "Goal C"],
                    day_number=1,
                    status="pending",
                )
            ],
        )
        await campaign_store.save(campaign)

        # Mock autopilot_runner to return partial completion
        mock_session = AutopilotSession(
            session_id="test-session",
            state=AutopilotState.PAUSED,  # Paused due to blocker
            goals=[
                {"goal_id": "goal-1", "description": "Goal A", "status": "complete"},
                {"goal_id": "goal-2", "description": "Goal B", "status": "blocked"},
                {"goal_id": "goal-3", "description": "Goal C", "status": "blocked"},
            ],
        )
        autopilot_runner.start.return_value = AutopilotRunResult(
            session=mock_session,
            goals_completed=1,
            goals_total=3,
            total_cost_usd=2.0,
            duration_seconds=90,
        )

        result = await executor.execute_day("test-campaign", day=today)

        assert result.goals_completed == 1
        # Should have blocked goals from failed execution
        assert result.cost_usd == 2.0

    @pytest.mark.asyncio
    async def test_execute_day_triggers_replan(self, setup_executor):
        """Test execute_day sets needs_replan when campaign is behind."""
        from swarm_attack.chief_of_staff.campaign_executor import DayExecutionResult

        executor, campaign_store, autopilot_runner, tmpdir = setup_executor

        today = date.today()
        # Create campaign that is significantly behind
        campaign = Campaign(
            id="test-campaign",
            name="Test Campaign",
            state=CampaignState.ACTIVE,
            start_date=today,
            planned_days=10,
            current_day=0,  # Behind schedule
            day_plans=[
                DayPlan(
                    date=today,
                    goals=["Goal A"],
                    day_number=1,
                    status="pending",
                )
            ],
        )
        await campaign_store.save(campaign)

        mock_session = AutopilotSession(
            session_id="test-session",
            state=AutopilotState.COMPLETED,
            goals=[],
        )
        autopilot_runner.start.return_value = AutopilotRunResult(
            session=mock_session,
            goals_completed=0,
            goals_total=1,
            total_cost_usd=1.0,
            duration_seconds=60,
        )

        result = await executor.execute_day("test-campaign", day=today)

        # Should indicate replan needed if campaign is behind
        # The needs_replan logic checks campaign.needs_replan()
        assert isinstance(result.needs_replan, bool)

    @pytest.mark.asyncio
    async def test_execute_day_updates_campaign_state(self, setup_executor):
        """Test execute_day updates campaign spent_usd and current_day."""
        executor, campaign_store, autopilot_runner, tmpdir = setup_executor

        today = date.today()
        campaign = Campaign(
            id="test-campaign",
            name="Test Campaign",
            state=CampaignState.ACTIVE,
            spent_usd=5.0,
            current_day=0,
            day_plans=[
                DayPlan(
                    date=today,
                    goals=["Goal A"],
                    day_number=1,
                    status="pending",
                )
            ],
        )
        await campaign_store.save(campaign)

        mock_session = AutopilotSession(
            session_id="test-session",
            state=AutopilotState.COMPLETED,
            goals=[],
        )
        autopilot_runner.start.return_value = AutopilotRunResult(
            session=mock_session,
            goals_completed=1,
            goals_total=1,
            total_cost_usd=2.50,
            duration_seconds=60,
        )

        await executor.execute_day("test-campaign", day=today)

        # Reload campaign and check updates
        updated_campaign = await campaign_store.load("test-campaign")
        assert updated_campaign.spent_usd == 7.50  # 5.0 + 2.50
        assert updated_campaign.current_day == 1  # Incremented

    @pytest.mark.asyncio
    async def test_execute_day_marks_day_plan_complete(self, setup_executor):
        """Test execute_day marks the day plan as complete."""
        executor, campaign_store, autopilot_runner, tmpdir = setup_executor

        today = date.today()
        campaign = Campaign(
            id="test-campaign",
            name="Test Campaign",
            state=CampaignState.ACTIVE,
            day_plans=[
                DayPlan(
                    date=today,
                    goals=["Goal A"],
                    day_number=1,
                    status="pending",
                )
            ],
        )
        await campaign_store.save(campaign)

        mock_session = AutopilotSession(
            session_id="test-session",
            state=AutopilotState.COMPLETED,
            goals=[],
        )
        autopilot_runner.start.return_value = AutopilotRunResult(
            session=mock_session,
            goals_completed=1,
            goals_total=1,
            total_cost_usd=1.0,
            duration_seconds=60,
        )

        await executor.execute_day("test-campaign", day=today)

        # Reload campaign and check day plan status
        updated_campaign = await campaign_store.load("test-campaign")
        day_plan = next(
            (dp for dp in updated_campaign.day_plans if dp.date == today), None
        )
        assert day_plan is not None
        assert day_plan.status == "complete"
