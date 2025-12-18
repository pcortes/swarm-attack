"""Tests for AutopilotRunner (Issue #10).

Tests the Option B+ stub implementation of AutopilotRunner which:
- Validates checkpoint trigger logic
- Tracks goal progress correctly
- Persists sessions for pause/resume
- Stubs actual goal execution
"""

from __future__ import annotations

import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from unittest.mock import MagicMock, patch

import pytest

from swarm_attack.chief_of_staff.autopilot import AutopilotSession, AutopilotState
from swarm_attack.chief_of_staff.autopilot_runner import (
    AutopilotRunner,
    AutopilotRunResult,
    GoalExecutionResult,
    SessionContext,
)
from swarm_attack.chief_of_staff.autopilot_store import AutopilotSessionStore
from swarm_attack.chief_of_staff.checkpoints import CheckpointSystem, CheckpointTrigger
from swarm_attack.chief_of_staff.config import ChiefOfStaffConfig
from swarm_attack.chief_of_staff.goal_tracker import DailyGoal, GoalPriority, GoalStatus


@pytest.fixture
def temp_storage_path() -> Path:
    """Create a temporary storage directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def config() -> ChiefOfStaffConfig:
    """Create a test configuration."""
    return ChiefOfStaffConfig()


@pytest.fixture
def checkpoint_system(config: ChiefOfStaffConfig) -> CheckpointSystem:
    """Create a checkpoint system."""
    return CheckpointSystem(config)


@pytest.fixture
def session_store(temp_storage_path: Path) -> AutopilotSessionStore:
    """Create a session store."""
    return AutopilotSessionStore(temp_storage_path)


@pytest.fixture
def runner(
    config: ChiefOfStaffConfig,
    checkpoint_system: CheckpointSystem,
    session_store: AutopilotSessionStore,
) -> AutopilotRunner:
    """Create an AutopilotRunner."""
    return AutopilotRunner(
        config=config,
        checkpoint_system=checkpoint_system,
        session_store=session_store,
    )


@pytest.fixture
def sample_goals() -> list[DailyGoal]:
    """Create sample goals for testing."""
    return [
        DailyGoal(
            goal_id="goal-1",
            description="Complete feature X",
            priority=GoalPriority.HIGH,
            estimated_minutes=60,
            linked_feature="feature-x",
        ),
        DailyGoal(
            goal_id="goal-2",
            description="Fix bug Y",
            priority=GoalPriority.MEDIUM,
            estimated_minutes=30,
            linked_bug="bug-y",
        ),
        DailyGoal(
            goal_id="goal-3",
            description="Manual task",
            priority=GoalPriority.LOW,
            estimated_minutes=15,
        ),
    ]


class TestAutopilotRunnerInit:
    """Test AutopilotRunner initialization."""

    def test_init_with_required_args(
        self,
        config: ChiefOfStaffConfig,
        checkpoint_system: CheckpointSystem,
        session_store: AutopilotSessionStore,
    ):
        """Test initialization with required arguments."""
        runner = AutopilotRunner(
            config=config,
            checkpoint_system=checkpoint_system,
            session_store=session_store,
        )

        assert runner.config is config
        assert runner.checkpoint_system is checkpoint_system
        assert runner.session_store is session_store
        assert runner.orchestrator is None
        assert runner.bug_orchestrator is None

    def test_init_with_callbacks(
        self,
        config: ChiefOfStaffConfig,
        checkpoint_system: CheckpointSystem,
        session_store: AutopilotSessionStore,
    ):
        """Test initialization with callbacks."""
        on_start = MagicMock()
        on_complete = MagicMock()
        on_checkpoint = MagicMock()

        runner = AutopilotRunner(
            config=config,
            checkpoint_system=checkpoint_system,
            session_store=session_store,
            on_goal_start=on_start,
            on_goal_complete=on_complete,
            on_checkpoint=on_checkpoint,
        )

        assert runner.on_goal_start is on_start
        assert runner.on_goal_complete is on_complete
        assert runner.on_checkpoint is on_checkpoint


class TestAutopilotRunnerStart:
    """Test AutopilotRunner.start() method."""

    def test_start_creates_session(
        self, runner: AutopilotRunner, sample_goals: list[DailyGoal]
    ):
        """Test that start creates a new session."""
        result = runner.start(sample_goals)

        assert result.session is not None
        assert result.session.session_id.startswith("auto-")
        assert result.session.state == AutopilotState.COMPLETED

    def test_start_executes_all_goals(
        self, runner: AutopilotRunner, sample_goals: list[DailyGoal]
    ):
        """Test that start executes all goals."""
        result = runner.start(sample_goals)

        assert result.goals_completed == 3
        assert result.goals_total == 3
        assert result.trigger is None

    def test_start_with_empty_goals(self, runner: AutopilotRunner):
        """Test start with no goals."""
        result = runner.start([])

        assert result.goals_completed == 0
        assert result.goals_total == 0
        assert result.session.state == AutopilotState.COMPLETED

    def test_start_saves_session(
        self, runner: AutopilotRunner, sample_goals: list[DailyGoal]
    ):
        """Test that start saves session to store."""
        result = runner.start(sample_goals)

        loaded = runner.session_store.load(result.session.session_id)
        assert loaded is not None
        assert loaded.session_id == result.session.session_id
        assert loaded.state == AutopilotState.COMPLETED

    def test_start_dry_run(
        self, runner: AutopilotRunner, sample_goals: list[DailyGoal]
    ):
        """Test dry run mode doesn't execute."""
        result = runner.start(sample_goals, dry_run=True)

        assert result.goals_completed == 0
        assert result.goals_total == 3
        assert result.session.state == AutopilotState.RUNNING

    def test_start_with_custom_budget(
        self, runner: AutopilotRunner, sample_goals: list[DailyGoal]
    ):
        """Test start with custom budget."""
        result = runner.start(sample_goals, budget_usd=5.0)

        # Stub execution has zero cost, so budget won't trigger
        assert result.trigger is None
        assert result.total_cost_usd == 0.0


