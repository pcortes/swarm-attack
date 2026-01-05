"""TDD Tests for PVI (Plan-Validate-Implement) Pipeline.

This module tests the PVI Pipeline which orchestrates the three-stage process:
1. Plan Stage: Produces implementation plan with structured steps
2. Validate Stage: Runs checks (tests exist, deps resolved)
3. Implement Stage: Executes with verification gates

Each stage creates a handoff for the next stage, enabling clean separation
of concerns and easy recovery from failures.

Tests follow TDD approach - write tests first, then implement to make them pass.
"""

import pytest
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum, auto
from typing import Any, Optional
from unittest.mock import MagicMock, patch, PropertyMock


# =============================================================================
# IMPORT TESTS
# =============================================================================


class TestPVIPipelineImports:
    """Tests to verify PVI Pipeline modules can be imported."""

    def test_can_import_pvi_pipeline_module(self):
        """Should be able to import pvi_pipeline module."""
        from swarm_attack.orchestration import pvi_pipeline
        assert pvi_pipeline is not None

    def test_can_import_pvi_pipeline_class(self):
        """Should be able to import PVIPipeline class."""
        from swarm_attack.orchestration.pvi_pipeline import PVIPipeline
        assert PVIPipeline is not None

    def test_can_import_plan_stage(self):
        """Should be able to import PlanStage class."""
        from swarm_attack.orchestration.pvi_pipeline import PlanStage
        assert PlanStage is not None

    def test_can_import_validate_stage(self):
        """Should be able to import ValidateStage class."""
        from swarm_attack.orchestration.pvi_pipeline import ValidateStage
        assert ValidateStage is not None

    def test_can_import_implement_stage(self):
        """Should be able to import ImplementStage class."""
        from swarm_attack.orchestration.pvi_pipeline import ImplementStage
        assert ImplementStage is not None

    def test_can_import_stage_handoff(self):
        """Should be able to import StageHandoff dataclass."""
        from swarm_attack.orchestration.pvi_pipeline import StageHandoff
        assert StageHandoff is not None

    def test_can_import_plan_result(self):
        """Should be able to import PlanResult dataclass."""
        from swarm_attack.orchestration.pvi_pipeline import PlanResult
        assert PlanResult is not None

    def test_can_import_validation_result(self):
        """Should be able to import ValidationResult dataclass."""
        from swarm_attack.orchestration.pvi_pipeline import ValidationResult
        assert ValidationResult is not None

    def test_can_import_implementation_result(self):
        """Should be able to import ImplementationResult dataclass."""
        from swarm_attack.orchestration.pvi_pipeline import ImplementationResult
        assert ImplementationResult is not None

    def test_can_import_stage_status_enum(self):
        """Should be able to import StageStatus enum."""
        from swarm_attack.orchestration.pvi_pipeline import StageStatus
        assert StageStatus is not None


# =============================================================================
# STAGE STATUS ENUM TESTS
# =============================================================================


class TestStageStatus:
    """Tests for StageStatus enum."""

    def test_has_pending_status(self):
        """StageStatus should have PENDING status."""
        from swarm_attack.orchestration.pvi_pipeline import StageStatus
        assert hasattr(StageStatus, 'PENDING')

    def test_has_running_status(self):
        """StageStatus should have RUNNING status."""
        from swarm_attack.orchestration.pvi_pipeline import StageStatus
        assert hasattr(StageStatus, 'RUNNING')

    def test_has_completed_status(self):
        """StageStatus should have COMPLETED status."""
        from swarm_attack.orchestration.pvi_pipeline import StageStatus
        assert hasattr(StageStatus, 'COMPLETED')

    def test_has_failed_status(self):
        """StageStatus should have FAILED status."""
        from swarm_attack.orchestration.pvi_pipeline import StageStatus
        assert hasattr(StageStatus, 'FAILED')

    def test_has_blocked_status(self):
        """StageStatus should have BLOCKED status."""
        from swarm_attack.orchestration.pvi_pipeline import StageStatus
        assert hasattr(StageStatus, 'BLOCKED')


# =============================================================================
# STAGE HANDOFF TESTS
# =============================================================================


class TestStageHandoff:
    """Tests for StageHandoff dataclass."""

    def test_handoff_has_source_stage(self):
        """StageHandoff should have source_stage field."""
        from swarm_attack.orchestration.pvi_pipeline import StageHandoff
        handoff = StageHandoff(
            source_stage="plan",
            target_stage="validate",
            payload={},
        )
        assert handoff.source_stage == "plan"

    def test_handoff_has_target_stage(self):
        """StageHandoff should have target_stage field."""
        from swarm_attack.orchestration.pvi_pipeline import StageHandoff
        handoff = StageHandoff(
            source_stage="plan",
            target_stage="validate",
            payload={},
        )
        assert handoff.target_stage == "validate"

    def test_handoff_has_payload(self):
        """StageHandoff should have payload dict."""
        from swarm_attack.orchestration.pvi_pipeline import StageHandoff
        payload = {"steps": [{"step": 1, "description": "Do something"}]}
        handoff = StageHandoff(
            source_stage="plan",
            target_stage="validate",
            payload=payload,
        )
        assert handoff.payload == payload

    def test_handoff_has_timestamp(self):
        """StageHandoff should have created_at timestamp."""
        from swarm_attack.orchestration.pvi_pipeline import StageHandoff
        handoff = StageHandoff(
            source_stage="plan",
            target_stage="validate",
            payload={},
        )
        assert hasattr(handoff, 'created_at')
        assert handoff.created_at is not None

    def test_handoff_has_status(self):
        """StageHandoff should have status field."""
        from swarm_attack.orchestration.pvi_pipeline import StageHandoff, StageStatus
        handoff = StageHandoff(
            source_stage="plan",
            target_stage="validate",
            payload={},
        )
        assert hasattr(handoff, 'status')
        assert handoff.status == StageStatus.PENDING

    def test_handoff_to_dict(self):
        """StageHandoff should serialize to dict."""
        from swarm_attack.orchestration.pvi_pipeline import StageHandoff
        handoff = StageHandoff(
            source_stage="plan",
            target_stage="validate",
            payload={"key": "value"},
        )
        data = handoff.to_dict()
        assert isinstance(data, dict)
        assert data["source_stage"] == "plan"
        assert data["target_stage"] == "validate"
        assert data["payload"] == {"key": "value"}

    def test_handoff_from_dict(self):
        """StageHandoff should deserialize from dict."""
        from swarm_attack.orchestration.pvi_pipeline import StageHandoff, StageStatus
        data = {
            "source_stage": "validate",
            "target_stage": "implement",
            "payload": {"validated": True},
            "created_at": "2025-01-01T00:00:00Z",
            "status": "COMPLETED",
        }
        handoff = StageHandoff.from_dict(data)
        assert handoff.source_stage == "validate"
        assert handoff.target_stage == "implement"
        assert handoff.payload == {"validated": True}
        assert handoff.status == StageStatus.COMPLETED


