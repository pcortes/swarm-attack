"""Tests for the RefactorSuggester module.

Tests the refactoring suggestion engine that maps detected issues
to specific refactoring patterns, steps, and effort estimates.
"""

import pytest

from swarm_attack.code_quality.models import (
    Finding,
    Severity,
    Category,
    Priority,
)
from swarm_attack.code_quality.refactor_suggester import RefactorSuggester


# ============================================================
# Test: suggest_refactoring()
# ============================================================

class TestSuggestRefactoring:
    """Tests for the suggest_refactoring() method."""

    def test_suggests_extract_method_for_long_method(self):
        """Long Method smell should suggest Extract Method refactoring."""
        finding = Finding(
            finding_id="CQA-001",
            severity=Severity.MEDIUM,
            category=Category.CODE_SMELL,
            file="test.py",
            line=10,
            title="Long Method: process_data",
            description="Method 'process_data' is 75 lines long",
        )
        suggester = RefactorSuggester()
        result = suggester.suggest_refactoring(finding)
        assert result == "Extract Method"

    def test_suggests_extract_class_for_large_class(self):
        """Large Class smell should suggest Extract Class refactoring."""
        finding = Finding(
            finding_id="CQA-002",
            severity=Severity.MEDIUM,
            category=Category.CODE_SMELL,
            file="test.py",
            line=1,
            title="Large Class: DataProcessor",
            description="Class 'DataProcessor' is 450 lines long",
        )
        suggester = RefactorSuggester()
        result = suggester.suggest_refactoring(finding)
        assert result == "Extract Class"

    def test_suggests_move_method_for_feature_envy(self):
        """Feature Envy smell should suggest Move Method refactoring."""
        finding = Finding(
            finding_id="CQA-003",
            severity=Severity.MEDIUM,
            category=Category.CODE_SMELL,
            file="test.py",
            line=25,
            title="Feature Envy: calculate_total",
            description="Method 'calculate_total' uses more features from Order class",
        )
        suggester = RefactorSuggester()
        result = suggester.suggest_refactoring(finding)
        assert result == "Move Method"

    def test_suggests_value_object_for_primitive_obsession(self):
        """Primitive Obsession should suggest Replace with Value Object."""
        finding = Finding(
            finding_id="CQA-004",
            severity=Severity.LOW,
            category=Category.CODE_SMELL,
            file="test.py",
            line=15,
            title="Primitive Obsession",
            description="Multiple primitive values used for money representation",
        )
        suggester = RefactorSuggester()
        result = suggester.suggest_refactoring(finding)
        assert result == "Replace with Value Object"

    def test_suggests_polymorphism_for_switch_on_type(self):
        """Switch on Type smell should suggest Replace Conditional with Polymorphism."""
        finding = Finding(
            finding_id="CQA-005",
            severity=Severity.MEDIUM,
            category=Category.SOLID,
            file="test.py",
            line=30,
            title="OCP Violation: Type Check Chain",
            description="Found 3 isinstance checks in an if/elif chain",
        )
        suggester = RefactorSuggester()
        result = suggester.suggest_refactoring(finding)
        assert result == "Replace Conditional with Polymorphism"

    def test_suggests_parameter_object_for_too_many_parameters(self):
        """Too Many Parameters should suggest Introduce Parameter Object."""
        finding = Finding(
            finding_id="CQA-006",
            severity=Severity.MEDIUM,
            category=Category.CODE_SMELL,
            file="test.py",
            line=40,
            title="Too Many Parameters: create_user",
            description="Function 'create_user' has 8 parameters",
        )
        suggester = RefactorSuggester()
        result = suggester.suggest_refactoring(finding)
        assert result == "Introduce Parameter Object"

    def test_suggests_extract_class_for_data_clump(self):
        """Data Clump smell should suggest Extract Class refactoring."""
        finding = Finding(
            finding_id="CQA-007",
            severity=Severity.LOW,
            category=Category.CODE_SMELL,
            file="test.py",
            line=50,
            title="Data Clump",
            description="Same group of variables appears in multiple places",
        )
        suggester = RefactorSuggester()
        result = suggester.suggest_refactoring(finding)
        assert result == "Extract Class"

    def test_suggests_hide_delegate_for_message_chain(self):
        """Message Chain smell should suggest Hide Delegate refactoring."""
        finding = Finding(
            finding_id="CQA-008",
            severity=Severity.LOW,
            category=Category.CODE_SMELL,
            file="test.py",
            line=60,
            title="Message Chain",
            description="Long chain of method calls: a.b.c.d.e.get_value()",
        )
        suggester = RefactorSuggester()
        result = suggester.suggest_refactoring(finding)
        assert result == "Hide Delegate"

    def test_suggests_extract_class_for_god_class(self):
        """God Class smell should suggest Extract Class (split by responsibility)."""
        finding = Finding(
            finding_id="CQA-009",
            severity=Severity.HIGH,
            category=Category.CODE_SMELL,
            file="test.py",
            line=1,
            title="God Class: ApplicationManager",
            description="Class handles database, email, logging, and UI",
        )
        suggester = RefactorSuggester()
        result = suggester.suggest_refactoring(finding)
        assert result == "Extract Class (split by responsibility)"

    def test_suggests_guard_clauses_for_deep_nesting(self):
        """Deep Nesting smell should suggest Extract Method / Guard Clauses."""
        finding = Finding(
            finding_id="CQA-010",
            severity=Severity.MEDIUM,
            category=Category.CODE_SMELL,
            file="test.py",
            line=70,
            title="Deep Nesting: process_request",
            description="Function has 6 levels of nesting",
        )
        suggester = RefactorSuggester()
        result = suggester.suggest_refactoring(finding)
        assert result == "Extract Method / Guard Clauses"

    def test_suggests_extract_method_for_duplicate_code(self):
        """Duplicate Code smell should suggest Extract Method or Base Class."""
        finding = Finding(
            finding_id="CQA-011",
            severity=Severity.MEDIUM,
            category=Category.CODE_SMELL,
            file="test.py",
            line=80,
            title="Duplicate Code",
            description="Same code block appears 3 times",
        )
        suggester = RefactorSuggester()
        result = suggester.suggest_refactoring(finding)
        assert result == "Extract Method or Base Class"

    def test_suggests_srp_extract_class_for_srp_violation(self):
        """SRP Violation should suggest Extract Class."""
        finding = Finding(
            finding_id="SOLID-001",
            severity=Severity.MEDIUM,
            category=Category.SOLID,
            file="test.py",
            line=1,
            title="SRP Violation: UserService",
            description="Class has 4 distinct responsibilities",
        )
        suggester = RefactorSuggester()
        result = suggester.suggest_refactoring(finding)
        assert result == "Extract Class"

    def test_suggests_dependency_injection_for_dip_violation(self):
        """DIP Violation should suggest Inject Dependencies."""
        finding = Finding(
            finding_id="SOLID-002",
            severity=Severity.MEDIUM,
            category=Category.SOLID,
            file="test.py",
            line=10,
            title="DIP Violation: PaymentProcessor",
            description="Class instantiates its dependencies directly",
        )
        suggester = RefactorSuggester()
        result = suggester.suggest_refactoring(finding)
        assert result == "Inject Dependencies"

    def test_returns_unknown_for_unrecognized_smell(self):
        """Unknown smell types should return descriptive message."""
        finding = Finding(
            finding_id="CQA-999",
            severity=Severity.LOW,
            category=Category.CODE_SMELL,
            file="test.py",
            line=100,
            title="Some Unknown Issue",
            description="This is a novel issue we haven't seen before",
        )
        suggester = RefactorSuggester()
        result = suggester.suggest_refactoring(finding)
        assert result == "Manual Review Required"


