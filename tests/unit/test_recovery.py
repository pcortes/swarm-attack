"""Unit tests for recovery module.

Tests for:
- LockManager: acquire, release, force-release, stale detection
- HealthChecker: all 5 health checks
- PreflightChecker: pre-flight validations
- Dependency helpers: circular deps, blocked deps, ready issues
"""

import json
import os
import socket
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional
from unittest.mock import MagicMock, patch

import pytest

from swarm_attack.recovery import (
    HealthCheckResult,
    HealthReport,
    LockInfo,
    LockManager,
    LockResult,
    HealthChecker,
    PreflightChecker,
    WorktreeRecovery,
    WorktreeStatus,
    validate_no_circular_deps,
    get_ready_issues_safe,
    should_skip_issue,
)
from swarm_attack.models import TaskStage


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def tmp_locks_dir(tmp_path):
    """Create a temporary locks directory."""
    locks_dir = tmp_path / "locks"
    locks_dir.mkdir()
    return locks_dir


@pytest.fixture
def lock_manager(tmp_locks_dir):
    """Create a LockManager with temp directory."""
    return LockManager(tmp_locks_dir)


@pytest.fixture
def mock_config(tmp_path):
    """Create a mock SwarmConfig for testing."""
    config = MagicMock()
    config.repo_root = str(tmp_path)
    config.swarm_path = tmp_path / ".swarm"
    config.swarm_path.mkdir(parents=True, exist_ok=True)
    config.git = MagicMock()
    config.git.use_worktrees = False
    config.git.worktrees_root = ".swarm/worktrees"
    config.tests = MagicMock()
    config.tests.command = "pytest"
    config.tests.args = []
    return config


@pytest.fixture
def health_checker(mock_config):
    """Create a HealthChecker with mock config."""
    return HealthChecker(mock_config)


@pytest.fixture
def preflight_checker(mock_config, health_checker):
    """Create a PreflightChecker with mock config."""
    return PreflightChecker(mock_config, health_checker)


# =============================================================================
# Mock TaskRef for dependency tests
# =============================================================================


@dataclass
class MockTaskRef:
    """Mock TaskRef for testing dependency functions."""
    issue_number: int
    stage: TaskStage
    title: str = ""
    dependencies: list = field(default_factory=list)


# =============================================================================
# LockManager Tests
# =============================================================================


class TestLockManagerAcquire:
    """Tests for LockManager.acquire_issue_lock()."""

    def test_acquire_lock_success(self, lock_manager):
        """Test successful lock acquisition."""
        result = lock_manager.acquire_issue_lock(
            feature_id="test-feature",
            issue_number=1,
            session_id="sess_123",
        )

        assert result.acquired is True
        assert result.error is None
        assert result.lock_holder is None

        # Verify lock file exists
        lock_path = lock_manager.locks_dir / "test-feature" / "issue_1.lock"
        assert lock_path.exists()

        # Verify lock contents
        lock_data = json.loads(lock_path.read_text())
        assert lock_data["session_id"] == "sess_123"
        assert lock_data["feature_id"] == "test-feature"
        assert lock_data["issue_number"] == 1
        assert lock_data["pid"] == os.getpid()
        assert lock_data["hostname"] == socket.gethostname()

    def test_acquire_lock_already_held(self, lock_manager):
        """Test lock acquisition when lock is already held."""
        # First acquisition
        result1 = lock_manager.acquire_issue_lock(
            feature_id="test-feature",
            issue_number=1,
            session_id="sess_123",
        )
        assert result1.acquired is True

        # Second acquisition should fail (different session)
        with patch.object(lock_manager, '_is_lock_stale', return_value=False):
            result2 = lock_manager.acquire_issue_lock(
                feature_id="test-feature",
                issue_number=1,
                session_id="sess_456",
            )

        assert result2.acquired is False
        assert result2.error is not None
        assert "locked by session sess_123" in result2.error
        assert result2.lock_holder is not None
        assert result2.lock_holder.session_id == "sess_123"

    def test_acquire_lock_creates_feature_directory(self, lock_manager):
        """Test that acquiring a lock creates the feature directory."""
        feature_dir = lock_manager.locks_dir / "new-feature"
        assert not feature_dir.exists()

        lock_manager.acquire_issue_lock(
            feature_id="new-feature",
            issue_number=1,
            session_id="sess_123",
        )

        assert feature_dir.exists()

    def test_acquire_lock_multiple_issues(self, lock_manager):
        """Test acquiring locks for multiple issues."""
        for i in range(1, 4):
            result = lock_manager.acquire_issue_lock(
                feature_id="test-feature",
                issue_number=i,
                session_id=f"sess_{i}",
            )
            assert result.acquired is True

        # Verify all locks exist
        for i in range(1, 4):
            lock_path = lock_manager.locks_dir / "test-feature" / f"issue_{i}.lock"
            assert lock_path.exists()


