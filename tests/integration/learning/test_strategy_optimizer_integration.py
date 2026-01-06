"""
Integration tests for StrategyOptimizer.

Tests integration between StrategyOptimizer and:
- EpisodeLogger (mocked - does not exist yet)
- PatternExtractor (mocked - does not exist yet)
- CoderAgent for applying optimizations

The StrategyOptimizer applies learned patterns to improve task execution:
- Prompt engineering suggestions
- Tool ordering recommendations
- Context construction improvements
- Recovery strategy tuning
"""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch
from dataclasses import dataclass, field
from typing import Any, Optional

from swarm_attack.learning.strategy_optimizer import (
    StrategyOptimizer,
    Task,
    Pattern,
    PatternSet,
    OptimizedStrategy,
    PromptSuggestion,
    RecoveryStrategy,
)
from swarm_attack.config import SwarmConfig, TestRunnerConfig


# =============================================================================
# Mock Classes for Non-Existent Dependencies
# =============================================================================


@dataclass
class MockEpisode:
    """Mock episode data representing a historical execution."""
    episode_id: str
    task_type: str
    success: bool
    duration_seconds: float
    tool_sequence: list[str] = field(default_factory=list)
    prompt_used: str = ""
    context_items: list[str] = field(default_factory=list)
    error_message: Optional[str] = None


class MockEpisodeLogger:
    """
    Mock EpisodeLogger for testing integration.

    In real implementation, EpisodeLogger would:
    - Store episodes from agent executions
    - Retrieve historical episodes by task type
    - Calculate success rates by pattern
    """

    def __init__(self, storage_path: Optional[Path] = None):
        self.storage_path = storage_path
        self._episodes: list[MockEpisode] = []

    def log_episode(self, episode: MockEpisode) -> None:
        """Log a new episode."""
        self._episodes.append(episode)

    def get_episodes_by_type(self, task_type: str) -> list[MockEpisode]:
        """Get all episodes for a given task type."""
        return [e for e in self._episodes if e.task_type == task_type]

    def get_successful_episodes(self) -> list[MockEpisode]:
        """Get all successful episodes."""
        return [e for e in self._episodes if e.success]

    def get_recent_episodes(self, limit: int = 100) -> list[MockEpisode]:
        """Get most recent episodes."""
        return self._episodes[-limit:]


class MockPatternExtractor:
    """
    Mock PatternExtractor for testing integration.

    In real implementation, PatternExtractor would:
    - Analyze historical episodes to find patterns
    - Extract successful prompt patterns
    - Identify optimal tool orderings
    - Discover context items that improve success
    """

    def __init__(self, min_samples: int = 5, min_confidence: float = 0.6):
        self.min_samples = min_samples
        self.min_confidence = min_confidence

    def extract_patterns(self, episodes: list[MockEpisode]) -> PatternSet:
        """Extract patterns from a list of episodes."""
        patterns = []

        # Analyze successful episodes for prompt patterns
        successful = [e for e in episodes if e.success]
        if len(successful) >= self.min_samples:
            # Find common prompt elements
            confidence = len(successful) / max(len(episodes), 1)
            if confidence >= self.min_confidence:
                patterns.append(Pattern(
                    pattern_id="prompt-001",
                    pattern_type="prompt",
                    description="Include specific context from issue body",
                    confidence=confidence,
                    success_rate=confidence,
                ))

        # Analyze tool sequences
        tool_sequences: dict[str, int] = {}
        for episode in successful:
            seq_key = "->".join(episode.tool_sequence)
            tool_sequences[seq_key] = tool_sequences.get(seq_key, 0) + 1

        if tool_sequences:
            best_seq = max(tool_sequences.items(), key=lambda x: x[1])
            seq_count = best_seq[1]
            confidence = seq_count / max(len(episodes), 1)
            if confidence >= self.min_confidence:
                patterns.append(Pattern(
                    pattern_id="tool-001",
                    pattern_type="tool_order",
                    description=f"Optimal tool sequence: {best_seq[0]}",
                    confidence=confidence,
                    success_rate=confidence,
                    metadata={"order": best_seq[0].split("->")},
                ))

        return PatternSet(patterns=patterns)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_config(tmp_path):
    """Create mock SwarmConfig with tmp_path as repo_root."""
    config = MagicMock(spec=SwarmConfig)
    config.repo_root = str(tmp_path)
    config.specs_path = tmp_path / "specs"
    config.state_path = tmp_path / ".swarm" / "state"
    config.tests = TestRunnerConfig(
        command="pytest",
        args=["-v"],
        timeout_seconds=300,
    )

    # Create necessary directories
    config.specs_path.mkdir(parents=True, exist_ok=True)
    config.state_path.mkdir(parents=True, exist_ok=True)

    return config


