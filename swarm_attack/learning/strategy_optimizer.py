"""Strategy Optimizer for applying learned patterns to improve execution.

This module provides components for optimizing execution strategies based on
learned patterns from previous runs. It applies:
- Prompt engineering suggestions
- Tool ordering recommendations
- Context construction improvements
- Recovery strategy tuning

Key Classes:
- StrategyOptimizer: Main optimizer that applies patterns to tasks
- Task: Represents a task to be optimized
- PatternSet: Collection of learned patterns
- Pattern: Individual learned pattern
- OptimizedStrategy: Result of optimization
- PromptSuggestion: Suggestion for prompt improvement
- RecoveryStrategy: Configuration for error recovery
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field, asdict
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from swarm_attack.config import SwarmConfig


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class Task:
    """Represents a task to be optimized.

    Attributes:
        task_id: Unique identifier for the task.
        description: Human-readable description of the task.
        task_type: Type of task (e.g., "implementation", "bug_fix", "refactor").
        complexity: Complexity level ("low", "medium", "high").
        context: Additional context information for the task.
    """
    task_id: str
    description: str
    task_type: str = "implementation"
    complexity: str = "medium"
    context: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Task:
        """Create from dictionary."""
        return cls(**data)


@dataclass
class Pattern:
    """Represents a learned pattern from historical executions.

    Attributes:
        pattern_id: Unique identifier for the pattern.
        pattern_type: Type of pattern ("prompt", "tool_order", "context", "recovery").
        description: Human-readable description of the pattern.
        confidence: Confidence score (0.0 to 1.0) in the pattern's effectiveness.
        success_rate: Historical success rate (0.0 to 1.0) when applying this pattern.
        metadata: Additional pattern-specific metadata.
    """
    pattern_id: str
    pattern_type: str  # "prompt", "tool_order", "context", "recovery"
    description: str
    confidence: float  # 0.0 to 1.0
    success_rate: float  # 0.0 to 1.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Pattern:
        """Create from dictionary."""
        return cls(**data)


@dataclass
class PatternSet:
    """Collection of learned patterns.

    Attributes:
        patterns: List of Pattern objects.
    """
    patterns: list[Pattern] = field(default_factory=list)

    def get_patterns_by_type(self, pattern_type: str) -> list[Pattern]:
        """Get patterns filtered by type.

        Args:
            pattern_type: Type of patterns to filter for.

        Returns:
            List of patterns matching the specified type.
        """
        return [p for p in self.patterns if p.pattern_type == pattern_type]

    def get_high_confidence_patterns(self, min_confidence: float = 0.7) -> list[Pattern]:
        """Get patterns above a confidence threshold.

        Args:
            min_confidence: Minimum confidence score (default 0.7).

        Returns:
            List of patterns meeting the confidence threshold.
        """
        return [p for p in self.patterns if p.confidence >= min_confidence]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {"patterns": [p.to_dict() for p in self.patterns]}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PatternSet:
        """Create from dictionary."""
        patterns = [Pattern.from_dict(p) for p in data.get("patterns", [])]
        return cls(patterns=patterns)


@dataclass
class PromptSuggestion:
    """Suggestion for improving a prompt.

    Attributes:
        suggestion_id: Unique identifier for this suggestion.
        original_text: The original text being improved.
        suggested_text: The suggested improved text.
        reason: Explanation for why this change is suggested.
        confidence: Confidence score (0.0 to 1.0) in this suggestion.
    """
    suggestion_id: str
    original_text: str
    suggested_text: str
    reason: str
    confidence: float

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PromptSuggestion:
        """Create from dictionary."""
        return cls(**data)


@dataclass
class RecoveryStrategy:
    """Configuration for error recovery behavior.

    Attributes:
        strategy_id: Unique identifier for this strategy.
        max_retries: Maximum number of retry attempts.
        backoff_multiplier: Multiplier for exponential backoff.
        timeout_seconds: Timeout in seconds for operations.
        fallback_actions: List of fallback actions in order of preference.
    """
    strategy_id: str
    max_retries: int = 3
    backoff_multiplier: float = 2.0
    timeout_seconds: int = 300
    fallback_actions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RecoveryStrategy:
        """Create from dictionary."""
        return cls(**data)


@dataclass
class OptimizedStrategy:
    """Result of optimizing a task based on patterns.

    Attributes:
        strategy_id: Unique identifier for this optimized strategy.
        task_id: ID of the task this strategy is for.
        prompt_suggestions: List of prompt improvement suggestions.
        tool_order: Suggested order for tool usage.
        context_improvements: List of context construction improvements.
        recovery_strategy: Tuned recovery strategy.
        confidence_score: Overall confidence score (0.0 to 1.0) in this strategy.
    """
    strategy_id: str
    task_id: str
    prompt_suggestions: list[PromptSuggestion] = field(default_factory=list)
    tool_order: list[str] = field(default_factory=list)
    context_improvements: list[str] = field(default_factory=list)
    recovery_strategy: Optional[RecoveryStrategy] = None
    confidence_score: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        data = asdict(self)
        data["prompt_suggestions"] = [s.to_dict() if hasattr(s, 'to_dict') else s
                                       for s in self.prompt_suggestions]
        if self.recovery_strategy:
            data["recovery_strategy"] = self.recovery_strategy.to_dict()
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> OptimizedStrategy:
        """Create from dictionary."""
        data = data.copy()
        if data.get("prompt_suggestions"):
            data["prompt_suggestions"] = [
                PromptSuggestion.from_dict(s) if isinstance(s, dict) else s
                for s in data["prompt_suggestions"]
            ]
        if data.get("recovery_strategy"):
            data["recovery_strategy"] = RecoveryStrategy.from_dict(data["recovery_strategy"])
        return cls(**data)


# =============================================================================
# Strategy Optimizer
# =============================================================================


class StrategyOptimizer:
    """Applies learned patterns to optimize execution strategies.

    This optimizer analyzes tasks and applies relevant patterns to generate
    optimized strategies for:
    - Prompt engineering (improving prompts based on success patterns)
    - Tool ordering (suggesting optimal tool usage sequences)
    - Context construction (improving what context to include)
    - Recovery tuning (adjusting retry/timeout/fallback settings)

    Attributes:
        config: SwarmConfig for accessing project settings.
        min_confidence: Minimum confidence threshold for applying patterns.

    Example:
        >>> optimizer = StrategyOptimizer(config, min_confidence=0.7)
        >>> task = Task(task_id="t1", description="Implement auth")
        >>> patterns = PatternSet(patterns=[...])
        >>> strategy = optimizer.optimize(task, patterns)
    """

    def __init__(
        self,
        config: Optional[SwarmConfig] = None,
        min_confidence: float = 0.7,
    ) -> None:
        """Initialize the StrategyOptimizer.

        Args:
            config: SwarmConfig for project settings (optional).
            min_confidence: Minimum confidence threshold for applying patterns.
                           Must be between 0.0 and 1.0.

        Raises:
            ValueError: If min_confidence is not between 0.0 and 1.0.
        """
        if min_confidence < 0.0 or min_confidence > 1.0:
            raise ValueError(
                f"min_confidence must be between 0.0 and 1.0, got {min_confidence}"
            )

        self.config = config
        self.min_confidence = min_confidence

    def optimize(self, task: Task, patterns: PatternSet) -> OptimizedStrategy:
        """Generate an optimized strategy for a task based on patterns.

        This method analyzes the task and applies relevant patterns from
        the pattern set to generate an optimized execution strategy.

        Args:
            task: The task to optimize.
            patterns: Collection of learned patterns to apply.

        Returns:
            OptimizedStrategy with suggestions for improving execution.

        Raises:
            ValueError: If task or patterns is None.
            TypeError: If task is not a Task or patterns is not a PatternSet.
        """
        if task is None:
            raise ValueError("task cannot be None")
        if patterns is None:
            raise ValueError("patterns cannot be None")
        if not isinstance(task, Task):
            raise TypeError(f"task must be a Task, got {type(task)}")
        if not isinstance(patterns, PatternSet):
            raise TypeError(f"patterns must be a PatternSet, got {type(patterns)}")

        # Generate unique strategy ID
        strategy_id = f"opt-{uuid.uuid4().hex[:8]}"

        # Get high confidence patterns
        high_conf_patterns = patterns.get_high_confidence_patterns(self.min_confidence)

        # Generate prompt suggestions
        prompt_suggestions = self._generate_prompt_suggestions(
            task.description, high_conf_patterns
        )

        # Generate tool order
        tool_order = self._generate_tool_order(high_conf_patterns)

        # Generate context improvements
        context_improvements = self._generate_context_improvements(high_conf_patterns)

        # Calculate confidence score
        confidence_score = self._calculate_confidence_score(high_conf_patterns)

        return OptimizedStrategy(
            strategy_id=strategy_id,
            task_id=task.task_id,
            prompt_suggestions=prompt_suggestions,
            tool_order=tool_order,
            context_improvements=context_improvements,
            confidence_score=confidence_score,
        )

    def suggest_prompt_improvements(
        self, prompt: str, patterns: PatternSet
    ) -> list[PromptSuggestion]:
        """Suggest improvements for a prompt based on success patterns.

        Analyzes the prompt and suggests improvements based on patterns
        that have historically led to better outcomes.

        Args:
            prompt: The prompt to improve.
            patterns: Collection of learned patterns.

        Returns:
            List of PromptSuggestion objects with improvement suggestions.

        Raises:
            ValueError: If prompt is None.
            TypeError: If patterns is not a PatternSet.
        """
        if prompt is None:
            raise ValueError("prompt cannot be None")
        if patterns is None:
            raise ValueError("patterns cannot be None")
        if not isinstance(patterns, PatternSet):
            raise TypeError(f"patterns must be a PatternSet, got {type(patterns)}")

        # Empty prompt returns empty suggestions
        if not prompt:
            return []

        # Get high confidence prompt patterns
        prompt_patterns = [
            p for p in patterns.get_patterns_by_type("prompt")
            if p.confidence >= self.min_confidence
        ]

        suggestions: list[PromptSuggestion] = []
        for pattern in prompt_patterns:
            suggestion = PromptSuggestion(
                suggestion_id=f"sug-{uuid.uuid4().hex[:8]}",
                original_text=prompt[:100],  # First 100 chars
                suggested_text=f"{prompt}\n\n[Apply: {pattern.description}]",
                reason=pattern.description,
                confidence=pattern.confidence,
            )
            suggestions.append(suggestion)

        return suggestions

    def suggest_tool_order(
        self, tools: list[str], patterns: PatternSet
    ) -> list[str]:
        """Suggest optimal ordering for a list of tools.

        Analyzes tool order patterns and suggests the best sequence
        for using the provided tools.

        Args:
            tools: List of tool names to order.
            patterns: Collection of learned patterns.

        Returns:
            Reordered list of tool names based on patterns.

        Raises:
            ValueError: If tools is None.
            TypeError: If patterns is not a PatternSet.
        """
        if tools is None:
            raise ValueError("tools cannot be None")
        if patterns is None:
            raise ValueError("patterns cannot be None")
        if not isinstance(patterns, PatternSet):
            raise TypeError(f"patterns must be a PatternSet, got {type(patterns)}")

        # Empty tools returns empty list
        if not tools:
            return []

        # Get high confidence tool order patterns
        tool_patterns = [
            p for p in patterns.get_patterns_by_type("tool_order")
            if p.confidence >= self.min_confidence
        ]

        # If no patterns, return original order
        if not tool_patterns:
            return tools.copy()

        # Apply ordering based on patterns
        result = tools.copy()

        for pattern in sorted(tool_patterns, key=lambda p: -p.confidence):
            order = pattern.metadata.get("order", [])
            if len(order) >= 2:
                # Apply the ordering constraint
                result = self._apply_ordering_constraint(result, order)

        return result

    def tune_recovery(
        self, current_strategy: RecoveryStrategy, patterns: PatternSet
    ) -> RecoveryStrategy:
        """Tune recovery strategy based on historical patterns.

        Adjusts recovery parameters (retries, timeouts, fallbacks) based
        on patterns that have historically improved recovery success.

        Args:
            current_strategy: The current recovery strategy to tune.
            patterns: Collection of learned patterns.

        Returns:
            New RecoveryStrategy with tuned parameters.

        Raises:
            ValueError: If current_strategy is None.
            TypeError: If patterns is not a PatternSet.
        """
        if current_strategy is None:
            raise ValueError("current_strategy cannot be None")
        if patterns is None:
            raise ValueError("patterns cannot be None")
        if not isinstance(patterns, PatternSet):
            raise TypeError(f"patterns must be a PatternSet, got {type(patterns)}")

        # Get high confidence recovery patterns
        recovery_patterns = [
            p for p in patterns.get_patterns_by_type("recovery")
            if p.confidence >= self.min_confidence
        ]

        # Start with current values
        new_max_retries = current_strategy.max_retries
        new_backoff = current_strategy.backoff_multiplier
        new_timeout = current_strategy.timeout_seconds
        new_fallbacks = current_strategy.fallback_actions.copy()

        # Apply patterns
        for pattern in recovery_patterns:
            metadata = pattern.metadata

            # Apply timeout multiplier
            if "timeout_multiplier" in metadata:
                new_timeout = int(new_timeout * metadata["timeout_multiplier"])

            # Apply retry delta
            if "max_retries_delta" in metadata:
                new_max_retries += metadata["max_retries_delta"]

            # Add fallback actions
            if "add_fallback" in metadata:
                fallback = metadata["add_fallback"]
                if fallback not in new_fallbacks:
                    new_fallbacks.append(fallback)

            # Apply backoff multiplier
            if "backoff_multiplier" in metadata:
                new_backoff = metadata["backoff_multiplier"]

        # Generate new strategy ID
        new_strategy_id = f"rec-{uuid.uuid4().hex[:8]}"

        return RecoveryStrategy(
            strategy_id=new_strategy_id,
            max_retries=new_max_retries,
            backoff_multiplier=new_backoff,
            timeout_seconds=new_timeout,
            fallback_actions=new_fallbacks,
        )

    # =========================================================================
    # Private Helper Methods
    # =========================================================================

    def _generate_prompt_suggestions(
        self, description: str, patterns: list[Pattern]
    ) -> list[PromptSuggestion]:
        """Generate prompt suggestions from patterns.

        Args:
            description: Task description to base suggestions on.
            patterns: High confidence patterns to apply.

        Returns:
            List of PromptSuggestion objects.
        """
        prompt_patterns = [p for p in patterns if p.pattern_type == "prompt"]
        suggestions: list[PromptSuggestion] = []

        for pattern in prompt_patterns:
            suggestion = PromptSuggestion(
                suggestion_id=f"sug-{uuid.uuid4().hex[:8]}",
                original_text=description[:100] if description else "",
                suggested_text=f"[Apply: {pattern.description}]",
                reason=pattern.description,
                confidence=pattern.confidence,
            )
            suggestions.append(suggestion)

        return suggestions

    def _generate_tool_order(self, patterns: list[Pattern]) -> list[str]:
        """Generate suggested tool order from patterns.

        Args:
            patterns: High confidence patterns to analyze.

        Returns:
            List of tool names in suggested order.
        """
        tool_patterns = [p for p in patterns if p.pattern_type == "tool_order"]

        # Collect all tools mentioned in patterns
        tools: list[str] = []
        for pattern in sorted(tool_patterns, key=lambda p: -p.confidence):
            order = pattern.metadata.get("order", [])
            for tool in order:
                if tool not in tools:
                    tools.append(tool)

        return tools

    def _generate_context_improvements(self, patterns: list[Pattern]) -> list[str]:
        """Generate context improvement suggestions from patterns.

        Args:
            patterns: High confidence patterns to analyze.

        Returns:
            List of context improvement suggestions.
        """
        context_patterns = [p for p in patterns if p.pattern_type == "context"]
        improvements: list[str] = []

        for pattern in context_patterns:
            include_items = pattern.metadata.get("include", [])
            for item in include_items:
                improvement = f"Include {item}"
                if improvement not in improvements:
                    improvements.append(improvement)

        return improvements

    def _calculate_confidence_score(self, patterns: list[Pattern]) -> float:
        """Calculate overall confidence score from patterns.

        Args:
            patterns: Patterns used in the optimization.

        Returns:
            Weighted average confidence score (0.0 to 1.0).
        """
        if not patterns:
            return 0.0

        total_confidence = sum(p.confidence * p.success_rate for p in patterns)
        total_weight = sum(p.success_rate for p in patterns)

        if total_weight == 0:
            return 0.0

        return min(1.0, total_confidence / total_weight)

    def _apply_ordering_constraint(
        self, tools: list[str], order: list[str]
    ) -> list[str]:
        """Apply an ordering constraint to a list of tools.

        Ensures that tools appear in the specified relative order.

        Args:
            tools: Current list of tools.
            order: Desired relative ordering (e.g., ["Read", "Edit"]).

        Returns:
            Reordered list of tools.
        """
        result = tools.copy()

        # Find positions of tools in the order constraint
        for i in range(len(order) - 1):
            first_tool = order[i]
            second_tool = order[i + 1]

            if first_tool in result and second_tool in result:
                first_idx = result.index(first_tool)
                second_idx = result.index(second_tool)

                # If second comes before first, swap them
                if second_idx < first_idx:
                    result[first_idx], result[second_idx] = (
                        result[second_idx], result[first_idx]
                    )

        return result
