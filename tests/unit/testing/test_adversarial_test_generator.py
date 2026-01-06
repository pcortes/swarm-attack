"""
Tests for AdversarialTestGenerator.

TDD Tests for a test generator that operates in an isolated context:
- Receives only spec/interface, NOT implementation
- Generates tests based on expected behavior
- Includes edge cases and error conditions
- Supports mutation testing to verify test quality
"""

import pytest
from dataclasses import dataclass
from typing import Optional
from unittest.mock import MagicMock, patch

from swarm_attack.testing.adversarial_test_generator import (
    AdversarialTestGenerator,
    InterfaceSpec,
    GeneratedTest,
    GenerationResult,
    AdversarialCategory,
    MutationTestResult,
    GenerationError,
)
from swarm_attack.config import SwarmConfig


# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture
def mock_config(tmp_path):
    """Create a mock SwarmConfig for testing."""
    config = MagicMock(spec=SwarmConfig)
    config.repo_root = str(tmp_path)
    config.claude = MagicMock()
    config.claude.binary = "claude"
    config.claude.max_turns = 10
    return config


@pytest.fixture
def sample_spec():
    """Create a sample interface specification."""
    return InterfaceSpec(
        name="Calculator",
        description="A simple calculator that performs basic arithmetic operations",
        methods=[
            {
                "name": "add",
                "signature": "def add(self, a: int, b: int) -> int",
                "description": "Add two integers and return the sum",
                "parameters": [
                    {"name": "a", "type": "int", "description": "First operand"},
                    {"name": "b", "type": "int", "description": "Second operand"},
                ],
                "returns": {"type": "int", "description": "Sum of a and b"},
                "raises": [],
            },
            {
                "name": "divide",
                "signature": "def divide(self, a: int, b: int) -> float",
                "description": "Divide a by b and return the result",
                "parameters": [
                    {"name": "a", "type": "int", "description": "Dividend"},
                    {"name": "b", "type": "int", "description": "Divisor"},
                ],
                "returns": {"type": "float", "description": "Result of a / b"},
                "raises": [
                    {"exception": "ZeroDivisionError", "condition": "when b is 0"}
                ],
            },
        ],
        constraints=[
            "All parameters must be integers",
            "Division by zero must raise ZeroDivisionError",
        ],
        examples=[
            {"call": "calculator.add(2, 3)", "result": "5"},
            {"call": "calculator.divide(10, 2)", "result": "5.0"},
        ],
    )


@pytest.fixture
def generator(mock_config):
    """Create an AdversarialTestGenerator instance."""
    return AdversarialTestGenerator(config=mock_config)


# ============================================================================
# InterfaceSpec Tests
# ============================================================================


class TestInterfaceSpec:
    """Tests for InterfaceSpec dataclass."""

    def test_create_interface_spec(self):
        """Test creating an InterfaceSpec with required fields."""
        spec = InterfaceSpec(
            name="MyClass",
            description="A test class",
            methods=[],
        )
        assert spec.name == "MyClass"
        assert spec.description == "A test class"
        assert spec.methods == []
        assert spec.constraints == []
        assert spec.examples == []

    def test_interface_spec_with_all_fields(self, sample_spec):
        """Test InterfaceSpec with all optional fields."""
        assert sample_spec.name == "Calculator"
        assert len(sample_spec.methods) == 2
        assert len(sample_spec.constraints) == 2
        assert len(sample_spec.examples) == 2

    def test_interface_spec_to_dict(self, sample_spec):
        """Test converting InterfaceSpec to dictionary."""
        d = sample_spec.to_dict()
        assert d["name"] == "Calculator"
        assert len(d["methods"]) == 2
        assert "constraints" in d
        assert "examples" in d

    def test_interface_spec_from_dict(self):
        """Test creating InterfaceSpec from dictionary."""
        data = {
            "name": "Parser",
            "description": "Parses input strings",
            "methods": [
                {
                    "name": "parse",
                    "signature": "def parse(self, text: str) -> dict",
                    "description": "Parse text into dict",
                }
            ],
            "constraints": ["Input must be valid JSON"],
            "examples": [],
        }
        spec = InterfaceSpec.from_dict(data)
        assert spec.name == "Parser"
        assert len(spec.methods) == 1
        assert spec.methods[0]["name"] == "parse"

    def test_interface_spec_from_dict_missing_optional(self):
        """Test from_dict handles missing optional fields."""
        data = {
            "name": "Minimal",
            "description": "Minimal spec",
            "methods": [],
        }
        spec = InterfaceSpec.from_dict(data)
        assert spec.constraints == []
        assert spec.examples == []

    def test_interface_spec_validates_required_fields(self):
        """Test that InterfaceSpec requires name and description."""
        with pytest.raises(TypeError):
            InterfaceSpec(name="NoDesc")  # Missing description


