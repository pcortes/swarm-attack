"""Tests for RecoveryManager integration into AutopilotRunner._execute_goal().

This test file verifies that the AutopilotRunner properly integrates with
RecoveryManager for hierarchical recovery during goal execution, including:
- AutopilotRunner instantiates or receives RecoveryManager
- _execute_goal() wraps orchestrator calls with execute_with_recovery()
- Recovery applies to both feature and bug goal types
- EpisodeStore passed to RecoveryManager for logging
- Existing behavior preserved when recovery succeeds on first try
- HICCUP checkpoints created via existing checkpoint system
- Integration tests verify recovery triggers during goal execution
- Integration tests verify checkpoint creation on escalation
"""

import asyncio
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

import pytest

from swarm_attack.chief_of_staff.autopilot_runner import (
    AutopilotRunner,
    GoalExecutionResult,
    AutopilotRunResult,
)
from swarm_attack.chief_of_staff.recovery import (
    RecoveryManager,
    RetryStrategy,
    ErrorCategory,
    classify_error,
)
from swarm_attack.chief_of_staff.episodes import Episode, EpisodeStore
from swarm_attack.chief_of_staff.checkpoints import (
    CheckpointSystem,
    CheckpointStore,
    CheckpointTrigger,
    Checkpoint,
    CheckpointResult,
)
from swarm_attack.chief_of_staff.config import ChiefOfStaffConfig
from swarm_attack.chief_of_staff.autopilot_store import AutopilotSessionStore
from swarm_attack.chief_of_staff.goal_tracker import DailyGoal, GoalPriority, GoalStatus
from swarm_attack.errors import LLMError, LLMErrorType


def make_goal(
    goal_id: str = "test-goal-1",
    description: str = "Test goal",
    linked_feature: Optional[str] = None,
    linked_bug: Optional[str] = None,
    linked_issue: Optional[int] = None,
) -> DailyGoal:
    """Create a DailyGoal for testing."""
    return DailyGoal(
        goal_id=goal_id,
        description=description,
        priority=GoalPriority.MEDIUM,
        estimated_minutes=30,
        status=GoalStatus.PENDING,
        linked_feature=linked_feature,
        linked_bug=linked_bug,
        linked_issue=linked_issue,
    )


class MockOrchestrator:
    """Mock Orchestrator for testing."""
    
    def __init__(self, run_issue_result=None, run_spec_result=None, should_raise=None):
        self._run_issue_result = run_issue_result
        self._run_spec_result = run_spec_result
        self._should_raise = should_raise
        self.run_issue_session_calls = []
        self.run_spec_pipeline_calls = []
    
    def run_issue_session(self, feature_id: str, issue_number: int):
        self.run_issue_session_calls.append((feature_id, issue_number))
        if self._should_raise:
            raise self._should_raise
        return self._run_issue_result or MagicMock(status="success", cost_usd=0.10, message="")
    
    def run_spec_pipeline(self, spec_id: str):
        self.run_spec_pipeline_calls.append(spec_id)
        if self._should_raise:
            raise self._should_raise
        return self._run_spec_result or MagicMock(status="success", total_cost_usd=0.05, message="")


class MockBugOrchestrator:
    """Mock BugOrchestrator for testing."""
    
    def __init__(self, fix_result=None, should_raise=None):
        self._fix_result = fix_result
        self._should_raise = should_raise
        self.fix_calls = []
    
    def fix(self, bug_id: str):
        self.fix_calls.append(bug_id)
        if self._should_raise:
            raise self._should_raise
        if self._fix_result:
            return self._fix_result
        result = MagicMock()
        result.success = True
        result.phase = MagicMock(value="fixed")
        result.cost_usd = 0.08
        result.message = ""
        return result


