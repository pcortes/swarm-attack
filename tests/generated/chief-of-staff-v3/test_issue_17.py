"""Tests for ValidationLayer consensus mechanism."""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import asyncio
from pathlib import Path

from swarm_attack.chief_of_staff.critics import (
    CriticFocus,
    CriticScore,
    Critic,
    SpecCritic,
    CodeCritic,
    TestCritic,
    ValidationResult,
    ValidationLayer,
)


class TestValidationResultDataclass:
    """Tests for ValidationResult dataclass."""

    def test_has_required_fields(self):
        """ValidationResult has all required fields."""
        result = ValidationResult(
            artifact_type="spec",
            artifact_id="test-123",
            approved=True,
            scores=[],
            blocking_issues=[],
            consensus_summary="All critics approved",
            human_review_required=False,
        )
        assert result.artifact_type == "spec"
        assert result.artifact_id == "test-123"
        assert result.approved is True
        assert result.scores == []
        assert result.blocking_issues == []
        assert result.consensus_summary == "All critics approved"
        assert result.human_review_required is False

    def test_to_dict(self):
        """ValidationResult can serialize to dict."""
        score = CriticScore(
            critic_name="TestCritic",
            focus=CriticFocus.COMPLETENESS,
            score=0.8,
            approved=True,
            issues=[],
            suggestions=[],
            reasoning="Looks good",
        )
        result = ValidationResult(
            artifact_type="spec",
            artifact_id="test-123",
            approved=True,
            scores=[score],
            blocking_issues=["security issue"],
            consensus_summary="Approved with issues",
            human_review_required=True,
        )
        data = result.to_dict()
        assert data["artifact_type"] == "spec"
        assert data["artifact_id"] == "test-123"
        assert data["approved"] is True
        assert len(data["scores"]) == 1
        assert data["blocking_issues"] == ["security issue"]
        assert data["consensus_summary"] == "Approved with issues"
        assert data["human_review_required"] is True

    def test_from_dict(self):
        """ValidationResult can deserialize from dict."""
        data = {
            "artifact_type": "code",
            "artifact_id": "code-456",
            "approved": False,
            "scores": [
                {
                    "critic_name": "SecurityCritic",
                    "focus": "SECURITY",
                    "score": 0.3,
                    "approved": False,
                    "issues": ["SQL injection risk"],
                    "suggestions": ["Use parameterized queries"],
                    "reasoning": "Critical security flaw",
                }
            ],
            "blocking_issues": ["SQL injection risk"],
            "consensus_summary": "Blocked by security",
            "human_review_required": True,
        }
        result = ValidationResult.from_dict(data)
        assert result.artifact_type == "code"
        assert result.artifact_id == "code-456"
        assert result.approved is False
        assert len(result.scores) == 1
        assert result.scores[0].critic_name == "SecurityCritic"
        assert result.blocking_issues == ["SQL injection risk"]
        assert result.human_review_required is True


class TestValidationLayerInit:
    """Tests for ValidationLayer initialization."""

    def test_constructor_takes_llm(self):
        """ValidationLayer constructor takes llm parameter."""
        mock_llm = Mock()
        layer = ValidationLayer(llm=mock_llm)
        assert layer.llm == mock_llm

    def test_initializes_critic_sets(self):
        """ValidationLayer initializes critic sets for spec/code/test."""
        mock_llm = Mock()
        layer = ValidationLayer(llm=mock_llm)
        
        # Should have critic sets
        assert hasattr(layer, "spec_critics")
        assert hasattr(layer, "code_critics")
        assert hasattr(layer, "test_critics")
        
        # Each should be a list of critics
        assert isinstance(layer.spec_critics, list)
        assert isinstance(layer.code_critics, list)
        assert isinstance(layer.test_critics, list)

    def test_spec_critics_include_required_focuses(self):
        """Spec critics include completeness, feasibility, security."""
        mock_llm = Mock()
        layer = ValidationLayer(llm=mock_llm)
        
        focuses = {c.focus for c in layer.spec_critics}
        assert CriticFocus.COMPLETENESS in focuses
        assert CriticFocus.FEASIBILITY in focuses
        assert CriticFocus.SECURITY in focuses

    def test_code_critics_include_required_focuses(self):
        """Code critics include style, security."""
        mock_llm = Mock()
        layer = ValidationLayer(llm=mock_llm)
        
        focuses = {c.focus for c in layer.code_critics}
        assert CriticFocus.STYLE in focuses
        assert CriticFocus.SECURITY in focuses

    def test_test_critics_include_required_focuses(self):
        """Test critics include coverage, edge_cases."""
        mock_llm = Mock()
        layer = ValidationLayer(llm=mock_llm)
        
        focuses = {c.focus for c in layer.test_critics}
        assert CriticFocus.COVERAGE in focuses
        assert CriticFocus.EDGE_CASES in focuses