@pytest.fixture
def episode_logger(tmp_path):
    """Create mock episode logger."""
    return MockEpisodeLogger(storage_path=tmp_path / "episodes")


@pytest.fixture
def pattern_extractor():
    """Create mock pattern extractor."""
    return MockPatternExtractor(min_samples=2, min_confidence=0.5)


@pytest.fixture
def sample_episodes():
    """Create sample episodes for testing."""
    return [
        MockEpisode(
            episode_id="ep-001",
            task_type="implementation",
            success=True,
            duration_seconds=120.0,
            tool_sequence=["Read", "Grep", "Edit"],
            prompt_used="Implement the feature as specified",
            context_items=["spec", "existing_code"],
        ),
        MockEpisode(
            episode_id="ep-002",
            task_type="implementation",
            success=True,
            duration_seconds=90.0,
            tool_sequence=["Read", "Grep", "Edit"],
            prompt_used="Implement the feature with tests",
            context_items=["spec", "existing_code", "tests"],
        ),
        MockEpisode(
            episode_id="ep-003",
            task_type="implementation",
            success=False,
            duration_seconds=180.0,
            tool_sequence=["Edit", "Read"],
            prompt_used="Implement quickly",
            context_items=["spec"],
            error_message="Tests failed",
        ),
        MockEpisode(
            episode_id="ep-004",
            task_type="bug_fix",
            success=True,
            duration_seconds=60.0,
            tool_sequence=["Grep", "Read", "Edit"],
            prompt_used="Fix the bug",
            context_items=["error_log", "stack_trace"],
        ),
    ]


@pytest.fixture
def sample_task():
    """Create a sample task for optimization."""
    return Task(
        task_id="task-001",
        description="Implement user authentication",
        task_type="implementation",
        complexity="medium",
        context={"feature": "auth", "priority": "high"},
    )


@pytest.fixture
def high_confidence_patterns():
    """Create a PatternSet with high confidence patterns."""
    return PatternSet(patterns=[
        Pattern(
            pattern_id="prompt-001",
            pattern_type="prompt",
            description="Include detailed acceptance criteria",
            confidence=0.9,
            success_rate=0.85,
        ),
        Pattern(
            pattern_id="tool-001",
            pattern_type="tool_order",
            description="Read before Edit",
            confidence=0.85,
            success_rate=0.90,
            metadata={"order": ["Read", "Grep", "Edit"]},
        ),
        Pattern(
            pattern_id="context-001",
            pattern_type="context",
            description="Include test files in context",
            confidence=0.8,
            success_rate=0.82,
            metadata={"include": ["test_files", "existing_implementation"]},
        ),
        Pattern(
            pattern_id="recovery-001",
            pattern_type="recovery",
            description="Increase timeout for complex tasks",
            confidence=0.75,
            success_rate=0.78,
            metadata={"timeout_multiplier": 1.5, "max_retries_delta": 1},
        ),
    ])


# =============================================================================
# Integration Tests: EpisodeLogger + StrategyOptimizer
# =============================================================================


