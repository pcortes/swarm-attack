"""Tests for TDD plan generation functionality."""

import pytest

from swarm_attack.commit_review.tdd_generator import (
    TDDPlanGenerator,
    generate_red_phase,
    generate_green_phase,
    generate_refactor_phase,
)
from swarm_attack.commit_review.models import Finding, Severity, TDDPlan


class TestTDDPlanGenerator:
    """Tests for TDDPlanGenerator."""

    def _make_finding(
        self,
        description: str = "Test finding",
        evidence: str = "file.py:10",
        severity: Severity = Severity.MEDIUM,
    ) -> Finding:
        """Helper to create a Finding for testing."""
        return Finding(
            commit_sha="abc123",
            expert="test_expert",
            severity=severity,
            category="quality",
            description=description,
            evidence=evidence,
        )

    def test_generate_red_phase(self):
        """Generates failing test descriptions for issues."""
        finding = self._make_finding(
            description="Missing error handling for null input",
            evidence="parser.py:45",
        )

        red_phase = generate_red_phase(finding)

        # Should contain test description
        assert "test" in red_phase.lower()

        # Should reference the issue
        assert "null" in red_phase.lower() or "error" in red_phase.lower()

        # Should reference the file
        assert "parser" in red_phase.lower()

    def test_generate_green_phase(self):
        """Generates minimal fix steps."""
        finding = self._make_finding(
            description="Missing error handling for null input",
            evidence="parser.py:45",
        )

        green_phase = generate_green_phase(finding)

        # Should contain implementation guidance
        assert len(green_phase) > 0

        # Should be actionable steps
        assert "add" in green_phase.lower() or "implement" in green_phase.lower() or "handle" in green_phase.lower()

    def test_generate_refactor_phase(self):
        """Generates cleanup suggestions."""
        finding = self._make_finding(
            description="Code duplication in error handling",
            evidence="parser.py:45",
        )

        refactor_phase = generate_refactor_phase(finding)

        # Should contain refactoring suggestions
        assert len(refactor_phase) > 0

    def test_generate_full_plan(self):
        """Generates complete TDD plan from finding."""
        generator = TDDPlanGenerator()
        finding = self._make_finding(
            description="Missing validation for user input",
            evidence="api.py:100",
        )

        plan = generator.generate_plan(finding)

        # Should be a TDDPlan
        assert isinstance(plan, TDDPlan)

        # Should have all three phases
        assert plan.red_phase is not None
        assert plan.green_phase is not None
        assert plan.refactor_phase is not None

    def test_generate_plan_includes_evidence(self):
        """Plan includes file:line references from finding."""
        generator = TDDPlanGenerator()
        finding = self._make_finding(
            description="Bug in authentication",
            evidence="auth.py:25",
        )

        plan = generator.generate_plan(finding)

        # Plan should reference the file
        full_plan = f"{plan.red_phase} {plan.green_phase} {plan.refactor_phase}"
        assert "auth" in full_plan.lower()

    def test_skip_low_severity(self):
        """Does not generate plan for low severity findings."""
        generator = TDDPlanGenerator()
        finding = self._make_finding(
            description="Minor style issue",
            severity=Severity.LOW,
        )

        plan = generator.generate_plan(finding)

        # Low severity should return None or minimal plan
        assert plan is None or plan.red_phase == ""

    def test_prioritize_critical(self):
        """Critical findings get detailed plans."""
        generator = TDDPlanGenerator()
        finding = self._make_finding(
            description="Security vulnerability in auth",
            evidence="auth.py:50",
            severity=Severity.CRITICAL,
        )

        plan = generator.generate_plan(finding)

        # Critical findings should have comprehensive plans
        assert plan is not None
        assert len(plan.red_phase) > 20
        assert len(plan.green_phase) > 20
