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


def _tokenize(text: str) -> set[str]:
    """Tokenize text into lowercase words for Jaccard similarity.
    
    Args:
        text: Text to tokenize.
        
    Returns:
        Set of lowercase word tokens.
    """
    # Convert to lowercase and split on whitespace/punctuation
    words = text.lower().split()
    return set(words)


def _jaccard_similarity(set1: set[str], set2: set[str]) -> float:
    """Calculate Jaccard similarity between two sets.
    
    Args:
        set1: First set of tokens.
        set2: Second set of tokens.
        
    Returns:
        Jaccard similarity coefficient (0.0 to 1.0).
    """
    if not set1 or not set2:
        return 0.0
    intersection = len(set1 & set2)
    union = len(set1 | set2)
    if union == 0:
        return 0.0
    return intersection / union


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

    def find_similar(self, content: str, k: int = 5) -> list[Episode]:
        """Find similar past episodes based on content matching.
        
        Uses keyword-based Jaccard similarity for matching episodes
        by comparing the search content against episode goal_id fields.
        
        Args:
            content: Search content to match against episodes.
            k: Maximum number of episodes to return. Defaults to 5.
            
        Returns:
            List of Episode objects sorted by relevance (highest first),
            limited to k results. Returns empty list when no matches found.
        """
        episodes = self.load_all()
        if not episodes:
            return []
        
        # Tokenize the search content
        query_tokens = _tokenize(content)
        if not query_tokens:
            return []
        
        # Calculate similarity scores for all episodes
        scored_episodes: list[tuple[float, Episode]] = []
        for episode in episodes:
            episode_tokens = _tokenize(episode.goal_id)
            similarity = _jaccard_similarity(query_tokens, episode_tokens)
            if similarity > 0:
                scored_episodes.append((similarity, episode))
        
        # Sort by similarity (highest first)
        scored_episodes.sort(key=lambda x: x[0], reverse=True)
        
        # Return top k episodes
        return [episode for _, episode in scored_episodes[:k]]


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

    def extract_signal(self, checkpoint: "Checkpoint") -> Optional[PreferenceSignal]:
        """Extract a preference signal from a resolved checkpoint.

        Args:
            checkpoint: A resolved checkpoint with decision info.

        Returns:
            PreferenceSignal if extractable, None otherwise.
        """
        if not hasattr(checkpoint, "resolution") or not checkpoint.resolution:
            return None

        signal = PreferenceSignal(
            signal_type=f"{checkpoint.resolution}_{checkpoint.trigger}",
            trigger=checkpoint.trigger,
            chosen_option=checkpoint.resolution,
            context_summary=checkpoint.description[:100] if checkpoint.description else "",
            timestamp=datetime.now().isoformat(),
        )
        self.signals.append(signal)
        return signal

    def get_signals(self) -> list[PreferenceSignal]:
        """Get all collected preference signals.

        Returns:
            List of PreferenceSignal objects.
        """
        return self.signals.copy()