# ============================================================
# Test: generate_steps()
# ============================================================

class TestGenerateSteps:
    """Tests for the generate_steps() method."""

    def test_generates_steps_for_extract_method(self):
        """Extract Method refactoring should have specific steps."""
        finding = Finding(
            finding_id="CQA-001",
            severity=Severity.MEDIUM,
            category=Category.CODE_SMELL,
            file="test.py",
            line=10,
            title="Long Method: process_data",
            description="Method too long",
        )
        suggester = RefactorSuggester()
        refactoring = "Extract Method"
        steps = suggester.generate_steps(finding, refactoring)

        assert len(steps) >= 3
        assert any("identify" in step.lower() for step in steps)
        assert any("extract" in step.lower() for step in steps)

    def test_generates_steps_for_extract_class(self):
        """Extract Class refactoring should have specific steps."""
        finding = Finding(
            finding_id="CQA-002",
            severity=Severity.MEDIUM,
            category=Category.CODE_SMELL,
            file="test.py",
            line=1,
            title="Large Class: DataProcessor",
            description="Class too large",
        )
        suggester = RefactorSuggester()
        refactoring = "Extract Class"
        steps = suggester.generate_steps(finding, refactoring)

        assert len(steps) >= 3
        assert any("class" in step.lower() for step in steps)
        assert any("move" in step.lower() for step in steps)

    def test_generates_steps_for_polymorphism(self):
        """Replace Conditional with Polymorphism should have specific steps."""
        finding = Finding(
            finding_id="CQA-003",
            severity=Severity.MEDIUM,
            category=Category.SOLID,
            file="test.py",
            line=30,
            title="OCP Violation: Type Check Chain",
            description="Multiple isinstance checks",
        )
        suggester = RefactorSuggester()
        refactoring = "Replace Conditional with Polymorphism"
        steps = suggester.generate_steps(finding, refactoring)

        assert len(steps) >= 3
        assert any("interface" in step.lower() or "base" in step.lower() for step in steps)
        assert any("implement" in step.lower() for step in steps)

    def test_generates_steps_for_inject_dependencies(self):
        """Inject Dependencies refactoring should have specific steps."""
        finding = Finding(
            finding_id="SOLID-001",
            severity=Severity.MEDIUM,
            category=Category.SOLID,
            file="test.py",
            line=10,
            title="DIP Violation: PaymentProcessor",
            description="Direct instantiation of dependencies",
        )
        suggester = RefactorSuggester()
        refactoring = "Inject Dependencies"
        steps = suggester.generate_steps(finding, refactoring)

        assert len(steps) >= 3
        assert any("parameter" in step.lower() or "__init__" in step.lower() for step in steps)

    def test_steps_include_file_reference(self):
        """Steps should reference the file from the finding when appropriate."""
        finding = Finding(
            finding_id="CQA-001",
            severity=Severity.MEDIUM,
            category=Category.CODE_SMELL,
            file="swarm_attack/agents/coder.py",
            line=50,
            title="Long Method: run",
            description="Method is 127 lines",
        )
        suggester = RefactorSuggester()
        steps = suggester.generate_steps(finding, "Extract Method")

        # At least some steps should be actionable
        assert len(steps) >= 2
        assert all(isinstance(step, str) for step in steps)
        assert all(len(step) > 10 for step in steps)  # Steps should be meaningful


