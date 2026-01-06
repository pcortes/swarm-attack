"""Pattern Extractor for extracting patterns from episode history.

This module provides components for extracting reusable patterns from
episode execution history. It analyzes episodes to identify:
- Success patterns (what leads to completion)
- Failure patterns (what leads to failure)
- Recovery patterns (what recoveries work)
- Context patterns (optimal context construction)

Key Classes:
- PatternExtractor: Main extractor that analyzes episodes
- ExtractedPattern: Individual extracted pattern with evidence
- PatternType: Enumeration of pattern categories
- ExtractionResult: Result of pattern extraction operation
"""

from __future__ import annotations

import re
import uuid
from collections import Counter
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from swarm_attack.config import SwarmConfig
    from swarm_attack.chief_of_staff.episodes import Episode, EpisodeStore

from swarm_attack.learning.strategy_optimizer import Pattern, PatternSet


# =============================================================================
# Enums
# =============================================================================


class PatternType(Enum):
    """Types of patterns that can be extracted from episodes."""

    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    RECOVERY = "RECOVERY"
    CONTEXT = "CONTEXT"


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class ExtractedPattern:
    """Represents a pattern extracted from episode analysis.

    Attributes:
        pattern_id: Unique identifier for the pattern.
        pattern_type: Type of pattern (SUCCESS, FAILURE, RECOVERY, CONTEXT).
        description: Human-readable description of the pattern.
        confidence: Confidence score (0.0 to 1.0) in the pattern's validity.
        success_rate: Historical success rate (0.0 to 1.0) when this pattern occurs.
        evidence_episode_ids: List of episode IDs that support this pattern.
        metadata: Additional pattern-specific metadata.
    """

    pattern_id: str
    pattern_type: PatternType
    description: str
    confidence: float
    success_rate: float
    evidence_episode_ids: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        data = asdict(self)
        data["pattern_type"] = self.pattern_type.value
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ExtractedPattern:
        """Create from dictionary."""
        data = data.copy()
        if isinstance(data.get("pattern_type"), str):
            data["pattern_type"] = PatternType(data["pattern_type"])
        return cls(**data)

    def to_optimizer_pattern(self) -> Pattern:
        """Convert to strategy_optimizer.Pattern format.

        Maps PatternType to strategy_optimizer pattern_type:
        - SUCCESS -> "prompt" (success patterns inform prompt engineering)
        - FAILURE -> "prompt" (failure patterns inform what to avoid)
        - RECOVERY -> "recovery" (recovery patterns directly map)
        - CONTEXT -> "context" (context patterns directly map)

        Returns:
            Pattern object compatible with StrategyOptimizer.
        """
        # Map PatternType to optimizer pattern_type
        type_mapping = {
            PatternType.SUCCESS: "prompt",
            PatternType.FAILURE: "prompt",
            PatternType.RECOVERY: "recovery",
            PatternType.CONTEXT: "context",
        }

        return Pattern(
            pattern_id=self.pattern_id,
            pattern_type=type_mapping.get(self.pattern_type, "prompt"),
            description=self.description,
            confidence=self.confidence,
            success_rate=self.success_rate,
            metadata=self.metadata.copy(),
        )


@dataclass
class ExtractionResult:
    """Result of pattern extraction from episodes.

    Attributes:
        total_episodes_analyzed: Number of episodes that were analyzed.
        patterns_extracted: Total number of patterns extracted.
        success_patterns: List of success patterns.
        failure_patterns: List of failure patterns.
        recovery_patterns: List of recovery patterns.
        context_patterns: List of context patterns.
    """

    total_episodes_analyzed: int
    patterns_extracted: int
    success_patterns: list[ExtractedPattern] = field(default_factory=list)
    failure_patterns: list[ExtractedPattern] = field(default_factory=list)
    recovery_patterns: list[ExtractedPattern] = field(default_factory=list)
    context_patterns: list[ExtractedPattern] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "total_episodes_analyzed": self.total_episodes_analyzed,
            "patterns_extracted": self.patterns_extracted,
            "success_patterns": [p.to_dict() for p in self.success_patterns],
            "failure_patterns": [p.to_dict() for p in self.failure_patterns],
            "recovery_patterns": [p.to_dict() for p in self.recovery_patterns],
            "context_patterns": [p.to_dict() for p in self.context_patterns],
        }

    def get_all_patterns(self) -> list[ExtractedPattern]:
        """Get all patterns from all categories.

        Returns:
            Combined list of all extracted patterns.
        """
        return (
            self.success_patterns +
            self.failure_patterns +
            self.recovery_patterns +
            self.context_patterns
        )