class TestLockManagerStaleLocks:
    """Tests for stale lock detection and cleanup."""

    def test_stale_lock_auto_cleanup(self, lock_manager):
        """Test that stale locks are automatically cleaned when acquiring."""
        # Create a stale lock (5 hours old)
        feature_dir = lock_manager.locks_dir / "test-feature"
        feature_dir.mkdir(parents=True, exist_ok=True)
        lock_path = feature_dir / "issue_1.lock"

        stale_time = datetime.now(timezone.utc) - timedelta(hours=5)
        lock_data = {
            "session_id": "old_sess",
            "pid": 99999,  # Non-existent PID
            "hostname": socket.gethostname(),
            "started_at": stale_time.isoformat().replace("+00:00", "Z"),
            "feature_id": "test-feature",
            "issue_number": 1,
        }
        lock_path.write_text(json.dumps(lock_data))

        # New acquisition should succeed because old lock is stale
        result = lock_manager.acquire_issue_lock(
            feature_id="test-feature",
            issue_number=1,
            session_id="new_sess",
        )

        assert result.acquired is True

    def test_lock_not_stale_within_ttl(self, lock_manager):
        """Test that recent locks are not considered stale."""
        # Create a recent lock (1 hour old)
        feature_dir = lock_manager.locks_dir / "test-feature"
        feature_dir.mkdir(parents=True, exist_ok=True)
        lock_path = feature_dir / "issue_1.lock"

        recent_time = datetime.now(timezone.utc) - timedelta(hours=1)
        lock_data = {
            "session_id": "recent_sess",
            "pid": os.getpid(),  # Current process
            "hostname": socket.gethostname(),
            "started_at": recent_time.isoformat().replace("+00:00", "Z"),
            "feature_id": "test-feature",
            "issue_number": 1,
        }
        lock_path.write_text(json.dumps(lock_data))

        # New acquisition should fail because existing lock is valid
        result = lock_manager.acquire_issue_lock(
            feature_id="test-feature",
            issue_number=1,
            session_id="new_sess",
        )

        assert result.acquired is False
        assert "locked by session recent_sess" in result.error

    def test_cleanup_stale_locks(self, lock_manager):
        """Test bulk cleanup of stale locks."""
        feature_dir = lock_manager.locks_dir / "test-feature"
        feature_dir.mkdir(parents=True, exist_ok=True)

        # Create 3 stale locks
        stale_time = datetime.now(timezone.utc) - timedelta(hours=5)
        for i in range(1, 4):
            lock_path = feature_dir / f"issue_{i}.lock"
            lock_data = {
                "session_id": f"old_sess_{i}",
                "pid": 99999,
                "hostname": socket.gethostname(),
                "started_at": stale_time.isoformat().replace("+00:00", "Z"),
                "feature_id": "test-feature",
                "issue_number": i,
            }
            lock_path.write_text(json.dumps(lock_data))

        # Cleanup stale locks
        cleaned = lock_manager.cleanup_stale_locks("test-feature")

        assert len(cleaned) == 3
        assert set(cleaned) == {1, 2, 3}

        # Verify locks are removed
        for i in range(1, 4):
            lock_path = feature_dir / f"issue_{i}.lock"
            assert not lock_path.exists()


