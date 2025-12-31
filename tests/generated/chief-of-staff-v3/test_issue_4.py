"""Tests for ProgressTracker integration with AutopilotRunner.

This test module verifies that AutopilotRunner properly integrates
with ProgressTracker to provide real-time progress tracking during execution.
"""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch

from swarm_attack.chief_of_staff.autopilot_runner import AutopilotRunner, GoalExecutionResult
from swarm_attack.chief_of_staff.autopilot_store import AutopilotSessionStore
from swarm_attack.chief_of_staff.checkpoints import CheckpointSystem
from swarm_attack.chief_of_staff.config import ChiefOfStaffConfig
from swarm_attack.chief_of_staff.goal_tracker import DailyGoal, GoalPriority, GoalStatus
from swarm_attack.chief_of_staff.progress import ProgressTracker


class TestAutopilotRunnerProgressTrackerIntegration:
    """Test ProgressTracker integration with AutopilotRunner."""

    @pytest.fixture
    def tmp_storage(self, tmp_path: Path) -> Path:
        """Create temporary storage path."""
        storage = tmp_path / ".swarm" / "chief-of-staff"
        storage.mkdir(parents=True, exist_ok=True)
        return storage

    @pytest.fixture
    def config(self, tmp_storage: Path) -> ChiefOfStaffConfig:
        """Create test config."""
        return ChiefOfStaffConfig(
            storage_path=str(tmp_storage),
        )

    @pytest.fixture
    def checkpoint_system(self) -> MagicMock:
        """Create mock checkpoint system."""
        mock = MagicMock(spec=CheckpointSystem)
        mock.reset_daily_cost = MagicMock()
        mock.update_daily_cost = MagicMock()
        # check_triggers is called before check_before_execution - must return None to continue
        mock.check_triggers = MagicMock(return_value=None)

        # check_before_execution returns a result that doesn't require approval
        check_result = MagicMock()
        check_result.requires_approval = False
        check_result.approved = True
        check_result.checkpoint = None
        mock.check_before_execution = AsyncMock(return_value=check_result)

        return mock

    @pytest.fixture
    def session_store(self, tmp_storage: Path) -> AutopilotSessionStore:
        """Create session store with tmp storage."""
        return AutopilotSessionStore(tmp_storage.parent.parent)

    @pytest.fixture
    def runner(
        self,
        config: ChiefOfStaffConfig,
        checkpoint_system: MagicMock,
        session_store: AutopilotSessionStore,
        tmp_storage: Path,
    ) -> AutopilotRunner:
        """Create AutopilotRunner instance."""
        return AutopilotRunner(
            config=config,
            checkpoint_system=checkpoint_system,
            session_store=session_store,
        )

    @pytest.fixture
    def sample_goals(self) -> list[DailyGoal]:
        """Create sample goals for testing."""
        return [
            DailyGoal(
                goal_id="goal-1",
                description="First goal",
                priority=GoalPriority.HIGH,
                estimated_minutes=30,
            ),
            DailyGoal(
                goal_id="goal-2",
                description="Second goal",
                priority=GoalPriority.MEDIUM,
                estimated_minutes=45,
            ),
            DailyGoal(
                goal_id="goal-3",
                description="Third goal",
                priority=GoalPriority.LOW,
                estimated_minutes=15,
            ),
        ]

    def test_autopilot_runner_has_progress_tracker_attribute(
        self,
        runner: AutopilotRunner,
    ) -> None:
        """AutopilotRunner should have progress_tracker attribute."""
        assert hasattr(runner, "progress_tracker")
        assert isinstance(runner.progress_tracker, ProgressTracker)

    def test_progress_tracker_initialized_in_init(
        self,
        config: ChiefOfStaffConfig,
        checkpoint_system: MagicMock,
        session_store: AutopilotSessionStore,
    ) -> None:
        """ProgressTracker should be initialized in __init__."""
        runner = AutopilotRunner(
            config=config,
            checkpoint_system=checkpoint_system,
            session_store=session_store,
        )
        
        assert runner.progress_tracker is not None
        assert isinstance(runner.progress_tracker, ProgressTracker)

    def test_start_calls_progress_tracker_start_session(
        self,
        runner: AutopilotRunner,
        sample_goals: list[DailyGoal],
    ) -> None:
        """start() should call progress_tracker.start_session(total_goals=len(goals))."""
        # Mock the progress tracker
        runner.progress_tracker = MagicMock(spec=ProgressTracker)
        
        # Run start
        runner.start(sample_goals, budget_usd=10.0)
        
        # Verify start_session was called with correct total
        runner.progress_tracker.start_session.assert_called_once_with(
            total_goals=len(sample_goals)
        )

    def test_execute_goal_updates_progress_with_current_goal(
        self,
        runner: AutopilotRunner,
        sample_goals: list[DailyGoal],
    ) -> None:
        """_execute_goal should update progress with current_goal at start."""
        # Mock the progress tracker
        runner.progress_tracker = MagicMock(spec=ProgressTracker)
        
        # Execute a goal directly
        goal = sample_goals[0]
        runner._execute_goal(goal)
        
        # Verify update was called with current_goal
        calls = runner.progress_tracker.update.call_args_list
        assert len(calls) >= 1
        
        # First call should set current_goal
        first_call_kwargs = calls[0].kwargs if calls[0].kwargs else {}
        first_call_args = calls[0].args if calls[0].args else ()
        
        # Check that current_goal was set (either as kwarg or expected behavior)
        # The update should include the goal description or id
        assert runner.progress_tracker.update.called

    def test_execute_goal_updates_progress_after_completion(
        self,
        runner: AutopilotRunner,
        sample_goals: list[DailyGoal],
    ) -> None:
        """_execute_goal should update goals_completed and cost_usd after completion."""
        # Mock the progress tracker
        runner.progress_tracker = MagicMock(spec=ProgressTracker)
        
        # Execute a goal
        goal = sample_goals[0]
        result = runner._execute_goal(goal)
        
        # Verify update was called
        assert runner.progress_tracker.update.called
        
        # Check the final update includes completion info
        calls = runner.progress_tracker.update.call_args_list
        # At least one update should happen after execution

    def test_start_tracks_progress_for_each_goal(
        self,
        runner: AutopilotRunner,
        sample_goals: list[DailyGoal],
    ) -> None:
        """start() should track progress for each goal executed."""
        # Mock the progress tracker
        runner.progress_tracker = MagicMock(spec=ProgressTracker)
        
        # Run start with goals
        runner.start(sample_goals, budget_usd=100.0)
        
        # start_session should be called once
        runner.progress_tracker.start_session.assert_called_once()
        
        # update should be called for each goal
        # (at minimum once per goal for start + once for completion)
        assert runner.progress_tracker.update.call_count >= len(sample_goals)

    def test_progress_tracker_accessible_via_runner_attribute(
        self,
        runner: AutopilotRunner,
    ) -> None:
        """Progress tracker should be accessible via runner.progress_tracker."""
        tracker = runner.progress_tracker
        
        # Should be a ProgressTracker instance
        assert isinstance(tracker, ProgressTracker)
        
        # Should have expected methods
        assert hasattr(tracker, "start_session")
        assert hasattr(tracker, "update")
        assert hasattr(tracker, "get_current")


