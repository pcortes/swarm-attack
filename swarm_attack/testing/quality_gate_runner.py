"""Quality Gate Runner for CI/validation pipeline integration.

Wires AdversarialTestGenerator and MutationTestGate into CI/validation pipeline
to provide comprehensive test quality validation.

Key components:
- QualityGateRunner: Orchestrates multiple quality gates
- AdversarialTestGenerator: Generates adversarial test suggestions
- MutationTestGate: Evaluates test quality via mutation analysis
- GateType: Enum of available gate types
- QualityGateResult: Result container with CI integration
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Optional


class GateType(Enum):
    """Types of quality gates available."""

    ADVERSARIAL = "adversarial"
    MUTATION = "mutation"


@dataclass
class GateResult:
    """Result from a single gate evaluation.

    Attributes:
        gate_type: Type of gate that produced this result.
        score: Quality score from 0.0 to 1.0.
        passed: Whether this gate passed its threshold.
        issues: List of identified issues.
        suggestions: List of improvement suggestions.
        reasoning: Explanation of the evaluation.
    """

    gate_type: GateType
    score: float
    passed: bool
    issues: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)
    reasoning: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "gate_type": self.gate_type.value,
            "score": self.score,
            "passed": self.passed,
            "issues": self.issues,
            "suggestions": self.suggestions,
            "reasoning": self.reasoning,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "GateResult":
        """Deserialize from dictionary."""
        return cls(
            gate_type=GateType(data["gate_type"]),
            score=data["score"],
            passed=data["passed"],
            issues=data.get("issues", []),
            suggestions=data.get("suggestions", []),
            reasoning=data.get("reasoning", ""),
        )


@dataclass
class QualityGateResult:
    """Result from running all quality gates.

    Attributes:
        artifact_id: Identifier for the artifact being validated.
        passed: Whether all gates passed.
        gates_passed: List of gate types that passed.
        gates_failed: List of gate types that failed.
        overall_score: Weighted average score across all gates.
        gate_results: Individual results from each gate.
    """

    artifact_id: str
    passed: bool
    gates_passed: list[GateType] = field(default_factory=list)
    gates_failed: list[GateType] = field(default_factory=list)
    overall_score: float = 0.0
    gate_results: list[GateResult] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "artifact_id": self.artifact_id,
            "passed": self.passed,
            "gates_passed": [g.value for g in self.gates_passed],
            "gates_failed": [g.value for g in self.gates_failed],
            "overall_score": self.overall_score,
            "gate_results": [gr.to_dict() for gr in self.gate_results],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "QualityGateResult":
        """Deserialize from dictionary."""
        return cls(
            artifact_id=data["artifact_id"],
            passed=data["passed"],
            gates_passed=[GateType(g) for g in data.get("gates_passed", [])],
            gates_failed=[GateType(g) for g in data.get("gates_failed", [])],
            overall_score=data.get("overall_score", 0.0),
            gate_results=[GateResult.from_dict(gr) for gr in data.get("gate_results", [])],
        )

    def to_exit_code(self) -> int:
        """Convert result to CI exit code.

        Returns:
            0 if passed, 1 if failed.
        """
        return 0 if self.passed else 1

    def to_report(self) -> str:
        """Generate human-readable report.

        Returns:
            Formatted report string.
        """
        lines = [
            f"Quality Gate Report: {self.artifact_id}",
            "=" * 50,
            f"Status: {'PASSED' if self.passed else 'FAILED'}",
            f"Overall Score: {self.overall_score:.2%}",
            "",
            "Gate Results:",
            "-" * 40,
        ]

        for gr in self.gate_results:
            status = "PASS" if gr.passed else "FAIL"
            lines.append(f"  {gr.gate_type.value}: {status} ({gr.score:.2%})")
            if gr.issues:
                for issue in gr.issues:
                    lines.append(f"    - Issue: {issue}")
            if gr.suggestions:
                for suggestion in gr.suggestions[:3]:  # Limit to 3 suggestions
                    lines.append(f"    - Suggestion: {suggestion}")

        if self.gates_passed:
            lines.append("")
            lines.append(f"Gates Passed: {', '.join(g.value for g in self.gates_passed)}")
        if self.gates_failed:
            lines.append(f"Gates Failed: {', '.join(g.value for g in self.gates_failed)}")

        return "\n".join(lines)

    def to_json(self) -> str:
        """Generate JSON report for CI parsing.

        Returns:
            JSON string of the result.
        """
        return json.dumps(self.to_dict(), indent=2)


@dataclass
class AdversarialTestResult:
    """Result from adversarial test generation.

    Attributes:
        score: Quality score for test coverage.
        approved: Whether tests pass adversarial analysis.
        issues: Identified gaps in test coverage.
        suggestions: Suggested adversarial test cases.
        reasoning: Explanation of analysis.
    """

    score: float
    approved: bool
    issues: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)
    reasoning: str = ""


class AdversarialTestGenerator:
    """Generates adversarial test case suggestions.

    Analyzes code to identify edge cases, boundary conditions,
    and potential failure modes that should be tested.
    """

    # Prompt for adversarial test generation
    PROMPT = """You are an adversarial test generator. Analyze the following code and suggest tests that would expose edge cases, boundary conditions, and potential bugs.

