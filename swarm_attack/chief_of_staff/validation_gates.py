"""Validation gates for integrating ValidationLayer into pipelines.

Provides specific validation gates for specs, code, and tests with:
- Configurable thresholds (60% default)
- Security veto for spec and code
- Coverage review requirement for tests <80%
- CLI-friendly output formatting
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from swarm_attack.chief_of_staff.critics import (
    ValidationLayer,
    ValidationResult,
    CriticFocus,
    CriticScore,
    SpecCritic,
    CodeCritic,
    TestCritic,
)


class ArtifactType(Enum):
    """Type of artifact being validated."""

    SPEC = "spec"
    CODE = "code"
    TEST = "test"


@dataclass
class ValidationGateResult:
    """Result from a validation gate check.

    Attributes:
        approved: Whether the artifact passed validation.
        artifact_type: Type of artifact validated.
        artifact_id: Identifier for the artifact.
        summary: Human-readable summary of validation result.
        blocking_issues: List of issues that blocked approval.
        needs_human_review: Whether human review is required.
        validation_result: Full ValidationResult from ValidationLayer.
    """

    approved: bool
    artifact_type: ArtifactType
    artifact_id: str
    summary: str
    blocking_issues: list[str]
    needs_human_review: bool
    validation_result: Optional[ValidationResult]

    def to_cli_output(self) -> str:
        """Format result for CLI display.

        Returns:
            Formatted string for CLI output.
        """
        status = "APPROVED" if self.approved else "NEEDS REVIEW"
        lines = [
            f"Status: {status}",
            f"Artifact: {self.artifact_id}",
            f"Type: {self.artifact_type.value}",
            f"Summary: {self.summary}",
        ]

        if self.blocking_issues:
            lines.append("Blocking Issues:")
            for issue in self.blocking_issues:
                lines.append(f"  - {issue}")

        return "\n".join(lines)


class ValidationGate:
    """Base class for validation gates.

    Provides common functionality for all validation gates including:
    - Threshold-based approval
    - Security veto support
    - File path validation
    """

    def __init__(
        self,
        llm: Any,
        threshold: float = 0.6,
        security_veto: bool = False,
    ) -> None:
        """Initialize validation gate.

        Args:
            llm: LLM instance for critic evaluations.
            threshold: Approval threshold (0-1). Default 60%.
            security_veto: Whether security issues block approval.
        """
        self.llm = llm
        self.threshold = threshold
        self.security_veto = security_veto
        self.validation_layer = ValidationLayer(llm)

    def validate(self, artifact: str, artifact_id: str) -> ValidationGateResult:
        """Validate an artifact.

        Args:
            artifact: Content to validate.
            artifact_id: Identifier for the artifact.

        Returns:
            ValidationGateResult with approval status.
        """
        raise NotImplementedError("Subclasses must implement validate()")

    def validate_from_path(self, path: Path) -> ValidationGateResult:
        """Validate artifact from file path.

        Args:
            path: Path to the file to validate.

        Returns:
            ValidationGateResult with approval status.

        Raises:
            FileNotFoundError: If the file doesn't exist.
        """
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        content = path.read_text()
        return self.validate(content, str(path))


class SpecValidationGate(ValidationGate):
    """Validation gate for engineering specs.

    Uses completeness, feasibility, and security critics.
    Security veto is enabled by default.
    Threshold: 60%
    """

    def __init__(self, llm: Any) -> None:
        """Initialize spec validation gate.

        Args:
            llm: LLM instance for critic evaluations.
        """
        super().__init__(llm, threshold=0.6, security_veto=True)

    def validate(self, artifact: str, artifact_id: str) -> ValidationGateResult:
        """Validate a spec artifact.

        Args:
            artifact: Spec content to validate.
            artifact_id: Identifier for the spec.

        Returns:
            ValidationGateResult with approval status.
        """
        # Use ValidationLayer with spec type
        result = self.validation_layer.validate(
            artifact=artifact,
            artifact_type="spec",
            artifact_id=artifact_id,
        )

        # Build summary
        if result.approved:
            summary = f"APPROVED - {result.consensus_summary}"
        else:
            summary = f"NEEDS REVIEW - {result.consensus_summary}"

        return ValidationGateResult(
            approved=result.approved,
            artifact_type=ArtifactType.SPEC,
            artifact_id=artifact_id,
            summary=summary,
            blocking_issues=result.blocking_issues,
            needs_human_review=result.human_review_required,
            validation_result=result,
        )


class CodeValidationGate(ValidationGate):
    """Validation gate for code diffs.

    Uses style and security critics.
    Security veto is enabled by default.
    Threshold: 60%
    """

    def __init__(self, llm: Any) -> None:
        """Initialize code validation gate.

        Args:
            llm: LLM instance for critic evaluations.
        """
        super().__init__(llm, threshold=0.6, security_veto=True)

    def validate(self, artifact: str, artifact_id: str) -> ValidationGateResult:
        """Validate a code artifact.

        Args:
            artifact: Code content to validate.
            artifact_id: Identifier for the code.

        Returns:
            ValidationGateResult with approval status.
        """
        # Use ValidationLayer with code type
        result = self.validation_layer.validate(
            artifact=artifact,
            artifact_type="code",
            artifact_id=artifact_id,
        )

        # Build summary
        if result.approved:
            summary = f"APPROVED - {result.consensus_summary}"
        else:
            summary = f"NEEDS REVIEW - {result.consensus_summary}"

        return ValidationGateResult(
            approved=result.approved,
            artifact_type=ArtifactType.CODE,
            artifact_id=artifact_id,
            summary=summary,
            blocking_issues=result.blocking_issues,
            needs_human_review=result.human_review_required,
            validation_result=result,
        )


class SuiteValidationGate(ValidationGate):
    """Validation gate for test files (BUG-13/14: renamed from TestingValidationGate).

    Uses coverage and edge_cases critics.
    No security veto (tests don't have security implications).
    Threshold: 60%
    Coverage below 80% requires human review.
    """

    COVERAGE_REVIEW_THRESHOLD = 0.8

    def __init__(self, llm: Any) -> None:
        """Initialize test validation gate.

        Args:
            llm: LLM instance for critic evaluations.
        """
        super().__init__(llm, threshold=0.6, security_veto=False)

    def validate(self, artifact: str, artifact_id: str) -> ValidationGateResult:
        """Validate a test artifact.

        Args:
            artifact: Test content to validate.
            artifact_id: Identifier for the test.

        Returns:
            ValidationGateResult with approval status.
        """
        # Use ValidationLayer with test type
        result = self.validation_layer.validate(
            artifact=artifact,
            artifact_type="test",
            artifact_id=artifact_id,
        )

        # Check coverage score for review requirement
        coverage_score = 1.0
        for score in result.scores:
            if score.focus == CriticFocus.COVERAGE:
                coverage_score = score.score
                break

        # Coverage below 80% requires review even if approved
        needs_review = result.human_review_required
        if coverage_score < self.COVERAGE_REVIEW_THRESHOLD:
            needs_review = True

        # Build summary
        if result.approved:
            if needs_review:
                summary = f"APPROVED (REVIEW RECOMMENDED) - Coverage: {coverage_score:.0%}"
            else:
                summary = f"APPROVED - {result.consensus_summary}"
        else:
            summary = f"NEEDS REVIEW - {result.consensus_summary}"

        return ValidationGateResult(
            approved=result.approved,
            artifact_type=ArtifactType.TEST,
            artifact_id=artifact_id,
            summary=summary,
            blocking_issues=result.blocking_issues,
            needs_human_review=needs_review,
            validation_result=result,
        )


# BUG-13/14: Backward compatibility aliases (not class definitions, so pytest won't collect)
TestingValidationGate = SuiteValidationGate
TestValidationGate = SuiteValidationGate


def get_validation_gate(
    artifact_type: str,
    llm: Any,
) -> ValidationGate:
    """Get the appropriate validation gate for an artifact type.

    Args:
        artifact_type: One of "spec", "code", or "test".
        llm: LLM instance for critic evaluations.

    Returns:
        Appropriate ValidationGate subclass.

    Raises:
        ValueError: If artifact_type is not recognized.
    """
    gates = {
        "spec": SpecValidationGate,
        "code": CodeValidationGate,
        "test": SuiteValidationGate,
    }

    gate_class = gates.get(artifact_type.lower())
    if gate_class is None:
        raise ValueError(
            f"Unknown artifact type: {artifact_type}. "
            f"Valid types: {', '.join(gates.keys())}"
        )

    return gate_class(llm)