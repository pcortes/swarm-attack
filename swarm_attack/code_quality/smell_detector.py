"""Code smell detection using AST analysis.

This module provides detection of common code smells:
- Long Method (> 50 lines)
- Large Class (> 300 lines)
- Deep Nesting (> 4 levels)
- Too Many Parameters (> 3 parameters)

Based on the Code Quality spec anti-patterns section.
"""

import ast
from pathlib import Path
from typing import Union

from .models import Finding, Severity, Category, Priority


class SmellDetector:
    """Detects code smells using AST analysis.

    Thresholds are based on the spec:
    - Method > 50 lines = Long Method smell (medium severity)
    - Class > 300 lines = Large Class smell (medium severity)
    - Nesting > 4 levels = Deep Nesting smell (medium severity)
    - Parameters > 3 = Too Many Parameters (medium severity)
    """

    # Thresholds from spec
    MAX_METHOD_LINES = 50
    MAX_CLASS_LINES = 300
    MAX_NESTING_DEPTH = 4
    MAX_PARAMETERS = 3

    # Finding ID counter
    _finding_counter = 0

    def _next_finding_id(self) -> str:
        """Generate the next finding ID."""
        SmellDetector._finding_counter += 1
        return f"CQA-{SmellDetector._finding_counter:03d}"

    def analyze_file(self, file_path: Union[Path, str]) -> list[Finding]:
        """Analyze a Python file for code smells.

        Args:
            file_path: Path to the Python file to analyze.

        Returns:
            List of Finding objects for any code smells detected.
            Returns empty list if file cannot be parsed or doesn't exist.
        """
        file_path = Path(file_path)

        # Handle non-existent files gracefully
        if not file_path.exists():
            return []

        try:
            source = file_path.read_text()
            tree = ast.parse(source)
        except (SyntaxError, ValueError, OSError):
            # Handle syntax errors and other parsing issues gracefully
            return []

        findings: list[Finding] = []
        file_str = str(file_path)

        # Run all detection methods
        findings.extend(self.detect_long_methods(tree, file_str))
        findings.extend(self.detect_large_classes(tree, file_str))
        findings.extend(self.detect_deep_nesting(tree, file_str))
        findings.extend(self.detect_too_many_parameters(tree, file_str))

        return findings

    def detect_long_methods(self, tree: ast.AST, file_path: str) -> list[Finding]:
        """Find methods > 50 lines.

        Args:
            tree: The parsed AST of the file.
            file_path: Path to the file being analyzed.

        Returns:
            List of findings for long methods.
        """
        findings: list[Finding] = []

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                line_count = self._count_lines(node)

                if line_count > self.MAX_METHOD_LINES:
                    # Find the class name if this is a method
                    class_name = self._find_parent_class(tree, node)
                    method_name = node.name
                    full_name = f"{class_name}.{method_name}" if class_name else method_name

                    findings.append(Finding(
                        finding_id=self._next_finding_id(),
                        severity=Severity.MEDIUM,
                        category=Category.CODE_SMELL,
                        file=file_path,
                        line=node.lineno,
                        title=f"Long Method: {method_name}",
                        description=(
                            f"Method '{full_name}' is {line_count} lines long, "
                            f"exceeding the threshold of {self.MAX_METHOD_LINES} lines. "
                            f"Consider extracting smaller methods."
                        ),
                        code_snippet=f"def {method_name}(...):",
                        expert="Dr. Martin Chen",
                        refactoring_pattern="Extract Method",
                        refactoring_steps=[
                            "Identify logical blocks within the method",
                            "Extract each block to a well-named private method",
                            "Replace inline code with calls to new methods",
                        ],
                        priority=Priority.FIX_LATER,
                        effort_estimate="medium",
                        confidence=0.95,
                    ))

        return findings

    def detect_large_classes(self, tree: ast.AST, file_path: str) -> list[Finding]:
        """Find classes > 300 lines.

        Args:
            tree: The parsed AST of the file.
            file_path: Path to the file being analyzed.

        Returns:
            List of findings for large classes.
        """
        findings: list[Finding] = []

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                line_count = self._count_lines(node)

                if line_count > self.MAX_CLASS_LINES:
                    findings.append(Finding(
                        finding_id=self._next_finding_id(),
                        severity=Severity.MEDIUM,
                        category=Category.CODE_SMELL,
                        file=file_path,
                        line=node.lineno,
                        title=f"Large Class: {node.name}",
                        description=(
                            f"Class '{node.name}' is {line_count} lines long, "
                            f"exceeding the threshold of {self.MAX_CLASS_LINES} lines. "
                            f"Consider splitting into smaller classes."
                        ),
                        code_snippet=f"class {node.name}:",
                        expert="Dr. Martin Chen",
                        refactoring_pattern="Extract Class",
                        refactoring_steps=[
                            "Identify groups of related methods and fields",
                            "Create new classes for each responsibility",
                            "Move methods and fields to appropriate classes",
                            "Use composition to connect the classes",
                        ],
                        priority=Priority.FIX_LATER,
                        effort_estimate="large",
                        confidence=0.90,
                    ))

        return findings

    def detect_deep_nesting(self, tree: ast.AST, file_path: str) -> list[Finding]:
        """Find nesting > 4 levels.

        Args:
            tree: The parsed AST of the file.
            file_path: Path to the file being analyzed.

        Returns:
            List of findings for deeply nested code.
        """
        findings: list[Finding] = []

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                max_depth = self._measure_nesting_depth(node)

                if max_depth > self.MAX_NESTING_DEPTH:
                    # Find the class name if this is a method
                    class_name = self._find_parent_class(tree, node)
                    method_name = node.name
                    full_name = f"{class_name}.{method_name}" if class_name else method_name

                    findings.append(Finding(
                        finding_id=self._next_finding_id(),
                        severity=Severity.MEDIUM,
                        category=Category.CODE_SMELL,
                        file=file_path,
                        line=node.lineno,
                        title=f"Deep Nesting: {method_name}",
                        description=(
                            f"Function '{full_name}' has {max_depth} levels of nesting, "
                            f"exceeding the threshold of {self.MAX_NESTING_DEPTH} levels. "
                            f"Consider extracting methods or using guard clauses."
                        ),
                        code_snippet=f"def {method_name}(...):",
                        expert="Dr. Martin Chen",
                        refactoring_pattern="Replace Nested Conditional with Guard Clauses",
                        refactoring_steps=[
                            "Convert outer conditions to early returns (guard clauses)",
                            "Extract deeply nested blocks to separate methods",
                            "Consider using strategy pattern for complex conditionals",
                        ],
                        priority=Priority.FIX_LATER,
                        effort_estimate="medium",
                        confidence=0.85,
                    ))

        return findings

    def detect_too_many_parameters(self, tree: ast.AST, file_path: str) -> list[Finding]:
        """Find functions with > 3 parameters.

        Note: 'self' and 'cls' are excluded from the count as they are
        conventional first parameters in methods.

        Args:
            tree: The parsed AST of the file.
            file_path: Path to the file being analyzed.

        Returns:
            List of findings for functions with too many parameters.
        """
        findings: list[Finding] = []

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                # Get all parameter names
                param_names = [arg.arg for arg in node.args.args]

                # Exclude 'self' and 'cls' from count
                real_params = [p for p in param_names if p not in ('self', 'cls')]
                param_count = len(real_params)

                if param_count > self.MAX_PARAMETERS:
                    # Find the class name if this is a method
                    class_name = self._find_parent_class(tree, node)
                    method_name = node.name
                    full_name = f"{class_name}.{method_name}" if class_name else method_name

                    findings.append(Finding(
                        finding_id=self._next_finding_id(),
                        severity=Severity.MEDIUM,
                        category=Category.CODE_SMELL,
                        file=file_path,
                        line=node.lineno,
                        title=f"Too Many Parameters: {method_name}",
                        description=(
                            f"Function '{full_name}' has {param_count} parameters, "
                            f"exceeding the threshold of {self.MAX_PARAMETERS}. "
                            f"Consider using a parameter object."
                        ),
                        code_snippet=f"def {method_name}({', '.join(param_names)}):",
                        expert="Dr. Martin Chen",
                        refactoring_pattern="Introduce Parameter Object",
                        refactoring_steps=[
                            "Create a dataclass to hold related parameters",
                            "Replace multiple parameters with the new object",
                            "Update all call sites to use the new object",
                        ],
                        priority=Priority.FIX_LATER,
                        effort_estimate="small",
                        confidence=0.90,
                    ))

        return findings

    def _count_lines(self, node: ast.AST) -> int:
        """Count lines in an AST node.

        Args:
            node: The AST node to count lines for.

        Returns:
            Number of lines the node spans.
        """
        if not hasattr(node, 'lineno') or not hasattr(node, 'end_lineno'):
            return 0

        return node.end_lineno - node.lineno + 1

    def _measure_nesting_depth(self, node: ast.AST, current_depth: int = 0) -> int:
        """Measure maximum nesting depth within an AST node.

        Args:
            node: The AST node to measure.
            current_depth: The current nesting depth (for recursion).

        Returns:
            Maximum nesting depth found within the node.
        """
        max_depth = current_depth

        # Types that increase nesting depth
        nesting_types = (ast.If, ast.For, ast.While, ast.With, ast.Try)

        for child in ast.iter_child_nodes(node):
            if isinstance(child, nesting_types):
                # This child increases nesting
                child_max = self._measure_nesting_depth(child, current_depth + 1)
                max_depth = max(max_depth, child_max)
            else:
                # Recurse without increasing depth
                child_max = self._measure_nesting_depth(child, current_depth)
                max_depth = max(max_depth, child_max)

        return max_depth

    def _find_parent_class(self, tree: ast.AST, target_func: ast.FunctionDef) -> str | None:
        """Find the parent class name for a method.

        Args:
            tree: The full AST tree.
            target_func: The function node to find the parent class for.

        Returns:
            The class name if the function is a method, None otherwise.
        """
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                for child in ast.iter_child_nodes(node):
                    if child is target_func:
                        return node.name
        return None