# ============================================================================
# GeneratedTest Tests
# ============================================================================


class TestGeneratedTest:
    """Tests for GeneratedTest dataclass."""

    def test_create_generated_test(self):
        """Test creating a GeneratedTest."""
        test = GeneratedTest(
            name="test_add_positive_numbers",
            category=AdversarialCategory.HAPPY_PATH,
            code="def test_add_positive_numbers():\n    assert add(2, 3) == 5",
            description="Test adding two positive numbers",
            target_method="add",
        )
        assert test.name == "test_add_positive_numbers"
        assert test.category == AdversarialCategory.HAPPY_PATH
        assert "assert add(2, 3) == 5" in test.code

    def test_generated_test_with_edge_case(self):
        """Test creating an edge case test."""
        test = GeneratedTest(
            name="test_add_negative_numbers",
            category=AdversarialCategory.EDGE_CASE,
            code="def test_add_negative_numbers():\n    assert add(-1, -2) == -3",
            description="Test adding negative numbers",
            target_method="add",
        )
        assert test.category == AdversarialCategory.EDGE_CASE

    def test_generated_test_with_error_condition(self):
        """Test creating an error condition test."""
        test = GeneratedTest(
            name="test_divide_by_zero",
            category=AdversarialCategory.ERROR_CONDITION,
            code="def test_divide_by_zero():\n    with pytest.raises(ZeroDivisionError):\n        divide(10, 0)",
            description="Test that division by zero raises error",
            target_method="divide",
            expected_exception="ZeroDivisionError",
        )
        assert test.category == AdversarialCategory.ERROR_CONDITION
        assert test.expected_exception == "ZeroDivisionError"

    def test_generated_test_to_dict(self):
        """Test converting GeneratedTest to dictionary."""
        test = GeneratedTest(
            name="test_example",
            category=AdversarialCategory.HAPPY_PATH,
            code="def test_example(): pass",
            description="Example test",
            target_method="example",
        )
        d = test.to_dict()
        assert d["name"] == "test_example"
        assert d["category"] == "happy_path"
        assert d["code"] == "def test_example(): pass"

    def test_generated_test_from_dict(self):
        """Test creating GeneratedTest from dictionary."""
        data = {
            "name": "test_foo",
            "category": "edge_case",
            "code": "def test_foo(): pass",
            "description": "Test foo",
            "target_method": "foo",
        }
        test = GeneratedTest.from_dict(data)
        assert test.name == "test_foo"
        assert test.category == AdversarialCategory.EDGE_CASE


# ============================================================================
# AdversarialCategory Tests
# ============================================================================


