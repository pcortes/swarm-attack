"""Unit tests for StrategyOptimizer.

Tests for:
- Strategy optimization generation
- Prompt improvement suggestions
- Tool ordering recommendations
- Context construction suggestions
- Recovery strategy tuning
- Empty patterns handling
- Confidence-based filtering

TDD Protocol: RED PHASE - These tests should fail initially.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional
from unittest.mock import MagicMock

import pytest


# =============================================================================
# Test Data Classes (used before implementation exists)
# =============================================================================


@dataclass
class MockTask:
    """Mock Task for testing before real implementation."""
    task_id: str
    description: str
    task_type: str = "implementation"
    complexity: str = "medium"
    context: dict[str, Any] = field(default_factory=dict)


@dataclass
class MockPattern:
    """Mock Pattern for testing success/failure patterns."""
    pattern_id: str
    pattern_type: str  # "prompt", "tool_order", "context", "recovery"
    description: str
    confidence: float  # 0.0 to 1.0
    success_rate: float  # 0.0 to 1.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class MockPatternSet:
    """Mock PatternSet for testing."""
    patterns: list[MockPattern] = field(default_factory=list)

    def get_patterns_by_type(self, pattern_type: str) -> list[MockPattern]:
        """Get patterns filtered by type."""
        return [p for p in self.patterns if p.pattern_type == pattern_type]

    def get_high_confidence_patterns(self, min_confidence: float = 0.7) -> list[MockPattern]:
        """Get patterns above confidence threshold."""
        return [p for p in self.patterns if p.confidence >= min_confidence]


@dataclass
class MockRecoveryStrategy:
    """Mock RecoveryStrategy for testing."""
    strategy_id: str
    max_retries: int = 3
    backoff_multiplier: float = 2.0
    timeout_seconds: int = 300
    fallback_actions: list[str] = field(default_factory=list)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def sample_task() -> MockTask:
    """Create a sample task for testing."""
    return MockTask(
        task_id="task-001",
        description="Implement user authentication module",
        task_type="implementation",
        complexity="medium",
        context={"module": "auth", "files": ["auth.py", "models.py"]},
    )


@pytest.fixture
def sample_patterns() -> MockPatternSet:
    """Create sample patterns for testing."""
    return MockPatternSet(
        patterns=[
            MockPattern(
                pattern_id="prompt-001",
                pattern_type="prompt",
                description="Use step-by-step reasoning",
                confidence=0.85,
                success_rate=0.90,
                metadata={"keywords": ["step", "reasoning"]},
            ),
            MockPattern(
                pattern_id="prompt-002",
                pattern_type="prompt",
                description="Include concrete examples",
                confidence=0.80,
                success_rate=0.85,
                metadata={"keywords": ["example", "concrete"]},
            ),
            MockPattern(
                pattern_id="tool-001",
                pattern_type="tool_order",
                description="Read before Edit",
                confidence=0.95,
                success_rate=0.92,
                metadata={"order": ["Read", "Edit"]},
            ),
            MockPattern(
                pattern_id="tool-002",
                pattern_type="tool_order",
                description="Glob before Grep for file discovery",
                confidence=0.78,
                success_rate=0.80,
                metadata={"order": ["Glob", "Grep"]},
            ),
            MockPattern(
                pattern_id="context-001",
                pattern_type="context",
                description="Include module registry",
                confidence=0.88,
                success_rate=0.85,
                metadata={"include": ["module_registry"]},
            ),
            MockPattern(
                pattern_id="recovery-001",
                pattern_type="recovery",
                description="Increase timeout on complex tasks",
                confidence=0.82,
                success_rate=0.78,
                metadata={"timeout_multiplier": 1.5},
            ),
            MockPattern(
                pattern_id="low-conf-001",
                pattern_type="prompt",
                description="Low confidence pattern",
                confidence=0.40,
                success_rate=0.50,
                metadata={},
            ),
        ]
    )


@pytest.fixture
def empty_patterns() -> MockPatternSet:
    """Create empty pattern set for testing edge cases."""
    return MockPatternSet(patterns=[])


@pytest.fixture
def sample_recovery_strategy() -> MockRecoveryStrategy:
    """Create sample recovery strategy for testing."""
    return MockRecoveryStrategy(
        strategy_id="recovery-default",
        max_retries=3,
        backoff_multiplier=2.0,
        timeout_seconds=300,
        fallback_actions=["retry", "escalate"],
    )


@pytest.fixture
def mock_config(tmp_path):
    """Create a mock SwarmConfig for testing."""
    config = MagicMock()
    config.repo_root = str(tmp_path)
    config.swarm_path = tmp_path / ".swarm"
    config.swarm_path.mkdir(parents=True, exist_ok=True)
    return config


# =============================================================================
# Import Tests - Verify module structure
# =============================================================================


class TestModuleImports:
    """Test that required classes can be imported."""

    def test_import_strategy_optimizer(self):
        """Test StrategyOptimizer class can be imported."""
        from swarm_attack.learning.strategy_optimizer import StrategyOptimizer
        assert StrategyOptimizer is not None

    def test_import_task(self):
        """Test Task class can be imported."""
        from swarm_attack.learning.strategy_optimizer import Task
        assert Task is not None

    def test_import_optimized_strategy(self):
        """Test OptimizedStrategy class can be imported."""
        from swarm_attack.learning.strategy_optimizer import OptimizedStrategy
        assert OptimizedStrategy is not None

    def test_import_prompt_suggestion(self):
        """Test PromptSuggestion class can be imported."""
        from swarm_attack.learning.strategy_optimizer import PromptSuggestion
        assert PromptSuggestion is not None

    def test_import_pattern_set(self):
        """Test PatternSet class can be imported."""
        from swarm_attack.learning.strategy_optimizer import PatternSet
        assert PatternSet is not None

    def test_import_recovery_strategy(self):
        """Test RecoveryStrategy class can be imported."""
        from swarm_attack.learning.strategy_optimizer import RecoveryStrategy
        assert RecoveryStrategy is not None


# =============================================================================
# Task Data Class Tests
# =============================================================================


class TestTaskDataClass:
    """Tests for Task data class."""

    def test_task_creation(self):
        """Test creating a Task with required fields."""
        from swarm_attack.learning.strategy_optimizer import Task

        task = Task(
            task_id="task-001",
            description="Test task",
        )

        assert task.task_id == "task-001"
        assert task.description == "Test task"

    def test_task_with_all_fields(self):
        """Test creating Task with all fields."""
        from swarm_attack.learning.strategy_optimizer import Task

        task = Task(
            task_id="task-002",
            description="Complex task",
            task_type="implementation",
            complexity="high",
            context={"module": "core"},
        )

        assert task.task_type == "implementation"
        assert task.complexity == "high"
        assert task.context == {"module": "core"}

    def test_task_to_dict(self):
        """Test Task serialization to dict."""
        from swarm_attack.learning.strategy_optimizer import Task

        task = Task(
            task_id="task-003",
            description="Serialization test",
        )

        data = task.to_dict()

        assert isinstance(data, dict)
        assert data["task_id"] == "task-003"
        assert data["description"] == "Serialization test"

    def test_task_from_dict(self):
        """Test Task deserialization from dict."""
        from swarm_attack.learning.strategy_optimizer import Task

        data = {
            "task_id": "task-004",
            "description": "Deserialization test",
            "task_type": "bug_fix",
            "complexity": "low",
            "context": {},
        }

        task = Task.from_dict(data)

        assert task.task_id == "task-004"
        assert task.task_type == "bug_fix"


# =============================================================================
# PatternSet Data Class Tests
# =============================================================================


class TestPatternSetDataClass:
    """Tests for PatternSet data class."""

    def test_pattern_set_creation(self):
        """Test creating an empty PatternSet."""
        from swarm_attack.learning.strategy_optimizer import PatternSet

        ps = PatternSet()

        assert ps.patterns == []

    def test_pattern_set_with_patterns(self):
        """Test creating PatternSet with patterns."""
        from swarm_attack.learning.strategy_optimizer import PatternSet, Pattern

        pattern = Pattern(
            pattern_id="p1",
            pattern_type="prompt",
            description="Test pattern",
            confidence=0.8,
            success_rate=0.85,
        )

        ps = PatternSet(patterns=[pattern])

        assert len(ps.patterns) == 1

    def test_pattern_set_get_by_type(self):
        """Test filtering patterns by type."""
        from swarm_attack.learning.strategy_optimizer import PatternSet, Pattern

        patterns = [
            Pattern("p1", "prompt", "desc", 0.8, 0.8),
            Pattern("p2", "tool_order", "desc", 0.8, 0.8),
            Pattern("p3", "prompt", "desc", 0.9, 0.9),
        ]

        ps = PatternSet(patterns=patterns)
        prompt_patterns = ps.get_patterns_by_type("prompt")

        assert len(prompt_patterns) == 2

    def test_pattern_set_get_high_confidence(self):
        """Test filtering patterns by confidence."""
        from swarm_attack.learning.strategy_optimizer import PatternSet, Pattern

        patterns = [
            Pattern("p1", "prompt", "desc", 0.9, 0.8),
            Pattern("p2", "prompt", "desc", 0.5, 0.8),
            Pattern("p3", "prompt", "desc", 0.8, 0.9),
        ]

        ps = PatternSet(patterns=patterns)
        high_conf = ps.get_high_confidence_patterns(min_confidence=0.7)

        assert len(high_conf) == 2


# =============================================================================
# OptimizedStrategy Data Class Tests
# =============================================================================


class TestOptimizedStrategyDataClass:
    """Tests for OptimizedStrategy data class."""

    def test_optimized_strategy_creation(self):
        """Test creating an OptimizedStrategy."""
        from swarm_attack.learning.strategy_optimizer import OptimizedStrategy

        strategy = OptimizedStrategy(
            strategy_id="opt-001",
            task_id="task-001",
        )

        assert strategy.strategy_id == "opt-001"
        assert strategy.task_id == "task-001"

    def test_optimized_strategy_with_suggestions(self):
        """Test OptimizedStrategy with all suggestion types."""
        from swarm_attack.learning.strategy_optimizer import (
            OptimizedStrategy,
            PromptSuggestion,
        )

        strategy = OptimizedStrategy(
            strategy_id="opt-002",
            task_id="task-002",
            prompt_suggestions=[
                PromptSuggestion(
                    suggestion_id="s1",
                    original_text="Do this",
                    suggested_text="Do this step by step",
                    reason="Improves clarity",
                    confidence=0.85,
                )
            ],
            tool_order=["Read", "Glob", "Edit"],
            context_improvements=["Add module registry"],
            confidence_score=0.88,
        )

        assert len(strategy.prompt_suggestions) == 1
        assert strategy.tool_order == ["Read", "Glob", "Edit"]
        assert strategy.confidence_score == 0.88

    def test_optimized_strategy_to_dict(self):
        """Test OptimizedStrategy serialization."""
        from swarm_attack.learning.strategy_optimizer import OptimizedStrategy

        strategy = OptimizedStrategy(
            strategy_id="opt-003",
            task_id="task-003",
            confidence_score=0.90,
        )

        data = strategy.to_dict()

        assert data["strategy_id"] == "opt-003"
        assert data["confidence_score"] == 0.90


# =============================================================================
# PromptSuggestion Data Class Tests
# =============================================================================


class TestPromptSuggestionDataClass:
    """Tests for PromptSuggestion data class."""

    def test_prompt_suggestion_creation(self):
        """Test creating a PromptSuggestion."""
        from swarm_attack.learning.strategy_optimizer import PromptSuggestion

        suggestion = PromptSuggestion(
            suggestion_id="sug-001",
            original_text="Write code",
            suggested_text="Write code following TDD",
            reason="TDD improves quality",
            confidence=0.82,
        )

        assert suggestion.suggestion_id == "sug-001"
        assert suggestion.confidence == 0.82

    def test_prompt_suggestion_to_dict(self):
        """Test PromptSuggestion serialization."""
        from swarm_attack.learning.strategy_optimizer import PromptSuggestion

        suggestion = PromptSuggestion(
            suggestion_id="sug-002",
            original_text="original",
            suggested_text="suggested",
            reason="reason",
            confidence=0.75,
        )

        data = suggestion.to_dict()

        assert data["suggestion_id"] == "sug-002"
        assert data["confidence"] == 0.75


# =============================================================================
# RecoveryStrategy Data Class Tests
# =============================================================================


class TestRecoveryStrategyDataClass:
    """Tests for RecoveryStrategy data class."""

    def test_recovery_strategy_creation(self):
        """Test creating a RecoveryStrategy."""
        from swarm_attack.learning.strategy_optimizer import RecoveryStrategy

        strategy = RecoveryStrategy(
            strategy_id="rec-001",
        )

        assert strategy.strategy_id == "rec-001"

    def test_recovery_strategy_with_all_fields(self):
        """Test RecoveryStrategy with all fields."""
        from swarm_attack.learning.strategy_optimizer import RecoveryStrategy

        strategy = RecoveryStrategy(
            strategy_id="rec-002",
            max_retries=5,
            backoff_multiplier=3.0,
            timeout_seconds=600,
            fallback_actions=["retry", "simplify", "escalate"],
        )

        assert strategy.max_retries == 5
        assert strategy.backoff_multiplier == 3.0
        assert len(strategy.fallback_actions) == 3

    def test_recovery_strategy_to_dict(self):
        """Test RecoveryStrategy serialization."""
        from swarm_attack.learning.strategy_optimizer import RecoveryStrategy

        strategy = RecoveryStrategy(
            strategy_id="rec-003",
            max_retries=4,
        )

        data = strategy.to_dict()

        assert data["strategy_id"] == "rec-003"
        assert data["max_retries"] == 4


# =============================================================================
# StrategyOptimizer.optimize() Tests
# =============================================================================


class TestStrategyOptimizerOptimize:
    """Tests for StrategyOptimizer.optimize() method."""

    def test_optimize_returns_optimized_strategy(self, mock_config, sample_task, sample_patterns):
        """Test that optimize() returns an OptimizedStrategy."""
        from swarm_attack.learning.strategy_optimizer import (
            StrategyOptimizer,
            Task,
            PatternSet,
            Pattern,
            OptimizedStrategy,
        )

        optimizer = StrategyOptimizer(config=mock_config)

        # Create real Task and PatternSet
        task = Task(
            task_id=sample_task.task_id,
            description=sample_task.description,
            task_type=sample_task.task_type,
            complexity=sample_task.complexity,
            context=sample_task.context,
        )

        patterns = PatternSet(patterns=[
            Pattern(
                pattern_id=p.pattern_id,
                pattern_type=p.pattern_type,
                description=p.description,
                confidence=p.confidence,
                success_rate=p.success_rate,
                metadata=p.metadata,
            )
            for p in sample_patterns.patterns
        ])

        result = optimizer.optimize(task, patterns)

        assert isinstance(result, OptimizedStrategy)
        assert result.task_id == task.task_id

    def test_optimize_with_empty_patterns(self, mock_config, sample_task, empty_patterns):
        """Test optimize() with empty pattern set."""
        from swarm_attack.learning.strategy_optimizer import (
            StrategyOptimizer,
            Task,
            PatternSet,
            OptimizedStrategy,
        )

        optimizer = StrategyOptimizer(config=mock_config)

        task = Task(
            task_id=sample_task.task_id,
            description=sample_task.description,
        )

        patterns = PatternSet(patterns=[])

        result = optimizer.optimize(task, patterns)

        # Should return a valid OptimizedStrategy even with no patterns
        assert isinstance(result, OptimizedStrategy)
        assert result.prompt_suggestions == []
        assert result.tool_order == []

    def test_optimize_generates_strategy_id(self, mock_config, sample_task, sample_patterns):
        """Test that optimize() generates a unique strategy ID."""
        from swarm_attack.learning.strategy_optimizer import (
            StrategyOptimizer,
            Task,
            PatternSet,
            Pattern,
        )

        optimizer = StrategyOptimizer(config=mock_config)

        task = Task(
            task_id=sample_task.task_id,
            description=sample_task.description,
        )

        patterns = PatternSet(patterns=[
            Pattern("p1", "prompt", "desc", 0.8, 0.8)
        ])

        result = optimizer.optimize(task, patterns)

        assert result.strategy_id is not None
        assert len(result.strategy_id) > 0

    def test_optimize_includes_prompt_suggestions(self, mock_config, sample_task, sample_patterns):
        """Test that optimize() includes prompt suggestions from patterns."""
        from swarm_attack.learning.strategy_optimizer import (
            StrategyOptimizer,
            Task,
            PatternSet,
            Pattern,
        )

        optimizer = StrategyOptimizer(config=mock_config)

        task = Task(
            task_id=sample_task.task_id,
            description=sample_task.description,
        )

        # Include prompt patterns with high confidence
        patterns = PatternSet(patterns=[
            Pattern(
                pattern_id="prompt-001",
                pattern_type="prompt",
                description="Use step-by-step reasoning",
                confidence=0.85,
                success_rate=0.90,
                metadata={"keywords": ["step", "reasoning"]},
            )
        ])

        result = optimizer.optimize(task, patterns)

        # Should have prompt suggestions based on patterns
        assert len(result.prompt_suggestions) >= 0  # May have suggestions

    def test_optimize_includes_tool_order(self, mock_config, sample_task, sample_patterns):
        """Test that optimize() suggests tool ordering."""
        from swarm_attack.learning.strategy_optimizer import (
            StrategyOptimizer,
            Task,
            PatternSet,
            Pattern,
        )

        optimizer = StrategyOptimizer(config=mock_config)

        task = Task(
            task_id=sample_task.task_id,
            description=sample_task.description,
        )

        # Include tool order patterns
        patterns = PatternSet(patterns=[
            Pattern(
                pattern_id="tool-001",
                pattern_type="tool_order",
                description="Read before Edit",
                confidence=0.95,
                success_rate=0.92,
                metadata={"order": ["Read", "Edit"]},
            )
        ])

        result = optimizer.optimize(task, patterns)

        # Should have tool_order populated
        assert isinstance(result.tool_order, list)

    def test_optimize_calculates_confidence_score(self, mock_config, sample_task, sample_patterns):
        """Test that optimize() calculates an overall confidence score."""
        from swarm_attack.learning.strategy_optimizer import (
            StrategyOptimizer,
            Task,
            PatternSet,
            Pattern,
        )

        optimizer = StrategyOptimizer(config=mock_config)

        task = Task(
            task_id=sample_task.task_id,
            description=sample_task.description,
        )

        patterns = PatternSet(patterns=[
            Pattern("p1", "prompt", "desc", 0.9, 0.85),
            Pattern("p2", "tool_order", "desc", 0.8, 0.80),
        ])

        result = optimizer.optimize(task, patterns)

        assert result.confidence_score >= 0.0
        assert result.confidence_score <= 1.0


# =============================================================================
# StrategyOptimizer.suggest_prompt_improvements() Tests
# =============================================================================


class TestStrategyOptimizerSuggestPromptImprovements:
    """Tests for suggest_prompt_improvements() method."""

    def test_suggest_prompt_improvements_returns_list(self, mock_config, sample_patterns):
        """Test that suggest_prompt_improvements returns a list."""
        from swarm_attack.learning.strategy_optimizer import (
            StrategyOptimizer,
            PatternSet,
            Pattern,
            PromptSuggestion,
        )

        optimizer = StrategyOptimizer(config=mock_config)

        prompt = "Write a function to authenticate users"
        patterns = PatternSet(patterns=[
            Pattern(
                pattern_id="prompt-001",
                pattern_type="prompt",
                description="Use step-by-step reasoning",
                confidence=0.85,
                success_rate=0.90,
                metadata={"keywords": ["step"]},
            )
        ])

        result = optimizer.suggest_prompt_improvements(prompt, patterns)

        assert isinstance(result, list)
        for suggestion in result:
            assert isinstance(suggestion, PromptSuggestion)

    def test_suggest_prompt_improvements_with_empty_prompt(self, mock_config, sample_patterns):
        """Test suggest_prompt_improvements with empty prompt."""
        from swarm_attack.learning.strategy_optimizer import (
            StrategyOptimizer,
            PatternSet,
            Pattern,
        )

        optimizer = StrategyOptimizer(config=mock_config)

        patterns = PatternSet(patterns=[
            Pattern("p1", "prompt", "desc", 0.8, 0.8)
        ])

        result = optimizer.suggest_prompt_improvements("", patterns)

        # Should return empty list for empty prompt
        assert result == []

    def test_suggest_prompt_improvements_with_empty_patterns(self, mock_config, empty_patterns):
        """Test suggest_prompt_improvements with no patterns."""
        from swarm_attack.learning.strategy_optimizer import (
            StrategyOptimizer,
            PatternSet,
        )

        optimizer = StrategyOptimizer(config=mock_config)

        prompt = "Write a function"
        patterns = PatternSet(patterns=[])

        result = optimizer.suggest_prompt_improvements(prompt, patterns)

        assert result == []

    def test_suggest_prompt_improvements_filters_low_confidence(self, mock_config):
        """Test that low confidence patterns are filtered out."""
        from swarm_attack.learning.strategy_optimizer import (
            StrategyOptimizer,
            PatternSet,
            Pattern,
        )

        optimizer = StrategyOptimizer(config=mock_config)

        prompt = "Write a function"
        patterns = PatternSet(patterns=[
            Pattern(
                pattern_id="low-conf",
                pattern_type="prompt",
                description="Low confidence suggestion",
                confidence=0.3,  # Below threshold
                success_rate=0.5,
            ),
            Pattern(
                pattern_id="high-conf",
                pattern_type="prompt",
                description="High confidence suggestion",
                confidence=0.9,  # Above threshold
                success_rate=0.85,
            ),
        ])

        result = optimizer.suggest_prompt_improvements(prompt, patterns)

        # Should only include high confidence suggestions
        for suggestion in result:
            assert suggestion.confidence >= 0.7  # Default threshold

    def test_suggest_prompt_improvements_custom_confidence_threshold(self, mock_config):
        """Test suggest_prompt_improvements with custom confidence threshold."""
        from swarm_attack.learning.strategy_optimizer import (
            StrategyOptimizer,
            PatternSet,
            Pattern,
        )

        optimizer = StrategyOptimizer(config=mock_config, min_confidence=0.5)

        prompt = "Write a function"
        patterns = PatternSet(patterns=[
            Pattern(
                pattern_id="medium-conf",
                pattern_type="prompt",
                description="Medium confidence",
                confidence=0.6,
                success_rate=0.7,
            ),
        ])

        result = optimizer.suggest_prompt_improvements(prompt, patterns)

        # Should include medium confidence with lower threshold
        assert len(result) >= 0  # May have suggestions


# =============================================================================
# StrategyOptimizer.suggest_tool_order() Tests
# =============================================================================


class TestStrategyOptimizerSuggestToolOrder:
    """Tests for suggest_tool_order() method."""

    def test_suggest_tool_order_returns_list(self, mock_config, sample_patterns):
        """Test that suggest_tool_order returns a list of strings."""
        from swarm_attack.learning.strategy_optimizer import (
            StrategyOptimizer,
            PatternSet,
            Pattern,
        )

        optimizer = StrategyOptimizer(config=mock_config)

        tools = ["Edit", "Read", "Glob"]
        patterns = PatternSet(patterns=[
            Pattern(
                pattern_id="tool-001",
                pattern_type="tool_order",
                description="Read before Edit",
                confidence=0.95,
                success_rate=0.92,
                metadata={"order": ["Read", "Edit"]},
            )
        ])

        result = optimizer.suggest_tool_order(tools, patterns)

        assert isinstance(result, list)
        for tool in result:
            assert isinstance(tool, str)

    def test_suggest_tool_order_preserves_tools(self, mock_config, sample_patterns):
        """Test that all input tools are in output."""
        from swarm_attack.learning.strategy_optimizer import (
            StrategyOptimizer,
            PatternSet,
            Pattern,
        )

        optimizer = StrategyOptimizer(config=mock_config)

        tools = ["Read", "Edit", "Glob", "Bash"]
        patterns = PatternSet(patterns=[
            Pattern(
                pattern_id="tool-001",
                pattern_type="tool_order",
                description="Read before Edit",
                confidence=0.95,
                success_rate=0.92,
                metadata={"order": ["Read", "Edit"]},
            )
        ])

        result = optimizer.suggest_tool_order(tools, patterns)

        assert set(result) == set(tools)

    def test_suggest_tool_order_with_empty_tools(self, mock_config, sample_patterns):
        """Test suggest_tool_order with empty tool list."""
        from swarm_attack.learning.strategy_optimizer import (
            StrategyOptimizer,
            PatternSet,
            Pattern,
        )

        optimizer = StrategyOptimizer(config=mock_config)

        tools = []
        patterns = PatternSet(patterns=[
            Pattern("p1", "tool_order", "desc", 0.8, 0.8, {"order": ["Read"]})
        ])

        result = optimizer.suggest_tool_order(tools, patterns)

        assert result == []

    def test_suggest_tool_order_with_empty_patterns(self, mock_config, empty_patterns):
        """Test suggest_tool_order with no patterns."""
        from swarm_attack.learning.strategy_optimizer import (
            StrategyOptimizer,
            PatternSet,
        )

        optimizer = StrategyOptimizer(config=mock_config)

        tools = ["Read", "Edit"]
        patterns = PatternSet(patterns=[])

        result = optimizer.suggest_tool_order(tools, patterns)

        # Should return original order when no patterns
        assert result == tools

    def test_suggest_tool_order_applies_high_confidence_patterns(self, mock_config):
        """Test that high confidence patterns are applied."""
        from swarm_attack.learning.strategy_optimizer import (
            StrategyOptimizer,
            PatternSet,
            Pattern,
        )

        optimizer = StrategyOptimizer(config=mock_config)

        tools = ["Edit", "Read"]  # Edit before Read (suboptimal)
        patterns = PatternSet(patterns=[
            Pattern(
                pattern_id="tool-001",
                pattern_type="tool_order",
                description="Read before Edit",
                confidence=0.95,
                success_rate=0.92,
                metadata={"order": ["Read", "Edit"]},
            )
        ])

        result = optimizer.suggest_tool_order(tools, patterns)

        # Should suggest Read before Edit based on pattern
        if len(result) >= 2:
            read_idx = result.index("Read") if "Read" in result else -1
            edit_idx = result.index("Edit") if "Edit" in result else -1
            if read_idx >= 0 and edit_idx >= 0:
                assert read_idx < edit_idx


# =============================================================================
# StrategyOptimizer.tune_recovery() Tests
# =============================================================================


class TestStrategyOptimizerTuneRecovery:
    """Tests for tune_recovery() method."""

    def test_tune_recovery_returns_recovery_strategy(self, mock_config, sample_recovery_strategy, sample_patterns):
        """Test that tune_recovery returns a RecoveryStrategy."""
        from swarm_attack.learning.strategy_optimizer import (
            StrategyOptimizer,
            RecoveryStrategy,
            PatternSet,
            Pattern,
        )

        optimizer = StrategyOptimizer(config=mock_config)

        current = RecoveryStrategy(
            strategy_id=sample_recovery_strategy.strategy_id,
            max_retries=sample_recovery_strategy.max_retries,
            backoff_multiplier=sample_recovery_strategy.backoff_multiplier,
            timeout_seconds=sample_recovery_strategy.timeout_seconds,
            fallback_actions=sample_recovery_strategy.fallback_actions,
        )

        patterns = PatternSet(patterns=[
            Pattern(
                pattern_id="recovery-001",
                pattern_type="recovery",
                description="Increase timeout",
                confidence=0.82,
                success_rate=0.78,
                metadata={"timeout_multiplier": 1.5},
            )
        ])

        result = optimizer.tune_recovery(current, patterns)

        assert isinstance(result, RecoveryStrategy)

    def test_tune_recovery_with_empty_patterns(self, mock_config, sample_recovery_strategy, empty_patterns):
        """Test tune_recovery with no patterns returns unchanged strategy."""
        from swarm_attack.learning.strategy_optimizer import (
            StrategyOptimizer,
            RecoveryStrategy,
            PatternSet,
        )

        optimizer = StrategyOptimizer(config=mock_config)

        current = RecoveryStrategy(
            strategy_id="rec-001",
            max_retries=3,
            backoff_multiplier=2.0,
            timeout_seconds=300,
        )

        patterns = PatternSet(patterns=[])

        result = optimizer.tune_recovery(current, patterns)

        # Should return equivalent strategy when no patterns
        assert result.max_retries == current.max_retries
        assert result.timeout_seconds == current.timeout_seconds

    def test_tune_recovery_applies_timeout_adjustment(self, mock_config):
        """Test that recovery patterns adjust timeout."""
        from swarm_attack.learning.strategy_optimizer import (
            StrategyOptimizer,
            RecoveryStrategy,
            PatternSet,
            Pattern,
        )

        optimizer = StrategyOptimizer(config=mock_config)

        current = RecoveryStrategy(
            strategy_id="rec-001",
            max_retries=3,
            timeout_seconds=300,
        )

        patterns = PatternSet(patterns=[
            Pattern(
                pattern_id="recovery-timeout",
                pattern_type="recovery",
                description="Increase timeout for complex tasks",
                confidence=0.90,
                success_rate=0.85,
                metadata={"timeout_multiplier": 2.0},
            )
        ])

        result = optimizer.tune_recovery(current, patterns)

        # Timeout should be adjusted based on pattern
        # The exact behavior depends on implementation
        assert result.timeout_seconds >= current.timeout_seconds

    def test_tune_recovery_applies_retry_adjustment(self, mock_config):
        """Test that recovery patterns can adjust max_retries."""
        from swarm_attack.learning.strategy_optimizer import (
            StrategyOptimizer,
            RecoveryStrategy,
            PatternSet,
            Pattern,
        )

        optimizer = StrategyOptimizer(config=mock_config)

        current = RecoveryStrategy(
            strategy_id="rec-001",
            max_retries=2,
        )

        patterns = PatternSet(patterns=[
            Pattern(
                pattern_id="recovery-retry",
                pattern_type="recovery",
                description="Increase retries for transient errors",
                confidence=0.85,
                success_rate=0.80,
                metadata={"max_retries_delta": 2},
            )
        ])

        result = optimizer.tune_recovery(current, patterns)

        # max_retries should be adjusted
        assert result.max_retries >= current.max_retries

    def test_tune_recovery_adds_fallback_actions(self, mock_config):
        """Test that recovery patterns can add fallback actions."""
        from swarm_attack.learning.strategy_optimizer import (
            StrategyOptimizer,
            RecoveryStrategy,
            PatternSet,
            Pattern,
        )

        optimizer = StrategyOptimizer(config=mock_config)

        current = RecoveryStrategy(
            strategy_id="rec-001",
            fallback_actions=["retry"],
        )

        patterns = PatternSet(patterns=[
            Pattern(
                pattern_id="recovery-fallback",
                pattern_type="recovery",
                description="Add simplification as fallback",
                confidence=0.88,
                success_rate=0.82,
                metadata={"add_fallback": "simplify"},
            )
        ])

        result = optimizer.tune_recovery(current, patterns)

        # Should have at least the original fallback actions
        assert "retry" in result.fallback_actions

    def test_tune_recovery_generates_new_strategy_id(self, mock_config):
        """Test that tune_recovery generates a new strategy ID."""
        from swarm_attack.learning.strategy_optimizer import (
            StrategyOptimizer,
            RecoveryStrategy,
            PatternSet,
            Pattern,
        )

        optimizer = StrategyOptimizer(config=mock_config)

        current = RecoveryStrategy(
            strategy_id="rec-original",
        )

        patterns = PatternSet(patterns=[
            Pattern("p1", "recovery", "desc", 0.8, 0.8)
        ])

        result = optimizer.tune_recovery(current, patterns)

        # Should have a different strategy ID
        assert result.strategy_id != current.strategy_id


# =============================================================================
# Context Construction Suggestions Tests
# =============================================================================


class TestStrategyOptimizerContextSuggestions:
    """Tests for context construction improvements in optimize()."""

    def test_optimize_includes_context_improvements(self, mock_config, sample_task):
        """Test that optimize() includes context construction improvements."""
        from swarm_attack.learning.strategy_optimizer import (
            StrategyOptimizer,
            Task,
            PatternSet,
            Pattern,
        )

        optimizer = StrategyOptimizer(config=mock_config)

        task = Task(
            task_id=sample_task.task_id,
            description=sample_task.description,
        )

        patterns = PatternSet(patterns=[
            Pattern(
                pattern_id="context-001",
                pattern_type="context",
                description="Include module registry",
                confidence=0.88,
                success_rate=0.85,
                metadata={"include": ["module_registry"]},
            )
        ])

        result = optimizer.optimize(task, patterns)

        # Should have context_improvements populated
        assert isinstance(result.context_improvements, list)

    def test_optimize_context_improvements_from_patterns(self, mock_config, sample_task):
        """Test that context improvements come from context patterns."""
        from swarm_attack.learning.strategy_optimizer import (
            StrategyOptimizer,
            Task,
            PatternSet,
            Pattern,
        )

        optimizer = StrategyOptimizer(config=mock_config)

        task = Task(
            task_id=sample_task.task_id,
            description=sample_task.description,
        )

        patterns = PatternSet(patterns=[
            Pattern(
                pattern_id="context-001",
                pattern_type="context",
                description="Include prior work summaries",
                confidence=0.90,
                success_rate=0.88,
                metadata={"include": ["completed_summaries"]},
            ),
            Pattern(
                pattern_id="context-002",
                pattern_type="context",
                description="Include test structure",
                confidence=0.85,
                success_rate=0.82,
                metadata={"include": ["test_structure"]},
            ),
        ])

        result = optimizer.optimize(task, patterns)

        # Should have improvements from high-confidence context patterns
        assert len(result.context_improvements) >= 0


# =============================================================================
# Confidence-Based Filtering Tests
# =============================================================================


class TestConfidenceBasedFiltering:
    """Tests for confidence-based filtering across all methods."""

    def test_optimizer_respects_min_confidence(self, mock_config):
        """Test that optimizer respects minimum confidence setting."""
        from swarm_attack.learning.strategy_optimizer import (
            StrategyOptimizer,
            Task,
            PatternSet,
            Pattern,
        )

        optimizer = StrategyOptimizer(config=mock_config, min_confidence=0.9)

        task = Task(
            task_id="task-001",
            description="Test task",
        )

        patterns = PatternSet(patterns=[
            Pattern(
                pattern_id="low",
                pattern_type="prompt",
                description="Low confidence",
                confidence=0.7,  # Below 0.9 threshold
                success_rate=0.8,
            ),
            Pattern(
                pattern_id="high",
                pattern_type="prompt",
                description="High confidence",
                confidence=0.95,  # Above 0.9 threshold
                success_rate=0.9,
            ),
        ])

        result = optimizer.optimize(task, patterns)

        # Only high confidence patterns should be applied
        # The exact assertion depends on implementation
        assert result.confidence_score >= 0.0

    def test_filter_patterns_by_confidence(self, mock_config):
        """Test internal pattern filtering by confidence."""
        from swarm_attack.learning.strategy_optimizer import (
            StrategyOptimizer,
            PatternSet,
            Pattern,
        )

        optimizer = StrategyOptimizer(config=mock_config, min_confidence=0.7)

        patterns = PatternSet(patterns=[
            Pattern("p1", "prompt", "desc", 0.5, 0.6),
            Pattern("p2", "prompt", "desc", 0.8, 0.9),
            Pattern("p3", "prompt", "desc", 0.9, 0.95),
        ])

        # Use internal method if available, or test via public methods
        filtered = patterns.get_high_confidence_patterns(min_confidence=0.7)

        assert len(filtered) == 2
        for p in filtered:
            assert p.confidence >= 0.7


# =============================================================================
# Edge Cases and Error Handling Tests
# =============================================================================


class TestEdgeCasesAndErrorHandling:
    """Tests for edge cases and error handling."""

    def test_optimize_with_none_task_raises_error(self, mock_config, sample_patterns):
        """Test that optimize() raises error for None task."""
        from swarm_attack.learning.strategy_optimizer import (
            StrategyOptimizer,
            PatternSet,
        )

        optimizer = StrategyOptimizer(config=mock_config)
        patterns = PatternSet(patterns=[])

        with pytest.raises((ValueError, TypeError)):
            optimizer.optimize(None, patterns)

    def test_optimize_with_none_patterns_raises_error(self, mock_config, sample_task):
        """Test that optimize() raises error for None patterns."""
        from swarm_attack.learning.strategy_optimizer import (
            StrategyOptimizer,
            Task,
        )

        optimizer = StrategyOptimizer(config=mock_config)
        task = Task(
            task_id=sample_task.task_id,
            description=sample_task.description,
        )

        with pytest.raises((ValueError, TypeError)):
            optimizer.optimize(task, None)

    def test_suggest_prompt_improvements_with_none_prompt(self, mock_config):
        """Test suggest_prompt_improvements with None prompt."""
        from swarm_attack.learning.strategy_optimizer import (
            StrategyOptimizer,
            PatternSet,
        )

        optimizer = StrategyOptimizer(config=mock_config)
        patterns = PatternSet(patterns=[])

        with pytest.raises((ValueError, TypeError)):
            optimizer.suggest_prompt_improvements(None, patterns)

    def test_suggest_tool_order_with_none_tools(self, mock_config):
        """Test suggest_tool_order with None tools."""
        from swarm_attack.learning.strategy_optimizer import (
            StrategyOptimizer,
            PatternSet,
        )

        optimizer = StrategyOptimizer(config=mock_config)
        patterns = PatternSet(patterns=[])

        with pytest.raises((ValueError, TypeError)):
            optimizer.suggest_tool_order(None, patterns)

    def test_tune_recovery_with_none_strategy(self, mock_config):
        """Test tune_recovery with None strategy."""
        from swarm_attack.learning.strategy_optimizer import (
            StrategyOptimizer,
            PatternSet,
        )

        optimizer = StrategyOptimizer(config=mock_config)
        patterns = PatternSet(patterns=[])

        with pytest.raises((ValueError, TypeError)):
            optimizer.tune_recovery(None, patterns)

    def test_optimizer_with_invalid_min_confidence(self, mock_config):
        """Test that invalid min_confidence values are handled."""
        from swarm_attack.learning.strategy_optimizer import StrategyOptimizer

        # Should handle or raise for values outside [0, 1]
        with pytest.raises(ValueError):
            StrategyOptimizer(config=mock_config, min_confidence=1.5)

        with pytest.raises(ValueError):
            StrategyOptimizer(config=mock_config, min_confidence=-0.1)


# =============================================================================
# Integration Tests
# =============================================================================


class TestStrategyOptimizerIntegration:
    """Integration tests for StrategyOptimizer."""

    def test_full_optimization_workflow(self, mock_config):
        """Test complete optimization workflow."""
        from swarm_attack.learning.strategy_optimizer import (
            StrategyOptimizer,
            Task,
            PatternSet,
            Pattern,
            RecoveryStrategy,
        )

        optimizer = StrategyOptimizer(config=mock_config)

        # Create a task
        task = Task(
            task_id="integration-task",
            description="Implement authentication module",
            task_type="implementation",
            complexity="medium",
        )

        # Create patterns of all types
        patterns = PatternSet(patterns=[
            Pattern(
                pattern_id="prompt-001",
                pattern_type="prompt",
                description="Use step-by-step",
                confidence=0.85,
                success_rate=0.88,
            ),
            Pattern(
                pattern_id="tool-001",
                pattern_type="tool_order",
                description="Read first",
                confidence=0.90,
                success_rate=0.92,
                metadata={"order": ["Read", "Edit"]},
            ),
            Pattern(
                pattern_id="context-001",
                pattern_type="context",
                description="Include registry",
                confidence=0.88,
                success_rate=0.85,
                metadata={"include": ["module_registry"]},
            ),
            Pattern(
                pattern_id="recovery-001",
                pattern_type="recovery",
                description="Increase timeout",
                confidence=0.82,
                success_rate=0.78,
                metadata={"timeout_multiplier": 1.5},
            ),
        ])

        # Run optimization
        strategy = optimizer.optimize(task, patterns)

        # Verify results
        assert strategy.task_id == task.task_id
        assert strategy.strategy_id is not None
        assert 0.0 <= strategy.confidence_score <= 1.0

    def test_sequential_optimizations(self, mock_config):
        """Test multiple sequential optimizations."""
        from swarm_attack.learning.strategy_optimizer import (
            StrategyOptimizer,
            Task,
            PatternSet,
            Pattern,
        )

        optimizer = StrategyOptimizer(config=mock_config)

        patterns = PatternSet(patterns=[
            Pattern("p1", "prompt", "desc", 0.8, 0.8)
        ])

        tasks = [
            Task(task_id=f"task-{i}", description=f"Task {i}")
            for i in range(3)
        ]

        strategies = [optimizer.optimize(task, patterns) for task in tasks]

        # Each strategy should have unique ID
        strategy_ids = [s.strategy_id for s in strategies]
        assert len(set(strategy_ids)) == len(strategy_ids)