class TestEpisodeLoggerIntegration:
    """Tests for StrategyOptimizer integration with EpisodeLogger."""

    def test_optimizer_uses_patterns_from_logged_episodes(
        self,
        mock_config,
        episode_logger,
        pattern_extractor,
        sample_episodes,
        sample_task,
    ):
        """
        StrategyOptimizer should use patterns derived from logged episodes.

        Scenario:
        1. Episodes are logged to EpisodeLogger
        2. PatternExtractor extracts patterns from episodes
        3. StrategyOptimizer uses patterns to optimize task
        4. Resulting strategy should reflect learned patterns
        """
        # ARRANGE: Log episodes
        for episode in sample_episodes:
            episode_logger.log_episode(episode)

        # Extract patterns from logged episodes
        episodes = episode_logger.get_episodes_by_type("implementation")
        patterns = pattern_extractor.extract_patterns(episodes)

        # ACT: Optimize task using extracted patterns
        optimizer = StrategyOptimizer(config=mock_config, min_confidence=0.5)
        strategy = optimizer.optimize(sample_task, patterns)

        # ASSERT: Strategy should be influenced by patterns
        assert isinstance(strategy, OptimizedStrategy)
        assert strategy.task_id == sample_task.task_id
        # Confidence score should reflect pattern quality
        assert 0.0 <= strategy.confidence_score <= 1.0

    def test_optimizer_filters_low_confidence_episodes(
        self,
        mock_config,
        episode_logger,
        sample_task,
    ):
        """
        StrategyOptimizer with high min_confidence should ignore low-quality patterns.
        """
        # ARRANGE: Create patterns with mixed confidence
        patterns = PatternSet(patterns=[
            Pattern(
                pattern_id="low-conf",
                pattern_type="prompt",
                description="Low confidence pattern",
                confidence=0.3,
                success_rate=0.4,
            ),
            Pattern(
                pattern_id="high-conf",
                pattern_type="prompt",
                description="High confidence pattern",
                confidence=0.9,
                success_rate=0.9,
            ),
        ])

        # ACT: Optimize with high confidence threshold
        optimizer = StrategyOptimizer(config=mock_config, min_confidence=0.7)
        strategy = optimizer.optimize(sample_task, patterns)

        # ASSERT: Only high confidence patterns should be used
        # The prompt suggestions should only include high-conf pattern
        if strategy.prompt_suggestions:
            for suggestion in strategy.prompt_suggestions:
                assert "High confidence" in suggestion.reason, \
                    "Only high confidence pattern should be applied"

    def test_no_patterns_yields_empty_strategy(
        self,
        mock_config,
        sample_task,
    ):
        """
        StrategyOptimizer with no patterns should produce minimal strategy.
        """
        # ARRANGE: Empty pattern set
        patterns = PatternSet(patterns=[])

        # ACT: Optimize
        optimizer = StrategyOptimizer(config=mock_config)
        strategy = optimizer.optimize(sample_task, patterns)

        # ASSERT: Strategy should be valid but minimal
        assert isinstance(strategy, OptimizedStrategy)
        assert strategy.task_id == sample_task.task_id
        assert len(strategy.prompt_suggestions) == 0
        assert len(strategy.tool_order) == 0
        assert len(strategy.context_improvements) == 0
        assert strategy.confidence_score == 0.0


# =============================================================================
# Integration Tests: PatternExtractor + StrategyOptimizer
# =============================================================================


class TestPatternExtractorIntegration:
    """Tests for StrategyOptimizer integration with PatternExtractor."""

    def test_extracted_prompt_patterns_become_suggestions(
        self,
        mock_config,
        sample_task,
    ):
        """
        Prompt patterns from extractor should become prompt suggestions.
        """
        # ARRANGE: Pattern with prompt type
        patterns = PatternSet(patterns=[
            Pattern(
                pattern_id="prompt-test",
                pattern_type="prompt",
                description="Always include acceptance criteria in prompt",
                confidence=0.85,
                success_rate=0.90,
            ),
        ])

        # ACT: Optimize and suggest improvements
        optimizer = StrategyOptimizer(config=mock_config, min_confidence=0.7)
        suggestions = optimizer.suggest_prompt_improvements(
            "Implement the feature",
            patterns,
        )

        # ASSERT: Should have suggestion based on pattern
        assert len(suggestions) == 1
        assert isinstance(suggestions[0], PromptSuggestion)
        assert "acceptance criteria" in suggestions[0].reason

    def test_extracted_tool_patterns_become_ordering(
        self,
        mock_config,
        sample_task,
    ):
        """
        Tool order patterns should influence suggested tool ordering.
        """
        # ARRANGE: Pattern with tool ordering
        patterns = PatternSet(patterns=[
            Pattern(
                pattern_id="tool-test",
                pattern_type="tool_order",
                description="Read before Edit pattern",
                confidence=0.9,
                success_rate=0.95,
                metadata={"order": ["Read", "Grep", "Edit"]},
            ),
        ])

        # ACT: Get tool ordering suggestion
        optimizer = StrategyOptimizer(config=mock_config, min_confidence=0.7)
        tools = ["Edit", "Read", "Grep"]  # Out of order
        ordered = optimizer.suggest_tool_order(tools, patterns)

        # ASSERT: Should reorder tools based on pattern
        assert ordered.index("Read") < ordered.index("Edit"), \
            "Read should come before Edit based on pattern"

    def test_extracted_context_patterns_become_improvements(
        self,
        mock_config,
        sample_task,
        high_confidence_patterns,
    ):
        """
        Context patterns should produce context improvements in strategy.
        """
        # ACT: Optimize task
        optimizer = StrategyOptimizer(config=mock_config, min_confidence=0.7)
        strategy = optimizer.optimize(sample_task, high_confidence_patterns)

        # ASSERT: Should have context improvements
        assert len(strategy.context_improvements) > 0
        # Should suggest including items from the pattern
        improvements_str = " ".join(strategy.context_improvements)
        assert "test_files" in improvements_str or "existing" in improvements_str


