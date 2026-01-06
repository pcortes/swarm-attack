"""TDD Tests for CoderAgent recommendation integration.

These tests verify that the CoderAgent correctly integrates with a
RecommendationEngine to receive and format recommendations in prompts.

Tests are written TDD-style - they define the expected behavior for
an extended CoderAgent that accepts an optional recommendation_engine
parameter. The implementation does not exist yet, so these tests
will FAIL until the feature is implemented.

Test Coverage:
1. test_coder_receives_recommendations_in_prompt - recs injected into prompt
2. test_coder_skips_recommendations_when_none - no recs = no section
3. test_recommendations_formatted_clearly - human-readable format
4. test_high_confidence_recommendations_highlighted - confidence shown
5. test_recommendations_include_source_context - source info included
"""

import pytest
from dataclasses import dataclass, field
from typing import Any, Optional
from unittest.mock import MagicMock, patch
from pathlib import Path


@dataclass
class Recommendation:
    """A single recommendation from the RecommendationEngine."""
    id: str
    title: str
    description: str
    confidence: float
    source: str
    source_context: dict[str, Any] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)
    priority: int = 0

    def is_high_confidence(self) -> bool:
        return self.confidence >= 0.8


class MockRecommendationEngine:
    """Mock RecommendationEngine for testing."""
    def __init__(self, recommendations: Optional[list[Recommendation]] = None):
        self.recommendations = recommendations or []
        self.get_recommendations_called = False
        self.last_context = None

    def get_recommendations(
        self,
        feature_id: str,
        issue_number: int,
        context: Optional[dict[str, Any]] = None,
    ) -> list[Recommendation]:
        self.get_recommendations_called = True
        self.last_context = {
            "feature_id": feature_id,
            "issue_number": issue_number,
            "context": context,
        }
        return self.recommendations


@pytest.fixture
def mock_config():
    from swarm_attack.config import SwarmConfig
    config = MagicMock(spec=SwarmConfig)
    config.repo_root = Path("/tmp/test-repo")
    config.specs_path = Path("/tmp/test-repo/specs")
    config.skills_path = Path("/tmp/test-repo/.claude/skills")
    return config


@pytest.fixture
def sample_recommendations() -> list[Recommendation]:
    return [
        Recommendation(
            id="rec-001",
            title="Use existing UserModel class",
            description="The UserModel class was created in Issue #1. Import it from swarm_attack/models/user.py instead of recreating it.",
            confidence=0.95,
            source="memory_store",
            source_context={
                "existing_file": "swarm_attack/models/user.py",
                "created_in_issue": 1,
                "class_name": "UserModel",
            },
            tags=["schema_drift", "import"],
            priority=10,
        ),
        Recommendation(
            id="rec-002",
            title="Follow async pattern from ConfigLoader",
            description="Similar async loading patterns were used in ConfigLoader. Consider following the same approach for consistency.",
            confidence=0.75,
            source="pattern_analyzer",
            source_context={
                "reference_file": "swarm_attack/config/loader.py",
                "pattern_type": "async_loading",
            },
            tags=["pattern", "async"],
            priority=5,
        ),
        Recommendation(
            id="rec-003",
            title="Add edge case test for empty input",
            description="Test failures in past sessions often involved empty input handling. Consider adding explicit tests.",
            confidence=0.85,
            source="test_history",
            source_context={
                "past_failures": 3,
                "common_assertion": "handles empty input gracefully",
            },
            tags=["testing", "edge_case"],
            priority=7,
        ),
    ]


@pytest.fixture
def high_confidence_recommendations() -> list[Recommendation]:
    return [
        Recommendation(
            id="rec-high-001",
            title="CRITICAL: Import existing Parser class",
            description="Parser class exists in swarm_attack/parsers/base.py",
            confidence=0.98,
            source="memory_store",
            source_context={"file": "swarm_attack/parsers/base.py"},
            tags=["critical"],
            priority=100,
        ),
        Recommendation(
            id="rec-high-002",
            title="Use established error handling pattern",
            description="Error handling should follow the SwarmError hierarchy.",
            confidence=0.92,
            source="pattern_analyzer",
            source_context={"base_class": "SwarmError"},
            tags=["error_handling"],
            priority=50,
        ),
    ]