# =============================================================================
# PLAN RESULT TESTS
# =============================================================================


class TestPlanResult:
    """Tests for PlanResult dataclass."""

    def test_plan_result_has_steps(self):
        """PlanResult should have steps list."""
        from swarm_attack.orchestration.pvi_pipeline import PlanResult
        result = PlanResult(
            success=True,
            steps=[],
        )
        assert hasattr(result, 'steps')
        assert isinstance(result.steps, list)

    def test_plan_result_has_success(self):
        """PlanResult should have success boolean."""
        from swarm_attack.orchestration.pvi_pipeline import PlanResult
        result = PlanResult(success=True, steps=[])
        assert result.success is True

    def test_plan_result_step_has_required_fields(self):
        """Each step in PlanResult should have required fields."""
        from swarm_attack.orchestration.pvi_pipeline import PlanResult, PlanStep
        step = PlanStep(
            step_number=1,
            description="Create database schema",
            estimated_complexity="medium",
            dependencies=[],
        )
        result = PlanResult(success=True, steps=[step])
        assert result.steps[0].step_number == 1
        assert result.steps[0].description == "Create database schema"
        assert result.steps[0].estimated_complexity == "medium"

    def test_plan_result_has_total_estimated_complexity(self):
        """PlanResult should have total_estimated_complexity."""
        from swarm_attack.orchestration.pvi_pipeline import PlanResult, PlanStep
        steps = [
            PlanStep(step_number=1, description="Step 1", estimated_complexity="low", dependencies=[]),
            PlanStep(step_number=2, description="Step 2", estimated_complexity="high", dependencies=[1]),
        ]
        result = PlanResult(success=True, steps=steps, total_estimated_complexity="high")
        assert result.total_estimated_complexity == "high"

    def test_plan_result_has_error_on_failure(self):
        """PlanResult should have error message on failure."""
        from swarm_attack.orchestration.pvi_pipeline import PlanResult
        result = PlanResult(
            success=False,
            steps=[],
            error="Failed to generate plan: missing context",
        )
        assert result.success is False
        assert result.error == "Failed to generate plan: missing context"

    def test_plan_result_to_dict(self):
        """PlanResult should serialize to dict."""
        from swarm_attack.orchestration.pvi_pipeline import PlanResult, PlanStep
        step = PlanStep(step_number=1, description="Test", estimated_complexity="low", dependencies=[])
        result = PlanResult(success=True, steps=[step])
        data = result.to_dict()
        assert data["success"] is True
        assert len(data["steps"]) == 1

    def test_plan_result_from_dict(self):
        """PlanResult should deserialize from dict."""
        from swarm_attack.orchestration.pvi_pipeline import PlanResult
        data = {
            "success": True,
            "steps": [
                {"step_number": 1, "description": "Test", "estimated_complexity": "low", "dependencies": []}
            ],
            "total_estimated_complexity": "low",
            "error": None,
        }
        result = PlanResult.from_dict(data)
        assert result.success is True
        assert len(result.steps) == 1


# =============================================================================
# VALIDATION RESULT TESTS
# =============================================================================


class TestValidationResult:
    """Tests for ValidationResult dataclass."""

    def test_validation_result_has_passed(self):
        """ValidationResult should have passed boolean."""
        from swarm_attack.orchestration.pvi_pipeline import ValidationResult
        result = ValidationResult(passed=True, checks=[])
        assert result.passed is True

    def test_validation_result_has_checks_list(self):
        """ValidationResult should have checks list."""
        from swarm_attack.orchestration.pvi_pipeline import ValidationResult, ValidationCheck
        check = ValidationCheck(
            check_name="tests_exist",
            passed=True,
            message="All tests found",
        )
        result = ValidationResult(passed=True, checks=[check])
        assert len(result.checks) == 1
        assert result.checks[0].check_name == "tests_exist"

    def test_validation_check_has_required_fields(self):
        """ValidationCheck should have required fields."""
        from swarm_attack.orchestration.pvi_pipeline import ValidationCheck
        check = ValidationCheck(
            check_name="deps_resolved",
            passed=False,
            message="Missing dependency: requests",
        )
        assert check.check_name == "deps_resolved"
        assert check.passed is False
        assert check.message == "Missing dependency: requests"

    def test_validation_result_blocking_issues(self):
        """ValidationResult should track blocking issues."""
        from swarm_attack.orchestration.pvi_pipeline import ValidationResult, ValidationCheck
        checks = [
            ValidationCheck(check_name="tests_exist", passed=True, message="OK"),
            ValidationCheck(check_name="deps_resolved", passed=False, message="Missing dep", blocking=True),
        ]
        result = ValidationResult(passed=False, checks=checks)
        assert result.has_blocking_issues() is True
        assert len(result.get_blocking_checks()) == 1

    def test_validation_result_to_dict(self):
        """ValidationResult should serialize to dict."""
        from swarm_attack.orchestration.pvi_pipeline import ValidationResult, ValidationCheck
        check = ValidationCheck(check_name="test", passed=True, message="OK")
        result = ValidationResult(passed=True, checks=[check])
        data = result.to_dict()
        assert data["passed"] is True
        assert len(data["checks"]) == 1

    def test_validation_result_from_dict(self):
        """ValidationResult should deserialize from dict."""
        from swarm_attack.orchestration.pvi_pipeline import ValidationResult
        data = {
            "passed": True,
            "checks": [{"check_name": "test", "passed": True, "message": "OK", "blocking": False}],
        }
        result = ValidationResult.from_dict(data)
        assert result.passed is True