Code to analyze:
{code_content}

Consider:
- Edge cases (empty inputs, null values, max/min values)
- Boundary conditions (off-by-one errors, limits)
- Error handling paths
- Race conditions if applicable
- Input validation gaps
- Type coercion issues

Respond with a JSON object:
{{
    "score": <float 0-1, where 1 means excellent edge case coverage>,
    "approved": <boolean, true if current tests are sufficient>,
    "issues": [<list of gaps in test coverage>],
    "suggestions": [<list of adversarial test cases to add>],
    "reasoning": "<explanation of analysis>"
}}

Return ONLY the JSON object."""

    def __init__(self, llm: Any) -> None:
        """Initialize the adversarial test generator.

        Args:
            llm: LLM instance for analysis.
        """
        self.llm = llm

    def generate(self, code: str) -> AdversarialTestResult:
        """Generate adversarial test suggestions for code.

        Args:
            code: Source code to analyze.

        Returns:
            AdversarialTestResult with suggestions.
        """
        prompt = self.PROMPT.format(code_content=code[:4000])  # Truncate if needed

        try:
            response = self.llm.generate(prompt)
            data = self._parse_response(response)

            return AdversarialTestResult(
                score=float(data.get("score", 0.0)),
                approved=bool(data.get("approved", False)),
                issues=data.get("issues", []),
                suggestions=data.get("suggestions", []),
                reasoning=data.get("reasoning", ""),
            )
        except Exception as e:
            return AdversarialTestResult(
                score=0.0,
                approved=False,
                issues=[f"Analysis failed: {e}"],
                suggestions=[],
                reasoning=f"Error during analysis: {e}",
            )

    def _parse_response(self, response: str) -> dict[str, Any]:
        """Parse LLM JSON response.

        Args:
            response: Raw LLM response.

        Returns:
            Parsed dictionary.

        Raises:
            ValueError: If response cannot be parsed.
        """
        # Try to extract JSON from response
        json_match = re.search(r"\{[\s\S]*\}", response)
        if json_match:
            return json.loads(json_match.group())
        return json.loads(response)

    def to_gate_result(self, result: AdversarialTestResult, threshold: float) -> GateResult:
        """Convert AdversarialTestResult to GateResult.

        Args:
            result: The adversarial test result.
            threshold: Score threshold for passing.

        Returns:
            GateResult for pipeline integration.
        """
        return GateResult(
            gate_type=GateType.ADVERSARIAL,
            score=result.score,
            passed=result.score >= threshold,
            issues=result.issues,
            suggestions=result.suggestions,
            reasoning=result.reasoning,
        )


@dataclass
class MutationTestResult:
    """Result from mutation test analysis.

    Attributes:
        score: Mutation score (killed/total).
        approved: Whether mutation score meets threshold.
        issues: Issues with test quality.
        suggestions: Ways to improve mutation score.
        reasoning: Explanation of analysis.
        mutation_score: Explicit mutation score.
        surviving_mutations: List of mutations that would survive.
    """

    score: float
    approved: bool
    issues: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)
    reasoning: str = ""
    mutation_score: float = 0.0
    surviving_mutations: list[str] = field(default_factory=list)


class MutationTestGate:
    """Evaluates test quality via mutation analysis.

    Analyzes code and tests to estimate how many mutations
    would be caught by the test suite.
    """

    # Prompt for mutation analysis
    PROMPT = """You are a mutation testing analyst. Analyze the following code and tests to estimate what percentage of code mutations would be caught by the tests.