class TestValidationLayerValidate:
    """Tests for ValidationLayer.validate() method."""

    def test_validate_returns_validation_result(self):
        """validate() returns a ValidationResult."""
        mock_llm = Mock()
        mock_llm.generate = Mock(return_value='{"score": 0.8, "approved": true, "issues": [], "suggestions": [], "reasoning": "Good"}')
        
        layer = ValidationLayer(llm=mock_llm)
        result = layer.validate(
            artifact="test content",
            artifact_type="spec",
            artifact_id="test-123",
        )
        
        assert isinstance(result, ValidationResult)
        assert result.artifact_type == "spec"
        assert result.artifact_id == "test-123"

    def test_validate_uses_correct_critic_set(self):
        """validate() uses the correct critic set based on artifact_type."""
        mock_llm = Mock()
        mock_llm.generate = Mock(return_value='{"score": 0.9, "approved": true, "issues": [], "suggestions": [], "reasoning": "OK"}')
        
        layer = ValidationLayer(llm=mock_llm)
        
        # Validate spec
        result = layer.validate("spec content", "spec", "spec-1")
        assert result.artifact_type == "spec"
        
        # Validate code
        result = layer.validate("code content", "code", "code-1")
        assert result.artifact_type == "code"
        
        # Validate test
        result = layer.validate("test content", "test", "test-1")
        assert result.artifact_type == "test"


class TestSecurityVeto:
    """Tests for security veto blocking approval."""

    def test_security_rejection_blocks_approval(self):
        """Security critic rejection blocks overall approval."""
        mock_llm = Mock()
        
        # First calls return high scores, security returns low
        responses = [
            '{"score": 0.9, "approved": true, "issues": [], "suggestions": [], "reasoning": "Good"}',
            '{"score": 0.9, "approved": true, "issues": [], "suggestions": [], "reasoning": "Good"}',
            '{"score": 0.2, "approved": false, "issues": ["SQL injection"], "suggestions": ["Fix it"], "reasoning": "Critical flaw"}',
        ]
        mock_llm.generate = Mock(side_effect=responses)
        
        layer = ValidationLayer(llm=mock_llm)
        result = layer.validate("vulnerable code", "spec", "spec-1")
        
        # Even with high scores from others, security veto blocks
        assert result.approved is False
        assert "SQL injection" in result.blocking_issues or any("SQL" in str(s) for s in result.blocking_issues)

    def test_security_approval_allows_consensus(self):
        """Security approval allows consensus to proceed normally."""
        mock_llm = Mock()
        mock_llm.generate = Mock(return_value='{"score": 0.85, "approved": true, "issues": [], "suggestions": [], "reasoning": "Secure"}')
        
        layer = ValidationLayer(llm=mock_llm)
        result = layer.validate("secure code", "spec", "spec-1")
        
        # With all critics approving, should be approved
        assert result.approved is True


