"""Integration module connecting learning layer to CoderAgent.

This module wires EpisodeLogger, PatternExtractor, and StrategyOptimizer
into the CoderAgent execution loop to enable learning from past executions
and applying optimized strategies.

Key Classes:
- Episode: Record of a single coder execution episode
- EpisodeLogger: Persistent logging of execution episodes
- PatternExtractor: Extracts patterns from historical episodes
- CoderIntegration: Main integration class wiring components together

Usage:
    from swarm_attack.learning.coder_integration import CoderIntegration

    integration = CoderIntegration(config, base_path)

    # Wrap coder execution
    result = integration.wrap_coder_run(
        coder_fn=coder.run,
        context={"feature_id": "my-feature", "issue_number": 1},
    )

    # Get optimized strategy
    strategy = integration.get_optimized_strategy(
        feature_id="my-feature",
        issue_number=1,
        task_description="Implement auth module",
    )
"""

from __future__ import annotations

import json
import uuid
from collections import Counter
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Optional

from swarm_attack.learning.strategy_optimizer import (
    StrategyOptimizer,
    Task,
    PatternSet,
    Pattern,
    OptimizedStrategy,
)

if TYPE_CHECKING:
    from swarm_attack.config import SwarmConfig


# =============================================================================
# Episode Data Class
# =============================================================================


@dataclass
class Episode:
    """Record of a single coder execution episode.

    Tracks the full lifecycle of a coder run including success/failure,
    cost, duration, retries, and associated metadata for pattern learning.

    Attributes:
        episode_id: Unique identifier for this episode.
        feature_id: Feature being implemented.
        issue_number: Issue number being addressed.
        task_type: Type of task (implementation, bug_fix, refactor).
        status: Current status (in_progress, completed, failed).
        success: Whether the execution succeeded.
        cost_usd: Cost in USD for this execution.
        duration_seconds: Duration of execution in seconds.
        retry_count: Number of retries attempted.
        error: Error message if failed.
        files_created: List of files created.
        files_modified: List of files modified.
        tool_sequence: Sequence of tools used.
        prompt_metadata: Metadata about the prompt used.
        recovery_actions: Recovery actions taken.
        started_at: ISO timestamp when started.
        completed_at: ISO timestamp when completed.
    """

    episode_id: str
    feature_id: str
    issue_number: int
    task_type: str = "implementation"
    status: str = "in_progress"
    success: bool = False
    cost_usd: float = 0.0
    duration_seconds: int = 0
    retry_count: int = 0
    error: Optional[str] = None
    files_created: list[str] = field(default_factory=list)
    files_modified: list[str] = field(default_factory=list)
    tool_sequence: list[str] = field(default_factory=list)
    prompt_metadata: dict[str, Any] = field(default_factory=dict)
    recovery_actions: list[str] = field(default_factory=list)
    started_at: str = ""
    completed_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert Episode to dictionary for serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Episode:
        """Create Episode from dictionary."""
        return cls(
            episode_id=data.get("episode_id", ""),
            feature_id=data.get("feature_id", ""),
            issue_number=data.get("issue_number", 0),
            task_type=data.get("task_type", "implementation"),
            status=data.get("status", "in_progress"),
            success=data.get("success", False),
            cost_usd=data.get("cost_usd", 0.0),
            duration_seconds=data.get("duration_seconds", 0),
            retry_count=data.get("retry_count", 0),
            error=data.get("error"),
            files_created=data.get("files_created", []),
            files_modified=data.get("files_modified", []),
            tool_sequence=data.get("tool_sequence", []),
            prompt_metadata=data.get("prompt_metadata", {}),
            recovery_actions=data.get("recovery_actions", []),
            started_at=data.get("started_at", ""),
            completed_at=data.get("completed_at", ""),
        )


# =============================================================================
# Episode Logger
# =============================================================================


