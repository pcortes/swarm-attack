# tests/unit/test_no_test_prefix_classes.py
"""Tests for production class naming (BUG-13, BUG-14)."""
import ast
from pathlib import Path


def test_no_production_classes_named_test():
    """BUG-13, BUG-14: Production code must not use Test* class names.

    pytest collects classes named Test* as test classes, causing warnings
    and collection issues when they're in production code.
    """
    violations = []
    for py_file in Path("swarm_attack").rglob("*.py"):
        try:
            tree = ast.parse(py_file.read_text())
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef) and node.name.startswith("Test"):
                    violations.append(f"{py_file}:{node.lineno} - {node.name}")
        except SyntaxError:
            pass  # Skip files with syntax errors

    assert not violations, f"Production Test* classes found:\n" + "\n".join(violations)