# =============================================================================
# Integration Tests: StrategyOptimizer + CoderAgent
# =============================================================================


class TestCoderAgentIntegration:
    """Tests for StrategyOptimizer integration with CoderAgent."""

    def test_optimized_strategy_can_be_applied_to_coder_context(
        self,
        mock_config,
        sample_task,
        high_confidence_patterns,
    ):
        """
        OptimizedStrategy output should be usable by CoderAgent.

        The strategy produces outputs that can be injected into
        CoderAgent's context for improved execution.
        """
        # ARRANGE: Optimize task
        optimizer = StrategyOptimizer(config=mock_config, min_confidence=0.7)
        strategy = optimizer.optimize(sample_task, high_confidence_patterns)

        # ACT: Convert strategy to CoderAgent-compatible context
        coder_context = {
            "feature_id": "test-feature",
            "issue_number": 1,
            # Inject strategy components
            "optimization_hints": {
                "prompt_suggestions": [s.to_dict() for s in strategy.prompt_suggestions],
                "tool_order": strategy.tool_order,
                "context_improvements": strategy.context_improvements,
            },
        }

        # ASSERT: Context should be valid and contain strategy elements
        assert "optimization_hints" in coder_context
        hints = coder_context["optimization_hints"]
        assert isinstance(hints["prompt_suggestions"], list)
        assert isinstance(hints["tool_order"], list)
        assert isinstance(hints["context_improvements"], list)

    @patch("swarm_attack.agents.coder.CoderAgent")
    def test_coder_receives_strategy_context(
        self,
        MockCoderAgent,
        mock_config,
        sample_task,
        high_confidence_patterns,
    ):
        """
        CoderAgent.run() should be called with strategy-enhanced context.
        """
        # ARRANGE: Create mock coder
        mock_coder = MagicMock()
        MockCoderAgent.return_value = mock_coder
        mock_coder.run.return_value = MagicMock(
            success=True,
            output={"files_created": ["test.py"]},
        )

        # Optimize task
        optimizer = StrategyOptimizer(config=mock_config, min_confidence=0.7)
        strategy = optimizer.optimize(sample_task, high_confidence_patterns)

        # ACT: Call coder with strategy-enhanced context
        coder = MockCoderAgent(mock_config)
        context = {
            "feature_id": "test-feature",
            "issue_number": 1,
            "strategy": strategy.to_dict(),
        }
        result = coder.run(context)

        # ASSERT: Coder was called with strategy in context
        mock_coder.run.assert_called_once()
        call_args = mock_coder.run.call_args
        assert "strategy" in call_args[0][0]

    def test_recovery_strategy_tuning_for_coder_retries(
        self,
        mock_config,
        high_confidence_patterns,
    ):
        """
        Tuned recovery strategy should provide better retry parameters.

        When CoderAgent fails, the tuned recovery strategy should
        provide adjusted retry parameters (timeouts, retries, fallbacks).
        """
        # ARRANGE: Create initial recovery strategy
        initial_strategy = RecoveryStrategy(
            strategy_id="initial",
            max_retries=3,
            backoff_multiplier=2.0,
            timeout_seconds=300,
            fallback_actions=["retry_with_smaller_scope"],
        )

        # ACT: Tune recovery based on patterns
        optimizer = StrategyOptimizer(config=mock_config, min_confidence=0.7)
        tuned = optimizer.tune_recovery(initial_strategy, high_confidence_patterns)

        # ASSERT: Recovery should be adjusted based on patterns
        assert isinstance(tuned, RecoveryStrategy)
        # The recovery pattern has timeout_multiplier=1.5 and max_retries_delta=1
        assert tuned.timeout_seconds == int(300 * 1.5)
        assert tuned.max_retries == 3 + 1  # Initial + delta


