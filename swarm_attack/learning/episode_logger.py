"""Episode Logger for capturing execution telemetry for learning.

This module provides components for logging execution episodes to enable
learning from past executions. It captures:
- Actions taken (tool calls, edits, commands)
- Outcomes (success, failure, partial)
- Context snapshots at key points
- Recovery attempts and results

Key Classes:
- EpisodeLogger: Main logger that manages episode lifecycle
- Episode: Represents a complete execution episode
- Action: Individual action within an episode
- Outcome: Enum for action/episode outcomes
- ContextSnapshot: Point-in-time context capture
- RecoveryAttempt: Recovery attempt tracking
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from swarm_attack.config import SwarmConfig


# =============================================================================
# Enums
# =============================================================================


class Outcome(Enum):
    """Outcome of an action or episode.

    Attributes:
        SUCCESS: Action/episode completed successfully.
        FAILURE: Action/episode failed.
        PARTIAL: Action/episode partially completed.
        PENDING: Action/episode is in progress.
    """
    SUCCESS = "success"
    FAILURE = "failure"
    PARTIAL = "partial"
    PENDING = "pending"


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class Action:
    """Represents an individual action within an episode.

    Actions capture tool calls, edits, commands, and other operations
    performed during execution.

    Attributes:
        action_id: Unique identifier for the action.
        action_type: Type of action (tool_call, edit, command, llm_call).
        tool_name: Name of the tool used (Read, Edit, Bash, etc.).
        timestamp: ISO format timestamp when action was initiated.
        input_data: Input parameters for the action.
        output_data: Output/result data from the action.
        outcome: Outcome of the action (success, failure, partial, pending).
        duration_ms: Duration of the action in milliseconds.
        error_message: Error message if action failed.
    """
    action_id: str
    action_type: str
    tool_name: str
    timestamp: str
    input_data: dict[str, Any] = field(default_factory=dict)
    output_data: dict[str, Any] = field(default_factory=dict)
    outcome: Outcome = Outcome.PENDING
    duration_ms: Optional[int] = None
    error_message: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        data = asdict(self)
        data["outcome"] = self.outcome.value
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Action:
        """Create from dictionary."""
        data = data.copy()
        if "outcome" in data:
            data["outcome"] = Outcome(data["outcome"])
        return cls(**data)


@dataclass
class ContextSnapshot:
    """Point-in-time snapshot of execution context.

    Captures the state of the context at key points during execution
    for learning and debugging purposes.

    Attributes:
        snapshot_id: Unique identifier for the snapshot.
        timestamp: ISO format timestamp when snapshot was taken.
        phase: Execution phase (initialization, implementation, testing, etc.).
        files_in_context: List of files currently in context.
        token_count: Current token count in context.
        key_variables: Important variables and their values.
        agent_state: Current state of the agent.
    """
    snapshot_id: str
    timestamp: str
    phase: str
    files_in_context: list[str] = field(default_factory=list)
    token_count: Optional[int] = None
    key_variables: dict[str, Any] = field(default_factory=dict)
    agent_state: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ContextSnapshot:
        """Create from dictionary."""
        # Handle missing fields with defaults
        return cls(
            snapshot_id=data.get("snapshot_id", ""),
            timestamp=data.get("timestamp", ""),
            phase=data.get("phase", ""),
            files_in_context=data.get("files_in_context", []),
            token_count=data.get("token_count"),
            key_variables=data.get("key_variables", {}),
            agent_state=data.get("agent_state"),
        )


@dataclass
class RecoveryAttempt:
    """Represents a recovery attempt after an error.

    Tracks recovery attempts including the trigger, strategy used,
    actions taken, and outcome.

    Attributes:
        attempt_id: Unique identifier for the attempt.
        timestamp: ISO format timestamp when recovery was initiated.
        trigger_error: Error that triggered the recovery.
        strategy: Recovery strategy used (retry, simplify, escalate, etc.).
        actions_taken: List of actions taken during recovery.
        outcome: Outcome of the recovery attempt.
        result_summary: Summary of the recovery result.
    """
    attempt_id: str
    timestamp: str
    trigger_error: str
    strategy: str
    actions_taken: list[str] = field(default_factory=list)
    outcome: Outcome = Outcome.PENDING
    result_summary: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        data = asdict(self)
        data["outcome"] = self.outcome.value
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RecoveryAttempt:
        """Create from dictionary."""
        data = data.copy()
        if "outcome" in data:
            data["outcome"] = Outcome(data["outcome"])
        return cls(**data)


@dataclass
class Episode:
    """Represents a complete execution episode.

    An episode captures the full lifecycle of an agent execution,
    including all actions, context snapshots, and recovery attempts.

    Attributes:
        episode_id: Unique identifier for the episode.
        feature_id: Feature being worked on.
        started_at: ISO format timestamp when episode started.
        issue_number: Optional issue number being worked on.
        agent_type: Type of agent (coder, verifier, etc.).
        ended_at: ISO format timestamp when episode ended.
        final_outcome: Final outcome of the episode.
        actions: List of actions taken during the episode.
        context_snapshots: List of context snapshots.
        recovery_attempts: List of recovery attempts.
        metadata: Additional episode metadata.
    """
    episode_id: str
    feature_id: str
    started_at: str
    issue_number: Optional[int] = None
    agent_type: Optional[str] = None
    ended_at: Optional[str] = None
    final_outcome: Optional[Outcome] = None
    actions: list[Action] = field(default_factory=list)
    context_snapshots: list[ContextSnapshot] = field(default_factory=list)
    recovery_attempts: list[RecoveryAttempt] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def duration_seconds(self) -> Optional[int]:
        """Calculate duration in seconds if episode has ended.

        Returns:
            Duration in seconds, or None if episode hasn't ended.
        """
        if self.ended_at is None:
            return None

        start = datetime.fromisoformat(self.started_at)
        end = datetime.fromisoformat(self.ended_at)
        return int((end - start).total_seconds())

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        data = {
            "episode_id": self.episode_id,
            "feature_id": self.feature_id,
            "started_at": self.started_at,
            "issue_number": self.issue_number,
            "agent_type": self.agent_type,
            "ended_at": self.ended_at,
            "final_outcome": self.final_outcome.value if self.final_outcome else None,
            "actions": [a.to_dict() for a in self.actions],
            "context_snapshots": [s.to_dict() for s in self.context_snapshots],
            "recovery_attempts": [r.to_dict() for r in self.recovery_attempts],
            "metadata": self.metadata,
        }
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Episode:
        """Create from dictionary."""
        return cls(
            episode_id=data.get("episode_id", ""),
            feature_id=data.get("feature_id", ""),
            started_at=data.get("started_at", ""),
            issue_number=data.get("issue_number"),
            agent_type=data.get("agent_type"),
            ended_at=data.get("ended_at"),
            final_outcome=Outcome(data["final_outcome"]) if data.get("final_outcome") else None,
            actions=[Action.from_dict(a) for a in data.get("actions", [])],
            context_snapshots=[ContextSnapshot.from_dict(s) for s in data.get("context_snapshots", [])],
            recovery_attempts=[RecoveryAttempt.from_dict(r) for r in data.get("recovery_attempts", [])],
            metadata=data.get("metadata", {}),
        )


# =============================================================================
# Episode Logger
# =============================================================================


class EpisodeLogger:
    """Logger for capturing execution episodes for learning.

    This logger manages the lifecycle of execution episodes, capturing
    actions, context snapshots, and recovery attempts. Episodes are
    persisted to disk for later analysis and learning.

    Attributes:
        config: SwarmConfig for accessing project settings.
        current_episode: Currently active episode (if any).
        episodes_path: Path to episode storage directory.

    Example:
        >>> logger = EpisodeLogger(config)
        >>> episode = logger.start_episode(feature_id="my-feature")
        >>> logger.log_action(action_type="tool_call", tool_name="Read")
        >>> logger.capture_context(phase="implementation")
        >>> logger.end_episode(outcome=Outcome.SUCCESS)
    """

    def __init__(
        self,
        config: Optional[SwarmConfig] = None,
    ) -> None:
        """Initialize the EpisodeLogger.

        Args:
            config: SwarmConfig for project settings (optional).
        """
        self.config = config
        self._current_episode: Optional[Episode] = None
        self._episodes: dict[str, Episode] = {}

        # Set up episodes path
        self._episodes_path: Optional[Path] = None
        if config and hasattr(config, "swarm_path"):
            self._episodes_path = Path(config.swarm_path) / "episodes"

    @property
    def current_episode(self) -> Optional[Episode]:
        """Get the currently active episode."""
        return self._current_episode

    @property
    def episodes_path(self) -> Optional[Path]:
        """Get the path to episode storage directory."""
        return self._episodes_path

    def start_episode(
        self,
        feature_id: str,
        issue_number: Optional[int] = None,
        agent_type: Optional[str] = None,
    ) -> Episode:
        """Start a new execution episode.

        Creates a new episode and sets it as the current active episode.

        Args:
            feature_id: Feature being worked on.
            issue_number: Optional issue number being worked on.
            agent_type: Type of agent (coder, verifier, etc.).

        Returns:
            The newly created Episode.
        """
        episode_id = f"ep-{uuid.uuid4().hex[:8]}"
        episode = Episode(
            episode_id=episode_id,
            feature_id=feature_id,
            started_at=datetime.now().isoformat(),
            issue_number=issue_number,
            agent_type=agent_type,
        )
        self._current_episode = episode
        return episode

    def log_action(
        self,
        action_type: str,
        tool_name: str,
        input_data: Optional[dict[str, Any]] = None,
        output_data: Optional[dict[str, Any]] = None,
    ) -> Action:
        """Log an action in the current episode.

        Args:
            action_type: Type of action (tool_call, edit, command, llm_call).
            tool_name: Name of the tool used.
            input_data: Input parameters for the action.
            output_data: Output/result data from the action.

        Returns:
            The newly created Action.

        Raises:
            ValueError: If no episode is currently active.
        """
        if self._current_episode is None:
            raise ValueError("No active episode. Call start_episode() first.")

        action_id = f"act-{uuid.uuid4().hex[:8]}"
        action = Action(
            action_id=action_id,
            action_type=action_type,
            tool_name=tool_name,
            timestamp=datetime.now().isoformat(),
            input_data=input_data or {},
            output_data=output_data or {},
        )
        self._current_episode.actions.append(action)
        return action

    def update_action_outcome(
        self,
        action_id: str,
        outcome: Outcome,
        duration_ms: Optional[int] = None,
        error_message: Optional[str] = None,
    ) -> None:
        """Update the outcome of an action.

        Args:
            action_id: ID of the action to update.
            outcome: Outcome of the action.
            duration_ms: Duration of the action in milliseconds.
            error_message: Error message if action failed.

        Raises:
            ValueError: If action not found in current episode.
        """
        if self._current_episode is None:
            raise ValueError("No active episode.")

        for action in self._current_episode.actions:
            if action.action_id == action_id:
                action.outcome = outcome
                if duration_ms is not None:
                    action.duration_ms = duration_ms
                if error_message is not None:
                    action.error_message = error_message
                return

        raise ValueError(f"Action not found: {action_id}")

    def capture_context(
        self,
        phase: str,
        files_in_context: Optional[list[str]] = None,
        token_count: Optional[int] = None,
        key_variables: Optional[dict[str, Any]] = None,
        agent_state: Optional[str] = None,
    ) -> ContextSnapshot:
        """Capture a context snapshot.

        Args:
            phase: Execution phase (initialization, implementation, etc.).
            files_in_context: List of files currently in context.
            token_count: Current token count in context.
            key_variables: Important variables and their values.
            agent_state: Current state of the agent.

        Returns:
            The newly created ContextSnapshot.

        Raises:
            ValueError: If no episode is currently active.
        """
        if self._current_episode is None:
            raise ValueError("No active episode. Call start_episode() first.")

        snapshot_id = f"snap-{uuid.uuid4().hex[:8]}"
        snapshot = ContextSnapshot(
            snapshot_id=snapshot_id,
            timestamp=datetime.now().isoformat(),
            phase=phase,
            files_in_context=files_in_context or [],
            token_count=token_count,
            key_variables=key_variables or {},
            agent_state=agent_state,
        )
        self._current_episode.context_snapshots.append(snapshot)
        return snapshot

    def log_recovery_attempt(
        self,
        trigger_error: str,
        strategy: str,
    ) -> RecoveryAttempt:
        """Log a recovery attempt.

        Args:
            trigger_error: Error that triggered the recovery.
            strategy: Recovery strategy used.

        Returns:
            The newly created RecoveryAttempt.

        Raises:
            ValueError: If no episode is currently active.
        """
        if self._current_episode is None:
            raise ValueError("No active episode. Call start_episode() first.")

        attempt_id = f"rec-{uuid.uuid4().hex[:8]}"
        attempt = RecoveryAttempt(
            attempt_id=attempt_id,
            timestamp=datetime.now().isoformat(),
            trigger_error=trigger_error,
            strategy=strategy,
        )
        self._current_episode.recovery_attempts.append(attempt)
        return attempt

    def update_recovery_outcome(
        self,
        attempt_id: str,
        outcome: Outcome,
        result_summary: Optional[str] = None,
        actions_taken: Optional[list[str]] = None,
    ) -> None:
        """Update the outcome of a recovery attempt.

        Args:
            attempt_id: ID of the recovery attempt to update.
            outcome: Outcome of the recovery attempt.
            result_summary: Summary of the recovery result.
            actions_taken: List of actions taken during recovery.

        Raises:
            ValueError: If recovery attempt not found in current episode.
        """
        if self._current_episode is None:
            raise ValueError("No active episode.")

        for attempt in self._current_episode.recovery_attempts:
            if attempt.attempt_id == attempt_id:
                attempt.outcome = outcome
                if result_summary is not None:
                    attempt.result_summary = result_summary
                if actions_taken is not None:
                    attempt.actions_taken = actions_taken
                return

        raise ValueError(f"Recovery attempt not found: {attempt_id}")

    def end_episode(self, outcome: Outcome) -> Episode:
        """End the current episode.

        Args:
            outcome: Final outcome of the episode.

        Returns:
            The completed Episode.

        Raises:
            ValueError: If no episode is currently active.
        """
        if self._current_episode is None:
            raise ValueError("No active episode. Call start_episode() first.")

        self._current_episode.ended_at = datetime.now().isoformat()
        self._current_episode.final_outcome = outcome

        # Store in memory
        self._episodes[self._current_episode.episode_id] = self._current_episode

        # Persist to disk if configured
        self._save_episode(self._current_episode)

        completed = self._current_episode
        self._current_episode = None
        return completed

    def get_episode(self, episode_id: str) -> Optional[Episode]:
        """Get an episode by ID.

        Args:
            episode_id: ID of the episode to retrieve.

        Returns:
            The Episode if found, None otherwise.
        """
        # Check memory first
        if episode_id in self._episodes:
            return self._episodes[episode_id]

        # Try loading from disk
        return self._load_episode(episode_id)

    def get_episodes_for_feature(self, feature_id: str) -> list[Episode]:
        """Get all episodes for a feature.

        Args:
            feature_id: Feature ID to filter by.

        Returns:
            List of episodes for the feature.
        """
        # Get from memory
        episodes = [
            ep for ep in self._episodes.values()
            if ep.feature_id == feature_id
        ]

        # Also load from disk if configured
        if self._episodes_path and self._episodes_path.exists():
            for file in self._episodes_path.glob("*.json"):
                try:
                    with open(file) as f:
                        data = json.load(f)
                    if data.get("feature_id") == feature_id:
                        ep = Episode.from_dict(data)
                        if ep.episode_id not in self._episodes:
                            episodes.append(ep)
                except (json.JSONDecodeError, KeyError):
                    continue

        return episodes

    def get_success_rate(self, feature_id: str) -> float:
        """Calculate success rate for a feature.

        Args:
            feature_id: Feature ID to calculate rate for.

        Returns:
            Success rate as a float (0.0 to 1.0).
        """
        episodes = self.get_episodes_for_feature(feature_id)
        if not episodes:
            return 0.0

        success_count = sum(
            1 for ep in episodes
            if ep.final_outcome == Outcome.SUCCESS
        )
        return success_count / len(episodes)

    def get_average_duration(self, feature_id: str) -> float:
        """Calculate average episode duration for a feature.

        Args:
            feature_id: Feature ID to calculate duration for.

        Returns:
            Average duration in seconds.
        """
        episodes = self.get_episodes_for_feature(feature_id)
        durations = [
            ep.duration_seconds for ep in episodes
            if ep.duration_seconds is not None
        ]
        if not durations:
            return 0.0
        return sum(durations) / len(durations)

    def get_recovery_success_rate(self, feature_id: str) -> float:
        """Calculate recovery attempt success rate for a feature.

        Args:
            feature_id: Feature ID to calculate rate for.

        Returns:
            Recovery success rate as a float (0.0 to 1.0).
        """
        episodes = self.get_episodes_for_feature(feature_id)
        total_attempts = 0
        successful_attempts = 0

        for ep in episodes:
            for attempt in ep.recovery_attempts:
                total_attempts += 1
                if attempt.outcome == Outcome.SUCCESS:
                    successful_attempts += 1

        if total_attempts == 0:
            return 0.0
        return successful_attempts / total_attempts

    def _save_episode(self, episode: Episode) -> None:
        """Save an episode to disk.

        Args:
            episode: Episode to save.
        """
        if self._episodes_path is None:
            return

        self._episodes_path.mkdir(parents=True, exist_ok=True)
        file_path = self._episodes_path / f"{episode.episode_id}.json"
        with open(file_path, "w") as f:
            json.dump(episode.to_dict(), f, indent=2)

    def _load_episode(self, episode_id: str) -> Optional[Episode]:
        """Load an episode from disk.

        Args:
            episode_id: ID of the episode to load.

        Returns:
            The Episode if found, None otherwise.
        """
        if self._episodes_path is None:
            return None

        file_path = self._episodes_path / f"{episode_id}.json"
        if not file_path.exists():
            return None

        try:
            with open(file_path) as f:
                data = json.load(f)
            return Episode.from_dict(data)
        except (json.JSONDecodeError, KeyError):
            return None
