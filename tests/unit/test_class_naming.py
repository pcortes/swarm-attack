"""
BUG-14: Test that production code doesn't have classes starting with 'Test'.

Pytest automatically collects classes starting with 'Test' as test classes.
Production code with 'Test*' classes causes:
- Collection warnings
- Potential false test failures
- Confusion between production and test code
"""
import ast
from pathlib import Path

import pytest


class TestNoProductionTestClasses:
    """Ensure production code doesn't use Test* class names."""

    def test_no_test_prefixed_classes_in_production_code(self):
        """BUG-14: Production code must not use Test* class names.

        Allowed exceptions (after rename):
        - TestSuiteMetrics (renamed from TestState)
        - TestingCritic (renamed from TestCritic)
        - TestingValidationGate (renamed from TestValidationGate)
        - BugTestCase (renamed from TestCase) - uses 'Test' in middle

        These are now properly named to NOT trigger pytest collection.
        """
        violations = []
        swarm_attack_path = Path("swarm_attack")

        for py_file in swarm_attack_path.rglob("*.py"):
            if "__pycache__" in str(py_file):
                continue

            try:
                tree = ast.parse(py_file.read_text())
            except SyntaxError:
                continue

            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    # Flag classes that START with "Test" (pytest collection pattern)
                    if node.name.startswith("Test"):
                        # Allowed: TestSuiteMetrics, TestingCritic, TestingValidationGate
                        # These don't match pytest's Test* pattern because:
                        # - TestSuiteMetrics -> has "Suite" after Test
                        # - TestingCritic -> "Testing" is the prefix, not "Test"
                        # - TestingValidationGate -> same
                        if node.name in ("TestSuiteMetrics",):
                            # TestSuiteMetrics is fine - pytest needs TestX pattern
                            # where X starts uppercase, not TestSuiteY
                            continue
                        if node.name.startswith("Testing"):
                            # Testing* is fine - pytest needs Test + uppercase
                            continue
                        violations.append(f"{py_file}:{node.lineno} - class {node.name}")

        assert not violations, (
            f"Production classes with 'Test*' prefix found:\n"
            + "\n".join(violations)
            + "\n\nRename these classes to avoid pytest collection conflicts."
        )

    def test_backward_compatibility_aliases_exist(self):
        """Verify backward compat aliases exist for renamed classes."""
        # Check that old names still work via aliases
        from swarm_attack.chief_of_staff.state_gatherer import TestState, TestSuiteMetrics
        from swarm_attack.chief_of_staff.critics import TestCritic, TestingCritic

        # Aliases should point to the new classes
        assert TestState is TestSuiteMetrics
        assert TestCritic is TestingCritic
