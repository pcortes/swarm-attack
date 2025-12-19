"""Episode logging and preference learning for Chief of Staff.

This module provides:
- Episode dataclass for tracking execution episodes
- EpisodeStore with JSONL storage for episode persistence
- PreferenceLearner for extracting signals from checkpoint decisions
"""

from __future__ import annotations

import json
import re
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
    retry_count: int = 0
    recovery_level: Optional[str] = None

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
            retry_count=data.get("retry_count", 0),
            recovery_level=data.get("recovery_level"),
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

    def _tokenize(self, text: str) -> set[str]:
        """Tokenize text into lowercase words for similarity matching.

        Args:
            text: Text to tokenize.

        Returns:
            Set of lowercase word tokens.
        """
        # Extract words (alphanumeric sequences), convert to lowercase
        words = re.findall(r'\w+', text.lower())
        return set(words)

    def _jaccard_similarity(self, set_a: set[str], set_b: set[str]) -> float:
        """Calculate Jaccard similarity between two sets.

        Args:
            set_a: First set of tokens.
            set_b: Second set of tokens.

        Returns:
            Jaccard similarity coefficient (0.0 to 1.0).
        """
        if not set_a or not set_b:
            return 0.0
        intersection = len(set_a & set_b)
        union = len(set_a | set_b)
        if union == 0:
            return 0.0
        return intersection / union

    def find_similar(self, content: str, k: int = 5) -> list[Episode]:
        """Find similar past episodes based on keyword matching.

        Uses Jaccard similarity on tokenized goal_id text to find
        episodes that are similar to the given content.

        Args:
            content: Content string to match against episode goal_ids.
            k: Maximum number of similar episodes to return. Defaults to 5.

        Returns:
            List of Episode objects sorted by relevance (highest first).
            Returns empty list if no matches are found.
        """
        episodes = self.load_all()
        if not episodes:
            return []

        query_tokens = self._tokenize(content)
        if not query_tokens:
            return []

        # Calculate similarity for each episode
        scored_episodes: list[tuple[float, Episode]] = []
        for episode in episodes:
            episode_tokens = self._tokenize(episode.goal_id)
            similarity = self._jaccard_similarity(query_tokens, episode_tokens)
            if similarity > 0:
                scored_episodes.append((similarity, episode))

        if not scored_episodes:
            return []

        # Sort by similarity (highest first)
        scored_episodes.sort(key=lambda x: x[0], reverse=True)

        # Return top k episodes
        return [episode for _, episode in scored_episodes[:k]]


class DailyGoalProtocol:
    """Protocol for DailyGoal to avoid circular imports."""
    tags: list[str]


@dataclass
class PreferenceSignal:
    """Signal extracted from a checkpoint decision."""

    signal_type: str = ""  # e.g., "approved_cost", "rejected_risk"
    trigger: str = ""
    chosen_option: str = ""
    context_summary: str = ""
    timestamp: Any = None  # Can be str or datetime
    was_accepted: bool = False  # True if user approved/proceeded


class PreferenceLearner:
    """Extracts preference signals from checkpoint decisions.

    Analyzes checkpoint resolutions to learn user preferences
    for future recommendations and autopilot behavior.
    """

    def __init__(self) -> None:
        """Initialize PreferenceLearner."""
        self.signals: list[PreferenceSignal] = []

    def extract_signal(self, checkpoint: "Checkpoint") -> Optional[PreferenceSignal]:
        """Extract a preference signal from a resolved checkpoint.

        Args:
            checkpoint: A resolved checkpoint with a decision.

        Returns:
            PreferenceSignal if the checkpoint contains learnable info,
            None otherwise.
        """
        if checkpoint.chosen_option is None:
            return None

        # Determine if this was an acceptance (proceed, approve, etc)
        chosen_lower = checkpoint.chosen_option.lower() if checkpoint.chosen_option else ""
        was_accepted = any(
            kw in chosen_lower
            for kw in ["proceed", "approve", "accept", "continue", "yes"]
        )

        # Get trigger value as string for signal_type
        trigger_value = (
            checkpoint.trigger.value
            if hasattr(checkpoint.trigger, 'value')
            else str(checkpoint.trigger)
        )

        signal = PreferenceSignal(
            signal_type=f"{checkpoint.chosen_option}_{trigger_value}",
            trigger=trigger_value,
            chosen_option=checkpoint.chosen_option,
            context_summary=checkpoint.context[:200] if checkpoint.context else "",
            timestamp=datetime.now().isoformat(),
            was_accepted=was_accepted,
        )
        self.signals.append(signal)
        return signal

    def get_signals(self) -> list[PreferenceSignal]:
        """Get all collected preference signals.

        Returns:
            List of PreferenceSignal objects.
        """
        return self.signals.copy()

    # Tag to trigger type mapping for find_similar_decisions
    TAG_TO_TRIGGER_MAP = {
        "ui": "UX_CHANGE",
        "ux": "UX_CHANGE",
        "architecture": "ARCHITECTURE",
        "refactor": "ARCHITECTURE",
    }

    # Triggers that are always considered relevant
    ALWAYS_RELEVANT_TRIGGERS = {"COST_SINGLE", "COST_CUMULATIVE"}

    def find_similar_decisions(
        self, goal: DailyGoalProtocol, k: int = 3
    ) -> list[dict[str, Any]]:
        """Find similar past checkpoint decisions for a goal.

        Args:
            goal: A DailyGoal object with tags attribute.
            k: Maximum number of results to return (default: 3).

        Returns:
            List of dicts with keys: trigger, context_summary, was_accepted,
            chosen_option, timestamp. Sorted by recency (most recent first).
        """
        if not self.signals:
            return []

        # Determine which triggers are relevant based on goal tags
        relevant_triggers: set[str] = set(self.ALWAYS_RELEVANT_TRIGGERS)

        for tag in goal.tags:
            tag_lower = tag.lower()
            if tag_lower in self.TAG_TO_TRIGGER_MAP:
                relevant_triggers.add(self.TAG_TO_TRIGGER_MAP[tag_lower])

        # Filter signals to those with relevant triggers
        matching_signals: list[PreferenceSignal] = []
        for signal in self.signals:
            if signal.trigger in relevant_triggers:
                matching_signals.append(signal)

        # Sort by timestamp descending (most recent first)
        # Handle both string and datetime timestamps
        def get_timestamp_key(s: PreferenceSignal) -> str:
            ts = s.timestamp
            if hasattr(ts, 'isoformat'):
                return ts.isoformat()
            return str(ts) if ts else ""

        matching_signals.sort(key=get_timestamp_key, reverse=True)

        # Convert to output format and apply limit
        result: list[dict[str, Any]] = []
        for signal in matching_signals[:k]:
            result.append({
                "trigger": signal.trigger,
                "context_summary": signal.context_summary,
                "was_accepted": signal.was_accepted,
                "chosen_option": signal.chosen_option,
                "timestamp": signal.timestamp,
            })

        return result