# =============================================================================
# IMPLEMENTATION RESULT TESTS
# =============================================================================


class TestImplementationResult:
    """Tests for ImplementationResult dataclass."""

    def test_implementation_result_has_success(self):
        """ImplementationResult should have success boolean."""
        from swarm_attack.orchestration.pvi_pipeline import ImplementationResult
        result = ImplementationResult(success=True, gates_passed=[])
        assert result.success is True

    def test_implementation_result_has_gates_passed(self):
        """ImplementationResult should have gates_passed list."""
        from swarm_attack.orchestration.pvi_pipeline import ImplementationResult, GateResult
        gate = GateResult(gate_name="pre_impl", passed=True)
        result = ImplementationResult(success=True, gates_passed=[gate])
        assert len(result.gates_passed) == 1
        assert result.gates_passed[0].gate_name == "pre_impl"

    def test_implementation_result_has_files_modified(self):
        """ImplementationResult should track files_modified."""
        from swarm_attack.orchestration.pvi_pipeline import ImplementationResult
        result = ImplementationResult(
            success=True,
            gates_passed=[],
            files_modified=["src/api.py", "tests/test_api.py"],
        )
        assert "src/api.py" in result.files_modified

    def test_implementation_result_has_commits(self):
        """ImplementationResult should track commits."""
        from swarm_attack.orchestration.pvi_pipeline import ImplementationResult
        result = ImplementationResult(
            success=True,
            gates_passed=[],
            commits=["abc123", "def456"],
        )
        assert "abc123" in result.commits

    def test_implementation_result_has_error_on_failure(self):
        """ImplementationResult should have error message on failure."""
        from swarm_attack.orchestration.pvi_pipeline import ImplementationResult
        result = ImplementationResult(
            success=False,
            gates_passed=[],
            error="Gate verification failed",
            failed_gate="post_impl",
        )
        assert result.success is False
        assert result.error == "Gate verification failed"
        assert result.failed_gate == "post_impl"

    def test_implementation_result_to_dict(self):
        """ImplementationResult should serialize to dict."""
        from swarm_attack.orchestration.pvi_pipeline import ImplementationResult
        result = ImplementationResult(success=True, gates_passed=[], files_modified=["test.py"])
        data = result.to_dict()
        assert data["success"] is True
        assert "test.py" in data["files_modified"]

    def test_implementation_result_from_dict(self):
        """ImplementationResult should deserialize from dict."""
        from swarm_attack.orchestration.pvi_pipeline import ImplementationResult
        data = {
            "success": True,
            "gates_passed": [],
            "files_modified": ["test.py"],
            "commits": [],
            "error": None,
            "failed_gate": None,
        }
        result = ImplementationResult.from_dict(data)
        assert result.success is True


# =============================================================================
# PLAN STAGE TESTS
# =============================================================================


class TestPlanStage:
    """Tests for PlanStage class."""

    @pytest.fixture
    def mock_config(self, tmp_path):
        """Create mock config."""
        config = MagicMock()
        config.repo_root = str(tmp_path)
        return config

    def test_plan_stage_initialization(self, mock_config):
        """PlanStage should initialize with config."""
        from swarm_attack.orchestration.pvi_pipeline import PlanStage
        stage = PlanStage(mock_config)
        assert stage.config == mock_config
        assert stage.name == "plan"

    def test_plan_stage_run_returns_plan_result(self, mock_config):
        """PlanStage.run() should return PlanResult."""
        from swarm_attack.orchestration.pvi_pipeline import PlanStage, PlanResult

        stage = PlanStage(mock_config)

        with patch.object(stage, '_generate_plan') as mock_gen:
            mock_gen.return_value = PlanResult(success=True, steps=[])
            result = stage.run(context={"issue_number": 42, "feature_id": "test"})

        assert isinstance(result, PlanResult)

    def test_plan_stage_produces_steps(self, mock_config):
        """PlanStage should produce implementation steps."""
        from swarm_attack.orchestration.pvi_pipeline import PlanStage, PlanResult, PlanStep

        stage = PlanStage(mock_config)
        steps = [
            PlanStep(step_number=1, description="Create model", estimated_complexity="low", dependencies=[]),
            PlanStep(step_number=2, description="Add API", estimated_complexity="medium", dependencies=[1]),
        ]

        with patch.object(stage, '_generate_plan') as mock_gen:
            mock_gen.return_value = PlanResult(success=True, steps=steps)
            result = stage.run(context={"issue_number": 42, "feature_id": "test"})

        assert len(result.steps) == 2
        assert result.steps[0].description == "Create model"
        assert result.steps[1].dependencies == [1]

    def test_plan_stage_handles_llm_failure(self, mock_config):
        """PlanStage should handle LLM failures gracefully."""
        from swarm_attack.orchestration.pvi_pipeline import PlanStage, PlanResult

        stage = PlanStage(mock_config)

        with patch.object(stage, '_generate_plan') as mock_gen:
            mock_gen.side_effect = Exception("LLM timeout")
            result = stage.run(context={"issue_number": 42, "feature_id": "test"})

        assert result.success is False
        assert "LLM timeout" in result.error

    def test_plan_stage_creates_handoff(self, mock_config):
        """PlanStage should create handoff for validate stage."""
        from swarm_attack.orchestration.pvi_pipeline import PlanStage, StageHandoff, PlanResult, PlanStep

        stage = PlanStage(mock_config)
        steps = [PlanStep(step_number=1, description="Test", estimated_complexity="low", dependencies=[])]

        with patch.object(stage, '_generate_plan') as mock_gen:
            mock_gen.return_value = PlanResult(success=True, steps=steps)
            result = stage.run(context={"issue_number": 42, "feature_id": "test"})
            handoff = stage.create_handoff(result)

        assert isinstance(handoff, StageHandoff)
        assert handoff.source_stage == "plan"
        assert handoff.target_stage == "validate"
        assert "steps" in handoff.payload

    def test_plan_stage_validates_context(self, mock_config):
        """PlanStage should validate required context fields."""
        from swarm_attack.orchestration.pvi_pipeline import PlanStage

        stage = PlanStage(mock_config)

        # Missing required fields should raise
        with pytest.raises(ValueError, match="issue_number"):
            stage.run(context={"feature_id": "test"})

    def test_plan_stage_estimates_complexity(self, mock_config):
        """PlanStage should estimate overall complexity."""
        from swarm_attack.orchestration.pvi_pipeline import PlanStage, PlanResult, PlanStep

        stage = PlanStage(mock_config)
        steps = [
            PlanStep(step_number=1, description="Step 1", estimated_complexity="low", dependencies=[]),
            PlanStep(step_number=2, description="Step 2", estimated_complexity="high", dependencies=[]),
        ]

        with patch.object(stage, '_generate_plan') as mock_gen:
            mock_gen.return_value = PlanResult(
                success=True,
                steps=steps,
                total_estimated_complexity="high"
            )
            result = stage.run(context={"issue_number": 42, "feature_id": "test"})

        assert result.total_estimated_complexity == "high"