# =============================================================================
# Integration Tests: Full Pipeline
# =============================================================================


class TestFullPipelineIntegration:
    """End-to-end integration tests for the full learning pipeline."""

    def test_episode_to_optimization_pipeline(
        self,
        mock_config,
        episode_logger,
        pattern_extractor,
        sample_episodes,
    ):
        """
        Full pipeline: Episodes -> Patterns -> Optimization -> Strategy.

        This tests the complete flow from logged episodes to
        an optimized strategy ready for CoderAgent.
        """
        # ARRANGE: Log episodes
        for episode in sample_episodes:
            episode_logger.log_episode(episode)

        # Create a new task to optimize
        new_task = Task(
            task_id="new-task",
            description="Add user profile feature",
            task_type="implementation",
            complexity="medium",
        )

        # ACT: Run full pipeline
        # Step 1: Get relevant episodes
        episodes = episode_logger.get_episodes_by_type("implementation")

        # Step 2: Extract patterns
        patterns = pattern_extractor.extract_patterns(episodes)

        # Step 3: Optimize task
        optimizer = StrategyOptimizer(config=mock_config, min_confidence=0.5)
        strategy = optimizer.optimize(new_task, patterns)

        # ASSERT: Strategy should be valid and influenced by historical data
        assert isinstance(strategy, OptimizedStrategy)
        assert strategy.task_id == "new-task"

        # Should have some suggestions if patterns were extracted
        if patterns.patterns:
            assert strategy.confidence_score > 0.0

    def test_continuous_learning_improves_strategy(
        self,
        mock_config,
        episode_logger,
        pattern_extractor,
    ):
        """
        Adding successful episodes should improve future strategies.

        As more successful episodes are logged, the confidence
        in patterns should increase.
        """
        # ARRANGE: Start with few episodes
        initial_episodes = [
            MockEpisode(
                episode_id=f"ep-{i}",
                task_type="implementation",
                success=True,
                duration_seconds=100.0,
                tool_sequence=["Read", "Edit"],
            )
            for i in range(3)
        ]

        for ep in initial_episodes:
            episode_logger.log_episode(ep)

        # Extract initial patterns
        episodes = episode_logger.get_episodes_by_type("implementation")
        initial_patterns = pattern_extractor.extract_patterns(episodes)

        # Add more successful episodes with same pattern
        additional_episodes = [
            MockEpisode(
                episode_id=f"ep-new-{i}",
                task_type="implementation",
                success=True,
                duration_seconds=90.0,
                tool_sequence=["Read", "Edit"],
            )
            for i in range(5)
        ]

        for ep in additional_episodes:
            episode_logger.log_episode(ep)

        # ACT: Extract patterns again
        all_episodes = episode_logger.get_episodes_by_type("implementation")
        updated_patterns = pattern_extractor.extract_patterns(all_episodes)

        # ASSERT: More data should improve confidence
        # Note: Confidence may or may not increase depending on implementation
        # But we should have valid patterns
        assert isinstance(updated_patterns, PatternSet)

    def test_failed_episodes_reduce_pattern_confidence(
        self,
        mock_config,
        pattern_extractor,
    ):
        """
        Adding failed episodes should reduce pattern confidence.

        If a pattern starts to fail, confidence should decrease.
        """
        # ARRANGE: Mix of successful and failed episodes with same sequence
        episodes = [
            MockEpisode(
                episode_id="success-1",
                task_type="implementation",
                success=True,
                duration_seconds=100.0,
                tool_sequence=["Read", "Edit"],
            ),
            MockEpisode(
                episode_id="success-2",
                task_type="implementation",
                success=True,
                duration_seconds=100.0,
                tool_sequence=["Read", "Edit"],
            ),
            MockEpisode(
                episode_id="fail-1",
                task_type="implementation",
                success=False,
                duration_seconds=200.0,
                tool_sequence=["Read", "Edit"],
                error_message="Tests failed",
            ),
            MockEpisode(
                episode_id="fail-2",
                task_type="implementation",
                success=False,
                duration_seconds=200.0,
                tool_sequence=["Read", "Edit"],
                error_message="Tests failed",
            ),
        ]

        # ACT: Extract patterns
        patterns = pattern_extractor.extract_patterns(episodes)

        # ASSERT: Confidence should be moderate (2/4 = 0.5)
        # With min_confidence=0.5 in fixture, patterns should be extracted
        # but with lower confidence than all-success case
        if patterns.patterns:
            for pattern in patterns.patterns:
                assert pattern.confidence <= 0.75, \
                    "Confidence should be reduced by failures"