class TestAutopilotRunnerHasRecoveryManager:
    """Test that AutopilotRunner can instantiate or receive RecoveryManager."""

    def test_runner_accepts_recovery_manager(self):
        """AutopilotRunner accepts a RecoveryManager in constructor."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = ChiefOfStaffConfig()
            checkpoint_system = CheckpointSystem(config=config)
            session_store = AutopilotSessionStore(base_path=Path(tmpdir))
            recovery_manager = RecoveryManager(checkpoint_system)
            
            runner = AutopilotRunner(
                config=config,
                checkpoint_system=checkpoint_system,
                session_store=session_store,
                recovery_manager=recovery_manager,
            )
            
            assert runner.recovery_manager is recovery_manager

    def test_runner_creates_recovery_manager_if_not_provided(self):
        """AutopilotRunner creates RecoveryManager if not provided."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = ChiefOfStaffConfig()
            checkpoint_system = CheckpointSystem(config=config)
            session_store = AutopilotSessionStore(base_path=Path(tmpdir))
            
            runner = AutopilotRunner(
                config=config,
                checkpoint_system=checkpoint_system,
                session_store=session_store,
            )
            
            # RecoveryManager should be created internally
            assert runner.recovery_manager is not None
            assert isinstance(runner.recovery_manager, RecoveryManager)

    def test_runner_accepts_episode_store(self):
        """AutopilotRunner accepts an EpisodeStore for recovery logging."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = ChiefOfStaffConfig()
            checkpoint_system = CheckpointSystem(config=config)
            session_store = AutopilotSessionStore(base_path=Path(tmpdir))
            episode_store = EpisodeStore(base_path=Path(tmpdir) / "episodes")
            
            runner = AutopilotRunner(
                config=config,
                checkpoint_system=checkpoint_system,
                session_store=session_store,
                episode_store=episode_store,
            )
            
            assert runner.episode_store is episode_store


class TestExecuteGoalWithRecovery:
    """Test that _execute_goal() wraps orchestrator calls with execute_with_recovery()."""

    def test_execute_goal_uses_recovery_manager_for_feature(self):
        """Feature goal execution goes through RecoveryManager."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = ChiefOfStaffConfig()
            checkpoint_system = CheckpointSystem(config=config)
            session_store = AutopilotSessionStore(base_path=Path(tmpdir))
            orchestrator = MockOrchestrator()
            
            runner = AutopilotRunner(
                config=config,
                checkpoint_system=checkpoint_system,
                session_store=session_store,
                orchestrator=orchestrator,
            )
            
            goal = make_goal(
                linked_feature="test-feature",
                linked_issue=1,
            )
            
            result = runner._execute_goal(goal)
            
            assert result.success is True
            assert len(orchestrator.run_issue_session_calls) == 1

    def test_execute_goal_uses_recovery_manager_for_bug(self):
        """Bug goal execution goes through RecoveryManager."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = ChiefOfStaffConfig()
            checkpoint_system = CheckpointSystem(config=config)
            session_store = AutopilotSessionStore(base_path=Path(tmpdir))
            bug_orchestrator = MockBugOrchestrator()
            
            runner = AutopilotRunner(
                config=config,
                checkpoint_system=checkpoint_system,
                session_store=session_store,
                bug_orchestrator=bug_orchestrator,
            )
            
            goal = make_goal(linked_bug="test-bug-1")
            
            result = runner._execute_goal(goal)
            
            assert result.success is True
            assert len(bug_orchestrator.fix_calls) == 1


class TestRecoveryAppliesAllGoalTypes:
    """Test that recovery applies to both feature and bug goal types."""

    def test_feature_goal_with_transient_error_retries(self):
        """Feature goal with transient error is retried."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = ChiefOfStaffConfig()
            checkpoint_system = CheckpointSystem(config=config)
            session_store = AutopilotSessionStore(base_path=Path(tmpdir))
            
            # First call fails, second succeeds
            call_count = [0]
            
            def run_issue_session(feature_id: str, issue_number: int):
                call_count[0] += 1
                if call_count[0] < 2:
                    raise LLMError("timeout", error_type=LLMErrorType.TIMEOUT)
                return MagicMock(status="success", cost_usd=0.10, message="")
            
            orchestrator = MagicMock()
            orchestrator.run_issue_session = run_issue_session
            
            runner = AutopilotRunner(
                config=config,
                checkpoint_system=checkpoint_system,
                session_store=session_store,
                orchestrator=orchestrator,
            )
            # Use 0 backoff for faster tests
            runner.recovery_manager.backoff_base_seconds = 0
            runner.recovery_manager.backoff_multiplier = 1
            
            goal = make_goal(linked_feature="test-feature", linked_issue=1)
            result = runner._execute_goal(goal)
            
            # Should succeed after retry
            assert result.success is True
            assert call_count[0] == 2

    def test_bug_goal_with_transient_error_retries(self):
        """Bug goal with transient error is retried."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = ChiefOfStaffConfig()
            checkpoint_system = CheckpointSystem(config=config)
            session_store = AutopilotSessionStore(base_path=Path(tmpdir))
            
            call_count = [0]
            
            def fix(bug_id: str):
                call_count[0] += 1
                if call_count[0] < 2:
                    raise LLMError("rate limit", error_type=LLMErrorType.RATE_LIMIT)
                result = MagicMock()
                result.success = True
                result.phase = MagicMock(value="fixed")
                result.cost_usd = 0.08
                result.message = ""
                return result
            
            bug_orchestrator = MagicMock()
            bug_orchestrator.fix = fix
            
            runner = AutopilotRunner(
                config=config,
                checkpoint_system=checkpoint_system,
                session_store=session_store,
                bug_orchestrator=bug_orchestrator,
            )
            runner.recovery_manager.backoff_base_seconds = 0
            runner.recovery_manager.backoff_multiplier = 1
            
            goal = make_goal(linked_bug="test-bug")
            result = runner._execute_goal(goal)
            
            assert result.success is True
            assert call_count[0] == 2


class TestEpisodeStorePassedToRecoveryManager:
    """Test that EpisodeStore is passed to RecoveryManager for logging."""

    def test_episode_logged_during_goal_execution(self):
        """Episodes are logged when EpisodeStore is provided."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = ChiefOfStaffConfig()
            checkpoint_system = CheckpointSystem(config=config)
            session_store = AutopilotSessionStore(base_path=Path(tmpdir))
            episode_store = EpisodeStore(base_path=Path(tmpdir) / "episodes")
            orchestrator = MockOrchestrator()
            
            runner = AutopilotRunner(
                config=config,
                checkpoint_system=checkpoint_system,
                session_store=session_store,
                orchestrator=orchestrator,
                episode_store=episode_store,
            )
            
            goal = make_goal(linked_feature="test-feature", linked_issue=1)
            result = runner._execute_goal(goal)
            
            assert result.success is True
            episodes = episode_store.load_all()
            assert len(episodes) >= 1
            assert episodes[0].goal_id == goal.goal_id

    def test_episode_not_logged_when_store_not_provided(self):
        """No error when EpisodeStore is not provided."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = ChiefOfStaffConfig()
            checkpoint_system = CheckpointSystem(config=config)
            session_store = AutopilotSessionStore(base_path=Path(tmpdir))
            orchestrator = MockOrchestrator()
            
            runner = AutopilotRunner(
                config=config,
                checkpoint_system=checkpoint_system,
                session_store=session_store,
                orchestrator=orchestrator,
                episode_store=None,
            )
            
            goal = make_goal(linked_feature="test-feature", linked_issue=1)
            result = runner._execute_goal(goal)
            
            # Should work without errors
            assert result.success is True


class TestExistingBehaviorPreserved:
    """Test that existing behavior is preserved when recovery succeeds on first try."""

    def test_first_try_success_returns_correct_result(self):
        """First successful attempt returns expected GoalExecutionResult."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = ChiefOfStaffConfig()
            checkpoint_system = CheckpointSystem(config=config)
            session_store = AutopilotSessionStore(base_path=Path(tmpdir))
            orchestrator = MockOrchestrator(
                run_issue_result=MagicMock(status="success", cost_usd=0.15, message="Completed")
            )
            
            runner = AutopilotRunner(
                config=config,
                checkpoint_system=checkpoint_system,
                session_store=session_store,
                orchestrator=orchestrator,
            )
            
            goal = make_goal(linked_feature="test-feature", linked_issue=1)
            result = runner._execute_goal(goal)
            
            assert result.success is True
            assert result.cost_usd == 0.15

    def test_generic_goal_still_works(self):
        """Generic goals (no linked artifact) still work."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = ChiefOfStaffConfig()
            checkpoint_system = CheckpointSystem(config=config)
            session_store = AutopilotSessionStore(base_path=Path(tmpdir))
            
            runner = AutopilotRunner(
                config=config,
                checkpoint_system=checkpoint_system,
                session_store=session_store,
            )
            
            goal = make_goal()  # No linked feature/bug
            result = runner._execute_goal(goal)
            
            assert result.success is True
            assert result.cost_usd == 0.0
            assert "Stub execution" in result.output


class TestHiccupCheckpointCreation:
    """Test that HICCUP checkpoints are created via existing checkpoint system."""

    def test_hiccup_checkpoint_created_on_fatal_error(self):
        """HICCUP checkpoint is created when fatal error occurs."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = ChiefOfStaffConfig()
            checkpoint_store = CheckpointStore(base_path=Path(tmpdir) / "checkpoints")
            checkpoint_system = CheckpointSystem(config=config, store=checkpoint_store)
            session_store = AutopilotSessionStore(base_path=Path(tmpdir))
            
            orchestrator = MockOrchestrator(
                should_raise=LLMError("auth failed", error_type=LLMErrorType.AUTH_REQUIRED)
            )
            
            runner = AutopilotRunner(
                config=config,
                checkpoint_system=checkpoint_system,
                session_store=session_store,
                orchestrator=orchestrator,
            )
            
            goal = make_goal(linked_feature="test-feature", linked_issue=1)
            result = runner._execute_goal(goal)
            
            assert result.success is False
            assert goal.is_hiccup is True
            
            # Verify checkpoint was created
            pending = asyncio.run(checkpoint_store.list_pending())
            assert len(pending) >= 1
            hiccup_checkpoints = [c for c in pending if c.trigger == CheckpointTrigger.HICCUP]
            assert len(hiccup_checkpoints) >= 1

    def test_hiccup_checkpoint_created_after_retries_exhausted(self):
        """HICCUP checkpoint is created when transient retries are exhausted."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = ChiefOfStaffConfig()
            checkpoint_store = CheckpointStore(base_path=Path(tmpdir) / "checkpoints")
            checkpoint_system = CheckpointSystem(config=config, store=checkpoint_store)
            session_store = AutopilotSessionStore(base_path=Path(tmpdir))
            
            # Always fail with transient error
            orchestrator = MockOrchestrator(
                should_raise=LLMError("timeout", error_type=LLMErrorType.TIMEOUT)
            )
            
            runner = AutopilotRunner(
                config=config,
                checkpoint_system=checkpoint_system,
                session_store=session_store,
                orchestrator=orchestrator,
            )
            runner.recovery_manager.backoff_base_seconds = 0
            runner.recovery_manager.backoff_multiplier = 1
            
            goal = make_goal(linked_feature="test-feature", linked_issue=1)
            result = runner._execute_goal(goal)
            
            assert result.success is False
            
            # Check checkpoint was created
            pending = asyncio.run(checkpoint_store.list_pending())
            hiccup_checkpoints = [c for c in pending if c.trigger == CheckpointTrigger.HICCUP]
            assert len(hiccup_checkpoints) >= 1


class TestRecoveryTriggeredDuringGoalExecution:
    """Integration tests verifying recovery triggers during goal execution."""

    def test_recovery_triggers_for_rate_limit_error(self):
        """Recovery is triggered for rate limit errors."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = ChiefOfStaffConfig()
            checkpoint_system = CheckpointSystem(config=config)
            session_store = AutopilotSessionStore(base_path=Path(tmpdir))
            
            call_count = [0]
            
            def run_issue_session(feature_id: str, issue_number: int):
                call_count[0] += 1
                if call_count[0] < 3:
                    raise LLMError("rate limited", error_type=LLMErrorType.RATE_LIMIT)
                return MagicMock(status="success", cost_usd=0.10, message="")
            
            orchestrator = MagicMock()
            orchestrator.run_issue_session = run_issue_session
            
            runner = AutopilotRunner(
                config=config,
                checkpoint_system=checkpoint_system,
                session_store=session_store,
                orchestrator=orchestrator,
            )
            runner.recovery_manager.backoff_base_seconds = 0
            runner.recovery_manager.backoff_multiplier = 1
            
            goal = make_goal(linked_feature="test-feature", linked_issue=1)
            result = runner._execute_goal(goal)
            
            # Should succeed after 2 retries
            assert result.success is True
            assert call_count[0] == 3

    def test_recovery_triggers_for_server_error(self):
        """Recovery is triggered for server errors."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = ChiefOfStaffConfig()
            checkpoint_system = CheckpointSystem(config=config)
            session_store = AutopilotSessionStore(base_path=Path(tmpdir))
            
            call_count = [0]
            
            def fix(bug_id: str):
                call_count[0] += 1
                if call_count[0] < 2:
                    raise LLMError("server error", error_type=LLMErrorType.SERVER_ERROR)
                result = MagicMock()
                result.success = True
                result.phase = MagicMock(value="fixed")
                result.cost_usd = 0.08
                result.message = ""
                return result
            
            bug_orchestrator = MagicMock()
            bug_orchestrator.fix = fix
            
            runner = AutopilotRunner(
                config=config,
                checkpoint_system=checkpoint_system,
                session_store=session_store,
                bug_orchestrator=bug_orchestrator,
            )
            runner.recovery_manager.backoff_base_seconds = 0
            runner.recovery_manager.backoff_multiplier = 1
            
            goal = make_goal(linked_bug="test-bug")
            result = runner._execute_goal(goal)
            
            assert result.success is True
            assert call_count[0] == 2


class TestCheckpointCreationOnEscalation:
    """Integration tests verifying checkpoint creation on escalation."""

    def test_checkpoint_has_goal_context(self):
        """HICCUP checkpoint includes goal context."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = ChiefOfStaffConfig()
            checkpoint_store = CheckpointStore(base_path=Path(tmpdir) / "checkpoints")
            checkpoint_system = CheckpointSystem(config=config, store=checkpoint_store)
            session_store = AutopilotSessionStore(base_path=Path(tmpdir))
            
            orchestrator = MockOrchestrator(
                should_raise=LLMError("cli not found", error_type=LLMErrorType.CLI_NOT_FOUND)
            )
            
            runner = AutopilotRunner(
                config=config,
                checkpoint_system=checkpoint_system,
                session_store=session_store,
                orchestrator=orchestrator,
            )
            
            goal = make_goal(
                goal_id="my-special-goal",
                description="Implement feature X",
                linked_feature="feature-x",
                linked_issue=5,
            )
            result = runner._execute_goal(goal)
            
            assert result.success is False
            
            pending = asyncio.run(checkpoint_store.list_pending())
            hiccup = next((c for c in pending if c.trigger == CheckpointTrigger.HICCUP), None)
            assert hiccup is not None
            assert hiccup.goal_id == "my-special-goal"
            assert "Implement feature X" in hiccup.context

    def test_checkpoint_has_error_details(self):
        """HICCUP checkpoint includes error details."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = ChiefOfStaffConfig()
            checkpoint_store = CheckpointStore(base_path=Path(tmpdir) / "checkpoints")
            checkpoint_system = CheckpointSystem(config=config, store=checkpoint_store)
            session_store = AutopilotSessionStore(base_path=Path(tmpdir))
            
            orchestrator = MockOrchestrator(
                should_raise=LLMError("Authentication token expired", error_type=LLMErrorType.AUTH_EXPIRED)
            )
            
            runner = AutopilotRunner(
                config=config,
                checkpoint_system=checkpoint_system,
                session_store=session_store,
                orchestrator=orchestrator,
            )
            
            goal = make_goal(linked_feature="test-feature", linked_issue=1)
            result = runner._execute_goal(goal)
            
            pending = asyncio.run(checkpoint_store.list_pending())
            hiccup = next((c for c in pending if c.trigger == CheckpointTrigger.HICCUP), None)
            assert hiccup is not None
            assert "Authentication token expired" in hiccup.context

    def test_checkpoint_has_recovery_options(self):
        """HICCUP checkpoint has standard recovery options."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = ChiefOfStaffConfig()
            checkpoint_store = CheckpointStore(base_path=Path(tmpdir) / "checkpoints")
            checkpoint_system = CheckpointSystem(config=config, store=checkpoint_store)
            session_store = AutopilotSessionStore(base_path=Path(tmpdir))
            
            orchestrator = MockOrchestrator(
                should_raise=LLMError("auth error", error_type=LLMErrorType.AUTH_REQUIRED)
            )
            
            runner = AutopilotRunner(
                config=config,
                checkpoint_system=checkpoint_system,
                session_store=session_store,
                orchestrator=orchestrator,
            )
            
            goal = make_goal(linked_feature="test-feature", linked_issue=1)
            runner._execute_goal(goal)
            
            pending = asyncio.run(checkpoint_store.list_pending())
            hiccup = next((c for c in pending if c.trigger == CheckpointTrigger.HICCUP), None)
            assert hiccup is not None
            
            option_labels = [o.label for o in hiccup.options]
            assert "Skip this goal" in option_labels
            assert "Retry with modifications" in option_labels
            assert "Handle manually" in option_labels