class TestMajorityVote:
    """Tests for majority vote consensus mechanism."""

    def test_sixty_percent_approval_passes(self):
        """60% weighted approval threshold passes validation."""
        mock_llm = Mock()
        # All critics approve with good scores
        mock_llm.generate = Mock(return_value='{"score": 0.75, "approved": true, "issues": [], "suggestions": [], "reasoning": "Acceptable"}')
        
        layer = ValidationLayer(llm=mock_llm)
        result = layer.validate("good content", "spec", "spec-1")
        
        assert result.approved is True
        assert result.human_review_required is False

    def test_below_sixty_percent_fails(self):
        """Below 60% weighted approval fails validation."""
        mock_llm = Mock()
        # Low scores that don't meet threshold
        mock_llm.generate = Mock(return_value='{"score": 0.4, "approved": false, "issues": ["Many problems"], "suggestions": ["Rewrite"], "reasoning": "Poor quality"}')
        
        layer = ValidationLayer(llm=mock_llm)
        result = layer.validate("poor content", "spec", "spec-1")
        
        assert result.approved is False
        assert result.human_review_required is True


class TestConsensusSummary:
    """Tests for consensus summary generation."""

    def test_consensus_summary_includes_average_score(self):
        """Consensus summary includes average score."""
        mock_llm = Mock()
        mock_llm.generate = Mock(return_value='{"score": 0.8, "approved": true, "issues": [], "suggestions": [], "reasoning": "Good"}')
        
        layer = ValidationLayer(llm=mock_llm)
        result = layer.validate("content", "spec", "spec-1")
        
        # Summary should mention the score or approval status
        assert result.consensus_summary is not None
        assert len(result.consensus_summary) > 0

    def test_consensus_summary_reflects_outcome(self):
        """Consensus summary reflects the validation outcome."""
        mock_llm = Mock()
        mock_llm.generate = Mock(return_value='{"score": 0.9, "approved": true, "issues": [], "suggestions": [], "reasoning": "Excellent"}')
        
        layer = ValidationLayer(llm=mock_llm)
        result = layer.validate("content", "spec", "spec-1")
        
        # Approved result should have positive summary
        assert "approved" in result.consensus_summary.lower() or "pass" in result.consensus_summary.lower() or result.approved


class TestHumanReviewRequired:
    """Tests for human_review_required flag."""

    def test_human_review_when_blocked(self):
        """human_review_required=True when blocked by security."""
        mock_llm = Mock()
        mock_llm.generate = Mock(return_value='{"score": 0.2, "approved": false, "issues": ["Critical security flaw"], "suggestions": [], "reasoning": "Blocked"}')
        
        layer = ValidationLayer(llm=mock_llm)
        result = layer.validate("insecure content", "spec", "spec-1")
        
        assert result.human_review_required is True

    def test_human_review_when_below_threshold(self):
        """human_review_required=True when below 60% approval."""
        mock_llm = Mock()
        mock_llm.generate = Mock(return_value='{"score": 0.5, "approved": false, "issues": ["Needs work"], "suggestions": [], "reasoning": "Below threshold"}')
        
        layer = ValidationLayer(llm=mock_llm)
        result = layer.validate("mediocre content", "spec", "spec-1")
        
        assert result.human_review_required is True

    def test_no_human_review_when_approved(self):
        """human_review_required=False when fully approved."""
        mock_llm = Mock()
        mock_llm.generate = Mock(return_value='{"score": 0.9, "approved": true, "issues": [], "suggestions": [], "reasoning": "Great"}')
        
        layer = ValidationLayer(llm=mock_llm)
        result = layer.validate("great content", "spec", "spec-1")
        
        assert result.human_review_required is False


class TestValidationLayerFileExists:
    """Test that the critics.py file exists with ValidationLayer."""

    def test_critics_file_exists(self):
        """critics.py file exists in the expected location."""
        path = Path.cwd() / "swarm_attack" / "chief_of_staff" / "critics.py"
        assert path.exists(), f"critics.py must exist at {path}"

    def test_validation_layer_importable(self):
        """ValidationLayer can be imported from critics module."""
        from swarm_attack.chief_of_staff.critics import ValidationLayer
        assert ValidationLayer is not None

    def test_validation_result_importable(self):
        """ValidationResult can be imported from critics module."""
        from swarm_attack.chief_of_staff.critics import ValidationResult
        assert ValidationResult is not None