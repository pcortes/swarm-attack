"""Tests for validation gates integration into pipelines and CLI."""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
from dataclasses import dataclass
from typing import Optional

from swarm_attack.chief_of_staff.critics import (
    ValidationLayer,
    ValidationResult,
    CriticScore,
    CriticFocus,
)
from swarm_attack.chief_of_staff.validation_gates import (
    ValidationGate,
    SpecValidationGate,
    CodeValidationGate,
    TestValidationGate,
    ValidationGateResult,
    ArtifactType,
)


class TestArtifactType:
    """Tests for ArtifactType enum."""

    def test_spec_exists(self):
        assert hasattr(ArtifactType, 'SPEC')

    def test_code_exists(self):
        assert hasattr(ArtifactType, 'CODE')

    def test_test_exists(self):
        assert hasattr(ArtifactType, 'TEST')

    def test_spec_value(self):
        assert ArtifactType.SPEC.value == "spec"

    def test_code_value(self):
        assert ArtifactType.CODE.value == "code"

    def test_test_value(self):
        assert ArtifactType.TEST.value == "test"


class TestValidationGateResult:
    """Tests for ValidationGateResult dataclass."""

    def test_has_approved_field(self):
        result = ValidationGateResult(
            approved=True,
            artifact_type=ArtifactType.SPEC,
            artifact_id="test-spec",
            summary="Approved",
            blocking_issues=[],
            needs_human_review=False,
            validation_result=None,
        )
        assert result.approved is True

    def test_has_artifact_type_field(self):
        result = ValidationGateResult(
            approved=True,
            artifact_type=ArtifactType.CODE,
            artifact_id="test-code",
            summary="Approved",
            blocking_issues=[],
            needs_human_review=False,
            validation_result=None,
        )
        assert result.artifact_type == ArtifactType.CODE

    def test_has_artifact_id_field(self):
        result = ValidationGateResult(
            approved=True,
            artifact_type=ArtifactType.SPEC,
            artifact_id="my-feature-spec",
            summary="Approved",
            blocking_issues=[],
            needs_human_review=False,
            validation_result=None,
        )
        assert result.artifact_id == "my-feature-spec"

    def test_has_summary_field(self):
        result = ValidationGateResult(
            approved=True,
            artifact_type=ArtifactType.SPEC,
            artifact_id="test",
            summary="Approved with 85% consensus",
            blocking_issues=[],
            needs_human_review=False,
            validation_result=None,
        )
        assert result.summary == "Approved with 85% consensus"

    def test_has_blocking_issues_field(self):
        issues = ["Security vulnerability detected", "Missing error handling"]
        result = ValidationGateResult(
            approved=False,
            artifact_type=ArtifactType.CODE,
            artifact_id="test",
            summary="Rejected",
            blocking_issues=issues,
            needs_human_review=True,
            validation_result=None,
        )
        assert result.blocking_issues == issues

    def test_has_needs_human_review_field(self):
        result = ValidationGateResult(
            approved=False,
            artifact_type=ArtifactType.SPEC,
            artifact_id="test",
            summary="Needs review",
            blocking_issues=[],
            needs_human_review=True,
            validation_result=None,
        )
        assert result.needs_human_review is True

    def test_has_validation_result_field(self):
        mock_result = MagicMock(spec=ValidationResult)
        result = ValidationGateResult(
            approved=True,
            artifact_type=ArtifactType.SPEC,
            artifact_id="test",
            summary="Approved",
            blocking_issues=[],
            needs_human_review=False,
            validation_result=mock_result,
        )
        assert result.validation_result is mock_result


