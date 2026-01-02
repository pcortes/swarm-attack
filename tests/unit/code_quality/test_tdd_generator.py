"""Tests for TDDGenerator TDD plan generation.

TDD RED Phase: These tests define the expected behavior of TDDGenerator.
Tests cover:
- Complete TDD plan generation (red, green, refactor phases)
- RED phase test code generation
- GREEN phase fix steps generation
- REFACTOR phase cleanup activities
- Test templates by smell type (Long Method, Hallucinated API, Missing Error Handling)
"""

import pytest

from swarm_attack.code_quality.tdd_generator import TDDGenerator
from swarm_attack.code_quality.models import (
    Finding,
    Severity,
    Category,
    Priority,
    TDDPlan,
    TDDPhase,
)


def create_long_method_finding() -> Finding:
    """Create a sample finding for a Long Method code smell."""
    return Finding(
        finding_id="CQA-001",
        severity=Severity.MEDIUM,
        category=Category.CODE_SMELL,
        file="swarm_attack/agents/coder.py",
        line=45,
        title="Long Method: run()",
        description="The run() method is 127 lines long, making it hard to understand and maintain.",
        expert="Dr. Martin Chen",
        code_snippet="def run(self, context):\n    ...",
        refactoring_pattern="Extract Method",
        refactoring_steps=[
            "Extract lines 50-80 to _validate_context()",
            "Extract lines 81-110 to _execute_tdd_cycle()",
            "Extract lines 111-127 to _generate_output()",
        ],
        priority=Priority.FIX_NOW,
        effort_estimate="medium",
        confidence=0.95,
    )


def create_hallucinated_api_finding() -> Finding:
    """Create a sample finding for a Hallucinated API issue."""
    return Finding(
        finding_id="CQA-002",
        severity=Severity.CRITICAL,
        category=Category.LLM_HALLUCINATION,
        file="swarm_attack/new_feature.py",
        line=10,
        title="Hallucinated Import: magic_helper",
        description="Import 'swarm_attack.utils.magic_helper' does not exist.",
        expert="Dr. James Liu",
        code_snippet="from swarm_attack.utils.magic_helper import do_magic",
        refactoring_pattern="Remove Hallucinated Import",
        refactoring_steps=[
            "Remove the non-existent import",
            "Find a real module that provides similar functionality",
            "Update the code to use the real module",
        ],
        priority=Priority.FIX_NOW,
        effort_estimate="small",
        confidence=0.99,
    )


def create_missing_error_handling_finding() -> Finding:
    """Create a sample finding for Missing Error Handling."""
    return Finding(
        finding_id="CQA-003",
        severity=Severity.HIGH,
        category=Category.ERROR_HANDLING,
        file="swarm_attack/data_loader.py",
        line=25,
        title="Missing Error Handling: load_file()",
        description="File operation in load_file() lacks try/except for IOError.",
        expert="Dr. James Liu",
        code_snippet="def load_file(self, path):\n    return open(path).read()",
        refactoring_pattern="Add Error Handling",
        refactoring_steps=[
            "Wrap file operation in try/except block",
            "Return error result instead of raising exception",
            "Add appropriate error logging",
        ],
        priority=Priority.FIX_NOW,
        effort_estimate="small",
        confidence=0.92,
    )


def create_large_class_finding() -> Finding:
    """Create a sample finding for a Large Class code smell."""
    return Finding(
        finding_id="CQA-004",
        severity=Severity.MEDIUM,
        category=Category.CODE_SMELL,
        file="swarm_attack/agents/dispatcher.py",
        line=1,
        title="Large Class: Dispatcher",
        description="Class 'Dispatcher' is 450 lines long, exceeding the 300 line threshold.",
        expert="Dr. Martin Chen",
        code_snippet="class Dispatcher:",
        refactoring_pattern="Extract Class",
        refactoring_steps=[
            "Identify groups of related methods",
            "Create new classes for each responsibility",
            "Use composition to connect the classes",
        ],
        priority=Priority.FIX_LATER,
        effort_estimate="large",
        confidence=0.88,
    )


class TestTDDGeneratorInit:
    """Tests for TDDGenerator initialization."""

    def test_creates_instance(self):
        """TDDGenerator should be instantiable."""
        generator = TDDGenerator()
        assert generator is not None