# ============================================================
# Test: estimate_effort()
# ============================================================

class TestEstimateEffort:
    """Tests for the estimate_effort() method."""

    def test_estimates_small_for_parameter_object(self):
        """Introduce Parameter Object should be small effort."""
        finding = Finding(
            finding_id="CQA-001",
            severity=Severity.MEDIUM,
            category=Category.CODE_SMELL,
            file="test.py",
            line=10,
            title="Too Many Parameters",
            description="5 parameters",
        )
        suggester = RefactorSuggester()
        effort = suggester.estimate_effort(finding, "Introduce Parameter Object")
        assert effort == "small"

    def test_estimates_medium_for_extract_method(self):
        """Extract Method should be medium effort."""
        finding = Finding(
            finding_id="CQA-001",
            severity=Severity.MEDIUM,
            category=Category.CODE_SMELL,
            file="test.py",
            line=10,
            title="Long Method",
            description="75 lines",
        )
        suggester = RefactorSuggester()
        effort = suggester.estimate_effort(finding, "Extract Method")
        assert effort == "medium"

    def test_estimates_large_for_extract_class(self):
        """Extract Class should be large effort."""
        finding = Finding(
            finding_id="CQA-001",
            severity=Severity.MEDIUM,
            category=Category.CODE_SMELL,
            file="test.py",
            line=1,
            title="Large Class",
            description="450 lines",
        )
        suggester = RefactorSuggester()
        effort = suggester.estimate_effort(finding, "Extract Class")
        assert effort == "large"

    def test_estimates_medium_for_polymorphism(self):
        """Replace Conditional with Polymorphism should be medium effort."""
        finding = Finding(
            finding_id="CQA-001",
            severity=Severity.MEDIUM,
            category=Category.SOLID,
            file="test.py",
            line=30,
            title="OCP Violation",
            description="Type check chain",
        )
        suggester = RefactorSuggester()
        effort = suggester.estimate_effort(finding, "Replace Conditional with Polymorphism")
        assert effort == "medium"

    def test_estimates_small_for_inject_dependencies(self):
        """Inject Dependencies should be small effort."""
        finding = Finding(
            finding_id="SOLID-001",
            severity=Severity.MEDIUM,
            category=Category.SOLID,
            file="test.py",
            line=10,
            title="DIP Violation",
            description="Direct instantiation",
        )
        suggester = RefactorSuggester()
        effort = suggester.estimate_effort(finding, "Inject Dependencies")
        assert effort == "small"

    def test_estimates_small_for_hide_delegate(self):
        """Hide Delegate should be small effort."""
        finding = Finding(
            finding_id="CQA-001",
            severity=Severity.LOW,
            category=Category.CODE_SMELL,
            file="test.py",
            line=60,
            title="Message Chain",
            description="Long chain",
        )
        suggester = RefactorSuggester()
        effort = suggester.estimate_effort(finding, "Hide Delegate")
        assert effort == "small"

    def test_estimates_large_for_god_class_split(self):
        """Extract Class (split by responsibility) should be large effort."""
        finding = Finding(
            finding_id="CQA-001",
            severity=Severity.HIGH,
            category=Category.CODE_SMELL,
            file="test.py",
            line=1,
            title="God Class",
            description="Multiple responsibilities",
        )
        suggester = RefactorSuggester()
        effort = suggester.estimate_effort(finding, "Extract Class (split by responsibility)")
        assert effort == "large"

    def test_estimates_medium_for_unknown_refactoring(self):
        """Unknown refactoring type should default to medium effort."""
        finding = Finding(
            finding_id="CQA-001",
            severity=Severity.LOW,
            category=Category.CODE_SMELL,
            file="test.py",
            line=100,
            title="Unknown Issue",
            description="Some issue",
        )
        suggester = RefactorSuggester()
        effort = suggester.estimate_effort(finding, "Some Unknown Refactoring")
        assert effort == "medium"