# =============================================================================
# VALIDATE STAGE TESTS
# =============================================================================


class TestValidateStage:
    """Tests for ValidateStage class."""

    @pytest.fixture
    def mock_config(self, tmp_path):
        """Create mock config."""
        config = MagicMock()
        config.repo_root = str(tmp_path)
        return config

    @pytest.fixture
    def sample_handoff(self):
        """Create sample handoff from plan stage."""
        from swarm_attack.orchestration.pvi_pipeline import StageHandoff
        return StageHandoff(
            source_stage="plan",
            target_stage="validate",
            payload={
                "steps": [
                    {"step_number": 1, "description": "Create model", "dependencies": []},
                ],
                "feature_id": "test-feature",
                "issue_number": 42,
            },
        )

    def test_validate_stage_initialization(self, mock_config):
        """ValidateStage should initialize with config."""
        from swarm_attack.orchestration.pvi_pipeline import ValidateStage
        stage = ValidateStage(mock_config)
        assert stage.config == mock_config
        assert stage.name == "validate"

    def test_validate_stage_run_returns_validation_result(self, mock_config, sample_handoff):
        """ValidateStage.run() should return ValidationResult."""
        from swarm_attack.orchestration.pvi_pipeline import ValidateStage, ValidationResult

        stage = ValidateStage(mock_config)

        with patch.object(stage, '_run_checks') as mock_checks:
            mock_checks.return_value = ValidationResult(passed=True, checks=[])
            result = stage.run(handoff=sample_handoff)

        assert isinstance(result, ValidationResult)

    def test_validate_stage_checks_tests_exist(self, mock_config, sample_handoff):
        """ValidateStage should check if tests exist."""
        from swarm_attack.orchestration.pvi_pipeline import ValidateStage, ValidationResult, ValidationCheck

        stage = ValidateStage(mock_config)
        checks = [ValidationCheck(check_name="tests_exist", passed=True, message="Tests found")]

        with patch.object(stage, '_run_checks') as mock_checks:
            mock_checks.return_value = ValidationResult(passed=True, checks=checks)
            result = stage.run(handoff=sample_handoff)

        assert any(c.check_name == "tests_exist" for c in result.checks)

    def test_validate_stage_checks_deps_resolved(self, mock_config, sample_handoff):
        """ValidateStage should check if dependencies are resolved."""
        from swarm_attack.orchestration.pvi_pipeline import ValidateStage, ValidationResult, ValidationCheck

        stage = ValidateStage(mock_config)
        checks = [
            ValidationCheck(check_name="tests_exist", passed=True, message="OK"),
            ValidationCheck(check_name="deps_resolved", passed=True, message="All deps available"),
        ]

        with patch.object(stage, '_run_checks') as mock_checks:
            mock_checks.return_value = ValidationResult(passed=True, checks=checks)
            result = stage.run(handoff=sample_handoff)

        assert any(c.check_name == "deps_resolved" for c in result.checks)

    def test_validate_stage_fails_on_missing_tests(self, mock_config, sample_handoff):
        """ValidateStage should fail if tests don't exist."""
        from swarm_attack.orchestration.pvi_pipeline import ValidateStage, ValidationResult, ValidationCheck

        stage = ValidateStage(mock_config)
        checks = [
            ValidationCheck(check_name="tests_exist", passed=False, message="No tests found", blocking=True),
        ]

        with patch.object(stage, '_run_checks') as mock_checks:
            mock_checks.return_value = ValidationResult(passed=False, checks=checks)
            result = stage.run(handoff=sample_handoff)

        assert result.passed is False
        assert result.has_blocking_issues()

    def test_validate_stage_creates_handoff(self, mock_config, sample_handoff):
        """ValidateStage should create handoff for implement stage."""
        from swarm_attack.orchestration.pvi_pipeline import ValidateStage, StageHandoff, ValidationResult, ValidationCheck

        stage = ValidateStage(mock_config)
        checks = [ValidationCheck(check_name="tests_exist", passed=True, message="OK")]

        with patch.object(stage, '_run_checks') as mock_checks:
            mock_checks.return_value = ValidationResult(passed=True, checks=checks)
            result = stage.run(handoff=sample_handoff)
            handoff = stage.create_handoff(result, sample_handoff)

        assert isinstance(handoff, StageHandoff)
        assert handoff.source_stage == "validate"
        assert handoff.target_stage == "implement"

    def test_validate_stage_rejects_invalid_handoff(self, mock_config):
        """ValidateStage should reject handoff from wrong source."""
        from swarm_attack.orchestration.pvi_pipeline import ValidateStage, StageHandoff

        stage = ValidateStage(mock_config)
        wrong_handoff = StageHandoff(
            source_stage="implement",  # Wrong source
            target_stage="validate",
            payload={},
        )

        with pytest.raises(ValueError, match="Expected handoff from plan"):
            stage.run(handoff=wrong_handoff)

    def test_validate_stage_runs_custom_validators(self, mock_config, sample_handoff):
        """ValidateStage should support custom validators."""
        from swarm_attack.orchestration.pvi_pipeline import ValidateStage, ValidationResult, ValidationCheck

        def custom_check(context):
            return ValidationCheck(check_name="custom", passed=True, message="Custom check passed")

        stage = ValidateStage(mock_config, custom_validators=[custom_check])
        checks = [
            ValidationCheck(check_name="tests_exist", passed=True, message="OK"),
            ValidationCheck(check_name="custom", passed=True, message="Custom check passed"),
        ]

        with patch.object(stage, '_run_checks') as mock_checks:
            mock_checks.return_value = ValidationResult(passed=True, checks=checks)
            result = stage.run(handoff=sample_handoff)

        assert any(c.check_name == "custom" for c in result.checks)


