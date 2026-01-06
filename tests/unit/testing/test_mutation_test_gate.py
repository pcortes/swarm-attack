"""Tests for MutationTestGate - mutation testing quality gate.

TDD tests for MutationTestGate that requires minimum mutation score for test adequacy.

Requirements:
- Minimum 60% mutation score to pass (configurable)
- Integration with mutmut or similar tool
- Configurable thresholds per project
- Detailed mutation survival reports
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
import json
import subprocess


# ============================================================================
# Test fixtures
# ============================================================================

@pytest.fixture
def temp_swarm_dir(tmp_path):
    """Create a temporary .swarm directory."""
    swarm_dir = tmp_path / ".swarm"
    swarm_dir.mkdir()
    return swarm_dir


@pytest.fixture
def mock_config():
    """Create a mock configuration."""
    config = Mock()
    config.mutation_testing = Mock()
    config.mutation_testing.min_score = 60.0
    config.mutation_testing.tool = "mutmut"
    config.mutation_testing.timeout_seconds = 300
    return config


@pytest.fixture
def sample_mutmut_output():
    """Sample mutmut JSON output."""
    return {
        "total_mutants": 100,
        "killed": 65,
        "survived": 30,
        "timeout": 3,
        "suspicious": 2,
        "skipped": 0,
        "survived_mutants": [
            {
                "id": 1,
                "file": "src/calculator.py",
                "line": 10,
                "description": "Changed + to -",
                "status": "survived"
            },
            {
                "id": 2,
                "file": "src/calculator.py",
                "line": 15,
                "description": "Removed return statement",
                "status": "survived"
            }
        ]
    }


# ============================================================================
# Test: MutationTestGate exists and has expected interface
# ============================================================================

class TestMutationTestGateInterface:
    """Test that MutationTestGate has the expected interface."""

    def test_gate_can_be_imported(self):
        """MutationTestGate should be importable from testing module."""
        from swarm_attack.testing.mutation_test_gate import MutationTestGate
        assert MutationTestGate is not None

    def test_gate_has_run_method(self):
        """Gate should have run method."""
        from swarm_attack.testing.mutation_test_gate import MutationTestGate
        gate = MutationTestGate()
        assert hasattr(gate, 'run')
        assert callable(gate.run)

    def test_gate_accepts_min_score_config(self):
        """Gate should accept minimum score configuration."""
        from swarm_attack.testing.mutation_test_gate import MutationTestGate
        gate = MutationTestGate(min_score=70.0)
        assert gate.min_score == 70.0

    def test_gate_default_min_score_is_60(self):
        """Gate should default to 60% minimum score."""
        from swarm_attack.testing.mutation_test_gate import MutationTestGate
        gate = MutationTestGate()
        assert gate.min_score == 60.0

    def test_gate_accepts_tool_config(self):
        """Gate should accept mutation tool configuration."""
        from swarm_attack.testing.mutation_test_gate import MutationTestGate
        gate = MutationTestGate(tool="mutmut")
        assert gate.tool == "mutmut"

    def test_gate_accepts_timeout_config(self):
        """Gate should accept timeout configuration."""
        from swarm_attack.testing.mutation_test_gate import MutationTestGate
        gate = MutationTestGate(timeout_seconds=600)
        assert gate.timeout_seconds == 600


# ============================================================================
# Test: MutationTestResult data class
# ============================================================================

class TestMutationTestResult:
    """Test the MutationTestResult data class."""

    def test_result_can_be_imported(self):
        """MutationTestResult should be importable."""
        from swarm_attack.testing.mutation_test_gate import MutationTestResult
        assert MutationTestResult is not None

    def test_result_has_expected_fields(self):
        """Result should have all expected fields."""
        from swarm_attack.testing.mutation_test_gate import MutationTestResult
        result = MutationTestResult(
            passed=True,
            score=75.0,
            total_mutants=100,
            killed=75,
            survived=20,
            timeout=3,
            suspicious=2,
            skipped=0,
            min_score_required=60.0,
            survived_mutants=[],
            report_path=None,
            error=None
        )
        assert result.passed is True
        assert result.score == 75.0
        assert result.total_mutants == 100

    def test_result_to_dict(self):
        """Result should be convertible to dictionary."""
        from swarm_attack.testing.mutation_test_gate import MutationTestResult
        result = MutationTestResult(
            passed=True,
            score=75.0,
            total_mutants=100,
            killed=75,
            survived=20,
            timeout=3,
            suspicious=2,
            skipped=0,
            min_score_required=60.0,
            survived_mutants=[],
            report_path=None,
            error=None
        )
        d = result.to_dict()
        assert d["passed"] is True
        assert d["score"] == 75.0


# ============================================================================
# Test: MutantInfo data class
# ============================================================================

class TestMutantInfo:
    """Test the MutantInfo data class."""

    def test_mutant_info_can_be_imported(self):
        """MutantInfo should be importable."""
        from swarm_attack.testing.mutation_test_gate import MutantInfo
        assert MutantInfo is not None

    def test_mutant_info_has_expected_fields(self):
        """MutantInfo should have all expected fields."""
        from swarm_attack.testing.mutation_test_gate import MutantInfo
        info = MutantInfo(
            id=1,
            file="src/calculator.py",
            line=10,
            description="Changed + to -",
            status="survived"
        )
        assert info.id == 1
        assert info.file == "src/calculator.py"
        assert info.line == 10


# ============================================================================
# Test: Gate passes when mutation score >= threshold
# ============================================================================

class TestMutationScorePass:
    """Test that gate passes when mutation score meets threshold."""

    def test_passes_when_score_equals_threshold(self):
        """Gate should pass when score equals threshold."""
        from swarm_attack.testing.mutation_test_gate import MutationTestGate
        gate = MutationTestGate(min_score=60.0)

        with patch.object(gate, '_run_mutmut') as mock_run:
            mock_run.return_value = {
                "total_mutants": 100,
                "killed": 60,
                "survived": 35,
                "timeout": 3,
                "suspicious": 2,
                "skipped": 0,
                "survived_mutants": []
            }
            result = gate.run(target_path="src/")
            assert result.passed is True
            assert result.score == 60.0

    def test_passes_when_score_exceeds_threshold(self):
        """Gate should pass when score exceeds threshold."""
        from swarm_attack.testing.mutation_test_gate import MutationTestGate
        gate = MutationTestGate(min_score=60.0)

        with patch.object(gate, '_run_mutmut') as mock_run:
            mock_run.return_value = {
                "total_mutants": 100,
                "killed": 85,
                "survived": 10,
                "timeout": 3,
                "suspicious": 2,
                "skipped": 0,
                "survived_mutants": []
            }
            result = gate.run(target_path="src/")
            assert result.passed is True
            assert result.score == 85.0

    def test_score_calculated_as_killed_percentage(self):
        """Score should be calculated as (killed/total) * 100."""
        from swarm_attack.testing.mutation_test_gate import MutationTestGate
        gate = MutationTestGate(min_score=60.0)

        with patch.object(gate, '_run_mutmut') as mock_run:
            mock_run.return_value = {
                "total_mutants": 200,
                "killed": 150,
                "survived": 40,
                "timeout": 5,
                "suspicious": 5,
                "skipped": 0,
                "survived_mutants": []
            }
            result = gate.run(target_path="src/")
            assert result.score == 75.0  # 150/200 * 100


# ============================================================================
# Test: Gate fails when mutation score < threshold
# ============================================================================

class TestMutationScoreFail:
    """Test that gate fails when mutation score is below threshold."""

    def test_fails_when_score_below_threshold(self):
        """Gate should fail when score is below threshold."""
        from swarm_attack.testing.mutation_test_gate import MutationTestGate
        gate = MutationTestGate(min_score=60.0)

        with patch.object(gate, '_run_mutmut') as mock_run:
            mock_run.return_value = {
                "total_mutants": 100,
                "killed": 50,
                "survived": 45,
                "timeout": 3,
                "suspicious": 2,
                "skipped": 0,
                "survived_mutants": []
            }
            result = gate.run(target_path="src/")
            assert result.passed is False
            assert result.score == 50.0

    def test_failure_includes_survived_mutants(self):
        """Failed result should include survived mutant details."""
        from swarm_attack.testing.mutation_test_gate import MutationTestGate
        gate = MutationTestGate(min_score=60.0)

        survived_list = [
            {"id": 1, "file": "src/calc.py", "line": 10, "description": "Changed + to -", "status": "survived"},
            {"id": 2, "file": "src/calc.py", "line": 15, "description": "Removed return", "status": "survived"}
        ]

        with patch.object(gate, '_run_mutmut') as mock_run:
            mock_run.return_value = {
                "total_mutants": 100,
                "killed": 50,
                "survived": 45,
                "timeout": 3,
                "suspicious": 2,
                "skipped": 0,
                "survived_mutants": survived_list
            }
            result = gate.run(target_path="src/")
            assert len(result.survived_mutants) == 2
            assert result.survived_mutants[0].file == "src/calc.py"


# ============================================================================
# Test: Configurable thresholds per project
# ============================================================================

class TestConfigurableThresholds:
    """Test configurable thresholds per project."""

    def test_can_set_custom_threshold(self):
        """Should be able to set custom threshold."""
        from swarm_attack.testing.mutation_test_gate import MutationTestGate
        gate = MutationTestGate(min_score=80.0)

        with patch.object(gate, '_run_mutmut') as mock_run:
            mock_run.return_value = {
                "total_mutants": 100,
                "killed": 75,
                "survived": 20,
                "timeout": 3,
                "suspicious": 2,
                "skipped": 0,
                "survived_mutants": []
            }
            result = gate.run(target_path="src/")
            assert result.passed is False  # 75% < 80%
            assert result.min_score_required == 80.0

    def test_strict_mode_requires_90_percent(self):
        """Strict mode should require 90% score."""
        from swarm_attack.testing.mutation_test_gate import MutationTestGate
        gate = MutationTestGate(min_score=90.0)

        with patch.object(gate, '_run_mutmut') as mock_run:
            mock_run.return_value = {
                "total_mutants": 100,
                "killed": 85,
                "survived": 10,
                "timeout": 3,
                "suspicious": 2,
                "skipped": 0,
                "survived_mutants": []
            }
            result = gate.run(target_path="src/")
            assert result.passed is False

    def test_lenient_mode_requires_40_percent(self):
        """Lenient mode should only require 40% score."""
        from swarm_attack.testing.mutation_test_gate import MutationTestGate
        gate = MutationTestGate(min_score=40.0)

        with patch.object(gate, '_run_mutmut') as mock_run:
            mock_run.return_value = {
                "total_mutants": 100,
                "killed": 45,
                "survived": 50,
                "timeout": 3,
                "suspicious": 2,
                "skipped": 0,
                "survived_mutants": []
            }
            result = gate.run(target_path="src/")
            assert result.passed is True

    def test_from_config_loads_threshold(self, mock_config):
        """Should load threshold from config object."""
        from swarm_attack.testing.mutation_test_gate import MutationTestGate
        gate = MutationTestGate.from_config(mock_config)
        assert gate.min_score == 60.0


# ============================================================================
# Test: Integration with mutmut tool
# ============================================================================

class TestMutmutIntegration:
    """Test integration with mutmut mutation testing tool."""

    def test_runs_mutmut_command(self):
        """Should run mutmut command."""
        from swarm_attack.testing.mutation_test_gate import MutationTestGate
        gate = MutationTestGate(tool="mutmut")

        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout='{"total_mutants": 10, "killed": 8, "survived": 2, "timeout": 0, "suspicious": 0, "skipped": 0, "survived_mutants": []}',
                stderr=""
            )
            gate.run(target_path="src/")

            # Verify mutmut was called
            mock_run.assert_called()
            call_args = mock_run.call_args
            assert "mutmut" in str(call_args)

    def test_parses_mutmut_json_output(self):
        """Should parse mutmut JSON output correctly."""
        from swarm_attack.testing.mutation_test_gate import MutationTestGate
        gate = MutationTestGate()

        json_output = json.dumps({
            "total_mutants": 100,
            "killed": 70,
            "survived": 25,
            "timeout": 3,
            "suspicious": 2,
            "skipped": 0,
            "survived_mutants": []
        })

        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout=json_output,
                stderr=""
            )
            result = gate.run(target_path="src/")
            assert result.total_mutants == 100
            assert result.killed == 70

    def test_handles_mutmut_timeout(self):
        """Should handle mutmut timeout gracefully."""
        from swarm_attack.testing.mutation_test_gate import MutationTestGate
        gate = MutationTestGate(timeout_seconds=10)

        with patch('subprocess.run') as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired(cmd="mutmut", timeout=10)
            result = gate.run(target_path="src/")
            assert result.passed is False
            assert "timeout" in result.error.lower()

    def test_handles_mutmut_not_installed(self):
        """Should handle mutmut not being installed."""
        from swarm_attack.testing.mutation_test_gate import MutationTestGate
        gate = MutationTestGate()

        with patch('subprocess.run') as mock_run:
            mock_run.side_effect = FileNotFoundError("mutmut not found")
            result = gate.run(target_path="src/")
            assert result.passed is False
            assert result.error is not None


# ============================================================================
# Test: Detailed mutation survival reports
# ============================================================================

class TestMutationSurvivalReports:
    """Test detailed mutation survival report generation."""

    def test_generates_survival_report(self, temp_swarm_dir):
        """Should generate detailed survival report."""
        from swarm_attack.testing.mutation_test_gate import MutationTestGate
        gate = MutationTestGate(report_dir=temp_swarm_dir / "mutation-reports")

        survived_list = [
            {"id": 1, "file": "src/calc.py", "line": 10, "description": "Changed + to -", "status": "survived"},
            {"id": 2, "file": "src/calc.py", "line": 15, "description": "Removed return", "status": "survived"}
        ]

        with patch.object(gate, '_run_mutmut') as mock_run:
            mock_run.return_value = {
                "total_mutants": 100,
                "killed": 50,
                "survived": 45,
                "timeout": 3,
                "suspicious": 2,
                "skipped": 0,
                "survived_mutants": survived_list
            }
            result = gate.run(target_path="src/")

            # Report should be generated
            assert result.report_path is not None
            assert Path(result.report_path).exists()

    def test_report_contains_survived_mutants(self, temp_swarm_dir):
        """Report should contain details of survived mutants."""
        from swarm_attack.testing.mutation_test_gate import MutationTestGate
        gate = MutationTestGate(report_dir=temp_swarm_dir / "mutation-reports")

        survived_list = [
            {"id": 1, "file": "src/calc.py", "line": 10, "description": "Changed + to -", "status": "survived"}
        ]

        with patch.object(gate, '_run_mutmut') as mock_run:
            mock_run.return_value = {
                "total_mutants": 100,
                "killed": 50,
                "survived": 45,
                "timeout": 3,
                "suspicious": 2,
                "skipped": 0,
                "survived_mutants": survived_list
            }
            result = gate.run(target_path="src/")

            # Read and verify report content
            with open(result.report_path, 'r') as f:
                content = f.read()
            assert "src/calc.py" in content
            assert "line 10" in content.lower() or "10" in content

    def test_report_includes_score_summary(self, temp_swarm_dir):
        """Report should include mutation score summary."""
        from swarm_attack.testing.mutation_test_gate import MutationTestGate
        gate = MutationTestGate(report_dir=temp_swarm_dir / "mutation-reports")

        with patch.object(gate, '_run_mutmut') as mock_run:
            mock_run.return_value = {
                "total_mutants": 100,
                "killed": 65,
                "survived": 30,
                "timeout": 3,
                "suspicious": 2,
                "skipped": 0,
                "survived_mutants": []
            }
            result = gate.run(target_path="src/")

            with open(result.report_path, 'r') as f:
                content = f.read()
            assert "65" in content  # killed count
            assert "100" in content  # total count

    def test_report_saved_as_json(self, temp_swarm_dir):
        """Report should be saved in JSON format."""
        from swarm_attack.testing.mutation_test_gate import MutationTestGate
        gate = MutationTestGate(report_dir=temp_swarm_dir / "mutation-reports")

        with patch.object(gate, '_run_mutmut') as mock_run:
            mock_run.return_value = {
                "total_mutants": 100,
                "killed": 65,
                "survived": 30,
                "timeout": 3,
                "suspicious": 2,
                "skipped": 0,
                "survived_mutants": []
            }
            result = gate.run(target_path="src/")

            # Should be valid JSON
            with open(result.report_path, 'r') as f:
                report_data = json.load(f)
            assert "score" in report_data
            assert report_data["score"] == 65.0


# ============================================================================
# Test: Edge cases
# ============================================================================

class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_handles_zero_mutants(self):
        """Should handle case with zero mutants gracefully."""
        from swarm_attack.testing.mutation_test_gate import MutationTestGate
        gate = MutationTestGate()

        with patch.object(gate, '_run_mutmut') as mock_run:
            mock_run.return_value = {
                "total_mutants": 0,
                "killed": 0,
                "survived": 0,
                "timeout": 0,
                "suspicious": 0,
                "skipped": 0,
                "survived_mutants": []
            }
            result = gate.run(target_path="src/")
            # Should pass by default when no mutants (nothing to test)
            assert result.passed is True
            assert result.score == 100.0  # Perfect score when nothing to test

    def test_handles_all_mutants_killed(self):
        """Should handle case where all mutants are killed."""
        from swarm_attack.testing.mutation_test_gate import MutationTestGate
        gate = MutationTestGate()

        with patch.object(gate, '_run_mutmut') as mock_run:
            mock_run.return_value = {
                "total_mutants": 50,
                "killed": 50,
                "survived": 0,
                "timeout": 0,
                "suspicious": 0,
                "skipped": 0,
                "survived_mutants": []
            }
            result = gate.run(target_path="src/")
            assert result.passed is True
            assert result.score == 100.0

    def test_handles_invalid_json_output(self):
        """Should handle invalid JSON from mutmut."""
        from swarm_attack.testing.mutation_test_gate import MutationTestGate
        gate = MutationTestGate()

        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout="not valid json {{{",
                stderr=""
            )
            result = gate.run(target_path="src/")
            assert result.passed is False
            assert result.error is not None

    def test_handles_subprocess_error(self):
        """Should handle subprocess execution errors."""
        from swarm_attack.testing.mutation_test_gate import MutationTestGate
        gate = MutationTestGate()

        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                returncode=1,
                stdout="",
                stderr="Error: failed to run"
            )
            result = gate.run(target_path="src/")
            assert result.passed is False
            assert result.error is not None

    def test_accepts_test_path_parameter(self):
        """Should accept test path parameter for targeted testing."""
        from swarm_attack.testing.mutation_test_gate import MutationTestGate
        gate = MutationTestGate()

        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout='{"total_mutants": 10, "killed": 8, "survived": 2, "timeout": 0, "suspicious": 0, "skipped": 0, "survived_mutants": []}',
                stderr=""
            )
            gate.run(target_path="src/module.py", test_path="tests/test_module.py")

            call_args = str(mock_run.call_args)
            assert "tests/test_module.py" in call_args or "test_module" in call_args


# ============================================================================
# Test: Score boundary conditions
# ============================================================================

class TestScoreBoundaryConditions:
    """Test boundary conditions for score calculations."""

    def test_score_at_59_9_fails(self):
        """Score of 59.9% should fail with 60% threshold."""
        from swarm_attack.testing.mutation_test_gate import MutationTestGate
        gate = MutationTestGate(min_score=60.0)

        with patch.object(gate, '_run_mutmut') as mock_run:
            mock_run.return_value = {
                "total_mutants": 1000,
                "killed": 599,  # 59.9%
                "survived": 396,
                "timeout": 3,
                "suspicious": 2,
                "skipped": 0,
                "survived_mutants": []
            }
            result = gate.run(target_path="src/")
            assert result.passed is False

    def test_score_at_60_0_passes(self):
        """Score of exactly 60.0% should pass with 60% threshold."""
        from swarm_attack.testing.mutation_test_gate import MutationTestGate
        gate = MutationTestGate(min_score=60.0)

        with patch.object(gate, '_run_mutmut') as mock_run:
            mock_run.return_value = {
                "total_mutants": 100,
                "killed": 60,  # Exactly 60%
                "survived": 35,
                "timeout": 3,
                "suspicious": 2,
                "skipped": 0,
                "survived_mutants": []
            }
            result = gate.run(target_path="src/")
            assert result.passed is True

    def test_score_rounds_to_two_decimals(self):
        """Score should be rounded to two decimal places."""
        from swarm_attack.testing.mutation_test_gate import MutationTestGate
        gate = MutationTestGate()

        with patch.object(gate, '_run_mutmut') as mock_run:
            mock_run.return_value = {
                "total_mutants": 3,
                "killed": 2,  # 66.666...%
                "survived": 1,
                "timeout": 0,
                "suspicious": 0,
                "skipped": 0,
                "survived_mutants": []
            }
            result = gate.run(target_path="src/")
            assert result.score == 66.67  # Rounded to 2 decimals