class TestCoderRecommendationIntegration:
    """Tests for CoderAgent recommendation integration."""

    def test_coder_receives_recommendations_in_prompt(
        self,
        mock_config,
        sample_recommendations,
    ):
        """Test that recommendations are injected into the prompt."""
        from swarm_attack.agents.coder import CoderAgent

        engine = MockRecommendationEngine(recommendations=sample_recommendations)
        coder = CoderAgent(
            config=mock_config,
            recommendation_engine=engine,
        )

        with patch.object(coder, "_load_skill_prompt", return_value="Skill prompt"):
            prompt = coder._build_prompt(
                feature_id="test-feature",
                issue={"title": "Test Issue", "body": "Description", "labels": [], "estimated_size": "small"},
                spec_content="Spec content",
                test_content="Test content",
                expected_modules=[],
            )

        assert "## Recommendations" in prompt or "## AI Recommendations" in prompt
        for rec in sample_recommendations:
            assert rec.title in prompt
        assert engine.get_recommendations_called

    def test_coder_skips_recommendations_when_none(self, mock_config):
        """Test that no recommendations section appears when there are none."""
        from swarm_attack.agents.coder import CoderAgent

        engine = MockRecommendationEngine(recommendations=[])
        coder = CoderAgent(
            config=mock_config,
            recommendation_engine=engine,
        )

        with patch.object(coder, "_load_skill_prompt", return_value="Skill prompt"):
            prompt = coder._build_prompt(
                feature_id="test-feature",
                issue={"title": "Test Issue", "body": "Description", "labels": [], "estimated_size": "small"},
                spec_content="Spec content",
                test_content="Test content",
                expected_modules=[],
            )

        assert "## Recommendations" not in prompt
        assert "## AI Recommendations" not in prompt
        assert "test-feature" in prompt

    def test_coder_works_without_recommendation_engine(self, mock_config):
        """Test that CoderAgent works without a recommendation engine."""
        from swarm_attack.agents.coder import CoderAgent

        coder = CoderAgent(config=mock_config)

        with patch.object(coder, "_load_skill_prompt", return_value="Skill prompt"):
            prompt = coder._build_prompt(
                feature_id="test-feature",
                issue={"title": "Test Issue", "body": "Description", "labels": [], "estimated_size": "small"},
                spec_content="Spec content",
                test_content="Test content",
                expected_modules=[],
            )

        assert "test-feature" in prompt
        assert "## Recommendations" not in prompt

    def test_recommendations_formatted_clearly(
        self,
        mock_config,
        sample_recommendations,
    ):
        """Test that recommendations are formatted in a human-readable way."""
        from swarm_attack.agents.coder import CoderAgent

        engine = MockRecommendationEngine(recommendations=sample_recommendations)
        coder = CoderAgent(
            config=mock_config,
            recommendation_engine=engine,
        )

        with patch.object(coder, "_load_skill_prompt", return_value="Skill prompt"):
            prompt = coder._build_prompt(
                feature_id="test-feature",
                issue={"title": "Test Issue", "body": "Description", "labels": [], "estimated_size": "small"},
                spec_content="Spec content",
                test_content="Test content",
                expected_modules=[],
            )

        assert "### " in prompt or "1. " in prompt or "**1.**" in prompt
        for rec in sample_recommendations:
            assert rec.description in prompt

    def test_high_confidence_recommendations_highlighted(
        self,
        mock_config,
        high_confidence_recommendations,
    ):
        """Test that high-confidence recommendations are visually highlighted."""
        from swarm_attack.agents.coder import CoderAgent

        engine = MockRecommendationEngine(recommendations=high_confidence_recommendations)
        coder = CoderAgent(
            config=mock_config,
            recommendation_engine=engine,
        )

        with patch.object(coder, "_load_skill_prompt", return_value="Skill prompt"):
            prompt = coder._build_prompt(
                feature_id="test-feature",
                issue={"title": "Test Issue", "body": "Description", "labels": [], "estimated_size": "small"},
                spec_content="Spec content",
                test_content="Test content",
                expected_modules=[],
            )

        assert "98%" in prompt or "0.98" in prompt
        assert "92%" in prompt or "0.92" in prompt
        high_confidence_indicators = [
            "HIGH CONFIDENCE", "[HIGH]", "**HIGH**", "high confidence", "Confidence: 9",
        ]
        assert any(ind in prompt for ind in high_confidence_indicators)

    def test_recommendations_include_source_context(
        self,
        mock_config,
        sample_recommendations,
    ):
        """Test that source context is included for traceability."""
        from swarm_attack.agents.coder import CoderAgent

        engine = MockRecommendationEngine(recommendations=sample_recommendations)
        coder = CoderAgent(
            config=mock_config,
            recommendation_engine=engine,
        )

        with patch.object(coder, "_load_skill_prompt", return_value="Skill prompt"):
            prompt = coder._build_prompt(
                feature_id="test-feature",
                issue={"title": "Test Issue", "body": "Description", "labels": [], "estimated_size": "small"},
                spec_content="Spec content",
                test_content="Test content",
                expected_modules=[],
            )

        assert "memory_store" in prompt.lower() or "pattern_analyzer" in prompt.lower()
        first_rec = sample_recommendations[0]
        existing_file = first_rec.source_context.get("existing_file", "")
        if existing_file:
            assert existing_file in prompt
        class_name = first_rec.source_context.get("class_name", "")
        if class_name:
            assert class_name in prompt

    def test_format_recommendations_method_exists(self, mock_config):
        """Test that a _format_recommendations method exists for formatting."""
        from swarm_attack.agents.coder import CoderAgent

        coder = CoderAgent(config=mock_config)
        assert hasattr(coder, "_format_recommendations")
        assert callable(getattr(coder, "_format_recommendations"))

    def test_format_recommendations_returns_empty_for_no_recommendations(
        self,
        mock_config,
    ):
        """Test that _format_recommendations returns empty string for no recs."""
        from swarm_attack.agents.coder import CoderAgent

        coder = CoderAgent(config=mock_config)
        result = coder._format_recommendations([])
        assert result == ""

    def test_format_recommendations_includes_all_recommendation_fields(
        self,
        mock_config,
        sample_recommendations,
    ):
        """Test that _format_recommendations includes all important fields."""
        from swarm_attack.agents.coder import CoderAgent

        coder = CoderAgent(config=mock_config)
        result = coder._format_recommendations(sample_recommendations)

        for rec in sample_recommendations:
            assert rec.title in result
            assert rec.description in result
            confidence_pct = f"{int(rec.confidence * 100)}%"
            assert confidence_pct in result or str(rec.confidence) in result

    def test_recommendations_sorted_by_priority(
        self,
        mock_config,
        sample_recommendations,
    ):
        """Test that recommendations are sorted by priority (highest first)."""
        from swarm_attack.agents.coder import CoderAgent

        coder = CoderAgent(config=mock_config)
        result = coder._format_recommendations(sample_recommendations)

        positions = {}
        for rec in sample_recommendations:
            pos = result.find(rec.title)
            if pos != -1:
                positions[rec.title] = pos

        sorted_by_priority = sorted(sample_recommendations, key=lambda r: r.priority, reverse=True)
        for i, rec in enumerate(sorted_by_priority[:-1]):
            next_rec = sorted_by_priority[i + 1]
            if rec.title in positions and next_rec.title in positions:
                assert positions[rec.title] < positions[next_rec.title]
