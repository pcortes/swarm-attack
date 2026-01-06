"""Unit tests for EpisodeLogger.

Tests for:
- Action logging (tool calls, edits, commands)
- Outcome tracking (success, failure, partial)
- Context snapshot capture
- Recovery attempt tracking
- Episode lifecycle management
- Serialization/deserialization

TDD Protocol: RED PHASE - These tests should fail initially.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional
from unittest.mock import MagicMock

import pytest


# =============================================================================
# Import Tests - Verify module structure
# =============================================================================


class TestModuleImports:
    """Test that required classes can be imported."""

    def test_import_episode_logger(self):
        """Test EpisodeLogger class can be imported."""
        from swarm_attack.learning.episode_logger import EpisodeLogger
        assert EpisodeLogger is not None

    def test_import_episode(self):
        """Test Episode class can be imported."""
        from swarm_attack.learning.episode_logger import Episode
        assert Episode is not None

    def test_import_action(self):
        """Test Action class can be imported."""
        from swarm_attack.learning.episode_logger import Action
        assert Action is not None

    def test_import_outcome(self):
        """Test Outcome enum can be imported."""
        from swarm_attack.learning.episode_logger import Outcome
        assert Outcome is not None

    def test_import_context_snapshot(self):
        """Test ContextSnapshot class can be imported."""
        from swarm_attack.learning.episode_logger import ContextSnapshot
        assert ContextSnapshot is not None

    def test_import_recovery_attempt(self):
        """Test RecoveryAttempt class can be imported."""
        from swarm_attack.learning.episode_logger import RecoveryAttempt
        assert RecoveryAttempt is not None


# =============================================================================
# Outcome Enum Tests
# =============================================================================


class TestOutcomeEnum:
    """Tests for Outcome enum."""

    def test_outcome_success(self):
        """Test Outcome.SUCCESS exists."""
        from swarm_attack.learning.episode_logger import Outcome

        assert Outcome.SUCCESS is not None
        assert Outcome.SUCCESS.value == "success"

    def test_outcome_failure(self):
        """Test Outcome.FAILURE exists."""
        from swarm_attack.learning.episode_logger import Outcome

        assert Outcome.FAILURE is not None
        assert Outcome.FAILURE.value == "failure"

    def test_outcome_partial(self):
        """Test Outcome.PARTIAL exists."""
        from swarm_attack.learning.episode_logger import Outcome

        assert Outcome.PARTIAL is not None
        assert Outcome.PARTIAL.value == "partial"

    def test_outcome_pending(self):
        """Test Outcome.PENDING exists for in-progress actions."""
        from swarm_attack.learning.episode_logger import Outcome

        assert Outcome.PENDING is not None
        assert Outcome.PENDING.value == "pending"


# =============================================================================
# Action Data Class Tests
# =============================================================================


class TestActionDataClass:
    """Tests for Action data class."""

    def test_action_creation(self):
        """Test creating an Action with required fields."""
        from swarm_attack.learning.episode_logger import Action, Outcome

        action = Action(
            action_id="act-001",
            action_type="tool_call",
            tool_name="Read",
            timestamp=datetime.now().isoformat(),
        )

        assert action.action_id == "act-001"
        assert action.action_type == "tool_call"
        assert action.tool_name == "Read"

    def test_action_with_all_fields(self):
        """Test creating Action with all fields."""
        from swarm_attack.learning.episode_logger import Action, Outcome

        action = Action(
            action_id="act-002",
            action_type="edit",
            tool_name="Edit",
            timestamp=datetime.now().isoformat(),
            input_data={"file": "test.py", "old": "foo", "new": "bar"},
            output_data={"success": True, "lines_changed": 1},
            outcome=Outcome.SUCCESS,
            duration_ms=150,
            error_message=None,
        )

        assert action.input_data == {"file": "test.py", "old": "foo", "new": "bar"}
        assert action.outcome == Outcome.SUCCESS
        assert action.duration_ms == 150

    def test_action_to_dict(self):
        """Test Action serialization to dict."""
        from swarm_attack.learning.episode_logger import Action, Outcome

        action = Action(
            action_id="act-003",
            action_type="tool_call",
            tool_name="Bash",
            timestamp="2025-01-06T10:00:00",
            outcome=Outcome.SUCCESS,
        )

        data = action.to_dict()

        assert isinstance(data, dict)
        assert data["action_id"] == "act-003"
        assert data["outcome"] == "success"

    def test_action_from_dict(self):
        """Test Action deserialization from dict."""
        from swarm_attack.learning.episode_logger import Action, Outcome

        data = {
            "action_id": "act-004",
            "action_type": "tool_call",
            "tool_name": "Glob",
            "timestamp": "2025-01-06T10:00:00",
            "outcome": "failure",
            "error_message": "File not found",
        }

        action = Action.from_dict(data)

        assert action.action_id == "act-004"
        assert action.outcome == Outcome.FAILURE
        assert action.error_message == "File not found"


# =============================================================================
# ContextSnapshot Data Class Tests
# =============================================================================


class TestContextSnapshotDataClass:
    """Tests for ContextSnapshot data class."""

    def test_context_snapshot_creation(self):
        """Test creating a ContextSnapshot."""
        from swarm_attack.learning.episode_logger import ContextSnapshot

        snapshot = ContextSnapshot(
            snapshot_id="snap-001",
            timestamp=datetime.now().isoformat(),
            phase="implementation",
        )

        assert snapshot.snapshot_id == "snap-001"
        assert snapshot.phase == "implementation"

    def test_context_snapshot_with_all_fields(self):
        """Test ContextSnapshot with all fields."""
        from swarm_attack.learning.episode_logger import ContextSnapshot

        snapshot = ContextSnapshot(
            snapshot_id="snap-002",
            timestamp="2025-01-06T10:00:00",
            phase="testing",
            files_in_context=["file1.py", "file2.py"],
            token_count=5000,
            key_variables={"issue_number": 3, "feature_id": "my-feature"},
            agent_state="running",
        )

        assert snapshot.files_in_context == ["file1.py", "file2.py"]
        assert snapshot.token_count == 5000
        assert snapshot.key_variables["issue_number"] == 3

    def test_context_snapshot_to_dict(self):
        """Test ContextSnapshot serialization."""
        from swarm_attack.learning.episode_logger import ContextSnapshot

        snapshot = ContextSnapshot(
            snapshot_id="snap-003",
            timestamp="2025-01-06T10:00:00",
            phase="debugging",
        )

        data = snapshot.to_dict()

        assert data["snapshot_id"] == "snap-003"
        assert data["phase"] == "debugging"

    def test_context_snapshot_from_dict(self):
        """Test ContextSnapshot deserialization."""
        from swarm_attack.learning.episode_logger import ContextSnapshot

        data = {
            "snapshot_id": "snap-004",
            "timestamp": "2025-01-06T10:00:00",
            "phase": "planning",
            "token_count": 3000,
        }

        snapshot = ContextSnapshot.from_dict(data)

        assert snapshot.snapshot_id == "snap-004"
        assert snapshot.token_count == 3000


# =============================================================================
# RecoveryAttempt Data Class Tests
# =============================================================================


class TestRecoveryAttemptDataClass:
    """Tests for RecoveryAttempt data class."""

    def test_recovery_attempt_creation(self):
        """Test creating a RecoveryAttempt."""
        from swarm_attack.learning.episode_logger import RecoveryAttempt, Outcome

        attempt = RecoveryAttempt(
            attempt_id="rec-001",
            timestamp=datetime.now().isoformat(),
            trigger_error="Test failed: AssertionError",
            strategy="retry",
        )

        assert attempt.attempt_id == "rec-001"
        assert attempt.strategy == "retry"

    def test_recovery_attempt_with_all_fields(self):
        """Test RecoveryAttempt with all fields."""
        from swarm_attack.learning.episode_logger import RecoveryAttempt, Outcome

        attempt = RecoveryAttempt(
            attempt_id="rec-002",
            timestamp="2025-01-06T10:00:00",
            trigger_error="ImportError: No module named 'foo'",
            strategy="simplify",
            actions_taken=["Removed import", "Added fallback"],
            outcome=Outcome.SUCCESS,
            result_summary="Fixed by removing unused import",
        )

        assert attempt.actions_taken == ["Removed import", "Added fallback"]
        assert attempt.outcome == Outcome.SUCCESS

    def test_recovery_attempt_to_dict(self):
        """Test RecoveryAttempt serialization."""
        from swarm_attack.learning.episode_logger import RecoveryAttempt, Outcome

        attempt = RecoveryAttempt(
            attempt_id="rec-003",
            timestamp="2025-01-06T10:00:00",
            trigger_error="SyntaxError",
            strategy="fix_syntax",
            outcome=Outcome.SUCCESS,
        )

        data = attempt.to_dict()

        assert data["attempt_id"] == "rec-003"
        assert data["outcome"] == "success"

    def test_recovery_attempt_from_dict(self):
        """Test RecoveryAttempt deserialization."""
        from swarm_attack.learning.episode_logger import RecoveryAttempt, Outcome

        data = {
            "attempt_id": "rec-004",
            "timestamp": "2025-01-06T10:00:00",
            "trigger_error": "TimeoutError",
            "strategy": "increase_timeout",
            "outcome": "failure",
        }

        attempt = RecoveryAttempt.from_dict(data)

        assert attempt.attempt_id == "rec-004"
        assert attempt.outcome == Outcome.FAILURE


# =============================================================================
# Episode Data Class Tests
# =============================================================================


class TestEpisodeDataClass:
    """Tests for Episode data class."""

    def test_episode_creation(self):
        """Test creating an Episode with required fields."""
        from swarm_attack.learning.episode_logger import Episode

        episode = Episode(
            episode_id="ep-001",
            feature_id="my-feature",
            started_at=datetime.now().isoformat(),
        )

        assert episode.episode_id == "ep-001"
        assert episode.feature_id == "my-feature"

    def test_episode_with_all_fields(self):
        """Test creating Episode with all fields."""
        from swarm_attack.learning.episode_logger import Episode, Outcome

        episode = Episode(
            episode_id="ep-002",
            feature_id="my-feature",
            issue_number=3,
            agent_type="coder",
            started_at="2025-01-06T10:00:00",
            ended_at="2025-01-06T10:30:00",
            final_outcome=Outcome.SUCCESS,
            actions=[],
            context_snapshots=[],
            recovery_attempts=[],
            metadata={"max_turns": 15},
        )

        assert episode.issue_number == 3
        assert episode.agent_type == "coder"
        assert episode.final_outcome == Outcome.SUCCESS

    def test_episode_to_dict(self):
        """Test Episode serialization."""
        from swarm_attack.learning.episode_logger import Episode

        episode = Episode(
            episode_id="ep-003",
            feature_id="test-feature",
            started_at="2025-01-06T10:00:00",
        )

        data = episode.to_dict()

        assert data["episode_id"] == "ep-003"
        assert data["feature_id"] == "test-feature"

    def test_episode_from_dict(self):
        """Test Episode deserialization."""
        from swarm_attack.learning.episode_logger import Episode, Outcome

        data = {
            "episode_id": "ep-004",
            "feature_id": "other-feature",
            "started_at": "2025-01-06T10:00:00",
            "final_outcome": "partial",
        }

        episode = Episode.from_dict(data)

        assert episode.episode_id == "ep-004"
        assert episode.final_outcome == Outcome.PARTIAL

    def test_episode_duration_property(self):
        """Test Episode duration calculation."""
        from swarm_attack.learning.episode_logger import Episode

        episode = Episode(
            episode_id="ep-005",
            feature_id="test-feature",
            started_at="2025-01-06T10:00:00",
            ended_at="2025-01-06T10:30:00",
        )

        # Duration should be in seconds
        assert episode.duration_seconds is not None
        assert episode.duration_seconds == 1800  # 30 minutes

    def test_episode_duration_none_when_not_ended(self):
        """Test Episode duration is None when not ended."""
        from swarm_attack.learning.episode_logger import Episode

        episode = Episode(
            episode_id="ep-006",
            feature_id="test-feature",
            started_at="2025-01-06T10:00:00",
        )

        assert episode.duration_seconds is None


# =============================================================================
# EpisodeLogger Creation Tests
# =============================================================================


class TestEpisodeLoggerCreation:
    """Tests for EpisodeLogger initialization."""

    def test_logger_creation_without_config(self):
        """Test creating EpisodeLogger without config."""
        from swarm_attack.learning.episode_logger import EpisodeLogger

        logger = EpisodeLogger()

        assert logger is not None

    def test_logger_creation_with_config(self):
        """Test creating EpisodeLogger with config."""
        from swarm_attack.learning.episode_logger import EpisodeLogger

        config = MagicMock()
        config.repo_root = "/tmp/test"

        logger = EpisodeLogger(config=config)

        assert logger.config == config

    def test_logger_stores_base_path(self):
        """Test that logger stores episodes at configured path."""
        from swarm_attack.learning.episode_logger import EpisodeLogger

        config = MagicMock()
        config.swarm_path = "/tmp/test/.swarm"

        logger = EpisodeLogger(config=config)

        assert logger.episodes_path is not None


# =============================================================================
# EpisodeLogger.start_episode() Tests
# =============================================================================


class TestEpisodeLoggerStartEpisode:
    """Tests for EpisodeLogger.start_episode() method."""

    def test_start_episode_returns_episode(self):
        """Test that start_episode returns an Episode."""
        from swarm_attack.learning.episode_logger import EpisodeLogger, Episode

        logger = EpisodeLogger()

        episode = logger.start_episode(
            feature_id="my-feature",
            agent_type="coder",
        )

        assert isinstance(episode, Episode)
        assert episode.feature_id == "my-feature"
        assert episode.agent_type == "coder"

    def test_start_episode_generates_id(self):
        """Test that start_episode generates unique ID."""
        from swarm_attack.learning.episode_logger import EpisodeLogger

        logger = EpisodeLogger()

        ep1 = logger.start_episode(feature_id="f1")
        ep2 = logger.start_episode(feature_id="f2")

        assert ep1.episode_id != ep2.episode_id

    def test_start_episode_with_issue_number(self):
        """Test starting episode with issue number."""
        from swarm_attack.learning.episode_logger import EpisodeLogger

        logger = EpisodeLogger()

        episode = logger.start_episode(
            feature_id="my-feature",
            issue_number=5,
        )

        assert episode.issue_number == 5

    def test_start_episode_sets_timestamp(self):
        """Test that start_episode sets started_at timestamp."""
        from swarm_attack.learning.episode_logger import EpisodeLogger

        logger = EpisodeLogger()

        episode = logger.start_episode(feature_id="my-feature")

        assert episode.started_at is not None

    def test_start_episode_tracks_active_episode(self):
        """Test that logger tracks active episode."""
        from swarm_attack.learning.episode_logger import EpisodeLogger

        logger = EpisodeLogger()

        episode = logger.start_episode(feature_id="my-feature")

        assert logger.current_episode == episode


# =============================================================================
# EpisodeLogger.log_action() Tests
# =============================================================================


class TestEpisodeLoggerLogAction:
    """Tests for EpisodeLogger.log_action() method."""

    def test_log_action_adds_to_episode(self):
        """Test that log_action adds action to current episode."""
        from swarm_attack.learning.episode_logger import EpisodeLogger, Action

        logger = EpisodeLogger()
        logger.start_episode(feature_id="my-feature")

        action = logger.log_action(
            action_type="tool_call",
            tool_name="Read",
            input_data={"file": "test.py"},
        )

        assert len(logger.current_episode.actions) == 1
        assert isinstance(action, Action)

    def test_log_action_generates_id(self):
        """Test that log_action generates unique action ID."""
        from swarm_attack.learning.episode_logger import EpisodeLogger

        logger = EpisodeLogger()
        logger.start_episode(feature_id="my-feature")

        action1 = logger.log_action(action_type="tool_call", tool_name="Read")
        action2 = logger.log_action(action_type="tool_call", tool_name="Edit")

        assert action1.action_id != action2.action_id

    def test_log_action_sets_timestamp(self):
        """Test that log_action sets timestamp."""
        from swarm_attack.learning.episode_logger import EpisodeLogger

        logger = EpisodeLogger()
        logger.start_episode(feature_id="my-feature")

        action = logger.log_action(action_type="tool_call", tool_name="Read")

        assert action.timestamp is not None

    def test_log_action_without_episode_raises(self):
        """Test that log_action raises when no episode started."""
        from swarm_attack.learning.episode_logger import EpisodeLogger

        logger = EpisodeLogger()

        with pytest.raises(ValueError, match="No active episode"):
            logger.log_action(action_type="tool_call", tool_name="Read")

    def test_log_action_with_output_data(self):
        """Test logging action with output data."""
        from swarm_attack.learning.episode_logger import EpisodeLogger

        logger = EpisodeLogger()
        logger.start_episode(feature_id="my-feature")

        action = logger.log_action(
            action_type="tool_call",
            tool_name="Read",
            output_data={"content": "file contents"},
        )

        assert action.output_data == {"content": "file contents"}


# =============================================================================
# EpisodeLogger.update_action_outcome() Tests
# =============================================================================


class TestEpisodeLoggerUpdateActionOutcome:
    """Tests for updating action outcomes."""

    def test_update_action_outcome_success(self):
        """Test updating action outcome to success."""
        from swarm_attack.learning.episode_logger import EpisodeLogger, Outcome

        logger = EpisodeLogger()
        logger.start_episode(feature_id="my-feature")
        action = logger.log_action(action_type="tool_call", tool_name="Read")

        logger.update_action_outcome(
            action_id=action.action_id,
            outcome=Outcome.SUCCESS,
        )

        assert action.outcome == Outcome.SUCCESS

    def test_update_action_outcome_failure_with_error(self):
        """Test updating action outcome to failure with error message."""
        from swarm_attack.learning.episode_logger import EpisodeLogger, Outcome

        logger = EpisodeLogger()
        logger.start_episode(feature_id="my-feature")
        action = logger.log_action(action_type="tool_call", tool_name="Bash")

        logger.update_action_outcome(
            action_id=action.action_id,
            outcome=Outcome.FAILURE,
            error_message="Command failed with exit code 1",
        )

        assert action.outcome == Outcome.FAILURE
        assert action.error_message == "Command failed with exit code 1"

    def test_update_action_outcome_with_duration(self):
        """Test updating action outcome with duration."""
        from swarm_attack.learning.episode_logger import EpisodeLogger, Outcome

        logger = EpisodeLogger()
        logger.start_episode(feature_id="my-feature")
        action = logger.log_action(action_type="tool_call", tool_name="Read")

        logger.update_action_outcome(
            action_id=action.action_id,
            outcome=Outcome.SUCCESS,
            duration_ms=250,
        )

        assert action.duration_ms == 250

    def test_update_action_outcome_not_found_raises(self):
        """Test updating non-existent action raises error."""
        from swarm_attack.learning.episode_logger import EpisodeLogger, Outcome

        logger = EpisodeLogger()
        logger.start_episode(feature_id="my-feature")

        with pytest.raises(ValueError, match="Action not found"):
            logger.update_action_outcome(
                action_id="nonexistent",
                outcome=Outcome.SUCCESS,
            )


# =============================================================================
# EpisodeLogger.capture_context() Tests
# =============================================================================


class TestEpisodeLoggerCaptureContext:
    """Tests for EpisodeLogger.capture_context() method."""

    def test_capture_context_returns_snapshot(self):
        """Test that capture_context returns a ContextSnapshot."""
        from swarm_attack.learning.episode_logger import (
            EpisodeLogger,
            ContextSnapshot,
        )

        logger = EpisodeLogger()
        logger.start_episode(feature_id="my-feature")

        snapshot = logger.capture_context(phase="implementation")

        assert isinstance(snapshot, ContextSnapshot)
        assert snapshot.phase == "implementation"

    def test_capture_context_adds_to_episode(self):
        """Test that snapshot is added to episode."""
        from swarm_attack.learning.episode_logger import EpisodeLogger

        logger = EpisodeLogger()
        logger.start_episode(feature_id="my-feature")

        logger.capture_context(phase="testing")

        assert len(logger.current_episode.context_snapshots) == 1

    def test_capture_context_with_files(self):
        """Test capturing context with files list."""
        from swarm_attack.learning.episode_logger import EpisodeLogger

        logger = EpisodeLogger()
        logger.start_episode(feature_id="my-feature")

        snapshot = logger.capture_context(
            phase="debugging",
            files_in_context=["main.py", "test_main.py"],
        )

        assert snapshot.files_in_context == ["main.py", "test_main.py"]

    def test_capture_context_with_token_count(self):
        """Test capturing context with token count."""
        from swarm_attack.learning.episode_logger import EpisodeLogger

        logger = EpisodeLogger()
        logger.start_episode(feature_id="my-feature")

        snapshot = logger.capture_context(
            phase="planning",
            token_count=8500,
        )

        assert snapshot.token_count == 8500

    def test_capture_context_with_key_variables(self):
        """Test capturing context with key variables."""
        from swarm_attack.learning.episode_logger import EpisodeLogger

        logger = EpisodeLogger()
        logger.start_episode(feature_id="my-feature")

        snapshot = logger.capture_context(
            phase="implementation",
            key_variables={"iteration": 3, "tests_passing": 5},
        )

        assert snapshot.key_variables["iteration"] == 3

    def test_capture_context_without_episode_raises(self):
        """Test that capture_context raises when no episode started."""
        from swarm_attack.learning.episode_logger import EpisodeLogger

        logger = EpisodeLogger()

        with pytest.raises(ValueError, match="No active episode"):
            logger.capture_context(phase="testing")


# =============================================================================
# EpisodeLogger.log_recovery_attempt() Tests
# =============================================================================


class TestEpisodeLoggerLogRecoveryAttempt:
    """Tests for EpisodeLogger.log_recovery_attempt() method."""

    def test_log_recovery_attempt_returns_attempt(self):
        """Test that log_recovery_attempt returns a RecoveryAttempt."""
        from swarm_attack.learning.episode_logger import (
            EpisodeLogger,
            RecoveryAttempt,
        )

        logger = EpisodeLogger()
        logger.start_episode(feature_id="my-feature")

        attempt = logger.log_recovery_attempt(
            trigger_error="AssertionError: Test failed",
            strategy="retry",
        )

        assert isinstance(attempt, RecoveryAttempt)
        assert attempt.trigger_error == "AssertionError: Test failed"
        assert attempt.strategy == "retry"

    def test_log_recovery_attempt_adds_to_episode(self):
        """Test that recovery attempt is added to episode."""
        from swarm_attack.learning.episode_logger import EpisodeLogger

        logger = EpisodeLogger()
        logger.start_episode(feature_id="my-feature")

        logger.log_recovery_attempt(
            trigger_error="Error",
            strategy="simplify",
        )

        assert len(logger.current_episode.recovery_attempts) == 1

    def test_log_recovery_attempt_generates_id(self):
        """Test that recovery attempt gets unique ID."""
        from swarm_attack.learning.episode_logger import EpisodeLogger

        logger = EpisodeLogger()
        logger.start_episode(feature_id="my-feature")

        attempt1 = logger.log_recovery_attempt(
            trigger_error="Error 1",
            strategy="retry",
        )
        attempt2 = logger.log_recovery_attempt(
            trigger_error="Error 2",
            strategy="simplify",
        )

        assert attempt1.attempt_id != attempt2.attempt_id

    def test_log_recovery_attempt_without_episode_raises(self):
        """Test that log_recovery_attempt raises when no episode started."""
        from swarm_attack.learning.episode_logger import EpisodeLogger

        logger = EpisodeLogger()

        with pytest.raises(ValueError, match="No active episode"):
            logger.log_recovery_attempt(
                trigger_error="Error",
                strategy="retry",
            )


# =============================================================================
# EpisodeLogger.update_recovery_outcome() Tests
# =============================================================================


class TestEpisodeLoggerUpdateRecoveryOutcome:
    """Tests for updating recovery attempt outcomes."""

    def test_update_recovery_outcome_success(self):
        """Test updating recovery outcome to success."""
        from swarm_attack.learning.episode_logger import EpisodeLogger, Outcome

        logger = EpisodeLogger()
        logger.start_episode(feature_id="my-feature")
        attempt = logger.log_recovery_attempt(
            trigger_error="Error",
            strategy="retry",
        )

        logger.update_recovery_outcome(
            attempt_id=attempt.attempt_id,
            outcome=Outcome.SUCCESS,
            result_summary="Retry succeeded after fixing import",
        )

        assert attempt.outcome == Outcome.SUCCESS
        assert attempt.result_summary == "Retry succeeded after fixing import"

    def test_update_recovery_outcome_failure(self):
        """Test updating recovery outcome to failure."""
        from swarm_attack.learning.episode_logger import EpisodeLogger, Outcome

        logger = EpisodeLogger()
        logger.start_episode(feature_id="my-feature")
        attempt = logger.log_recovery_attempt(
            trigger_error="Error",
            strategy="simplify",
        )

        logger.update_recovery_outcome(
            attempt_id=attempt.attempt_id,
            outcome=Outcome.FAILURE,
            result_summary="Simplification did not resolve the issue",
        )

        assert attempt.outcome == Outcome.FAILURE

    def test_update_recovery_outcome_with_actions(self):
        """Test updating recovery outcome with actions taken."""
        from swarm_attack.learning.episode_logger import EpisodeLogger, Outcome

        logger = EpisodeLogger()
        logger.start_episode(feature_id="my-feature")
        attempt = logger.log_recovery_attempt(
            trigger_error="ImportError",
            strategy="fix_import",
        )

        logger.update_recovery_outcome(
            attempt_id=attempt.attempt_id,
            outcome=Outcome.SUCCESS,
            actions_taken=["Removed unused import", "Added correct import"],
        )

        assert attempt.actions_taken == ["Removed unused import", "Added correct import"]

    def test_update_recovery_outcome_not_found_raises(self):
        """Test updating non-existent recovery raises error."""
        from swarm_attack.learning.episode_logger import EpisodeLogger, Outcome

        logger = EpisodeLogger()
        logger.start_episode(feature_id="my-feature")

        with pytest.raises(ValueError, match="Recovery attempt not found"):
            logger.update_recovery_outcome(
                attempt_id="nonexistent",
                outcome=Outcome.SUCCESS,
            )


# =============================================================================
# EpisodeLogger.end_episode() Tests
# =============================================================================


class TestEpisodeLoggerEndEpisode:
    """Tests for EpisodeLogger.end_episode() method."""

    def test_end_episode_sets_ended_at(self):
        """Test that end_episode sets ended_at timestamp."""
        from swarm_attack.learning.episode_logger import EpisodeLogger, Outcome

        logger = EpisodeLogger()
        episode = logger.start_episode(feature_id="my-feature")

        logger.end_episode(outcome=Outcome.SUCCESS)

        assert episode.ended_at is not None

    def test_end_episode_sets_final_outcome(self):
        """Test that end_episode sets final_outcome."""
        from swarm_attack.learning.episode_logger import EpisodeLogger, Outcome

        logger = EpisodeLogger()
        logger.start_episode(feature_id="my-feature")

        logger.end_episode(outcome=Outcome.FAILURE)

        assert logger.current_episode is None  # Episode ended
        # Check via get_episode method
        # Need to track episodes

    def test_end_episode_returns_episode(self):
        """Test that end_episode returns the completed episode."""
        from swarm_attack.learning.episode_logger import EpisodeLogger, Outcome, Episode

        logger = EpisodeLogger()
        logger.start_episode(feature_id="my-feature")

        episode = logger.end_episode(outcome=Outcome.SUCCESS)

        assert isinstance(episode, Episode)
        assert episode.final_outcome == Outcome.SUCCESS

    def test_end_episode_clears_current_episode(self):
        """Test that end_episode clears current_episode."""
        from swarm_attack.learning.episode_logger import EpisodeLogger, Outcome

        logger = EpisodeLogger()
        logger.start_episode(feature_id="my-feature")

        logger.end_episode(outcome=Outcome.SUCCESS)

        assert logger.current_episode is None

    def test_end_episode_without_active_raises(self):
        """Test that end_episode raises when no episode active."""
        from swarm_attack.learning.episode_logger import EpisodeLogger, Outcome

        logger = EpisodeLogger()

        with pytest.raises(ValueError, match="No active episode"):
            logger.end_episode(outcome=Outcome.SUCCESS)

    def test_end_episode_stores_in_history(self):
        """Test that completed episode is stored in history."""
        from swarm_attack.learning.episode_logger import EpisodeLogger, Outcome

        logger = EpisodeLogger()
        logger.start_episode(feature_id="my-feature")
        ep_id = logger.current_episode.episode_id

        logger.end_episode(outcome=Outcome.SUCCESS)

        # Should be able to retrieve by ID
        episode = logger.get_episode(ep_id)
        assert episode is not None
        assert episode.final_outcome == Outcome.SUCCESS


# =============================================================================
# EpisodeLogger.get_episode() Tests
# =============================================================================


class TestEpisodeLoggerGetEpisode:
    """Tests for EpisodeLogger.get_episode() method."""

    def test_get_episode_by_id(self):
        """Test retrieving episode by ID."""
        from swarm_attack.learning.episode_logger import EpisodeLogger, Outcome

        logger = EpisodeLogger()
        logger.start_episode(feature_id="my-feature")
        ep_id = logger.current_episode.episode_id
        logger.end_episode(outcome=Outcome.SUCCESS)

        episode = logger.get_episode(ep_id)

        assert episode is not None
        assert episode.episode_id == ep_id

    def test_get_episode_not_found_returns_none(self):
        """Test get_episode returns None for unknown ID."""
        from swarm_attack.learning.episode_logger import EpisodeLogger

        logger = EpisodeLogger()

        episode = logger.get_episode("nonexistent")

        assert episode is None


# =============================================================================
# EpisodeLogger.get_episodes_for_feature() Tests
# =============================================================================


class TestEpisodeLoggerGetEpisodesForFeature:
    """Tests for retrieving episodes by feature."""

    def test_get_episodes_for_feature(self):
        """Test retrieving all episodes for a feature."""
        from swarm_attack.learning.episode_logger import EpisodeLogger, Outcome

        logger = EpisodeLogger()

        # Create multiple episodes for same feature
        logger.start_episode(feature_id="feature-a")
        logger.end_episode(outcome=Outcome.SUCCESS)

        logger.start_episode(feature_id="feature-a")
        logger.end_episode(outcome=Outcome.FAILURE)

        logger.start_episode(feature_id="feature-b")
        logger.end_episode(outcome=Outcome.SUCCESS)

        episodes = logger.get_episodes_for_feature("feature-a")

        assert len(episodes) == 2
        for ep in episodes:
            assert ep.feature_id == "feature-a"

    def test_get_episodes_for_feature_empty(self):
        """Test get_episodes_for_feature returns empty list for unknown feature."""
        from swarm_attack.learning.episode_logger import EpisodeLogger

        logger = EpisodeLogger()

        episodes = logger.get_episodes_for_feature("unknown")

        assert episodes == []


# =============================================================================
# EpisodeLogger Persistence Tests
# =============================================================================


class TestEpisodeLoggerPersistence:
    """Tests for episode persistence."""

    def test_save_episode(self, tmp_path):
        """Test saving episode to disk."""
        from swarm_attack.learning.episode_logger import EpisodeLogger, Outcome

        config = MagicMock()
        config.swarm_path = tmp_path / ".swarm"
        config.swarm_path.mkdir(parents=True)

        logger = EpisodeLogger(config=config)
        logger.start_episode(feature_id="my-feature")
        logger.log_action(action_type="tool_call", tool_name="Read")
        episode = logger.end_episode(outcome=Outcome.SUCCESS)

        # Episode should be saved
        episode_file = logger.episodes_path / f"{episode.episode_id}.json"
        assert episode_file.exists()

    def test_load_episode(self, tmp_path):
        """Test loading episode from disk."""
        from swarm_attack.learning.episode_logger import EpisodeLogger, Outcome

        config = MagicMock()
        config.swarm_path = tmp_path / ".swarm"
        config.swarm_path.mkdir(parents=True)

        # Create and save episode
        logger1 = EpisodeLogger(config=config)
        logger1.start_episode(feature_id="my-feature")
        logger1.log_action(action_type="tool_call", tool_name="Read")
        episode = logger1.end_episode(outcome=Outcome.SUCCESS)
        ep_id = episode.episode_id

        # Create new logger and load
        logger2 = EpisodeLogger(config=config)
        loaded = logger2.get_episode(ep_id)

        assert loaded is not None
        assert loaded.episode_id == ep_id
        assert loaded.feature_id == "my-feature"
        assert len(loaded.actions) == 1


# =============================================================================
# EpisodeLogger Statistics Tests
# =============================================================================


class TestEpisodeLoggerStatistics:
    """Tests for episode statistics."""

    def test_get_success_rate(self):
        """Test calculating success rate for feature."""
        from swarm_attack.learning.episode_logger import EpisodeLogger, Outcome

        logger = EpisodeLogger()

        # 2 success, 1 failure = 66.67% success rate
        logger.start_episode(feature_id="my-feature")
        logger.end_episode(outcome=Outcome.SUCCESS)

        logger.start_episode(feature_id="my-feature")
        logger.end_episode(outcome=Outcome.SUCCESS)

        logger.start_episode(feature_id="my-feature")
        logger.end_episode(outcome=Outcome.FAILURE)

        success_rate = logger.get_success_rate("my-feature")

        assert abs(success_rate - 0.6667) < 0.01

    def test_get_average_duration(self):
        """Test calculating average episode duration."""
        from swarm_attack.learning.episode_logger import EpisodeLogger, Outcome

        logger = EpisodeLogger()

        # Multiple episodes with different durations would be tested
        # For now, just ensure method exists and returns float
        logger.start_episode(feature_id="my-feature")
        logger.end_episode(outcome=Outcome.SUCCESS)

        avg_duration = logger.get_average_duration("my-feature")

        assert isinstance(avg_duration, (int, float))

    def test_get_recovery_success_rate(self):
        """Test calculating recovery attempt success rate."""
        from swarm_attack.learning.episode_logger import EpisodeLogger, Outcome

        logger = EpisodeLogger()

        logger.start_episode(feature_id="my-feature")

        # 1 success, 1 failure = 50% recovery success
        attempt1 = logger.log_recovery_attempt(
            trigger_error="Error 1",
            strategy="retry",
        )
        logger.update_recovery_outcome(
            attempt_id=attempt1.attempt_id,
            outcome=Outcome.SUCCESS,
        )

        attempt2 = logger.log_recovery_attempt(
            trigger_error="Error 2",
            strategy="simplify",
        )
        logger.update_recovery_outcome(
            attempt_id=attempt2.attempt_id,
            outcome=Outcome.FAILURE,
        )

        logger.end_episode(outcome=Outcome.PARTIAL)

        recovery_rate = logger.get_recovery_success_rate("my-feature")

        assert abs(recovery_rate - 0.5) < 0.01


# =============================================================================
# EpisodeLogger Action Type Tests
# =============================================================================


class TestEpisodeLoggerActionTypes:
    """Tests for different action types."""

    def test_log_tool_call_action(self):
        """Test logging a tool call action."""
        from swarm_attack.learning.episode_logger import EpisodeLogger

        logger = EpisodeLogger()
        logger.start_episode(feature_id="my-feature")

        action = logger.log_action(
            action_type="tool_call",
            tool_name="Read",
            input_data={"file_path": "/path/to/file.py"},
        )

        assert action.action_type == "tool_call"
        assert action.tool_name == "Read"

    def test_log_edit_action(self):
        """Test logging an edit action."""
        from swarm_attack.learning.episode_logger import EpisodeLogger

        logger = EpisodeLogger()
        logger.start_episode(feature_id="my-feature")

        action = logger.log_action(
            action_type="edit",
            tool_name="Edit",
            input_data={
                "file_path": "/path/to/file.py",
                "old_string": "foo",
                "new_string": "bar",
            },
        )

        assert action.action_type == "edit"

    def test_log_command_action(self):
        """Test logging a command/bash action."""
        from swarm_attack.learning.episode_logger import EpisodeLogger

        logger = EpisodeLogger()
        logger.start_episode(feature_id="my-feature")

        action = logger.log_action(
            action_type="command",
            tool_name="Bash",
            input_data={"command": "pytest tests/ -v"},
        )

        assert action.action_type == "command"

    def test_log_llm_call_action(self):
        """Test logging an LLM call action."""
        from swarm_attack.learning.episode_logger import EpisodeLogger

        logger = EpisodeLogger()
        logger.start_episode(feature_id="my-feature")

        action = logger.log_action(
            action_type="llm_call",
            tool_name="claude",
            input_data={"prompt_tokens": 5000},
            output_data={"completion_tokens": 1500},
        )

        assert action.action_type == "llm_call"


# =============================================================================
# Integration Tests
# =============================================================================


class TestEpisodeLoggerIntegration:
    """Integration tests for EpisodeLogger."""

    def test_full_episode_workflow(self):
        """Test complete episode workflow."""
        from swarm_attack.learning.episode_logger import EpisodeLogger, Outcome

        logger = EpisodeLogger()

        # Start episode
        episode = logger.start_episode(
            feature_id="test-feature",
            issue_number=1,
            agent_type="coder",
        )

        # Capture initial context
        logger.capture_context(
            phase="initialization",
            token_count=5000,
            key_variables={"max_turns": 15},
        )

        # Log some actions
        read_action = logger.log_action(
            action_type="tool_call",
            tool_name="Read",
            input_data={"file": "main.py"},
        )
        logger.update_action_outcome(
            action_id=read_action.action_id,
            outcome=Outcome.SUCCESS,
            duration_ms=50,
        )

        edit_action = logger.log_action(
            action_type="edit",
            tool_name="Edit",
            input_data={"file": "main.py", "old": "foo", "new": "bar"},
        )
        logger.update_action_outcome(
            action_id=edit_action.action_id,
            outcome=Outcome.SUCCESS,
            duration_ms=30,
        )

        # Run tests - fails first time
        test_action = logger.log_action(
            action_type="command",
            tool_name="Bash",
            input_data={"command": "pytest"},
        )
        logger.update_action_outcome(
            action_id=test_action.action_id,
            outcome=Outcome.FAILURE,
            error_message="1 test failed",
        )

        # Recovery attempt
        recovery = logger.log_recovery_attempt(
            trigger_error="1 test failed",
            strategy="fix_test",
        )

        # Capture context during recovery
        logger.capture_context(
            phase="recovery",
            token_count=7500,
        )

        # Fix and rerun
        logger.update_recovery_outcome(
            attempt_id=recovery.attempt_id,
            outcome=Outcome.SUCCESS,
            actions_taken=["Fixed assertion", "Reran tests"],
        )

        # End episode successfully
        completed = logger.end_episode(outcome=Outcome.SUCCESS)

        # Verify episode
        assert completed.feature_id == "test-feature"
        assert completed.final_outcome == Outcome.SUCCESS
        assert len(completed.actions) == 3
        assert len(completed.context_snapshots) == 2
        assert len(completed.recovery_attempts) == 1

    def test_multiple_episodes_same_feature(self):
        """Test multiple episodes for same feature."""
        from swarm_attack.learning.episode_logger import EpisodeLogger, Outcome

        logger = EpisodeLogger()

        # First episode - fails
        logger.start_episode(feature_id="multi-feature", issue_number=1)
        logger.log_action(action_type="tool_call", tool_name="Read")
        logger.end_episode(outcome=Outcome.FAILURE)

        # Second episode - succeeds
        logger.start_episode(feature_id="multi-feature", issue_number=1)
        logger.log_action(action_type="tool_call", tool_name="Read")
        logger.log_action(action_type="edit", tool_name="Edit")
        logger.end_episode(outcome=Outcome.SUCCESS)

        # Get all episodes for feature
        episodes = logger.get_episodes_for_feature("multi-feature")

        assert len(episodes) == 2
        assert episodes[0].final_outcome == Outcome.FAILURE
        assert episodes[1].final_outcome == Outcome.SUCCESS
