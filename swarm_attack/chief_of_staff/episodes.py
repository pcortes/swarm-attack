"""Episode logging and preference learning for Chief of Staff.

This module provides:
- Episode dataclass for tracking execution episodes
- EpisodeStore with JSONL storage for episode persistence
- PreferenceLearner for extracting signals from checkpoint decisions
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from swarm_attack.chief_of_staff.checkpoints import Checkpoint


@dataclass
class Episode:
    """Record of a single goal execution episode.

    Tracks the full lifecycle of a goal execution including
    success/failure, cost, duration, and any checkpoints triggered.
    """

    episode_id: str
    timestamp: str  # ISO format
    goal_id: str
    success: bool
    cost_usd: float
    duration_seconds: int
    checkpoints_triggered: list[str] = field(default_factory=list)
    error: Optional[str] = None
    notes: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert Episode to dictionary for serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Episode":
        """Create Episode from dictionary."""
        return cls(
            episode_id=data.get("episode_id", ""),
            timestamp=data.get("timestamp", ""),
            goal_id=data.get("goal_id", ""),
            success=data.get("success", False),
            cost_usd=data.get("cost_usd", 0.0),
            duration_seconds=data.get("duration_seconds", 0),
            checkpoints_triggered=data.get("checkpoints_triggered", []),
            error=data.get("error"),
            notes=data.get("notes"),
        )


class EpisodeStore:
    """Persistent storage for episodes using JSONL format.

    Stores episodes in .swarm/chief-of-staff/episodes/episodes.jsonl
    for efficient append-only logging and recent episode retrieval.
    """

    def __init__(self, base_path: Optional[Path] = None) -> None:
        """Initialize EpisodeStore.

        Args:
            base_path: Base directory for storage.
                       Defaults to .swarm/chief-of-staff/episodes/
        """
        if base_path is None:
            base_path = Path.cwd() / ".swarm" / "chief-of-staff" / "episodes"
        self.base_path = base_path
        self.base_path.mkdir(parents=True, exist_ok=True)
        self.episodes_file = self.base_path / "episodes.jsonl"

    def save(self, episode: Episode) -> None:
        """Append an episode to the JSONL file.

        Args:
            episode: Episode to save.
        """
        with open(self.episodes_file, "a") as f:
            f.write(json.dumps(episode.to_dict()) + "\n")

    def load_recent(self, limit: int = 100) -> list[Episode]:
        """Load the most recent episodes.

        Args:
            limit: Maximum number of episodes to return. Defaults to 100.

        Returns:
            List of Episode objects, most recent first.
        """
        if not self.episodes_file.exists():
            return []

        episodes = []
        with open(self.episodes_file, "r") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        data = json.loads(line)
                        episodes.append(Episode.from_dict(data))
                    except json.JSONDecodeError:
                        continue  # Skip malformed lines

        # Return most recent first
        episodes.reverse()
        return episodes[:limit]

    def load_all(self) -> list[Episode]:
        """Load all episodes.

        Returns:
            List of all Episode objects.
        """
        if not self.episodes_file.exists():
            return []

        episodes = []
        with open(self.episodes_file, "r") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        data = json.loads(line)
                        episodes.append(Episode.from_dict(data))
                    except json.JSONDecodeError:
                        continue

        return episodes


@dataclass
class PreferenceSignal:
    """Signal extracted from a checkpoint decision."""

    signal_type: str  # e.g., "approved_cost", "rejected_risk"
    trigger: str
    chosen_option: str
    context_summary: str
    timestamp: str


class PreferenceLearner:
    """Extracts preference signals from checkpoint decisions.

    Analyzes checkpoint resolutions to learn user preferences
    for future recommendations and autopilot behavior.
    """

    def __init__(self) -> None:
        """Initialize PreferenceLearner."""
        self.signals: list[PreferenceSignal] = []

    def record_decision(self, checkpoint: "Checkpoint") -> PreferenceSignal:
        """Extract and record a preference signal from a resolved checkpoint.

        Args:
            checkpoint: A resolved checkpoint with chosen_option set.

        Returns:
            PreferenceSignal extracted from the decision.
        """
        # Determine signal type based on trigger and chosen option
        signal_type = self._classify_signal(checkpoint)

        # Summarize context (first 100 chars)
        context_summary = checkpoint.context[:100] if checkpoint.context else ""

        signal = PreferenceSignal(
            signal_type=signal_type,
            trigger=checkpoint.trigger.value,
            chosen_option=checkpoint.chosen_option or "",
            context_summary=context_summary,
            timestamp=checkpoint.resolved_at or datetime.utcnow().isoformat(),
        )

        self.signals.append(signal)
        return signal

    def _classify_signal(self, checkpoint: "Checkpoint") -> str:
        """Classify the type of preference signal.

        Args:
            checkpoint: Resolved checkpoint to classify.

        Returns:
            Signal type string.
        """
        trigger = checkpoint.trigger.value.lower()
        option = (checkpoint.chosen_option or "").lower()

        if "proceed" in option or "approve" in option:
            return f"approved_{trigger}"
        elif "skip" in option or "reject" in option:
            return f"rejected_{trigger}"
        else:
            return f"custom_{trigger}"

    def get_signals_by_trigger(self, trigger: str) -> list[PreferenceSignal]:
        """Get all signals for a specific trigger type.

        Args:
            trigger: Trigger type to filter by.

        Returns:
            List of PreferenceSignal matching the trigger.
        """
        return [s for s in self.signals if s.trigger == trigger]

    def get_approval_rate(self, trigger: str) -> float:
        """Calculate approval rate for a trigger type.

        Args:
            trigger: Trigger type to analyze.

        Returns:
            Approval rate (0.0 to 1.0). Returns 0.0 if no data.
        """
        signals = self.get_signals_by_trigger(trigger)
        if not signals:
            return 0.0

        approved = sum(1 for s in signals if s.signal_type.startswith("approved_"))
        return approved / len(signals)