class TestGeneratePlan:
    """Tests for the main generate_plan method."""

    def test_generates_complete_plan(self):
        """Generate plan should produce a TDDPlan with all three phases."""
        finding = create_long_method_finding()
        generator = TDDGenerator()

        plan = generator.generate_plan(finding)

        assert isinstance(plan, TDDPlan)
        assert plan.red is not None
        assert plan.green is not None
        assert plan.refactor is not None

    def test_plan_red_phase_is_tdd_phase(self):
        """Red phase should be a TDDPhase instance."""
        finding = create_long_method_finding()
        generator = TDDGenerator()

        plan = generator.generate_plan(finding)

        assert isinstance(plan.red, TDDPhase)

    def test_plan_green_phase_is_tdd_phase(self):
        """Green phase should be a TDDPhase instance."""
        finding = create_long_method_finding()
        generator = TDDGenerator()

        plan = generator.generate_plan(finding)

        assert isinstance(plan.green, TDDPhase)

    def test_plan_refactor_phase_is_tdd_phase(self):
        """Refactor phase should be a TDDPhase instance."""
        finding = create_long_method_finding()
        generator = TDDGenerator()

        plan = generator.generate_plan(finding)

        assert isinstance(plan.refactor, TDDPhase)


class TestGenerateRedPhase:
    """Tests for RED phase generation."""

    def test_red_phase_has_description(self):
        """RED phase should have a description."""
        finding = create_long_method_finding()
        generator = TDDGenerator()

        red_phase = generator.generate_red_phase(finding)

        assert red_phase.description
        assert len(red_phase.description) > 0

    def test_red_phase_has_test_file(self):
        """RED phase should specify a test file."""
        finding = create_long_method_finding()
        generator = TDDGenerator()

        red_phase = generator.generate_red_phase(finding)

        assert red_phase.test_file
        assert red_phase.test_file.endswith(".py")
        assert "test" in red_phase.test_file.lower()

    def test_red_phase_has_test_code(self):
        """RED phase should include executable test code."""
        finding = create_long_method_finding()
        generator = TDDGenerator()

        red_phase = generator.generate_red_phase(finding)

        assert red_phase.test_code
        assert "def test_" in red_phase.test_code
        assert "assert" in red_phase.test_code

    def test_red_phase_test_code_for_long_method(self):
        """RED phase for Long Method should test complexity metrics."""
        finding = create_long_method_finding()
        generator = TDDGenerator()

        red_phase = generator.generate_red_phase(finding)

        # Should reference complexity or line count
        assert "complexity" in red_phase.test_code.lower() or "lines" in red_phase.test_code.lower()

    def test_red_phase_test_code_for_hallucinated_api(self):
        """RED phase for Hallucinated API should test import verification."""
        finding = create_hallucinated_api_finding()
        generator = TDDGenerator()

        red_phase = generator.generate_red_phase(finding)

        # Should reference import verification
        assert "import" in red_phase.test_code.lower()

    def test_red_phase_test_code_for_missing_error_handling(self):
        """RED phase for Missing Error Handling should test graceful error returns."""
        finding = create_missing_error_handling_finding()
        generator = TDDGenerator()

        red_phase = generator.generate_red_phase(finding)

        # Should reference error handling
        assert "error" in red_phase.test_code.lower()


class TestGenerateGreenPhase:
    """Tests for GREEN phase generation."""

    def test_green_phase_has_description(self):
        """GREEN phase should have a description."""
        finding = create_long_method_finding()
        generator = TDDGenerator()

        green_phase = generator.generate_green_phase(finding)

        assert green_phase.description
        assert len(green_phase.description) > 0

    def test_green_phase_has_changes(self):
        """GREEN phase should have a list of changes."""
        finding = create_long_method_finding()
        generator = TDDGenerator()

        green_phase = generator.generate_green_phase(finding)

        assert green_phase.changes
        assert len(green_phase.changes) > 0

    def test_green_phase_changes_include_file_reference(self):
        """GREEN phase changes should reference the file to modify."""
        finding = create_long_method_finding()
        generator = TDDGenerator()

        green_phase = generator.generate_green_phase(finding)

        # Check that at least one change references the file
        changes_str = str(green_phase.changes)
        assert finding.file in changes_str or "coder.py" in changes_str.lower()

    def test_green_phase_uses_refactoring_steps(self):
        """GREEN phase should incorporate the finding's refactoring steps."""
        finding = create_long_method_finding()
        generator = TDDGenerator()

        green_phase = generator.generate_green_phase(finding)

        # The changes should reflect the refactoring steps from the finding
        changes_str = str(green_phase.changes)
        # At least one of the refactoring steps should be reflected
        assert any(
            step_keyword in changes_str.lower()
            for step_keyword in ["extract", "_validate", "_execute", "_generate"]
        )