# ============================================================
# Test: enrich_finding()
# ============================================================

class TestEnrichFinding:
    """Tests for the enrich_finding() method."""

    def test_enrich_finding_adds_refactoring_pattern(self):
        """enrich_finding should add refactoring_pattern to the finding."""
        finding = Finding(
            finding_id="CQA-001",
            severity=Severity.MEDIUM,
            category=Category.CODE_SMELL,
            file="test.py",
            line=10,
            title="Long Method: process",
            description="Method too long",
        )
        suggester = RefactorSuggester()
        enriched = suggester.enrich_finding(finding)

        assert enriched.refactoring_pattern == "Extract Method"

    def test_enrich_finding_adds_steps(self):
        """enrich_finding should add refactoring_steps to the finding."""
        finding = Finding(
            finding_id="CQA-001",
            severity=Severity.MEDIUM,
            category=Category.CODE_SMELL,
            file="test.py",
            line=10,
            title="Long Method: process",
            description="Method too long",
        )
        suggester = RefactorSuggester()
        enriched = suggester.enrich_finding(finding)

        assert len(enriched.refactoring_steps) >= 3
        assert all(isinstance(step, str) for step in enriched.refactoring_steps)

    def test_enrich_finding_adds_effort_estimate(self):
        """enrich_finding should add effort_estimate to the finding."""
        finding = Finding(
            finding_id="CQA-001",
            severity=Severity.MEDIUM,
            category=Category.CODE_SMELL,
            file="test.py",
            line=10,
            title="Long Method: process",
            description="Method too long",
        )
        suggester = RefactorSuggester()
        enriched = suggester.enrich_finding(finding)

        assert enriched.effort_estimate in ["small", "medium", "large"]

    def test_enrich_finding_preserves_original_fields(self):
        """enrich_finding should preserve all original finding fields."""
        finding = Finding(
            finding_id="CQA-001",
            severity=Severity.HIGH,
            category=Category.SOLID,
            file="swarm_attack/agents/coder.py",
            line=50,
            title="SRP Violation: CoderAgent",
            description="Class handles too many responsibilities",
            expert="Alexandra Vance",
            code_snippet="class CoderAgent:",
            priority=Priority.FIX_NOW,
            confidence=0.95,
        )
        suggester = RefactorSuggester()
        enriched = suggester.enrich_finding(finding)

        assert enriched.finding_id == "CQA-001"
        assert enriched.severity == Severity.HIGH
        assert enriched.category == Category.SOLID
        assert enriched.file == "swarm_attack/agents/coder.py"
        assert enriched.line == 50
        assert enriched.title == "SRP Violation: CoderAgent"
        assert enriched.description == "Class handles too many responsibilities"
        assert enriched.expert == "Alexandra Vance"
        assert enriched.code_snippet == "class CoderAgent:"
        assert enriched.priority == Priority.FIX_NOW
        assert enriched.confidence == 0.95

    def test_enrich_finding_does_not_mutate_original(self):
        """enrich_finding should return a new Finding, not mutate the original."""
        finding = Finding(
            finding_id="CQA-001",
            severity=Severity.MEDIUM,
            category=Category.CODE_SMELL,
            file="test.py",
            line=10,
            title="Long Method: process",
            description="Method too long",
            refactoring_pattern="",
            refactoring_steps=[],
            effort_estimate="medium",
        )
        original_pattern = finding.refactoring_pattern
        original_steps = finding.refactoring_steps.copy()

        suggester = RefactorSuggester()
        enriched = suggester.enrich_finding(finding)

        # Original should be unchanged
        assert finding.refactoring_pattern == original_pattern
        assert finding.refactoring_steps == original_steps
        # Enriched should be different
        assert enriched.refactoring_pattern != original_pattern
        assert len(enriched.refactoring_steps) > len(original_steps)

    def test_enrich_multiple_findings(self):
        """enrich_finding should work correctly for multiple findings."""
        findings = [
            Finding(
                finding_id="CQA-001",
                severity=Severity.MEDIUM,
                category=Category.CODE_SMELL,
                file="test.py",
                line=10,
                title="Long Method: process",
                description="Method too long",
            ),
            Finding(
                finding_id="CQA-002",
                severity=Severity.MEDIUM,
                category=Category.CODE_SMELL,
                file="test.py",
                line=100,
                title="Large Class: Manager",
                description="Class too large",
            ),
            Finding(
                finding_id="SOLID-001",
                severity=Severity.MEDIUM,
                category=Category.SOLID,
                file="test.py",
                line=200,
                title="DIP Violation: Service",
                description="Direct instantiation",
            ),
        ]

        suggester = RefactorSuggester()
        enriched = [suggester.enrich_finding(f) for f in findings]

        assert enriched[0].refactoring_pattern == "Extract Method"
        assert enriched[1].refactoring_pattern == "Extract Class"
        assert enriched[2].refactoring_pattern == "Inject Dependencies"


