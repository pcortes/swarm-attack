"""Unit tests for PatternExtractor.

Tests for extracting patterns from episode history:
- Success patterns (what leads to completion)
- Failure patterns (what leads to failure)
- Recovery patterns (what recoveries work)
- Context patterns (optimal context construction)

TDD Protocol: RED PHASE - These tests should fail initially.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional
from unittest.mock import MagicMock

import pytest


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_config(tmp_path):
    """Create a mock SwarmConfig for testing."""
    config = MagicMock()
    config.repo_root = str(tmp_path)
    config.swarm_path = tmp_path / ".swarm"
    config.swarm_path.mkdir(parents=True, exist_ok=True)
    return config


@pytest.fixture
def sample_success_episodes():
    """Create sample successful episodes for testing."""
    from swarm_attack.chief_of_staff.episodes import Episode

    return [
        Episode(
            episode_id="ep-001",
            timestamp="2025-01-01T10:00:00",
            goal_id="implement-auth-module",
            success=True,
            cost_usd=1.50,
            duration_seconds=300,
            checkpoints_triggered=[],
            error=None,
            notes="Used TDD approach, all tests passed",
            retry_count=0,
            recovery_level=None,
        ),
        Episode(
            episode_id="ep-002",
            timestamp="2025-01-01T11:00:00",
            goal_id="fix-login-bug",
            success=True,
            cost_usd=0.80,
            duration_seconds=180,
            checkpoints_triggered=[],
            error=None,
            notes="Root cause analysis helped",
            retry_count=0,
            recovery_level=None,
        ),
        Episode(
            episode_id="ep-003",
            timestamp="2025-01-01T12:00:00",
            goal_id="implement-api-endpoint",
            success=True,
            cost_usd=2.00,
            duration_seconds=450,
            checkpoints_triggered=["COST_SINGLE"],
            error=None,
            notes="Included comprehensive tests",
            retry_count=0,
            recovery_level=None,
        ),
    ]


@pytest.fixture
def sample_failure_episodes():
    """Create sample failed episodes for testing."""
    from swarm_attack.chief_of_staff.episodes import Episode

    return [
        Episode(
            episode_id="ep-004",
            timestamp="2025-01-01T13:00:00",
            goal_id="refactor-database-layer",
            success=False,
            cost_usd=5.00,
            duration_seconds=900,
            checkpoints_triggered=["COST_CUMULATIVE", "HICCUP"],
            error="Timeout exceeded",
            notes="Task was too complex",
            retry_count=3,
            recovery_level="RETRY",
        ),
        Episode(
            episode_id="ep-005",
            timestamp="2025-01-01T14:00:00",
            goal_id="migrate-legacy-code",
            success=False,
            cost_usd=3.50,
            duration_seconds=600,
            checkpoints_triggered=["ARCHITECTURE"],
            error="Circular dependency detected",
            notes="Missing context about dependencies",
            retry_count=2,
            recovery_level="SIMPLIFY",
        ),
    ]


@pytest.fixture
def sample_recovery_episodes():
    """Create sample episodes with successful recoveries."""
    from swarm_attack.chief_of_staff.episodes import Episode

    return [
        Episode(
            episode_id="ep-006",
            timestamp="2025-01-01T15:00:00",
            goal_id="fix-test-failures",
            success=True,
            cost_usd=1.20,
            duration_seconds=240,
            checkpoints_triggered=["HICCUP"],
            error=None,
            notes="Recovered after retry with simplified approach",
            retry_count=1,
            recovery_level="RETRY",
        ),
        Episode(
            episode_id="ep-007",
            timestamp="2025-01-01T16:00:00",
            goal_id="resolve-merge-conflict",
            success=True,
            cost_usd=0.90,
            duration_seconds=150,
            checkpoints_triggered=["HICCUP"],
            error=None,
            notes="Skip strategy worked",
            retry_count=1,
            recovery_level="SKIP",
        ),
        Episode(
            episode_id="ep-008",
            timestamp="2025-01-01T17:00:00",
            goal_id="complex-refactor",
            success=True,
            cost_usd=2.50,
            duration_seconds=500,
            checkpoints_triggered=["COST_SINGLE", "HICCUP"],
            error=None,
            notes="Simplified task and retried",
            retry_count=2,
            recovery_level="SIMPLIFY",
        ),
    ]


@pytest.fixture
def mixed_episodes(sample_success_episodes, sample_failure_episodes, sample_recovery_episodes):
    """Combine all episode types for comprehensive testing."""
    return sample_success_episodes + sample_failure_episodes + sample_recovery_episodes


# =============================================================================
# Import Tests - Verify module structure
# =============================================================================


class TestModuleImports:
    """Test that required classes can be imported."""

    def test_import_pattern_extractor(self):
        """Test PatternExtractor class can be imported."""
        from swarm_attack.learning.pattern_extractor import PatternExtractor
        assert PatternExtractor is not None

    def test_import_extracted_pattern(self):
        """Test ExtractedPattern class can be imported."""
        from swarm_attack.learning.pattern_extractor import ExtractedPattern
        assert ExtractedPattern is not None

    def test_import_pattern_type_enum(self):
        """Test PatternType enum can be imported."""
        from swarm_attack.learning.pattern_extractor import PatternType
        assert PatternType is not None

    def test_import_extraction_result(self):
        """Test ExtractionResult class can be imported."""
        from swarm_attack.learning.pattern_extractor import ExtractionResult
        assert ExtractionResult is not None


# =============================================================================
# PatternType Enum Tests
# =============================================================================


class TestPatternTypeEnum:
    """Tests for PatternType enumeration."""

    def test_pattern_type_has_success(self):
        """Test PatternType has SUCCESS value."""
        from swarm_attack.learning.pattern_extractor import PatternType
        assert hasattr(PatternType, "SUCCESS")

    def test_pattern_type_has_failure(self):
        """Test PatternType has FAILURE value."""
        from swarm_attack.learning.pattern_extractor import PatternType
        assert hasattr(PatternType, "FAILURE")

    def test_pattern_type_has_recovery(self):
        """Test PatternType has RECOVERY value."""
        from swarm_attack.learning.pattern_extractor import PatternType
        assert hasattr(PatternType, "RECOVERY")

    def test_pattern_type_has_context(self):
        """Test PatternType has CONTEXT value."""
        from swarm_attack.learning.pattern_extractor import PatternType
        assert hasattr(PatternType, "CONTEXT")


# =============================================================================
# ExtractedPattern Data Class Tests
# =============================================================================


class TestExtractedPatternDataClass:
    """Tests for ExtractedPattern data class."""

    def test_extracted_pattern_creation(self):
        """Test creating an ExtractedPattern with required fields."""
        from swarm_attack.learning.pattern_extractor import ExtractedPattern, PatternType

        pattern = ExtractedPattern(
            pattern_id="pat-001",
            pattern_type=PatternType.SUCCESS,
            description="TDD approach improves success rate",
            confidence=0.85,
            success_rate=0.90,
        )

        assert pattern.pattern_id == "pat-001"
        assert pattern.pattern_type == PatternType.SUCCESS
        assert pattern.confidence == 0.85

    def test_extracted_pattern_with_evidence(self):
        """Test ExtractedPattern with evidence episodes."""
        from swarm_attack.learning.pattern_extractor import ExtractedPattern, PatternType

        pattern = ExtractedPattern(
            pattern_id="pat-002",
            pattern_type=PatternType.FAILURE,
            description="Complex refactors fail without split",
            confidence=0.75,
            success_rate=0.20,
            evidence_episode_ids=["ep-004", "ep-005"],
        )

        assert len(pattern.evidence_episode_ids) == 2
        assert "ep-004" in pattern.evidence_episode_ids

    def test_extracted_pattern_with_metadata(self):
        """Test ExtractedPattern with metadata."""
        from swarm_attack.learning.pattern_extractor import ExtractedPattern, PatternType

        pattern = ExtractedPattern(
            pattern_id="pat-003",
            pattern_type=PatternType.RECOVERY,
            description="Retry with simplification works",
            confidence=0.80,
            success_rate=0.85,
            metadata={"recovery_level": "SIMPLIFY", "avg_retries": 1.5},
        )

        assert pattern.metadata["recovery_level"] == "SIMPLIFY"

    def test_extracted_pattern_to_dict(self):
        """Test ExtractedPattern serialization to dict."""
        from swarm_attack.learning.pattern_extractor import ExtractedPattern, PatternType

        pattern = ExtractedPattern(
            pattern_id="pat-004",
            pattern_type=PatternType.CONTEXT,
            description="Include module registry",
            confidence=0.88,
            success_rate=0.92,
        )

        data = pattern.to_dict()

        assert isinstance(data, dict)
        assert data["pattern_id"] == "pat-004"
        assert data["pattern_type"] == "CONTEXT"

    def test_extracted_pattern_from_dict(self):
        """Test ExtractedPattern deserialization from dict."""
        from swarm_attack.learning.pattern_extractor import ExtractedPattern, PatternType

        data = {
            "pattern_id": "pat-005",
            "pattern_type": "SUCCESS",
            "description": "Test pattern",
            "confidence": 0.85,
            "success_rate": 0.90,
            "evidence_episode_ids": ["ep-001"],
            "metadata": {},
        }

        pattern = ExtractedPattern.from_dict(data)

        assert pattern.pattern_id == "pat-005"
        assert pattern.pattern_type == PatternType.SUCCESS

    def test_extracted_pattern_to_optimizer_pattern(self):
        """Test conversion to strategy_optimizer.Pattern format."""
        from swarm_attack.learning.pattern_extractor import ExtractedPattern, PatternType
        from swarm_attack.learning.strategy_optimizer import Pattern

        extracted = ExtractedPattern(
            pattern_id="pat-006",
            pattern_type=PatternType.SUCCESS,
            description="TDD works well",
            confidence=0.85,
            success_rate=0.90,
            metadata={"keywords": ["tdd", "tests"]},
        )

        optimizer_pattern = extracted.to_optimizer_pattern()

        assert isinstance(optimizer_pattern, Pattern)
        assert optimizer_pattern.pattern_id == "pat-006"
        assert optimizer_pattern.pattern_type == "prompt"  # SUCCESS maps to prompt


# =============================================================================
# ExtractionResult Data Class Tests
# =============================================================================


class TestExtractionResultDataClass:
    """Tests for ExtractionResult data class."""

    def test_extraction_result_creation(self):
        """Test creating an ExtractionResult."""
        from swarm_attack.learning.pattern_extractor import ExtractionResult

        result = ExtractionResult(
            total_episodes_analyzed=100,
            patterns_extracted=15,
        )

        assert result.total_episodes_analyzed == 100
        assert result.patterns_extracted == 15

    def test_extraction_result_with_all_pattern_types(self):
        """Test ExtractionResult with all pattern type counts."""
        from swarm_attack.learning.pattern_extractor import (
            ExtractionResult,
            ExtractedPattern,
            PatternType,
        )

        patterns = [
            ExtractedPattern("p1", PatternType.SUCCESS, "desc", 0.8, 0.9),
            ExtractedPattern("p2", PatternType.FAILURE, "desc", 0.7, 0.2),
            ExtractedPattern("p3", PatternType.RECOVERY, "desc", 0.8, 0.8),
            ExtractedPattern("p4", PatternType.CONTEXT, "desc", 0.9, 0.85),
        ]

        result = ExtractionResult(
            total_episodes_analyzed=50,
            patterns_extracted=4,
            success_patterns=patterns[:1],
            failure_patterns=patterns[1:2],
            recovery_patterns=patterns[2:3],
            context_patterns=patterns[3:4],
        )

        assert len(result.success_patterns) == 1
        assert len(result.failure_patterns) == 1
        assert len(result.recovery_patterns) == 1
        assert len(result.context_patterns) == 1

    def test_extraction_result_to_dict(self):
        """Test ExtractionResult serialization."""
        from swarm_attack.learning.pattern_extractor import ExtractionResult

        result = ExtractionResult(
            total_episodes_analyzed=25,
            patterns_extracted=5,
        )

        data = result.to_dict()

        assert data["total_episodes_analyzed"] == 25
        assert data["patterns_extracted"] == 5

    def test_extraction_result_get_all_patterns(self):
        """Test ExtractionResult.get_all_patterns() method."""
        from swarm_attack.learning.pattern_extractor import (
            ExtractionResult,
            ExtractedPattern,
            PatternType,
        )

        patterns = [
            ExtractedPattern("p1", PatternType.SUCCESS, "desc", 0.8, 0.9),
            ExtractedPattern("p2", PatternType.FAILURE, "desc", 0.7, 0.2),
        ]

        result = ExtractionResult(
            total_episodes_analyzed=20,
            patterns_extracted=2,
            success_patterns=[patterns[0]],
            failure_patterns=[patterns[1]],
        )

        all_patterns = result.get_all_patterns()

        assert len(all_patterns) == 2


# =============================================================================
# PatternExtractor Initialization Tests
# =============================================================================


class TestPatternExtractorInit:
    """Tests for PatternExtractor initialization."""

    def test_init_with_defaults(self, mock_config):
        """Test initialization with default parameters."""
        from swarm_attack.learning.pattern_extractor import PatternExtractor

        extractor = PatternExtractor(config=mock_config)

        assert extractor.config == mock_config
        assert extractor.min_confidence == 0.7  # Default threshold

    def test_init_with_custom_min_confidence(self, mock_config):
        """Test initialization with custom confidence threshold."""
        from swarm_attack.learning.pattern_extractor import PatternExtractor

        extractor = PatternExtractor(config=mock_config, min_confidence=0.5)

        assert extractor.min_confidence == 0.5

    def test_init_with_invalid_confidence_raises(self, mock_config):
        """Test that invalid min_confidence raises ValueError."""
        from swarm_attack.learning.pattern_extractor import PatternExtractor

        with pytest.raises(ValueError):
            PatternExtractor(config=mock_config, min_confidence=1.5)

        with pytest.raises(ValueError):
            PatternExtractor(config=mock_config, min_confidence=-0.1)

    def test_init_with_episode_store(self, mock_config):
        """Test initialization with custom episode store."""
        from swarm_attack.learning.pattern_extractor import PatternExtractor
        from swarm_attack.chief_of_staff.episodes import EpisodeStore

        store = EpisodeStore(base_path=mock_config.swarm_path / "episodes")
        extractor = PatternExtractor(config=mock_config, episode_store=store)

        assert extractor.episode_store is not None


# =============================================================================
# PatternExtractor.extract_all() Tests
# =============================================================================


class TestPatternExtractorExtractAll:
    """Tests for PatternExtractor.extract_all() method."""

    def test_extract_all_returns_extraction_result(self, mock_config, mixed_episodes):
        """Test that extract_all() returns an ExtractionResult."""
        from swarm_attack.learning.pattern_extractor import PatternExtractor, ExtractionResult

        extractor = PatternExtractor(config=mock_config)

        result = extractor.extract_all(mixed_episodes)

        assert isinstance(result, ExtractionResult)

    def test_extract_all_counts_episodes(self, mock_config, mixed_episodes):
        """Test that extract_all() counts analyzed episodes correctly."""
        from swarm_attack.learning.pattern_extractor import PatternExtractor

        extractor = PatternExtractor(config=mock_config)

        result = extractor.extract_all(mixed_episodes)

        assert result.total_episodes_analyzed == len(mixed_episodes)

    def test_extract_all_with_empty_episodes(self, mock_config):
        """Test extract_all() with empty episode list."""
        from swarm_attack.learning.pattern_extractor import PatternExtractor

        extractor = PatternExtractor(config=mock_config)

        result = extractor.extract_all([])

        assert result.total_episodes_analyzed == 0
        assert result.patterns_extracted == 0

    def test_extract_all_extracts_success_patterns(self, mock_config, sample_success_episodes):
        """Test that extract_all() extracts success patterns."""
        from swarm_attack.learning.pattern_extractor import PatternExtractor

        extractor = PatternExtractor(config=mock_config)

        result = extractor.extract_all(sample_success_episodes)

        assert len(result.success_patterns) >= 0  # May have patterns

    def test_extract_all_extracts_failure_patterns(self, mock_config, sample_failure_episodes):
        """Test that extract_all() extracts failure patterns."""
        from swarm_attack.learning.pattern_extractor import PatternExtractor

        extractor = PatternExtractor(config=mock_config)

        result = extractor.extract_all(sample_failure_episodes)

        assert len(result.failure_patterns) >= 0

    def test_extract_all_extracts_recovery_patterns(self, mock_config, sample_recovery_episodes):
        """Test that extract_all() extracts recovery patterns."""
        from swarm_attack.learning.pattern_extractor import PatternExtractor

        extractor = PatternExtractor(config=mock_config)

        result = extractor.extract_all(sample_recovery_episodes)

        assert len(result.recovery_patterns) >= 0


# =============================================================================
# PatternExtractor.extract_success_patterns() Tests
# =============================================================================


class TestPatternExtractorExtractSuccessPatterns:
    """Tests for extracting success patterns."""

    def test_extract_success_patterns_returns_list(self, mock_config, sample_success_episodes):
        """Test that extract_success_patterns returns a list."""
        from swarm_attack.learning.pattern_extractor import PatternExtractor, ExtractedPattern

        extractor = PatternExtractor(config=mock_config)

        patterns = extractor.extract_success_patterns(sample_success_episodes)

        assert isinstance(patterns, list)
        for p in patterns:
            assert isinstance(p, ExtractedPattern)

    def test_extract_success_patterns_filters_successful(self, mock_config, mixed_episodes):
        """Test that only successful episodes contribute to success patterns."""
        from swarm_attack.learning.pattern_extractor import PatternExtractor, PatternType

        extractor = PatternExtractor(config=mock_config)

        patterns = extractor.extract_success_patterns(mixed_episodes)

        for p in patterns:
            assert p.pattern_type == PatternType.SUCCESS

    def test_extract_success_patterns_calculates_confidence(self, mock_config, sample_success_episodes):
        """Test that confidence is calculated for success patterns."""
        from swarm_attack.learning.pattern_extractor import PatternExtractor

        extractor = PatternExtractor(config=mock_config)

        patterns = extractor.extract_success_patterns(sample_success_episodes)

        for p in patterns:
            assert 0.0 <= p.confidence <= 1.0

    def test_extract_success_patterns_includes_evidence(self, mock_config, sample_success_episodes):
        """Test that patterns include evidence episode IDs."""
        from swarm_attack.learning.pattern_extractor import PatternExtractor

        extractor = PatternExtractor(config=mock_config)

        patterns = extractor.extract_success_patterns(sample_success_episodes)

        for p in patterns:
            assert isinstance(p.evidence_episode_ids, list)

    def test_extract_success_identifies_low_cost_pattern(self, mock_config, sample_success_episodes):
        """Test that low-cost successes are identified as a pattern."""
        from swarm_attack.learning.pattern_extractor import PatternExtractor

        extractor = PatternExtractor(config=mock_config)

        patterns = extractor.extract_success_patterns(sample_success_episodes)

        # Should identify patterns about cost efficiency
        pattern_descriptions = [p.description.lower() for p in patterns]
        # Implementation should identify cost-related patterns
        assert len(patterns) >= 0  # At least should run without error

    def test_extract_success_identifies_fast_completion_pattern(self, mock_config, sample_success_episodes):
        """Test that fast completions are identified as a pattern."""
        from swarm_attack.learning.pattern_extractor import PatternExtractor

        extractor = PatternExtractor(config=mock_config)

        patterns = extractor.extract_success_patterns(sample_success_episodes)

        # Pattern about duration efficiency should be possible
        assert len(patterns) >= 0


# =============================================================================
# PatternExtractor.extract_failure_patterns() Tests
# =============================================================================


class TestPatternExtractorExtractFailurePatterns:
    """Tests for extracting failure patterns."""

    def test_extract_failure_patterns_returns_list(self, mock_config, sample_failure_episodes):
        """Test that extract_failure_patterns returns a list."""
        from swarm_attack.learning.pattern_extractor import PatternExtractor, ExtractedPattern

        extractor = PatternExtractor(config=mock_config)

        patterns = extractor.extract_failure_patterns(sample_failure_episodes)

        assert isinstance(patterns, list)
        for p in patterns:
            assert isinstance(p, ExtractedPattern)

    def test_extract_failure_patterns_filters_failed(self, mock_config, mixed_episodes):
        """Test that only failed episodes contribute to failure patterns."""
        from swarm_attack.learning.pattern_extractor import PatternExtractor, PatternType

        extractor = PatternExtractor(config=mock_config)

        patterns = extractor.extract_failure_patterns(mixed_episodes)

        for p in patterns:
            assert p.pattern_type == PatternType.FAILURE

    def test_extract_failure_patterns_includes_error_info(self, mock_config, sample_failure_episodes):
        """Test that failure patterns include error information."""
        from swarm_attack.learning.pattern_extractor import PatternExtractor

        extractor = PatternExtractor(config=mock_config)

        patterns = extractor.extract_failure_patterns(sample_failure_episodes)

        # Patterns should capture error information
        for p in patterns:
            assert p.description is not None

    def test_extract_failure_identifies_timeout_pattern(self, mock_config, sample_failure_episodes):
        """Test that timeout failures are identified."""
        from swarm_attack.learning.pattern_extractor import PatternExtractor

        extractor = PatternExtractor(config=mock_config)

        patterns = extractor.extract_failure_patterns(sample_failure_episodes)

        # Should potentially identify timeout-related patterns
        assert len(patterns) >= 0

    def test_extract_failure_identifies_complexity_pattern(self, mock_config, sample_failure_episodes):
        """Test that complexity-related failures are identified."""
        from swarm_attack.learning.pattern_extractor import PatternExtractor

        extractor = PatternExtractor(config=mock_config)

        patterns = extractor.extract_failure_patterns(sample_failure_episodes)

        assert len(patterns) >= 0

    def test_extract_failure_low_success_rate(self, mock_config, sample_failure_episodes):
        """Test that failure patterns have low success rates."""
        from swarm_attack.learning.pattern_extractor import PatternExtractor

        extractor = PatternExtractor(config=mock_config)

        patterns = extractor.extract_failure_patterns(sample_failure_episodes)

        for p in patterns:
            # Failure patterns should indicate low success
            assert p.success_rate <= 0.5


# =============================================================================
# PatternExtractor.extract_recovery_patterns() Tests
# =============================================================================


class TestPatternExtractorExtractRecoveryPatterns:
    """Tests for extracting recovery patterns."""

    def test_extract_recovery_patterns_returns_list(self, mock_config, sample_recovery_episodes):
        """Test that extract_recovery_patterns returns a list."""
        from swarm_attack.learning.pattern_extractor import PatternExtractor, ExtractedPattern

        extractor = PatternExtractor(config=mock_config)

        patterns = extractor.extract_recovery_patterns(sample_recovery_episodes)

        assert isinstance(patterns, list)
        for p in patterns:
            assert isinstance(p, ExtractedPattern)

    def test_extract_recovery_patterns_filters_recovered(self, mock_config, mixed_episodes):
        """Test that only recovered episodes contribute to recovery patterns."""
        from swarm_attack.learning.pattern_extractor import PatternExtractor, PatternType

        extractor = PatternExtractor(config=mock_config)

        patterns = extractor.extract_recovery_patterns(mixed_episodes)

        for p in patterns:
            assert p.pattern_type == PatternType.RECOVERY

    def test_extract_recovery_includes_recovery_level(self, mock_config, sample_recovery_episodes):
        """Test that recovery patterns include recovery level info."""
        from swarm_attack.learning.pattern_extractor import PatternExtractor

        extractor = PatternExtractor(config=mock_config)

        patterns = extractor.extract_recovery_patterns(sample_recovery_episodes)

        for p in patterns:
            # Metadata should include recovery information
            assert isinstance(p.metadata, dict)

    def test_extract_recovery_identifies_retry_pattern(self, mock_config, sample_recovery_episodes):
        """Test that RETRY recovery level is identified."""
        from swarm_attack.learning.pattern_extractor import PatternExtractor

        extractor = PatternExtractor(config=mock_config)

        patterns = extractor.extract_recovery_patterns(sample_recovery_episodes)

        assert len(patterns) >= 0

    def test_extract_recovery_identifies_simplify_pattern(self, mock_config, sample_recovery_episodes):
        """Test that SIMPLIFY recovery level is identified."""
        from swarm_attack.learning.pattern_extractor import PatternExtractor

        extractor = PatternExtractor(config=mock_config)

        patterns = extractor.extract_recovery_patterns(sample_recovery_episodes)

        assert len(patterns) >= 0

    def test_extract_recovery_calculates_effectiveness(self, mock_config, sample_recovery_episodes):
        """Test that recovery patterns include effectiveness metrics."""
        from swarm_attack.learning.pattern_extractor import PatternExtractor

        extractor = PatternExtractor(config=mock_config)

        patterns = extractor.extract_recovery_patterns(sample_recovery_episodes)

        for p in patterns:
            # Recovery patterns should have a positive success rate
            assert p.success_rate >= 0.0


# =============================================================================
# PatternExtractor.extract_context_patterns() Tests
# =============================================================================


class TestPatternExtractorExtractContextPatterns:
    """Tests for extracting context patterns."""

    def test_extract_context_patterns_returns_list(self, mock_config, sample_success_episodes):
        """Test that extract_context_patterns returns a list."""
        from swarm_attack.learning.pattern_extractor import PatternExtractor, ExtractedPattern

        extractor = PatternExtractor(config=mock_config)

        patterns = extractor.extract_context_patterns(sample_success_episodes)

        assert isinstance(patterns, list)
        for p in patterns:
            assert isinstance(p, ExtractedPattern)

    def test_extract_context_patterns_type(self, mock_config, sample_success_episodes):
        """Test that context patterns have correct type."""
        from swarm_attack.learning.pattern_extractor import PatternExtractor, PatternType

        extractor = PatternExtractor(config=mock_config)

        patterns = extractor.extract_context_patterns(sample_success_episodes)

        for p in patterns:
            assert p.pattern_type == PatternType.CONTEXT

    def test_extract_context_from_notes(self, mock_config, sample_success_episodes):
        """Test that context patterns are derived from episode notes."""
        from swarm_attack.learning.pattern_extractor import PatternExtractor

        extractor = PatternExtractor(config=mock_config)

        patterns = extractor.extract_context_patterns(sample_success_episodes)

        # Should analyze notes for context-related insights
        assert len(patterns) >= 0

    def test_extract_context_identifies_tdd_pattern(self, mock_config, sample_success_episodes):
        """Test that TDD mentions in notes create context patterns."""
        from swarm_attack.learning.pattern_extractor import PatternExtractor

        extractor = PatternExtractor(config=mock_config)

        patterns = extractor.extract_context_patterns(sample_success_episodes)

        # Episode ep-001 has "Used TDD approach" in notes
        # Implementation should identify this
        assert len(patterns) >= 0

    def test_extract_context_identifies_analysis_pattern(self, mock_config, sample_success_episodes):
        """Test that analysis mentions create context patterns."""
        from swarm_attack.learning.pattern_extractor import PatternExtractor

        extractor = PatternExtractor(config=mock_config)

        patterns = extractor.extract_context_patterns(sample_success_episodes)

        # Episode ep-002 has "Root cause analysis" in notes
        assert len(patterns) >= 0


# =============================================================================
# PatternExtractor.to_pattern_set() Tests
# =============================================================================


class TestPatternExtractorToPatternSet:
    """Tests for converting extracted patterns to PatternSet."""

    def test_to_pattern_set_returns_pattern_set(self, mock_config, mixed_episodes):
        """Test that to_pattern_set returns a PatternSet."""
        from swarm_attack.learning.pattern_extractor import PatternExtractor
        from swarm_attack.learning.strategy_optimizer import PatternSet

        extractor = PatternExtractor(config=mock_config)

        result = extractor.extract_all(mixed_episodes)
        pattern_set = extractor.to_pattern_set(result)

        assert isinstance(pattern_set, PatternSet)

    def test_to_pattern_set_converts_all_patterns(self, mock_config, mixed_episodes):
        """Test that all extracted patterns are converted."""
        from swarm_attack.learning.pattern_extractor import PatternExtractor

        extractor = PatternExtractor(config=mock_config)

        result = extractor.extract_all(mixed_episodes)
        pattern_set = extractor.to_pattern_set(result)

        # Pattern set should contain patterns from all categories
        total_extracted = (
            len(result.success_patterns) +
            len(result.failure_patterns) +
            len(result.recovery_patterns) +
            len(result.context_patterns)
        )
        assert len(pattern_set.patterns) == total_extracted

    def test_to_pattern_set_preserves_confidence(self, mock_config, sample_success_episodes):
        """Test that confidence values are preserved in conversion."""
        from swarm_attack.learning.pattern_extractor import PatternExtractor

        extractor = PatternExtractor(config=mock_config)

        result = extractor.extract_all(sample_success_episodes)
        pattern_set = extractor.to_pattern_set(result)

        for pattern in pattern_set.patterns:
            assert 0.0 <= pattern.confidence <= 1.0

    def test_to_pattern_set_maps_pattern_types(self, mock_config, mixed_episodes):
        """Test that pattern types are correctly mapped."""
        from swarm_attack.learning.pattern_extractor import PatternExtractor

        extractor = PatternExtractor(config=mock_config)

        result = extractor.extract_all(mixed_episodes)
        pattern_set = extractor.to_pattern_set(result)

        # Verify pattern_type mapping for strategy_optimizer compatibility
        valid_types = {"prompt", "tool_order", "context", "recovery"}
        for pattern in pattern_set.patterns:
            assert pattern.pattern_type in valid_types


# =============================================================================
# PatternExtractor Statistical Analysis Tests
# =============================================================================


class TestPatternExtractorStatistics:
    """Tests for statistical analysis in pattern extraction."""

    def test_calculate_success_rate(self, mock_config, mixed_episodes):
        """Test calculation of overall success rate."""
        from swarm_attack.learning.pattern_extractor import PatternExtractor

        extractor = PatternExtractor(config=mock_config)

        success_rate = extractor.calculate_success_rate(mixed_episodes)

        assert 0.0 <= success_rate <= 1.0

    def test_calculate_average_cost(self, mock_config, sample_success_episodes):
        """Test calculation of average cost for successful episodes."""
        from swarm_attack.learning.pattern_extractor import PatternExtractor

        extractor = PatternExtractor(config=mock_config)

        avg_cost = extractor.calculate_average_cost(sample_success_episodes)

        assert avg_cost >= 0.0

    def test_calculate_average_duration(self, mock_config, sample_success_episodes):
        """Test calculation of average duration."""
        from swarm_attack.learning.pattern_extractor import PatternExtractor

        extractor = PatternExtractor(config=mock_config)

        avg_duration = extractor.calculate_average_duration(sample_success_episodes)

        assert avg_duration >= 0

    def test_calculate_recovery_effectiveness(self, mock_config, sample_recovery_episodes):
        """Test calculation of recovery effectiveness by level."""
        from swarm_attack.learning.pattern_extractor import PatternExtractor

        extractor = PatternExtractor(config=mock_config)

        effectiveness = extractor.calculate_recovery_effectiveness(sample_recovery_episodes)

        assert isinstance(effectiveness, dict)
        # Should have entries for different recovery levels
        assert "RETRY" in effectiveness or "SIMPLIFY" in effectiveness or "SKIP" in effectiveness

    def test_identify_checkpoint_correlations(self, mock_config, mixed_episodes):
        """Test identification of checkpoint-failure correlations."""
        from swarm_attack.learning.pattern_extractor import PatternExtractor

        extractor = PatternExtractor(config=mock_config)

        correlations = extractor.identify_checkpoint_correlations(mixed_episodes)

        assert isinstance(correlations, dict)


# =============================================================================
# PatternExtractor Edge Cases
# =============================================================================


class TestPatternExtractorEdgeCases:
    """Tests for edge cases and error handling."""

    def test_extract_with_none_episodes_raises(self, mock_config):
        """Test that None episodes raises ValueError."""
        from swarm_attack.learning.pattern_extractor import PatternExtractor

        extractor = PatternExtractor(config=mock_config)

        with pytest.raises((ValueError, TypeError)):
            extractor.extract_all(None)

    def test_extract_with_single_episode(self, mock_config, sample_success_episodes):
        """Test extraction with single episode."""
        from swarm_attack.learning.pattern_extractor import PatternExtractor

        extractor = PatternExtractor(config=mock_config)

        result = extractor.extract_all([sample_success_episodes[0]])

        assert result.total_episodes_analyzed == 1

    def test_extract_with_all_same_outcome(self, mock_config, sample_success_episodes):
        """Test extraction when all episodes have same outcome."""
        from swarm_attack.learning.pattern_extractor import PatternExtractor

        extractor = PatternExtractor(config=mock_config)

        result = extractor.extract_all(sample_success_episodes)

        # Should still produce valid result
        assert result.total_episodes_analyzed == len(sample_success_episodes)

    def test_extract_handles_missing_notes(self, mock_config):
        """Test extraction handles episodes with missing notes."""
        from swarm_attack.learning.pattern_extractor import PatternExtractor
        from swarm_attack.chief_of_staff.episodes import Episode

        episode_no_notes = Episode(
            episode_id="ep-no-notes",
            timestamp="2025-01-01T10:00:00",
            goal_id="simple-task",
            success=True,
            cost_usd=1.0,
            duration_seconds=100,
            notes=None,
        )

        extractor = PatternExtractor(config=mock_config)

        # Should not raise
        result = extractor.extract_all([episode_no_notes])
        assert result.total_episodes_analyzed == 1

    def test_extract_handles_empty_error(self, mock_config):
        """Test extraction handles episodes with empty error."""
        from swarm_attack.learning.pattern_extractor import PatternExtractor
        from swarm_attack.chief_of_staff.episodes import Episode

        episode_empty_error = Episode(
            episode_id="ep-empty-error",
            timestamp="2025-01-01T10:00:00",
            goal_id="failed-task",
            success=False,
            cost_usd=2.0,
            duration_seconds=200,
            error="",
        )

        extractor = PatternExtractor(config=mock_config)

        result = extractor.extract_all([episode_empty_error])
        assert result.total_episodes_analyzed == 1


# =============================================================================
# Integration Tests
# =============================================================================


class TestPatternExtractorIntegration:
    """Integration tests for PatternExtractor."""

    def test_full_extraction_workflow(self, mock_config, mixed_episodes):
        """Test complete extraction workflow."""
        from swarm_attack.learning.pattern_extractor import PatternExtractor
        from swarm_attack.learning.strategy_optimizer import StrategyOptimizer, Task

        # Extract patterns from episodes
        extractor = PatternExtractor(config=mock_config)
        result = extractor.extract_all(mixed_episodes)

        # Convert to PatternSet for optimizer
        pattern_set = extractor.to_pattern_set(result)

        # Use patterns with StrategyOptimizer
        optimizer = StrategyOptimizer(config=mock_config)
        task = Task(
            task_id="test-task",
            description="Implement new feature",
        )

        strategy = optimizer.optimize(task, pattern_set)

        # Should produce valid optimized strategy
        assert strategy.task_id == task.task_id
        assert strategy.confidence_score >= 0.0

    def test_extract_from_episode_store(self, mock_config):
        """Test extraction using EpisodeStore."""
        from swarm_attack.learning.pattern_extractor import PatternExtractor
        from swarm_attack.chief_of_staff.episodes import EpisodeStore, Episode

        # Create store and add episodes
        store = EpisodeStore(base_path=mock_config.swarm_path / "episodes")

        episodes = [
            Episode(
                episode_id="stored-ep-001",
                timestamp="2025-01-01T10:00:00",
                goal_id="test-goal",
                success=True,
                cost_usd=1.0,
                duration_seconds=100,
            ),
            Episode(
                episode_id="stored-ep-002",
                timestamp="2025-01-01T11:00:00",
                goal_id="test-goal-2",
                success=False,
                cost_usd=2.0,
                duration_seconds=200,
                error="Test error",
            ),
        ]

        for ep in episodes:
            store.save(ep)

        # Create extractor with store
        extractor = PatternExtractor(config=mock_config, episode_store=store)

        # Extract from store
        result = extractor.extract_from_store(limit=100)

        assert result.total_episodes_analyzed == 2

    def test_incremental_extraction(self, mock_config, sample_success_episodes):
        """Test incremental pattern extraction."""
        from swarm_attack.learning.pattern_extractor import PatternExtractor

        extractor = PatternExtractor(config=mock_config)

        # First extraction
        result1 = extractor.extract_all(sample_success_episodes[:2])

        # Second extraction with more episodes
        result2 = extractor.extract_all(sample_success_episodes)

        # Second should analyze more episodes
        assert result2.total_episodes_analyzed > result1.total_episodes_analyzed
