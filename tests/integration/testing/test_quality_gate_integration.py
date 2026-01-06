"""
Integration tests for QualityGateRunner.

Purpose: Wire AdversarialTestGenerator and MutationTestGate into CI/validation pipeline.

Tests verify:
1. QualityGateRunner orchestrates multiple gates in sequence
2. Integration with AdversarialTestGenerator for test enhancement
3. Integration with MutationTestGate for mutation testing validation
4. CI pipeline integration (exit codes, reports)
5. Configurable thresholds and gate composition
"""

from __future__ import annotations

import json
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional
from unittest.mock import Mock, patch, MagicMock

import pytest


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def temp_project():
    """Create a temporary project directory with required structure."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)

        # Create required directories
        (tmppath / ".swarm" / "state").mkdir(parents=True)
        (tmppath / ".swarm" / "testing").mkdir(parents=True)
        (tmppath / "tests").mkdir(parents=True)
        (tmppath / "src").mkdir(parents=True)

        yield tmppath


@pytest.fixture
def mock_llm():
    """Create a mock LLM for testing."""
    llm = Mock()
    llm.generate = Mock(return_value='{"score": 0.85, "approved": true, "issues": [], "suggestions": [], "reasoning": "Good quality"}')
    return llm


@pytest.fixture
def sample_code():
    """Sample code for testing gates."""
    return '''
def calculate_total(items: list[float]) -> float:
    """Calculate total sum of items."""
    if not items:
        return 0.0
    return sum(items)


def apply_discount(total: float, discount_percent: float) -> float:
    """Apply percentage discount to total."""
    if discount_percent < 0 or discount_percent > 100:
        raise ValueError("Discount must be between 0 and 100")
    return total * (1 - discount_percent / 100)
'''


@pytest.fixture
def sample_tests():
    """Sample test code for testing gates."""
    return '''
import pytest
from src.calculator import calculate_total, apply_discount


def test_calculate_total_empty():
    assert calculate_total([]) == 0.0


def test_calculate_total_single():
    assert calculate_total([10.0]) == 10.0


def test_calculate_total_multiple():
    assert calculate_total([1.0, 2.0, 3.0]) == 6.0


def test_apply_discount_zero():
    assert apply_discount(100.0, 0) == 100.0


def test_apply_discount_fifty_percent():
    assert apply_discount(100.0, 50) == 50.0
'''


# ============================================================================
# Test: QualityGateRunner Basic Operation
# ============================================================================


class TestQualityGateRunnerBasic:
    """Tests for basic QualityGateRunner operation."""

    def test_quality_gate_runner_import(self):
        """QualityGateRunner can be imported from swarm_attack.testing."""
        from swarm_attack.testing.quality_gate_runner import QualityGateRunner
        assert QualityGateRunner is not None

    def test_quality_gate_runner_init_default(self, mock_llm):
        """QualityGateRunner initializes with default configuration."""
        from swarm_attack.testing.quality_gate_runner import QualityGateRunner

        runner = QualityGateRunner(llm=mock_llm)

        assert runner.llm is mock_llm
        assert runner.threshold >= 0.0
        assert runner.threshold <= 1.0

    def test_quality_gate_runner_init_custom_threshold(self, mock_llm):
        """QualityGateRunner accepts custom threshold."""
        from swarm_attack.testing.quality_gate_runner import QualityGateRunner

        runner = QualityGateRunner(llm=mock_llm, threshold=0.9)

        assert runner.threshold == 0.9

    def test_quality_gate_runner_run_returns_result(self, mock_llm, sample_code, sample_tests, temp_project):
        """QualityGateRunner.run() returns QualityGateResult."""
        from swarm_attack.testing.quality_gate_runner import QualityGateRunner, QualityGateResult

        runner = QualityGateRunner(llm=mock_llm)
        result = runner.run(
            code=sample_code,
            tests=sample_tests,
            artifact_id="test-artifact",
        )

        assert isinstance(result, QualityGateResult)
        assert result.artifact_id == "test-artifact"


# ============================================================================
# Test: QualityGateResult Structure
# ============================================================================


class TestQualityGateResult:
    """Tests for QualityGateResult dataclass."""

    def test_quality_gate_result_import(self):
        """QualityGateResult can be imported."""
        from swarm_attack.testing.quality_gate_runner import QualityGateResult
        assert QualityGateResult is not None

    def test_quality_gate_result_fields(self, mock_llm, sample_code, sample_tests):
        """QualityGateResult has required fields."""
        from swarm_attack.testing.quality_gate_runner import QualityGateRunner, QualityGateResult

        runner = QualityGateRunner(llm=mock_llm)
        result = runner.run(code=sample_code, tests=sample_tests, artifact_id="test")

        # Check required fields exist
        assert hasattr(result, "passed")
        assert hasattr(result, "artifact_id")
        assert hasattr(result, "gates_passed")
        assert hasattr(result, "gates_failed")
        assert hasattr(result, "overall_score")
        assert hasattr(result, "gate_results")

    def test_quality_gate_result_to_dict(self, mock_llm, sample_code, sample_tests):
        """QualityGateResult can be serialized to dict."""
        from swarm_attack.testing.quality_gate_runner import QualityGateRunner

        runner = QualityGateRunner(llm=mock_llm)
        result = runner.run(code=sample_code, tests=sample_tests, artifact_id="test")

        result_dict = result.to_dict()

        assert isinstance(result_dict, dict)
        assert "passed" in result_dict
        assert "artifact_id" in result_dict
        assert "overall_score" in result_dict

    def test_quality_gate_result_to_ci_exit_code(self, mock_llm, sample_code, sample_tests):
        """QualityGateResult provides CI exit code."""
        from swarm_attack.testing.quality_gate_runner import QualityGateRunner

        runner = QualityGateRunner(llm=mock_llm)
        result = runner.run(code=sample_code, tests=sample_tests, artifact_id="test")

        exit_code = result.to_exit_code()

        # 0 for success, non-zero for failure
        assert exit_code == 0 if result.passed else exit_code != 0


# ============================================================================
# Test: AdversarialTestGenerator Integration
# ============================================================================


class TestAdversarialTestGeneratorIntegration:
    """Tests for AdversarialTestGenerator integration."""

    def test_adversarial_test_generator_import(self):
        """AdversarialTestGenerator can be imported."""
        from swarm_attack.testing.quality_gate_runner import AdversarialTestGenerator
        assert AdversarialTestGenerator is not None

    def test_adversarial_generator_init(self, mock_llm):
        """AdversarialTestGenerator initializes with LLM."""
        from swarm_attack.testing.quality_gate_runner import AdversarialTestGenerator

        generator = AdversarialTestGenerator(llm=mock_llm)

        assert generator.llm is mock_llm

    def test_adversarial_generator_generate_returns_tests(self, mock_llm, sample_code):
        """AdversarialTestGenerator.generate() returns test suggestions."""
        from swarm_attack.testing.quality_gate_runner import AdversarialTestGenerator

        # Configure mock to return adversarial test suggestions
        mock_llm.generate.return_value = json.dumps({
            "score": 0.75,
            "approved": True,
            "issues": ["Missing negative input test"],
            "suggestions": [
                "Test with negative numbers",
                "Test with very large numbers",
                "Test with None input",
            ],
            "reasoning": "Edge cases not fully covered",
        })

        generator = AdversarialTestGenerator(llm=mock_llm)
        result = generator.generate(code=sample_code)

        assert result is not None
        assert hasattr(result, "suggestions")
        assert len(result.suggestions) > 0

    def test_adversarial_generator_integrated_in_runner(self, mock_llm, sample_code, sample_tests):
        """AdversarialTestGenerator is called when runner includes adversarial gate."""
        from swarm_attack.testing.quality_gate_runner import (
            QualityGateRunner,
            GateType,
        )

        runner = QualityGateRunner(
            llm=mock_llm,
            gates=[GateType.ADVERSARIAL],
        )
        result = runner.run(code=sample_code, tests=sample_tests, artifact_id="test")

        # Verify adversarial gate was executed
        assert any(gr.gate_type == GateType.ADVERSARIAL for gr in result.gate_results)


# ============================================================================
# Test: MutationTestGate Integration
# ============================================================================


class TestMutationTestGateIntegration:
    """Tests for MutationTestGate integration."""

    def test_mutation_test_gate_import(self):
        """MutationTestGate can be imported."""
        from swarm_attack.testing.quality_gate_runner import MutationTestGate
        assert MutationTestGate is not None

    def test_mutation_gate_init(self, mock_llm):
        """MutationTestGate initializes with LLM."""
        from swarm_attack.testing.quality_gate_runner import MutationTestGate

        gate = MutationTestGate(llm=mock_llm)

        assert gate.llm is mock_llm

    def test_mutation_gate_evaluate_returns_score(self, mock_llm, sample_code, sample_tests):
        """MutationTestGate.evaluate() returns mutation score analysis."""
        from swarm_attack.testing.quality_gate_runner import MutationTestGate

        # Configure mock for mutation analysis
        mock_llm.generate.return_value = json.dumps({
            "score": 0.80,
            "approved": True,
            "issues": ["Some mutations would survive"],
            "suggestions": [
                "Add assertion for boundary conditions",
                "Test error handling paths",
            ],
            "reasoning": "80% of mutations would be caught by existing tests",
            "mutation_score": 0.80,
            "surviving_mutations": ["boundary condition at line 5"],
        })

        gate = MutationTestGate(llm=mock_llm)
        result = gate.evaluate(code=sample_code, tests=sample_tests)

        assert result is not None
        assert hasattr(result, "score")
        assert hasattr(result, "approved")

    def test_mutation_gate_integrated_in_runner(self, mock_llm, sample_code, sample_tests):
        """MutationTestGate is called when runner includes mutation gate."""
        from swarm_attack.testing.quality_gate_runner import (
            QualityGateRunner,
            GateType,
        )

        runner = QualityGateRunner(
            llm=mock_llm,
            gates=[GateType.MUTATION],
        )
        result = runner.run(code=sample_code, tests=sample_tests, artifact_id="test")

        # Verify mutation gate was executed
        assert any(gr.gate_type == GateType.MUTATION for gr in result.gate_results)


# ============================================================================
# Test: Pipeline Orchestration
# ============================================================================


class TestPipelineOrchestration:
    """Tests for gate orchestration in pipeline."""

    def test_runner_executes_multiple_gates(self, mock_llm, sample_code, sample_tests):
        """QualityGateRunner executes multiple gates in sequence."""
        from swarm_attack.testing.quality_gate_runner import (
            QualityGateRunner,
            GateType,
        )

        runner = QualityGateRunner(
            llm=mock_llm,
            gates=[GateType.ADVERSARIAL, GateType.MUTATION],
        )
        result = runner.run(code=sample_code, tests=sample_tests, artifact_id="test")

        # Both gates should have results
        gate_types = [gr.gate_type for gr in result.gate_results]
        assert GateType.ADVERSARIAL in gate_types
        assert GateType.MUTATION in gate_types

    def test_runner_fails_if_any_gate_fails(self, mock_llm, sample_code, sample_tests):
        """QualityGateRunner fails if any gate fails threshold."""
        from swarm_attack.testing.quality_gate_runner import (
            QualityGateRunner,
            GateType,
        )

        # First call passes, second fails
        mock_llm.generate.side_effect = [
            json.dumps({"score": 0.90, "approved": True, "issues": [], "suggestions": [], "reasoning": "Good"}),
            json.dumps({"score": 0.30, "approved": False, "issues": ["Too many mutations survive"], "suggestions": [], "reasoning": "Poor mutation coverage"}),
        ]

        runner = QualityGateRunner(
            llm=mock_llm,
            gates=[GateType.ADVERSARIAL, GateType.MUTATION],
            threshold=0.6,
        )
        result = runner.run(code=sample_code, tests=sample_tests, artifact_id="test")

        assert not result.passed
        assert len(result.gates_failed) >= 1

    def test_runner_passes_if_all_gates_pass(self, mock_llm, sample_code, sample_tests):
        """QualityGateRunner passes if all gates pass threshold."""
        from swarm_attack.testing.quality_gate_runner import (
            QualityGateRunner,
            GateType,
        )

        # Both calls pass
        mock_llm.generate.side_effect = [
            json.dumps({"score": 0.90, "approved": True, "issues": [], "suggestions": [], "reasoning": "Good"}),
            json.dumps({"score": 0.85, "approved": True, "issues": [], "suggestions": [], "reasoning": "Good mutation coverage"}),
        ]

        runner = QualityGateRunner(
            llm=mock_llm,
            gates=[GateType.ADVERSARIAL, GateType.MUTATION],
            threshold=0.6,
        )
        result = runner.run(code=sample_code, tests=sample_tests, artifact_id="test")

        assert result.passed
        assert len(result.gates_failed) == 0


# ============================================================================
# Test: CI Integration
# ============================================================================


class TestCIIntegration:
    """Tests for CI/CD pipeline integration."""

    def test_runner_generates_report(self, mock_llm, sample_code, sample_tests, temp_project):
        """QualityGateRunner generates CI-friendly report."""
        from swarm_attack.testing.quality_gate_runner import QualityGateRunner

        runner = QualityGateRunner(llm=mock_llm)
        result = runner.run(code=sample_code, tests=sample_tests, artifact_id="test")

        report = result.to_report()

        assert isinstance(report, str)
        assert "test" in report  # artifact_id should be in report

    def test_runner_generates_json_report(self, mock_llm, sample_code, sample_tests, temp_project):
        """QualityGateRunner generates JSON report for CI parsing."""
        from swarm_attack.testing.quality_gate_runner import QualityGateRunner

        runner = QualityGateRunner(llm=mock_llm)
        result = runner.run(code=sample_code, tests=sample_tests, artifact_id="test")

        json_report = result.to_json()

        # Verify it's valid JSON
        parsed = json.loads(json_report)
        assert "passed" in parsed
        assert "artifact_id" in parsed

    def test_runner_writes_report_to_file(self, mock_llm, sample_code, sample_tests, temp_project):
        """QualityGateRunner can write report to file."""
        from swarm_attack.testing.quality_gate_runner import QualityGateRunner

        report_path = temp_project / ".swarm" / "testing" / "report.json"

        runner = QualityGateRunner(llm=mock_llm)
        result = runner.run(
            code=sample_code,
            tests=sample_tests,
            artifact_id="test",
            report_path=report_path,
        )

        assert report_path.exists()
        report_data = json.loads(report_path.read_text())
        assert report_data["artifact_id"] == "test"


# ============================================================================
# Test: Default Gate Configuration
# ============================================================================


class TestDefaultGateConfiguration:
    """Tests for default gate configuration."""

    def test_runner_uses_default_gates(self, mock_llm):
        """QualityGateRunner uses default gates when none specified."""
        from swarm_attack.testing.quality_gate_runner import (
            QualityGateRunner,
            GateType,
        )

        runner = QualityGateRunner(llm=mock_llm)

        # Default should include both adversarial and mutation gates
        assert GateType.ADVERSARIAL in runner.gates
        assert GateType.MUTATION in runner.gates

    def test_runner_allows_custom_gates(self, mock_llm):
        """QualityGateRunner accepts custom gate configuration."""
        from swarm_attack.testing.quality_gate_runner import (
            QualityGateRunner,
            GateType,
        )

        runner = QualityGateRunner(
            llm=mock_llm,
            gates=[GateType.MUTATION],  # Only mutation
        )

        assert runner.gates == [GateType.MUTATION]


# ============================================================================
# Test: Integration with ValidationGates
# ============================================================================


class TestValidationGatesIntegration:
    """Tests for integration with existing ValidationGates."""

    def test_runner_uses_validation_layer_internally(self, mock_llm, sample_code, sample_tests):
        """QualityGateRunner uses ValidationLayer-style patterns."""
        from swarm_attack.testing.quality_gate_runner import QualityGateRunner

        runner = QualityGateRunner(llm=mock_llm)
        result = runner.run(code=sample_code, tests=sample_tests, artifact_id="test")

        # Result should have similar structure to ValidationGateResult
        assert hasattr(result, "passed")  # Similar to 'approved'
        assert hasattr(result, "gate_results")  # Similar to 'scores'

    def test_runner_compatible_with_validation_gates(self, mock_llm, sample_code, sample_tests):
        """QualityGateRunner results can be combined with ValidationGates."""
        from swarm_attack.testing.quality_gate_runner import QualityGateRunner
        from swarm_attack.chief_of_staff.validation_gates import (
            SuiteValidationGate,
            ValidationGateResult,
        )

        # Run quality gates
        quality_runner = QualityGateRunner(llm=mock_llm)
        quality_result = quality_runner.run(code=sample_code, tests=sample_tests, artifact_id="test")

        # Run validation gate
        validation_gate = SuiteValidationGate(llm=mock_llm)
        validation_result = validation_gate.validate(sample_tests, "test-validation")

        # Both should have pass/fail semantics
        assert isinstance(quality_result.passed, bool)
        assert isinstance(validation_result.approved, bool)


# ============================================================================
# Test: Error Handling
# ============================================================================


class TestErrorHandling:
    """Tests for error handling in QualityGateRunner."""

    def test_runner_handles_llm_error(self, mock_llm, sample_code, sample_tests):
        """QualityGateRunner handles LLM errors gracefully."""
        from swarm_attack.testing.quality_gate_runner import QualityGateRunner

        mock_llm.generate.side_effect = Exception("LLM service unavailable")

        runner = QualityGateRunner(llm=mock_llm)
        result = runner.run(code=sample_code, tests=sample_tests, artifact_id="test")

        # Should return a failed result, not raise
        assert not result.passed
        assert len(result.gates_failed) > 0

    def test_runner_handles_empty_code(self, mock_llm, sample_tests):
        """QualityGateRunner handles empty code input."""
        from swarm_attack.testing.quality_gate_runner import QualityGateRunner

        runner = QualityGateRunner(llm=mock_llm)
        result = runner.run(code="", tests=sample_tests, artifact_id="test")

        # Should not crash, may fail validation
        assert isinstance(result.passed, bool)

    def test_runner_handles_empty_tests(self, mock_llm, sample_code):
        """QualityGateRunner handles empty tests input."""
        from swarm_attack.testing.quality_gate_runner import QualityGateRunner

        runner = QualityGateRunner(llm=mock_llm)
        result = runner.run(code=sample_code, tests="", artifact_id="test")

        # Should not crash, likely fails
        assert isinstance(result.passed, bool)

    def test_runner_handles_malformed_llm_response(self, mock_llm, sample_code, sample_tests):
        """QualityGateRunner handles malformed LLM responses."""
        from swarm_attack.testing.quality_gate_runner import QualityGateRunner

        mock_llm.generate.return_value = "This is not valid JSON"

        runner = QualityGateRunner(llm=mock_llm)
        result = runner.run(code=sample_code, tests=sample_tests, artifact_id="test")

        # Should return a failed result, not raise
        assert not result.passed