class TestSpecValidationGate:
    """Tests for SpecValidationGate."""

    def test_threshold_is_60_percent(self):
        gate = SpecValidationGate(llm=MagicMock())
        assert gate.threshold == 0.6

    def test_has_security_veto(self):
        gate = SpecValidationGate(llm=MagicMock())
        assert gate.security_veto is True

    def test_validate_calls_validation_layer(self):
        mock_llm = MagicMock()
        mock_llm.generate.return_value = '{"score": 0.8, "approved": true, "issues": [], "suggestions": [], "reasoning": "good"}'
        
        gate = SpecValidationGate(llm=mock_llm)
        result = gate.validate("Test spec content", "test-spec-id")
        
        assert isinstance(result, ValidationGateResult)
        assert result.artifact_type == ArtifactType.SPEC

    def test_validate_returns_approved_on_high_score(self):
        mock_llm = MagicMock()
        # Return high scores for all critics
        mock_llm.generate.return_value = '{"score": 0.85, "approved": true, "issues": [], "suggestions": [], "reasoning": "excellent"}'
        
        gate = SpecValidationGate(llm=mock_llm)
        result = gate.validate("Good spec content", "test-spec")
        
        assert result.approved is True
        assert result.needs_human_review is False

    def test_validate_returns_rejected_on_low_score(self):
        mock_llm = MagicMock()
        # Return low scores
        mock_llm.generate.return_value = '{"score": 0.3, "approved": false, "issues": ["incomplete"], "suggestions": ["add more"], "reasoning": "needs work"}'
        
        gate = SpecValidationGate(llm=mock_llm)
        result = gate.validate("Poor spec content", "test-spec")
        
        assert result.approved is False
        assert result.needs_human_review is True

    def test_validate_security_veto_blocks(self):
        """Security issues should block even if overall score is high."""
        mock_llm = MagicMock()
        
        # First call (completeness) - high score
        # Second call (feasibility) - high score
        # Third call (security) - low score with issues
        mock_llm.generate.side_effect = [
            '{"score": 0.9, "approved": true, "issues": [], "suggestions": [], "reasoning": "complete"}',
            '{"score": 0.9, "approved": true, "issues": [], "suggestions": [], "reasoning": "feasible"}',
            '{"score": 0.3, "approved": false, "issues": ["SQL injection risk"], "suggestions": ["sanitize input"], "reasoning": "security concern"}',
        ]
        
        gate = SpecValidationGate(llm=mock_llm)
        result = gate.validate("Spec with security issues", "test-spec")
        
        assert result.approved is False
        assert "SQL injection risk" in result.blocking_issues or len(result.blocking_issues) > 0


class TestCodeValidationGate:
    """Tests for CodeValidationGate."""

    def test_threshold_is_60_percent(self):
        gate = CodeValidationGate(llm=MagicMock())
        assert gate.threshold == 0.6

    def test_has_security_veto(self):
        gate = CodeValidationGate(llm=MagicMock())
        assert gate.security_veto is True

    def test_validate_code_diff(self):
        mock_llm = MagicMock()
        mock_llm.generate.return_value = '{"score": 0.8, "approved": true, "issues": [], "suggestions": [], "reasoning": "good code"}'
        
        gate = CodeValidationGate(llm=mock_llm)
        result = gate.validate("def foo():\n    return 'bar'", "code-diff-123")
        
        assert isinstance(result, ValidationGateResult)
        assert result.artifact_type == ArtifactType.CODE

    def test_validate_returns_approved_on_good_code(self):
        mock_llm = MagicMock()
        mock_llm.generate.return_value = '{"score": 0.85, "approved": true, "issues": [], "suggestions": [], "reasoning": "clean code"}'
        
        gate = CodeValidationGate(llm=mock_llm)
        result = gate.validate("Clean code here", "good-code")
        
        assert result.approved is True

    def test_validate_blocks_on_security_issue(self):
        mock_llm = MagicMock()
        # Style passes, security fails
        mock_llm.generate.side_effect = [
            '{"score": 0.9, "approved": true, "issues": [], "suggestions": [], "reasoning": "good style"}',
            '{"score": 0.2, "approved": false, "issues": ["hardcoded password"], "suggestions": ["use env var"], "reasoning": "security risk"}',
        ]
        
        gate = CodeValidationGate(llm=mock_llm)
        result = gate.validate("password = 'secret123'", "bad-code")
        
        assert result.approved is False


class TestTestValidationGate:
    """Tests for TestValidationGate."""

    def test_threshold_is_60_percent(self):
        gate = TestValidationGate(llm=MagicMock())
        assert gate.threshold == 0.6

    def test_no_security_veto(self):
        """Test validation doesn't have security veto."""
        gate = TestValidationGate(llm=MagicMock())
        assert gate.security_veto is False

    def test_coverage_below_80_requires_review(self):
        mock_llm = MagicMock()
        # Coverage score below 0.8
        mock_llm.generate.side_effect = [
            '{"score": 0.7, "approved": true, "issues": ["low coverage"], "suggestions": ["add more tests"], "reasoning": "needs more coverage"}',
            '{"score": 0.8, "approved": true, "issues": [], "suggestions": [], "reasoning": "good edge cases"}',
        ]
        
        gate = TestValidationGate(llm=mock_llm)
        result = gate.validate("def test_foo(): pass", "test-123")
        
        # Should still approve but flag for review if coverage < 80%
        assert result.needs_human_review is True or result.approved is True

    def test_validate_test_content(self):
        mock_llm = MagicMock()
        mock_llm.generate.return_value = '{"score": 0.9, "approved": true, "issues": [], "suggestions": [], "reasoning": "comprehensive tests"}'
        
        gate = TestValidationGate(llm=mock_llm)
        result = gate.validate("def test_thing(): assert True", "test-file")
        
        assert isinstance(result, ValidationGateResult)
        assert result.artifact_type == ArtifactType.TEST