# =============================================================================
# IMPLEMENT STAGE TESTS
# =============================================================================


class TestImplementStage:
    """Tests for ImplementStage class."""

    @pytest.fixture
    def mock_config(self, tmp_path):
        """Create mock config."""
        config = MagicMock()
        config.repo_root = str(tmp_path)
        return config

    @pytest.fixture
    def sample_handoff(self):
        """Create sample handoff from validate stage."""
        from swarm_attack.orchestration.pvi_pipeline import StageHandoff
        return StageHandoff(
            source_stage="validate",
            target_stage="implement",
            payload={
                "steps": [
                    {"step_number": 1, "description": "Create model", "dependencies": []},
                ],
                "feature_id": "test-feature",
                "issue_number": 42,
                "validation_passed": True,
            },
        )

    def test_implement_stage_initialization(self, mock_config):
        """ImplementStage should initialize with config."""
        from swarm_attack.orchestration.pvi_pipeline import ImplementStage
        stage = ImplementStage(mock_config)
        assert stage.config == mock_config
        assert stage.name == "implement"

    def test_implement_stage_run_returns_implementation_result(self, mock_config, sample_handoff):
        """ImplementStage.run() should return ImplementationResult."""
        from swarm_attack.orchestration.pvi_pipeline import ImplementStage, ImplementationResult

        stage = ImplementStage(mock_config)

        with patch.object(stage, '_execute_implementation') as mock_impl:
            mock_impl.return_value = ImplementationResult(success=True, gates_passed=[])
            result = stage.run(handoff=sample_handoff)

        assert isinstance(result, ImplementationResult)

    def test_implement_stage_runs_pre_gate(self, mock_config, sample_handoff):
        """ImplementStage should run pre-implementation gate."""
        from swarm_attack.orchestration.pvi_pipeline import ImplementStage, ImplementationResult, GateResult

        stage = ImplementStage(mock_config)
        gates = [GateResult(gate_name="pre_impl", passed=True)]

        with patch.object(stage, '_execute_implementation') as mock_impl:
            mock_impl.return_value = ImplementationResult(success=True, gates_passed=gates)
            result = stage.run(handoff=sample_handoff)

        assert any(g.gate_name == "pre_impl" for g in result.gates_passed)

    def test_implement_stage_runs_post_gate(self, mock_config, sample_handoff):
        """ImplementStage should run post-implementation gate."""
        from swarm_attack.orchestration.pvi_pipeline import ImplementStage, ImplementationResult, GateResult

        stage = ImplementStage(mock_config)
        gates = [
            GateResult(gate_name="pre_impl", passed=True),
            GateResult(gate_name="post_impl", passed=True),
        ]

        with patch.object(stage, '_execute_implementation') as mock_impl:
            mock_impl.return_value = ImplementationResult(success=True, gates_passed=gates)
            result = stage.run(handoff=sample_handoff)

        assert any(g.gate_name == "post_impl" for g in result.gates_passed)

    def test_implement_stage_fails_on_pre_gate_failure(self, mock_config, sample_handoff):
        """ImplementStage should fail if pre-gate fails."""
        from swarm_attack.orchestration.pvi_pipeline import ImplementStage, ImplementationResult, GateResult

        stage = ImplementStage(mock_config)
        gates = [GateResult(gate_name="pre_impl", passed=False, error="Tests failing")]

        with patch.object(stage, '_execute_implementation') as mock_impl:
            mock_impl.return_value = ImplementationResult(
                success=False,
                gates_passed=gates,
                error="Pre-implementation gate failed",
                failed_gate="pre_impl",
            )
            result = stage.run(handoff=sample_handoff)

        assert result.success is False
        assert result.failed_gate == "pre_impl"

    def test_implement_stage_fails_on_post_gate_failure(self, mock_config, sample_handoff):
        """ImplementStage should fail if post-gate fails."""
        from swarm_attack.orchestration.pvi_pipeline import ImplementStage, ImplementationResult, GateResult

        stage = ImplementStage(mock_config)
        gates = [
            GateResult(gate_name="pre_impl", passed=True),
            GateResult(gate_name="post_impl", passed=False, error="Tests broke"),
        ]

        with patch.object(stage, '_execute_implementation') as mock_impl:
            mock_impl.return_value = ImplementationResult(
                success=False,
                gates_passed=gates,
                error="Post-implementation gate failed",
                failed_gate="post_impl",
            )
            result = stage.run(handoff=sample_handoff)

        assert result.success is False
        assert result.failed_gate == "post_impl"

    def test_implement_stage_tracks_modified_files(self, mock_config, sample_handoff):
        """ImplementStage should track modified files."""
        from swarm_attack.orchestration.pvi_pipeline import ImplementStage, ImplementationResult

        stage = ImplementStage(mock_config)

        with patch.object(stage, '_execute_implementation') as mock_impl:
            mock_impl.return_value = ImplementationResult(
                success=True,
                gates_passed=[],
                files_modified=["src/model.py", "tests/test_model.py"],
            )
            result = stage.run(handoff=sample_handoff)

        assert "src/model.py" in result.files_modified
        assert "tests/test_model.py" in result.files_modified

    def test_implement_stage_tracks_commits(self, mock_config, sample_handoff):
        """ImplementStage should track commits made."""
        from swarm_attack.orchestration.pvi_pipeline import ImplementStage, ImplementationResult

        stage = ImplementStage(mock_config)

        with patch.object(stage, '_execute_implementation') as mock_impl:
            mock_impl.return_value = ImplementationResult(
                success=True,
                gates_passed=[],
                commits=["abc123"],
            )
            result = stage.run(handoff=sample_handoff)

        assert "abc123" in result.commits

    def test_implement_stage_rejects_invalid_handoff(self, mock_config):
        """ImplementStage should reject handoff from wrong source."""
        from swarm_attack.orchestration.pvi_pipeline import ImplementStage, StageHandoff

        stage = ImplementStage(mock_config)
        wrong_handoff = StageHandoff(
            source_stage="plan",  # Wrong source, should be validate
            target_stage="implement",
            payload={},
        )

        with pytest.raises(ValueError, match="Expected handoff from validate"):
            stage.run(handoff=wrong_handoff)

    def test_implement_stage_rejects_failed_validation(self, mock_config):
        """ImplementStage should reject handoff where validation failed."""
        from swarm_attack.orchestration.pvi_pipeline import ImplementStage, StageHandoff

        stage = ImplementStage(mock_config)
        failed_handoff = StageHandoff(
            source_stage="validate",
            target_stage="implement",
            payload={"validation_passed": False},
        )

        with pytest.raises(ValueError, match="Validation did not pass"):
            stage.run(handoff=failed_handoff)