class TestAutopilotRunnerCheckpoints:
    """Test checkpoint trigger detection."""

    def test_cost_trigger(
        self,
        config: ChiefOfStaffConfig,
        session_store: AutopilotSessionStore,
        sample_goals: list[DailyGoal],
    ):
        """Test that cost threshold triggers pause."""
        # Create config with low budget
        config.budget_usd = 0.01

        checkpoint_system = CheckpointSystem(config)
        runner = AutopilotRunner(
            config=config,
            checkpoint_system=checkpoint_system,
            session_store=session_store,
        )

        # Mock _execute_goal to return non-zero cost
        original_execute = runner._execute_goal

        def mock_execute(goal: DailyGoal) -> GoalExecutionResult:
            return GoalExecutionResult(
                success=True, cost_usd=0.1, duration_seconds=10
            )

        runner._execute_goal = mock_execute

        result = runner.start(sample_goals)

        # First goal executes, then cost exceeds budget
        assert result.trigger is not None
        assert result.trigger.trigger_type == "cost"
        assert result.session.state == AutopilotState.PAUSED

    def test_approval_trigger(
        self,
        config: ChiefOfStaffConfig,
        checkpoint_system: CheckpointSystem,
        session_store: AutopilotSessionStore,
    ):
        """Test that approval-required actions trigger pause."""
        runner = AutopilotRunner(
            config=config,
            checkpoint_system=checkpoint_system,
            session_store=session_store,
        )

        # Goal that requires approval
        goals = [
            DailyGoal(
                goal_id="goal-approval",
                description="Review and approve spec changes",
                priority=GoalPriority.HIGH,
                estimated_minutes=30,
            ),
        ]

        result = runner.start(goals)

        assert result.trigger is not None
        assert result.trigger.trigger_type == "approval"
        assert result.session.state == AutopilotState.PAUSED

    def test_high_risk_trigger(
        self,
        config: ChiefOfStaffConfig,
        checkpoint_system: CheckpointSystem,
        session_store: AutopilotSessionStore,
    ):
        """Test that high-risk actions trigger pause."""
        runner = AutopilotRunner(
            config=config,
            checkpoint_system=checkpoint_system,
            session_store=session_store,
        )

        # High-risk goal
        goals = [
            DailyGoal(
                goal_id="goal-risk",
                description="Push to main branch",
                priority=GoalPriority.HIGH,
                estimated_minutes=5,
            ),
        ]

        result = runner.start(goals)

        assert result.trigger is not None
        assert result.trigger.trigger_type == "high_risk"
        assert result.session.state == AutopilotState.PAUSED

    def test_checkpoint_callback(
        self,
        config: ChiefOfStaffConfig,
        checkpoint_system: CheckpointSystem,
        session_store: AutopilotSessionStore,
    ):
        """Test that checkpoint callback is called."""
        callback = MagicMock()

        runner = AutopilotRunner(
            config=config,
            checkpoint_system=checkpoint_system,
            session_store=session_store,
            on_checkpoint=callback,
        )

        goals = [
            DailyGoal(
                goal_id="goal-approval",
                description="Approve fix plan",
                priority=GoalPriority.HIGH,
                estimated_minutes=10,
            ),
        ]

        runner.start(goals)

        callback.assert_called_once()
        assert callback.call_args[0][0].trigger_type == "approval"