# =============================================================================
# Pattern Extractor
# =============================================================================


class PatternExtractor:
    """Extracts patterns from episode history for strategy optimization.

    Analyzes episodes to identify:
    - Success patterns: characteristics of successful episodes
    - Failure patterns: characteristics that lead to failures
    - Recovery patterns: recovery strategies that work
    - Context patterns: optimal context construction approaches

    Attributes:
        config: SwarmConfig for accessing project settings.
        min_confidence: Minimum confidence threshold for pattern inclusion.
        episode_store: Optional EpisodeStore for loading episodes.

    Example:
        >>> extractor = PatternExtractor(config, min_confidence=0.7)
        >>> result = extractor.extract_all(episodes)
        >>> pattern_set = extractor.to_pattern_set(result)
    """

    # Context keywords to detect in notes
    CONTEXT_KEYWORDS = {
        "tdd": "Include TDD approach in context",
        "test": "Include test information in context",
        "analysis": "Include root cause analysis in context",
        "comprehensive": "Include comprehensive context",
        "module": "Include module registry in context",
        "registry": "Include module registry in context",
        "dependency": "Include dependency information in context",
    }

    # Recovery level mapping
    RECOVERY_LEVELS = {"RETRY", "SIMPLIFY", "SKIP", "ESCALATE"}

    def __init__(
        self,
        config: Optional[SwarmConfig] = None,
        min_confidence: float = 0.7,
        episode_store: Optional[EpisodeStore] = None,
    ) -> None:
        """Initialize the PatternExtractor.

        Args:
            config: SwarmConfig for project settings (optional).
            min_confidence: Minimum confidence threshold for pattern inclusion.
                           Must be between 0.0 and 1.0.
            episode_store: Optional EpisodeStore for loading episodes.

        Raises:
            ValueError: If min_confidence is not between 0.0 and 1.0.
        """
        if min_confidence < 0.0 or min_confidence > 1.0:
            raise ValueError(
                f"min_confidence must be between 0.0 and 1.0, got {min_confidence}"
            )

        self.config = config
        self.min_confidence = min_confidence
        self.episode_store = episode_store

    def extract_all(self, episodes: list[Episode]) -> ExtractionResult:
        """Extract all pattern types from episodes.

        Args:
            episodes: List of Episode objects to analyze.

        Returns:
            ExtractionResult containing all extracted patterns.

        Raises:
            ValueError: If episodes is None.
            TypeError: If episodes is not a list.
        """
        if episodes is None:
            raise ValueError("episodes cannot be None")
        if not isinstance(episodes, list):
            raise TypeError(f"episodes must be a list, got {type(episodes)}")

        if not episodes:
            return ExtractionResult(
                total_episodes_analyzed=0,
                patterns_extracted=0,
            )

        success_patterns = self.extract_success_patterns(episodes)
        failure_patterns = self.extract_failure_patterns(episodes)
        recovery_patterns = self.extract_recovery_patterns(episodes)
        context_patterns = self.extract_context_patterns(episodes)

        total_patterns = (
            len(success_patterns) +
            len(failure_patterns) +
            len(recovery_patterns) +
            len(context_patterns)
        )

        return ExtractionResult(
            total_episodes_analyzed=len(episodes),
            patterns_extracted=total_patterns,
            success_patterns=success_patterns,
            failure_patterns=failure_patterns,
            recovery_patterns=recovery_patterns,
            context_patterns=context_patterns,
        )

    def extract_from_store(self, limit: int = 100) -> ExtractionResult:
        """Extract patterns from episodes loaded from the episode store.

        Args:
            limit: Maximum number of episodes to load and analyze.

        Returns:
            ExtractionResult containing all extracted patterns.

        Raises:
            ValueError: If no episode store is configured.
        """
        if self.episode_store is None:
            raise ValueError("No episode store configured")

        episodes = self.episode_store.load_recent(limit=limit)
        return self.extract_all(episodes)

    def extract_success_patterns(self, episodes: list[Episode]) -> list[ExtractedPattern]:
        """Extract patterns from successful episodes.

        Analyzes successful episodes to identify characteristics
        that correlate with success (low cost, fast completion, etc.).

        Args:
            episodes: List of episodes to analyze.

        Returns:
            List of ExtractedPattern objects for success patterns.
        """
        successful = [ep for ep in episodes if ep.success]

        if not successful:
            return []

        patterns: list[ExtractedPattern] = []
        success_rate = len(successful) / len(episodes) if episodes else 0.0

        # Analyze cost efficiency
        avg_cost = sum(ep.cost_usd for ep in successful) / len(successful)
        low_cost_eps = [ep for ep in successful if ep.cost_usd < avg_cost]

        if len(low_cost_eps) >= 2:
            confidence = min(1.0, 0.5 + len(low_cost_eps) / len(successful))
            if confidence >= self.min_confidence:
                patterns.append(ExtractedPattern(
                    pattern_id=f"success-cost-{uuid.uuid4().hex[:8]}",
                    pattern_type=PatternType.SUCCESS,
                    description="Lower cost correlates with success",
                    confidence=confidence,
                    success_rate=success_rate,
                    evidence_episode_ids=[ep.episode_id for ep in low_cost_eps],
                    metadata={"avg_cost": avg_cost, "pattern": "low_cost"},
                ))

        # Analyze duration efficiency
        avg_duration = sum(ep.duration_seconds for ep in successful) / len(successful)
        fast_eps = [ep for ep in successful if ep.duration_seconds < avg_duration]

        if len(fast_eps) >= 2:
            confidence = min(1.0, 0.5 + len(fast_eps) / len(successful))
            if confidence >= self.min_confidence:
                patterns.append(ExtractedPattern(
                    pattern_id=f"success-duration-{uuid.uuid4().hex[:8]}",
                    pattern_type=PatternType.SUCCESS,
                    description="Faster completion correlates with success",
                    confidence=confidence,
                    success_rate=success_rate,
                    evidence_episode_ids=[ep.episode_id for ep in fast_eps],
                    metadata={"avg_duration": avg_duration, "pattern": "fast_completion"},
                ))

        # Analyze zero-retry success
        no_retry_eps = [ep for ep in successful if ep.retry_count == 0]
        if len(no_retry_eps) >= 2:
            confidence = min(1.0, 0.5 + len(no_retry_eps) / len(successful))
            if confidence >= self.min_confidence:
                patterns.append(ExtractedPattern(
                    pattern_id=f"success-noretry-{uuid.uuid4().hex[:8]}",
                    pattern_type=PatternType.SUCCESS,
                    description="First-try success indicates good preparation",
                    confidence=confidence,
                    success_rate=success_rate,
                    evidence_episode_ids=[ep.episode_id for ep in no_retry_eps],
                    metadata={"pattern": "no_retry"},
                ))

        return patterns

    def extract_failure_patterns(self, episodes: list[Episode]) -> list[ExtractedPattern]:
        """Extract patterns from failed episodes.

        Analyzes failed episodes to identify characteristics
        that correlate with failure (high cost, timeouts, specific errors).

        Args:
            episodes: List of episodes to analyze.

        Returns:
            List of ExtractedPattern objects for failure patterns.
        """
        failed = [ep for ep in episodes if not ep.success]

        if not failed:
            return []

        patterns: list[ExtractedPattern] = []
        failure_rate = len(failed) / len(episodes) if episodes else 0.0

        # Analyze error types
        error_types: dict[str, list[Episode]] = {}
        for ep in failed:
            if ep.error:
                error_key = self._categorize_error(ep.error)
                if error_key not in error_types:
                    error_types[error_key] = []
                error_types[error_key].append(ep)

        for error_key, error_eps in error_types.items():
            if len(error_eps) >= 2:
                confidence = min(1.0, 0.6 + len(error_eps) / len(failed) * 0.3)
                if confidence >= self.min_confidence:
                    patterns.append(ExtractedPattern(
                        pattern_id=f"failure-{error_key}-{uuid.uuid4().hex[:8]}",
                        pattern_type=PatternType.FAILURE,
                        description=f"{error_key.replace('_', ' ').title()} errors lead to failure",
                        confidence=confidence,
                        success_rate=1.0 - failure_rate,  # Inverted for failure
                        evidence_episode_ids=[ep.episode_id for ep in error_eps],
                        metadata={"error_type": error_key, "count": len(error_eps)},
                    ))

        # Analyze high retry count
        high_retry_eps = [ep for ep in failed if ep.retry_count >= 2]
        if len(high_retry_eps) >= 2:
            confidence = min(1.0, 0.5 + len(high_retry_eps) / len(failed))
            if confidence >= self.min_confidence:
                patterns.append(ExtractedPattern(
                    pattern_id=f"failure-highretry-{uuid.uuid4().hex[:8]}",
                    pattern_type=PatternType.FAILURE,
                    description="High retry count indicates underlying issue",
                    confidence=confidence,
                    success_rate=1.0 - failure_rate,
                    evidence_episode_ids=[ep.episode_id for ep in high_retry_eps],
                    metadata={"pattern": "high_retry"},
                ))

        # Analyze checkpoint triggers in failures
        checkpoint_counts: Counter = Counter()
        for ep in failed:
            for checkpoint in ep.checkpoints_triggered:
                checkpoint_counts[checkpoint] += 1

        for checkpoint, count in checkpoint_counts.items():
            if count >= 2:
                confidence = min(1.0, 0.5 + count / len(failed))
                if confidence >= self.min_confidence:
                    patterns.append(ExtractedPattern(
                        pattern_id=f"failure-checkpoint-{checkpoint.lower()}-{uuid.uuid4().hex[:8]}",
                        pattern_type=PatternType.FAILURE,
                        description=f"{checkpoint} checkpoint often precedes failure",
                        confidence=confidence,
                        success_rate=1.0 - failure_rate,
                        evidence_episode_ids=[
                            ep.episode_id for ep in failed
                            if checkpoint in ep.checkpoints_triggered
                        ],
                        metadata={"checkpoint": checkpoint, "count": count},
                    ))

        return patterns

    def extract_recovery_patterns(self, episodes: list[Episode]) -> list[ExtractedPattern]:
        """Extract patterns from episodes with successful recoveries.

        Analyzes episodes where recovery strategies led to success
        despite initial difficulties.

        Args:
            episodes: List of episodes to analyze.

        Returns:
            List of ExtractedPattern objects for recovery patterns.
        """
        # Find episodes that had retries or recovery and succeeded
        recovered = [
            ep for ep in episodes
            if ep.success and (ep.retry_count > 0 or ep.recovery_level)
        ]

        if not recovered:
            return []

        patterns: list[ExtractedPattern] = []

        # Group by recovery level
        by_recovery_level: dict[str, list[Episode]] = {}
        for ep in recovered:
            level = ep.recovery_level or "RETRY"
            if level not in by_recovery_level:
                by_recovery_level[level] = []
            by_recovery_level[level].append(ep)

        # Calculate effectiveness for each recovery level
        for level, level_eps in by_recovery_level.items():
            if len(level_eps) >= 1:
                # Compare to failed episodes with same recovery level
                failed_same_level = [
                    ep for ep in episodes
                    if not ep.success and ep.recovery_level == level
                ]
                total_with_level = len(level_eps) + len(failed_same_level)
                effectiveness = len(level_eps) / total_with_level if total_with_level > 0 else 1.0

                confidence = min(1.0, 0.5 + effectiveness * 0.4)
                if confidence >= self.min_confidence:
                    patterns.append(ExtractedPattern(
                        pattern_id=f"recovery-{level.lower()}-{uuid.uuid4().hex[:8]}",
                        pattern_type=PatternType.RECOVERY,
                        description=f"{level} recovery strategy is effective",
                        confidence=confidence,
                        success_rate=effectiveness,
                        evidence_episode_ids=[ep.episode_id for ep in level_eps],
                        metadata={
                            "recovery_level": level,
                            "effectiveness": effectiveness,
                            "success_count": len(level_eps),
                            "total_attempts": total_with_level,
                        },
                    ))

        # Analyze retry counts in successful recoveries
        if recovered:
            avg_retries = sum(ep.retry_count for ep in recovered) / len(recovered)
            low_retry_recoveries = [ep for ep in recovered if ep.retry_count <= avg_retries]

            if len(low_retry_recoveries) >= 2:
                confidence = min(1.0, 0.6 + len(low_retry_recoveries) / len(recovered) * 0.3)
                if confidence >= self.min_confidence:
                    patterns.append(ExtractedPattern(
                        pattern_id=f"recovery-lowretry-{uuid.uuid4().hex[:8]}",
                        pattern_type=PatternType.RECOVERY,
                        description="Fewer retries in recovery correlates with success",
                        confidence=confidence,
                        success_rate=len(recovered) / len(episodes) if episodes else 0.0,
                        evidence_episode_ids=[ep.episode_id for ep in low_retry_recoveries],
                        metadata={"avg_retries": avg_retries, "pattern": "low_retry_recovery"},
                    ))

        return patterns

    def extract_context_patterns(self, episodes: list[Episode]) -> list[ExtractedPattern]:
        """Extract patterns about optimal context construction.

        Analyzes episode notes to identify context elements
        that correlate with success.

        Args:
            episodes: List of episodes to analyze.

        Returns:
            List of ExtractedPattern objects for context patterns.
        """
        successful = [ep for ep in episodes if ep.success]

        if not successful:
            return []

        patterns: list[ExtractedPattern] = []
        success_rate = len(successful) / len(episodes) if episodes else 0.0

        # Analyze keywords in notes
        keyword_episodes: dict[str, list[Episode]] = {}

        for ep in successful:
            if ep.notes:
                notes_lower = ep.notes.lower()
                for keyword, description in self.CONTEXT_KEYWORDS.items():
                    if keyword in notes_lower:
                        if description not in keyword_episodes:
                            keyword_episodes[description] = []
                        if ep not in keyword_episodes[description]:
                            keyword_episodes[description].append(ep)

        for description, kw_eps in keyword_episodes.items():
            if len(kw_eps) >= 1:
                confidence = min(1.0, 0.5 + len(kw_eps) / len(successful))
                if confidence >= self.min_confidence:
                    patterns.append(ExtractedPattern(
                        pattern_id=f"context-{uuid.uuid4().hex[:8]}",
                        pattern_type=PatternType.CONTEXT,
                        description=description,
                        confidence=confidence,
                        success_rate=success_rate,
                        evidence_episode_ids=[ep.episode_id for ep in kw_eps],
                        metadata={"pattern": "context_keyword"},
                    ))

        return patterns

    def to_pattern_set(self, result: ExtractionResult) -> PatternSet:
        """Convert extraction result to a PatternSet for strategy optimization.

        Args:
            result: ExtractionResult from extract_all().

        Returns:
            PatternSet compatible with StrategyOptimizer.
        """
        all_patterns = result.get_all_patterns()
        optimizer_patterns = [p.to_optimizer_pattern() for p in all_patterns]

        return PatternSet(patterns=optimizer_patterns)

    # =========================================================================
    # Statistical Analysis Methods
    # =========================================================================

    def calculate_success_rate(self, episodes: list[Episode]) -> float:
        """Calculate overall success rate from episodes.

        Args:
            episodes: List of episodes to analyze.

        Returns:
            Success rate between 0.0 and 1.0.
        """
        if not episodes:
            return 0.0

        successful = sum(1 for ep in episodes if ep.success)
        return successful / len(episodes)

    def calculate_average_cost(self, episodes: list[Episode]) -> float:
        """Calculate average cost from episodes.

        Args:
            episodes: List of episodes to analyze.

        Returns:
            Average cost in USD.
        """
        if not episodes:
            return 0.0

        return sum(ep.cost_usd for ep in episodes) / len(episodes)

    def calculate_average_duration(self, episodes: list[Episode]) -> float:
        """Calculate average duration from episodes.

        Args:
            episodes: List of episodes to analyze.

        Returns:
            Average duration in seconds.
        """
        if not episodes:
            return 0.0

        return sum(ep.duration_seconds for ep in episodes) / len(episodes)

    def calculate_recovery_effectiveness(
        self, episodes: list[Episode]
    ) -> dict[str, float]:
        """Calculate effectiveness of each recovery level.

        Args:
            episodes: List of episodes to analyze.

        Returns:
            Dictionary mapping recovery level to effectiveness (0.0 to 1.0).
        """
        effectiveness: dict[str, float] = {}

        # Group by recovery level
        by_level: dict[str, list[Episode]] = {}
        for ep in episodes:
            if ep.recovery_level:
                level = ep.recovery_level
                if level not in by_level:
                    by_level[level] = []
                by_level[level].append(ep)

        for level, level_eps in by_level.items():
            successful = sum(1 for ep in level_eps if ep.success)
            effectiveness[level] = successful / len(level_eps) if level_eps else 0.0

        return effectiveness

    def identify_checkpoint_correlations(
        self, episodes: list[Episode]
    ) -> dict[str, dict[str, float]]:
        """Identify correlations between checkpoints and outcomes.

        Args:
            episodes: List of episodes to analyze.

        Returns:
            Dictionary mapping checkpoint type to success/failure rates.
        """
        correlations: dict[str, dict[str, float]] = {}

        # Collect all checkpoints
        all_checkpoints: set[str] = set()
        for ep in episodes:
            all_checkpoints.update(ep.checkpoints_triggered)

        for checkpoint in all_checkpoints:
            checkpoint_eps = [
                ep for ep in episodes
                if checkpoint in ep.checkpoints_triggered
            ]

            if checkpoint_eps:
                successful = sum(1 for ep in checkpoint_eps if ep.success)
                total = len(checkpoint_eps)
                correlations[checkpoint] = {
                    "success_rate": successful / total,
                    "failure_rate": (total - successful) / total,
                    "count": total,
                }

        return correlations

    # =========================================================================
    # Private Helper Methods
    # =========================================================================

    def _categorize_error(self, error: str) -> str:
        """Categorize an error message into a type.

        Args:
            error: Error message string.

        Returns:
            Error category string.
        """
        error_lower = error.lower()

        if "timeout" in error_lower:
            return "timeout"
        elif "circular" in error_lower or "dependency" in error_lower:
            return "dependency"
        elif "complex" in error_lower:
            return "complexity"
        elif "rate limit" in error_lower:
            return "rate_limit"
        elif "auth" in error_lower:
            return "authentication"
        else:
            return "other"