class TestAdversarialCategory:
    """Tests for AdversarialCategory enum."""

    def test_happy_path_category(self):
        """Test HAPPY_PATH category."""
        assert AdversarialCategory.HAPPY_PATH.value == "happy_path"

    def test_edge_case_category(self):
        """Test EDGE_CASE category."""
        assert AdversarialCategory.EDGE_CASE.value == "edge_case"

    def test_error_condition_category(self):
        """Test ERROR_CONDITION category."""
        assert AdversarialCategory.ERROR_CONDITION.value == "error_condition"

    def test_boundary_category(self):
        """Test BOUNDARY category."""
        assert AdversarialCategory.BOUNDARY.value == "boundary"

    def test_null_empty_category(self):
        """Test NULL_EMPTY category."""
        assert AdversarialCategory.NULL_EMPTY.value == "null_empty"

    def test_type_coercion_category(self):
        """Test TYPE_COERCION category."""
        assert AdversarialCategory.TYPE_COERCION.value == "type_coercion"


# ============================================================================
# GenerationResult Tests
# ============================================================================


class TestGenerationResult:
    """Tests for GenerationResult dataclass."""

    def test_create_result(self):
        """Test creating a GenerationResult."""
        result = GenerationResult(
            success=True,
            tests=[],
            spec_name="Calculator",
        )
        assert result.success is True
        assert result.tests == []
        assert result.spec_name == "Calculator"

    def test_result_with_tests(self):
        """Test result with generated tests."""
        tests = [
            GeneratedTest(
                name="test_add",
                category=AdversarialCategory.HAPPY_PATH,
                code="def test_add(): pass",
                description="Test add",
                target_method="add",
            ),
        ]
        result = GenerationResult(
            success=True,
            tests=tests,
            spec_name="Calculator",
        )
        assert len(result.tests) == 1
        assert result.tests[0].name == "test_add"

    def test_result_with_errors(self):
        """Test result with errors."""
        result = GenerationResult(
            success=False,
            tests=[],
            spec_name="Broken",
            errors=["Failed to parse spec", "Invalid method signature"],
        )
        assert not result.success
        assert len(result.errors) == 2

    def test_result_test_count_by_category(self):
        """Test counting tests by category."""
        tests = [
            GeneratedTest(
                name="test1",
                category=AdversarialCategory.HAPPY_PATH,
                code="",
                description="",
                target_method="",
            ),
            GeneratedTest(
                name="test2",
                category=AdversarialCategory.HAPPY_PATH,
                code="",
                description="",
                target_method="",
            ),
            GeneratedTest(
                name="test3",
                category=AdversarialCategory.EDGE_CASE,
                code="",
                description="",
                target_method="",
            ),
        ]
        result = GenerationResult(
            success=True,
            tests=tests,
            spec_name="Test",
        )
        counts = result.get_test_counts_by_category()
        assert counts[AdversarialCategory.HAPPY_PATH] == 2
        assert counts[AdversarialCategory.EDGE_CASE] == 1
        assert counts.get(AdversarialCategory.ERROR_CONDITION, 0) == 0

    def test_result_to_dict(self):
        """Test converting result to dictionary."""
        result = GenerationResult(
            success=True,
            tests=[],
            spec_name="Test",
        )
        d = result.to_dict()
        assert d["success"] is True
        assert d["spec_name"] == "Test"
        assert "tests" in d

    def test_result_get_combined_code(self):
        """Test getting combined test code."""
        tests = [
            GeneratedTest(
                name="test_a",
                category=AdversarialCategory.HAPPY_PATH,
                code="def test_a():\n    pass",
                description="",
                target_method="",
            ),
            GeneratedTest(
                name="test_b",
                category=AdversarialCategory.EDGE_CASE,
                code="def test_b():\n    pass",
                description="",
                target_method="",
            ),
        ]
        result = GenerationResult(
            success=True,
            tests=tests,
            spec_name="Test",
        )
        combined = result.get_combined_code()
        assert "def test_a():" in combined
        assert "def test_b():" in combined


# ============================================================================
# AdversarialTestGenerator Tests
# ============================================================================


class TestAdversarialTestGeneratorInit:
    """Tests for AdversarialTestGenerator initialization."""

    def test_init_with_config(self, mock_config):
        """Test initialization with config."""
        gen = AdversarialTestGenerator(config=mock_config)
        assert gen.config == mock_config
        assert gen.name == "adversarial_test_generator"

    def test_init_with_logger(self, mock_config):
        """Test initialization with logger."""
        logger = MagicMock()
        gen = AdversarialTestGenerator(config=mock_config, logger=logger)
        assert gen._logger == logger