class TestLockManagerRelease:
    """Tests for LockManager.release_issue_lock()."""

    def test_release_lock_success(self, lock_manager):
        """Test successful lock release."""
        # Acquire lock
        lock_manager.acquire_issue_lock(
            feature_id="test-feature",
            issue_number=1,
            session_id="sess_123",
        )

        # Release lock
        released = lock_manager.release_issue_lock("test-feature", 1)

        assert released is True
        lock_path = lock_manager.locks_dir / "test-feature" / "issue_1.lock"
        assert not lock_path.exists()

    def test_release_nonexistent_lock(self, lock_manager):
        """Test releasing a lock that doesn't exist."""
        released = lock_manager.release_issue_lock("test-feature", 999)
        assert released is True  # No lock to release = success

    def test_release_lock_held_by_different_process(self, lock_manager, tmp_locks_dir):
        """Test that we can't release a lock held by different process."""
        # Create a lock with different PID
        feature_dir = tmp_locks_dir / "test-feature"
        feature_dir.mkdir(parents=True, exist_ok=True)
        lock_path = feature_dir / "issue_1.lock"

        lock_data = {
            "session_id": "other_sess",
            "pid": 99999,  # Different PID
            "hostname": socket.gethostname(),
            "started_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "feature_id": "test-feature",
            "issue_number": 1,
        }
        lock_path.write_text(json.dumps(lock_data))

        # Try to release
        released = lock_manager.release_issue_lock("test-feature", 1)

        assert released is False
        assert lock_path.exists()  # Lock should still exist


class TestLockManagerForceRelease:
    """Tests for LockManager.force_release()."""

    def test_force_release_lock(self, lock_manager):
        """Test force releasing a lock."""
        # Create a lock
        lock_manager.acquire_issue_lock(
            feature_id="test-feature",
            issue_number=1,
            session_id="sess_123",
        )

        # Force release
        released = lock_manager.force_release("test-feature", 1)

        assert released is True
        lock_path = lock_manager.locks_dir / "test-feature" / "issue_1.lock"
        assert not lock_path.exists()

    def test_force_release_nonexistent_lock(self, lock_manager):
        """Test force releasing a lock that doesn't exist."""
        released = lock_manager.force_release("test-feature", 999)
        assert released is True


class TestLockManagerListLocks:
    """Tests for LockManager.list_locks()."""

    def test_list_locks(self, lock_manager):
        """Test listing all locks for a feature."""
        # Create multiple locks
        for i in range(1, 4):
            lock_manager.acquire_issue_lock(
                feature_id="test-feature",
                issue_number=i,
                session_id=f"sess_{i}",
            )

        locks = lock_manager.list_locks("test-feature")

        assert len(locks) == 3
        session_ids = {l.session_id for l in locks}
        assert session_ids == {"sess_1", "sess_2", "sess_3"}

    def test_list_locks_empty(self, lock_manager):
        """Test listing locks when none exist."""
        locks = lock_manager.list_locks("nonexistent-feature")
        assert locks == []


class TestLockManagerGetLockHolder:
    """Tests for LockManager.get_lock_holder()."""

    def test_get_lock_holder(self, lock_manager):
        """Test getting lock holder information."""
        lock_manager.acquire_issue_lock(
            feature_id="test-feature",
            issue_number=1,
            session_id="sess_123",
        )

        holder = lock_manager.get_lock_holder("test-feature", 1)

        assert holder is not None
        assert holder.session_id == "sess_123"
        assert holder.feature_id == "test-feature"
        assert holder.issue_number == 1

    def test_get_lock_holder_no_lock(self, lock_manager):
        """Test getting lock holder when no lock exists."""
        holder = lock_manager.get_lock_holder("test-feature", 999)
        assert holder is None


# =============================================================================
# HealthChecker Tests
# =============================================================================


class TestHealthCheckerDiskSpace:
    """Tests for HealthChecker._check_disk_space()."""

    def test_disk_space_ok(self, health_checker):
        """Test disk space check passes with sufficient space."""
        result = health_checker._check_disk_space()

        # Should pass on most systems
        assert result.name == "disk_space"
        assert "Disk space" in result.message

    def test_disk_space_low(self, health_checker):
        """Test disk space check fails with low space."""
        # Check with impossibly high threshold
        result = health_checker._check_disk_space(min_free_gb=99999999)

        assert result.passed is False
        assert "Low disk space" in result.message


class TestHealthCheckerStaleSessions:
    """Tests for HealthChecker._check_stale_sessions()."""

    def test_stale_sessions_no_state_store(self, health_checker):
        """Test stale sessions check skips when no state store."""
        result = health_checker._check_stale_sessions()

        assert result.passed is True
        assert "Skipped" in result.message

    def test_stale_sessions_with_state_store(self, mock_config):
        """Test stale sessions check with state store."""
        mock_state_store = MagicMock()
        mock_state_store.list_features.return_value = []

        checker = HealthChecker(mock_config, state_store=mock_state_store)
        result = checker._check_stale_sessions()

        assert result.passed is True
        assert "No stale sessions found" in result.message


