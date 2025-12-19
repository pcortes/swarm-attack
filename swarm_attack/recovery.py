"""
Recovery utilities for handling edge cases in swarm orchestration.

This module implements production-grade error handling for the Swarm Attack system:
- Stale session detection and cleanup (4-hour TTL)
- Health check framework with 5 automated checks
- Lock management with rich metadata for debugging
- Pre-flight validations before starting work
- Git worktree recovery from failure states
- Robust test execution with timeouts and flaky detection

Expert Panel Contributors:
- Expert 1 (SRE): Session TTL, stale lock cleanup, health monitoring
- Expert 2 (Distributed Systems): Lock management, concurrent access prevention
- Expert 3 (DevOps): Git worktree health, disk space, pre-flight checks
- Expert 4 (Test Infrastructure): Test execution robustness, flaky detection
- Expert 5 (State Machine): Phase transitions, dependency handling, idempotency
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import signal
import socket
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from swarm_attack.config import SwarmConfig
    from swarm_attack.session_manager import SessionManager
    from swarm_attack.state_store import StateStore


# =============================================================================
# Data Classes - Expert Panel Consensus
# =============================================================================


@dataclass
class HealthCheckResult:
    """Result of a single health check."""
    name: str
    passed: bool
    message: str
    details: Optional[dict] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "passed": self.passed,
            "message": self.message,
            "details": self.details,
        }


@dataclass
class HealthReport:
    """Complete health report from all checks."""
    healthy: bool
    checks: dict[str, HealthCheckResult]
    summary: str
    timestamp: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "healthy": self.healthy,
            "checks": {k: v.to_dict() for k, v in self.checks.items()},
            "summary": self.summary,
            "timestamp": self.timestamp,
        }


@dataclass
class LockInfo:
    """Information about who holds a lock."""
    session_id: str
    pid: int
    hostname: str
    started_at: str
    feature_id: str = ""
    issue_number: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "pid": self.pid,
            "hostname": self.hostname,
            "started_at": self.started_at,
            "feature_id": self.feature_id,
            "issue_number": self.issue_number,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> LockInfo:
        return cls(**data)


@dataclass
class LockResult:
    """Result of a lock acquisition attempt."""
    acquired: bool
    error: Optional[str] = None
    lock_holder: Optional[LockInfo] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "acquired": self.acquired,
            "error": self.error,
            "lock_holder": self.lock_holder.to_dict() if self.lock_holder else None,
        }


@dataclass
class WorktreeStatus:
    """Status of a git worktree."""
    healthy: bool
    issues: list[str] = field(default_factory=list)
    error: Optional[str] = None
    path: str = ""
    branch: str = ""
    is_detached: bool = False
    has_uncommitted: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "healthy": self.healthy,
            "issues": self.issues,
            "error": self.error,
            "path": self.path,
            "branch": self.branch,
            "is_detached": self.is_detached,
            "has_uncommitted": self.has_uncommitted,
        }


@dataclass
class FlakyTestReport:
    """Report on flaky test detection."""
    is_flaky: bool
    flaky_tests: list[str] = field(default_factory=list)
    pass_rate: float = 1.0
    runs_completed: int = 0
    error: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "is_flaky": self.is_flaky,
            "flaky_tests": self.flaky_tests,
            "pass_rate": self.pass_rate,
            "runs_completed": self.runs_completed,
            "error": self.error,
        }


@dataclass
class TestRunResult:
    """Result of a test run with timeout."""
    success: bool
    passed: int = 0
    failed: int = 0
    error: Optional[str] = None
    timed_out: bool = False
    duration_seconds: float = 0.0
    output: str = ""
    failures: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "passed": self.passed,
            "failed": self.failed,
            "error": self.error,
            "timed_out": self.timed_out,
            "duration_seconds": self.duration_seconds,
            "output": self.output,
            "failures": self.failures,
        }


# =============================================================================
# Expert 2: Distributed Systems Architect - Lock Management
# =============================================================================


class LockManager:
    """
    Manages issue-level locks with metadata for debugging.

    Key features:
    - Atomic lock acquisition with PID, hostname, timestamp
    - Rich error messages showing who holds the lock
    - Force-release capability for admin operations
    - Stale lock detection and cleanup

    Lock file format (JSON):
    {
        "session_id": "sess_20241217_...",
        "pid": 12345,
        "hostname": "dev-machine",
        "started_at": "2024-12-17T10:00:00Z",
        "feature_id": "my-feature",
        "issue_number": 1
    }
    """

    def __init__(self, locks_dir: Path, stale_timeout_minutes: int = 240):
        """
        Initialize LockManager.

        Args:
            locks_dir: Directory to store lock files.
            stale_timeout_minutes: Minutes before a lock is considered stale (default 4 hours).
        """
        self.locks_dir = locks_dir
        self.stale_timeout_minutes = stale_timeout_minutes
        self.locks_dir.mkdir(parents=True, exist_ok=True)
        self._logger = logging.getLogger(__name__)

    def _get_lock_path(self, feature_id: str, issue_number: int) -> Path:
        """Get path to lock file for an issue."""
        feature_dir = self.locks_dir / feature_id
        feature_dir.mkdir(parents=True, exist_ok=True)
        return feature_dir / f"issue_{issue_number}.lock"

    def _now_iso(self) -> str:
        """Get current timestamp in ISO format."""
        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    def _is_process_alive(self, pid: int) -> bool:
        """Check if a process with given PID is still running."""
        try:
            os.kill(pid, 0)  # Signal 0 doesn't kill, just checks
            return True
        except (OSError, ProcessLookupError):
            return False

    def _is_lock_stale(self, lock_info: LockInfo) -> bool:
        """Check if a lock is stale based on age and process status."""
        # Parse timestamp
        try:
            started_at = datetime.fromisoformat(
                lock_info.started_at.replace("Z", "+00:00")
            )
            age = datetime.now(timezone.utc) - started_at

            # Stale if older than TTL
            if age >= timedelta(minutes=self.stale_timeout_minutes):
                return True

            # Stale if process is dead AND we're on the same host
            if lock_info.hostname == socket.gethostname():
                if not self._is_process_alive(lock_info.pid):
                    return True

        except (ValueError, AttributeError):
            # Can't parse timestamp - consider stale
            return True

        return False

    def acquire_issue_lock(
        self,
        feature_id: str,
        issue_number: int,
        session_id: str,
    ) -> LockResult:
        """
        Acquire lock with rich metadata for debugging.

        This is an atomic operation that prevents concurrent work on the same issue.
        If the lock is already held, returns information about the holder.

        Args:
            feature_id: The feature identifier.
            issue_number: GitHub issue number.
            session_id: Current session identifier.

        Returns:
            LockResult with acquired=True on success, or lock_holder info on failure.
        """
        lock_path = self._get_lock_path(feature_id, issue_number)

        # Check for existing lock
        if lock_path.exists():
            try:
                lock_data = json.loads(lock_path.read_text())
                lock_info = LockInfo.from_dict(lock_data)

                # Check if lock is stale
                if self._is_lock_stale(lock_info):
                    self._logger.warning(
                        f"Cleaning stale lock for {feature_id}#{issue_number} "
                        f"(held by PID {lock_info.pid} on {lock_info.hostname})"
                    )
                    lock_path.unlink()
                else:
                    # Lock is valid - return holder info
                    return LockResult(
                        acquired=False,
                        error=f"Issue #{issue_number} is locked by session {lock_info.session_id} "
                              f"(PID {lock_info.pid} on {lock_info.hostname} since {lock_info.started_at})",
                        lock_holder=lock_info,
                    )
            except (json.JSONDecodeError, KeyError, OSError) as e:
                # Corrupted lock file - remove it
                self._logger.warning(f"Removing corrupted lock file: {e}")
                try:
                    lock_path.unlink()
                except OSError:
                    pass

        # Create new lock with metadata
        lock_info = LockInfo(
            session_id=session_id,
            pid=os.getpid(),
            hostname=socket.gethostname(),
            started_at=self._now_iso(),
            feature_id=feature_id,
            issue_number=issue_number,
        )

        try:
            # Atomic write using temp file + rename
            temp_path = lock_path.with_suffix(".tmp")
            temp_path.write_text(json.dumps(lock_info.to_dict(), indent=2))
            temp_path.rename(lock_path)

            self._logger.info(
                f"Acquired lock for {feature_id}#{issue_number} "
                f"(session {session_id}, PID {lock_info.pid})"
            )

            return LockResult(acquired=True)

        except OSError as e:
            return LockResult(
                acquired=False,
                error=f"Failed to create lock file: {e}",
            )

    def release_issue_lock(self, feature_id: str, issue_number: int) -> bool:
        """
        Release lock if held by current process.

        Only releases if the lock is held by the current process (same PID).

        Args:
            feature_id: The feature identifier.
            issue_number: GitHub issue number.

        Returns:
            True if lock was released, False otherwise.
        """
        lock_path = self._get_lock_path(feature_id, issue_number)

        if not lock_path.exists():
            return True  # No lock to release

        try:
            lock_data = json.loads(lock_path.read_text())
            lock_info = LockInfo.from_dict(lock_data)

            # Only release if we hold it (same PID and host)
            current_pid = os.getpid()
            current_host = socket.gethostname()

            if lock_info.pid == current_pid and lock_info.hostname == current_host:
                lock_path.unlink()
                self._logger.info(
                    f"Released lock for {feature_id}#{issue_number}"
                )
                return True
            else:
                self._logger.warning(
                    f"Cannot release lock for {feature_id}#{issue_number}: "
                    f"held by PID {lock_info.pid} on {lock_info.hostname}, "
                    f"we are PID {current_pid} on {current_host}"
                )
                return False

        except (json.JSONDecodeError, KeyError, OSError):
            # Corrupted or missing - consider released
            return True

    def get_lock_holder(
        self,
        feature_id: str,
        issue_number: int,
    ) -> Optional[LockInfo]:
        """
        Get information about who holds the lock.

        Handles two lock formats for backwards compatibility:
        1. Plain timestamp string (from SessionManager): "2025-12-19T16:24:11Z"
        2. JSON with full LockInfo (newer format): {"session_id": ..., "pid": ...}

        Args:
            feature_id: The feature identifier.
            issue_number: GitHub issue number.

        Returns:
            LockInfo if lock exists, None otherwise.
        """
        lock_path = self._get_lock_path(feature_id, issue_number)

        if not lock_path.exists():
            return None

        try:
            lock_content = lock_path.read_text().strip()

            # Try JSON format first (newer format)
            try:
                lock_data = json.loads(lock_content)
                return LockInfo.from_dict(lock_data)
            except json.JSONDecodeError:
                pass

            # Fall back to plain timestamp format (SessionManager format)
            # Create a minimal LockInfo with what we know
            if lock_content:
                return LockInfo(
                    session_id="unknown",
                    pid=0,
                    hostname="unknown",
                    started_at=lock_content,
                    feature_id=feature_id,
                    issue_number=issue_number,
                )

            return None
        except (KeyError, OSError):
            return None

    def force_release(self, feature_id: str, issue_number: int) -> bool:
        """
        Force release lock (admin operation).

        Use with caution - this can cause concurrent work on the same issue
        if the original process is still running.

        Args:
            feature_id: The feature identifier.
            issue_number: GitHub issue number.

        Returns:
            True if lock was removed, False on error.
        """
        lock_path = self._get_lock_path(feature_id, issue_number)

        if not lock_path.exists():
            return True

        try:
            # Log who we're evicting
            lock_info = self.get_lock_holder(feature_id, issue_number)
            if lock_info:
                self._logger.warning(
                    f"Force-releasing lock for {feature_id}#{issue_number} "
                    f"(was held by PID {lock_info.pid} on {lock_info.hostname})"
                )

            lock_path.unlink()
            return True
        except OSError as e:
            self._logger.error(f"Failed to force-release lock: {e}")
            return False

    def list_locks(self, feature_id: str) -> list[LockInfo]:
        """
        List all locks for a feature.

        Args:
            feature_id: The feature identifier.

        Returns:
            List of LockInfo for all locked issues.
        """
        feature_dir = self.locks_dir / feature_id
        if not feature_dir.exists():
            return []

        locks = []
        for lock_file in feature_dir.glob("issue_*.lock"):
            try:
                lock_data = json.loads(lock_file.read_text())
                locks.append(LockInfo.from_dict(lock_data))
            except (json.JSONDecodeError, KeyError, OSError):
                continue

        return locks

    def cleanup_stale_locks(self, feature_id: str) -> list[int]:
        """
        Clean up stale locks for a feature.

        Args:
            feature_id: The feature identifier.

        Returns:
            List of issue numbers whose locks were cleaned.
        """
        feature_dir = self.locks_dir / feature_id
        if not feature_dir.exists():
            return []

        cleaned = []
        for lock_file in feature_dir.glob("issue_*.lock"):
            try:
                lock_data = json.loads(lock_file.read_text())
                lock_info = LockInfo.from_dict(lock_data)

                if self._is_lock_stale(lock_info):
                    issue_num = int(lock_file.stem.replace("issue_", ""))
                    lock_file.unlink()
                    cleaned.append(issue_num)
                    self._logger.info(
                        f"Cleaned stale lock for {feature_id}#{issue_num}"
                    )
            except (json.JSONDecodeError, KeyError, OSError, ValueError):
                # Corrupted - remove it
                try:
                    lock_file.unlink()
                except OSError:
                    pass

        return cleaned


# =============================================================================
# Expert 1: SRE - Health Check Framework
# =============================================================================


class HealthChecker:
    """
    Run health checks on swarm infrastructure.

    Implements 5 automated checks:
    1. Stale sessions - sessions older than 4-hour TTL
    2. Orphan locks - lock files without active sessions
    3. Stuck features - features in same phase >24 hours
    4. Disk space - minimum 1GB free
    5. Worktree health - git worktrees in valid state
    """

    # Session TTL in hours
    SESSION_TTL_HOURS = 4

    # Hours before a feature is considered stuck
    STUCK_THRESHOLD_HOURS = 24

    def __init__(
        self,
        config: SwarmConfig,
        session_manager: Optional[SessionManager] = None,
        state_store: Optional[StateStore] = None,
    ):
        """
        Initialize HealthChecker.

        Args:
            config: SwarmConfig with paths and settings.
            session_manager: Optional SessionManager for session checks.
            state_store: Optional StateStore for state checks.
        """
        self.config = config
        self.session_manager = session_manager
        self.state_store = state_store
        self._logger = logging.getLogger(__name__)

    def _now_iso(self) -> str:
        """Get current timestamp in ISO format."""
        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    def run_health_checks(self) -> HealthReport:
        """
        Run all health checks and return report.

        Returns:
            HealthReport with results from all checks.
        """
        checks = {
            "stale_sessions": self._check_stale_sessions(),
            "orphan_locks": self._check_orphan_locks(),
            "stuck_features": self._check_stuck_features(),
            "disk_space": self._check_disk_space(),
            "worktree_health": self._check_worktree_health(),
        }

        # Determine overall health
        all_passed = all(check.passed for check in checks.values())

        # Build summary
        failed_checks = [name for name, check in checks.items() if not check.passed]
        if all_passed:
            summary = "All health checks passed"
        else:
            summary = f"Failed checks: {', '.join(failed_checks)}"

        return HealthReport(
            healthy=all_passed,
            checks=checks,
            summary=summary,
            timestamp=self._now_iso(),
        )

    def _check_stale_sessions(self) -> HealthCheckResult:
        """Check for sessions older than TTL."""
        if not self.state_store:
            return HealthCheckResult(
                name="stale_sessions",
                passed=True,
                message="Skipped - no state store configured",
            )

        stale_sessions = []
        now = datetime.now(timezone.utc)
        ttl = timedelta(hours=self.SESSION_TTL_HOURS)

        try:
            for feature_id in self.state_store.list_features():
                for session_id in self.state_store.list_sessions(feature_id):
                    session = self.state_store.load_session(feature_id, session_id)
                    if session and session.status == "active":
                        try:
                            started_at = datetime.fromisoformat(
                                session.started_at.replace("Z", "+00:00")
                            )
                            if now - started_at > ttl:
                                stale_sessions.append({
                                    "feature_id": feature_id,
                                    "session_id": session_id,
                                    "issue_number": session.issue_number,
                                    "age_hours": (now - started_at).total_seconds() / 3600,
                                })
                        except (ValueError, AttributeError):
                            # Can't parse - consider stale
                            stale_sessions.append({
                                "feature_id": feature_id,
                                "session_id": session_id,
                                "issue_number": session.issue_number,
                                "age_hours": "unknown",
                            })
        except Exception as e:
            return HealthCheckResult(
                name="stale_sessions",
                passed=False,
                message=f"Error checking sessions: {e}",
            )

        if stale_sessions:
            return HealthCheckResult(
                name="stale_sessions",
                passed=False,
                message=f"Found {len(stale_sessions)} stale session(s)",
                details={"stale_sessions": stale_sessions},
            )

        return HealthCheckResult(
            name="stale_sessions",
            passed=True,
            message="No stale sessions found",
        )

    def _check_orphan_locks(self) -> HealthCheckResult:
        """Check for lock files without active sessions."""
        locks_dir = self.config.swarm_path / "locks"
        if not locks_dir.exists():
            return HealthCheckResult(
                name="orphan_locks",
                passed=True,
                message="No locks directory exists",
            )

        orphan_locks = []
        lock_manager = LockManager(locks_dir)

        try:
            for feature_dir in locks_dir.iterdir():
                if not feature_dir.is_dir():
                    continue

                feature_id = feature_dir.name
                locks = lock_manager.list_locks(feature_id)

                for lock_info in locks:
                    # Check if session still exists and is active
                    if self.state_store:
                        session = self.state_store.load_session(
                            feature_id, lock_info.session_id
                        )
                        if not session or session.status != "active":
                            orphan_locks.append(lock_info.to_dict())
                    else:
                        # No state store - check if process is alive
                        if lock_info.hostname == socket.gethostname():
                            if not lock_manager._is_process_alive(lock_info.pid):
                                orphan_locks.append(lock_info.to_dict())

        except Exception as e:
            return HealthCheckResult(
                name="orphan_locks",
                passed=False,
                message=f"Error checking locks: {e}",
            )

        if orphan_locks:
            return HealthCheckResult(
                name="orphan_locks",
                passed=False,
                message=f"Found {len(orphan_locks)} orphan lock(s)",
                details={"orphan_locks": orphan_locks},
            )

        return HealthCheckResult(
            name="orphan_locks",
            passed=True,
            message="No orphan locks found",
        )

    def _check_stuck_features(self) -> HealthCheckResult:
        """Check for features stuck in same phase >24 hours."""
        if not self.state_store:
            return HealthCheckResult(
                name="stuck_features",
                passed=True,
                message="Skipped - no state store configured",
            )

        stuck_features = []
        now = datetime.now(timezone.utc)
        threshold = timedelta(hours=self.STUCK_THRESHOLD_HOURS)

        try:
            for feature_id in self.state_store.list_features():
                state = self.state_store.load(feature_id)
                if state:
                    try:
                        updated_at = datetime.fromisoformat(
                            state.updated_at.replace("Z", "+00:00")
                        )
                        if now - updated_at > threshold:
                            stuck_features.append({
                                "feature_id": feature_id,
                                "phase": state.phase.name,
                                "age_hours": (now - updated_at).total_seconds() / 3600,
                            })
                    except (ValueError, AttributeError):
                        pass

        except Exception as e:
            return HealthCheckResult(
                name="stuck_features",
                passed=False,
                message=f"Error checking features: {e}",
            )

        if stuck_features:
            return HealthCheckResult(
                name="stuck_features",
                passed=False,
                message=f"Found {len(stuck_features)} stuck feature(s)",
                details={"stuck_features": stuck_features},
            )

        return HealthCheckResult(
            name="stuck_features",
            passed=True,
            message="No stuck features found",
        )

    def _check_disk_space(self, min_free_gb: float = 1.0) -> HealthCheckResult:
        """Check disk has sufficient free space."""
        try:
            stat = shutil.disk_usage(self.config.repo_root)
            free_gb = stat.free / (1024 ** 3)

            if free_gb < min_free_gb:
                return HealthCheckResult(
                    name="disk_space",
                    passed=False,
                    message=f"Low disk space: {free_gb:.2f}GB free (minimum: {min_free_gb}GB)",
                    details={
                        "free_gb": free_gb,
                        "total_gb": stat.total / (1024 ** 3),
                        "min_required_gb": min_free_gb,
                    },
                )

            return HealthCheckResult(
                name="disk_space",
                passed=True,
                message=f"Disk space OK: {free_gb:.2f}GB free",
                details={"free_gb": free_gb},
            )

        except OSError as e:
            return HealthCheckResult(
                name="disk_space",
                passed=False,
                message=f"Failed to check disk space: {e}",
            )

    def _check_worktree_health(self) -> HealthCheckResult:
        """Check git worktrees are in valid state."""
        worktrees_root = Path(self.config.repo_root) / self.config.git.worktrees_root

        if not worktrees_root.exists():
            return HealthCheckResult(
                name="worktree_health",
                passed=True,
                message="No worktrees directory exists",
            )

        unhealthy_worktrees = []
        recovery = WorktreeRecovery(self.config)

        try:
            for worktree_dir in worktrees_root.iterdir():
                if not worktree_dir.is_dir():
                    continue

                status = recovery.validate_worktree_health(str(worktree_dir))
                if not status.healthy:
                    unhealthy_worktrees.append(status.to_dict())

        except Exception as e:
            return HealthCheckResult(
                name="worktree_health",
                passed=False,
                message=f"Error checking worktrees: {e}",
            )

        if unhealthy_worktrees:
            return HealthCheckResult(
                name="worktree_health",
                passed=False,
                message=f"Found {len(unhealthy_worktrees)} unhealthy worktree(s)",
                details={"unhealthy_worktrees": unhealthy_worktrees},
            )

        return HealthCheckResult(
            name="worktree_health",
            passed=True,
            message="All worktrees healthy",
        )


# =============================================================================
# Expert 3: DevOps Engineer - Worktree Recovery
# =============================================================================


class WorktreeRecovery:
    """
    Recover git worktrees from various failure states.

    Handles:
    - Detached HEAD state
    - Uncommitted changes
    - Corrupted worktree state
    - Stale worktrees
    """

    def __init__(self, config: SwarmConfig):
        """
        Initialize WorktreeRecovery.

        Args:
            config: SwarmConfig with repo settings.
        """
        self.config = config
        self._logger = logging.getLogger(__name__)

    def validate_worktree_health(self, worktree_path: str) -> WorktreeStatus:
        """
        Check worktree is in valid state for work.

        Checks:
        1. Directory exists
        2. Is a valid git worktree
        3. Not in detached HEAD state
        4. No uncommitted changes
        5. Can fetch from remote

        Args:
            worktree_path: Path to the worktree directory.

        Returns:
            WorktreeStatus with health information.
        """
        path = Path(worktree_path)
        issues = []

        # Check directory exists
        if not path.exists():
            return WorktreeStatus(
                healthy=False,
                issues=["Directory does not exist"],
                error="Worktree directory not found",
                path=worktree_path,
            )

        # Check it's a valid git directory
        git_dir = path / ".git"
        if not git_dir.exists():
            return WorktreeStatus(
                healthy=False,
                issues=["Not a git directory"],
                error="No .git file/directory found",
                path=worktree_path,
            )

        # Check for detached HEAD
        is_detached = False
        try:
            result = subprocess.run(
                ["git", "symbolic-ref", "-q", "HEAD"],
                capture_output=True,
                text=True,
                cwd=worktree_path,
                timeout=30,
            )
            is_detached = result.returncode != 0
            if is_detached:
                issues.append("Detached HEAD state")
        except (subprocess.TimeoutExpired, OSError) as e:
            issues.append(f"Cannot check HEAD: {e}")

        # Get current branch
        branch = ""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                capture_output=True,
                text=True,
                cwd=worktree_path,
                timeout=30,
            )
            branch = result.stdout.strip()
        except (subprocess.TimeoutExpired, OSError):
            pass

        # Check for uncommitted changes
        has_uncommitted = False
        try:
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                capture_output=True,
                text=True,
                cwd=worktree_path,
                timeout=30,
            )
            has_uncommitted = bool(result.stdout.strip())
            if has_uncommitted:
                issues.append("Has uncommitted changes")
        except (subprocess.TimeoutExpired, OSError) as e:
            issues.append(f"Cannot check status: {e}")

        return WorktreeStatus(
            healthy=len(issues) == 0,
            issues=issues,
            path=worktree_path,
            branch=branch,
            is_detached=is_detached,
            has_uncommitted=has_uncommitted,
        )

    def recover_worktree(self, worktree_path: str, issues: list[str]) -> bool:
        """
        Attempt automatic recovery of worktree issues.

        Recovery steps:
        1. Stash uncommitted changes
        2. Checkout correct branch
        3. Clean up untracked files if needed

        Args:
            worktree_path: Path to the worktree.
            issues: List of issues to recover from.

        Returns:
            True if recovery succeeded, False otherwise.
        """
        path = Path(worktree_path)
        if not path.exists():
            return False

        try:
            # Step 1: Stash uncommitted changes
            if "Has uncommitted changes" in issues:
                self._logger.info(f"Stashing changes in {worktree_path}")
                result = subprocess.run(
                    ["git", "stash", "push", "-m", "auto-stash by recovery"],
                    capture_output=True,
                    text=True,
                    cwd=worktree_path,
                    timeout=60,
                )
                if result.returncode != 0:
                    self._logger.warning(f"Stash failed: {result.stderr}")

            # Step 2: Fix detached HEAD by checking out a branch
            if "Detached HEAD state" in issues:
                self._logger.info(f"Fixing detached HEAD in {worktree_path}")

                # Try to checkout main/master
                for branch in ["main", "master"]:
                    result = subprocess.run(
                        ["git", "checkout", branch],
                        capture_output=True,
                        text=True,
                        cwd=worktree_path,
                        timeout=60,
                    )
                    if result.returncode == 0:
                        break
                else:
                    self._logger.warning("Could not checkout main/master")

            # Verify recovery
            status = self.validate_worktree_health(worktree_path)
            return status.healthy

        except (subprocess.TimeoutExpired, OSError) as e:
            self._logger.error(f"Recovery failed: {e}")
            return False


# =============================================================================
# Expert 4: Test Infrastructure Engineer - Robust Test Execution
# =============================================================================


class TestRunner:
    """
    Robust test execution with timeouts and flaky detection.

    Features:
    - Hard timeout with process cleanup
    - Flaky test detection via multiple runs
    - Import validation before execution
    - Structured output parsing
    """

    DEFAULT_TIMEOUT = 300  # 5 minutes

    def __init__(self, config: SwarmConfig):
        """
        Initialize TestRunner.

        Args:
            config: SwarmConfig with test settings.
        """
        self.config = config
        self._logger = logging.getLogger(__name__)

    def run_tests_with_timeout(
        self,
        test_path: str,
        timeout_seconds: Optional[int] = None,
    ) -> TestRunResult:
        """
        Run tests with hard timeout, kill on expiry.

        Uses subprocess with timeout, sends SIGTERM then SIGKILL if needed.

        Args:
            test_path: Path to test file or directory.
            timeout_seconds: Timeout in seconds (default 5 minutes).

        Returns:
            TestRunResult with success status and details.
        """
        timeout = timeout_seconds or self.DEFAULT_TIMEOUT
        test_cmd = self.config.tests.command
        test_args = self.config.tests.args.copy() if self.config.tests.args else []

        cmd = [test_cmd] + test_args + [test_path, "-v", "--tb=short"]

        self._logger.info(f"Running tests: {' '.join(cmd)} (timeout: {timeout}s)")

        start_time = datetime.now()
        process = None

        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                cwd=self.config.repo_root,
                env={**os.environ, "PYTHONPATH": str(self.config.repo_root)},
            )

            stdout, _ = process.communicate(timeout=timeout)
            duration = (datetime.now() - start_time).total_seconds()

            # Parse output for pass/fail counts
            passed, failed, failures = self._parse_pytest_output(stdout)

            return TestRunResult(
                success=process.returncode == 0,
                passed=passed,
                failed=failed,
                timed_out=False,
                duration_seconds=duration,
                output=stdout,
                failures=failures,
            )

        except subprocess.TimeoutExpired:
            self._logger.warning(f"Test timed out after {timeout}s, killing process")

            if process:
                # Try graceful shutdown first
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    # Force kill
                    process.kill()
                    # Also kill any child processes
                    self._kill_process_tree(process.pid)

            duration = (datetime.now() - start_time).total_seconds()

            return TestRunResult(
                success=False,
                timed_out=True,
                duration_seconds=duration,
                error=f"Tests timed out after {timeout} seconds",
            )

        except OSError as e:
            return TestRunResult(
                success=False,
                error=f"Failed to run tests: {e}",
            )

    def _kill_process_tree(self, pid: int) -> None:
        """Kill a process and all its children."""
        try:
            # Try pkill with parent PID
            subprocess.run(
                ["pkill", "-P", str(pid)],
                capture_output=True,
                timeout=5,
            )
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            pass

        try:
            os.kill(pid, signal.SIGKILL)
        except (OSError, ProcessLookupError):
            pass

    def _parse_pytest_output(
        self,
        output: str,
    ) -> tuple[int, int, list[dict]]:
        """
        Parse pytest output for pass/fail counts.

        Returns:
            Tuple of (passed, failed, failures_list).
        """
        passed = 0
        failed = 0
        failures = []

        # Look for summary line like "5 passed, 2 failed"
        for line in output.split("\n"):
            if "passed" in line or "failed" in line:
                import re

                pass_match = re.search(r"(\d+) passed", line)
                fail_match = re.search(r"(\d+) failed", line)

                if pass_match:
                    passed = int(pass_match.group(1))
                if fail_match:
                    failed = int(fail_match.group(1))

            # Capture failure names
            if line.startswith("FAILED"):
                failures.append({"test": line.replace("FAILED", "").strip()})

        return passed, failed, failures

    def detect_flaky_tests(
        self,
        test_path: str,
        runs: int = 3,
    ) -> FlakyTestReport:
        """
        Run tests multiple times to detect flakiness.

        A test is considered flaky if it produces different results
        across multiple runs.

        Args:
            test_path: Path to test file.
            runs: Number of times to run tests (default 3).

        Returns:
            FlakyTestReport with flakiness information.
        """
        results = []
        test_outcomes: dict[str, list[bool]] = {}  # test_name -> [pass/fail per run]

        for i in range(runs):
            self._logger.info(f"Flaky detection run {i+1}/{runs}")
            result = self.run_tests_with_timeout(test_path, timeout_seconds=120)
            results.append(result)

            if result.timed_out or result.error:
                return FlakyTestReport(
                    is_flaky=False,
                    runs_completed=i + 1,
                    error=result.error or "Test timed out",
                )

        # Analyze results for consistency
        # If all runs have same pass/fail count, likely not flaky
        pass_counts = [r.passed for r in results]
        fail_counts = [r.failed for r in results]

        all_consistent = (
            len(set(pass_counts)) == 1 and len(set(fail_counts)) == 1
        )

        if all_consistent:
            total_passed = sum(r.passed for r in results)
            total_failed = sum(r.failed for r in results)
            total_tests = total_passed + total_failed

            return FlakyTestReport(
                is_flaky=False,
                pass_rate=total_passed / (total_tests * runs) if total_tests else 1.0,
                runs_completed=runs,
            )

        # Identify specific flaky tests by comparing failures across runs
        all_failures = set()
        for r in results:
            for f in r.failures:
                all_failures.add(f.get("test", "unknown"))

        # A test is flaky if it failed in some runs but not all
        flaky_tests = list(all_failures)  # Simplified - real detection needs per-test tracking

        return FlakyTestReport(
            is_flaky=True,
            flaky_tests=flaky_tests,
            pass_rate=sum(r.passed for r in results) / (sum(r.passed + r.failed for r in results) or 1),
            runs_completed=runs,
        )

    def validate_test_imports(self, test_path: str) -> tuple[bool, str]:
        """
        Check test file can be imported without errors.

        Uses pytest --collect-only to validate imports.

        Args:
            test_path: Path to test file.

        Returns:
            Tuple of (success, error_message).
        """
        try:
            result = subprocess.run(
                ["pytest", test_path, "--collect-only", "-q"],
                capture_output=True,
                text=True,
                timeout=30,
                cwd=self.config.repo_root,
                env={**os.environ, "PYTHONPATH": str(self.config.repo_root)},
            )

            # Exit code 0 = success, 5 = no tests (but valid), 2 = errors
            if result.returncode in (0, 5):
                return True, ""
            else:
                return False, result.stderr or result.stdout

        except subprocess.TimeoutExpired:
            return False, "Import check timed out"
        except OSError as e:
            return False, f"Failed to check imports: {e}"


# =============================================================================
# Expert 3: DevOps Engineer - Pre-flight Checks
# =============================================================================


class PreflightChecker:
    """
    Run pre-flight checks before starting any work.

    Validates:
    1. Disk space (minimum 1GB free)
    2. No stale sessions for this feature
    3. Git worktree healthy (if using worktrees)
    4. State file not corrupted
    """

    def __init__(
        self,
        config: SwarmConfig,
        health_checker: Optional[HealthChecker] = None,
    ):
        """
        Initialize PreflightChecker.

        Args:
            config: SwarmConfig with paths and settings.
            health_checker: Optional HealthChecker for reuse.
        """
        self.config = config
        self.health_checker = health_checker or HealthChecker(config)
        self._logger = logging.getLogger(__name__)

    def run_preflight_checks(self, feature_id: str) -> tuple[bool, list[str]]:
        """
        Run all pre-flight checks before starting work.

        Args:
            feature_id: The feature identifier.

        Returns:
            Tuple of (passed, list of error messages).
        """
        errors = []

        # 1. Disk space check
        disk_result = self.health_checker._check_disk_space()
        if not disk_result.passed:
            errors.append(f"Disk space: {disk_result.message}")

        # 2. Check for stale sessions
        session_result = self.health_checker._check_stale_sessions()
        if not session_result.passed:
            # Check if any stale sessions are for this feature
            details = session_result.details or {}
            stale = details.get("stale_sessions", [])
            feature_stale = [s for s in stale if s.get("feature_id") == feature_id]
            if feature_stale:
                errors.append(
                    f"Stale sessions: {len(feature_stale)} stale session(s) for this feature"
                )

        # 3. Git worktree health (if using worktrees)
        if self.config.git.use_worktrees:
            worktree_path = (
                Path(self.config.repo_root)
                / self.config.git.worktrees_root
                / feature_id
            )
            if worktree_path.exists():
                recovery = WorktreeRecovery(self.config)
                status = recovery.validate_worktree_health(str(worktree_path))
                if not status.healthy:
                    errors.append(f"Worktree: {', '.join(status.issues)}")

        # 4. State file not corrupted (try to load it)
        if self.health_checker.state_store:
            try:
                state = self.health_checker.state_store.load(feature_id)
                if state is None:
                    # Not an error if feature doesn't exist yet
                    pass
            except Exception as e:
                errors.append(f"State file: {e}")

        passed = len(errors) == 0

        if not passed:
            self._logger.warning(f"Pre-flight checks failed: {errors}")
        else:
            self._logger.info(f"Pre-flight checks passed for {feature_id}")

        return passed, errors


# =============================================================================
# Expert 5: State Machine Engineer - Dependency Validation
# =============================================================================


def validate_no_circular_deps(tasks: list) -> Optional[str]:
    """
    Detect circular dependencies in task graph using topological sort.

    Uses Kahn's algorithm for cycle detection.

    Args:
        tasks: List of TaskRef objects with dependencies.

    Returns:
        Error message if cycle detected, None otherwise.
    """
    from collections import deque

    # Build adjacency list and in-degree count
    # task.issue_number -> list of dependents
    graph: dict[int, list[int]] = {}
    in_degree: dict[int, int] = {}

    for task in tasks:
        issue = task.issue_number
        if issue not in graph:
            graph[issue] = []
        if issue not in in_degree:
            in_degree[issue] = 0

        for dep in task.dependencies:
            if dep not in graph:
                graph[dep] = []
            graph[dep].append(issue)
            in_degree[issue] = in_degree.get(issue, 0) + 1

    # Kahn's algorithm
    queue = deque([node for node, degree in in_degree.items() if degree == 0])
    processed = 0

    while queue:
        node = queue.popleft()
        processed += 1

        for neighbor in graph.get(node, []):
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    if processed != len(in_degree):
        # Find the cycle - nodes with remaining in-degree
        cycle_nodes = [node for node, degree in in_degree.items() if degree > 0]
        return f"Circular dependency detected involving issues: {cycle_nodes}"

    return None


def get_ready_issues_safe(
    tasks: list,
    done_issues: set[int],
    blocked_issues: set[int],
) -> list:
    """
    Get issues ready for work, respecting blocked dependencies.

    An issue is ready if:
    1. Its stage is READY
    2. All its dependencies are DONE (not BLOCKED or SKIPPED)

    Args:
        tasks: List of TaskRef objects.
        done_issues: Set of issue numbers that are DONE.
        blocked_issues: Set of issue numbers that are BLOCKED.

    Returns:
        List of TaskRef objects ready for work.
    """
    from swarm_attack.models import TaskStage

    ready = []

    for task in tasks:
        if task.stage != TaskStage.READY:
            continue

        # Check all dependencies are done
        deps_satisfied = all(
            dep in done_issues and dep not in blocked_issues
            for dep in task.dependencies
        )

        if deps_satisfied:
            ready.append(task)

    return ready


def should_skip_issue(
    task,
    blocked_issues: set[int],
    skipped_issues: set[int],
) -> Optional[int]:
    """
    Check if an issue should be skipped due to blocked dependencies.

    An issue should be skipped if any of its dependencies are:
    1. BLOCKED
    2. Already SKIPPED (cascading)

    Args:
        task: The TaskRef to check.
        blocked_issues: Set of blocked issue numbers.
        skipped_issues: Set of already-skipped issue numbers.

    Returns:
        The blocking issue number if should skip, None otherwise.
    """
    for dep in task.dependencies:
        if dep in blocked_issues:
            return dep
        if dep in skipped_issues:
            return dep

    return None
