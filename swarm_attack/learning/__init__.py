"""Learning module for Swarm Attack.

This module provides components for learning from execution patterns
and optimizing strategies for better performance.

Key Components:
- StrategyOptimizer: Applies patterns to optimize execution strategies
- PatternExtractor: Extracts patterns from coder episodes
- EpisodePatternExtractor: Extracts patterns from chief-of-staff episodes
- EpisodeLogger: Logs execution episodes for learning (simple coder integration)
- TelemetryEpisodeLogger: Detailed telemetry logging for episodes
- CoderIntegration: Wires learning layer to CoderAgent
"""

from swarm_attack.learning.strategy_optimizer import (
    StrategyOptimizer,
    Task,
    PatternSet,
    Pattern,
    OptimizedStrategy,
    PromptSuggestion,
    RecoveryStrategy,
)
from swarm_attack.learning.coder_integration import (
    CoderIntegration,
    EpisodeLogger,
    PatternExtractor,
    Episode,
)
from swarm_attack.learning.pattern_extractor import (
    PatternExtractor as EpisodePatternExtractor,
    ExtractedPattern,
    PatternType,
    ExtractionResult,
)
from swarm_attack.learning.episode_logger import (
    EpisodeLogger as TelemetryEpisodeLogger,
    Episode as TelemetryEpisode,
    Action,
    Outcome,
    ContextSnapshot,
    RecoveryAttempt,
)

__all__ = [
    # Strategy optimizer
    "StrategyOptimizer",
    "Task",
    "PatternSet",
    "Pattern",
    "OptimizedStrategy",
    "PromptSuggestion",
    "RecoveryStrategy",
    # Coder integration
    "CoderIntegration",
    "EpisodeLogger",
    "PatternExtractor",
    "Episode",
    # Episode pattern extraction (chief-of-staff)
    "EpisodePatternExtractor",
    "ExtractedPattern",
    "PatternType",
    "ExtractionResult",
    # Telemetry episode logging
    "TelemetryEpisodeLogger",
    "TelemetryEpisode",
    "Action",
    "Outcome",
    "ContextSnapshot",
    "RecoveryAttempt",
]