class TestGoalErrorCountUpdated:
    """Test that goal.error_count is updated correctly during recovery."""

    def test_error_count_incremented_on_each_failure(self):
        """goal.error_count is incremented once per failed execution (not per retry).

        AutopilotRunner consolidates retries into a single error count from the
        user's perspective - one execution attempt = one potential error.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            config = ChiefOfStaffConfig()
            checkpoint_system = CheckpointSystem(config=config)
            session_store = AutopilotSessionStore(base_path=Path(tmpdir))

            orchestrator = MockOrchestrator(
                should_raise=LLMError("timeout", error_type=LLMErrorType.TIMEOUT)
            )

            runner = AutopilotRunner(
                config=config,
                checkpoint_system=checkpoint_system,
                session_store=session_store,
                orchestrator=orchestrator,
            )
            runner.recovery_manager.backoff_base_seconds = 0
            runner.recovery_manager.backoff_multiplier = 1

            goal = make_goal(linked_feature="test-feature", linked_issue=1)
            assert goal.error_count == 0

            runner._execute_goal(goal)

            # One failed execution = one error increment (retries are consolidated)
            assert goal.error_count == 1

    def test_error_count_correct_after_eventual_success(self):
        """goal.error_count is not incremented on eventual success.

        AutopilotRunner resets error_count to original on success - from the
        user's perspective, a successful execution means no error occurred.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            config = ChiefOfStaffConfig()
            checkpoint_system = CheckpointSystem(config=config)
            session_store = AutopilotSessionStore(base_path=Path(tmpdir))

            call_count = [0]

            def run_issue_session(feature_id: str, issue_number: int):
                call_count[0] += 1
                if call_count[0] < 3:
                    raise LLMError("timeout", error_type=LLMErrorType.TIMEOUT)
                return MagicMock(status="success", cost_usd=0.10, message="")

            orchestrator = MagicMock()
            orchestrator.run_issue_session = run_issue_session

            runner = AutopilotRunner(
                config=config,
                checkpoint_system=checkpoint_system,
                session_store=session_store,
                orchestrator=orchestrator,
            )
            runner.recovery_manager.backoff_base_seconds = 0
            runner.recovery_manager.backoff_multiplier = 1

            goal = make_goal(linked_feature="test-feature", linked_issue=1)
            result = runner._execute_goal(goal)

            assert result.success is True
            # Success resets error_count - no error from user's perspective
            assert goal.error_count == 0