class TestAdversarialTestGeneratorGenerate:
    """Tests for generate() method."""

    def test_generate_from_spec(self, generator, sample_spec):
        """Test generating tests from a spec."""
        with patch.object(generator, "_call_llm") as mock_llm:
            mock_llm.return_value = MagicMock(
                success=True,
                output="""
[TESTS]
def test_add_positive_numbers():
    calc = Calculator()
    assert calc.add(2, 3) == 5

def test_add_negative_numbers():
    calc = Calculator()
    assert calc.add(-1, -2) == -3

def test_divide_by_zero():
    calc = Calculator()
    with pytest.raises(ZeroDivisionError):
        calc.divide(10, 0)
[/TESTS]
""",
            )
            result = generator.generate(sample_spec)

            assert result.success is True
            assert len(result.tests) > 0
            assert result.spec_name == "Calculator"

    def test_generate_isolates_from_implementation(self, generator, sample_spec):
        """Test that generator does NOT receive implementation details."""
        with patch.object(generator, "_call_llm") as mock_llm:
            mock_llm.return_value = MagicMock(success=True, output="[TESTS][/TESTS]")

            # Pass implementation details - they should be ignored
            generator.generate(
                sample_spec,
                forbidden_context={"implementation": "def add(a, b): return a + b"},
            )

            # Verify the LLM call doesn't include implementation
            call_args = mock_llm.call_args
            prompt = call_args[1]["prompt"]
            assert "return a + b" not in prompt

    def test_generate_includes_edge_cases(self, generator, sample_spec):
        """Test that generation includes edge cases."""
        with patch.object(generator, "_call_llm") as mock_llm:
            mock_llm.return_value = MagicMock(
                success=True,
                output="""
[TESTS]
# CATEGORY: edge_case
def test_add_large_numbers():
    calc = Calculator()
    assert calc.add(2**31 - 1, 1) == 2**31
[/TESTS]
""",
            )
            result = generator.generate(sample_spec)

            edge_cases = [t for t in result.tests if t.category == AdversarialCategory.EDGE_CASE]
            assert len(edge_cases) > 0

    def test_generate_includes_error_conditions(self, generator, sample_spec):
        """Test that generation includes error condition tests."""
        with patch.object(generator, "_call_llm") as mock_llm:
            mock_llm.return_value = MagicMock(
                success=True,
                output="""
[TESTS]
# CATEGORY: error_condition
# EXCEPTION: ZeroDivisionError
def test_divide_by_zero():
    calc = Calculator()
    with pytest.raises(ZeroDivisionError):
        calc.divide(10, 0)
[/TESTS]
""",
            )
            result = generator.generate(sample_spec)

            error_tests = [
                t for t in result.tests if t.category == AdversarialCategory.ERROR_CONDITION
            ]
            assert len(error_tests) > 0

    def test_generate_returns_failure_on_llm_error(self, generator, sample_spec):
        """Test that generation returns failure when LLM fails."""
        with patch.object(generator, "_call_llm") as mock_llm:
            mock_llm.return_value = MagicMock(
                success=False,
                error="Rate limit exceeded",
            )
            result = generator.generate(sample_spec)

            assert result.success is False
            assert "Rate limit exceeded" in result.errors[0]

    def test_generate_handles_empty_spec(self, generator):
        """Test handling of empty/minimal spec."""
        empty_spec = InterfaceSpec(
            name="Empty",
            description="An empty class",
            methods=[],
        )
        with patch.object(generator, "_call_llm") as mock_llm:
            mock_llm.return_value = MagicMock(
                success=True,
                output="[TESTS][/TESTS]",
            )
            result = generator.generate(empty_spec)

            assert result.success is True
            assert len(result.tests) == 0


