"""TDD plan generation for code quality findings.

This module provides the TDDGenerator class which generates Test-Driven
Development plans from code quality findings. Each plan includes:
- RED phase: Write a failing test that exposes the issue
- GREEN phase: Make minimal changes to pass the test
- REFACTOR phase: Clean up without changing behavior

Based on the Code Quality spec TDD protocol section.
"""

from pathlib import Path
from typing import Any

from .models import Finding, TDDPlan, TDDPhase, Category


class TDDGenerator:
    """Generates TDD plans for refactoring findings.

    This class creates complete TDD plans (red/green/refactor) for code
    quality findings. Each plan provides:
    - A failing test that exposes the quality issue
    - Minimal changes to make the test pass
    - Cleanup activities to polish the code

    The generated plans are tailored to the type of issue (code smell,
    SOLID violation, LLM hallucination, error handling, etc.).
    """

    # Test templates by category and smell type
    _TEST_TEMPLATES: dict[str, dict[str, str]] = {
        "code_smell": {
            "Long Method": '''def test_{method_name}_complexity():
    """Method should have low cyclomatic complexity."""
    from radon.complexity import cc_visit
    import ast

    with open("{file_path}") as f:
        code = f.read()

    tree = ast.parse(code)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "{method_name}":
            complexity = cc_visit(ast.unparse(node))[0].complexity
            assert complexity <= 10, f"Complexity is {{complexity}}, should be <= 10"
''',
            "Large Class": '''def test_{class_name}_lines():
    """Class should not exceed 300 lines."""
    import ast

    with open("{file_path}") as f:
        code = f.read()

    tree = ast.parse(code)
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "{class_name}":
            line_count = node.end_lineno - node.lineno + 1
            assert line_count <= 300, f"Class has {{line_count}} lines, should be <= 300"
''',
            "Deep Nesting": '''def test_{method_name}_nesting_depth():
    """Method should not have deeply nested code."""
    import ast

    def measure_depth(node, depth=0):
        max_depth = depth
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.If, ast.For, ast.While, ast.With)):
                max_depth = max(max_depth, measure_depth(child, depth + 1))
            else:
                max_depth = max(max_depth, measure_depth(child, depth))
        return max_depth

    with open("{file_path}") as f:
        tree = ast.parse(f.read())

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "{method_name}":
            depth = measure_depth(node)
            assert depth <= 4, f"Nesting depth is {{depth}}, should be <= 4"
''',
            "Too Many Parameters": '''def test_{method_name}_parameters():
    """Method should have at most 3 parameters (excluding self/cls)."""
    import ast

    with open("{file_path}") as f:
        tree = ast.parse(f.read())

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "{method_name}":
            params = [p.arg for p in node.args.args if p.arg not in ("self", "cls")]
            assert len(params) <= 3, f"Has {{len(params)}} params, should be <= 3"
''',
        },
        "llm_hallucination": {
            "Hallucinated Import": '''def test_no_hallucinated_imports():
    """All imports should resolve to real modules."""
    import importlib.util
    import ast

    with open("{file_path}") as f:
        tree = ast.parse(f.read())

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                spec = importlib.util.find_spec(alias.name)
                assert spec is not None, f"Import {{alias.name}} does not exist"
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                spec = importlib.util.find_spec(node.module)
                assert spec is not None, f"Import {{node.module}} does not exist"
''',
            "Hallucinated API": '''def test_no_hallucinated_api_calls():
    """All method calls should exist on their classes."""
    import ast
    import inspect

    # Import the module and verify the API exists
    with open("{file_path}") as f:
        code = f.read()

    tree = ast.parse(code)
    # Verify all imports resolve and called methods exist
    assert True  # Replace with specific API verification
''',
        },
        "error_handling": {
            "Missing Error Handling": '''def test_file_operation_handles_errors():
    """File operations should handle IOError gracefully."""
    from {module_path} import {class_name}

    instance = {class_name}()

    # Should not raise, should return error result
    result = instance.{method_name}("/nonexistent/path")
    assert hasattr(result, "error") or result is None or isinstance(result, dict)
    # Verify error is communicated, not raised
''',
            "Swallowed Exception": '''def test_exception_not_swallowed():
    """Exceptions should be logged or propagated, not silently swallowed."""
    import ast

    with open("{file_path}") as f:
        tree = ast.parse(f.read())

    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler):
            # Exception handler should have a body beyond just 'pass'
            assert not (len(node.body) == 1 and isinstance(node.body[0], ast.Pass)), \\
                "Empty except block found - exception is swallowed"
''',
            "Bare Except": '''def test_no_bare_except():
    """All except blocks should specify an exception type."""
    import ast

    with open("{file_path}") as f:
        tree = ast.parse(f.read())

    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler):
            assert node.type is not None, \\
                "Bare except found - should specify exception type"
''',
        },
        "solid": {
            "SRP Violation": '''def test_single_responsibility():
    """Class should have a single responsibility."""
    import ast

    with open("{file_path}") as f:
        tree = ast.parse(f.read())

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "{class_name}":
            methods = [n.name for n in node.body if isinstance(n, ast.FunctionDef)]
            # Heuristic: methods with very different prefixes indicate multiple responsibilities
            # This is a basic check - real detection would be more sophisticated
            assert True  # Replace with specific responsibility check
''',
        },
        "incomplete": {
            "TODO in Code": '''def test_no_todos_in_production_code():
    """Production code should not have TODO/FIXME comments."""
    with open("{file_path}") as f:
        code = f.read()

    assert "TODO" not in code, "Found TODO in production code"
    assert "FIXME" not in code, "Found FIXME in production code"
''',
            "Placeholder Return": '''def test_no_placeholder_returns():
    """Methods should not return placeholder values."""
    import ast

    with open("{file_path}") as f:
        tree = ast.parse(f.read())

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "{method_name}":
            for child in ast.walk(node):
                if isinstance(child, ast.Return):
                    # Check for placeholder returns: None, {{}}, 0
                    if child.value is None:
                        continue  # None might be intentional
                    if isinstance(child.value, ast.Dict) and not child.value.keys:
                        assert False, "Found empty dict placeholder return"
''',
        },
    }

    # Generic fallback template
    _GENERIC_TEMPLATE = '''def test_{identifier}_quality():
    """Verify code quality issue is fixed."""
    # This test should fail before the fix and pass after
    # Customize this test based on the specific issue

    # Example: Check that the problematic pattern no longer exists
    with open("{file_path}") as f:
        code = f.read()

    # Add specific assertions based on the finding
    assert True  # Replace with actual verification
'''

    def generate_plan(self, finding: Finding) -> TDDPlan:
        """Generate a complete TDD plan for a finding.

        Args:
            finding: The code quality finding to generate a plan for.

        Returns:
            A TDDPlan with red, green, and refactor phases.
        """
        red_phase = self.generate_red_phase(finding)
        green_phase = self.generate_green_phase(finding)
        refactor_phase = self.generate_refactor_phase(finding)

        return TDDPlan(
            red=red_phase,
            green=green_phase,
            refactor=refactor_phase,
        )

    def generate_red_phase(self, finding: Finding) -> TDDPhase:
        """Generate RED phase: failing test that exposes the issue.

        Args:
            finding: The code quality finding.

        Returns:
            TDDPhase with test file and test code.
        """
        # Determine test file path based on the source file
        source_path = Path(finding.file)
        test_file = self._derive_test_file_path(source_path)

        # Get the appropriate test template
        category_str = finding.category.value
        smell_type = self._extract_smell_type(finding.title)
        test_code = self._get_test_template(category_str, smell_type)

        # Fill in template placeholders
        test_code = self._fill_template(test_code, finding)

        description = (
            f"Write failing test that exposes the {smell_type} issue. "
            f"This test should FAIL with the current code and PASS after the fix."
        )

        return TDDPhase(
            description=description,
            test_file=test_file,
            test_code=test_code,
            changes=[],
        )

    def generate_green_phase(self, finding: Finding) -> TDDPhase:
        """Generate GREEN phase: minimal change to pass test.

        Args:
            finding: The code quality finding.

        Returns:
            TDDPhase with changes to make.
        """
        # Build changes from refactoring steps
        changes: list[dict[str, Any]] = []

        # Primary change: the refactoring
        primary_change = {
            "file": finding.file,
            "action": finding.refactoring_pattern,
            "steps": finding.refactoring_steps if finding.refactoring_steps else [
                "Apply the minimal fix to resolve the issue"
            ],
        }
        changes.append(primary_change)

        description = (
            f"Make minimal changes to pass the test. "
            f"Apply '{finding.refactoring_pattern}' refactoring."
        )

        return TDDPhase(
            description=description,
            test_file="",
            test_code="",
            changes=changes,
        )

    def generate_refactor_phase(self, finding: Finding) -> TDDPhase:
        """Generate REFACTOR phase: polish without behavior change.

        Args:
            finding: The code quality finding.

        Returns:
            TDDPhase with cleanup activities.
        """
        # Standard refactor activities from the spec
        changes = [
            "Add docstrings to new/modified methods",
            "Ensure type hints are complete",
            "Improve variable/method names if needed",
            "Remove dead code",
            "Verify all tests still pass",
        ]

        description = (
            "Clean up without changing behavior. "
            "Polish the code with documentation and type hints."
        )

        return TDDPhase(
            description=description,
            test_file="",
            test_code="",
            changes=changes,
        )

    def _get_test_template(self, category: str, smell_type: str) -> str:
        """Get test code template for a specific smell type.

        Args:
            category: The category of the finding (e.g., "code_smell").
            smell_type: The specific smell type (e.g., "Long Method").

        Returns:
            A test code template string.
        """
        # Look up in category-specific templates
        if category in self._TEST_TEMPLATES:
            category_templates = self._TEST_TEMPLATES[category]
            if smell_type in category_templates:
                return category_templates[smell_type]

            # Try partial match (e.g., "Long Method" in "Long Method: run()")
            for key, template in category_templates.items():
                if key in smell_type or smell_type in key:
                    return template

        # Return generic template for unknown types
        return self._GENERIC_TEMPLATE

    def _derive_test_file_path(self, source_path: Path) -> str:
        """Derive the test file path from the source file path.

        Args:
            source_path: Path to the source file.

        Returns:
            Path to the corresponding test file.
        """
        # Convert source path to test path
        # e.g., swarm_attack/agents/coder.py -> tests/unit/agents/test_coder.py
        parts = source_path.parts

        # Find the module root (e.g., "swarm_attack")
        if "swarm_attack" in parts:
            idx = parts.index("swarm_attack")
            relative_parts = parts[idx + 1:]
        else:
            relative_parts = parts

        # Build test path
        if relative_parts:
            test_dir = "/".join(["tests", "unit"] + list(relative_parts[:-1]))
            test_filename = f"test_{source_path.name}"
            return f"{test_dir}/{test_filename}"
        else:
            return f"tests/unit/test_{source_path.name}"

    def _extract_smell_type(self, title: str) -> str:
        """Extract the smell type from a finding title.

        Args:
            title: The finding title (e.g., "Long Method: run()").

        Returns:
            The smell type (e.g., "Long Method").
        """
        # Handle formats like "Long Method: run()" or "Hallucinated Import: magic_helper"
        if ":" in title:
            return title.split(":")[0].strip()
        return title

    def _fill_template(self, template: str, finding: Finding) -> str:
        """Fill in template placeholders with finding data.

        Args:
            template: The template string with placeholders.
            finding: The finding to extract data from.

        Returns:
            The filled-in template.
        """
        # Extract method name from title or description
        method_name = self._extract_identifier(finding.title, finding.description)
        class_name = self._extract_class_name(finding.title, finding.description)

        # Build module path from file path for imports
        file_path = Path(finding.file)
        module_path = str(file_path.with_suffix("")).replace("/", ".")

        # Fill placeholders
        result = template.replace("{file_path}", finding.file)
        result = result.replace("{method_name}", method_name)
        result = result.replace("{class_name}", class_name)
        result = result.replace("{module_path}", module_path)
        result = result.replace("{identifier}", method_name or "issue")

        return result

    def _extract_identifier(self, title: str, description: str) -> str:
        """Extract a method or function identifier from title/description.

        Args:
            title: The finding title.
            description: The finding description.

        Returns:
            The identifier (method/function name).
        """
        # Try to extract from title like "Long Method: run()"
        if ":" in title:
            identifier = title.split(":")[1].strip()
            # Remove parentheses if present
            if "(" in identifier:
                identifier = identifier.split("(")[0]
            return identifier

        # Try to extract from description
        # Look for patterns like "Method 'xxx'" or "Function 'xxx'"
        for pattern in ["Method '", "Function '", "method '", "function '"]:
            if pattern in description:
                start = description.index(pattern) + len(pattern)
                end = description.index("'", start)
                return description[start:end].split(".")[-1]

        return "method"

    def _extract_class_name(self, title: str, description: str) -> str:
        """Extract a class name from title/description.

        Args:
            title: The finding title.
            description: The finding description.

        Returns:
            The class name or a default.
        """
        # Try to extract from title like "Large Class: Dispatcher"
        if "Class:" in title:
            class_name = title.split(":")[1].strip()
            return class_name

        # Try to extract from description
        for pattern in ["Class '", "class '"]:
            if pattern in description:
                start = description.index(pattern) + len(pattern)
                end = description.index("'", start)
                return description[start:end]

        return "TargetClass"