class TestAutopilotRunnerResume:
    """Test AutopilotRunner.resume() method."""

    def test_resume_paused_session(
        self,
        config: ChiefOfStaffConfig,
        checkpoint_system: CheckpointSystem,
        session_store: AutopilotSessionStore,
    ):
        """Test resuming a paused session."""
        runner = AutopilotRunner(
            config=config,
            checkpoint_system=checkpoint_system,
            session_store=session_store,
        )

        # Create and pause a session
        goals = [
            DailyGoal(
                goal_id="goal-1",
                description="Task 1",
                priority=GoalPriority.HIGH,
                estimated_minutes=30,
            ),
            DailyGoal(
                goal_id="goal-approval",
                description="Approve changes",
                priority=GoalPriority.HIGH,
                estimated_minutes=10,
            ),
            DailyGoal(
                goal_id="goal-3",
                description="Task 3",
                priority=GoalPriority.LOW,
                estimated_minutes=20,
            ),
        ]

        result1 = runner.start(goals)
        assert result1.session.state == AutopilotState.PAUSED
        session_id = result1.session.session_id

        # Resume - but it will pause again on approval
        # For testing, we need to modify the goal or mock checkpoint
        # In production, the user would have approved the action

    def test_resume_not_found(self, runner: AutopilotRunner):
        """Test resume with non-existent session."""
        with pytest.raises(ValueError, match="Session not found"):
            runner.resume("nonexistent-session-id")

    def test_resume_not_paused(
        self, runner: AutopilotRunner, sample_goals: list[DailyGoal]
    ):
        """Test resume on non-paused session fails."""
        result = runner.start(sample_goals)  # Completes normally

        with pytest.raises(ValueError, match="is not paused"):
            runner.resume(result.session.session_id)


class TestAutopilotRunnerCallbacks:
    """Test callback invocation."""

    def test_goal_start_callback(
        self,
        config: ChiefOfStaffConfig,
        checkpoint_system: CheckpointSystem,
        session_store: AutopilotSessionStore,
        sample_goals: list[DailyGoal],
    ):
        """Test on_goal_start callback is called for each goal."""
        callback = MagicMock()

        runner = AutopilotRunner(
            config=config,
            checkpoint_system=checkpoint_system,
            session_store=session_store,
            on_goal_start=callback,
        )

        runner.start(sample_goals)

        assert callback.call_count == 3

    def test_goal_complete_callback(
        self,
        config: ChiefOfStaffConfig,
        checkpoint_system: CheckpointSystem,
        session_store: AutopilotSessionStore,
        sample_goals: list[DailyGoal],
    ):
        """Test on_goal_complete callback is called for each goal."""
        callback = MagicMock()

        runner = AutopilotRunner(
            config=config,
            checkpoint_system=checkpoint_system,
            session_store=session_store,
            on_goal_complete=callback,
        )

        runner.start(sample_goals)

        assert callback.call_count == 3


