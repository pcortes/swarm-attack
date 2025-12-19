"""Progress tracking for Chief of Staff autopilot execution.

This module provides:
- ProgressSnapshot dataclass for point-in-time progress state
- ProgressTracker for real-time execution monitoring with persistence
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


@dataclass
class ProgressSnapshot:
    """Point-in-time progress state.

    Captures the execution state at a specific moment, including
    completed goals, costs, and any blockers encountered.
    """

    timestamp: str
    goals_completed: int
    goals_total: int
    cost_usd: float
    duration_seconds: int
    current_goal: Optional[str] = None
    blockers: list[str] = field(default_factory=list)

    @property
    def completion_percent(self) -> float:
        """Calculate completion percentage.

        Returns:
            Percentage complete (0.0 to 100.0).
        """
        if self.goals_total == 0:
            return 0.0
        return (self.goals_completed / self.goals_total) * 100

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization.

        Returns:
            Dictionary representation of the snapshot.
        """
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ProgressSnapshot":
        """Create ProgressSnapshot from dictionary.

        Args:
            data: Dictionary with snapshot data.

        Returns:
            ProgressSnapshot instance.
        """
        return cls(
            timestamp=data.get("timestamp", ""),
            goals_completed=data.get("goals_completed", 0),
            goals_total=data.get("goals_total", 0),
            cost_usd=data.get("cost_usd", 0.0),
            duration_seconds=data.get("duration_seconds", 0),
            current_goal=data.get("current_goal"),
            blockers=data.get("blockers", []),
        )


class ProgressTracker:
    """Tracks execution progress in real-time with persistence.

    Provides real-time progress monitoring for autopilot execution,
    with snapshot history and disk persistence for recovery.

    Usage:
        tracker = ProgressTracker(base_path)
        tracker.start_session(total_goals=5)
        tracker.update(current_goal="Implement feature X")
        tracker.update(goals_completed=1, cost_usd=2.50)
        current = tracker.get_current()
    """

    def __init__(self, base_path: Path) -> None:
        """Initialize ProgressTracker.

        Args:
            base_path: Base directory for progress file storage.
        """
        self.base_path = base_path
        self.progress_file = base_path / "progress.json"
        self.snapshots: list[ProgressSnapshot] = []
        self._current_snapshot: Optional[ProgressSnapshot] = None

    def start_session(self, total_goals: int) -> None:
        """Start tracking a new session.

        Creates an initial progress snapshot with zero progress.

        Args:
            total_goals: Total number of goals to execute in this session.
        """
        self._current_snapshot = ProgressSnapshot(
            timestamp=datetime.now(timezone.utc).isoformat(),
            goals_completed=0,
            goals_total=total_goals,
            cost_usd=0.0,
            duration_seconds=0,
        )
        self.snapshots = [self._current_snapshot]
        self._save()

    def update(
        self,
        goals_completed: Optional[int] = None,
        cost_usd: Optional[float] = None,
        duration_seconds: Optional[int] = None,
        current_goal: Optional[str] = None,
        blocker: Optional[str] = None,
    ) -> ProgressSnapshot:
        """Update progress and create new snapshot.

        Each update creates a new snapshot in the history, preserving
        the full timeline of progress updates.

        Args:
            goals_completed: Number of goals completed (or None to keep current).
            cost_usd: Total cost so far (or None to keep current).
            duration_seconds: Total duration so far (or None to keep current).
            current_goal: Description of the current goal being worked on.
            blocker: Description of a new blocker (appended to list).

        Returns:
            The new ProgressSnapshot.

        Raises:
            RuntimeError: If no active session exists.
        """
        if self._current_snapshot is None:
            raise RuntimeError("No active session. Call start_session() first.")

        # Build new blockers list
        new_blockers = list(self._current_snapshot.blockers)
        if blocker:
            new_blockers.append(blocker)

        new_snapshot = ProgressSnapshot(
            timestamp=datetime.now(timezone.utc).isoformat(),
            goals_completed=(
                goals_completed
                if goals_completed is not None
                else self._current_snapshot.goals_completed
            ),
            goals_total=self._current_snapshot.goals_total,
            cost_usd=(
                cost_usd if cost_usd is not None else self._current_snapshot.cost_usd
            ),
            duration_seconds=(
                duration_seconds
                if duration_seconds is not None
                else self._current_snapshot.duration_seconds
            ),
            current_goal=current_goal,
            blockers=new_blockers,
        )

        self._current_snapshot = new_snapshot
        self.snapshots.append(new_snapshot)
        self._save()
        return new_snapshot

    def get_current(self) -> Optional[ProgressSnapshot]:
        """Get current progress snapshot.

        Returns:
            The most recent ProgressSnapshot, or None if no session active.
        """
        return self._current_snapshot

    def get_history(self) -> list[ProgressSnapshot]:
        """Get all progress snapshots.

        Returns:
            List of all snapshots in chronological order.
        """
        return self.snapshots.copy()

    def _save(self) -> None:
        """Persist progress to disk."""
        self.base_path.mkdir(parents=True, exist_ok=True)
        data = [s.to_dict() for s in self.snapshots]
        self.progress_file.write_text(json.dumps(data, indent=2))

    def load(self) -> None:
        """Load progress from disk.

        Restores snapshots from the progress file if it exists.
        """
        if self.progress_file.exists():
            data = json.loads(self.progress_file.read_text())
            self.snapshots = [ProgressSnapshot.from_dict(s) for s in data]
            if self.snapshots:
                self._current_snapshot = self.snapshots[-1]