class TestHealthCheckerOrphanLocks:
    """Tests for HealthChecker._check_orphan_locks()."""

    def test_orphan_locks_no_directory(self, health_checker, mock_config):
        """Test orphan locks check passes when no locks directory."""
        result = health_checker._check_orphan_locks()

        assert result.passed is True
        assert "No locks directory exists" in result.message

    def test_orphan_locks_with_locks(self, health_checker, mock_config):
        """Test orphan locks check with existing locks."""
        # Create locks directory with a lock file
        locks_dir = mock_config.swarm_path / "locks" / "test-feature"
        locks_dir.mkdir(parents=True, exist_ok=True)

        lock_data = {
            "session_id": "orphan_sess",
            "pid": 99999,  # Non-existent PID
            "hostname": socket.gethostname(),
            "started_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "feature_id": "test-feature",
            "issue_number": 1,
        }
        (locks_dir / "issue_1.lock").write_text(json.dumps(lock_data))

        result = health_checker._check_orphan_locks()

        # Should detect orphan (dead PID)
        assert result.passed is False
        assert "orphan lock" in result.message


class TestHealthCheckerStuckFeatures:
    """Tests for HealthChecker._check_stuck_features()."""

    def test_stuck_features_no_state_store(self, health_checker):
        """Test stuck features check skips when no state store."""
        result = health_checker._check_stuck_features()

        assert result.passed is True
        assert "Skipped" in result.message


class TestHealthCheckerWorktreeHealth:
    """Tests for HealthChecker._check_worktree_health()."""

    def test_worktree_health_no_directory(self, health_checker, mock_config):
        """Test worktree health check passes when no worktrees directory."""
        result = health_checker._check_worktree_health()

        assert result.passed is True
        assert "No worktrees directory exists" in result.message


class TestHealthCheckerRunAll:
    """Tests for HealthChecker.run_health_checks()."""

    def test_run_health_checks_all_pass(self, health_checker):
        """Test running all health checks."""
        report = health_checker.run_health_checks()

        assert isinstance(report, HealthReport)
        assert "timestamp" in report.to_dict()
        assert len(report.checks) == 5

        # All checks should be present
        check_names = set(report.checks.keys())
        assert check_names == {
            "stale_sessions",
            "orphan_locks",
            "stuck_features",
            "disk_space",
            "worktree_health",
        }


# =============================================================================
# PreflightChecker Tests
# =============================================================================


class TestPreflightChecker:
    """Tests for PreflightChecker."""

    def test_preflight_checks_pass(self, preflight_checker):
        """Test preflight checks pass with minimal setup."""
        passed, errors = preflight_checker.run_preflight_checks("test-feature")

        # Should pass with minimal config
        assert isinstance(passed, bool)
        assert isinstance(errors, list)

    def test_preflight_checks_disk_space_fail(self, mock_config):
        """Test preflight checks fail when disk space is low."""
        mock_health_checker = MagicMock()
        mock_health_checker._check_disk_space.return_value = HealthCheckResult(
            name="disk_space",
            passed=False,
            message="Low disk space: 0.5GB free",
        )
        mock_health_checker._check_stale_sessions.return_value = HealthCheckResult(
            name="stale_sessions",
            passed=True,
            message="OK",
        )
        mock_health_checker.state_store = None

        checker = PreflightChecker(mock_config, mock_health_checker)
        passed, errors = checker.run_preflight_checks("test-feature")

        assert passed is False
        assert len(errors) == 1
        assert "Disk space" in errors[0]


# =============================================================================
# WorktreeRecovery Tests
# =============================================================================


class TestWorktreeRecovery:
    """Tests for WorktreeRecovery."""

    def test_validate_worktree_nonexistent(self, mock_config):
        """Test validation fails for nonexistent directory."""
        recovery = WorktreeRecovery(mock_config)
        status = recovery.validate_worktree_health("/nonexistent/path")

        assert status.healthy is False
        assert "Directory does not exist" in status.issues

    def test_validate_worktree_not_git(self, mock_config, tmp_path):
        """Test validation fails for non-git directory."""
        recovery = WorktreeRecovery(mock_config)

        # Create directory without .git
        test_dir = tmp_path / "not-git"
        test_dir.mkdir()

        status = recovery.validate_worktree_health(str(test_dir))

        assert status.healthy is False
        assert "Not a git directory" in status.issues