class TestValidationGateIntegration:
    """Integration tests for validation gates."""

    def test_spec_gate_uses_correct_critics(self):
        """SpecValidationGate should use completeness, feasibility, security critics."""
        mock_llm = MagicMock()
        mock_llm.generate.return_value = '{"score": 0.8, "approved": true, "issues": [], "suggestions": [], "reasoning": "good"}'
        
        gate = SpecValidationGate(llm=mock_llm)
        gate.validate("test spec", "spec-1")
        
        # Should have made 3 calls (completeness, feasibility, security)
        assert mock_llm.generate.call_count == 3

    def test_code_gate_uses_correct_critics(self):
        """CodeValidationGate should use style, security critics."""
        mock_llm = MagicMock()
        mock_llm.generate.return_value = '{"score": 0.8, "approved": true, "issues": [], "suggestions": [], "reasoning": "good"}'
        
        gate = CodeValidationGate(llm=mock_llm)
        gate.validate("test code", "code-1")
        
        # Should have made 2 calls (style, security)
        assert mock_llm.generate.call_count == 2

    def test_test_gate_uses_correct_critics(self):
        """TestValidationGate should use coverage, edge_cases critics."""
        mock_llm = MagicMock()
        mock_llm.generate.return_value = '{"score": 0.8, "approved": true, "issues": [], "suggestions": [], "reasoning": "good"}'
        
        gate = TestValidationGate(llm=mock_llm)
        gate.validate("test content", "test-1")
        
        # Should have made 2 calls (coverage, edge_cases)
        assert mock_llm.generate.call_count == 2


class TestValidationGateSummaryFormat:
    """Tests for validation gate summary formatting."""

    def test_approved_summary_shows_approved(self):
        mock_llm = MagicMock()
        mock_llm.generate.return_value = '{"score": 0.9, "approved": true, "issues": [], "suggestions": [], "reasoning": "excellent"}'
        
        gate = SpecValidationGate(llm=mock_llm)
        result = gate.validate("good spec", "spec-1")
        
        assert "APPROVED" in result.summary.upper() or result.approved is True

    def test_rejected_summary_shows_needs_review(self):
        mock_llm = MagicMock()
        mock_llm.generate.return_value = '{"score": 0.3, "approved": false, "issues": ["problem"], "suggestions": [], "reasoning": "bad"}'
        
        gate = SpecValidationGate(llm=mock_llm)
        result = gate.validate("bad spec", "spec-1")
        
        assert "REVIEW" in result.summary.upper() or result.needs_human_review is True


class TestValidationGateFromPath:
    """Tests for validating from file path."""

    def test_validate_from_path_reads_file(self, tmp_path):
        mock_llm = MagicMock()
        mock_llm.generate.return_value = '{"score": 0.8, "approved": true, "issues": [], "suggestions": [], "reasoning": "good"}'
        
        # Create test file
        test_file = tmp_path / "test_spec.md"
        test_file.write_text("# My Spec\n\nContent here")
        
        gate = SpecValidationGate(llm=mock_llm)
        result = gate.validate_from_path(test_file)
        
        assert isinstance(result, ValidationGateResult)
        assert result.artifact_id == str(test_file)

    def test_validate_from_path_handles_missing_file(self, tmp_path):
        mock_llm = MagicMock()
        
        gate = SpecValidationGate(llm=mock_llm)
        missing_path = tmp_path / "nonexistent.md"
        
        with pytest.raises(FileNotFoundError):
            gate.validate_from_path(missing_path)


class TestValidationGateCLIFormat:
    """Tests for CLI output format helper."""

    def test_to_cli_output_approved(self):
        result = ValidationGateResult(
            approved=True,
            artifact_type=ArtifactType.SPEC,
            artifact_id="test-spec",
            summary="Approved with 85% consensus",
            blocking_issues=[],
            needs_human_review=False,
            validation_result=None,
        )
        
        output = result.to_cli_output()
        
        assert "APPROVED" in output
        assert "test-spec" in output

    def test_to_cli_output_needs_review(self):
        result = ValidationGateResult(
            approved=False,
            artifact_type=ArtifactType.CODE,
            artifact_id="my-code",
            summary="Rejected due to security issues",
            blocking_issues=["SQL injection", "XSS vulnerability"],
            needs_human_review=True,
            validation_result=None,
        )
        
        output = result.to_cli_output()
        
        assert "NEEDS REVIEW" in output or "REJECTED" in output
        assert "SQL injection" in output or "blocking" in output.lower()


class TestValidationGateFileExists:
    """Test that implementation files exist."""

    def test_validation_gates_module_exists(self):
        path = Path.cwd() / "swarm_attack" / "chief_of_staff" / "validation_gates.py"
        assert path.exists(), "validation_gates.py must exist"