# ============================================================
# Test: SMELL_TO_REFACTORING mapping
# ============================================================

class TestSmellToRefactoringMapping:
    """Tests for the SMELL_TO_REFACTORING class attribute."""

    def test_mapping_contains_all_spec_smells(self):
        """SMELL_TO_REFACTORING should contain all smells from the spec."""
        expected_smells = [
            "long_method",
            "large_class",
            "feature_envy",
            "primitive_obsession",
            "switch_on_type",
            "too_many_parameters",
            "data_clump",
            "message_chain",
            "god_class",
            "deep_nesting",
            "duplicate_code",
        ]

        for smell in expected_smells:
            assert smell in RefactorSuggester.SMELL_TO_REFACTORING, f"Missing smell: {smell}"

    def test_mapping_values_are_valid_refactorings(self):
        """All mapping values should be valid refactoring pattern names."""
        valid_refactorings = [
            "Extract Method",
            "Extract Class",
            "Move Method",
            "Replace with Value Object",
            "Replace Conditional with Polymorphism",
            "Introduce Parameter Object",
            "Hide Delegate",
            "Extract Class (split by responsibility)",
            "Extract Method / Guard Clauses",
            "Extract Method or Base Class",
        ]

        for smell, refactoring in RefactorSuggester.SMELL_TO_REFACTORING.items():
            assert refactoring in valid_refactorings, f"Invalid refactoring for {smell}: {refactoring}"