# =============================================================================
# PIPELINE HANDOFFS TESTS
# =============================================================================


class TestPipelineHandoffs:
    """Tests for stage-to-stage handoffs in the pipeline."""

    @pytest.fixture
    def mock_config(self, tmp_path):
        """Create mock config."""
        config = MagicMock()
        config.repo_root = str(tmp_path)
        return config

    def test_plan_to_validate_handoff_contains_steps(self, mock_config):
        """Plan to validate handoff should contain implementation steps."""
        from swarm_attack.orchestration.pvi_pipeline import PlanStage, PlanResult, PlanStep, StageHandoff

        stage = PlanStage(mock_config)
        steps = [
            PlanStep(step_number=1, description="Create model", estimated_complexity="low", dependencies=[]),
            PlanStep(step_number=2, description="Add API", estimated_complexity="medium", dependencies=[1]),
        ]
        result = PlanResult(success=True, steps=steps)
        handoff = stage.create_handoff(result)

        assert "steps" in handoff.payload
        assert len(handoff.payload["steps"]) == 2

    def test_plan_to_validate_handoff_contains_context(self, mock_config):
        """Plan to validate handoff should preserve context."""
        from swarm_attack.orchestration.pvi_pipeline import PlanStage, PlanResult, PlanStep

        stage = PlanStage(mock_config)
        context = {"feature_id": "test-feature", "issue_number": 42}

        with patch.object(stage, '_generate_plan') as mock_gen:
            mock_gen.return_value = PlanResult(success=True, steps=[])
            stage.run(context=context)
            handoff = stage.create_handoff(
                PlanResult(success=True, steps=[]),
                context=context
            )

        assert handoff.payload["feature_id"] == "test-feature"
        assert handoff.payload["issue_number"] == 42

    def test_validate_to_implement_handoff_contains_validation_status(self, mock_config):
        """Validate to implement handoff should contain validation status."""
        from swarm_attack.orchestration.pvi_pipeline import (
            ValidateStage, ValidationResult, ValidationCheck, StageHandoff
        )

        stage = ValidateStage(mock_config)
        plan_handoff = StageHandoff(
            source_stage="plan",
            target_stage="validate",
            payload={"steps": [], "feature_id": "test", "issue_number": 1},
        )
        checks = [ValidationCheck(check_name="tests_exist", passed=True, message="OK")]

        with patch.object(stage, '_run_checks') as mock_checks:
            mock_checks.return_value = ValidationResult(passed=True, checks=checks)
            result = stage.run(handoff=plan_handoff)
            handoff = stage.create_handoff(result, plan_handoff)

        assert handoff.payload["validation_passed"] is True

    def test_validate_to_implement_handoff_contains_steps_from_plan(self, mock_config):
        """Validate to implement handoff should pass through steps from plan."""
        from swarm_attack.orchestration.pvi_pipeline import (
            ValidateStage, ValidationResult, ValidationCheck, StageHandoff
        )

        stage = ValidateStage(mock_config)
        plan_handoff = StageHandoff(
            source_stage="plan",
            target_stage="validate",
            payload={
                "steps": [{"step_number": 1, "description": "Test step"}],
                "feature_id": "test",
                "issue_number": 1,
            },
        )

        with patch.object(stage, '_run_checks') as mock_checks:
            mock_checks.return_value = ValidationResult(passed=True, checks=[])
            result = stage.run(handoff=plan_handoff)
            handoff = stage.create_handoff(result, plan_handoff)

        assert "steps" in handoff.payload
        assert len(handoff.payload["steps"]) == 1

    def test_handoff_chain_preserves_feature_context(self, mock_config):
        """Handoffs should preserve feature context through the pipeline."""
        from swarm_attack.orchestration.pvi_pipeline import (
            PlanStage, ValidateStage, ImplementStage,
            PlanResult, PlanStep, ValidationResult, ValidationCheck,
            StageHandoff
        )

        # Create stages
        plan_stage = PlanStage(mock_config)
        validate_stage = ValidateStage(mock_config)
        implement_stage = ImplementStage(mock_config)

        # Initial context
        initial_context = {
            "feature_id": "my-cool-feature",
            "issue_number": 123,
            "branch": "feature/my-cool-feature",
        }

        # Mock plan stage
        with patch.object(plan_stage, '_generate_plan') as mock_plan:
            mock_plan.return_value = PlanResult(
                success=True,
                steps=[PlanStep(step_number=1, description="Test", estimated_complexity="low", dependencies=[])],
            )
            plan_result = plan_stage.run(context=initial_context)
            plan_handoff = plan_stage.create_handoff(plan_result, context=initial_context)

        # Mock validate stage
        with patch.object(validate_stage, '_run_checks') as mock_validate:
            mock_validate.return_value = ValidationResult(passed=True, checks=[])
            validate_result = validate_stage.run(handoff=plan_handoff)
            validate_handoff = validate_stage.create_handoff(validate_result, plan_handoff)

        # Verify context preserved
        assert validate_handoff.payload["feature_id"] == "my-cool-feature"
        assert validate_handoff.payload["issue_number"] == 123

    def test_handoff_includes_timestamp(self, mock_config):
        """Each handoff should include a timestamp."""
        from swarm_attack.orchestration.pvi_pipeline import PlanStage, PlanResult

        stage = PlanStage(mock_config)
        result = PlanResult(success=True, steps=[])
        handoff = stage.create_handoff(result)

        assert handoff.created_at is not None
        # Should be parseable as ISO format
        datetime.fromisoformat(handoff.created_at.replace("Z", "+00:00"))

    def test_failed_plan_does_not_create_handoff(self, mock_config):
        """Failed plan stage should not create a valid handoff."""
        from swarm_attack.orchestration.pvi_pipeline import PlanStage, PlanResult, StageStatus

        stage = PlanStage(mock_config)
        failed_result = PlanResult(success=False, steps=[], error="Planning failed")
        handoff = stage.create_handoff(failed_result)

        assert handoff.status == StageStatus.FAILED

    def test_failed_validation_creates_blocked_handoff(self, mock_config):
        """Failed validation should create a blocked handoff."""
        from swarm_attack.orchestration.pvi_pipeline import (
            ValidateStage, ValidationResult, ValidationCheck, StageHandoff, StageStatus
        )

        stage = ValidateStage(mock_config)
        plan_handoff = StageHandoff(
            source_stage="plan",
            target_stage="validate",
            payload={"steps": [], "feature_id": "test", "issue_number": 1},
        )
        checks = [
            ValidationCheck(check_name="tests_exist", passed=False, message="No tests", blocking=True)
        ]

        with patch.object(stage, '_run_checks') as mock_checks:
            mock_checks.return_value = ValidationResult(passed=False, checks=checks)
            result = stage.run(handoff=plan_handoff)
            handoff = stage.create_handoff(result, plan_handoff)

        assert handoff.status == StageStatus.BLOCKED