class TestGenerateRefactorPhase:
    """Tests for REFACTOR phase generation."""

    def test_refactor_phase_has_description(self):
        """REFACTOR phase should have a description."""
        finding = create_long_method_finding()
        generator = TDDGenerator()

        refactor_phase = generator.generate_refactor_phase(finding)

        assert refactor_phase.description
        assert len(refactor_phase.description) > 0

    def test_refactor_phase_has_changes(self):
        """REFACTOR phase should have cleanup activities."""
        finding = create_long_method_finding()
        generator = TDDGenerator()

        refactor_phase = generator.generate_refactor_phase(finding)

        assert refactor_phase.changes
        assert len(refactor_phase.changes) > 0

    def test_refactor_phase_includes_docstrings(self):
        """REFACTOR phase should mention adding docstrings."""
        finding = create_long_method_finding()
        generator = TDDGenerator()

        refactor_phase = generator.generate_refactor_phase(finding)

        changes_str = str(refactor_phase.changes).lower()
        assert "docstring" in changes_str

    def test_refactor_phase_includes_type_hints(self):
        """REFACTOR phase should mention type hints."""
        finding = create_long_method_finding()
        generator = TDDGenerator()

        refactor_phase = generator.generate_refactor_phase(finding)

        changes_str = str(refactor_phase.changes).lower()
        assert "type" in changes_str or "hint" in changes_str

    def test_refactor_phase_includes_verification(self):
        """REFACTOR phase should mention verifying tests still pass."""
        finding = create_long_method_finding()
        generator = TDDGenerator()

        refactor_phase = generator.generate_refactor_phase(finding)

        changes_str = str(refactor_phase.changes).lower()
        assert "test" in changes_str or "verify" in changes_str


class TestGetTestTemplate:
    """Tests for the _get_test_template helper method."""

    def test_returns_template_for_code_smell_long_method(self):
        """Should return template for code_smell / Long Method."""
        generator = TDDGenerator()

        template = generator._get_test_template("code_smell", "Long Method")

        assert template
        assert "def test_" in template
        # Long method template should reference complexity or lines
        assert "complexity" in template.lower() or "lines" in template.lower()

    def test_returns_template_for_hallucinated_api(self):
        """Should return template for llm_hallucination / Hallucinated Import."""
        generator = TDDGenerator()

        template = generator._get_test_template("llm_hallucination", "Hallucinated Import")

        assert template
        assert "def test_" in template
        # Hallucination template should reference import verification
        assert "import" in template.lower()

    def test_returns_template_for_missing_error_handling(self):
        """Should return template for error_handling / Missing Error Handling."""
        generator = TDDGenerator()

        template = generator._get_test_template("error_handling", "Missing Error Handling")

        assert template
        assert "def test_" in template
        # Error handling template should reference error
        assert "error" in template.lower()

    def test_returns_generic_template_for_unknown_type(self):
        """Should return a generic template for unknown smell types."""
        generator = TDDGenerator()

        template = generator._get_test_template("unknown_category", "Unknown Type")

        assert template
        assert "def test_" in template


class TestPlanSerialization:
    """Tests for TDDPlan serialization."""

    def test_plan_to_dict_roundtrip(self):
        """TDDPlan should roundtrip through to_dict/from_dict."""
        finding = create_long_method_finding()
        generator = TDDGenerator()

        plan = generator.generate_plan(finding)
        plan_dict = plan.to_dict()
        restored_plan = TDDPlan.from_dict(plan_dict)

        assert restored_plan.red.description == plan.red.description
        assert restored_plan.green.description == plan.green.description
        assert restored_plan.refactor.description == plan.refactor.description


class TestMultipleFindingTypes:
    """Tests for generating plans for different finding types."""

    def test_generates_plan_for_long_method(self):
        """Should generate a complete plan for Long Method finding."""
        finding = create_long_method_finding()
        generator = TDDGenerator()

        plan = generator.generate_plan(finding)

        assert plan.red.test_code
        assert plan.green.changes
        assert plan.refactor.changes

    def test_generates_plan_for_hallucinated_api(self):
        """Should generate a complete plan for Hallucinated API finding."""
        finding = create_hallucinated_api_finding()
        generator = TDDGenerator()

        plan = generator.generate_plan(finding)

        assert plan.red.test_code
        assert plan.green.changes
        assert plan.refactor.changes

    def test_generates_plan_for_missing_error_handling(self):
        """Should generate a complete plan for Missing Error Handling finding."""
        finding = create_missing_error_handling_finding()
        generator = TDDGenerator()

        plan = generator.generate_plan(finding)

        assert plan.red.test_code
        assert plan.green.changes
        assert plan.refactor.changes

    def test_generates_plan_for_large_class(self):
        """Should generate a complete plan for Large Class finding."""
        finding = create_large_class_finding()
        generator = TDDGenerator()

        plan = generator.generate_plan(finding)

        assert plan.red.test_code
        assert plan.green.changes
        assert plan.refactor.changes
