"""Relevance scoring for memory entries.

Provides time-based decay and category-weighted relevance scoring.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from swarm_attack.memory.store import MemoryEntry


class RelevanceScorer:
    """Calculate relevance scores for memory entries.

    Score formula: hit_count * category_weight * recency_factor

    Where:
    - hit_count: Number of times entry was queried (at least 1)
    - category_weight: Weight based on entry category
    - recency_factor: Exponential decay based on age (0.95 ^ (age_hours / 24))
    """

    CATEGORY_WEIGHTS = {
        "schema_warning": 1.5,
        "bug_fix": 1.3,
        "verification_failure": 1.2,
        "recovery_action": 1.0,
    }
    DEFAULT_WEIGHT = 1.0

    def score(self, entry: "MemoryEntry", now: datetime = None) -> float:
        """Calculate relevance score for entry.

        Args:
            entry: The memory entry to score.
            now: Reference time for recency calculation. Defaults to now.

        Returns:
            Relevance score (higher is more relevant).
        """
        if now is None:
            now = datetime.now()

        # Get hit count (at least 1 for zero-hit entries to have positive score)
        hit_count = max(1, entry.hit_count)

        # Get category weight (default if unknown category)
        category_weight = self.CATEGORY_WEIGHTS.get(entry.category, self.DEFAULT_WEIGHT)

        # Calculate age in hours from created_at timestamp
        created_at = datetime.fromisoformat(entry.created_at)
        age_delta = now - created_at
        age_hours = age_delta.total_seconds() / 3600.0

        # Calculate recency factor using decay formula
        recency_factor = self.decay_factor(age_hours)

        # Combined score: hit_count * category_weight * recency_factor
        return hit_count * category_weight * recency_factor

    def decay_factor(self, age_hours: float) -> float:
        """Calculate time-based decay factor.

        Args:
            age_hours: Age of entry in hours.

        Returns:
            Decay factor between 0 and 1.
            Formula: 0.95 ^ (age_hours / 24)
        """
        return 0.95 ** (age_hours / 24.0)