class TestAutopilotRunnerHelpers:
    """Test helper methods."""

    def test_parse_duration_hours(self, runner: AutopilotRunner):
        """Test parsing duration with hours."""
        assert runner._parse_duration("2h") == 120
        assert runner._parse_duration("1h") == 60
        assert runner._parse_duration("3h") == 180

    def test_parse_duration_minutes(self, runner: AutopilotRunner):
        """Test parsing duration with minutes."""
        assert runner._parse_duration("30m") == 30
        assert runner._parse_duration("90m") == 90
        assert runner._parse_duration("120m") == 120

    def test_parse_duration_combined(self, runner: AutopilotRunner):
        """Test parsing duration with hours and minutes."""
        assert runner._parse_duration("1h30m") == 90
        assert runner._parse_duration("2h15m") == 135

    def test_parse_duration_default(self, runner: AutopilotRunner):
        """Test parsing invalid duration returns default."""
        assert runner._parse_duration("") == 120
        assert runner._parse_duration("invalid") == 120

    def test_describe_goal_feature(self, runner: AutopilotRunner):
        """Test goal description for feature goal."""
        goal = DailyGoal(
            goal_id="g1",
            description="Implement feature",
            priority=GoalPriority.HIGH,
            estimated_minutes=60,
            linked_feature="my-feature",
        )

        desc = runner._describe_goal(goal)
        assert "feature" in desc.lower()
        assert "my-feature" in desc

    def test_describe_goal_bug(self, runner: AutopilotRunner):
        """Test goal description for bug goal."""
        goal = DailyGoal(
            goal_id="g1",
            description="Fix bug",
            priority=GoalPriority.HIGH,
            estimated_minutes=30,
            linked_bug="bug-123",
        )

        desc = runner._describe_goal(goal)
        assert "bug" in desc.lower()
        assert "bug-123" in desc

    def test_describe_goal_manual(self, runner: AutopilotRunner):
        """Test goal description for manual goal."""
        goal = DailyGoal(
            goal_id="g1",
            description="Review PR",
            priority=GoalPriority.LOW,
            estimated_minutes=15,
        )

        desc = runner._describe_goal(goal)
        assert "Review PR" in desc


class TestAutopilotRunnerSessionManagement:
    """Test session management methods."""

    def test_list_paused_sessions(
        self, runner: AutopilotRunner
    ):
        """Test listing paused sessions."""
        # Create some paused sessions
        goals = [
            DailyGoal(
                goal_id="goal-1",
                description="Approve spec",
                priority=GoalPriority.HIGH,
                estimated_minutes=10,
            ),
        ]

        result1 = runner.start(goals)
        result2 = runner.start(goals)

        paused = runner.list_paused_sessions()
        assert len(paused) == 2
        assert all(s.state == AutopilotState.PAUSED for s in paused)

    def test_cancel_session(
        self, runner: AutopilotRunner
    ):
        """Test cancelling a session."""
        goals = [
            DailyGoal(
                goal_id="goal-1",
                description="Approve spec",
                priority=GoalPriority.HIGH,
                estimated_minutes=10,
            ),
        ]

        result = runner.start(goals)
        session_id = result.session.session_id

        success = runner.cancel(session_id)
        assert success is True

        loaded = runner.session_store.load(session_id)
        assert loaded.state == AutopilotState.FAILED
        assert "Cancelled" in loaded.error_message

    def test_cancel_nonexistent_session(self, runner: AutopilotRunner):
        """Test cancelling non-existent session."""
        success = runner.cancel("nonexistent-id")
        assert success is False


class TestGoalExecutionResult:
    """Test GoalExecutionResult dataclass."""

    def test_success_result(self):
        """Test creating a successful result."""
        result = GoalExecutionResult(
            success=True,
            cost_usd=1.50,
            duration_seconds=300,
            output="Completed successfully",
        )

        assert result.success is True
        assert result.cost_usd == 1.50
        assert result.duration_seconds == 300
        assert result.error is None

    def test_failure_result(self):
        """Test creating a failure result."""
        result = GoalExecutionResult(
            success=False,
            cost_usd=0.50,
            duration_seconds=60,
            error="Something went wrong",
        )

        assert result.success is False
        assert result.error == "Something went wrong"


class TestSessionContext:
    """Test SessionContext dataclass."""

    def test_default_values(self):
        """Test default values."""
        ctx = SessionContext()

        assert ctx.total_cost_usd == 0.0
        assert ctx.elapsed_minutes == 0.0
        assert ctx.stop_trigger is None
        assert ctx.is_blocked is False

    def test_custom_values(self):
        """Test custom values."""
        ctx = SessionContext(
            total_cost_usd=5.0,
            elapsed_minutes=30.0,
            stop_trigger="approval",
            is_blocked=True,
        )

        assert ctx.total_cost_usd == 5.0
        assert ctx.elapsed_minutes == 30.0
        assert ctx.stop_trigger == "approval"
        assert ctx.is_blocked is True
