"""Tests for stale lock cleanup functionality.

These tests verify the fix for the stale lock bug where lock files persist
indefinitely after process interruption (Ctrl+C, kill, crash), blocking
subsequent swarm runs.

Bug Report:
- Lock files from 08:13 AM persisted until 4:49 PM (8+ hours)
- Stale timeout is 30 minutes
- Manual rm -f .swarm/locks/*/issue_*.lock resolved the issue
"""

import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, Mock

import pytest

from swarm_attack.config import (
    ClaudeConfig,
    GitConfig,
    GitHubConfig,
    SessionConfig,
    SpecDebateConfig,
    SwarmConfig,
    TestRunnerConfig,
)
from swarm_attack.session_manager import SessionManager
from swarm_attack.state_store import StateStore


def _create_test_config(tmp_path: Path, stale_timeout_minutes: int = 30) -> SwarmConfig:
    """Create a test config with the given temp directory."""
    return SwarmConfig(
        repo_root=str(tmp_path),
        specs_dir="specs",
        swarm_dir=".swarm",
        github=GitHubConfig(repo="test/repo"),
        claude=ClaudeConfig(),
        spec_debate=SpecDebateConfig(),
        sessions=SessionConfig(stale_timeout_minutes=stale_timeout_minutes),
        tests=TestRunnerConfig(command="pytest"),
        git=GitConfig(),
    )


def _create_lock_file(lock_dir: Path, issue_number: int, timestamp: datetime) -> Path:
    """Create a lock file with the given timestamp."""
    lock_dir.mkdir(parents=True, exist_ok=True)
    lock_file = lock_dir / f"issue_{issue_number}.lock"
    lock_file.write_text(timestamp.isoformat().replace("+00:00", "Z"))
    return lock_file


class TestCleanStaleLocks:
    """Tests for SessionManager.clean_stale_locks()."""

    def test_no_locks_directory(self, tmp_path: Path):
        """Test clean_stale_locks when locks directory doesn't exist."""
        config = _create_test_config(tmp_path)
        store = StateStore(config)
        manager = SessionManager(config, store)

        result = manager.clean_stale_locks("test-feature")

        assert result == []

    def test_empty_locks_directory(self, tmp_path: Path):
        """Test clean_stale_locks when locks directory is empty."""
        config = _create_test_config(tmp_path)
        store = StateStore(config)
        manager = SessionManager(config, store)

        lock_dir = config.swarm_path / "locks" / "test-feature"
        lock_dir.mkdir(parents=True, exist_ok=True)

        result = manager.clean_stale_locks("test-feature")

        assert result == []

    def test_fresh_lock_not_cleaned(self, tmp_path: Path):
        """Test that a fresh lock (< stale_timeout) is NOT cleaned."""
        config = _create_test_config(tmp_path, stale_timeout_minutes=30)
        store = StateStore(config)
        manager = SessionManager(config, store)

        # Create a lock that's only 10 minutes old
        lock_dir = config.swarm_path / "locks" / "test-feature"
        fresh_time = datetime.now(timezone.utc) - timedelta(minutes=10)
        lock_file = _create_lock_file(lock_dir, 1, fresh_time)

        result = manager.clean_stale_locks("test-feature")

        assert result == []
        assert lock_file.exists()  # Lock should still exist

    def test_stale_lock_cleaned(self, tmp_path: Path):
        """Test that a stale lock (>= stale_timeout) IS cleaned."""
        config = _create_test_config(tmp_path, stale_timeout_minutes=30)
        store = StateStore(config)
        manager = SessionManager(config, store)

        # Create a lock that's 45 minutes old (stale)
        lock_dir = config.swarm_path / "locks" / "test-feature"
        stale_time = datetime.now(timezone.utc) - timedelta(minutes=45)
        lock_file = _create_lock_file(lock_dir, 1, stale_time)

        result = manager.clean_stale_locks("test-feature")

        assert result == [1]
        assert not lock_file.exists()  # Lock should be removed

    def test_exact_timeout_boundary(self, tmp_path: Path):
        """Test lock at exactly stale_timeout boundary is cleaned."""
        config = _create_test_config(tmp_path, stale_timeout_minutes=30)
        store = StateStore(config)
        manager = SessionManager(config, store)

        # Create a lock that's exactly 30 minutes old
        lock_dir = config.swarm_path / "locks" / "test-feature"
        boundary_time = datetime.now(timezone.utc) - timedelta(minutes=30)
        lock_file = _create_lock_file(lock_dir, 1, boundary_time)

        result = manager.clean_stale_locks("test-feature")

        assert result == [1]
        assert not lock_file.exists()

    def test_multiple_locks_mixed_ages(self, tmp_path: Path):
        """Test cleaning multiple locks with different ages."""
        config = _create_test_config(tmp_path, stale_timeout_minutes=30)
        store = StateStore(config)
        manager = SessionManager(config, store)

        lock_dir = config.swarm_path / "locks" / "test-feature"
        now = datetime.now(timezone.utc)

        # Create locks of varying ages
        fresh_lock = _create_lock_file(lock_dir, 1, now - timedelta(minutes=10))
        stale_lock_1 = _create_lock_file(lock_dir, 2, now - timedelta(minutes=45))
        another_fresh = _create_lock_file(lock_dir, 3, now - timedelta(minutes=5))
        stale_lock_2 = _create_lock_file(lock_dir, 4, now - timedelta(hours=8))

        result = manager.clean_stale_locks("test-feature")

        # Should clean issues 2 and 4 (stale), leave 1 and 3 (fresh)
        assert sorted(result) == [2, 4]
        assert fresh_lock.exists()
        assert not stale_lock_1.exists()
        assert another_fresh.exists()
        assert not stale_lock_2.exists()

    def test_empty_lock_file_cleaned(self, tmp_path: Path):
        """Test that an empty lock file is cleaned as corrupted."""
        config = _create_test_config(tmp_path, stale_timeout_minutes=30)
        store = StateStore(config)
        manager = SessionManager(config, store)

        lock_dir = config.swarm_path / "locks" / "test-feature"
        lock_dir.mkdir(parents=True, exist_ok=True)
        empty_lock = lock_dir / "issue_1.lock"
        empty_lock.write_text("")  # Empty content

        result = manager.clean_stale_locks("test-feature")

        assert result == [1]
        assert not empty_lock.exists()

    def test_corrupted_lock_file_cleaned(self, tmp_path: Path):
        """Test that a lock file with invalid timestamp is cleaned."""
        config = _create_test_config(tmp_path, stale_timeout_minutes=30)
        store = StateStore(config)
        manager = SessionManager(config, store)

        lock_dir = config.swarm_path / "locks" / "test-feature"
        lock_dir.mkdir(parents=True, exist_ok=True)
        bad_lock = lock_dir / "issue_1.lock"
        bad_lock.write_text("not-a-valid-timestamp")

        result = manager.clean_stale_locks("test-feature")

        # Corrupted lock is cleaned
        assert not bad_lock.exists()