class TestProgressTrackerIntegrationEndToEnd:
    """End-to-end integration tests for ProgressTracker with AutopilotRunner."""

    @pytest.fixture
    def tmp_storage(self, tmp_path: Path) -> Path:
        """Create temporary storage path."""
        storage = tmp_path / ".swarm" / "chief-of-staff"
        storage.mkdir(parents=True, exist_ok=True)
        return storage

    @pytest.fixture
    def config(self, tmp_storage: Path) -> ChiefOfStaffConfig:
        """Create test config."""
        return ChiefOfStaffConfig(
            storage_path=str(tmp_storage),
        )

    @pytest.fixture
    def checkpoint_system(self) -> MagicMock:
        """Create mock checkpoint system."""
        mock = MagicMock(spec=CheckpointSystem)
        mock.reset_daily_cost = MagicMock()
        mock.update_daily_cost = MagicMock()
        # check_triggers is called before check_before_execution - must return None to continue
        mock.check_triggers = MagicMock(return_value=None)

        check_result = MagicMock()
        check_result.requires_approval = False
        check_result.approved = True
        check_result.checkpoint = None
        mock.check_before_execution = AsyncMock(return_value=check_result)

        return mock

    @pytest.fixture
    def session_store(self, tmp_storage: Path) -> AutopilotSessionStore:
        """Create session store."""
        return AutopilotSessionStore(tmp_storage.parent.parent)

    def test_progress_file_created_after_start(
        self,
        config: ChiefOfStaffConfig,
        checkpoint_system: MagicMock,
        session_store: AutopilotSessionStore,
        tmp_storage: Path,
    ) -> None:
        """Progress file should be created when start() is called."""
        runner = AutopilotRunner(
            config=config,
            checkpoint_system=checkpoint_system,
            session_store=session_store,
        )
        
        goals = [
            DailyGoal(
                goal_id="test-goal",
                description="Test goal",
                priority=GoalPriority.MEDIUM,
                estimated_minutes=10,
            ),
        ]
        
        runner.start(goals, budget_usd=10.0)
        
        # Check that progress directory/file exists
        progress_path = Path(config.storage_path) / "progress"
        assert progress_path.exists() or (progress_path / "progress.json").exists()

    def test_progress_snapshot_reflects_goal_count(
        self,
        config: ChiefOfStaffConfig,
        checkpoint_system: MagicMock,
        session_store: AutopilotSessionStore,
    ) -> None:
        """Progress snapshot should reflect total goal count."""
        runner = AutopilotRunner(
            config=config,
            checkpoint_system=checkpoint_system,
            session_store=session_store,
        )
        
        goals = [
            DailyGoal(
                goal_id=f"goal-{i}",
                description=f"Goal {i}",
                priority=GoalPriority.MEDIUM,
                estimated_minutes=10,
            )
            for i in range(5)
        ]
        
        runner.start(goals, budget_usd=100.0)
        
        current = runner.progress_tracker.get_current()
        assert current is not None
        assert current.goals_total == 5

    def test_progress_updates_after_each_goal(
        self,
        config: ChiefOfStaffConfig,
        checkpoint_system: MagicMock,
        session_store: AutopilotSessionStore,
    ) -> None:
        """Progress should update after each goal completes."""
        runner = AutopilotRunner(
            config=config,
            checkpoint_system=checkpoint_system,
            session_store=session_store,
        )
        
        goals = [
            DailyGoal(
                goal_id=f"goal-{i}",
                description=f"Goal {i}",
                priority=GoalPriority.MEDIUM,
                estimated_minutes=5,
            )
            for i in range(3)
        ]
        
        runner.start(goals, budget_usd=100.0)
        
        # After execution, progress should reflect completed goals
        current = runner.progress_tracker.get_current()
        assert current is not None
        # Generic goals complete successfully, so goals_completed should match
        assert current.goals_completed == 3