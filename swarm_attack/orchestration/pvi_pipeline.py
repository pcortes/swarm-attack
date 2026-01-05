"""PVI (Plan-Validate-Implement) Pipeline for orchestrated implementation.

This module provides a three-stage pipeline for feature implementation:
1. Plan Stage: Produces implementation plan with structured steps
2. Validate Stage: Runs checks (tests exist, deps resolved)
3. Implement Stage: Executes with verification gates

Each stage creates a handoff for the next stage, enabling clean separation
of concerns and easy recovery from failures.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum, auto
from typing import Any, Callable, Dict, List, Optional
import time


# =============================================================================
# ENUMS
# =============================================================================


class StageStatus(Enum):
    """Status of a pipeline stage."""
    PENDING = auto()
    RUNNING = auto()
    COMPLETED = auto()
    FAILED = auto()
    BLOCKED = auto()


# =============================================================================
# DATA CLASSES - Plan Stage
# =============================================================================


@dataclass
class PlanStep:
    """A single step in an implementation plan."""
    step_number: int
    description: str
    estimated_complexity: str  # "low", "medium", "high"
    dependencies: List[int] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dict."""
        return {
            "step_number": self.step_number,
            "description": self.description,
            "estimated_complexity": self.estimated_complexity,
            "dependencies": self.dependencies,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PlanStep":
        """Deserialize from dict."""
        return cls(
            step_number=data["step_number"],
            description=data["description"],
            estimated_complexity=data.get("estimated_complexity", "medium"),
            dependencies=data.get("dependencies", []),
        )


@dataclass
class PlanResult:
    """Result of the plan stage."""
    success: bool
    steps: List[PlanStep]
    total_estimated_complexity: Optional[str] = None
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dict."""
        return {
            "success": self.success,
            "steps": [s.to_dict() for s in self.steps],
            "total_estimated_complexity": self.total_estimated_complexity,
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PlanResult":
        """Deserialize from dict."""
        steps = [PlanStep.from_dict(s) for s in data.get("steps", [])]
        return cls(
            success=data["success"],
            steps=steps,
            total_estimated_complexity=data.get("total_estimated_complexity"),
            error=data.get("error"),
        )


# =============================================================================
# DATA CLASSES - Validation Stage
# =============================================================================


@dataclass
class ValidationCheck:
    """A single validation check."""
    check_name: str
    passed: bool
    message: str
    blocking: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dict."""
        return {
            "check_name": self.check_name,
            "passed": self.passed,
            "message": self.message,
            "blocking": self.blocking,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ValidationCheck":
        """Deserialize from dict."""
        return cls(
            check_name=data["check_name"],
            passed=data["passed"],
            message=data["message"],
            blocking=data.get("blocking", False),
        )


@dataclass
class ValidationResult:
    """Result of the validation stage."""
    passed: bool
    checks: List[ValidationCheck]

    def has_blocking_issues(self) -> bool:
        """Return True if there are any blocking checks that failed."""
        return any(c.blocking and not c.passed for c in self.checks)

    def get_blocking_checks(self) -> List[ValidationCheck]:
        """Return list of blocking checks that failed."""
        return [c for c in self.checks if c.blocking and not c.passed]

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dict."""
        return {
            "passed": self.passed,
            "checks": [c.to_dict() for c in self.checks],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ValidationResult":
        """Deserialize from dict."""
        checks = [ValidationCheck.from_dict(c) for c in data.get("checks", [])]
        return cls(
            passed=data["passed"],
            checks=checks,
        )


# =============================================================================
# DATA CLASSES - Implementation Stage
# =============================================================================


@dataclass
class GateResult:
    """Result of a verification gate."""
    gate_name: str
    passed: bool
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dict."""
        return {
            "gate_name": self.gate_name,
            "passed": self.passed,
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GateResult":
        """Deserialize from dict."""
        return cls(
            gate_name=data["gate_name"],
            passed=data["passed"],
            error=data.get("error"),
        )


@dataclass
class ImplementationResult:
    """Result of the implementation stage."""
    success: bool
    gates_passed: List[GateResult]
    files_modified: List[str] = field(default_factory=list)
    commits: List[str] = field(default_factory=list)
    error: Optional[str] = None
    failed_gate: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dict."""
        return {
            "success": self.success,
            "gates_passed": [g.to_dict() for g in self.gates_passed],
            "files_modified": self.files_modified,
            "commits": self.commits,
            "error": self.error,
            "failed_gate": self.failed_gate,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ImplementationResult":
        """Deserialize from dict."""
        gates = [GateResult.from_dict(g) for g in data.get("gates_passed", [])]
        return cls(
            success=data["success"],
            gates_passed=gates,
            files_modified=data.get("files_modified", []),
            commits=data.get("commits", []),
            error=data.get("error"),
            failed_gate=data.get("failed_gate"),
        )


# =============================================================================
# STAGE HANDOFF
# =============================================================================


@dataclass
class StageHandoff:
    """Data passed between pipeline stages."""
    source_stage: str
    target_stage: str
    payload: Dict[str, Any]
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"))
    status: StageStatus = StageStatus.PENDING

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dict."""
        return {
            "source_stage": self.source_stage,
            "target_stage": self.target_stage,
            "payload": self.payload,
            "created_at": self.created_at,
            "status": self.status.name,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StageHandoff":
        """Deserialize from dict."""
        return cls(
            source_stage=data["source_stage"],
            target_stage=data["target_stage"],
            payload=data["payload"],
            created_at=data.get("created_at", datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")),
            status=StageStatus[data.get("status", "PENDING")],
        )


# =============================================================================
# PIPELINE RESULT
# =============================================================================


@dataclass
class PipelineResult:
    """Result of the full PVI pipeline execution."""
    success: bool
    plan_result: Optional[PlanResult] = None
    validation_result: Optional[ValidationResult] = None
    implementation_result: Optional[ImplementationResult] = None
    failed_stage: Optional[str] = None
    error: Optional[str] = None
    duration_ms: int = 0
    handoffs: List[StageHandoff] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dict."""
        return {
            "success": self.success,
            "plan_result": self.plan_result.to_dict() if self.plan_result else None,
            "validation_result": self.validation_result.to_dict() if self.validation_result else None,
            "implementation_result": self.implementation_result.to_dict() if self.implementation_result else None,
            "failed_stage": self.failed_stage,
            "error": self.error,
            "duration_ms": self.duration_ms,
            "handoffs": [h.to_dict() for h in self.handoffs],
        }


# =============================================================================
# PLAN STAGE
# =============================================================================


class PlanStage:
    """Stage that creates an implementation plan."""

    def __init__(self, config: Any):
        """Initialize with configuration.

        Args:
            config: Configuration object with repo_root and other settings.
        """
        self.config = config
        self.name = "plan"
        self._context: Optional[Dict[str, Any]] = None

    def run(self, context: Dict[str, Any]) -> PlanResult:
        """Run the plan stage.

        Args:
            context: Context dict with required fields (issue_number, feature_id).

        Returns:
            PlanResult with success status and implementation steps.

        Raises:
            ValueError: If required context fields are missing.
        """
        # Validate required context
        if "issue_number" not in context:
            raise ValueError("Missing required context field: issue_number")
        if "feature_id" not in context:
            raise ValueError("Missing required context field: feature_id")

        self._context = context

        try:
            return self._generate_plan(context)
        except Exception as e:
            return PlanResult(
                success=False,
                steps=[],
                error=str(e),
            )

    def _generate_plan(self, context: Dict[str, Any]) -> PlanResult:
        """Generate implementation plan. Override in subclass or mock in tests.

        Args:
            context: Context dict with issue_number, feature_id, etc.

        Returns:
            PlanResult with implementation steps.
        """
        # Default implementation - override in subclass or mock in tests
        return PlanResult(success=True, steps=[])

    def create_handoff(
        self,
        result: PlanResult,
        context: Optional[Dict[str, Any]] = None
    ) -> StageHandoff:
        """Create handoff for the validate stage.

        Args:
            result: PlanResult from run().
            context: Original context dict (optional, uses stored if not provided).

        Returns:
            StageHandoff for the validate stage.
        """
        ctx = context or self._context or {}

        if not result.success:
            return StageHandoff(
                source_stage="plan",
                target_stage="validate",
                payload={},
                status=StageStatus.FAILED,
            )

        payload = {
            "steps": [s.to_dict() for s in result.steps],
            "total_estimated_complexity": result.total_estimated_complexity,
        }
        # Preserve context fields
        payload.update(ctx)

        return StageHandoff(
            source_stage="plan",
            target_stage="validate",
            payload=payload,
            status=StageStatus.COMPLETED,
        )


# =============================================================================
# VALIDATE STAGE
# =============================================================================


class ValidateStage:
    """Stage that validates the plan before implementation."""

    def __init__(
        self,
        config: Any,
        custom_validators: Optional[List[Callable[[Dict[str, Any]], ValidationCheck]]] = None
    ):
        """Initialize with configuration.

        Args:
            config: Configuration object with repo_root and other settings.
            custom_validators: Optional list of custom validation functions.
        """
        self.config = config
        self.name = "validate"
        self.custom_validators = custom_validators or []

    def run(self, handoff: StageHandoff) -> ValidationResult:
        """Run the validate stage.

        Args:
            handoff: StageHandoff from the plan stage.

        Returns:
            ValidationResult with passed status and check results.

        Raises:
            ValueError: If handoff is from wrong source stage.
        """
        if handoff.source_stage != "plan":
            raise ValueError(f"Expected handoff from plan stage, got {handoff.source_stage}")

        return self._run_checks(handoff.payload)

    def _run_checks(self, context: Dict[str, Any]) -> ValidationResult:
        """Run validation checks. Override in subclass or mock in tests.

        Args:
            context: Context dict with steps, feature_id, etc.

        Returns:
            ValidationResult with check results.
        """
        # Default implementation - override in subclass or mock in tests
        return ValidationResult(passed=True, checks=[])

    def create_handoff(
        self,
        result: ValidationResult,
        plan_handoff: StageHandoff
    ) -> StageHandoff:
        """Create handoff for the implement stage.

        Args:
            result: ValidationResult from run().
            plan_handoff: The handoff received from plan stage.

        Returns:
            StageHandoff for the implement stage.
        """
        if not result.passed or result.has_blocking_issues():
            return StageHandoff(
                source_stage="validate",
                target_stage="implement",
                payload=plan_handoff.payload,
                status=StageStatus.BLOCKED,
            )

        payload = dict(plan_handoff.payload)
        payload["validation_passed"] = True
        payload["checks"] = [c.to_dict() for c in result.checks]

        return StageHandoff(
            source_stage="validate",
            target_stage="implement",
            payload=payload,
            status=StageStatus.COMPLETED,
        )


# =============================================================================
# IMPLEMENT STAGE
# =============================================================================


class ImplementStage:
    """Stage that executes the implementation with verification gates."""

    def __init__(self, config: Any):
        """Initialize with configuration.

        Args:
            config: Configuration object with repo_root and other settings.
        """
        self.config = config
        self.name = "implement"

    def run(self, handoff: StageHandoff) -> ImplementationResult:
        """Run the implement stage.

        Args:
            handoff: StageHandoff from the validate stage.

        Returns:
            ImplementationResult with success status and gate results.

        Raises:
            ValueError: If handoff is from wrong source or validation failed.
        """
        if handoff.source_stage != "validate":
            raise ValueError(f"Expected handoff from validate stage, got {handoff.source_stage}")

        if not handoff.payload.get("validation_passed", False):
            raise ValueError("Validation did not pass, cannot proceed with implementation")

        return self._execute_implementation(handoff.payload)

    def _execute_implementation(self, context: Dict[str, Any]) -> ImplementationResult:
        """Execute implementation. Override in subclass or mock in tests.

        Args:
            context: Context dict with steps, feature_id, validation info, etc.

        Returns:
            ImplementationResult with gate results and files/commits.
        """
        # Default implementation - override in subclass or mock in tests
        return ImplementationResult(success=True, gates_passed=[])


# =============================================================================
# PVI PIPELINE
# =============================================================================


class PVIPipeline:
    """Orchestrates the Plan-Validate-Implement pipeline."""

    def __init__(self, config: Any):
        """Initialize the pipeline with configuration.

        Args:
            config: Configuration object with repo_root and other settings.
        """
        self.config = config
        self.plan_stage = PlanStage(config)
        self.validate_stage = ValidateStage(config)
        self.implement_stage = ImplementStage(config)

    def run(self, context: Dict[str, Any]) -> PipelineResult:
        """Run the full PVI pipeline.

        Args:
            context: Context dict with required fields (issue_number, feature_id).

        Returns:
            PipelineResult with success status and results from all stages.
        """
        start_time = time.time()
        handoffs: List[StageHandoff] = []

        # ---- PLAN STAGE ----
        plan_result = self.plan_stage.run(context=context)
        plan_handoff = self.plan_stage.create_handoff(plan_result, context=context)
        handoffs.append(plan_handoff)

        if plan_handoff.status == StageStatus.FAILED:
            duration_ms = int((time.time() - start_time) * 1000)
            return PipelineResult(
                success=False,
                plan_result=plan_result,
                failed_stage="plan",
                error=plan_result.error,
                duration_ms=duration_ms,
                handoffs=handoffs,
            )

        # ---- VALIDATE STAGE ----
        validation_result = self.validate_stage.run(handoff=plan_handoff)
        validate_handoff = self.validate_stage.create_handoff(validation_result, plan_handoff)
        handoffs.append(validate_handoff)

        if validate_handoff.status == StageStatus.BLOCKED:
            duration_ms = int((time.time() - start_time) * 1000)
            return PipelineResult(
                success=False,
                plan_result=plan_result,
                validation_result=validation_result,
                failed_stage="validate",
                error="Validation blocked",
                duration_ms=duration_ms,
                handoffs=handoffs,
            )

        # ---- IMPLEMENT STAGE ----
        implementation_result = self.implement_stage.run(handoff=validate_handoff)

        duration_ms = int((time.time() - start_time) * 1000)

        if not implementation_result.success:
            return PipelineResult(
                success=False,
                plan_result=plan_result,
                validation_result=validation_result,
                implementation_result=implementation_result,
                failed_stage="implement",
                error=implementation_result.error,
                duration_ms=duration_ms,
                handoffs=handoffs,
            )

        return PipelineResult(
            success=True,
            plan_result=plan_result,
            validation_result=validation_result,
            implementation_result=implementation_result,
            duration_ms=duration_ms,
            handoffs=handoffs,
        )