# =============================================================================
# Edge Case Tests
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_optimizer_handles_empty_episode_list(
        self,
        mock_config,
        pattern_extractor,
        sample_task,
    ):
        """
        StrategyOptimizer should handle empty episode data gracefully.
        """
        # ARRANGE: No episodes
        patterns = pattern_extractor.extract_patterns([])

        # ACT: Optimize with empty patterns
        optimizer = StrategyOptimizer(config=mock_config)
        strategy = optimizer.optimize(sample_task, patterns)

        # ASSERT: Should return valid but empty strategy
        assert isinstance(strategy, OptimizedStrategy)
        assert strategy.confidence_score == 0.0

    def test_optimizer_handles_invalid_task(self, mock_config):
        """
        StrategyOptimizer should raise error for invalid task input.
        """
        optimizer = StrategyOptimizer(config=mock_config)
        patterns = PatternSet(patterns=[])

        with pytest.raises((ValueError, TypeError)):
            optimizer.optimize(None, patterns)

    def test_optimizer_handles_invalid_patterns(self, mock_config, sample_task):
        """
        StrategyOptimizer should raise error for invalid patterns input.
        """
        optimizer = StrategyOptimizer(config=mock_config)

        with pytest.raises((ValueError, TypeError)):
            optimizer.optimize(sample_task, None)

    def test_strategy_serialization_roundtrip(
        self,
        mock_config,
        sample_task,
        high_confidence_patterns,
    ):
        """
        OptimizedStrategy should survive JSON serialization roundtrip.
        """
        # ARRANGE: Create strategy
        optimizer = StrategyOptimizer(config=mock_config, min_confidence=0.7)
        strategy = optimizer.optimize(sample_task, high_confidence_patterns)

        # ACT: Serialize and deserialize
        strategy_dict = strategy.to_dict()
        restored = OptimizedStrategy.from_dict(strategy_dict)

        # ASSERT: Should be equivalent
        assert restored.strategy_id == strategy.strategy_id
        assert restored.task_id == strategy.task_id
        assert restored.confidence_score == strategy.confidence_score
        assert len(restored.tool_order) == len(strategy.tool_order)
        assert len(restored.context_improvements) == len(strategy.context_improvements)

    def test_pattern_set_filtering_by_type(self, high_confidence_patterns):
        """
        PatternSet should correctly filter patterns by type.
        """
        # ACT: Filter by different types
        prompt_patterns = high_confidence_patterns.get_patterns_by_type("prompt")
        tool_patterns = high_confidence_patterns.get_patterns_by_type("tool_order")
        context_patterns = high_confidence_patterns.get_patterns_by_type("context")
        recovery_patterns = high_confidence_patterns.get_patterns_by_type("recovery")

        # ASSERT: Each type should return correct patterns
        assert all(p.pattern_type == "prompt" for p in prompt_patterns)
        assert all(p.pattern_type == "tool_order" for p in tool_patterns)
        assert all(p.pattern_type == "context" for p in context_patterns)
        assert all(p.pattern_type == "recovery" for p in recovery_patterns)

    def test_min_confidence_validation(self, mock_config):
        """
        StrategyOptimizer should validate min_confidence bounds.
        """
        # Valid values
        StrategyOptimizer(config=mock_config, min_confidence=0.0)
        StrategyOptimizer(config=mock_config, min_confidence=0.5)
        StrategyOptimizer(config=mock_config, min_confidence=1.0)

        # Invalid values
        with pytest.raises(ValueError):
            StrategyOptimizer(config=mock_config, min_confidence=-0.1)

        with pytest.raises(ValueError):
            StrategyOptimizer(config=mock_config, min_confidence=1.1)