class EpisodeLogger:
    """Persistent storage and logging for execution episodes.

    Stores episodes in JSONL format for efficient append-only logging
    and recent episode retrieval.

    Attributes:
        base_path: Base directory for episode storage.
    """

    def __init__(self, base_path: Optional[Path] = None) -> None:
        """Initialize EpisodeLogger.

        Args:
            base_path: Base directory for storage.
                      Defaults to .swarm/learning/episodes/
        """
        if base_path is None:
            base_path = Path.cwd() / ".swarm" / "learning" / "episodes"
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
        self._episodes_file = self.base_path / "episodes.jsonl"

    def start_episode(
        self,
        feature_id: str,
        issue_number: int,
        task_type: str = "implementation",
    ) -> Episode:
        """Start a new episode and return it.

        Args:
            feature_id: Feature being implemented.
            issue_number: Issue number being addressed.
            task_type: Type of task.

        Returns:
            New Episode instance in "in_progress" status.
        """
        episode = Episode(
            episode_id=f"ep-{uuid.uuid4().hex[:12]}",
            feature_id=feature_id,
            issue_number=issue_number,
            task_type=task_type,
            status="in_progress",
            started_at=datetime.now().isoformat(),
        )
        return episode

    def complete_episode(
        self,
        episode: Episode,
        success: bool,
        cost_usd: float = 0.0,
        error: Optional[str] = None,
        files_created: Optional[list[str]] = None,
        files_modified: Optional[list[str]] = None,
    ) -> None:
        """Complete an episode and persist it.

        Args:
            episode: The episode to complete.
            success: Whether the execution succeeded.
            cost_usd: Cost in USD.
            error: Error message if failed.
            files_created: List of files created.
            files_modified: List of files modified.
        """
        episode.success = success
        episode.cost_usd = cost_usd
        episode.status = "completed" if success else "failed"
        episode.completed_at = datetime.now().isoformat()

        if error:
            episode.error = error
        if files_created:
            episode.files_created = files_created
        if files_modified:
            episode.files_modified = files_modified

        # Calculate duration
        if episode.started_at and episode.completed_at:
            try:
                start = datetime.fromisoformat(episode.started_at)
                end = datetime.fromisoformat(episode.completed_at)
                episode.duration_seconds = int((end - start).total_seconds())
            except ValueError:
                pass

        self._persist(episode)

    def record_retry(
        self,
        episode: Episode,
        retry_number: int,
        error: str,
    ) -> None:
        """Record a retry attempt for an episode.

        Args:
            episode: The episode being retried.
            retry_number: The retry attempt number.
            error: The error that triggered the retry.
        """
        episode.retry_count = retry_number
        if error and error not in (episode.error or ""):
            episode.error = error

    def _persist(self, episode: Episode) -> None:
        """Persist an episode to the JSONL file.

        Args:
            episode: Episode to persist.
        """
        with open(self._episodes_file, "a") as f:
            f.write(json.dumps(episode.to_dict()) + "\n")

    def load_recent(self, limit: int = 100) -> list[Episode]:
        """Load the most recent episodes.

        Args:
            limit: Maximum number of episodes to return.

        Returns:
            List of Episode objects, most recent first.
        """
        episodes = self.load_all()
        episodes.reverse()  # Most recent first
        return episodes[:limit]

    def load_all(self) -> list[Episode]:
        """Load all episodes from storage.

        Returns:
            List of all Episode objects.
        """
        if not self._episodes_file.exists():
            return []

        episodes: list[Episode] = []
        with open(self._episodes_file, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    episodes.append(Episode.from_dict(data))
                except json.JSONDecodeError:
                    # Skip malformed lines
                    continue

        return episodes


# =============================================================================
# Pattern Extractor
# =============================================================================


class PatternExtractor:
    """Extracts patterns from historical execution episodes.

    Analyzes episode history to identify successful patterns for:
    - Prompt construction
    - Tool ordering
    - Context building
    - Recovery strategies

    Attributes:
        min_episodes: Minimum episodes required to extract a pattern.
        min_confidence: Minimum confidence threshold for patterns.
    """

    def __init__(
        self,
        min_episodes: int = 5,
        min_confidence: float = 0.6,
    ) -> None:
        """Initialize PatternExtractor.

        Args:
            min_episodes: Minimum episodes to form a pattern.
            min_confidence: Minimum confidence for pattern inclusion.
        """
        self.min_episodes = min_episodes
        self.min_confidence = min_confidence

    def extract_patterns(self, episodes: list[Episode]) -> PatternSet:
        """Extract patterns from a list of episodes.

        Args:
            episodes: List of episodes to analyze.

        Returns:
            PatternSet containing extracted patterns.
        """
        if len(episodes) < self.min_episodes:
            return PatternSet(patterns=[])

        patterns: list[Pattern] = []

        # Extract tool order patterns
        tool_patterns = self._extract_tool_order_patterns(episodes)
        patterns.extend(tool_patterns)

        # Extract prompt patterns
        prompt_patterns = self._extract_prompt_patterns(episodes)
        patterns.extend(prompt_patterns)

        # Extract context patterns
        context_patterns = self._extract_context_patterns(episodes)
        patterns.extend(context_patterns)

        # Extract recovery patterns
        recovery_patterns = self._extract_recovery_patterns(episodes)
        patterns.extend(recovery_patterns)

        # Filter by confidence
        filtered = [p for p in patterns if p.confidence >= self.min_confidence]

        return PatternSet(patterns=filtered)

    def _extract_tool_order_patterns(self, episodes: list[Episode]) -> list[Pattern]:
        """Extract tool ordering patterns from episodes.

        Args:
            episodes: Episodes to analyze.

        Returns:
            List of tool order patterns.
        """
        patterns: list[Pattern] = []

        # Count tool sequences in successful episodes
        successful = [ep for ep in episodes if ep.success and ep.tool_sequence]
        if len(successful) < self.min_episodes:
            return patterns

        # Find common tool sequences
        sequence_counts: Counter[tuple[str, ...]] = Counter()
        for ep in successful:
            if ep.tool_sequence:
                seq = tuple(ep.tool_sequence)
                sequence_counts[seq] += 1

        # Create patterns for common sequences
        for seq, count in sequence_counts.most_common(3):
            if count >= 3:  # At least 3 occurrences
                confidence = count / len(successful)
                success_rate = count / len(successful)

                pattern = Pattern(
                    pattern_id=f"tool-{uuid.uuid4().hex[:8]}",
                    pattern_type="tool_order",
                    description=f"Tool sequence: {' -> '.join(seq)}",
                    confidence=confidence,
                    success_rate=success_rate,
                    metadata={"order": list(seq)},
                )
                patterns.append(pattern)

        return patterns

    def _extract_prompt_patterns(self, episodes: list[Episode]) -> list[Pattern]:
        """Extract prompt construction patterns from episodes.

        Args:
            episodes: Episodes to analyze.

        Returns:
            List of prompt patterns.
        """
        patterns: list[Pattern] = []

        # Analyze prompt metadata from successful episodes
        successful = [
            ep for ep in episodes
            if ep.success and ep.prompt_metadata
        ]
        if len(successful) < self.min_episodes:
            return patterns

        # Find common prompt configurations
        config_counts: Counter[str] = Counter()
        for ep in successful:
            meta = ep.prompt_metadata
            if meta.get("included_context"):
                for ctx in meta["included_context"]:
                    config_counts[ctx] += 1
            if meta.get("included_examples"):
                config_counts["examples"] += 1

        # Create patterns for common configurations
        for config, count in config_counts.most_common(5):
            if count >= 3:
                confidence = count / len(successful)

                pattern = Pattern(
                    pattern_id=f"prompt-{uuid.uuid4().hex[:8]}",
                    pattern_type="prompt",
                    description=f"Include {config} in prompt",
                    confidence=confidence,
                    success_rate=confidence,
                    metadata={"include": config},
                )
                patterns.append(pattern)

        return patterns

    def _extract_context_patterns(self, episodes: list[Episode]) -> list[Pattern]:
        """Extract context building patterns from episodes.

        Args:
            episodes: Episodes to analyze.

        Returns:
            List of context patterns.
        """
        patterns: list[Pattern] = []

        successful = [ep for ep in episodes if ep.success and ep.prompt_metadata]
        if len(successful) < self.min_episodes:
            return patterns

        # Analyze what context was included
        context_items: Counter[str] = Counter()
        for ep in successful:
            meta = ep.prompt_metadata
            if meta.get("included_context"):
                for item in meta["included_context"]:
                    context_items[item] += 1

        # Create context patterns
        for item, count in context_items.most_common(5):
            if count >= 3:
                confidence = count / len(successful)

                pattern = Pattern(
                    pattern_id=f"ctx-{uuid.uuid4().hex[:8]}",
                    pattern_type="context",
                    description=f"Include {item} in context",
                    confidence=confidence,
                    success_rate=confidence,
                    metadata={"include": [item]},
                )
                patterns.append(pattern)

        return patterns

    def _extract_recovery_patterns(self, episodes: list[Episode]) -> list[Pattern]:
        """Extract recovery strategy patterns from episodes.

        Args:
            episodes: Episodes to analyze.

        Returns:
            List of recovery patterns.
        """
        patterns: list[Pattern] = []

        # Find episodes that succeeded after retries
        recovered = [
            ep for ep in episodes
            if ep.success and ep.retry_count > 0
        ]
        if len(recovered) < 3:
            return patterns

        # Analyze recovery actions
        action_counts: Counter[str] = Counter()
        for ep in recovered:
            for action in ep.recovery_actions:
                action_counts[action] += 1

        # Create recovery patterns
        for action, count in action_counts.most_common(3):
            if count >= 2:
                confidence = count / len(recovered)

                pattern = Pattern(
                    pattern_id=f"rec-{uuid.uuid4().hex[:8]}",
                    pattern_type="recovery",
                    description=f"Recovery action: {action}",
                    confidence=confidence,
                    success_rate=confidence,
                    metadata={"action": action},
                )
                patterns.append(pattern)

        return patterns


# =============================================================================
# Coder Integration
# =============================================================================


class CoderIntegration:
    """Main integration class wiring learning components to CoderAgent.

    This class provides:
    - Episode logging for coder executions
    - Pattern extraction from historical data
    - Strategy optimization for new tasks
    - Context enhancement with learned patterns
    - Pre/post execution hooks

    Attributes:
        config: SwarmConfig for project settings.
        episode_logger: Logger for execution episodes.
        pattern_extractor: Extractor for learning patterns.
        strategy_optimizer: Optimizer for execution strategies.
    """

    def __init__(
        self,
        config: Optional[SwarmConfig] = None,
        base_path: Optional[Path] = None,
        min_confidence: float = 0.7,
    ) -> None:
        """Initialize CoderIntegration.

        Args:
            config: SwarmConfig for project settings.
            base_path: Base path for episode storage.
            min_confidence: Minimum confidence for patterns.
        """
        self.config = config
        self._base_path = base_path or Path.cwd() / ".swarm" / "learning"

        # Initialize components
        self.episode_logger = EpisodeLogger(
            base_path=self._base_path / "episodes"
        )
        self.pattern_extractor = PatternExtractor(
            min_episodes=5,
            min_confidence=min_confidence,
        )
        self.strategy_optimizer = StrategyOptimizer(
            config=config,
            min_confidence=min_confidence,
        )

        # Hooks
        self._pre_hooks: list[Callable[[dict, Optional[OptimizedStrategy]], None]] = []
        self._post_hooks: list[Callable[[dict, Any, Episode], None]] = []

    def register_pre_execution_hook(
        self,
        hook: Callable[[dict, Optional[OptimizedStrategy]], None],
    ) -> None:
        """Register a pre-execution hook.

        Args:
            hook: Callable that receives (context, strategy).
        """
        self._pre_hooks.append(hook)

    def register_post_execution_hook(
        self,
        hook: Callable[[dict, Any, Episode], None],
    ) -> None:
        """Register a post-execution hook.

        Args:
            hook: Callable that receives (context, result, episode).
        """
        self._post_hooks.append(hook)

    def wrap_coder_run(
        self,
        coder_fn: Callable[[dict], Any],
        context: dict[str, Any],
    ) -> Any:
        """Wrap a coder run with learning layer integration.

        This method:
        1. Starts an episode
        2. Gets optimized strategy
        3. Calls pre-execution hooks
        4. Executes the coder function
        5. Calls post-execution hooks
        6. Completes the episode

        Args:
            coder_fn: The coder function to wrap.
            context: Context dictionary for the coder.

        Returns:
            The result from the coder function.
        """
        feature_id = context.get("feature_id", "unknown")
        issue_number = context.get("issue_number", 0)
        retry_number = context.get("retry_number", 0)

        # Start episode
        episode = self.episode_logger.start_episode(
            feature_id=feature_id,
            issue_number=issue_number,
            task_type=context.get("task_type", "implementation"),
        )

        # Record retry if this is a retry
        if retry_number > 0:
            episode.retry_count = retry_number

        # Get optimized strategy
        strategy = None
        try:
            strategy = self.get_optimized_strategy(
                feature_id=feature_id,
                issue_number=issue_number,
                task_description=context.get("task_description", ""),
            )
        except Exception:
            # Don't fail if strategy optimization fails
            pass

        # Call pre-execution hooks
        for pre_hook in self._pre_hooks:
            try:
                pre_hook(context, strategy)
            except Exception:
                pass

        # Execute the coder
        result = coder_fn(context)

        # Call post-execution hooks
        for post_hook in self._post_hooks:
            try:
                post_hook(context, result, episode)
            except Exception:
                pass

        # Complete the episode - safely extract values handling mock objects
        success = self._safe_bool(getattr(result, "success", False))
        cost = self._safe_float(getattr(result, "cost_usd", 0.0))
        output = self._safe_dict(getattr(result, "output", {}))
        errors = self._safe_list(getattr(result, "errors", []))

        error_msg = None
        if errors:
            first_error = errors[0] if isinstance(errors[0], str) else str(errors[0])
            error_msg = first_error

        self.episode_logger.complete_episode(
            episode=episode,
            success=success,
            cost_usd=cost,
            error=error_msg,
            files_created=output.get("files_created", []),
            files_modified=output.get("files_modified", []),
        )

        return result

    def get_optimized_strategy(
        self,
        feature_id: str,
        issue_number: int,
        task_description: str = "",
    ) -> OptimizedStrategy:
        """Get an optimized strategy for a task.

        Args:
            feature_id: Feature being implemented.
            issue_number: Issue number.
            task_description: Description of the task.

        Returns:
            OptimizedStrategy with optimization suggestions.
        """
        # Load historical episodes
        episodes = self.episode_logger.load_all()

        # Extract patterns
        patterns = self.pattern_extractor.extract_patterns(episodes)

        # Create task
        task = Task(
            task_id=f"{feature_id}-{issue_number}",
            description=task_description or f"Implement issue {issue_number}",
            task_type="implementation",
        )

        # Optimize
        return self.strategy_optimizer.optimize(task, patterns)

    def enhance_context(self, context: dict[str, Any]) -> dict[str, Any]:
        """Enhance coder context with learned insights.

        Args:
            context: Original context dictionary.

        Returns:
            Enhanced context with learning insights.
        """
        enhanced = context.copy()

        try:
            # Load recent successful episodes for similar tasks
            episodes = self.episode_logger.load_recent(limit=20)
            successful = [ep for ep in episodes if ep.success]

            if successful:
                # Add learning insights
                insights = {
                    "recent_success_count": len(successful),
                    "common_tools": self._get_common_tools(successful),
                    "avg_cost": sum(ep.cost_usd for ep in successful) / len(successful),
                }
                enhanced["learning_insights"] = insights

        except Exception:
            # Don't fail context enhancement
            pass

        return enhanced

    def _get_common_tools(self, episodes: list[Episode]) -> list[str]:
        """Get commonly used tools from episodes.

        Args:
            episodes: List of episodes.

        Returns:
            List of common tool names.
        """
        tool_counts: Counter[str] = Counter()
        for ep in episodes:
            for tool in ep.tool_sequence:
                tool_counts[tool] += 1

        return [tool for tool, _ in tool_counts.most_common(5)]

    def _safe_bool(self, value: Any) -> bool:
        """Safely convert value to bool.

        Args:
            value: Value to convert.

        Returns:
            Boolean value.
        """
        if isinstance(value, bool):
            return value
        if hasattr(value, "__bool__"):
            try:
                return bool(value)
            except Exception:
                return False
        return False

    def _safe_float(self, value: Any) -> float:
        """Safely convert value to float.

        Args:
            value: Value to convert.

        Returns:
            Float value.
        """
        if isinstance(value, (int, float)):
            return float(value)
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    def _safe_dict(self, value: Any) -> dict[str, Any]:
        """Safely convert value to dict.

        Args:
            value: Value to convert.

        Returns:
            Dictionary value.
        """
        if isinstance(value, dict):
            return value
        return {}

    def _safe_list(self, value: Any) -> list[Any]:
        """Safely convert value to list.

        Args:
            value: Value to convert.

        Returns:
            List value.
        """
        if isinstance(value, list):
            return value
        return []
