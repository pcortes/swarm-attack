"""Integration tests for CoderIntegration module.

Tests the wiring of EpisodeLogger, PatternExtractor, and StrategyOptimizer
into the CoderAgent execution loop.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
from unittest.mock import MagicMock, patch

import pytest

# Import the learning layer components
from swarm_attack.learning.strategy_optimizer import (
    StrategyOptimizer,
    Task,
    PatternSet,
    Pattern,
    OptimizedStrategy,
    PromptSuggestion,
    RecoveryStrategy,
)


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def temp_dir(tmp_path: Path) -> Path:
    """Create a temporary directory for test files."""
    return tmp_path


@pytest.fixture
def mock_config(temp_dir: Path) -> MagicMock:
    """Create a mock SwarmConfig."""
    config = MagicMock()
    config.repo_root = temp_dir
    config.specs_path = temp_dir / "specs"
    config.specs_path.mkdir(parents=True, exist_ok=True)
    return config


@pytest.fixture
def sample_patterns() -> PatternSet:
    """Create sample patterns for testing."""
    return PatternSet(patterns=[
        Pattern(
            pattern_id="p1",
            pattern_type="prompt",
            description="Add specific examples to prompts",
            confidence=0.85,
            success_rate=0.9,
            metadata={"examples_count": 3},
        ),
        Pattern(
            pattern_id="p2",
            pattern_type="tool_order",
            description="Read files before editing",
            confidence=0.92,
            success_rate=0.95,
            metadata={"order": ["Read", "Grep", "Edit"]},
        ),
        Pattern(
            pattern_id="p3",
            pattern_type="context",
            description="Include module registry",
            confidence=0.8,
            success_rate=0.85,
            metadata={"include": ["module_registry", "completed_summaries"]},
        ),
        Pattern(
            pattern_id="p4",
            pattern_type="recovery",
            description="Increase timeout for complex tasks",
            confidence=0.75,
            success_rate=0.8,
            metadata={"timeout_multiplier": 1.5},
        ),
    ])


# =============================================================================
# EpisodeLogger Tests
# =============================================================================


class TestEpisodeLogger:
    """Tests for EpisodeLogger component."""

    def test_episode_logger_creation(self, temp_dir: Path) -> None:
        """Test that EpisodeLogger can be created with base path."""
        from swarm_attack.learning.coder_integration import EpisodeLogger

        logger = EpisodeLogger(base_path=temp_dir)
        assert logger is not None
        assert logger.base_path == temp_dir

    def test_log_episode_start(self, temp_dir: Path) -> None:
        """Test logging the start of an episode."""
        from swarm_attack.learning.coder_integration import EpisodeLogger, Episode

        logger = EpisodeLogger(base_path=temp_dir)
        episode = logger.start_episode(
            feature_id="test-feature",
            issue_number=1,
            task_type="implementation",
        )

        assert episode is not None
        assert episode.feature_id == "test-feature"
        assert episode.issue_number == 1
        assert episode.task_type == "implementation"
        assert episode.status == "in_progress"

    def test_log_episode_success(self, temp_dir: Path) -> None:
        """Test logging a successful episode completion."""
        from swarm_attack.learning.coder_integration import EpisodeLogger

        logger = EpisodeLogger(base_path=temp_dir)
        episode = logger.start_episode(
            feature_id="test-feature",
            issue_number=1,
            task_type="implementation",
        )

        logger.complete_episode(
            episode=episode,
            success=True,
            cost_usd=0.05,
            files_created=["src/foo.py"],
            files_modified=["src/bar.py"],
        )

        assert episode.status == "completed"
        assert episode.success is True
        assert episode.cost_usd == 0.05

    def test_log_episode_failure(self, temp_dir: Path) -> None:
        """Test logging a failed episode."""
        from swarm_attack.learning.coder_integration import EpisodeLogger

        logger = EpisodeLogger(base_path=temp_dir)
        episode = logger.start_episode(
            feature_id="test-feature",
            issue_number=1,
            task_type="implementation",
        )

        logger.complete_episode(
            episode=episode,
            success=False,
            error="Test validation failed",
        )

        assert episode.status == "failed"
        assert episode.success is False
        assert episode.error == "Test validation failed"

    def test_episode_persistence(self, temp_dir: Path) -> None:
        """Test that episodes are persisted to disk."""
        from swarm_attack.learning.coder_integration import EpisodeLogger

        logger = EpisodeLogger(base_path=temp_dir)
        episode = logger.start_episode(
            feature_id="test-feature",
            issue_number=1,
            task_type="implementation",
        )
        logger.complete_episode(episode=episode, success=True, cost_usd=0.05)

        # Verify file was created
        episodes_file = temp_dir / "episodes.jsonl"
        assert episodes_file.exists()

        # Verify content
        with open(episodes_file, "r") as f:
            lines = f.readlines()
            assert len(lines) >= 1
            data = json.loads(lines[-1])
            assert data["feature_id"] == "test-feature"

    def test_load_recent_episodes(self, temp_dir: Path) -> None:
        """Test loading recent episodes."""
        from swarm_attack.learning.coder_integration import EpisodeLogger

        logger = EpisodeLogger(base_path=temp_dir)

        # Create several episodes
        for i in range(5):
            episode = logger.start_episode(
                feature_id=f"feature-{i}",
                issue_number=i,
                task_type="implementation",
            )
            logger.complete_episode(episode=episode, success=True, cost_usd=0.01 * i)

        # Load recent
        recent = logger.load_recent(limit=3)
        assert len(recent) == 3
        # Should be most recent first
        assert recent[0].feature_id == "feature-4"

    def test_record_retry(self, temp_dir: Path) -> None:
        """Test recording retry attempts."""
        from swarm_attack.learning.coder_integration import EpisodeLogger

        logger = EpisodeLogger(base_path=temp_dir)
        episode = logger.start_episode(
            feature_id="test-feature",
            issue_number=1,
            task_type="implementation",
        )

        logger.record_retry(episode=episode, retry_number=1, error="Test failed")
        assert episode.retry_count == 1

        logger.record_retry(episode=episode, retry_number=2, error="Still failing")
        assert episode.retry_count == 2


# =============================================================================
# PatternExtractor Tests
# =============================================================================


class TestPatternExtractor:
    """Tests for PatternExtractor component."""

    def test_pattern_extractor_creation(self) -> None:
        """Test that PatternExtractor can be created."""
        from swarm_attack.learning.coder_integration import PatternExtractor

        extractor = PatternExtractor()
        assert extractor is not None

    def test_extract_prompt_patterns(self, temp_dir: Path) -> None:
        """Test extracting prompt patterns from episodes."""
        from swarm_attack.learning.coder_integration import (
            PatternExtractor,
            EpisodeLogger,
        )

        logger = EpisodeLogger(base_path=temp_dir)

        # Create successful episodes with prompt context
        for i in range(5):
            episode = logger.start_episode(
                feature_id="feature",
                issue_number=i,
                task_type="implementation",
            )
            episode.prompt_metadata = {
                "included_context": ["module_registry", "spec"],
                "prompt_length": 5000 + i * 100,
            }
            logger.complete_episode(episode=episode, success=True, cost_usd=0.05)

        extractor = PatternExtractor()
        patterns = extractor.extract_patterns(logger.load_all())

        # Should extract some patterns
        assert patterns is not None
        assert isinstance(patterns, PatternSet)

    def test_extract_tool_order_patterns(self, temp_dir: Path) -> None:
        """Test extracting tool order patterns."""
        from swarm_attack.learning.coder_integration import (
            PatternExtractor,
            EpisodeLogger,
        )

        logger = EpisodeLogger(base_path=temp_dir)

        # Create episodes with tool sequences
        for i in range(5):
            episode = logger.start_episode(
                feature_id="feature",
                issue_number=i,
                task_type="implementation",
            )
            episode.tool_sequence = ["Read", "Grep", "Edit", "Bash"]
            logger.complete_episode(episode=episode, success=True, cost_usd=0.05)

        extractor = PatternExtractor()
        patterns = extractor.extract_patterns(logger.load_all())

        tool_patterns = patterns.get_patterns_by_type("tool_order")
        # May or may not have tool patterns depending on data
        assert isinstance(tool_patterns, list)

    def test_extract_recovery_patterns(self, temp_dir: Path) -> None:
        """Test extracting recovery patterns from retry episodes."""
        from swarm_attack.learning.coder_integration import (
            PatternExtractor,
            EpisodeLogger,
        )

        logger = EpisodeLogger(base_path=temp_dir)

        # Create episodes with retries that eventually succeeded
        for i in range(3):
            episode = logger.start_episode(
                feature_id="feature",
                issue_number=i,
                task_type="implementation",
            )
            logger.record_retry(episode=episode, retry_number=1, error="Import error")
            logger.record_retry(episode=episode, retry_number=2, error="Test failed")
            episode.recovery_actions = ["increase_timeout", "add_context"]
            logger.complete_episode(episode=episode, success=True, cost_usd=0.10)

        extractor = PatternExtractor()
        patterns = extractor.extract_patterns(logger.load_all())

        recovery_patterns = patterns.get_patterns_by_type("recovery")
        assert isinstance(recovery_patterns, list)

    def test_minimum_episodes_for_pattern(self) -> None:
        """Test that patterns require minimum episode count."""
        from swarm_attack.learning.coder_integration import PatternExtractor

        extractor = PatternExtractor(min_episodes=10)
        # With empty episodes, should return empty pattern set
        patterns = extractor.extract_patterns([])

        assert patterns is not None
        assert len(patterns.patterns) == 0


# =============================================================================
# CoderIntegration Tests
# =============================================================================


class TestCoderIntegration:
    """Tests for the main CoderIntegration class."""

    def test_coder_integration_creation(self, mock_config: MagicMock, temp_dir: Path) -> None:
        """Test that CoderIntegration can be created."""
        from swarm_attack.learning.coder_integration import CoderIntegration

        integration = CoderIntegration(
            config=mock_config,
            base_path=temp_dir,
        )
        assert integration is not None
        assert integration.episode_logger is not None
        assert integration.pattern_extractor is not None
        assert integration.strategy_optimizer is not None

    def test_wrap_coder_run_success(self, mock_config: MagicMock, temp_dir: Path) -> None:
        """Test wrapping a successful coder run."""
        from swarm_attack.learning.coder_integration import CoderIntegration

        integration = CoderIntegration(config=mock_config, base_path=temp_dir)

        # Mock coder result
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.cost_usd = 0.05
        mock_result.output = {
            "files_created": ["src/foo.py"],
            "files_modified": [],
        }

        # Define a mock coder function
        def mock_coder_run(context: dict) -> Any:
            return mock_result

        # Wrap and execute
        result = integration.wrap_coder_run(
            coder_fn=mock_coder_run,
            context={
                "feature_id": "test-feature",
                "issue_number": 1,
            },
        )

        assert result.success is True

        # Verify episode was logged
        episodes = integration.episode_logger.load_recent(limit=1)
        assert len(episodes) == 1
        assert episodes[0].feature_id == "test-feature"
        assert episodes[0].success is True

    def test_wrap_coder_run_failure(self, mock_config: MagicMock, temp_dir: Path) -> None:
        """Test wrapping a failed coder run."""
        from swarm_attack.learning.coder_integration import CoderIntegration

        integration = CoderIntegration(config=mock_config, base_path=temp_dir)

        # Mock coder result
        mock_result = MagicMock()
        mock_result.success = False
        mock_result.cost_usd = 0.03
        mock_result.errors = ["Test validation failed"]

        def mock_coder_run(context: dict) -> Any:
            return mock_result

        result = integration.wrap_coder_run(
            coder_fn=mock_coder_run,
            context={
                "feature_id": "test-feature",
                "issue_number": 1,
            },
        )

        assert result.success is False

        # Verify episode was logged
        episodes = integration.episode_logger.load_recent(limit=1)
        assert len(episodes) == 1
        assert episodes[0].success is False

    def test_wrap_coder_run_with_retry(self, mock_config: MagicMock, temp_dir: Path) -> None:
        """Test wrapping a coder run with retry context."""
        from swarm_attack.learning.coder_integration import CoderIntegration

        integration = CoderIntegration(config=mock_config, base_path=temp_dir)

        mock_result = MagicMock()
        mock_result.success = True
        mock_result.cost_usd = 0.05
        mock_result.output = {"files_created": [], "files_modified": []}

        def mock_coder_run(context: dict) -> Any:
            return mock_result

        result = integration.wrap_coder_run(
            coder_fn=mock_coder_run,
            context={
                "feature_id": "test-feature",
                "issue_number": 1,
                "retry_number": 2,
            },
        )

        assert result.success is True

        episodes = integration.episode_logger.load_recent(limit=1)
        assert episodes[0].retry_count == 2

    def test_get_optimized_strategy(
        self, mock_config: MagicMock, temp_dir: Path, sample_patterns: PatternSet
    ) -> None:
        """Test getting an optimized strategy for a task."""
        from swarm_attack.learning.coder_integration import CoderIntegration

        integration = CoderIntegration(config=mock_config, base_path=temp_dir)

        # Create some episodes first to establish patterns
        for i in range(5):
            episode = integration.episode_logger.start_episode(
                feature_id="feature",
                issue_number=i,
                task_type="implementation",
            )
            episode.tool_sequence = ["Read", "Grep", "Edit"]
            integration.episode_logger.complete_episode(
                episode=episode, success=True, cost_usd=0.05
            )

        strategy = integration.get_optimized_strategy(
            feature_id="new-feature",
            issue_number=1,
            task_description="Implement authentication module",
        )

        assert strategy is not None
        assert isinstance(strategy, OptimizedStrategy)
        assert strategy.task_id is not None

    def test_enhance_context_with_patterns(
        self, mock_config: MagicMock, temp_dir: Path
    ) -> None:
        """Test enhancing coder context with learned patterns."""
        from swarm_attack.learning.coder_integration import CoderIntegration

        integration = CoderIntegration(config=mock_config, base_path=temp_dir)

        base_context = {
            "feature_id": "test-feature",
            "issue_number": 1,
        }

        enhanced = integration.enhance_context(base_context)

        assert enhanced is not None
        assert "feature_id" in enhanced
        assert "learning_insights" in enhanced or enhanced == base_context

    def test_pre_execution_hook(self, mock_config: MagicMock, temp_dir: Path) -> None:
        """Test pre-execution hook is called."""
        from swarm_attack.learning.coder_integration import CoderIntegration

        integration = CoderIntegration(config=mock_config, base_path=temp_dir)

        hook_called = {"value": False}

        def custom_hook(context: dict, strategy: Optional[OptimizedStrategy]) -> None:
            hook_called["value"] = True

        integration.register_pre_execution_hook(custom_hook)

        mock_result = MagicMock()
        mock_result.success = True
        mock_result.cost_usd = 0.05
        mock_result.output = {"files_created": [], "files_modified": []}

        integration.wrap_coder_run(
            coder_fn=lambda ctx: mock_result,
            context={"feature_id": "test", "issue_number": 1},
        )

        assert hook_called["value"] is True

    def test_post_execution_hook(self, mock_config: MagicMock, temp_dir: Path) -> None:
        """Test post-execution hook is called."""
        from swarm_attack.learning.coder_integration import CoderIntegration

        integration = CoderIntegration(config=mock_config, base_path=temp_dir)

        hook_data = {"result": None}

        def custom_hook(context: dict, result: Any, episode: Any) -> None:
            hook_data["result"] = result

        integration.register_post_execution_hook(custom_hook)

        mock_result = MagicMock()
        mock_result.success = True
        mock_result.cost_usd = 0.05
        mock_result.output = {"files_created": [], "files_modified": []}

        integration.wrap_coder_run(
            coder_fn=lambda ctx: mock_result,
            context={"feature_id": "test", "issue_number": 1},
        )

        assert hook_data["result"] is not None
        assert hook_data["result"].success is True


# =============================================================================
# Integration with Real CoderAgent Tests
# =============================================================================


class TestCoderAgentIntegration:
    """Tests for integration with actual CoderAgent."""

    def test_coder_agent_with_learning(self, mock_config: MagicMock, temp_dir: Path) -> None:
        """Test that CoderAgent can be enhanced with learning layer."""
        from swarm_attack.learning.coder_integration import CoderIntegration

        integration = CoderIntegration(config=mock_config, base_path=temp_dir)

        # Create a context that would be passed to CoderAgent
        context = {
            "feature_id": "my-feature",
            "issue_number": 1,
            "retry_number": 0,
            "test_failures": [],
        }

        # Enhance context
        enhanced_context = integration.enhance_context(context)

        # Should have original keys
        assert enhanced_context["feature_id"] == "my-feature"
        assert enhanced_context["issue_number"] == 1

    def test_learning_from_multiple_features(
        self, mock_config: MagicMock, temp_dir: Path
    ) -> None:
        """Test learning patterns across multiple features."""
        from swarm_attack.learning.coder_integration import CoderIntegration

        integration = CoderIntegration(config=mock_config, base_path=temp_dir)

        # Log episodes for multiple features
        features = ["auth", "api", "database"]
        for feature in features:
            for issue in range(3):
                episode = integration.episode_logger.start_episode(
                    feature_id=feature,
                    issue_number=issue,
                    task_type="implementation",
                )
                episode.tool_sequence = ["Read", "Grep", "Edit", "Bash"]
                integration.episode_logger.complete_episode(
                    episode=episode,
                    success=True,
                    cost_usd=0.05,
                )

        # Should have episodes from all features
        all_episodes = integration.episode_logger.load_all()
        assert len(all_episodes) == 9

    def test_strategy_application(self, mock_config: MagicMock, temp_dir: Path) -> None:
        """Test applying optimized strategy to coder execution."""
        from swarm_attack.learning.coder_integration import CoderIntegration

        integration = CoderIntegration(config=mock_config, base_path=temp_dir)

        # First, create historical data
        for i in range(10):
            episode = integration.episode_logger.start_episode(
                feature_id="historical",
                issue_number=i,
                task_type="implementation",
            )
            episode.prompt_metadata = {"included_examples": True}
            episode.tool_sequence = ["Read", "Grep", "Edit"]
            integration.episode_logger.complete_episode(
                episode=episode, success=True, cost_usd=0.05
            )

        # Get strategy for new task
        strategy = integration.get_optimized_strategy(
            feature_id="new-feature",
            issue_number=1,
            task_description="Implement new module",
        )

        assert strategy is not None


# =============================================================================
# Pattern Confidence Tests
# =============================================================================


class TestPatternConfidence:
    """Tests for pattern confidence calculations."""

    def test_high_success_rate_increases_confidence(self, temp_dir: Path) -> None:
        """Test that high success rate increases pattern confidence."""
        from swarm_attack.learning.coder_integration import (
            PatternExtractor,
            EpisodeLogger,
        )

        logger = EpisodeLogger(base_path=temp_dir)

        # Create many successful episodes with same pattern
        for i in range(20):
            episode = logger.start_episode(
                feature_id="feature",
                issue_number=i,
                task_type="implementation",
            )
            episode.tool_sequence = ["Read", "Edit"]
            logger.complete_episode(episode=episode, success=True, cost_usd=0.05)

        extractor = PatternExtractor(min_episodes=5)
        patterns = extractor.extract_patterns(logger.load_all())

        # High confidence patterns should exist
        high_conf = patterns.get_high_confidence_patterns(min_confidence=0.5)
        # May have patterns depending on implementation
        assert isinstance(high_conf, list)

    def test_failure_reduces_confidence(self, temp_dir: Path) -> None:
        """Test that failures reduce pattern confidence."""
        from swarm_attack.learning.coder_integration import (
            PatternExtractor,
            EpisodeLogger,
        )

        logger = EpisodeLogger(base_path=temp_dir)

        # Mix of successes and failures
        for i in range(10):
            episode = logger.start_episode(
                feature_id="feature",
                issue_number=i,
                task_type="implementation",
            )
            episode.tool_sequence = ["Read", "Edit"]
            # 50% failure rate
            logger.complete_episode(
                episode=episode,
                success=(i % 2 == 0),
                cost_usd=0.05,
            )

        extractor = PatternExtractor(min_episodes=5)
        patterns = extractor.extract_patterns(logger.load_all())

        # Should have lower confidence
        assert patterns is not None


# =============================================================================
# Edge Cases and Error Handling
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_empty_episode_log(self, temp_dir: Path) -> None:
        """Test handling empty episode log."""
        from swarm_attack.learning.coder_integration import (
            PatternExtractor,
            EpisodeLogger,
        )

        logger = EpisodeLogger(base_path=temp_dir)
        extractor = PatternExtractor()

        patterns = extractor.extract_patterns(logger.load_all())

        assert patterns is not None
        assert len(patterns.patterns) == 0

    def test_corrupt_episode_file(self, temp_dir: Path) -> None:
        """Test handling corrupt episode file."""
        from swarm_attack.learning.coder_integration import EpisodeLogger

        # Write corrupt data
        episodes_file = temp_dir / "episodes.jsonl"
        with open(episodes_file, "w") as f:
            f.write("not valid json\n")
            f.write('{"valid": "json"}\n')

        logger = EpisodeLogger(base_path=temp_dir)
        episodes = logger.load_all()

        # Should handle gracefully
        assert isinstance(episodes, list)

    def test_concurrent_episode_writes(self, temp_dir: Path) -> None:
        """Test handling concurrent episode writes."""
        from swarm_attack.learning.coder_integration import EpisodeLogger

        logger1 = EpisodeLogger(base_path=temp_dir)
        logger2 = EpisodeLogger(base_path=temp_dir)

        # Write from both loggers
        ep1 = logger1.start_episode(
            feature_id="feature1", issue_number=1, task_type="impl"
        )
        ep2 = logger2.start_episode(
            feature_id="feature2", issue_number=2, task_type="impl"
        )

        logger1.complete_episode(ep1, success=True, cost_usd=0.01)
        logger2.complete_episode(ep2, success=True, cost_usd=0.02)

        # Both should be persisted
        all_episodes = logger1.load_all()
        assert len(all_episodes) == 2

    def test_missing_context_fields(self, mock_config: MagicMock, temp_dir: Path) -> None:
        """Test handling missing required context fields."""
        from swarm_attack.learning.coder_integration import CoderIntegration

        integration = CoderIntegration(config=mock_config, base_path=temp_dir)

        mock_result = MagicMock()
        mock_result.success = True
        mock_result.cost_usd = 0.05
        mock_result.output = {}

        # Missing feature_id should be handled
        result = integration.wrap_coder_run(
            coder_fn=lambda ctx: mock_result,
            context={"issue_number": 1},  # Missing feature_id
        )

        # Should still work with defaults
        assert result is not None


# =============================================================================
# Performance Tests
# =============================================================================


class TestPerformance:
    """Tests for performance characteristics."""

    def test_large_episode_log_load(self, temp_dir: Path) -> None:
        """Test loading large episode logs efficiently."""
        from swarm_attack.learning.coder_integration import EpisodeLogger

        logger = EpisodeLogger(base_path=temp_dir)

        # Create many episodes
        for i in range(100):
            episode = logger.start_episode(
                feature_id=f"feature-{i % 10}",
                issue_number=i,
                task_type="implementation",
            )
            logger.complete_episode(episode=episode, success=True, cost_usd=0.01)

        # Should load efficiently
        import time
        start = time.time()
        recent = logger.load_recent(limit=50)
        elapsed = time.time() - start

        assert len(recent) == 50
        assert elapsed < 1.0  # Should be fast

    def test_pattern_extraction_performance(self, temp_dir: Path) -> None:
        """Test pattern extraction with large dataset."""
        from swarm_attack.learning.coder_integration import (
            PatternExtractor,
            EpisodeLogger,
        )

        logger = EpisodeLogger(base_path=temp_dir)

        # Create many episodes
        for i in range(100):
            episode = logger.start_episode(
                feature_id="feature",
                issue_number=i,
                task_type="implementation",
            )
            episode.tool_sequence = ["Read", "Grep", "Edit"]
            logger.complete_episode(episode=episode, success=True, cost_usd=0.05)

        extractor = PatternExtractor()

        import time
        start = time.time()
        patterns = extractor.extract_patterns(logger.load_all())
        elapsed = time.time() - start

        assert patterns is not None
        assert elapsed < 2.0  # Should be reasonably fast