Code under test:
{code_content}

Test suite:
{test_content}

Consider these mutation operators:
- Arithmetic operator replacement (+, -, *, /)
- Relational operator replacement (<, >, <=, >=, ==, !=)
- Logical operator replacement (and, or, not)
- Constant replacement (boundary values)
- Statement deletion
- Return value modification

Respond with a JSON object:
{{
    "score": <float 0-1, estimated mutation score>,
    "approved": <boolean, true if mutation score >= 0.7>,
    "issues": [<list of test quality issues>],
    "suggestions": [<list of tests to add for better mutation coverage>],
    "reasoning": "<explanation of analysis>",
    "mutation_score": <float 0-1, explicit mutation score>,
    "surviving_mutations": [<list of mutations that would survive>]
}}

Return ONLY the JSON object."""

    def __init__(self, llm: Any) -> None:
        """Initialize the mutation test gate.

        Args:
            llm: LLM instance for analysis.
        """
        self.llm = llm

    def evaluate(self, code: str, tests: str) -> MutationTestResult:
        """Evaluate test quality via mutation analysis.

        Args:
            code: Source code under test.
            tests: Test suite code.

        Returns:
            MutationTestResult with analysis.
        """
        prompt = self.PROMPT.format(
            code_content=code[:3000],  # Truncate if needed
            test_content=tests[:3000],
        )

        try:
            response = self.llm.generate(prompt)
            data = self._parse_response(response)

            return MutationTestResult(
                score=float(data.get("score", 0.0)),
                approved=bool(data.get("approved", False)),
                issues=data.get("issues", []),
                suggestions=data.get("suggestions", []),
                reasoning=data.get("reasoning", ""),
                mutation_score=float(data.get("mutation_score", data.get("score", 0.0))),
                surviving_mutations=data.get("surviving_mutations", []),
            )
        except Exception as e:
            return MutationTestResult(
                score=0.0,
                approved=False,
                issues=[f"Analysis failed: {e}"],
                suggestions=[],
                reasoning=f"Error during analysis: {e}",
            )

    def _parse_response(self, response: str) -> dict[str, Any]:
        """Parse LLM JSON response.

        Args:
            response: Raw LLM response.

        Returns:
            Parsed dictionary.

        Raises:
            ValueError: If response cannot be parsed.
        """
        # Try to extract JSON from response
        json_match = re.search(r"\{[\s\S]*\}", response)
        if json_match:
            return json.loads(json_match.group())
        return json.loads(response)

    def to_gate_result(self, result: MutationTestResult, threshold: float) -> GateResult:
        """Convert MutationTestResult to GateResult.

        Args:
            result: The mutation test result.
            threshold: Score threshold for passing.

        Returns:
            GateResult for pipeline integration.
        """
        return GateResult(
            gate_type=GateType.MUTATION,
            score=result.score,
            passed=result.score >= threshold,
            issues=result.issues,
            suggestions=result.suggestions,
            reasoning=result.reasoning,
        )


class QualityGateRunner:
    """Orchestrates quality gates for CI/validation pipeline.

    Runs multiple quality gates (AdversarialTestGenerator, MutationTestGate)
    in sequence and aggregates results for CI integration.

    Attributes:
        llm: LLM instance for gate evaluations.
        threshold: Score threshold for passing (0.0-1.0).
        gates: List of gate types to run.
    """

    DEFAULT_GATES = [GateType.ADVERSARIAL, GateType.MUTATION]
    DEFAULT_THRESHOLD = 0.6

    def __init__(
        self,
        llm: Any,
        threshold: float = DEFAULT_THRESHOLD,
        gates: Optional[list[GateType]] = None,
    ) -> None:
        """Initialize the quality gate runner.

        Args:
            llm: LLM instance for gate evaluations.
            threshold: Score threshold for passing (default 0.6).
            gates: List of gates to run (default: all gates).
        """
        self.llm = llm
        self.threshold = threshold
        self.gates = gates if gates is not None else self.DEFAULT_GATES.copy()

        # Initialize gate instances
        self._adversarial_generator = AdversarialTestGenerator(llm)
        self._mutation_gate = MutationTestGate(llm)

    def run(
        self,
        code: str,
        tests: str,
        artifact_id: str,
        report_path: Optional[Path] = None,
    ) -> QualityGateResult:
        """Run all configured quality gates.

        Args:
            code: Source code to validate.
            tests: Test code to validate.
            artifact_id: Identifier for the artifact.
            report_path: Optional path to write report.

        Returns:
            QualityGateResult with aggregated results.
        """
        gate_results: list[GateResult] = []
        gates_passed: list[GateType] = []
        gates_failed: list[GateType] = []

        # Run each configured gate
        for gate_type in self.gates:
            try:
                gate_result = self._run_gate(gate_type, code, tests)
                gate_results.append(gate_result)

                if gate_result.passed:
                    gates_passed.append(gate_type)
                else:
                    gates_failed.append(gate_type)
            except Exception as e:
                # Create a failed result for this gate
                gate_result = GateResult(
                    gate_type=gate_type,
                    score=0.0,
                    passed=False,
                    issues=[f"Gate execution failed: {e}"],
                    suggestions=[],
                    reasoning=f"Error: {e}",
                )
                gate_results.append(gate_result)
                gates_failed.append(gate_type)

        # Calculate overall score
        if gate_results:
            overall_score = sum(gr.score for gr in gate_results) / len(gate_results)
        else:
            overall_score = 0.0

        # Determine overall pass/fail
        passed = len(gates_failed) == 0

        result = QualityGateResult(
            artifact_id=artifact_id,
            passed=passed,
            gates_passed=gates_passed,
            gates_failed=gates_failed,
            overall_score=overall_score,
            gate_results=gate_results,
        )

        # Write report if path provided
        if report_path:
            self._write_report(result, report_path)

        return result

    def _run_gate(self, gate_type: GateType, code: str, tests: str) -> GateResult:
        """Run a single gate.

        Args:
            gate_type: Type of gate to run.
            code: Source code.
            tests: Test code.

        Returns:
            GateResult from the gate.
        """
        if gate_type == GateType.ADVERSARIAL:
            result = self._adversarial_generator.generate(code)
            return self._adversarial_generator.to_gate_result(result, self.threshold)
        elif gate_type == GateType.MUTATION:
            result = self._mutation_gate.evaluate(code, tests)
            return self._mutation_gate.to_gate_result(result, self.threshold)
        else:
            raise ValueError(f"Unknown gate type: {gate_type}")

    def _write_report(self, result: QualityGateResult, report_path: Path) -> None:
        """Write report to file.

        Args:
            result: The quality gate result.
            report_path: Path to write report.
        """
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(result.to_json())