# =============================================================================
# Dependency Validation Tests
# =============================================================================


class TestValidateNoCircularDeps:
    """Tests for validate_no_circular_deps()."""

    def test_no_circular_deps(self):
        """Test passes with no circular dependencies."""
        tasks = [
            MockTaskRef(issue_number=1, stage=TaskStage.READY, dependencies=[]),
            MockTaskRef(issue_number=2, stage=TaskStage.READY, dependencies=[1]),
            MockTaskRef(issue_number=3, stage=TaskStage.READY, dependencies=[2]),
        ]

        result = validate_no_circular_deps(tasks)
        assert result is None

    def test_detect_simple_circular_dependency(self):
        """Test detects simple circular dependency."""
        tasks = [
            MockTaskRef(issue_number=1, stage=TaskStage.READY, dependencies=[2]),
            MockTaskRef(issue_number=2, stage=TaskStage.READY, dependencies=[1]),
        ]

        result = validate_no_circular_deps(tasks)
        assert result is not None
        assert "Circular dependency" in result

    def test_detect_complex_circular_dependency(self):
        """Test detects circular dependency in longer chain."""
        tasks = [
            MockTaskRef(issue_number=1, stage=TaskStage.READY, dependencies=[3]),
            MockTaskRef(issue_number=2, stage=TaskStage.READY, dependencies=[1]),
            MockTaskRef(issue_number=3, stage=TaskStage.READY, dependencies=[2]),
        ]

        result = validate_no_circular_deps(tasks)
        assert result is not None
        assert "Circular dependency" in result

    def test_empty_task_list(self):
        """Test passes with empty task list."""
        result = validate_no_circular_deps([])
        assert result is None


class TestGetReadyIssuesSafe:
    """Tests for get_ready_issues_safe()."""

    def test_get_ready_issues_no_deps(self):
        """Test getting ready issues with no dependencies."""
        tasks = [
            MockTaskRef(issue_number=1, stage=TaskStage.READY, dependencies=[]),
            MockTaskRef(issue_number=2, stage=TaskStage.READY, dependencies=[]),
        ]

        ready = get_ready_issues_safe(tasks, done_issues=set(), blocked_issues=set())

        assert len(ready) == 2

    def test_get_ready_issues_with_satisfied_deps(self):
        """Test getting ready issues when dependencies are done."""
        tasks = [
            MockTaskRef(issue_number=1, stage=TaskStage.DONE, dependencies=[]),
            MockTaskRef(issue_number=2, stage=TaskStage.READY, dependencies=[1]),
        ]

        ready = get_ready_issues_safe(tasks, done_issues={1}, blocked_issues=set())

        assert len(ready) == 1
        assert ready[0].issue_number == 2

    def test_get_ready_issues_with_blocked_deps(self):
        """Test that issues with blocked dependencies are excluded."""
        tasks = [
            MockTaskRef(issue_number=1, stage=TaskStage.BLOCKED, dependencies=[]),
            MockTaskRef(issue_number=2, stage=TaskStage.READY, dependencies=[1]),
        ]

        ready = get_ready_issues_safe(tasks, done_issues={1}, blocked_issues={1})

        # Issue 2 should not be ready because issue 1 is blocked
        assert len(ready) == 0

    def test_get_ready_issues_excludes_non_ready(self):
        """Test that only READY stage issues are returned."""
        tasks = [
            MockTaskRef(issue_number=1, stage=TaskStage.DONE, dependencies=[]),
            MockTaskRef(issue_number=2, stage=TaskStage.IN_PROGRESS, dependencies=[]),
            MockTaskRef(issue_number=3, stage=TaskStage.READY, dependencies=[]),
        ]

        ready = get_ready_issues_safe(tasks, done_issues=set(), blocked_issues=set())

        assert len(ready) == 1
        assert ready[0].issue_number == 3


