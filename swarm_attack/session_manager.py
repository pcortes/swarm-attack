"""
Session Manager for Feature Swarm.

This module handles:
- One issue per session enforcement
- Checkpoint creation at each stage
- Recovery from interrupted sessions
- Session state persistence

Session Lifecycle:
1. start_session() - Claim an issue, create session
2. add_checkpoint() - Record progress at each stage
3. add_commit() - Track git commits
4. end_session() - Mark session as complete/failed/blocked

Interrupt Handling:
- If a session is left "active" but no process owns it, it's considered interrupted
- Interrupted sessions can be resumed via resume_session()
"""

from __future__ import annotations

import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

from swarm_attack.models import CheckpointData, SessionState

if TYPE_CHECKING:
    from swarm_attack.config import SwarmConfig
    from swarm_attack.logger import SwarmLogger
    from swarm_attack.state_store import StateStore


class SessionError(Exception):
    """Base exception for session errors."""
    pass


class SessionAlreadyActiveError(SessionError):
    """Raised when trying to start a session while one is already active."""
    pass


class SessionNotFoundError(SessionError):
    """Raised when a session cannot be found."""
    pass


class SessionManager:
    """
    Manages work sessions for Feature Swarm.

    Each session tracks work on a single GitHub issue, including:
    - Checkpoints (progress markers)
    - Git commits
    - Cost tracking
    - Status (active, complete, interrupted)

    Enforces one issue per session.

    TTL and Stale Detection (Expert 1 - SRE):
    - Sessions expire after 4 hours of inactivity (SESSION_TTL_HOURS)
    - Stale sessions are auto-detected and can be cleaned up
    - Task state is synchronized when session ends
    """

    # Session TTL in hours - sessions without activity for this long are stale
    SESSION_TTL_HOURS = 4

    def __init__(
        self,
        config: SwarmConfig,
        state_store: StateStore,
        logger: Optional[SwarmLogger] = None,
    ) -> None:
        """
        Initialize the SessionManager.

        Args:
            config: SwarmConfig with paths and settings.
            state_store: StateStore for persistence.
            logger: Optional logger for recording operations.
        """
        self.config = config
        self.state_store = state_store
        self.logger = logger

    def _log(
        self,
        event_type: str,
        data: Optional[dict] = None,
        level: str = "info"
    ) -> None:
        """Log an event if logger is configured."""
        if self.logger:
            self.logger.log(event_type, data, level=level)

    def _generate_session_id(self) -> str:
        """Generate a unique session ID."""
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
        return f"sess_{timestamp}"

    def _now_iso(self) -> str:
        """Get current timestamp in ISO format."""
        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    def _get_feature_id_from_session(self, session_id: str) -> Optional[str]:
        """
        Find which feature a session belongs to.

        This searches through all features to find the session.
        Returns None if not found.
        """
        for feature_id in self.state_store.list_features():
            sessions = self.state_store.list_sessions(feature_id)
            if session_id in sessions:
                return feature_id
        return None

    # =========================================================================
    # Session Creation
    # =========================================================================

    def start_session(
        self,
        feature_id: str,
        issue_number: int,
        worktree_path: Optional[str] = None,
    ) -> SessionState:
        """
        Start a new session for working on an issue.

        Args:
            feature_id: The feature identifier.
            issue_number: GitHub issue number to work on.
            worktree_path: Optional path to git worktree.

        Returns:
            The created SessionState.

        Raises:
            SessionError: If feature doesn't exist.
            SessionAlreadyActiveError: If another session is already active.
        """
        # Verify feature exists
        state = self.state_store.load(feature_id)
        if state is None:
            raise SessionError(f"Feature '{feature_id}' not found")

        # Check for existing active session
        active = self.get_active_session(feature_id)
        if active is not None:
            raise SessionAlreadyActiveError(
                f"Session '{active.session_id}' is already active for feature "
                f"'{feature_id}' (working on issue #{active.issue_number})"
            )

        # Create new session
        session_id = self._generate_session_id()
        session = SessionState(
            session_id=session_id,
            feature_id=feature_id,
            issue_number=issue_number,
            started_at=self._now_iso(),
            status="active",
            worktree_path=worktree_path,
        )

        # Save session
        self.state_store.save_session(session)

        # Update run state with current session
        state.current_session = session_id
        self.state_store.save(state)

        self._log(
            "session_started",
            {
                "session_id": session_id,
                "feature_id": feature_id,
                "issue_number": issue_number,
            },
        )

        return session

    # =========================================================================
    # Session Retrieval
    # =========================================================================

    def get_session(
        self,
        feature_id: str,
        session_id: str,
    ) -> Optional[SessionState]:
        """
        Get a session by ID.

        Args:
            feature_id: The feature identifier.
            session_id: The session identifier.

        Returns:
            SessionState if found, None otherwise.
        """
        return self.state_store.load_session(feature_id, session_id)

    def get_active_session(self, feature_id: str) -> Optional[SessionState]:
        """
        Get the active session for a feature.

        Args:
            feature_id: The feature identifier.

        Returns:
            Active SessionState or None if no active session.
        """
        return self.state_store.get_active_session(feature_id)

    def has_active_session(self, feature_id: str) -> bool:
        """
        Check if a feature has an active session.

        Args:
            feature_id: The feature identifier.

        Returns:
            True if an active session exists.
        """
        return self.get_active_session(feature_id) is not None

    def get_latest_session(self, feature_id: str) -> Optional[SessionState]:
        """
        Get the most recent session for a feature.

        Args:
            feature_id: The feature identifier.

        Returns:
            Most recent SessionState or None.
        """
        return self.state_store.get_latest_session(feature_id)

    def list_sessions(self, feature_id: str) -> list[str]:
        """
        List all session IDs for a feature.

        Args:
            feature_id: The feature identifier.

        Returns:
            List of session ID strings.
        """
        return self.state_store.list_sessions(feature_id)

    # =========================================================================
    # Checkpoints
    # =========================================================================

    def add_checkpoint(
        self,
        session_id: str,
        agent: str,
        status: str,
        commit: Optional[str] = None,
        cost_usd: float = 0.0,
    ) -> SessionState:
        """
        Add a checkpoint to a session.

        Args:
            session_id: The session identifier.
            agent: Name of the agent creating the checkpoint.
            status: Status at checkpoint (e.g., "complete", "in_progress").
            commit: Optional git commit hash.
            cost_usd: Cost incurred at this checkpoint.

        Returns:
            Updated SessionState.

        Raises:
            SessionNotFoundError: If session doesn't exist.
            SessionError: If session is not active.
        """
        # Find the feature for this session
        feature_id = self._get_feature_id_from_session(session_id)
        if feature_id is None:
            raise SessionNotFoundError(f"Session '{session_id}' not found")

        session = self.state_store.load_session(feature_id, session_id)
        if session is None:
            raise SessionNotFoundError(f"Session '{session_id}' not found")

        if session.status != "active":
            raise SessionError(
                f"Cannot add checkpoint: session '{session_id}' is not active "
                f"(status: {session.status})"
            )

        # Create checkpoint
        checkpoint = CheckpointData(
            agent=agent,
            status=status,
            timestamp=self._now_iso(),
            commit=commit,
            cost_usd=cost_usd,
        )

        # Add to session
        session.checkpoints.append(checkpoint)
        session.cost_usd += cost_usd

        # Save
        self.state_store.save_session(session)

        self._log(
            "checkpoint_added",
            {
                "session_id": session_id,
                "agent": agent,
                "status": status,
                "cost_usd": cost_usd,
            },
        )

        return session

    # =========================================================================
    # Git Commit Tracking
    # =========================================================================

    def add_commit(
        self,
        session_id: str,
        commit_hash: str,
    ) -> SessionState:
        """
        Add a git commit to a session.

        Args:
            session_id: The session identifier.
            commit_hash: The git commit hash.

        Returns:
            Updated SessionState.

        Raises:
            SessionNotFoundError: If session doesn't exist.
        """
        feature_id = self._get_feature_id_from_session(session_id)
        if feature_id is None:
            raise SessionNotFoundError(f"Session '{session_id}' not found")

        session = self.state_store.load_session(feature_id, session_id)
        if session is None:
            raise SessionNotFoundError(f"Session '{session_id}' not found")

        session.commits.append(commit_hash)
        self.state_store.save_session(session)

        self._log(
            "commit_added",
            {
                "session_id": session_id,
                "commit_hash": commit_hash,
            },
        )

        return session

    # =========================================================================
    # Session Ending
    # =========================================================================

    def end_session(
        self,
        session_id: str,
        end_status: str,
    ) -> SessionState:
        """
        End a session.

        Args:
            session_id: The session identifier.
            end_status: Final status ("success", "failed", "blocked").

        Returns:
            Updated SessionState.

        Raises:
            SessionNotFoundError: If session doesn't exist.
            SessionError: If session is already ended.
        """
        feature_id = self._get_feature_id_from_session(session_id)
        if feature_id is None:
            raise SessionNotFoundError(f"Session '{session_id}' not found")

        session = self.state_store.load_session(feature_id, session_id)
        if session is None:
            raise SessionNotFoundError(f"Session '{session_id}' not found")

        if session.status == "complete":
            raise SessionError(
                f"Session '{session_id}' is already completed"
            )

        if session.status == "interrupted":
            # Allow ending interrupted sessions
            pass

        # Update session
        session.status = "complete"
        session.end_status = end_status
        session.ended_at = self._now_iso()

        # Save session
        self.state_store.save_session(session)

        # Clear current_session from run state
        state = self.state_store.load(feature_id)
        if state and state.current_session == session_id:
            state.current_session = None
            self.state_store.save(state)

        self._log(
            "session_ended",
            {
                "session_id": session_id,
                "feature_id": feature_id,
                "end_status": end_status,
                "cost_usd": session.cost_usd,
            },
        )

        return session

    # =========================================================================
    # Interrupt Handling
    # =========================================================================

    def get_interrupted_session(
        self,
        feature_id: str,
    ) -> Optional[SessionState]:
        """
        Get an interrupted or orphaned active session.

        An active session without an owning process is considered interrupted.

        Args:
            feature_id: The feature identifier.

        Returns:
            Interrupted/orphaned SessionState or None.
        """
        # Check for any active session (which is orphaned since we just started)
        return self.get_active_session(feature_id)

    def mark_as_interrupted(
        self,
        session_id: str,
    ) -> SessionState:
        """
        Mark a session as interrupted.

        Args:
            session_id: The session identifier.

        Returns:
            Updated SessionState.

        Raises:
            SessionNotFoundError: If session doesn't exist.
        """
        feature_id = self._get_feature_id_from_session(session_id)
        if feature_id is None:
            raise SessionNotFoundError(f"Session '{session_id}' not found")

        session = self.state_store.load_session(feature_id, session_id)
        if session is None:
            raise SessionNotFoundError(f"Session '{session_id}' not found")

        session.status = "interrupted"
        self.state_store.save_session(session)

        # Clear current_session from run state
        state = self.state_store.load(feature_id)
        if state and state.current_session == session_id:
            state.current_session = None
            self.state_store.save(state)

        self._log(
            "session_interrupted",
            {
                "session_id": session_id,
                "feature_id": feature_id,
            },
        )

        return session

    def resume_session(
        self,
        session_id: str,
    ) -> SessionState:
        """
        Resume an interrupted session.

        Args:
            session_id: The session identifier.

        Returns:
            Resumed SessionState.

        Raises:
            SessionNotFoundError: If session doesn't exist.
            SessionError: If session cannot be resumed.
        """
        feature_id = self._get_feature_id_from_session(session_id)
        if feature_id is None:
            raise SessionNotFoundError(f"Session '{session_id}' not found")

        session = self.state_store.load_session(feature_id, session_id)
        if session is None:
            raise SessionNotFoundError(f"Session '{session_id}' not found")

        if session.status == "complete":
            raise SessionError(
                f"Cannot resume session '{session_id}': already completed"
            )

        # Check for other active sessions
        active = self.get_active_session(feature_id)
        if active is not None and active.session_id != session_id:
            raise SessionAlreadyActiveError(
                f"Cannot resume: session '{active.session_id}' is already active"
            )

        # Resume
        session.status = "active"
        self.state_store.save_session(session)

        # Update run state
        state = self.state_store.load(feature_id)
        if state:
            state.current_session = session_id
            self.state_store.save(state)

        self._log(
            "session_resumed",
            {
                "session_id": session_id,
                "feature_id": feature_id,
                "checkpoints_count": len(session.checkpoints),
            },
        )

        return session

    def get_interrupted_sessions(
        self,
        feature_id: str,
    ) -> list[SessionState]:
        """
        Find sessions that were interrupted (status == 'active' or 'interrupted').

        This returns all non-complete sessions, unlike get_interrupted_session
        which only returns a single one.

        Args:
            feature_id: The feature identifier.

        Returns:
            List of interrupted SessionState objects.
        """
        interrupted = []
        session_ids = self.state_store.list_sessions(feature_id)

        for session_id in session_ids:
            session = self.state_store.load_session(feature_id, session_id)
            if session is not None and session.status in ("active", "interrupted"):
                interrupted.append(session)

        return interrupted

    # =========================================================================
    # Feature Branch Management
    # =========================================================================

    def get_feature_branch(self, feature_id: str) -> str:
        """
        Get feature branch name for a feature.

        Uses the pattern from config.git.feature_branch_pattern.

        Args:
            feature_id: The feature identifier (slug).

        Returns:
            Branch name string.
        """
        pattern = self.config.git.feature_branch_pattern
        return pattern.format(feature_slug=feature_id)

    def ensure_feature_branch(self, feature_id: str) -> str:
        """
        Create feature/<slug> branch if it doesn't exist.

        Args:
            feature_id: The feature identifier.

        Returns:
            Branch name string.
        """
        branch_name = self.get_feature_branch(feature_id)

        # Check if branch exists
        result = subprocess.run(
            ["git", "branch", "--list", branch_name],
            capture_output=True,
            text=True,
            cwd=self.config.repo_root,
        )

        if branch_name not in result.stdout:
            # Branch doesn't exist, create it from base branch
            base_branch = self.config.git.base_branch
            subprocess.run(
                ["git", "checkout", "-b", branch_name, base_branch],
                capture_output=True,
                text=True,
                cwd=self.config.repo_root,
            )

            self._log(
                "feature_branch_created",
                {
                    "feature_id": feature_id,
                    "branch_name": branch_name,
                },
            )
        else:
            self._log(
                "feature_branch_exists",
                {
                    "feature_id": feature_id,
                    "branch_name": branch_name,
                },
            )

        return branch_name

    # =========================================================================
    # Issue Locking
    # =========================================================================

    def claim_issue(
        self,
        feature_id: str,
        issue_number: int,
    ) -> bool:
        """
        Lock an issue for this session.

        Prevents concurrent work on the same issue.

        Args:
            feature_id: The feature identifier.
            issue_number: GitHub issue number.

        Returns:
            True if claimed successfully, False if already claimed.
        """
        lock_dir = self.config.swarm_path / "locks" / feature_id
        lock_dir.mkdir(parents=True, exist_ok=True)

        lock_file = lock_dir / f"issue_{issue_number}.lock"

        if lock_file.exists():
            # Check if lock is stale
            try:
                lock_data = lock_file.read_text()
                # Lock file contains timestamp
                if lock_data:
                    locked_at = datetime.fromisoformat(lock_data.replace("Z", "+00:00"))
                    stale_timeout = self.config.sessions.stale_timeout_minutes
                    if datetime.now(timezone.utc) - locked_at < timedelta(minutes=stale_timeout):
                        # Lock is still valid
                        return False
            except (ValueError, OSError):
                pass  # Corrupted lock, we can claim it

        # Create lock
        lock_file.write_text(self._now_iso())

        self._log(
            "issue_claimed",
            {
                "feature_id": feature_id,
                "issue_number": issue_number,
            },
        )

        return True

    def release_issue(
        self,
        feature_id: str,
        issue_number: int,
    ) -> None:
        """
        Release an issue lock.

        Args:
            feature_id: The feature identifier.
            issue_number: GitHub issue number.
        """
        lock_file = self.config.swarm_path / "locks" / feature_id / f"issue_{issue_number}.lock"

        if lock_file.exists():
            lock_file.unlink()

            self._log(
                "issue_released",
                {
                    "feature_id": feature_id,
                    "issue_number": issue_number,
                },
            )

    def clean_stale_locks(
        self,
        feature_id: str,
    ) -> list[int]:
        """
        Clean up stale issue locks for a feature.

        Locks are considered stale if they are older than stale_timeout_minutes.
        This should be called on startup before attempting to claim new issues
        to ensure interrupted processes don't leave orphaned locks.

        Args:
            feature_id: The feature identifier.

        Returns:
            List of issue numbers whose locks were cleaned.
        """
        lock_dir = self.config.swarm_path / "locks" / feature_id
        if not lock_dir.exists():
            return []

        stale_timeout = self.config.sessions.stale_timeout_minutes
        now = datetime.now(timezone.utc)
        cleaned_issues: list[int] = []

        # Find all lock files for this feature
        for lock_file in lock_dir.glob("issue_*.lock"):
            try:
                # Extract issue number from filename
                issue_num_str = lock_file.stem.replace("issue_", "")
                issue_number = int(issue_num_str)

                # Read lock timestamp
                lock_data = lock_file.read_text().strip()
                if not lock_data:
                    # Empty lock file is considered stale
                    lock_file.unlink()
                    cleaned_issues.append(issue_number)
                    continue

                # Parse timestamp and check if stale
                locked_at = datetime.fromisoformat(lock_data.replace("Z", "+00:00"))
                age = now - locked_at

                if age >= timedelta(minutes=stale_timeout):
                    lock_file.unlink()
                    cleaned_issues.append(issue_number)
                    self._log(
                        "stale_lock_cleaned",
                        {
                            "feature_id": feature_id,
                            "issue_number": issue_number,
                            "lock_age_minutes": age.total_seconds() / 60,
                            "stale_timeout_minutes": stale_timeout,
                        },
                    )

            except (ValueError, OSError) as e:
                # Corrupted lock file - remove it
                try:
                    lock_file.unlink()
                    self._log(
                        "corrupted_lock_cleaned",
                        {
                            "feature_id": feature_id,
                            "lock_file": str(lock_file),
                            "error": str(e),
                        },
                        level="warning",
                    )
                except OSError:
                    pass

        if cleaned_issues:
            self._log(
                "stale_locks_cleaned",
                {
                    "feature_id": feature_id,
                    "cleaned_count": len(cleaned_issues),
                    "cleaned_issues": cleaned_issues,
                },
            )

        return cleaned_issues

    def clear_all_locks(
        self,
        feature_id: str,
    ) -> list[int]:
        """
        Clear ALL issue locks for a feature (regardless of age).

        This is a manual override used when automation fails and
        the user needs to force-clear locks.

        Args:
            feature_id: The feature identifier.

        Returns:
            List of issue numbers whose locks were cleared.
        """
        lock_dir = self.config.swarm_path / "locks" / feature_id
        if not lock_dir.exists():
            return []

        cleared_issues: list[int] = []

        for lock_file in lock_dir.glob("issue_*.lock"):
            try:
                issue_num_str = lock_file.stem.replace("issue_", "")
                issue_number = int(issue_num_str)
                lock_file.unlink()
                cleared_issues.append(issue_number)
            except (ValueError, OSError):
                # Try to remove anyway
                try:
                    lock_file.unlink()
                except OSError:
                    pass

        if cleared_issues:
            self._log(
                "locks_force_cleared",
                {
                    "feature_id": feature_id,
                    "cleared_count": len(cleared_issues),
                    "cleared_issues": cleared_issues,
                },
            )

        return cleared_issues

    def detect_stale_sessions(
        self,
        feature_id: str,
    ) -> list[SessionState]:
        """
        Find sessions older than stale_timeout_minutes.

        Args:
            feature_id: The feature identifier.

        Returns:
            List of stale SessionState objects.
        """
        stale = []
        stale_timeout = self.config.sessions.stale_timeout_minutes
        now = datetime.now(timezone.utc)

        session_ids = self.state_store.list_sessions(feature_id)

        for session_id in session_ids:
            session = self.state_store.load_session(feature_id, session_id)
            if session is None:
                continue

            # Only check active sessions
            if session.status != "active":
                continue

            # Parse started_at and check age
            try:
                started_at = datetime.fromisoformat(
                    session.started_at.replace("Z", "+00:00")
                )
                age_minutes = (now - started_at).total_seconds() / 60
                if age_minutes >= stale_timeout:
                    stale.append(session)
            except (ValueError, AttributeError):
                # Can't parse timestamp, consider it stale
                stale.append(session)

        return stale

    # =========================================================================
    # Issue Commit Tracking
    # =========================================================================

    def get_commits_for_issue(
        self,
        feature_id: str,
        issue_number: int,
    ) -> list[str]:
        """
        Get all commits for an issue across sessions.

        Args:
            feature_id: The feature identifier.
            issue_number: GitHub issue number.

        Returns:
            List of commit hash strings.
        """
        commits = []
        session_ids = self.state_store.list_sessions(feature_id)

        for session_id in session_ids:
            session = self.state_store.load_session(feature_id, session_id)
            if session is not None and session.issue_number == issue_number:
                commits.extend(session.commits)

        return commits

    # =========================================================================
    # Rollback Operations
    # =========================================================================

    def rollback_session(
        self,
        session_id: str,
    ) -> None:
        """
        Rollback a session by reverting its commits.

        Args:
            session_id: The session identifier.

        Raises:
            SessionNotFoundError: If session doesn't exist.
        """
        feature_id = self._get_feature_id_from_session(session_id)
        if feature_id is None:
            raise SessionNotFoundError(f"Session '{session_id}' not found")

        session = self.state_store.load_session(feature_id, session_id)
        if session is None:
            raise SessionNotFoundError(f"Session '{session_id}' not found")

        # Revert commits in reverse order
        for commit_hash in reversed(session.commits):
            subprocess.run(
                ["git", "revert", "--no-commit", commit_hash],
                capture_output=True,
                text=True,
                cwd=self.config.repo_root,
            )

        if session.commits:
            # Commit the reverts
            subprocess.run(
                ["git", "commit", "-m", f"Rollback session {session_id}"],
                capture_output=True,
                text=True,
                cwd=self.config.repo_root,
            )

        self._log(
            "session_rollback",
            {
                "session_id": session_id,
                "feature_id": feature_id,
                "commits_reverted": len(session.commits),
            },
        )

    def rollback_issue(
        self,
        feature_id: str,
        issue_number: int,
    ) -> None:
        """
        Rollback all commits for an issue.

        Args:
            feature_id: The feature identifier.
            issue_number: GitHub issue number.
        """
        commits = self.get_commits_for_issue(feature_id, issue_number)

        if not commits:
            self._log(
                "rollback_issue_no_commits",
                {
                    "feature_id": feature_id,
                    "issue_number": issue_number,
                },
            )
            return

        # Revert commits in reverse order
        for commit_hash in reversed(commits):
            subprocess.run(
                ["git", "revert", "--no-commit", commit_hash],
                capture_output=True,
                text=True,
                cwd=self.config.repo_root,
            )

        # Commit the reverts
        subprocess.run(
            ["git", "commit", "-m", f"Rollback issue #{issue_number}"],
            capture_output=True,
            text=True,
            cwd=self.config.repo_root,
        )

        self._log(
            "issue_rollback",
            {
                "feature_id": feature_id,
                "issue_number": issue_number,
                "commits_reverted": len(commits),
            },
        )

    # =========================================================================
    # Checkpoint (Spec-compatible alias)
    # =========================================================================

    def checkpoint(
        self,
        session_id: str,
        agent: str,
        status: str,
        commit: Optional[str] = None,
        cost_usd: float = 0.0,
    ) -> CheckpointData:
        """
        Create checkpoint for progress tracking.

        This is an alias for add_checkpoint that returns CheckpointData
        to match the spec interface.

        Args:
            session_id: The session identifier.
            agent: Name of the agent creating the checkpoint.
            status: Status at checkpoint.
            commit: Optional git commit hash.
            cost_usd: Cost incurred at this checkpoint.

        Returns:
            The created CheckpointData.
        """
        session = self.add_checkpoint(session_id, agent, status, commit, cost_usd)

        # Return the last checkpoint (the one we just added)
        return session.checkpoints[-1]

    # =========================================================================
    # TTL and Stale Detection (Expert 1 - SRE)
    # =========================================================================

    def is_session_stale(self, session_id: str) -> bool:
        """
        Check if session is stale (no activity for TTL period).

        A session is stale if:
        1. It's still "active" but hasn't had activity for SESSION_TTL_HOURS
        2. Activity is measured by the last checkpoint timestamp or started_at

        Args:
            session_id: The session identifier.

        Returns:
            True if session is stale, False otherwise.
        """
        feature_id = self._get_feature_id_from_session(session_id)
        if feature_id is None:
            return False

        session = self.state_store.load_session(feature_id, session_id)
        if session is None or session.status != "active":
            return False

        # Get the most recent timestamp
        last_activity = session.started_at
        if session.checkpoints:
            last_checkpoint = session.checkpoints[-1]
            if last_checkpoint.timestamp > last_activity:
                last_activity = last_checkpoint.timestamp

        try:
            last_activity_dt = datetime.fromisoformat(
                last_activity.replace("Z", "+00:00")
            )
            age = datetime.now(timezone.utc) - last_activity_dt
            return age >= timedelta(hours=self.SESSION_TTL_HOURS)
        except (ValueError, AttributeError):
            # Can't parse timestamp - consider stale to be safe
            return True

    def cleanup_stale_sessions(self, feature_id: str) -> list[str]:
        """
        Auto-cleanup stale sessions for a feature.

        Stale sessions are:
        1. Marked as interrupted
        2. Their associated issue lock is released
        3. The task stage is synced if still IN_PROGRESS

        Args:
            feature_id: The feature identifier.

        Returns:
            List of cleaned session IDs.
        """
        cleaned_sessions: list[str] = []
        session_ids = self.state_store.list_sessions(feature_id)

        for session_id in session_ids:
            session = self.state_store.load_session(feature_id, session_id)
            if session is None or session.status != "active":
                continue

            if self.is_session_stale(session_id):
                # Mark as interrupted
                self.mark_as_interrupted(session_id)

                # Release the issue lock
                self.release_issue(feature_id, session.issue_number)

                # Sync task state - if task is IN_PROGRESS, mark as INTERRUPTED
                self._sync_task_state_on_cleanup(feature_id, session.issue_number)

                cleaned_sessions.append(session_id)

                self._log(
                    "stale_session_cleaned",
                    {
                        "session_id": session_id,
                        "feature_id": feature_id,
                        "issue_number": session.issue_number,
                    },
                )

        return cleaned_sessions

    def _sync_task_state_on_cleanup(
        self,
        feature_id: str,
        issue_number: int,
    ) -> None:
        """
        Sync task state when a session is cleaned up.

        If the task is still IN_PROGRESS, mark it as INTERRUPTED.

        Args:
            feature_id: The feature identifier.
            issue_number: The issue number.
        """
        from swarm_attack.models import TaskStage

        state = self.state_store.load(feature_id)
        if state is None:
            return

        for task in state.tasks:
            if task.issue_number == issue_number:
                if task.stage == TaskStage.IN_PROGRESS:
                    task.stage = TaskStage.INTERRUPTED
                    self.state_store.save(state)
                    self._log(
                        "task_marked_interrupted",
                        {
                            "feature_id": feature_id,
                            "issue_number": issue_number,
                        },
                    )
                break

    def get_sessions_for_feature(self, feature_id: str) -> list[SessionState]:
        """
        Get all sessions (active and inactive) for a feature.

        Args:
            feature_id: The feature identifier.

        Returns:
            List of SessionState objects.
        """
        sessions: list[SessionState] = []
        session_ids = self.state_store.list_sessions(feature_id)

        for session_id in session_ids:
            session = self.state_store.load_session(feature_id, session_id)
            if session is not None:
                sessions.append(session)

        return sessions

    def finalize_session_on_task_done(
        self,
        session_id: str,
        issue_number: int,
    ) -> None:
        """
        Ensure session is closed when task is marked DONE.

        This fixes the edge case where a task is marked DONE but the
        session is still active.

        Args:
            session_id: The session identifier.
            issue_number: The issue number.
        """
        feature_id = self._get_feature_id_from_session(session_id)
        if feature_id is None:
            return

        session = self.state_store.load_session(feature_id, session_id)
        if session is None:
            return

        # Only finalize if session is still active
        if session.status != "active":
            return

        # End the session
        try:
            self.end_session(session_id, "success")
        except SessionError:
            # Session may have been ended by another process
            pass

        # Release the issue lock
        self.release_issue(feature_id, issue_number)

        self._log(
            "session_finalized_on_task_done",
            {
                "session_id": session_id,
                "feature_id": feature_id,
                "issue_number": issue_number,
            },
        )