# ============================================================
# Test: Integration with SmellDetector
# ============================================================

class TestIntegrationWithDetectors:
    """Tests for integration with SmellDetector and SOLIDChecker."""

    def test_enriches_smell_detector_finding(self):
        """Should correctly enrich findings from SmellDetector."""
        # Simulating a finding from SmellDetector
        finding = Finding(
            finding_id="CQA-001",
            severity=Severity.MEDIUM,
            category=Category.CODE_SMELL,
            file="test.py",
            line=10,
            title="Long Method: run",
            description="Method 'run' is 75 lines long, exceeding the threshold of 50 lines.",
            expert="Dr. Martin Chen",
            refactoring_pattern="Extract Method",  # Already set by detector
            refactoring_steps=[
                "Identify logical blocks within the method",
                "Extract each block to a well-named private method",
                "Replace inline code with calls to new methods",
            ],
        )

        suggester = RefactorSuggester()
        enriched = suggester.enrich_finding(finding)

        # Should still work even if some fields are pre-populated
        assert enriched.refactoring_pattern == "Extract Method"
        assert len(enriched.refactoring_steps) >= 3

    def test_enriches_solid_checker_finding(self):
        """Should correctly enrich findings from SOLIDChecker."""
        # Simulating a finding from SOLIDChecker
        finding = Finding(
            finding_id="SOLID-001",
            severity=Severity.MEDIUM,
            category=Category.SOLID,
            file="test.py",
            line=10,
            title="DIP Violation: MyService",
            description="Class 'MyService' instantiates its dependencies directly",
            expert="Alexandra Vance",
        )

        suggester = RefactorSuggester()
        enriched = suggester.enrich_finding(finding)

        assert enriched.refactoring_pattern == "Inject Dependencies"
        assert len(enriched.refactoring_steps) >= 3
        assert enriched.effort_estimate == "small"