class TestAdversarialTestGeneratorPromptBuilding:
    """Tests for prompt building."""

    def test_build_prompt_includes_spec_name(self, generator, sample_spec):
        """Test that prompt includes spec name."""
        prompt = generator._build_prompt(sample_spec)
        assert "Calculator" in prompt

    def test_build_prompt_includes_method_signatures(self, generator, sample_spec):
        """Test that prompt includes method signatures."""
        prompt = generator._build_prompt(sample_spec)
        assert "def add(self, a: int, b: int) -> int" in prompt
        assert "def divide(self, a: int, b: int) -> float" in prompt

    def test_build_prompt_includes_constraints(self, generator, sample_spec):
        """Test that prompt includes constraints."""
        prompt = generator._build_prompt(sample_spec)
        assert "Division by zero must raise ZeroDivisionError" in prompt

    def test_build_prompt_includes_examples(self, generator, sample_spec):
        """Test that prompt includes examples."""
        prompt = generator._build_prompt(sample_spec)
        assert "calculator.add(2, 3)" in prompt

    def test_build_prompt_excludes_implementation(self, generator, sample_spec):
        """Test that prompt explicitly excludes implementation hints."""
        prompt = generator._build_prompt(sample_spec)
        # The prompt should instruct NOT to assume implementation
        assert "implementation" in prompt.lower() or "behavior" in prompt.lower()

    def test_build_prompt_requests_categories(self, generator, sample_spec):
        """Test that prompt requests tests for all categories."""
        prompt = generator._build_prompt(sample_spec)
        assert "edge" in prompt.lower()
        assert "error" in prompt.lower()
        assert "boundary" in prompt.lower()


class TestAdversarialTestGeneratorParsing:
    """Tests for output parsing."""

    def test_parse_single_test(self, generator):
        """Test parsing a single test from output."""
        output = """
[TESTS]
# CATEGORY: happy_path
# TARGET: add
# DESCRIPTION: Test basic addition
def test_add_basic():
    assert add(1, 2) == 3
[/TESTS]
"""
        tests = generator._parse_tests(output)
        assert len(tests) == 1
        assert tests[0].name == "test_add_basic"
        assert tests[0].category == AdversarialCategory.HAPPY_PATH
        assert tests[0].target_method == "add"

    def test_parse_multiple_tests(self, generator):
        """Test parsing multiple tests from output."""
        output = """
[TESTS]
# CATEGORY: happy_path
def test_one():
    pass

# CATEGORY: edge_case
def test_two():
    pass

# CATEGORY: error_condition
def test_three():
    pass
[/TESTS]
"""
        tests = generator._parse_tests(output)
        assert len(tests) == 3

    def test_parse_extracts_category(self, generator):
        """Test that parser extracts category from comment."""
        output = """
[TESTS]
# CATEGORY: boundary
def test_boundary():
    pass
[/TESTS]
"""
        tests = generator._parse_tests(output)
        assert tests[0].category == AdversarialCategory.BOUNDARY

    def test_parse_extracts_exception(self, generator):
        """Test that parser extracts expected exception."""
        output = """
[TESTS]
# CATEGORY: error_condition
# EXCEPTION: ValueError
def test_raises_value_error():
    with pytest.raises(ValueError):
        func(-1)
[/TESTS]
"""
        tests = generator._parse_tests(output)
        assert tests[0].expected_exception == "ValueError"

    def test_parse_handles_no_tests(self, generator):
        """Test parsing when no tests are generated."""
        output = "[TESTS][/TESTS]"
        tests = generator._parse_tests(output)
        assert tests == []

    def test_parse_handles_malformed_output(self, generator):
        """Test parsing handles malformed output gracefully."""
        output = "No tests here, just random text"
        tests = generator._parse_tests(output)
        assert tests == []


# ============================================================================
# Mutation Testing Tests
# ============================================================================