# =============================================================================
# PVI PIPELINE ORCHESTRATION TESTS
# =============================================================================


class TestPVIPipeline:
    """Tests for the full PVI Pipeline orchestration."""

    @pytest.fixture
    def mock_config(self, tmp_path):
        """Create mock config."""
        config = MagicMock()
        config.repo_root = str(tmp_path)
        return config

    def test_pipeline_initialization(self, mock_config):
        """PVIPipeline should initialize with config."""
        from swarm_attack.orchestration.pvi_pipeline import PVIPipeline
        pipeline = PVIPipeline(mock_config)
        assert pipeline.config == mock_config
        assert pipeline.plan_stage is not None
        assert pipeline.validate_stage is not None
        assert pipeline.implement_stage is not None

    def test_pipeline_run_executes_all_stages(self, mock_config):
        """PVIPipeline.run() should execute all three stages."""
        from swarm_attack.orchestration.pvi_pipeline import (
            PVIPipeline, PlanResult, PlanStep, ValidationResult, ImplementationResult
        )

        pipeline = PVIPipeline(mock_config)

        with patch.object(pipeline.plan_stage, 'run') as mock_plan, \
             patch.object(pipeline.validate_stage, 'run') as mock_validate, \
             patch.object(pipeline.implement_stage, 'run') as mock_implement:

            mock_plan.return_value = PlanResult(success=True, steps=[])
            mock_validate.return_value = ValidationResult(passed=True, checks=[])
            mock_implement.return_value = ImplementationResult(success=True, gates_passed=[])

            # Need to patch create_handoff methods as well
            with patch.object(pipeline.plan_stage, 'create_handoff') as mock_plan_handoff, \
                 patch.object(pipeline.validate_stage, 'create_handoff') as mock_validate_handoff:

                from swarm_attack.orchestration.pvi_pipeline import StageHandoff, StageStatus
                mock_plan_handoff.return_value = StageHandoff(
                    source_stage="plan",
                    target_stage="validate",
                    payload={"steps": []},
                    status=StageStatus.COMPLETED,
                )
                mock_validate_handoff.return_value = StageHandoff(
                    source_stage="validate",
                    target_stage="implement",
                    payload={"validation_passed": True},
                    status=StageStatus.COMPLETED,
                )

                result = pipeline.run(context={"feature_id": "test", "issue_number": 1})

        mock_plan.assert_called_once()
        mock_validate.assert_called_once()
        mock_implement.assert_called_once()

    def test_pipeline_stops_on_plan_failure(self, mock_config):
        """Pipeline should stop if plan stage fails."""
        from swarm_attack.orchestration.pvi_pipeline import PVIPipeline, PlanResult

        pipeline = PVIPipeline(mock_config)

        with patch.object(pipeline.plan_stage, 'run') as mock_plan:
            mock_plan.return_value = PlanResult(success=False, steps=[], error="Plan failed")

            with patch.object(pipeline.plan_stage, 'create_handoff') as mock_handoff:
                from swarm_attack.orchestration.pvi_pipeline import StageHandoff, StageStatus
                mock_handoff.return_value = StageHandoff(
                    source_stage="plan",
                    target_stage="validate",
                    payload={},
                    status=StageStatus.FAILED,
                )

                result = pipeline.run(context={"feature_id": "test", "issue_number": 1})

        assert result.success is False
        assert result.failed_stage == "plan"

    def test_pipeline_stops_on_validation_failure(self, mock_config):
        """Pipeline should stop if validation stage fails."""
        from swarm_attack.orchestration.pvi_pipeline import (
            PVIPipeline, PlanResult, ValidationResult, ValidationCheck
        )

        pipeline = PVIPipeline(mock_config)

        with patch.object(pipeline.plan_stage, 'run') as mock_plan, \
             patch.object(pipeline.validate_stage, 'run') as mock_validate:

            mock_plan.return_value = PlanResult(success=True, steps=[])
            mock_validate.return_value = ValidationResult(
                passed=False,
                checks=[ValidationCheck(check_name="test", passed=False, message="Failed", blocking=True)]
            )

            with patch.object(pipeline.plan_stage, 'create_handoff') as mock_plan_handoff, \
                 patch.object(pipeline.validate_stage, 'create_handoff') as mock_validate_handoff:

                from swarm_attack.orchestration.pvi_pipeline import StageHandoff, StageStatus
                mock_plan_handoff.return_value = StageHandoff(
                    source_stage="plan",
                    target_stage="validate",
                    payload={"steps": []},
                    status=StageStatus.COMPLETED,
                )
                mock_validate_handoff.return_value = StageHandoff(
                    source_stage="validate",
                    target_stage="implement",
                    payload={},
                    status=StageStatus.BLOCKED,
                )

                result = pipeline.run(context={"feature_id": "test", "issue_number": 1})

        assert result.success is False
        assert result.failed_stage == "validate"

    def test_pipeline_returns_full_result_on_success(self, mock_config):
        """Pipeline should return comprehensive result on success."""
        from swarm_attack.orchestration.pvi_pipeline import (
            PVIPipeline, PlanResult, PlanStep, ValidationResult,
            ImplementationResult, GateResult, PipelineResult
        )

        pipeline = PVIPipeline(mock_config)

        with patch.object(pipeline.plan_stage, 'run') as mock_plan, \
             patch.object(pipeline.validate_stage, 'run') as mock_validate, \
             patch.object(pipeline.implement_stage, 'run') as mock_implement:

            mock_plan.return_value = PlanResult(
                success=True,
                steps=[PlanStep(step_number=1, description="Test", estimated_complexity="low", dependencies=[])]
            )
            mock_validate.return_value = ValidationResult(passed=True, checks=[])
            mock_implement.return_value = ImplementationResult(
                success=True,
                gates_passed=[GateResult(gate_name="post_impl", passed=True)],
                files_modified=["test.py"],
                commits=["abc123"],
            )

            with patch.object(pipeline.plan_stage, 'create_handoff') as mock_plan_handoff, \
                 patch.object(pipeline.validate_stage, 'create_handoff') as mock_validate_handoff:

                from swarm_attack.orchestration.pvi_pipeline import StageHandoff, StageStatus
                mock_plan_handoff.return_value = StageHandoff(
                    source_stage="plan",
                    target_stage="validate",
                    payload={"steps": []},
                    status=StageStatus.COMPLETED,
                )
                mock_validate_handoff.return_value = StageHandoff(
                    source_stage="validate",
                    target_stage="implement",
                    payload={"validation_passed": True},
                    status=StageStatus.COMPLETED,
                )

                result = pipeline.run(context={"feature_id": "test", "issue_number": 1})

        assert isinstance(result, PipelineResult)
        assert result.success is True
        assert result.plan_result is not None
        assert result.validation_result is not None
        assert result.implementation_result is not None

    def test_pipeline_tracks_total_duration(self, mock_config):
        """Pipeline should track total execution duration."""
        from swarm_attack.orchestration.pvi_pipeline import (
            PVIPipeline, PlanResult, ValidationResult, ImplementationResult
        )

        pipeline = PVIPipeline(mock_config)

        with patch.object(pipeline.plan_stage, 'run') as mock_plan, \
             patch.object(pipeline.validate_stage, 'run') as mock_validate, \
             patch.object(pipeline.implement_stage, 'run') as mock_implement:

            mock_plan.return_value = PlanResult(success=True, steps=[])
            mock_validate.return_value = ValidationResult(passed=True, checks=[])
            mock_implement.return_value = ImplementationResult(success=True, gates_passed=[])

            with patch.object(pipeline.plan_stage, 'create_handoff') as mock_plan_handoff, \
                 patch.object(pipeline.validate_stage, 'create_handoff') as mock_validate_handoff:

                from swarm_attack.orchestration.pvi_pipeline import StageHandoff, StageStatus
                mock_plan_handoff.return_value = StageHandoff(
                    source_stage="plan",
                    target_stage="validate",
                    payload={"steps": []},
                    status=StageStatus.COMPLETED,
                )
                mock_validate_handoff.return_value = StageHandoff(
                    source_stage="validate",
                    target_stage="implement",
                    payload={"validation_passed": True},
                    status=StageStatus.COMPLETED,
                )

                result = pipeline.run(context={"feature_id": "test", "issue_number": 1})

        assert hasattr(result, 'duration_ms')
        assert result.duration_ms >= 0

    def test_pipeline_stores_handoffs_for_recovery(self, mock_config):
        """Pipeline should store handoffs for potential recovery."""
        from swarm_attack.orchestration.pvi_pipeline import (
            PVIPipeline, PlanResult, ValidationResult, ImplementationResult
        )

        pipeline = PVIPipeline(mock_config)

        with patch.object(pipeline.plan_stage, 'run') as mock_plan, \
             patch.object(pipeline.validate_stage, 'run') as mock_validate, \
             patch.object(pipeline.implement_stage, 'run') as mock_implement:

            mock_plan.return_value = PlanResult(success=True, steps=[])
            mock_validate.return_value = ValidationResult(passed=True, checks=[])
            mock_implement.return_value = ImplementationResult(success=True, gates_passed=[])

            with patch.object(pipeline.plan_stage, 'create_handoff') as mock_plan_handoff, \
                 patch.object(pipeline.validate_stage, 'create_handoff') as mock_validate_handoff:

                from swarm_attack.orchestration.pvi_pipeline import StageHandoff, StageStatus
                mock_plan_handoff.return_value = StageHandoff(
                    source_stage="plan",
                    target_stage="validate",
                    payload={"steps": []},
                    status=StageStatus.COMPLETED,
                )
                mock_validate_handoff.return_value = StageHandoff(
                    source_stage="validate",
                    target_stage="implement",
                    payload={"validation_passed": True},
                    status=StageStatus.COMPLETED,
                )

                result = pipeline.run(context={"feature_id": "test", "issue_number": 1})

        assert hasattr(result, 'handoffs')
        assert len(result.handoffs) == 2  # plan->validate, validate->implement
