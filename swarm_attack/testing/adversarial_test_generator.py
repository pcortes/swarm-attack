"""
AdversarialTestGenerator - Generate tests in isolated context.

This module provides adversarial test generation that operates
without knowledge of the implementation. It receives only
spec/interface information and generates comprehensive tests
including edge cases, error conditions, and boundary tests.

Key features:
- Generates tests based solely on interface specification
- No implementation knowledge (true black-box testing)
- Includes multiple test categories (happy path, edge, error, boundary)
- Supports mutation testing to verify test quality
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any, Optional

from swarm_attack.agents.base import BaseAgent, AgentResult

if TYPE_CHECKING:
    from swarm_attack.config import SwarmConfig
    from swarm_attack.logger import SwarmLogger


class AdversarialCategory(Enum):
    """Categories of generated tests."""

    HAPPY_PATH = "happy_path"
    EDGE_CASE = "edge_case"
    ERROR_CONDITION = "error_condition"
    BOUNDARY = "boundary"
    NULL_EMPTY = "null_empty"
    TYPE_COERCION = "type_coercion"


class GenerationError(Exception):
    """Raised when test generation fails."""

    pass


@dataclass
class InterfaceSpec:
    """
    Specification of an interface for test generation.

    Contains the contract information needed to generate tests
    without any implementation details.
    """

    name: str
    description: str
    methods: list[dict[str, Any]] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    examples: list[dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "name": self.name,
            "description": self.description,
            "methods": self.methods,
            "constraints": self.constraints,
            "examples": self.examples,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> InterfaceSpec:
        """Create from dictionary."""
        return cls(
            name=data["name"],
            description=data["description"],
            methods=data.get("methods", []),
            constraints=data.get("constraints", []),
            examples=data.get("examples", []),
        )


@dataclass
class GeneratedTest:
    """A generated test case."""

    name: str
    category: AdversarialCategory
    code: str
    description: str
    target_method: str
    expected_exception: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "name": self.name,
            "category": self.category.value,
            "code": self.code,
            "description": self.description,
            "target_method": self.target_method,
            "expected_exception": self.expected_exception,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GeneratedTest:
        """Create from dictionary."""
        return cls(
            name=data["name"],
            category=AdversarialCategory(data["category"]),
            code=data["code"],
            description=data["description"],
            target_method=data["target_method"],
            expected_exception=data.get("expected_exception"),
        )


@dataclass
class GenerationResult:
    """Result of test generation."""

    success: bool
    tests: list[GeneratedTest]
    spec_name: str
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "success": self.success,
            "tests": [t.to_dict() for t in self.tests],
            "spec_name": self.spec_name,
            "errors": self.errors,
        }

    def get_test_counts_by_category(self) -> dict[AdversarialCategory, int]:
        """Get count of tests per category."""
        counts: dict[AdversarialCategory, int] = {}
        for test in self.tests:
            counts[test.category] = counts.get(test.category, 0) + 1
        return counts

    def get_combined_code(self) -> str:
        """Get combined code of all tests."""
        return "\n\n".join(test.code for test in self.tests)


@dataclass
class MutationTestResult:
    """Result of mutation testing."""

    total_mutants: int
    killed_mutants: int
    survived_mutants: int
    mutation_score: float
    surviving_mutant_details: list[dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "total_mutants": self.total_mutants,
            "killed_mutants": self.killed_mutants,
            "survived_mutants": self.survived_mutants,
            "mutation_score": self.mutation_score,
            "surviving_mutant_details": self.surviving_mutant_details,
        }


class AdversarialTestGenerator(BaseAgent):
    """
    Generate tests in isolated context without implementation knowledge.

    This generator receives only interface specifications (method signatures,
    expected behaviors, constraints) and generates comprehensive tests
    without seeing the actual implementation. This approach ensures
    tests are truly behavior-driven rather than implementation-driven.

    Key principles:
    - Tests are based solely on the spec/interface
    - No access to implementation code
    - Generates edge cases and error conditions
    - Supports mutation testing for quality verification
    """

    name: str = "adversarial_test_generator"

    def __init__(
        self,
        config: "SwarmConfig",
        logger: Optional["SwarmLogger"] = None,
        llm_runner: Any = None,
    ) -> None:
        """
        Initialize the AdversarialTestGenerator.

        Args:
            config: SwarmConfig with paths and settings.
            logger: Optional logger for recording operations.
            llm_runner: Optional LLM runner for test generation.
        """
        super().__init__(config, logger=logger, llm_runner=llm_runner)

    def run(self, context: dict[str, Any]) -> AgentResult:
        """
        Execute test generation.

        Args:
            context: Dictionary containing:
                - spec: InterfaceSpec to generate tests for

        Returns:
            AgentResult with generated tests.
        """
        spec = context.get("spec")
        if not spec:
            return AgentResult.failure_result("No spec provided")

        result = self.generate(spec)
        if result.success:
            return AgentResult.success_result(result.to_dict())
        return AgentResult.failure_result("; ".join(result.errors))

    def generate(
        self,
        spec: InterfaceSpec,
        forbidden_context: Optional[dict[str, Any]] = None,
    ) -> GenerationResult:
        """
        Generate tests from an interface specification.

        Args:
            spec: Interface specification to generate tests for.
            forbidden_context: Optional dict of context that should
                NOT be used (e.g., implementation details).

        Returns:
            GenerationResult with generated tests.

        Raises:
            GenerationError: If spec is invalid.
        """
        if spec is None:
            raise GenerationError("Spec cannot be None")

        try:
            # Build prompt - intentionally excluding any implementation details
            prompt = self._build_prompt(spec)

            # Call LLM
            llm_result = self._call_llm(prompt=prompt)

            if not llm_result.success:
                error_msg = getattr(llm_result, "error", "Unknown LLM error")
                return GenerationResult(
                    success=False,
                    tests=[],
                    spec_name=spec.name,
                    errors=[error_msg],
                )

            # Parse tests from output
            tests = self._parse_tests(llm_result.output)

            return GenerationResult(
                success=True,
                tests=tests,
                spec_name=spec.name,
            )

        except TimeoutError as e:
            return GenerationResult(
                success=False,
                tests=[],
                spec_name=spec.name,
                errors=[f"Timeout error: {str(e)}"],
            )
        except Exception as e:
            return GenerationResult(
                success=False,
                tests=[],
                spec_name=spec.name,
                errors=[str(e)],
            )

    def _build_prompt(self, spec: InterfaceSpec) -> str:
        """
        Build the prompt for test generation.

        The prompt explicitly excludes implementation details and focuses
        only on the interface contract.
        """
        prompt_parts = [
            "# Test Generation Task",
            "",
            "Generate comprehensive tests for the following interface specification.",
            "You must generate tests based ONLY on the expected behavior described below.",
            "Do NOT assume any implementation details - test only the contract/interface.",
            "",
            "## Interface Specification",
            f"**Name:** {spec.name}",
            f"**Description:** {spec.description}",
            "",
            "## Methods",
        ]

        for method in spec.methods:
            prompt_parts.append(f"\n### {method.get('name', 'Unknown')}")
            if "signature" in method:
                prompt_parts.append(f"**Signature:** `{method['signature']}`")
            if "description" in method:
                prompt_parts.append(f"**Description:** {method['description']}")
            if "parameters" in method:
                prompt_parts.append("**Parameters:**")
                for param in method["parameters"]:
                    prompt_parts.append(
                        f"  - `{param['name']}` ({param.get('type', 'any')}): "
                        f"{param.get('description', '')}"
                    )
            if "returns" in method:
                ret = method["returns"]
                prompt_parts.append(
                    f"**Returns:** `{ret.get('type', 'any')}` - {ret.get('description', '')}"
                )
            if "raises" in method:
                prompt_parts.append("**Raises:**")
                for exc in method["raises"]:
                    prompt_parts.append(
                        f"  - `{exc['exception']}`: {exc.get('condition', '')}"
                    )

        if spec.constraints:
            prompt_parts.append("\n## Constraints")
            for constraint in spec.constraints:
                prompt_parts.append(f"- {constraint}")

        if spec.examples:
            prompt_parts.append("\n## Examples")
            for example in spec.examples:
                prompt_parts.append(f"- `{example['call']}` -> `{example['result']}`")

        prompt_parts.extend([
            "",
            "## Test Generation Requirements",
            "",
            "Generate tests for the following categories:",
            "1. **Happy Path** (CATEGORY: happy_path): Normal expected usage",
            "2. **Edge Cases** (CATEGORY: edge_case): Unusual but valid inputs",
            "3. **Error Conditions** (CATEGORY: error_condition): Inputs that should raise exceptions",
            "4. **Boundary Tests** (CATEGORY: boundary): Min/max values, limits",
            "5. **Null/Empty** (CATEGORY: null_empty): None, empty strings, empty lists",
            "6. **Type Coercion** (CATEGORY: type_coercion): Wrong types if applicable",
            "",
            "## Output Format",
            "",
            "Output your tests in the following format:",
            "```",
            "[TESTS]",
            "# CATEGORY: <category>",
            "# TARGET: <method_name>",
            "# DESCRIPTION: <test description>",
            "# EXCEPTION: <ExceptionName>  (only for error_condition tests)",
            "def test_name():",
            "    # test implementation",
            "",
            "# CATEGORY: <next_category>",
            "...",
            "[/TESTS]",
            "```",
            "",
            "IMPORTANT: Base tests ONLY on the interface specification above.",
            "Do NOT assume any specific implementation behavior.",
        ])

        return "\n".join(prompt_parts)

    def _call_llm(self, prompt: str) -> Any:
        """
        Call the LLM to generate tests.

        Args:
            prompt: The prompt to send to the LLM.

        Returns:
            LLM response with success status and output.
        """
        return self.llm.run(
            prompt=prompt,
            max_turns=5,
            timeout=120,
        )

    def _parse_tests(self, output: str) -> list[GeneratedTest]:
        """
        Parse generated tests from LLM output.

        Args:
            output: Raw LLM output containing tests.

        Returns:
            List of parsed GeneratedTest objects.
        """
        tests: list[GeneratedTest] = []

        # Extract content between [TESTS] and [/TESTS]
        match = re.search(r"\[TESTS\](.*?)\[/TESTS\]", output, re.DOTALL)
        if not match:
            return tests

        content = match.group(1).strip()
        if not content:
            return tests

        # Split by test functions
        test_pattern = re.compile(
            r"((?:#[^\n]*\n)*)"  # Capture preceding comments
            r"(def\s+test_\w+\([^)]*\):.*?)(?=(?:#[^\n]*\n)*def\s+test_|\Z)",
            re.DOTALL,
        )

        for test_match in test_pattern.finditer(content):
            comments = test_match.group(1)
            code = test_match.group(2).strip()

            if not code:
                continue

            # Extract metadata from comments
            category = self._extract_category(comments)
            target_method = self._extract_target(comments)
            description = self._extract_description(comments)
            exception = self._extract_exception(comments)

            # Extract test name
            name_match = re.search(r"def\s+(test_\w+)", code)
            name = name_match.group(1) if name_match else "test_unknown"

            try:
                # Validate code is syntactically valid
                compile(code, "<string>", "exec")

                tests.append(
                    GeneratedTest(
                        name=name,
                        category=category,
                        code=code,
                        description=description,
                        target_method=target_method,
                        expected_exception=exception,
                    )
                )
            except SyntaxError:
                # Skip malformed tests but continue parsing
                self._log(
                    "parse_warning",
                    {"test_name": name, "reason": "syntax_error"},
                    level="warning",
                )
                continue

        return tests

    def _extract_category(self, comments: str) -> AdversarialCategory:
        """Extract test category from comments."""
        match = re.search(r"#\s*CATEGORY:\s*(\w+)", comments, re.IGNORECASE)
        if match:
            category_str = match.group(1).lower()
            try:
                return AdversarialCategory(category_str)
            except ValueError:
                pass
        return AdversarialCategory.HAPPY_PATH  # Default

    def _extract_target(self, comments: str) -> str:
        """Extract target method from comments."""
        match = re.search(r"#\s*TARGET:\s*(\w+)", comments, re.IGNORECASE)
        return match.group(1) if match else ""

    def _extract_description(self, comments: str) -> str:
        """Extract description from comments."""
        match = re.search(r"#\s*DESCRIPTION:\s*(.+)", comments, re.IGNORECASE)
        return match.group(1).strip() if match else ""

    def _extract_exception(self, comments: str) -> Optional[str]:
        """Extract expected exception from comments."""
        match = re.search(r"#\s*EXCEPTION:\s*(\w+)", comments, re.IGNORECASE)
        return match.group(1) if match else None

    def run_mutation_testing(
        self,
        tests: list[GeneratedTest],
        impl_code: str,
    ) -> MutationTestResult:
        """
        Run mutation testing on generated tests.

        Args:
            tests: List of generated tests.
            impl_code: Implementation code to mutate.

        Returns:
            MutationTestResult with mutation score.
        """
        return self._run_mutmut(tests, impl_code)

    def _run_mutmut(
        self,
        tests: list[GeneratedTest],
        impl_code: str,
    ) -> MutationTestResult:
        """
        Run mutmut mutation testing tool.

        In production, this would call the actual mutmut tool.
        """
        # This is a placeholder - actual implementation would run mutmut
        return MutationTestResult(
            total_mutants=0,
            killed_mutants=0,
            survived_mutants=0,
            mutation_score=0.0,
        )

    def is_test_suite_adequate(
        self,
        result: MutationTestResult,
        threshold: float = 0.8,
    ) -> bool:
        """
        Check if test suite meets quality threshold.

        Args:
            result: Mutation testing result.
            threshold: Required mutation score (default 80%).

        Returns:
            True if mutation score meets threshold.
        """
        return result.mutation_score >= threshold

    def suggest_tests_for_surviving_mutants(
        self,
        spec: InterfaceSpec,
        mutation_result: MutationTestResult,
    ) -> list[GeneratedTest]:
        """
        Suggest additional tests to kill surviving mutants.

        Args:
            spec: Original interface specification.
            mutation_result: Result with surviving mutant details.

        Returns:
            List of suggested tests to kill surviving mutants.
        """
        if not mutation_result.surviving_mutant_details:
            return []

        # Build prompt with surviving mutant info
        prompt = self._build_mutation_improvement_prompt(spec, mutation_result)

        # Call LLM for additional tests
        llm_result = self._call_llm(prompt=prompt)

        if not llm_result.success:
            return []

        return self._parse_tests(llm_result.output)

    def _build_mutation_improvement_prompt(
        self,
        spec: InterfaceSpec,
        mutation_result: MutationTestResult,
    ) -> str:
        """Build prompt to generate tests for surviving mutants."""
        prompt_parts = [
            "# Generate Tests to Kill Surviving Mutants",
            "",
            f"The following mutants survived testing for `{spec.name}`:",
            "",
        ]

        for detail in mutation_result.surviving_mutant_details:
            prompt_parts.append(
                f"- Location: {detail.get('location', 'unknown')}, "
                f"Mutation: {detail.get('mutation', 'unknown')}"
            )

        prompt_parts.extend([
            "",
            "Generate additional tests that would detect these mutations.",
            "",
            "[TESTS]",
            "# Generate tests here",
            "[/TESTS]",
        ])

        return "\n".join(prompt_parts)