class TestMutationTestResult:
    """Tests for MutationTestResult dataclass."""

    def test_create_result(self):
        """Test creating a MutationTestResult."""
        result = MutationTestResult(
            total_mutants=10,
            killed_mutants=8,
            survived_mutants=2,
            mutation_score=0.8,
        )
        assert result.total_mutants == 10
        assert result.killed_mutants == 8
        assert result.mutation_score == 0.8

    def test_mutation_score_calculation(self):
        """Test mutation score is correctly calculated."""
        result = MutationTestResult(
            total_mutants=10,
            killed_mutants=5,
            survived_mutants=5,
            mutation_score=0.5,
        )
        assert result.mutation_score == 0.5

    def test_result_to_dict(self):
        """Test converting to dictionary."""
        result = MutationTestResult(
            total_mutants=10,
            killed_mutants=10,
            survived_mutants=0,
            mutation_score=1.0,
        )
        d = result.to_dict()
        assert d["total_mutants"] == 10
        assert d["mutation_score"] == 1.0

    def test_result_with_surviving_mutants(self):
        """Test result includes surviving mutant info."""
        result = MutationTestResult(
            total_mutants=5,
            killed_mutants=3,
            survived_mutants=2,
            mutation_score=0.6,
            surviving_mutant_details=[
                {"location": "line 10", "mutation": "changed + to -"},
                {"location": "line 15", "mutation": "removed condition"},
            ],
        )
        assert len(result.surviving_mutant_details) == 2


class TestAdversarialTestGeneratorMutation:
    """Tests for mutation testing integration."""

    def test_run_mutation_testing(self, generator):
        """Test running mutation tests on generated tests."""
        tests = [
            GeneratedTest(
                name="test_add",
                category=AdversarialCategory.HAPPY_PATH,
                code="def test_add():\n    assert add(1, 2) == 3",
                description="Test add",
                target_method="add",
            ),
        ]
        impl_code = "def add(a, b):\n    return a + b"

        with patch.object(generator, "_run_mutmut") as mock_mutmut:
            mock_mutmut.return_value = MutationTestResult(
                total_mutants=5,
                killed_mutants=4,
                survived_mutants=1,
                mutation_score=0.8,
            )
            result = generator.run_mutation_testing(tests, impl_code)

            assert result.total_mutants == 5
            assert result.mutation_score == 0.8

    def test_mutation_score_threshold(self, generator):
        """Test mutation score threshold check."""
        result = MutationTestResult(
            total_mutants=10,
            killed_mutants=7,
            survived_mutants=3,
            mutation_score=0.7,
        )
        # Threshold is 80% by default
        assert not generator.is_test_suite_adequate(result, threshold=0.8)
        assert generator.is_test_suite_adequate(result, threshold=0.6)

    def test_suggest_additional_tests(self, generator):
        """Test suggesting additional tests for surviving mutants."""
        mutation_result = MutationTestResult(
            total_mutants=5,
            killed_mutants=3,
            survived_mutants=2,
            mutation_score=0.6,
            surviving_mutant_details=[
                {"location": "line 10", "mutation": "changed + to -"},
            ],
        )
        spec = InterfaceSpec(
            name="Calculator",
            description="Calculator",
            methods=[
                {
                    "name": "add",
                    "signature": "def add(a, b)",
                    "description": "Add numbers",
                }
            ],
        )

        with patch.object(generator, "_call_llm") as mock_llm:
            mock_llm.return_value = MagicMock(
                success=True,
                output="""
[TESTS]
# CATEGORY: boundary
def test_add_detects_sign_change():
    # This test should catch the + to - mutation
    assert add(5, 3) == 8
    assert add(5, -3) == 2  # Would be wrong if + became -
[/TESTS]
""",
            )
            suggestions = generator.suggest_tests_for_surviving_mutants(
                spec, mutation_result
            )

            assert len(suggestions) > 0


# ============================================================================
# Integration Tests
# ============================================================================