class TestClearAllLocks:
    """Tests for SessionManager.clear_all_locks()."""

    def test_clear_all_locks_empty(self, tmp_path: Path):
        """Test clear_all_locks with no locks."""
        config = _create_test_config(tmp_path)
        store = StateStore(config)
        manager = SessionManager(config, store)

        result = manager.clear_all_locks("test-feature")

        assert result == []

    def test_clear_all_locks_regardless_of_age(self, tmp_path: Path):
        """Test clear_all_locks removes ALL locks regardless of age."""
        config = _create_test_config(tmp_path, stale_timeout_minutes=30)
        store = StateStore(config)
        manager = SessionManager(config, store)

        lock_dir = config.swarm_path / "locks" / "test-feature"
        now = datetime.now(timezone.utc)

        # Create both fresh and stale locks
        fresh_lock = _create_lock_file(lock_dir, 1, now - timedelta(minutes=5))
        stale_lock = _create_lock_file(lock_dir, 2, now - timedelta(hours=8))

        result = manager.clear_all_locks("test-feature")

        # Should clear ALL locks
        assert sorted(result) == [1, 2]
        assert not fresh_lock.exists()
        assert not stale_lock.exists()


class TestClaimIssueWithStaleLock:
    """Tests for claim_issue behavior with stale locks."""

    def test_claim_issue_with_stale_lock(self, tmp_path: Path):
        """Test that claim_issue succeeds when existing lock is stale."""
        config = _create_test_config(tmp_path, stale_timeout_minutes=30)
        store = StateStore(config)
        manager = SessionManager(config, store)

        # Create a stale lock
        lock_dir = config.swarm_path / "locks" / "test-feature"
        stale_time = datetime.now(timezone.utc) - timedelta(minutes=45)
        _create_lock_file(lock_dir, 1, stale_time)

        # claim_issue should succeed because lock is stale
        result = manager.claim_issue("test-feature", 1)

        assert result is True

    def test_claim_issue_with_fresh_lock(self, tmp_path: Path):
        """Test that claim_issue fails when existing lock is fresh."""
        config = _create_test_config(tmp_path, stale_timeout_minutes=30)
        store = StateStore(config)
        manager = SessionManager(config, store)

        # Create a fresh lock
        lock_dir = config.swarm_path / "locks" / "test-feature"
        fresh_time = datetime.now(timezone.utc) - timedelta(minutes=10)
        _create_lock_file(lock_dir, 1, fresh_time)

        # claim_issue should fail because lock is fresh
        result = manager.claim_issue("test-feature", 1)

        assert result is False


class TestReleaseIssue:
    """Tests for release_issue."""

    def test_release_issue_removes_lock(self, tmp_path: Path):
        """Test that release_issue removes the lock file."""
        config = _create_test_config(tmp_path)
        store = StateStore(config)
        manager = SessionManager(config, store)

        # Claim an issue first
        manager.claim_issue("test-feature", 1)
        lock_file = config.swarm_path / "locks" / "test-feature" / "issue_1.lock"
        assert lock_file.exists()

        # Release should remove the lock
        manager.release_issue("test-feature", 1)
        assert not lock_file.exists()

    def test_release_issue_nonexistent_lock(self, tmp_path: Path):
        """Test that release_issue handles nonexistent lock gracefully."""
        config = _create_test_config(tmp_path)
        store = StateStore(config)
        manager = SessionManager(config, store)

        # Should not raise an error
        manager.release_issue("test-feature", 999)
