"""
Append-only progress log for session tracking.

This module provides a human-readable, append-only progress log at .swarm/progress.txt.
Each entry is timestamped and never truncated, providing a complete history of
all session activity.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Optional


class ProgressLogger:
    """
    Append-only human-readable progress log.

    Writes timestamped entries to .swarm/progress.txt.
    Never truncates - only appends.
    """

    def __init__(self, swarm_dir: Path) -> None:
        """
        Initialize the progress logger.

        Args:
            swarm_dir: Path to the .swarm directory.
        """
        self._swarm_dir = Path(swarm_dir)
        self._log_path = self._swarm_dir / "progress.txt"

    def _ensure_directory(self) -> None:
        """Ensure the .swarm directory exists."""
        self._swarm_dir.mkdir(parents=True, exist_ok=True)

    def _append(self, entry: str) -> None:
        """
        Append entry with timestamp. Never truncates.

        Args:
            entry: The log entry text (without timestamp).
        """
        self._ensure_directory()
        timestamp = datetime.now().isoformat()
        with self._log_path.open("a") as f:
            f.write(f"[{timestamp}] {entry}\n")

    def log_session_start(
        self,
        feature_id: str,
        issue_number: Optional[int] = None
    ) -> None:
        """
        Log session start.

        Args:
            feature_id: The feature identifier.
            issue_number: Optional issue number being worked on.
        """
        issue_str = f"issue=#{issue_number}" if issue_number else "issue=None"
        self._append(f"SESSION_START feature={feature_id} {issue_str}")

    def log_verification_passed(self, test_count: int) -> None:
        """
        Log that verification tests passed.

        Args:
            test_count: Number of tests that passed.
        """
        self._append(f"VERIFICATION_PASSED {test_count} tests, 0 failures")

    def log_checkpoint(self, phase: str) -> None:
        """
        Log a checkpoint during the session.

        Args:
            phase: Description of the phase (e.g., "RED phase", "GREEN phase").
        """
        self._append(f"CHECKPOINT {phase}")

    def log_session_end(
        self,
        feature_id: str,
        issue_number: int,
        status: str,
        commits: list[str]
    ) -> None:
        """
        Log session end.

        Args:
            feature_id: The feature identifier.
            issue_number: The issue that was worked on.
            status: Final status (e.g., "DONE", "BLOCKED", "FAILED").
            commits: List of commit hashes created during the session.
        """
        commit_str = ",".join(commits[:3]) if commits else "none"
        self._append(
            f"SESSION_END feature={feature_id} issue=#{issue_number} "
            f"status={status} commits={commit_str}"
        )

    def log_verification_failed(self, failure_count: int, failures: list[str]) -> None:
        """
        Log that verification tests failed.

        Args:
            failure_count: Number of tests that failed.
            failures: List of failure messages/names.
        """
        failures_str = ", ".join(failures[:3]) if failures else "unknown"
        self._append(f"VERIFICATION_FAILED {failure_count} failures: {failures_str}")

    def log_error(self, error: str) -> None:
        """
        Log an error that occurred during the session.

        Args:
            error: Error message.
        """
        self._append(f"ERROR {error}")