class TestShouldSkipIssue:
    """Tests for should_skip_issue()."""

    def test_skip_issue_with_blocked_dependency(self):
        """Test should skip when dependency is blocked."""
        task = MockTaskRef(issue_number=2, stage=TaskStage.READY, dependencies=[1])

        blocking_issue = should_skip_issue(
            task,
            blocked_issues={1},
            skipped_issues=set(),
        )

        assert blocking_issue == 1

    def test_skip_issue_with_skipped_dependency(self):
        """Test should skip when dependency was already skipped."""
        task = MockTaskRef(issue_number=3, stage=TaskStage.READY, dependencies=[2])

        blocking_issue = should_skip_issue(
            task,
            blocked_issues=set(),
            skipped_issues={2},
        )

        assert blocking_issue == 2

    def test_no_skip_with_satisfied_deps(self):
        """Test should not skip when dependencies are satisfied."""
        task = MockTaskRef(issue_number=2, stage=TaskStage.READY, dependencies=[1])

        blocking_issue = should_skip_issue(
            task,
            blocked_issues=set(),
            skipped_issues=set(),
        )

        assert blocking_issue is None

    def test_no_skip_with_no_deps(self):
        """Test should not skip when no dependencies."""
        task = MockTaskRef(issue_number=1, stage=TaskStage.READY, dependencies=[])

        blocking_issue = should_skip_issue(
            task,
            blocked_issues={99},
            skipped_issues={98},
        )

        assert blocking_issue is None


# =============================================================================
# Data Class Tests
# =============================================================================


class TestLockInfo:
    """Tests for LockInfo data class."""

    def test_to_dict(self):
        """Test LockInfo.to_dict()."""
        lock_info = LockInfo(
            session_id="sess_123",
            pid=12345,
            hostname="test-host",
            started_at="2024-12-17T10:00:00Z",
            feature_id="test-feature",
            issue_number=1,
        )

        data = lock_info.to_dict()

        assert data["session_id"] == "sess_123"
        assert data["pid"] == 12345
        assert data["hostname"] == "test-host"

    def test_from_dict(self):
        """Test LockInfo.from_dict()."""
        data = {
            "session_id": "sess_123",
            "pid": 12345,
            "hostname": "test-host",
            "started_at": "2024-12-17T10:00:00Z",
            "feature_id": "test-feature",
            "issue_number": 1,
        }

        lock_info = LockInfo.from_dict(data)

        assert lock_info.session_id == "sess_123"
        assert lock_info.pid == 12345


class TestHealthCheckResult:
    """Tests for HealthCheckResult data class."""

    def test_to_dict(self):
        """Test HealthCheckResult.to_dict()."""
        result = HealthCheckResult(
            name="test_check",
            passed=True,
            message="All good",
            details={"key": "value"},
        )

        data = result.to_dict()

        assert data["name"] == "test_check"
        assert data["passed"] is True
        assert data["message"] == "All good"
        assert data["details"] == {"key": "value"}


class TestHealthReport:
    """Tests for HealthReport data class."""

    def test_to_dict(self):
        """Test HealthReport.to_dict()."""
        checks = {
            "test_check": HealthCheckResult(
                name="test_check",
                passed=True,
                message="OK",
            )
        }

        report = HealthReport(
            healthy=True,
            checks=checks,
            summary="All checks passed",
            timestamp="2024-12-17T10:00:00Z",
        )

        data = report.to_dict()

        assert data["healthy"] is True
        assert "test_check" in data["checks"]
        assert data["summary"] == "All checks passed"


class TestLockResult:
    """Tests for LockResult data class."""

    def test_to_dict_acquired(self):
        """Test LockResult.to_dict() when acquired."""
        result = LockResult(acquired=True)

        data = result.to_dict()

        assert data["acquired"] is True
        assert data["error"] is None
        assert data["lock_holder"] is None

    def test_to_dict_not_acquired(self):
        """Test LockResult.to_dict() when not acquired."""
        lock_holder = LockInfo(
            session_id="sess_123",
            pid=12345,
            hostname="test-host",
            started_at="2024-12-17T10:00:00Z",
        )

        result = LockResult(
            acquired=False,
            error="Lock held by another process",
            lock_holder=lock_holder,
        )

        data = result.to_dict()

        assert data["acquired"] is False
        assert "Lock held" in data["error"]
        assert data["lock_holder"]["session_id"] == "sess_123"


class TestWorktreeStatus:
    """Tests for WorktreeStatus data class."""

    def test_to_dict(self):
        """Test WorktreeStatus.to_dict()."""
        status = WorktreeStatus(
            healthy=False,
            issues=["Detached HEAD state", "Has uncommitted changes"],
            path="/path/to/worktree",
            branch="feature-branch",
            is_detached=True,
            has_uncommitted=True,
        )

        data = status.to_dict()

        assert data["healthy"] is False
        assert len(data["issues"]) == 2
        assert data["is_detached"] is True
        assert data["has_uncommitted"] is True