class TestAdversarialTestGeneratorIntegration:
    """Integration-style tests for the full workflow."""

    def test_full_generation_workflow(self, generator, sample_spec):
        """Test the full generation workflow."""
        with patch.object(generator, "_call_llm") as mock_llm:
            mock_llm.return_value = MagicMock(
                success=True,
                output="""
[TESTS]
# CATEGORY: happy_path
# TARGET: add
def test_add_positive():
    calc = Calculator()
    assert calc.add(2, 3) == 5

# CATEGORY: edge_case
# TARGET: add
def test_add_zero():
    calc = Calculator()
    assert calc.add(0, 0) == 0

# CATEGORY: error_condition
# TARGET: divide
# EXCEPTION: ZeroDivisionError
def test_divide_by_zero():
    calc = Calculator()
    with pytest.raises(ZeroDivisionError):
        calc.divide(10, 0)

# CATEGORY: boundary
# TARGET: add
def test_add_max_int():
    calc = Calculator()
    import sys
    result = calc.add(sys.maxsize, 0)
    assert result == sys.maxsize
[/TESTS]
""",
            )
            result = generator.generate(sample_spec)

            assert result.success is True
            assert len(result.tests) == 4

            # Verify categories
            categories = [t.category for t in result.tests]
            assert AdversarialCategory.HAPPY_PATH in categories
            assert AdversarialCategory.EDGE_CASE in categories
            assert AdversarialCategory.ERROR_CONDITION in categories
            assert AdversarialCategory.BOUNDARY in categories

    def test_generate_and_verify_quality(self, generator, sample_spec):
        """Test generating tests and verifying quality with mutation testing."""
        with patch.object(generator, "_call_llm") as mock_llm:
            mock_llm.return_value = MagicMock(
                success=True,
                output="""
[TESTS]
# CATEGORY: happy_path
def test_add():
    assert add(1, 2) == 3
[/TESTS]
""",
            )
            result = generator.generate(sample_spec)
            assert result.success

        with patch.object(generator, "_run_mutmut") as mock_mutmut:
            mock_mutmut.return_value = MutationTestResult(
                total_mutants=5,
                killed_mutants=5,
                survived_mutants=0,
                mutation_score=1.0,
            )
            mutation_result = generator.run_mutation_testing(
                result.tests, "def add(a, b): return a + b"
            )
            assert mutation_result.mutation_score == 1.0
            assert generator.is_test_suite_adequate(mutation_result)


# ============================================================================
# Error Handling Tests
# ============================================================================


class TestAdversarialTestGeneratorErrors:
    """Tests for error handling."""

    def test_raises_error_on_invalid_spec(self, generator):
        """Test that invalid spec raises GenerationError."""
        with pytest.raises(GenerationError):
            generator.generate(None)

    def test_handles_llm_timeout(self, generator, sample_spec):
        """Test handling of LLM timeout."""
        with patch.object(generator, "_call_llm") as mock_llm:
            mock_llm.side_effect = TimeoutError("LLM call timed out")
            result = generator.generate(sample_spec)

            assert result.success is False
            assert "timeout" in result.errors[0].lower()

    def test_handles_llm_rate_limit(self, generator, sample_spec):
        """Test handling of rate limit errors."""
        with patch.object(generator, "_call_llm") as mock_llm:
            mock_llm.return_value = MagicMock(
                success=False,
                error="Rate limit exceeded",
            )
            result = generator.generate(sample_spec)

            assert result.success is False

    def test_recovers_from_partial_output(self, generator, sample_spec):
        """Test recovery from partially valid LLM output."""
        with patch.object(generator, "_call_llm") as mock_llm:
            mock_llm.return_value = MagicMock(
                success=True,
                output="""
[TESTS]
# CATEGORY: happy_path
def test_valid():
    pass

# This is malformed
def test_incomplete(
[/TESTS]
""",
            )
            result = generator.generate(sample_spec)

            # Should recover with at least the valid test
            assert result.success is True
            assert len(result.tests) >= 1
